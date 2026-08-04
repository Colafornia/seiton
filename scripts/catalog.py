import json
import re
import subprocess
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EXTERNAL = ROOT / "external"
SKILLS_PACKAGE = "skills@1.5.21"


def run_skills(arguments, quiet=False):
    try:
        return subprocess.run(
            ["npx", SKILLS_PACKAGE, *arguments],
            cwd=EXTERNAL,
            check=True,
            **({"capture_output": True, "text": True} if quiet else {}),
        )
    except subprocess.CalledProcessError as exc:
        detail = (exc.stderr or exc.stdout or "").strip()
        message = f"npx {SKILLS_PACKAGE} failed with exit code {exc.returncode}"
        raise ValueError(f"{message}: {detail}" if detail else message) from exc


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
        command = ["add", source]
        for name in skill_names:
            command.extend(["--skill", name])
        command.extend(
            ["--agent", "codex", "--agent", "claude-code", "--yes"]
        )
        run_skills(command, quiet=quiet)
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
    command = ["add", source]
    if all_skills:
        command.extend(["--skill", "*"])
    elif names:
        command.extend(["--skill", *names])
    command.extend(["--agent", "codex", "--agent", "claude-code", "--yes"])
    result = run_skills(command, quiet=quiet)

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
    result = run_skills(
        ["update", *names, "--project", "--yes"], quiet=quiet
    )
    after = locked_skills()
    changed = sorted(
        name for name in set(before) | set(after) if before.get(name) != after.get(name)
    )
    return {"changed": changed, "upstream": result}


def catalog(locked):
    groups = [
        [ROOT / "seiton"],
        list((ROOT / "owned").glob("*")),
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
