---
name: reference-repo
description: >
  Maintain persistent, ref-isolated shallow clones of upstream reference
  repositories under ~/.agent-context, sync and commit-pin them at task start,
  and consult them on demand. Use when a task needs a stable, on-disk copy of
  external repos (library source, docs, examples, specs) to reason against —
  typically at task start, before investigating or implementing. Do not use for
  the repository being edited, for one-off web lookups, or for repos already
  checked out in the workspace.
---

# Reference Repo

Keep upstream reference repos on disk as **shallow, ref-isolated, commit-pinned**
clones, and read from them on demand — never bulk-load a repo into context.

## Model

Four ideas, one tool:

- **Ref-isolated clone dirs** (lburgazzoli/agents): each source lives at
  `repos/<owner>/<repo>@<ref>/`. The same repo at different refs coexists as
  separate dirs; a sync never switches a dir to a different ref in place.
- **Independent reconcile, then aggregate** (FluxCD): each source syncs on its
  own; one failing source does not block the others. `lock.yaml` is the
  aggregate of all pinned commits for this task.
- **Commit pin + include/ignore** (Repomix): at sync, record each source's
  commit SHA in `lock.yaml` so the reference cannot move mid-task. Per-source
  `include`/`ignore` filters scope what is worth reading.
- **On-demand retrieval** (GitMCP): the clones are on disk so you can
  `grep`/`ls`/read specific paths. Retrieve only what the current question
  needs; do not dump a whole repo into context.

## Layout

```
~/.agent-context/
├── repos.yaml          registry: owner/repo -> url, ref, include, ignore
├── lock.yaml           per-task commit pin (aggregate of pinned sources)
└── repos/
    └── <owner>/<repo>@<ref>/   shallow clone, one per ref
```

`repos.yaml` entry:

```yaml
repos:
  TanStack/table:
    url: https://github.com/TanStack/table
    ref: main              # branch, tag, or "latest" (newest stable tag)
    include: ["packages/table-core/src/**"]
    ignore: ["**/*.test.ts", "docs/**"]
```

## Task cycle

1. **Sync** at task start — `python3 scripts/repo.py sync [source...]`.
   Clones/fetches each source, resolves `latest` to the newest stable tag, and
   writes every commit SHA into `lock.yaml`. While a source is pinned, a later
   `sync` leaves it untouched — the reference stays stable for the task.
2. **Read on demand** — use `grep`/`ls`/read against the clone dir
   (`python3 scripts/repo.py path <owner/repo>` prints it). Apply that source's
   `include`/`ignore` as path filters: only search inside `include`, skip
   `ignore`. Treat each source as independent; aggregate findings across
   sources at the end, do not conflate them.
3. **Release** at wrap-up — `python3 scripts/repo.py release` drops
   `lock.yaml`. Clones persist, so the next task reuses them and only fetches
   what has moved.

Use `sync --force` to re-pin every source in one pass (e.g. after registry
changes). `sync` never deletes a clone; `release` never deletes a clone.

## Commands

```
python3 scripts/repo.py sync [source...] [--force]   clone/fetch + pin in lock.yaml
python3 scripts/repo.py status                       show pinned commits for this task
python3 scripts/repo.py release                      drop lock.yaml (clones kept)
python3 scripts/repo.py add <owner/repo> <url> [ref] [--include PAT...] [--ignore PAT...]
python3 scripts/repo.py list                         list registry
python3 scripts/repo.py remove <owner/repo>          unregister (clone kept)
python3 scripts/repo.py path <owner/repo>            print the clone dir
```

`REFERENCE_REPOS_DIR` overrides the default `~/.agent-context` (used for tests).

## Completion

- Sync is done when every requested source is either pinned in `lock.yaml` or
  reported failed; a partial run is an honest terminal state, not success.
- Retrieval is done when the specific question is answered from the clone, not
  when the whole repo has been read.
- The task's reference use is done when `release` has run and `status` reports
  no active lock.
