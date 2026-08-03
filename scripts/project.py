import json
import os
from pathlib import Path

if __package__:
    from .catalog import estimate_sources
else:
    from catalog import estimate_sources

CLIENTS = {"codex": ".agents", "claude": ".claude"}


def link_target(link):
    return (link.parent / os.readlink(link)).resolve()


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
        for global_path in global_skills_paths(client):
            for name in names:
                conflict = global_path / name
                if conflict.exists() or conflict.is_symlink():
                    conflicts.append(f"conflicting global path: {conflict}")
        for values in changes.values():
            values.sort()
        plan[client] = changes

    if conflicts:
        raise ValueError("; ".join(conflicts))
    return plan


def activation_operations(plan):
    operations = []
    for client, changes in plan.items():
        operations.extend(
            (client, "unlink", name) for name in changes["removed"]
        )
        for name in changes["replaced"]:
            operations.extend(
                ((client, "unlink", name), (client, "symlink", name))
            )
        operations.extend(
            (client, "symlink", name) for name in changes["added"]
        )
    return operations


def format_operations(operations):
    return ", ".join(
        f"{client}:{action}:{name}" for client, action, name in operations
    ) or "none"


def apply_activation(project, sources, operations):
    completed = []
    try:
        for directory in CLIENTS.values():
            (project / directory / "skills").mkdir(parents=True, exist_ok=True)
        for client, action, name in operations:
            link = project / CLIENTS[client] / "skills" / name
            if action == "unlink":
                link.unlink()
            else:
                link.symlink_to(sources[name], target_is_directory=True)
            completed.append((client, action, name))
    except OSError as exc:
        incomplete = operations[len(completed):]
        raise ValueError(
            f"reconcile failed: {exc}; "
            f"completed: {format_operations(completed)}; "
            f"incomplete: {format_operations(incomplete)}"
        ) from exc


def verify_activation(project, names, sources, managed, operations):
    status = status_payload(project, sources, managed)
    expected = {
        (name, str(sources[name].resolve()), "healthy") for name in names
    }
    invalid = [
        client
        for client, layers in status["clients"].items()
        if {
            (entry["name"], entry["target"], entry["health"])
            for entry in layers["seiton"]
        }
        != expected
    ]
    if invalid:
        raise ValueError(
            f"reconcile verification failed for: {', '.join(invalid)}; "
            f"completed: {format_operations(operations)}; incomplete: none"
        )


def activate(project, names, sources, managed, dry_run=False):
    plan = activation_plan(project, names, sources, managed)
    operations = activation_operations(plan)
    if dry_run:
        return bool(operations), plan

    apply_activation(project, sources, operations)
    verify_activation(project, names, sources, managed, operations)
    return bool(operations), plan
