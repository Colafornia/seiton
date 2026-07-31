---
name: seiton
description: >
  Manage a project's minimal agent Skill set from a central catalog for Codex
  and Claude Code. Use when the user asks to inspect, activate, replace,
  restore, update, or minimize project Skills.
---

# seiton

Expose only the Skills a project needs. Keep `seiton` as the sole baseline so
the project can switch again. Use the catalog CLI; do not copy Skill contents
into projects or install user-managed Skills globally.

## Resolve the target

1. Use the current Git root, falling back to the current directory.
2. Resolve this file's real path; its parent is the catalog root.
3. Treat direct child directories as owned Skills, lock entries as open-source
   Skills, and `<catalog-root>/local/*` as local-only Skills.

## Choose interactively

On a bare `$seiton` invocation, do not modify links:

1. Run:

   ```sh
   seiton list --project <project> --json
   seiton status --project <project> --json
   ```

2. Offer `profile`, `custom`, and `minimal`. Show each profile's Skill names.
3. For `custom`, show title, name, and description. Group open-source Skills by
   author. Do not read individual Skill bodies.
4. Use native multi-select when available; otherwise accept comma-separated
   numbers, ranges, or names from one numbered list.
5. Preview the exact choice:

   ```sh
   seiton use <name> [...] --project <project> --dry-run --json
   seiton minimal --project <project> --dry-run --json
   ```

6. Show the changes and approximate context cost, then wait for confirmation.
7. Apply only the confirmed command and finish with `status --json`.

Keep `seiton` implicit; do not show it as a selectable option.

## Apply explicit requests

Use one of:

```sh
seiton use --profile <profile> --project <project>
seiton use <name> [...] --project <project>
seiton minimal --project <project>
```

Selections replace the previous catalog-managed set for Codex and Claude Code.
Preserve foreign links and real directories. Treat `Already active` as success.

After activation, explicitly read a newly linked Skill when it is needed in the
current session. A new session is optional for native `$name` discovery or
implicit triggering. `minimal` cannot unload context already read by the
current session.

## Maintain profiles

Store reusable combinations in `<catalog-root>/skillsets.toml`:

```toml
[profiles.review]
skills = ["code-review"]
```

Add or edit a profile only when asked. Keep profiles small; they are convenience
lists, not dependency graphs.

## Maintain open-source Skills

Restore the committed lock with:

```sh
seiton restore
```

Update only on an explicit request:

```sh
seiton update [name ...]
```

Before adding a source, inspect its license and notices, then run `npx skills
add` from `<catalog-root>/external/`. Commit only `skills-lock.json`; ignore
downloaded copies and generated links.

## Report

Return the target project, selected profile or names, added and removed links,
preserved foreign entries, conflicts, approximate context cost, and final
status.
