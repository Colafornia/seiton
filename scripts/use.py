#!/usr/bin/env python3

import argparse
import json
import os
import re
import subprocess
import sys
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EXTERNAL = ROOT / "external"
BASE_SKILLS = ["seiton"]
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
    return list(dict.fromkeys(BASE_SKILLS + names))


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
        command = ["npx", "skills", "add", source]
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
    groups = {"owned": [], "open_source": {}, "local": []}
    local_root = (ROOT / "local").resolve()
    for name, path in sorted(sources.items()):
        if name == "seiton":
            continue
        installed = (path / "SKILL.md").is_file()
        metadata = (
            skill_metadata(path)
            if installed
            else {"title": name.replace("-", " ").title(), "description": ""}
        )
        item = {"name": name, **metadata, "installed": installed}
        if name in locked:
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
        if not path or not (path / "SKILL.md").is_file():
            continue
        metadata = skill_metadata(path)
        metadata_chars += len(name) + len(metadata["description"])
        body_chars += len((path / "SKILL.md").read_text(encoding="utf-8"))
        measured.append(name)
    return {
        "discovery_tokens": (metadata_chars + 3) // 4,
        "body_tokens_if_invoked": (body_chars + 3) // 4,
        "measured": measured,
        "approximate": True,
    }


def status_payload(project, sources, managed):
    clients = {}
    all_names = set()
    managed_names = set()
    foreign_names = set()
    broken = []

    for client, directory in CLIENTS.items():
        links = project / directory / "skills"
        entries = []
        if links.is_dir():
            for link in sorted(links.iterdir(), key=lambda path: path.name):
                item = {"name": link.name, "kind": "foreign", "broken": False}
                if link.is_symlink():
                    target = link_target(link)
                    item["target"] = str(target)
                    item["broken"] = not (target / "SKILL.md").is_file()
                    if target in managed:
                        item["kind"] = "managed"
                elif (link / "SKILL.md").is_file():
                    item["target"] = str(link.resolve())
                else:
                    item["broken"] = True
                entries.append(item)
                all_names.add(link.name)
                (managed_names if item["kind"] == "managed" else foreign_names).add(link.name)
                if item["broken"]:
                    broken.append(str(link))
        clients[client] = entries

    active = {
        client: [entry["name"] for entry in entries]
        for client, entries in clients.items()
    }
    signatures = {
        client: tuple(
            (
                entry["name"],
                entry.get("target"),
                entry["kind"],
                entry["broken"],
            )
            for entry in entries
        )
        for client, entries in clients.items()
    }
    return {
        "project": str(project),
        "active": active,
        "synced": len(set(signatures.values())) <= 1,
        "managed": sorted(managed_names),
        "foreign": sorted(foreign_names),
        "broken": sorted(broken),
        "context": estimate_sources(sorted(all_names), sources),
        "clients": clients,
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


def print_status(payload):
    print(f"Project: {payload['project']}")
    for client, names in payload["active"].items():
        print(f"{client.capitalize()}: {', '.join(names) or 'none'}")
    print(f"Synced: {'yes' if payload['synced'] else 'no'}")
    print(f"Managed: {', '.join(payload['managed']) or 'none'}")
    print(f"Foreign: {', '.join(payload['foreign']) or 'none'}")
    print(f"Broken: {', '.join(payload['broken']) or 'none'}")
    context = payload["context"]
    print(
        "Context: "
        f"~{context['discovery_tokens']} discovery tokens; "
        f"~{context['body_tokens_if_invoked']} body tokens if all invoked"
    )


def print_catalog(payload):
    print("Profiles")
    for name, config in payload["profiles"].items():
        print(f"  {name}: {', '.join(config['skills']) or 'minimal'}")
    labels = {"owned": "Owned", "local": "Local"}
    for group in ("owned", "local"):
        print(labels[group])
        for item in payload["groups"][group]:
            print(f"  {item['title']} ({item['name']}): {item['description']}")
    print("Open source")
    for author, items in payload["groups"]["open_source"].items():
        print(f"  {author}")
        for item in items:
            suffix = "" if item["installed"] else " [not restored]"
            print(f"    {item['title']} ({item['name']}){suffix}: {item['description']}")


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


def run_check(project, sources, managed):
    repository = subprocess.run(
        [sys.executable, str(ROOT / "scripts/check.py")],
        capture_output=True,
        text=True,
    )
    status = status_payload(project, sources, managed)
    project_ok = status["synced"] and not status["broken"]
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
    add_common_options(parser)
    parser.add_argument("--dry-run", action="store_true")

    legacy = parser.add_mutually_exclusive_group()
    legacy.add_argument("--profile", help=argparse.SUPPRESS)
    legacy.add_argument("--skill", nargs="+", help=argparse.SUPPRESS)
    legacy.add_argument("--catalog", action="store_true", help=argparse.SUPPRESS)

    subcommands = parser.add_subparsers(dest="command")
    for name, aliases in (
        ("status", []),
        ("list", ["ls"]),
        ("minimal", []),
        ("restore", []),
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

    update = subcommands.add_parser("update")
    add_common_options(update, suppressed=True)
    update.add_argument("skills", nargs="*")
    return parser


def main(argv=None):
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.catalog:
        args.command = "list"
        args.json = True
    elif args.profile or args.skill:
        args.command = "use"
        args.skills = args.skill or []
    elif not args.command:
        args.command = "status"

    try:
        if args.dry_run and args.command not in {"use", "minimal"}:
            raise ValueError("--dry-run is supported only by use and minimal")
        project = resolve_project(args.project or Path.cwd())
        locked = locked_skills()
        sources, managed = catalog(locked)

        if args.command == "status":
            payload = status_payload(project, sources, managed)
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

        if args.command == "restore":
            missing = restore_if_needed(locked, locked, quiet=args.json)
            payload = {"project": str(project), "restored": missing}
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
            command = [
                "npx",
                "skills",
                "update",
                *args.skills,
                "--project",
                "--yes",
            ]
            result = subprocess.run(
                command,
                cwd=EXTERNAL,
                check=True,
                **({"capture_output": True, "text": True} if args.json else {}),
            )
            payload = {
                "project": str(project),
                "updated": args.skills or "all",
                **({"upstream": result.stdout.strip()} if args.json else {}),
            }
            if args.json:
                print(json.dumps(payload, ensure_ascii=False, indent=2))
            else:
                print(
                    f"Updated: {', '.join(args.skills)}"
                    if args.skills
                    else "Updated all external Skills"
                )
            return 0

        if args.command == "check":
            payload = run_check(project, sources, managed)
            if args.json:
                print(json.dumps(payload, ensure_ascii=False, indent=2))
            else:
                print(payload["repository"]["output"])
                print(
                    "Project links: OK"
                    if payload["project"]["synced"] and not payload["project"]["broken"]
                    else "Project links: ERROR"
                )
            return 0 if payload["ok"] else 1
    except (OSError, KeyError, ValueError, subprocess.CalledProcessError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    parser.error(f"unknown command: {args.command}")


if __name__ == "__main__":
    raise SystemExit(main())
