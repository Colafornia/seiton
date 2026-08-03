#!/usr/bin/env python3

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EXTERNAL = ROOT / "external"
SKILLS_PACKAGE = "skills@1.5.21"
CLIENTS = {"codex": ".agents", "claude": ".claude"}


def locked_skills():
    lock = json.loads((EXTERNAL / "skills-lock.json").read_text(encoding="utf-8"))
    return lock["skills"]


def profiles(root=ROOT):
    shared = tomllib.loads(
        (root / "skillsets.toml").read_text(encoding="utf-8")
    )["profiles"]
    local = root / ".agent/skillsets.toml"
    if local.is_file():
        shared.update(tomllib.loads(local.read_text(encoding="utf-8"))["profiles"])
    return shared


def resolve_project(path):
    project = path.resolve()
    if not project.is_dir():
        raise ValueError(f"project is not a directory: {project}")
    result = subprocess.run(
        ["git", "-C", str(project), "rev-parse", "--show-toplevel"],
        capture_output=True,
        text=True,
    )
    if result.returncode == 0:
        project = Path(result.stdout.strip()).resolve()
    if project == Path.home().resolve():
        raise ValueError("home directory is not a project; global Skill installation is disabled")
    return project


def requested_names(skills=None, profile=None):
    names = list(skills or [])
    if profile:
        available = profiles()
        if profile not in available:
            raise ValueError(f"unknown profile: {profile}")
        names = available[profile]["skills"]
    return list(dict.fromkeys(names))


def restore_if_needed(names, locked, quiet=False):
    missing = [
        name
        for name in names
        if name in locked
        and not (EXTERNAL / ".agents/skills" / name / "SKILL.md").is_file()
    ]
    grouped = {}
    for name in missing:
        entry = locked[name]
        source = entry.get("sourceUrl") or entry["source"]
        if entry.get("ref"):
            source = f"{source}@{entry['ref']}"
        grouped.setdefault(source, []).append(name)

    for source, skill_names in grouped.items():
        command = ["npx", SKILLS_PACKAGE, "add", source]
        for name in skill_names:
            command.extend(["--skill", name])
        command.extend(
            ["--agent", "codex", "--agent", "claude-code", "--yes"]
        )
        subprocess.run(
            command,
            cwd=EXTERNAL,
            check=True,
            **({"capture_output": True, "text": True} if quiet else {}),
        )
    still_missing = [
        name
        for name in missing
        if not (EXTERNAL / ".agents/skills" / name / "SKILL.md").is_file()
    ]
    if still_missing:
        raise ValueError(f"failed to restore: {', '.join(still_missing)}")
    return missing


def add_to_catalog(source, names, all_skills=False, quiet=False):
    if bool(names) == bool(all_skills):
        raise ValueError("add requires Skill names or --all")
    before = locked_skills()
    command = ["npx", SKILLS_PACKAGE, "add", source]
    if all_skills:
        command.extend(["--skill", "*"])
    elif names:
        command.extend(["--skill", *names])
    command.extend(["--agent", "codex", "--agent", "claude-code", "--yes"])
    result = subprocess.run(
        command,
        cwd=EXTERNAL,
        check=True,
        **({"capture_output": True, "text": True} if quiet else {}),
    )

    after = locked_skills()
    added = sorted(set(after) - set(before))
    changed = sorted(
        name for name in set(after) & set(before) if after[name] != before[name]
    )
    verified = added + changed if all_skills else names
    missing_lock = [name for name in verified if name not in after]
    missing_files = [
        name
        for name in verified
        if not (EXTERNAL / ".agents/skills" / name / "SKILL.md").is_file()
    ]
    errors = []
    if missing_lock:
        errors.append(f"missing from lock: {', '.join(missing_lock)}")
    if missing_files:
        errors.append(f"missing SKILL.md: {', '.join(missing_files)}")
    if errors:
        raise ValueError(f"catalog verification failed; {'; '.join(errors)}")
    return {"added": added, "changed": changed, "upstream": result}


def update_catalog(names, quiet=False):
    before = locked_skills()
    result = subprocess.run(
        ["npx", SKILLS_PACKAGE, "update", *names, "--project", "--yes"],
        cwd=EXTERNAL,
        check=True,
        **({"capture_output": True, "text": True} if quiet else {}),
    )
    after = locked_skills()
    changed = sorted(
        name for name in set(before) | set(after) if before.get(name) != after.get(name)
    )
    return {"changed": changed, "upstream": result}


def catalog(locked):
    groups = [
        [path for path in ROOT.iterdir() if (path / "SKILL.md").is_file()],
        list((EXTERNAL / ".agents/skills").glob("*")),
        list((ROOT / "local").glob("*")) if (ROOT / "local").exists() else [],
    ]
    sources = {}
    for paths in groups:
        for path in paths:
            if not (path / "SKILL.md").is_file():
                continue
            if path.name in sources and sources[path.name] != path.resolve():
                raise ValueError(f"duplicate skill: {path.name}")
            sources[path.name] = path.resolve()
    for name in locked:
        sources.setdefault(name, (EXTERNAL / ".agents/skills" / name).resolve())

    return sources, set(sources.values())


def skill_metadata(path):
    text = (path / "SKILL.md").read_text(encoding="utf-8")
    _, frontmatter, body = text.split("---", 2)
    lines = frontmatter.splitlines()
    description = ""
    for index, line in enumerate(lines):
        if not line.startswith("description:"):
            continue
        value = line.partition(":")[2].strip()
        if value in {">", ">-", "|", "|-"}:
            parts = []
            for continuation in lines[index + 1 :]:
                if continuation and not continuation[0].isspace():
                    break
                if continuation.strip():
                    parts.append(continuation.strip())
            description = " ".join(parts)
        else:
            description = value.strip("\"'")
        break
    heading = re.search(r"^#\s+(.+?)\s*$", body, re.MULTILINE)
    return {
        "title": heading.group(1) if heading else path.name,
        "description": description,
    }


def catalog_payload(project, sources, locked, available_profiles):
    groups = {"bundled": [], "owned": [], "open_source": {}, "local": []}
    local_root = (ROOT / "local").resolve()
    for name, path in sorted(sources.items()):
        installed = (path / "SKILL.md").is_file()
        metadata = (
            skill_metadata(path)
            if installed
            else {"title": name.replace("-", " ").title(), "description": ""}
        )
        item = {"name": name, **metadata, "installed": installed}
        if name == "seiton":
            groups["bundled"].append(item)
        elif name in locked:
            author = locked[name]["source"].split("/", 1)[0]
            groups["open_source"].setdefault(author, []).append(item)
        elif path.parent == local_root:
            groups["local"].append(item)
        else:
            groups["owned"].append(item)
    groups["open_source"] = dict(
        sorted(groups["open_source"].items(), key=lambda item: item[0].casefold())
    )

    active = {}
    for client, directory in CLIENTS.items():
        links = project / directory / "skills"
        active[client] = sorted(path.name for path in links.iterdir()) if links.is_dir() else []
    return {"project": str(project), "active": active, "profiles": available_profiles, "groups": groups}


def link_target(link):
    return (link.parent / os.readlink(link)).resolve()


def estimate_sources(names, sources):
    metadata_chars = 0
    body_chars = 0
    measured = []
    for name in dict.fromkeys(names):
        path = sources.get(name)
        if not path:
            continue
        try:
            if not (path / "SKILL.md").is_file():
                continue
            metadata = skill_metadata(path)
            body = (path / "SKILL.md").read_text(encoding="utf-8")
        except (OSError, ValueError):
            continue
        metadata_chars += len(name) + len(metadata["description"])
        body_chars += len(body)
        measured.append(name)
    return {
        "discovery_tokens": (metadata_chars + 3) // 4,
        "body_tokens_if_invoked": (body_chars + 3) // 4,
        "measured": measured,
        "approximate": True,
    }


def skill_entry(path):
    target = link_target(path) if path.is_symlink() else path.resolve()
    if path.is_symlink() and not target.exists():
        health = "broken"
    elif (target / "SKILL.md").is_file():
        health = "healthy"
    else:
        health = "invalid"
    return {
        "name": path.name,
        "path": str(path),
        "target": str(target),
        "health": health,
    }


def scan_skills(directory, skip_hidden=False):
    if not directory.is_dir():
        return []
    return [
        skill_entry(path)
        for path in sorted(directory.iterdir(), key=lambda item: item.name)
        if not skip_hidden or not path.name.startswith(".")
    ]


def global_skills_paths(client):
    if client == "codex":
        homes = [
            Path(os.environ.get("CODEX_HOME") or Path.home() / ".codex"),
            Path.home() / ".agents",
        ]
    else:
        homes = [
            Path(os.environ.get("CLAUDE_CONFIG_DIR") or Path.home() / ".claude")
        ]
    return list(dict.fromkeys((home.expanduser() / "skills").resolve() for home in homes))


def read_skill_lock(path):
    try:
        skills = json.loads(path.read_text(encoding="utf-8"))["skills"]
    except (KeyError, OSError, TypeError, ValueError):
        return {}
    return skills if isinstance(skills, dict) else {}


def status_payload(project, sources, managed, locked=None):
    clients = {}
    seiton_signatures = {}
    readable_seiton = set()
    conflicts = []
    project_lock = read_skill_lock(project / ".agents/.skill-lock.json")
    global_lock = read_skill_lock(Path.home() / ".agents/.skill-lock.json")
    source_indexes = {
        "seiton": {
            sources[name].resolve(): entry["source"]
            for name, entry in (locked or {}).items()
            if name in sources and entry.get("source")
        },
        "project": {
            (project / ".agents/skills" / name).resolve(): entry["source"]
            for name, entry in project_lock.items()
            if entry.get("source")
        },
        "global": {
            (Path.home() / ".agents/skills" / name).resolve(): entry["source"]
            for name, entry in global_lock.items()
            if entry.get("source")
        },
    }
    for client, directory in CLIENTS.items():
        project_path = project / directory / "skills"
        project_entries = scan_skills(project_path)
        seiton = [
            entry for entry in project_entries if Path(entry["target"]) in managed
        ]
        project_layer = [entry for entry in project_entries if entry not in seiton]
        global_layer = sorted(
            (
                entry
                for path in global_skills_paths(client)
                for entry in scan_skills(path, skip_hidden=True)
            ),
            key=lambda entry: (entry["name"], entry["path"]),
        )
        clients[client] = {
            "seiton": seiton,
            "project": project_layer,
            "global": global_layer,
        }
        for layer, entries in clients[client].items():
            for entry in entries:
                source = source_indexes[layer].get(Path(entry["target"]))
                if source:
                    entry["source"] = source
        seiton_signatures[client] = tuple(
            (entry["name"], entry["target"], entry["health"])
            for entry in seiton
        )
        readable_seiton.update(
            entry["name"] for entry in seiton if entry["health"] == "healthy"
        )
        layers_by_name = {}
        for layer, entries in clients[client].items():
            for entry in entries:
                layers_by_name.setdefault(entry["name"], set()).add(layer)
        conflicts.extend(
            {
                "client": client,
                "name": name,
                "layers": [layer for layer in clients[client] if layer in layers],
            }
            for name, layers in sorted(layers_by_name.items())
            if len(layers) > 1
        )

    return {
        "project": str(project),
        "clients": clients,
        "conflicts": conflicts,
        "synced": len(set(seiton_signatures.values())) <= 1,
        "context": estimate_sources(sorted(readable_seiton), sources),
    }


def activation_plan(project, names, sources, managed):
    selected = set(names)
    missing = sorted(selected - set(sources))
    if missing:
        raise ValueError(f"missing skills: {', '.join(missing)}")

    plan = {}
    conflicts = []
    for client, directory in CLIENTS.items():
        links = project / directory / "skills"
        existing = list(links.iterdir()) if links.is_dir() else []
        changes = {
            "added": [],
            "removed": [],
            "replaced": [],
            "preserved": [],
            "foreign": [],
        }

        for name in names:
            link = links / name
            if link.is_symlink():
                target = link_target(link)
                if target == sources[name]:
                    changes["preserved"].append(name)
                elif target in managed:
                    changes["replaced"].append(name)
                else:
                    conflicts.append(f"conflicting link: {link}")
            elif link.exists():
                conflicts.append(f"conflicting path: {link}")
            else:
                changes["added"].append(name)

        for link in existing:
            if link.name in selected:
                continue
            if link.is_symlink() and link_target(link) in managed:
                changes["removed"].append(link.name)
            else:
                changes["foreign"].append(link.name)
        for values in changes.values():
            values.sort()
        plan[client] = changes

    if conflicts:
        raise ValueError("; ".join(conflicts))
    return plan


def activate(project, names, sources, managed, dry_run=False):
    plan = activation_plan(project, names, sources, managed)
    changed = any(
        changes[key]
        for changes in plan.values()
        for key in ("added", "removed", "replaced")
    )
    if dry_run:
        return changed, plan

    for client, directory in CLIENTS.items():
        links = project / directory / "skills"
        links.mkdir(parents=True, exist_ok=True)
        changes = plan[client]
        for name in changes["removed"] + changes["replaced"]:
            (links / name).unlink()
        for name in changes["added"] + changes["replaced"]:
            (links / name).symlink_to(sources[name], target_is_directory=True)
    return changed, plan


def truncate(value, width):
    if len(value) <= width:
        return value
    return value[: max(0, width - 1)] + "…"


def print_table(headers, rows):
    rows = [[str(value) for value in row] for row in rows]
    widths = [
        max(len(header), *(len(row[index]) for row in rows))
        for index, header in enumerate(headers)
    ]
    available = shutil.get_terminal_size(fallback=(100, 24)).columns
    overflow = sum(widths) + 2 * (len(widths) - 1) - available
    for index in reversed(range(len(widths))):
        minimum = len(headers[index])
        reduction = min(overflow, widths[index] - minimum)
        widths[index] -= reduction
        overflow -= reduction
        if not overflow:
            break

    for row in [list(headers), *rows]:
        print("  ".join(
            truncate(value, widths[index]).ljust(widths[index])
            if index < len(widths) - 1
            else truncate(value, widths[index])
            for index, value in enumerate(row)
        ).rstrip())


def display_path(value, project):
    path = Path(value)
    for base, label in ((project, "."), (ROOT, "$SEITON"), (Path.home(), "~")):
        try:
            relative = path.relative_to(base)
        except ValueError:
            continue
        if relative == Path("."):
            return label
        return str(relative) if label == "." else f"{label}/{relative}"
    return str(path)


def status_entry_label(entry, project):
    if entry["health"] == "healthy":
        return entry["name"]
    return (
        f"{entry['name']} [{entry['health']}] -> "
        f"{display_path(entry['target'], project)}"
    )


def print_status_entries(entries, project, prefix):
    direct = [entry for entry in entries if "source" not in entry]
    repositories = {}
    for entry in entries:
        if "source" in entry:
            repositories.setdefault(entry["source"], []).append(entry)

    nodes = [(None, [entry]) for entry in direct] + sorted(repositories.items())
    for index, (source, group) in enumerate(nodes):
        last = index == len(nodes) - 1
        branch = "└── " if last else "├── "
        if source is None:
            print(f"{prefix}{branch}{status_entry_label(group[0], project)}")
            continue
        print(f"{prefix}{branch}{source}")
        child_prefix = prefix + ("    " if last else "│   ")
        for child_index, entry in enumerate(group):
            child_branch = "└── " if child_index == len(group) - 1 else "├── "
            print(
                f"{child_prefix}{child_branch}"
                f"{status_entry_label(entry, project)}"
            )


def print_status(payload):
    project = Path(payload["project"])
    state = "✓ synced" if payload["synced"] else "✗ different"
    counts = "  ".join(
        f"{client}:{len(layers['seiton'])}"
        for client, layers in payload["clients"].items()
    )
    conflicts = (
        f"  ⚠ conflicts:{len(payload['conflicts'])}"
        if payload["conflicts"]
        else ""
    )
    print(f"seiton status  {project}")
    print(f"{state}  {counts}{conflicts}")
    for client, layers in payload["clients"].items():
        print()
        print(client)
        layer_items = list(layers.items())
        for index, (layer, entries) in enumerate(layer_items):
            last = index == len(layer_items) - 1
            branch = "└── " if last else "├── "
            child_prefix = "    " if last else "│   "
            directory = (
                project / CLIENTS[client] / "skills"
                if layer != "global"
                else None
            )
            paths = (
                display_path(directory, project)
                if directory
                else " · ".join(
                    display_path(path, project)
                    for path in global_skills_paths(client)
                )
            )
            empty = "  ∅" if not entries else ""
            print(f"{branch}{layer:<7} {paths}{empty}")
            print_status_entries(entries, project, child_prefix)
    if payload["conflicts"]:
        print()
        print("CONFLICTS")
        for item in payload["conflicts"]:
            print(
                f"└── {item['client']}:{item['name']}  "
                f"{' ↔ '.join(item['layers'])}"
            )
    context = payload["context"]
    print()
    print(
        f"context ~{context['discovery_tokens']:,} discovery / "
        f"~{context['body_tokens_if_invoked']:,} invoked"
    )
    print("directory view only, not full runtime · system/plugin/unknown omitted")


def print_catalog(payload):
    print("PROFILES")
    print()
    print_table(
        ("NAME", "SKILLS", "SELECTION"),
        [
            (name, len(config["skills"]), ", ".join(config["skills"]) or "minimal")
            for name, config in payload["profiles"].items()
        ],
    )
    print()
    print("SKILLS")
    print()
    rows = []
    for source in ("bundled", "owned", "local"):
        for item in payload["groups"].get(source, []):
            rows.append((
                item["name"], source, "ready" if item["installed"] else "missing",
                item["description"] or "-",
            ))
    for author, items in payload["groups"]["open_source"].items():
        for item in items:
            rows.append((
                item["name"], author, "ready" if item["installed"] else "missing",
                item["description"] or "-",
            ))
    print_table(("NAME", "SOURCE", "STATE", "DESCRIPTION"), rows)


def print_activation(payload):
    action = "Preview" if payload["dry_run"] else (
        "Activated" if payload["changed"] else "Already active"
    )
    print(f"{action} in {payload['project']}: {', '.join(payload['selected'])}")
    for client, changes in payload["clients"].items():
        summary = []
        for key in ("added", "removed", "replaced"):
            if changes[key]:
                summary.append(f"{key}={','.join(changes[key])}")
        print(f"{client.capitalize()}: {'; '.join(summary) or 'unchanged'}")
    context = payload["context"]
    print(
        "Context: "
        f"~{context['discovery_tokens']} discovery tokens; "
        f"~{context['body_tokens_if_invoked']} body tokens if all invoked"
    )


def status_is_healthy(status):
    return (
        status["synced"]
        and not status["conflicts"]
        and all(
            entry["health"] == "healthy"
            for layers in status["clients"].values()
            for entry in layers["seiton"]
        )
    )


def run_check(project, sources, managed, locked=None):
    repository = subprocess.run(
        [sys.executable, str(ROOT / "scripts/check.py")],
        capture_output=True,
        text=True,
    )
    status = status_payload(project, sources, managed, locked)
    project_ok = status_is_healthy(status)
    return {
        "ok": repository.returncode == 0 and project_ok,
        "repository": {
            "ok": repository.returncode == 0,
            "output": (repository.stdout or repository.stderr).strip(),
        },
        "project": status,
    }


def add_common_options(parser, suppressed=False):
    default = argparse.SUPPRESS if suppressed else None
    parser.add_argument("--project", type=Path, default=default)
    parser.add_argument("--json", action="store_true", default=default)


def build_parser():
    parser = argparse.ArgumentParser(
        description="Manage a minimal project-specific Skill set"
    )
    parser.set_defaults(project=None, json=False, dry_run=False)

    subcommands = parser.add_subparsers(dest="command")
    for name, aliases in (
        ("status", []),
        ("list", ["ls"]),
        ("minimal", []),
        ("check", []),
    ):
        child = subcommands.add_parser(name, aliases=aliases)
        add_common_options(child, suppressed=True)
        if name == "minimal":
            child.add_argument("--dry-run", action="store_true", default=argparse.SUPPRESS)

    use = subcommands.add_parser("use")
    add_common_options(use, suppressed=True)
    use.add_argument("skills", nargs="*")
    use.add_argument("--profile")
    use.add_argument("--dry-run", action="store_true", default=argparse.SUPPRESS)

    add = subcommands.add_parser("add")
    add.add_argument("--json", action="store_true", default=argparse.SUPPRESS)
    add.add_argument("source")
    add.add_argument("skills", nargs="*")
    add.add_argument("--all", dest="all_skills", action="store_true")

    restore = subcommands.add_parser("restore")
    restore.add_argument("--json", action="store_true", default=argparse.SUPPRESS)

    update = subcommands.add_parser("update")
    update.add_argument("--json", action="store_true", default=argparse.SUPPRESS)
    update.add_argument("skills", nargs="*")
    update.add_argument("--all", dest="all_skills", action="store_true")
    return parser


def main(argv=None):
    parser = build_parser()
    args = parser.parse_args(argv)

    if not args.command:
        args.command = "status"

    try:
        if args.dry_run and args.command not in {"use", "minimal"}:
            raise ValueError("--dry-run is supported only by use and minimal")
        if args.command == "use" and args.profile and args.skills:
            raise ValueError("use Skill names and --profile are mutually exclusive")
        if args.command == "add":
            names = args.skills or []
            if bool(names) == bool(args.all_skills):
                raise ValueError("add requires Skill names or --all")
            changes = add_to_catalog(
                args.source,
                names,
                all_skills=bool(args.all_skills),
                quiet=bool(args.json),
            )
            activation = f"seiton use {' '.join(names)}" if names else None
            payload = {
                "source": args.source,
                "added": changes["added"],
                "changed": changes["changed"],
                "activation": activation,
            }
            if args.json:
                print(json.dumps(payload, ensure_ascii=False, indent=2))
            else:
                print(f"Added to catalog: {', '.join(changes['added']) or 'none'}")
                print(f"Changed in catalog: {', '.join(changes['changed']) or 'none'}")
                if activation:
                    print(f"Activate with: {activation}")
            return 0

        if args.command == "restore":
            locked = locked_skills()
            missing = restore_if_needed(locked, locked, quiet=bool(args.json))
            payload = {"restored": missing}
            if args.json:
                print(json.dumps(payload, ensure_ascii=False, indent=2))
            else:
                print(
                    f"Restored: {', '.join(missing)}"
                    if missing
                    else "External Skills are already restored"
                )
            return 0

        if args.command == "update":
            if bool(args.skills) == bool(args.all_skills):
                raise ValueError("update requires Skill names or --all")
            names = [] if args.all_skills else args.skills
            changes = update_catalog(names, quiet=bool(args.json))
            impact = "Central changes affect every project linked to these Skills."
            payload = {
                "updated": names or "all",
                "changed": changes["changed"],
                "impact": impact,
            }
            if args.json:
                payload["upstream"] = changes["upstream"].stdout.strip()
                print(json.dumps(payload, ensure_ascii=False, indent=2))
            else:
                print(
                    f"Updated: {', '.join(names)}"
                    if names
                    else "Updated all external Skills"
                )
                print(f"Changed in catalog: {', '.join(changes['changed']) or 'none'}")
                print(f"WARNING: {impact}")
            return 0

        project = resolve_project(args.project or Path.cwd())
        locked = locked_skills()
        sources, managed = catalog(locked)

        if args.command == "status":
            payload = status_payload(project, sources, managed, locked)
            if args.json:
                print(json.dumps(payload, ensure_ascii=False, indent=2))
            else:
                print_status(payload)
            return 0

        if args.command in {"list", "ls"}:
            payload = catalog_payload(project, sources, locked, profiles())
            if args.json:
                print(json.dumps(payload, ensure_ascii=False, indent=2))
            else:
                print_catalog(payload)
            return 0

        if args.command in {"use", "minimal"}:
            profile = args.profile if args.command == "use" else None
            skills = args.skills if args.command == "use" else []
            if args.command == "use" and not profile and not skills:
                raise ValueError("use requires Skill names or --profile")
            names = requested_names(skills, profile)
            dry_run = args.dry_run
            if not dry_run:
                restore_if_needed(names, locked, quiet=args.json)
                sources, managed = catalog(locked)
            changed, changes = activate(
                project, names, sources, managed, dry_run=dry_run
            )
            payload = {
                "project": str(project),
                "selected": names,
                "profile": profile,
                "dry_run": dry_run,
                "changed": changed,
                "clients": changes,
                "context": estimate_sources(names, sources),
            }
            if args.json:
                print(json.dumps(payload, ensure_ascii=False, indent=2))
            else:
                print_activation(payload)
            return 0

        if args.command == "check":
            payload = run_check(project, sources, managed, locked)
            if args.json:
                print(json.dumps(payload, ensure_ascii=False, indent=2))
            else:
                print(payload["repository"]["output"])
                print(
                    "Project links: OK"
                    if status_is_healthy(payload["project"])
                    else "Project links: ERROR"
                )
            return 0 if payload["ok"] else 1
    except (OSError, KeyError, ValueError, subprocess.CalledProcessError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    parser.error(f"unknown command: {args.command}")


if __name__ == "__main__":
    raise SystemExit(main())
