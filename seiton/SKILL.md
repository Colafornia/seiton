---
name: seiton
description: >
  Manage a project's Seiton-controlled Skill overlay for Codex and Claude Code.
  Use when the user asks to inspect, select, replace, or minimize project
  Skills from the central catalog.
---

# seiton

Use the `seiton` CLI to manage catalog links. Do not copy Skill contents into a
project or install user-managed Skills globally.

## Choose and preview

1. Resolve the current Git root, falling back to the current directory.
2. For a bare invocation, run `seiton list --project <project> --json` and
   `seiton status --project <project> --json` without changing links.
3. Offer the available profiles, a custom selection, and `minimal`. Show names
   and metadata from `list`; do not read individual Skill bodies. Treat bundled
   `seiton` like any other optional selection.
4. Preview the exact command with `--dry-run --json`:

   ```sh
   seiton use <name> [...] --project <project> --dry-run --json
   seiton use --profile <profile> --project <project> --dry-run --json
   seiton minimal --project <project> --dry-run --json
   ```

5. Show added, removed, replaced, preserved, conflicts, and approximate context
   cost. Wait for explicit confirmation.

## Execute and verify

Run only the confirmed command. A selection replaces the previous
Seiton-managed overlay for both clients; `minimal` selects an empty overlay.
Preserve project directories and links outside the catalog.

Finish project changes with `seiton status --project <project> --json` and
report the final selection, changes, preserved entries, conflicts, and context
estimate. Newly linked Skills may require a new session for native discovery;
the current session keeps any Skill content already loaded.
