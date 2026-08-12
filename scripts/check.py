#!/usr/bin/env python3

import json
import os
import re
import sys
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def skill_name(path):
    text = (path / "SKILL.md").read_text(encoding="utf-8")
    if not text.startswith("---\n"):
        raise ValueError("missing YAML frontmatter")
    frontmatter = text.split("---", 2)[1]
    match = re.search(r"^name:\s*[\"']?([^\"'#\n]+?)[\"']?\s*$", frontmatter, re.M)
    if not match:
        raise ValueError("missing name")
    return match.group(1).strip()


def source_dirs(root=ROOT):
    bundled = root / "seiton"
    owned = list((root / "owned").glob("*"))
    external = list((root / "external/.agents/skills").glob("*"))
    local = list((root / "local").glob("*")) if (root / "local").exists() else []
    return {
        "bundled": [bundled] if (bundled / "SKILL.md").is_file() else [],
        "owned": sorted(path for path in owned if (path / "SKILL.md").is_file()),
        "external": sorted(path for path in external if (path / "SKILL.md").is_file()),
        "local": sorted(path for path in local if (path / "SKILL.md").is_file()),
    }


def validate_workspace(root=ROOT):
    errors = []
    sources = source_dirs(root)
    skills = {}

    for paths in sources.values():
        for path in paths:
            try:
                name = skill_name(path)
            except (OSError, ValueError) as exc:
                errors.append(f"{path.relative_to(root)}: {exc}")
                continue
            if name != path.name:
                errors.append(f"{path.relative_to(root)}: name is {name!r}")
            if name in skills:
                errors.append(f"duplicate skill {name!r}: {skills[name]} and {path}")
            skills[name] = path.resolve()

    lock_path = root / "external/skills-lock.json"
    try:
        locked = set(json.loads(lock_path.read_text(encoding="utf-8"))["skills"])
    except (OSError, KeyError, json.JSONDecodeError) as exc:
        errors.append(f"{lock_path.relative_to(root)}: {exc}")
        locked = set()
    installed = {path.name for path in sources["external"]}
    external_cache = root / "external/.agents/skills"
    if external_cache.exists() and locked != installed:
        errors.append(
            f"external lock mismatch: locked={sorted(locked)}, "
            f"installed={sorted(installed)}"
        )
    local_names = {
        path.name
        for category in ("bundled", "owned", "local")
        for path in sources[category]
    }
    if locked & local_names:
        errors.append(
            f"lock names collide with local sources: {sorted(locked & local_names)}"
        )

    required_ignores = {
        ".agent/",
        ".agents/skills/",
        ".claude/skills/",
        "external/.agents/",
        "external/.claude/",
        "local/",
    }
    ignores = set((root / ".gitignore").read_text(encoding="utf-8").splitlines())
    if required_ignores - ignores:
        errors.append(f"missing ignore rules: {sorted(required_ignores - ignores)}")

    profiles = {}
    profile_paths = [root / "skillsets.toml"]
    local_profiles = root / ".agent/skillsets.toml"
    if local_profiles.is_file():
        profile_paths.append(local_profiles)
    try:
        for profile_path in profile_paths:
            profiles.update(
                tomllib.loads(profile_path.read_text(encoding="utf-8"))["profiles"]
            )
    except (OSError, KeyError, tomllib.TOMLDecodeError) as exc:
        errors.append(f"{profile_path.relative_to(root)}: {exc}")
        profiles = {}
    for profile, config in profiles.items():
        names = config.get("skills", [])
        if not isinstance(names, list) or not all(isinstance(name, str) for name in names):
            errors.append(f"profile {profile!r} must contain a string list")
            continue
        missing = sorted(set(names) - (set(skills) | locked))
        if missing:
            errors.append(f"profile {profile!r} references missing skills: {missing}")

    active = {}
    clients = (".agents", ".claude")
    has_active_links = any((root / client / "skills").is_dir() for client in clients)
    managed = set(skills.values()) | {
        (external_cache / name).resolve() for name in locked
    }
    for client in clients:
        link_dir = root / client / "skills"
        if not link_dir.is_dir():
            if has_active_links:
                errors.append(f"missing project entry: {link_dir.relative_to(root)}")
            active[client] = set()
            continue
        names = set()
        for link in link_dir.iterdir():
            names.add(link.name)
            if not link.is_symlink():
                errors.append(f"{link.relative_to(root)} is not a symlink")
                continue
            target = (link.parent / os.readlink(link)).resolve()
            if target not in managed:
                errors.append(f"{link.relative_to(root)} points outside the catalog")
            elif not (target / "SKILL.md").is_file():
                errors.append(f"{link.relative_to(root)} has no readable SKILL.md")
        active[client] = names
    if active.get(".agents") != active.get(".claude"):
        errors.append("Codex and Claude Code active skill sets differ")

    counts = ", ".join(f"{name}={len(paths)}" for name, paths in sources.items())
    return {
        "ok": not errors,
        "errors": errors,
        "summary": f"OK: {counts}; active={','.join(sorted(active['.agents']))}",
    }


def main():
    report = validate_workspace()
    if not report["ok"]:
        for error in report["errors"]:
            print(f"ERROR: {error}", file=sys.stderr)
        return 1
    print(report["summary"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
