#!/usr/bin/env python3

import argparse
import json
import shutil
import subprocess
import sys
from pathlib import Path

if __package__:
    from .catalog import (
        ROOT,
        add_to_catalog,
        catalog,
        estimate_sources,
        locked_skills,
        profiles,
        restore_if_needed,
        skill_metadata,
        update_catalog,
    )
    from .check import validate_workspace
    from .selection import (
        CLIENTS,
        SelectionConflict,
        apply_selection,
        global_skills_paths,
        inspect_selection,
        plan_selection,
        selection_is_healthy,
    )
else:
    from catalog import (
        ROOT,
        add_to_catalog,
        catalog,
        estimate_sources,
        locked_skills,
        profiles,
        restore_if_needed,
        skill_metadata,
        update_catalog,
    )
    from check import validate_workspace
    from selection import (
        CLIENTS,
        SelectionConflict,
        apply_selection,
        global_skills_paths,
        inspect_selection,
        plan_selection,
        selection_is_healthy,
    )


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


def print_selection(payload):
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


def print_selection_conflict(error, project, profile=None):
    subject = f'profile "{profile}"' if profile else "selected Skills"
    lines = [f"ERROR: cannot activate {subject}."]
    for scope in ("project", "global"):
        names = sorted({
            item["skill"] for item in error.conflicts if item["scope"] == scope
        })
        if not names:
            continue
        lines += ["", f"Conflicts with existing {scope} Skills ({len(names)}):"]
        lines += [f"  {name}" for name in names]

    lines += ["", "Detected locations:"]
    compact = len({item["skill"] for item in error.conflicts}) > 1
    locations = set()
    for item in error.conflicts:
        client = f"{item['client'].capitalize()}:"
        path = Path(item["path"])
        if compact:
            path = path.parent / "<name>"
        location = f"{display_path(path, project)} ({item['kind']})"
        if item["target"]:
            target = Path(item["target"])
            if compact and target.name == item["skill"]:
                target = target.parent / "<name>"
            location += f" -> {display_path(target, project)}"
        locations.add((list(CLIENTS).index(item["client"]), client, location))
    for _, client, location in sorted(locations):
        lines.append(f"  {client:<8}{location}")

    lines += [
        "",
        "No files were changed.",
        "Seiton does not replace project-owned or global Skills.",
        "Back up and remove the conflicting Skills before retrying.",
        'Run "seiton status" to inspect ownership.',
    ]
    print("\n".join(lines), file=sys.stderr)


def run_check(project, sources, managed, locked=None):
    repository = validate_workspace()
    status = inspect_selection(project, sources, managed, locked)
    project_ok = selection_is_healthy(status)
    return {
        "ok": repository["ok"] and project_ok,
        "repository": {
            "ok": repository["ok"],
            "output": repository["summary"] if repository["ok"] else "\n".join(
                f"ERROR: {error}" for error in repository["errors"]
            ),
        },
        "project": status,
    }


def add_common_options(parser, suppressed=False):
    default = argparse.SUPPRESS if suppressed else None
    parser.add_argument("--project", type=Path, default=default)
    parser.add_argument("--json", action="store_true", default=default)


def build_parser():
    parser = argparse.ArgumentParser(
        description="Manage a project-specific Seiton Skill selection"
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

    switch = subcommands.add_parser(
        "switch", help="Replace the current Seiton-managed selection"
    )
    add_common_options(switch, suppressed=True)
    switch.add_argument("skills", nargs="*")
    switch.add_argument("--profile")
    switch.add_argument("--dry-run", action="store_true", default=argparse.SUPPRESS)

    enable = subcommands.add_parser(
        "enable", help="Add Skills without removing the current selection"
    )
    add_common_options(enable, suppressed=True)
    enable.add_argument("skills", nargs="+")
    enable.add_argument("--dry-run", action="store_true", default=argparse.SUPPRESS)

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


def command_add(args):
    names = args.skills or []
    if bool(names) == bool(args.all_skills):
        raise ValueError("add requires Skill names or --all")
    changes = add_to_catalog(
        args.source,
        names,
        all_skills=bool(args.all_skills),
        quiet=bool(args.json),
    )
    activation = f"seiton switch {' '.join(names)}" if names else None
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


def command_restore(args):
    locked = locked_skills()
    missing = restore_if_needed(locked, locked, quiet=bool(args.json))
    if args.json:
        print(json.dumps({"restored": missing}, ensure_ascii=False, indent=2))
    else:
        print(
            f"Restored: {', '.join(missing)}"
            if missing
            else "External Skills are already restored"
        )
    return 0


def command_update(args):
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


def command_selection(args, project, locked, sources, managed):
    profile = args.profile if args.command == "switch" else None
    skills = args.skills if args.command in {"switch", "enable"} else []
    if args.command == "switch" and not profile and not skills:
        raise ValueError("switch requires Skill names or --profile")
    names = requested_names(skills, profile)
    if args.command == "enable":
        status = inspect_selection(project, sources, managed, locked)
        active = sorted({
            entry["name"]
            for layers in status["clients"].values()
            for entry in layers["seiton"]
        })
        names = list(dict.fromkeys([*active, *names]))
    if not args.dry_run:
        # Conflicts must abort before restore can modify the catalog.
        plan_selection(project, names, sources, managed)
        restore_if_needed(names, locked, quiet=args.json)
        sources, managed = catalog(locked)
    changed, changes = apply_selection(
        project, names, sources, managed, dry_run=args.dry_run
    )
    payload = {
        "project": str(project),
        "selected": names,
        "profile": profile,
        "dry_run": args.dry_run,
        "changed": changed,
        "clients": changes,
        "context": estimate_sources(names, sources),
    }
    if args.json:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        print_selection(payload)
    return 0


def command_check(args, project, locked, sources, managed):
    payload = run_check(project, sources, managed, locked)
    if args.json:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        print(payload["repository"]["output"])
        print(
            "Project links: OK"
            if selection_is_healthy(payload["project"])
            else "Project links: ERROR"
        )
    return 0 if payload["ok"] else 1


def command_project(args):
    project = resolve_project(args.project or Path.cwd())
    locked = locked_skills()
    sources, managed = catalog(locked)

    if args.command == "status":
        payload = inspect_selection(project, sources, managed, locked)
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
    if args.command in {"switch", "enable", "minimal"}:
        return command_selection(args, project, locked, sources, managed)
    if args.command == "check":
        return command_check(args, project, locked, sources, managed)
    raise ValueError(f"unknown command: {args.command}")


def main(argv=None):
    parser = build_parser()
    args = parser.parse_args(argv)
    args.command = args.command or "status"

    try:
        if args.dry_run and args.command not in {"switch", "enable", "minimal"}:
            raise ValueError(
                "--dry-run is supported only by switch, enable, and minimal"
            )
        if args.command == "switch" and args.profile and args.skills:
            raise ValueError(
                "switch Skill names and --profile are mutually exclusive"
            )
        if args.command == "add":
            return command_add(args)
        if args.command == "restore":
            return command_restore(args)
        if args.command == "update":
            return command_update(args)
        return command_project(args)
    except SelectionConflict as exc:
        profile = args.profile if args.command == "switch" else None
        if args.json:
            print(json.dumps({
                "error": {
                    "code": "selection_conflict",
                    "profile": profile,
                    "changed": False,
                    "conflicts": exc.conflicts,
                }
            }, ensure_ascii=False, indent=2))
        else:
            project = resolve_project(args.project or Path.cwd())
            print_selection_conflict(exc, project, profile)
        return 1
    except (OSError, KeyError, ValueError, subprocess.CalledProcessError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
