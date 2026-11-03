<h1 align="center">seiton</h1>

<p align="center">A central Skill catalog with repository-specific activation for Codex and Claude Code.</p>

![seiton keeps Skills in one central workspace and activates a repository-specific selection](docs/seiton-workflow.svg)

## Why seiton

Installing a Skill is easy. Keeping the right Skills active across repositories
and coding agents is not.

seiton gives you one place to:

- maintain owned, private, and open-source Skills;
- activate only what each repository needs;
- apply the same managed selection to Codex and Claude Code;
- preserve existing project and global Skills;
- restore and update open-source Skills without committing downloaded copies.

Use Skills unchanged, combine them, or adapt them into new workflows. Your
catalog stays central; each repository gets its own focused selection.

`npx skills` handles open-source sources and updates. seiton adds the catalog,
repository selection, and verification around it.

## Workspace structure

```text
~/seiton/
├── seiton/                     Optional control Skill
├── owned/                      Skills you maintain
│   └── <skill>/
├── external/
│   └── skills-lock.json        Open-source sources and hashes
├── local/                      Private or unverified Skills, ignored
├── scripts/                    CLI and validation
└── skillsets.toml              Reusable selections
```

The workspace can be its own Git repository and sync across machines. Commit
your owned Skills, configuration, and `external/skills-lock.json`—not downloaded
copies, private Skills, or repository links.

## Quick start

Requires Python 3.11+, Node.js 22.20+ with `npx`, and macOS or Linux.

The npm package is not published yet. Install from source:

```sh
git clone https://github.com/Colafornia/seiton.git seiton-src
cd seiton-src
npm link
seiton init
```

`seiton init` creates `~/seiton` and installs the command in `~/.local/bin`.
Use a different workspace path if needed:

```sh
seiton init ~/Tools/seiton
```

Ensure `~/.local/bin` is on `PATH`.

### 1. Build your catalog

Put Skills you maintain in `owned/`:

```text
~/seiton/owned/my-skill/SKILL.md
```

Keep private or unverified Skills in the ignored `local/` directory:

```text
~/seiton/local/my-private-skill/SKILL.md
```

Add reviewed open-source Skills by name:

```sh
seiton add owner/repository skill-name
seiton add owner/repository one two
```

Use `--all` only after reviewing the entire source. Adding a Skill updates the
catalog; it does not activate the Skill in any repository.

### 2. Choose Skills for a repository

Run these commands anywhere inside the target Git repository:

```sh
seiton list
seiton status
seiton switch code-review tdd --dry-run
seiton switch code-review tdd
seiton enable write-github
seiton check
```

The selection is linked into both supported clients:

```text
<repo>/.agents/skills/   Codex and compatible agents
<repo>/.claude/skills/  Claude Code
```

seiton replaces only its managed overlay and preserves other project Skills.
The links are machine-specific, so ignore them unless the repository
intentionally tracks its own links:

```gitignore
.agents/skills/
.claude/skills/
```

### 3. Maintain the catalog

```sh
seiton update tdd code-review   # update selected open-source Skills
seiton update --all             # update every open-source Skill
seiton restore                  # restore missing downloaded copies
seiton check                    # validate the catalog and project links
```

Central updates are immediately visible to repositories linked to those Skills.
Commit changes to `external/skills-lock.json`.

## Reusable selections

Define a profile in `skillsets.toml`:

```toml
[profiles.review]
skills = ["code-review", "tdd"]
```

Then preview or activate it:

```sh
seiton switch --profile review --dry-run
seiton switch --profile review
```

Machine-specific overrides belong in the ignored `.agent/skillsets.toml`. A
local profile replaces a shared profile with the same name.

Skills that need machine-specific settings can also use user-wide configuration
under `~/.agent/`. For example, `takeaway` reads `~/.agent/takeaway.toml` for
all repositories and uses `<repo>/.agent/takeaway.toml` only when a project
needs an override. This keeps a shared Obsidian vault configured once without
putting its local path in a repository.

The catalog includes selected Skills from
[pstack-claude](https://github.com/michael-denyer/pstack-claude). The `delivery`
profile adds `how`, `architect`, `benchmark-checklist`, and
`create-verification-skill`; `solution-research` also includes `how`.
`blast-radius` and `correct` are available for task-specific activation:

```sh
seiton enable blast-radius correct
```

Pstack's companion Skills and references stay in the catalog without enabling
its `poteto-mode` router or installing plugin hooks. Resolve an activated
Skill's symlink to its catalog directory before following relative references
to a companion. `architect` proceeds from design into implementation by
default; ask for `architect with checkpoint` when you want the design reviewed
before implementation. Codex uses the bundled
`poteto-mode/references/codex-tools.md` mapping for tools, models, and paths.

Use `seiton enable SKILL...` to add Skills without removing the active
selection. Use `seiton minimal` to remove the entire seiton-managed overlay
while leaving other project Skills untouched.

## Conversational selection

The bundled `seiton` control Skill is optional and never activated implicitly:

```sh
seiton switch seiton
```

Then invoke `$seiton` without arguments to inspect the catalog, preview a
profile or custom selection, confirm the change, and verify the result.

Newly linked Skills work immediately when invoked explicitly. Start a new
session only when you need native `$name` discovery or implicit triggering.

## Context estimates

`status` and selection previews estimate:

- discovery tokens from each Skill's `name` and `description`;
- body tokens if every selected `SKILL.md` were invoked.

These dependency-free estimates compare selections. They are not billing,
performance, or remaining-context measurements.

## Command reference

```text
seiton [status] [--project PATH] [--json]
seiton list [--project PATH] [--json]
seiton switch SKILL... [--project PATH] [--dry-run] [--json]
seiton switch --profile NAME [--project PATH] [--dry-run] [--json]
seiton enable SKILL... [--project PATH] [--dry-run] [--json]
seiton minimal [--project PATH] [--dry-run] [--json]
seiton check [--project PATH] [--json]

seiton add SOURCE SKILL... [--json]
seiton add SOURCE --all [--json]
seiton restore [--json]
seiton update SKILL... [--json]
seiton update --all [--json]
```

`ls` is an alias for `list`. For a one-off open-source Skill that should not
join the catalog, use `npx skills use` directly.

## Upgrade

After updating the source checkout, replace the installed core without touching
user content:

```sh
seiton upgrade
```

Pass the workspace path if it is not `~/seiton`. `upgrade` replaces only
`scripts/` and `seiton/`; it preserves your catalog, profiles, local content,
ignore rules, and workspace README.

## Scope and trust

- seiton manages only links it created; project and global Skills remain yours.
- seiton does not audit third-party Skills. Review sources before adding them.
- the lock records sources, paths, and hashes; current entries do not pin
  upstream commits.
- the CLI supports Codex and Claude Code and delegates open-source operations to
  `skills@1.5.21`.

## Development

```sh
npm test
npm run check
npm pack --dry-run
```

## License

seiton core and the original contents of this repository are available under
the [MIT License](LICENSE). Other Skills retain their own licenses.
