import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from scripts import use

ROOT = Path(__file__).resolve().parents[1]


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
    )


class UseSkillsTest(unittest.TestCase):
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
            result = run_cli(project)

            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn(f"Project: {project.resolve()}", result.stdout)
            self.assertFalse((project / ".agents").exists())
            self.assertFalse((project / ".claude").exists())

    def test_minimal_activates_only_baseline_and_is_idempotent(self):
        with tempfile.TemporaryDirectory() as directory:
            project = Path(directory)
            result = run_cli(project, "minimal")

            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("Activated in", result.stdout)
            for client in (".agents", ".claude"):
                links = project / client / "skills"
                self.assertEqual({path.name for path in links.iterdir()}, {"seiton"})

            result = run_cli(project, "minimal")
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("Already active in", result.stdout)

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
                "skills",
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

    def test_selection_replaces_catalog_links_and_preserves_foreign_links(self):
        with tempfile.TemporaryDirectory() as directory:
            project = Path(directory)
            foreign = project / "foreign"
            foreign.mkdir()
            (foreign / "SKILL.md").write_text("---\nname: foreign\n---\n", encoding="utf-8")

            for client in (".agents", ".claude"):
                links = project / client / "skills"
                links.mkdir(parents=True)
                (links / "stale").symlink_to(ROOT / "compare-solutions")
                (links / "foreign").symlink_to(foreign)

            result = run_cli(project, "use", "deliver")

            self.assertEqual(result.returncode, 0, result.stderr)
            for client in (".agents", ".claude"):
                links = project / client / "skills"
                self.assertEqual((links / "deliver").resolve(), ROOT / "deliver")
                self.assertEqual((links / "seiton").resolve(), ROOT / "seiton")
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

    def test_status_detects_same_name_with_different_targets(self):
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

            self.assertFalse(payload["synced"])

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
