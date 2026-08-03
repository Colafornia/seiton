import json
import io
import os
import subprocess
import sys
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from os import terminal_size
from pathlib import Path
from unittest.mock import patch

from scripts import use

ROOT = Path(__file__).resolve().parents[1]


def isolated_env(root):
    return {
        "HOME": str(root / "home"),
        "CODEX_HOME": str(root / "codex"),
        "CLAUDE_CONFIG_DIR": str(root / "claude"),
    }


def run_cli(project, *args):
    return subprocess.run(
        [
            sys.executable,
            str(ROOT / "scripts/use.py"),
            *args,
            "--project",
            str(project),
        ],
        text=True,
        capture_output=True,
        env={**os.environ, **isolated_env(project)},
    )


class UseSkillsTest(unittest.TestCase):
    def test_legacy_top_level_selection_options_are_rejected(self):
        parser = use.build_parser()

        for option in (["--catalog"], ["--skill", "tdd"], ["--profile", "review"]):
            with self.subTest(option=option), redirect_stderr(io.StringIO()):
                with self.assertRaises(SystemExit):
                    parser.parse_args(option)

    def test_catalog_commands_reject_project_option(self):
        parser = use.build_parser()

        for command in (
            ["add", "owner/repo", "tdd"],
            ["restore"],
            ["update", "tdd"],
        ):
            with self.subTest(command=command), redirect_stderr(io.StringIO()):
                with self.assertRaises(SystemExit):
                    parser.parse_args([*command, "--project", "/tmp/project"])

    def test_ls_alias_is_preserved(self):
        self.assertEqual(use.build_parser().parse_args(["ls"]).command, "ls")

    def test_local_profiles_override_shared_profiles(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "skillsets.toml").write_text(
                '[profiles.review]\nskills = ["deliver"]\n', encoding="utf-8"
            )
            (root / ".agent").mkdir()
            (root / ".agent/skillsets.toml").write_text(
                '[profiles.review]\nskills = ["code-review"]\n', encoding="utf-8"
            )

            self.assertEqual(
                use.profiles(root), {"review": {"skills": ["code-review"]}}
            )

    def test_use_rejects_skill_names_with_profile(self):
        with tempfile.TemporaryDirectory() as directory, redirect_stderr(io.StringIO()):
            result = use.main(
                [
                    "use",
                    "tdd",
                    "--profile",
                    "delivery",
                    "--project",
                    directory,
                    "--dry-run",
                ]
            )

        self.assertEqual(result, 1)

    def test_catalog_metadata_and_author_grouping(self):
        with tempfile.TemporaryDirectory() as directory:
            project = Path(directory)
            source = project / "example"
            source.mkdir()
            (source / "SKILL.md").write_text(
                "---\n"
                "name: example\n"
                "description: >\n"
                "  First line.\n"
                "  Second line.\n"
                "---\n"
                "# Example Skill\n",
                encoding="utf-8",
            )

            payload = use.catalog_payload(
                project,
                {"example": source.resolve()},
                {"example": {"source": "alice/tools"}},
                {},
            )

            self.assertEqual(
                payload["groups"]["open_source"]["alice"],
                [
                    {
                        "name": "example",
                        "title": "Example Skill",
                        "description": "First line. Second line.",
                        "installed": True,
                    }
                ],
            )

    def test_no_arguments_is_read_only_status(self):
        with tempfile.TemporaryDirectory() as directory:
            project = Path(directory)
            result = subprocess.run(
                [sys.executable, str(ROOT / "scripts/use.py")],
                cwd=project,
                text=True,
                capture_output=True,
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn(f"seiton status  {project.resolve()}", result.stdout)
            self.assertIn("✓ synced  codex:0  claude:0", result.stdout)
            self.assertIn("codex\n├── seiton", result.stdout)
            self.assertIn("claude\n├── seiton", result.stdout)
            self.assertIn("directory view only, not full runtime", result.stdout)
            self.assertFalse((project / ".agents").exists())
            self.assertFalse((project / ".claude").exists())

    def test_status_text_only_explains_unhealthy_entries(self):
        project = Path("/project")
        payload = {
            "project": str(project),
            "clients": {
                "codex": {
                    "seiton": [
                        {
                            "name": "ready",
                            "path": "/project/.agents/skills/ready",
                            "target": "/catalog/ready",
                            "health": "healthy",
                            "source": "owner/repo",
                        },
                        {
                            "name": "missing",
                            "path": "/project/.agents/skills/missing",
                            "target": "/catalog/missing",
                            "health": "broken",
                            "source": "owner/repo",
                        },
                    ],
                    "project": [],
                    "global": [],
                },
                "claude": {"seiton": [], "project": [], "global": []},
            },
            "conflicts": [],
            "synced": False,
            "context": {
                "discovery_tokens": 0,
                "body_tokens_if_invoked": 0,
                "measured": [],
                "approximate": True,
            },
        }
        output = io.StringIO()
        with (
            patch("scripts.use.global_skills_paths", return_value=[Path("/global")]),
            redirect_stdout(output),
        ):
            use.print_status(payload)

        text = output.getvalue()
        self.assertIn("│   └── owner/repo\n│       ├── ready", text)
        self.assertNotIn("healthy", text)
        self.assertNotIn("/catalog/ready", text)
        self.assertIn("missing [broken] -> /catalog/missing", text)

    def test_catalog_is_a_compact_table_that_fits_the_terminal(self):
        payload = {
            "profiles": {
                "delivery": {"skills": ["deliver", "debug", "tdd"]},
            },
            "groups": {
                "owned": [
                    {
                        "name": "deliver",
                        "title": "Deliver",
                        "description": "A deliberately long description that must be truncated.",
                        "installed": True,
                    }
                ],
                "local": [],
                "open_source": {
                    "alice": [
                        {
                            "name": "debug",
                            "title": "Debug",
                            "description": "Diagnose failures.",
                            "installed": False,
                        }
                    ]
                },
            },
        }
        output = io.StringIO()
        with (
            patch("scripts.use.shutil.get_terminal_size", return_value=terminal_size((60, 24))),
            redirect_stdout(output),
        ):
            use.print_catalog(payload)

        lines = output.getvalue().splitlines()
        self.assertIn("NAME      SKILLS  SELECTION", lines)
        self.assertIn("NAME     SOURCE  STATE    DESCRIPTION", lines)
        self.assertTrue(any("deliver" in line and line.endswith("…") for line in lines))
        self.assertTrue(any("debug" in line and "missing" in line for line in lines))
        self.assertTrue(all(len(line) <= 60 for line in lines))

    def test_list_json_includes_bundled_seiton(self):
        with tempfile.TemporaryDirectory() as directory:
            result = run_cli(Path(directory), "list", "--json")

            self.assertEqual(result.returncode, 0, result.stderr)
            payload = json.loads(result.stdout)
            self.assertEqual(
                [item["name"] for item in payload["groups"]["bundled"]],
                ["seiton"],
            )

    def test_minimal_activates_empty_overlay_and_is_idempotent(self):
        with tempfile.TemporaryDirectory() as directory:
            project = Path(directory)
            result = run_cli(project, "minimal")

            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("Already active in", result.stdout)
            for client in (".agents", ".claude"):
                links = project / client / "skills"
                self.assertEqual(list(links.iterdir()), [])

            result = run_cli(project, "minimal")
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("Already active in", result.stdout)

    def test_seiton_can_be_selected_explicitly(self):
        with tempfile.TemporaryDirectory() as directory:
            project = Path(directory)

            result = run_cli(project, "use", "seiton")

            self.assertEqual(result.returncode, 0, result.stderr)
            for client in (".agents", ".claude"):
                self.assertEqual(
                    (project / client / "skills/seiton").resolve(),
                    ROOT / "seiton",
                )

    def test_minimal_removes_previously_selected_seiton(self):
        with tempfile.TemporaryDirectory() as directory:
            project = Path(directory)
            self.assertEqual(run_cli(project, "use", "seiton").returncode, 0)

            result = run_cli(project, "minimal")

            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("removed=seiton", result.stdout)
            for client in (".agents", ".claude"):
                self.assertFalse((project / client / "skills/seiton").exists())

    def test_minimal_preserves_project_skill_directories(self):
        with tempfile.TemporaryDirectory() as directory:
            project = Path(directory)
            for client in (".agents", ".claude"):
                skill = project / client / "skills/project-owned"
                skill.mkdir(parents=True)
                (skill / "SKILL.md").write_text("project content\n", encoding="utf-8")

            result = run_cli(project, "minimal")

            self.assertEqual(result.returncode, 0, result.stderr)
            for client in (".agents", ".claude"):
                skill_file = project / client / "skills/project-owned/SKILL.md"
                self.assertEqual(skill_file.read_text(encoding="utf-8"), "project content\n")

    def test_missing_locked_skill_restores_from_lock(self):
        with (
            patch("scripts.use.subprocess.run") as run,
            patch("pathlib.Path.is_file", side_effect=[False, True]),
        ):
            use.restore_if_needed(
                ["missing"],
                {"missing": {"source": "alice/skills", "sourceType": "github"}},
            )

        run.assert_called_once_with(
            [
                "npx",
                "skills@1.5.21",
                "add",
                "alice/skills",
                "--skill",
                "missing",
                "--agent",
                "codex",
                "--agent",
                "claude-code",
                "--yes",
            ],
            cwd=ROOT / "external",
            check=True,
        )

    def test_captured_upstream_failure_includes_stderr(self):
        failure = subprocess.CalledProcessError(
            1,
            ["npx", "skills@1.5.21"],
            stderr="repository not found\n",
        )
        with (
            patch("scripts.use.subprocess.run", side_effect=failure),
            self.assertRaisesRegex(
                ValueError,
                r"npx skills@1\.5\.21 failed with exit code 1: repository not found",
            ),
        ):
            use.run_skills(["add", "owner/repo"], quiet=True)

    def test_restore_does_not_require_a_git_project(self):
        output = io.StringIO()
        with (
            patch("scripts.use.locked_skills", return_value={}),
            patch("scripts.use.restore_if_needed", return_value=[]) as restore,
            patch("scripts.use.resolve_project") as resolve_project,
            redirect_stdout(output),
        ):
            result = use.main(["restore"])

        self.assertEqual(result, 0)
        restore.assert_called_once_with({}, {}, quiet=False)
        resolve_project.assert_not_called()
        self.assertEqual(output.getvalue(), "External Skills are already restored\n")

    def test_add_registers_and_verifies_an_open_source_skill(self):
        with (
            patch("scripts.use.subprocess.run") as run,
            patch(
                "scripts.use.locked_skills",
                return_value={"tdd": {}, "debug": {}},
            ),
            patch("pathlib.Path.is_file", return_value=True),
        ):
            use.add_to_catalog("owner/repo", ["tdd", "debug"], quiet=True)

        run.assert_called_once_with(
            [
                "npx",
                "skills@1.5.21",
                "add",
                "owner/repo",
                "--skill",
                "tdd",
                "debug",
                "--agent",
                "codex",
                "--agent",
                "claude-code",
                "--yes",
            ],
            cwd=ROOT / "external",
            check=True,
            capture_output=True,
            text=True,
        )

    def test_add_all_expands_to_wildcard_and_reports_lock_changes(self):
        with (
            patch("scripts.use.subprocess.run") as run,
            patch(
                "scripts.use.locked_skills",
                side_effect=[
                    {"existing": {"installPath": "old"}},
                    {
                        "existing": {"installPath": "new"},
                        "added": {"installPath": "added"},
                    },
                ],
            ),
            patch("pathlib.Path.is_file", return_value=True),
        ):
            changes = use.add_to_catalog(
                "owner/repo", [], all_skills=True, quiet=True
            )

        run.assert_called_once_with(
            [
                "npx",
                "skills@1.5.21",
                "add",
                "owner/repo",
                "--skill",
                "*",
                "--agent",
                "codex",
                "--agent",
                "claude-code",
                "--yes",
            ],
            cwd=ROOT / "external",
            check=True,
            capture_output=True,
            text=True,
        )
        self.assertEqual(changes["added"], ["added"])
        self.assertEqual(changes["changed"], ["existing"])

    def test_add_fails_when_upstream_does_not_update_the_catalog(self):
        with (
            patch("scripts.use.subprocess.run"),
            patch("scripts.use.locked_skills", return_value={}),
            patch("pathlib.Path.is_file", return_value=False),
            self.assertRaisesRegex(ValueError, "missing from lock: tdd"),
        ):
            use.add_to_catalog("owner/repo", ["tdd"])

    def test_add_command_does_not_resolve_a_project_or_activate(self):
        output = io.StringIO()
        with (
            patch(
                "scripts.use.add_to_catalog",
                return_value={"added": ["tdd", "debug"], "changed": []},
            ) as add,
            patch("scripts.use.resolve_project") as resolve_project,
            redirect_stdout(output),
        ):
            result = use.main(["add", "owner/repo", "tdd", "debug"])

        self.assertEqual(result, 0)
        add.assert_called_once_with(
            "owner/repo", ["tdd", "debug"], all_skills=False, quiet=False
        )
        resolve_project.assert_not_called()
        self.assertEqual(
            output.getvalue(),
            "Added to catalog: tdd, debug\n"
            "Changed in catalog: none\n"
            "Activate with: seiton use tdd debug\n",
        )

    def test_add_requires_skill_names_or_all(self):
        error = io.StringIO()
        with (
            patch("scripts.use.add_to_catalog") as add,
            redirect_stderr(error),
        ):
            result = use.main(["add", "owner/repo"])

        self.assertEqual(result, 1)
        add.assert_not_called()
        self.assertIn("add requires Skill names or --all", error.getvalue())

    def test_add_rejects_skill_names_with_all(self):
        with (
            patch("scripts.use.add_to_catalog") as add,
            redirect_stderr(io.StringIO()),
        ):
            result = use.main(["add", "owner/repo", "tdd", "--all"])

        self.assertEqual(result, 1)
        add.assert_not_called()

    def test_add_all_succeeds_when_the_lock_is_unchanged(self):
        output = io.StringIO()
        with (
            patch(
                "scripts.use.add_to_catalog",
                return_value={"added": [], "changed": []},
            ) as add,
            patch("scripts.use.resolve_project") as resolve_project,
            redirect_stdout(output),
        ):
            result = use.main(["add", "owner/repo", "--all"])

        self.assertEqual(result, 0)
        add.assert_called_once_with(
            "owner/repo", [], all_skills=True, quiet=False
        )
        resolve_project.assert_not_called()
        self.assertEqual(
            output.getvalue(),
            "Added to catalog: none\nChanged in catalog: none\n",
        )

    def test_update_uses_pinned_upstream_package(self):
        with (
            patch("scripts.use.subprocess.run") as run,
            patch(
                "scripts.use.locked_skills",
                side_effect=[{"tdd": {}}, {"tdd": {"updated": True}}],
            ),
        ):
            changes = use.update_catalog(["tdd"], quiet=True)

        run.assert_called_once_with(
            [
                "npx",
                "skills@1.5.21",
                "update",
                "tdd",
                "--project",
                "--yes",
            ],
            cwd=ROOT / "external",
            check=True,
            capture_output=True,
            text=True,
        )
        self.assertEqual(changes["changed"], ["tdd"])

    def test_update_all_uses_upstream_default_all_behavior(self):
        with (
            patch("scripts.use.subprocess.run") as run,
            patch("scripts.use.locked_skills", side_effect=[{}, {}]),
        ):
            use.update_catalog([], quiet=True)

        run.assert_called_once_with(
            [
                "npx",
                "skills@1.5.21",
                "update",
                "--project",
                "--yes",
            ],
            cwd=ROOT / "external",
            check=True,
            capture_output=True,
            text=True,
        )

    def test_update_names_does_not_require_a_git_project(self):
        output = io.StringIO()
        with (
            patch(
                "scripts.use.update_catalog",
                return_value={"changed": ["tdd"], "upstream": None},
            ) as update,
            patch("scripts.use.resolve_project") as resolve_project,
            patch("scripts.use.subprocess.run"),
            redirect_stdout(output),
        ):
            result = use.main(["update", "tdd"])

        self.assertEqual(result, 0)
        update.assert_called_once_with(["tdd"], quiet=False)
        resolve_project.assert_not_called()
        self.assertEqual(
            output.getvalue(),
            "Updated: tdd\n"
            "Changed in catalog: tdd\n"
            "WARNING: Central changes affect every project linked to these Skills.\n",
        )

    def test_update_rejects_an_empty_selection(self):
        error = io.StringIO()
        with (
            patch("scripts.use.update_catalog") as update,
            redirect_stderr(error),
        ):
            result = use.main(["update"])

        self.assertEqual(result, 1)
        update.assert_not_called()
        self.assertIn("update requires Skill names or --all", error.getvalue())

    def test_update_rejects_names_with_all(self):
        with (
            patch("scripts.use.update_catalog") as update,
            redirect_stderr(io.StringIO()),
        ):
            result = use.main(["update", "tdd", "--all"])

        self.assertEqual(result, 1)
        update.assert_not_called()

    def test_update_all_maps_to_upstream_all_without_a_git_project(self):
        with (
            patch(
                "scripts.use.update_catalog",
                return_value={"changed": [], "upstream": None},
            ) as update,
            patch("scripts.use.resolve_project") as resolve_project,
            redirect_stdout(io.StringIO()),
        ):
            result = use.main(["update", "--all"])

        self.assertEqual(result, 0)
        update.assert_called_once_with([], quiet=False)
        resolve_project.assert_not_called()

    def test_selection_isolated_from_global_and_preserves_foreign_links(self):
        with tempfile.TemporaryDirectory() as directory:
            project = Path(directory)
            parent = project / "parent"
            (parent / "codex/skills/deliver").mkdir(parents=True)
            foreign = project / "foreign"
            foreign.mkdir()
            (foreign / "SKILL.md").write_text("---\nname: foreign\n---\n", encoding="utf-8")

            for client in (".agents", ".claude"):
                links = project / client / "skills"
                links.mkdir(parents=True)
                (links / "stale").symlink_to(ROOT / "compare-solutions")
                (links / "foreign").symlink_to(foreign)

            with patch.dict(os.environ, isolated_env(parent)):
                result = run_cli(project, "use", "deliver")

            self.assertEqual(result.returncode, 0, result.stderr)
            for client in (".agents", ".claude"):
                links = project / client / "skills"
                self.assertEqual((links / "deliver").resolve(), ROOT / "deliver")
                self.assertFalse((links / "seiton").exists())
                self.assertFalse((links / "stale").exists())
                self.assertEqual((links / "foreign").resolve(), foreign.resolve())

    def test_dry_run_does_not_create_links(self):
        with tempfile.TemporaryDirectory() as directory:
            project = Path(directory)
            result = run_cli(project, "use", "deliver", "--dry-run", "--json")

            self.assertEqual(result.returncode, 0, result.stderr)
            payload = json.loads(result.stdout)
            self.assertTrue(payload["dry_run"])
            self.assertTrue(payload["changed"])
            self.assertFalse((project / ".agents").exists())
            self.assertFalse((project / ".claude").exists())

    def test_conflict_changes_neither_client(self):
        with tempfile.TemporaryDirectory() as directory:
            project = Path(directory)
            (project / ".agents/skills").mkdir(parents=True)
            conflict = project / ".claude/skills/deliver"
            conflict.mkdir(parents=True)

            result = run_cli(project, "use", "deliver")

            self.assertEqual(result.returncode, 1)
            self.assertFalse((project / ".agents/skills/deliver").exists())
            self.assertTrue(conflict.is_dir())

    def test_global_conflict_prevents_restore_and_project_writes(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            project = root / "project"
            project.mkdir()
            global_skill = root / "codex/skills/deliver"
            global_skill.mkdir(parents=True)

            with (
                patch.dict(
                    "scripts.use.os.environ",
                    isolated_env(root),
                ),
                patch("scripts.use.restore_if_needed") as restore,
                redirect_stderr(io.StringIO()),
            ):
                result = use.main(
                    ["use", "deliver", "--project", str(project)]
                )

            self.assertEqual(result, 1)
            restore.assert_not_called()
            self.assertFalse((project / ".agents").exists())
            self.assertFalse((project / ".claude").exists())

    def test_partial_replacement_is_reported_and_rerun_repairs_it(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            project = root / "project"
            old = root / "old"
            new = root / "new"
            for source in (old, new):
                source.mkdir()
                (source / "SKILL.md").write_text("---\nname: skill\n---\n")
            for client in (".agents", ".claude"):
                link = project / client / "skills/skill"
                link.parent.mkdir(parents=True)
                link.symlink_to(old, target_is_directory=True)
            original = Path.symlink_to
            calls = 0

            def fail_first(link, target, **kwargs):
                nonlocal calls
                calls += 1
                if calls == 1:
                    raise OSError("simulated failure")
                return original(link, target, **kwargs)

            with (
                patch.dict("scripts.use.os.environ", isolated_env(root)),
                patch.object(Path, "symlink_to", fail_first),
            ):
                with self.assertRaisesRegex(
                    ValueError,
                    r"completed: codex:unlink:skill; incomplete: "
                    r"codex:symlink:skill, claude:unlink:skill, "
                    r"claude:symlink:skill",
                ):
                    use.activate(
                        project,
                        ["skill"],
                        {"skill": new.resolve()},
                        {old.resolve(), new.resolve()},
                    )

            self.assertFalse((project / ".agents/skills/skill").exists())
            self.assertEqual((project / ".claude/skills/skill").resolve(), old.resolve())

            with patch.dict("scripts.use.os.environ", isolated_env(root)):
                changed, _ = use.activate(
                    project,
                    ["skill"],
                    {"skill": new.resolve()},
                    {old.resolve(), new.resolve()},
                )

            self.assertTrue(changed)
            for client in (".agents", ".claude"):
                self.assertEqual(
                    (project / client / "skills/skill").resolve(), new.resolve()
                )

    def test_post_write_verification_failure_returns_nonzero(self):
        with tempfile.TemporaryDirectory() as directory:
            project = Path(directory)
            invalid_status = {
                "clients": {
                    client: {"seiton": [], "project": [], "global": []}
                    for client in use.CLIENTS
                }
            }
            error = io.StringIO()
            with (
                patch.dict("scripts.use.os.environ", isolated_env(project)),
                patch("scripts.use.status_payload", return_value=invalid_status),
                redirect_stderr(error),
            ):
                result = use.main(
                    ["use", "deliver", "--project", str(project)]
                )

            self.assertEqual(result, 1)
            self.assertIn("reconcile verification failed", error.getvalue())

    def test_project_differences_do_not_affect_status_sync(self):
        with tempfile.TemporaryDirectory() as directory:
            project = Path(directory)
            targets = []
            for name in ("one", "two"):
                target = project / name
                target.mkdir()
                (target / "SKILL.md").write_text(
                    "---\nname: foreign\n---\n", encoding="utf-8"
                )
                targets.append(target)
            for client, target in zip((".agents", ".claude"), targets):
                links = project / client / "skills"
                links.mkdir(parents=True)
                (links / "foreign").symlink_to(target)

            payload = use.status_payload(project, {}, set())

            self.assertTrue(payload["synced"])
            self.assertTrue(use.status_is_healthy(payload))
            self.assertEqual(
                [entry["name"] for entry in payload["clients"]["codex"]["project"]],
                ["foreign"],
            )

    def test_status_reports_layers_health_conflicts_and_readable_context(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            project = root / "project"
            project.mkdir()
            catalog = root / "catalog"
            managed = catalog / "managed"
            managed.mkdir(parents=True)
            (managed / "SKILL.md").write_text(
                "---\nname: managed\ndescription: Managed.\n---\nbody\n",
                encoding="utf-8",
            )
            invalid_managed = catalog / "invalid-managed"
            invalid_managed.mkdir()
            missing_managed = catalog / "missing-managed"
            sources = {
                "managed": managed,
                "invalid-managed": invalid_managed,
                "missing-managed": missing_managed,
            }
            managed_paths = {path.resolve() for path in sources.values()}

            for client in (".agents", ".claude"):
                skills = project / client / "skills"
                skills.mkdir(parents=True)
                (skills / "managed").symlink_to(managed, target_is_directory=True)
                (skills / "invalid-managed").symlink_to(
                    invalid_managed, target_is_directory=True
                )
                (skills / "missing-managed").symlink_to(
                    missing_managed, target_is_directory=True
                )

            codex_project = project / ".agents/skills"
            project_owned = codex_project / "project-owned"
            project_owned.mkdir()
            (project_owned / "SKILL.md").write_text(
                "---\nname: project-owned\n---\n", encoding="utf-8"
            )
            (codex_project / "broken-project").symlink_to(
                root / "missing-project", target_is_directory=True
            )
            (codex_project / "invalid-project").mkdir()

            codex_home = root / "codex-home"
            codex_global = codex_home / "skills"
            for name in ("managed", "project-owned"):
                skill = codex_global / name
                skill.mkdir(parents=True)
                (skill / "SKILL.md").write_text(
                    f"---\nname: {name}\n---\n", encoding="utf-8"
                )
            (codex_global / "broken-global").symlink_to(
                root / "missing-global", target_is_directory=True
            )
            (codex_global / "invalid-global").mkdir()

            with patch.dict(
                "scripts.use.os.environ",
                {"HOME": str(root / "home"), "CODEX_HOME": str(codex_home)},
            ):
                payload = use.status_payload(
                    project,
                    sources,
                    managed_paths,
                    {name: {"source": "owner/catalog"} for name in sources},
                )

            codex = payload["clients"]["codex"]
            health = {
                layer: {entry["name"]: entry["health"] for entry in entries}
                for layer, entries in codex.items()
            }
            self.assertEqual(
                health["seiton"],
                {
                    "invalid-managed": "invalid",
                    "managed": "healthy",
                    "missing-managed": "broken",
                },
            )
            self.assertEqual(health["project"]["project-owned"], "healthy")
            self.assertEqual(health["project"]["broken-project"], "broken")
            self.assertEqual(health["project"]["invalid-project"], "invalid")
            self.assertEqual(health["global"]["broken-global"], "broken")
            self.assertEqual(health["global"]["invalid-global"], "invalid")
            self.assertEqual(payload["clients"]["claude"]["global"], [])
            self.assertTrue(payload["synced"])
            self.assertEqual(payload["context"]["measured"], ["managed"])
            self.assertEqual(
                payload["conflicts"],
                [
                    {"client": "codex", "name": "managed", "layers": ["seiton", "global"]},
                    {"client": "codex", "name": "project-owned", "layers": ["project", "global"]},
                ],
            )
            self.assertEqual(
                set(codex["seiton"][0]),
                {"name", "path", "target", "health", "source"},
            )

    def test_seiton_differences_make_status_unsynced(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            project = root / "project"
            project.mkdir()
            targets = []
            for name in ("one", "two"):
                target = root / name
                target.mkdir()
                (target / "SKILL.md").write_text(
                    f"---\nname: {name}\n---\n", encoding="utf-8"
                )
                targets.append(target.resolve())
            for client, target in zip((".agents", ".claude"), targets):
                skills = project / client / "skills"
                skills.mkdir(parents=True)
                (skills / "managed").symlink_to(target, target_is_directory=True)

            with patch.dict(
                "scripts.use.os.environ",
                {"HOME": str(root / "home"), "CODEX_HOME": str(root / "codex")},
            ):
                payload = use.status_payload(
                    project, {"managed": targets[0]}, set(targets)
                )

            self.assertFalse(payload["synced"])

    def test_status_observes_supported_client_global_roots(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            project = root / "project"
            project.mkdir()
            home = root / "home"
            codex_home = root / "codex"
            claude_home = root / "claude"
            for base, name in (
                (home / ".agents/skills", "universal"),
                (codex_home / "skills", "codex-only"),
                (claude_home / "skills", "claude-only"),
            ):
                skill = base / name
                skill.mkdir(parents=True)
                (skill / "SKILL.md").write_text(
                    f"---\nname: {name}\n---\n", encoding="utf-8"
                )

            with patch.dict(
                "scripts.use.os.environ",
                {
                    "HOME": str(home),
                    "CODEX_HOME": str(codex_home),
                    "CLAUDE_CONFIG_DIR": str(claude_home),
                },
            ):
                payload = use.status_payload(project, {}, set())

            self.assertEqual(
                [entry["name"] for entry in payload["clients"]["codex"]["global"]],
                ["codex-only", "universal"],
            )
            self.assertEqual(
                [entry["name"] for entry in payload["clients"]["claude"]["global"]],
                ["claude-only"],
            )
            self.assertEqual(payload["conflicts"], [])

    def test_project_resolution_uses_git_root(self):
        with tempfile.TemporaryDirectory() as directory:
            project = Path(directory)
            subprocess.run(
                ["git", "init", "-q", str(project)],
                check=True,
                capture_output=True,
            )
            nested = project / "one/two"
            nested.mkdir(parents=True)

            self.assertEqual(use.resolve_project(nested), project.resolve())


if __name__ == "__main__":
    unittest.main()
