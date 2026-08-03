# seiton

seiton is a central Skill workspace for coding agents. Keep owned, private, and
open-source Skills in one place, then activate only what each repository needs.

![seiton keeps Skills in one central workspace and activates a repository-specific selection](docs/seiton-workflow.svg)

## Why

Skills are easy to install and easy to forget. Global installations grow
stale, add discovery context to every session, and spread Skill management
across agent-specific directories.

seiton instead:

- keeps owned, private, and open-source Skills in one source of truth;
- activates an exact Seiton-managed overlay for each repository;
- allows an empty overlay with `minimal`;
- switches Codex and Claude Code together;
- restores and updates open-source Skills without committing downloaded copies;
- lets you use Skills unchanged, combine them, or build on them.

`npx skills` handles open-source Skill installation and updates. seiton adds
the central catalog and repository-specific selection. Its bundled `seiton`
control Skill is available but never activated implicitly.

## Workspace structure

```text
~/seiton/
├── seiton/                     Optional bundled control Skill
├── <owned-skill>/              Skills you maintain
├── external/
│   └── skills-lock.json        Open-source Skill sources
├── local/                      Private Skills, ignored
├── scripts/                    CLI and validator
└── skillsets.toml              Reusable selections
```

The workspace can be its own Git repository and sync across machines.
Downloaded open-source Skill copies, private Skills, and repository links stay
uncommitted.

## Install

### Requirements

- Python 3.11 or newer
- Node.js 22.20 or newer with `npx`
- macOS or Linux

Create a clean workspace:

```sh
npx seiton@latest init
```

This creates `~/seiton`, installs the `seiton` command in `~/.local/bin`, and
starts with no owned Skills, open-source dependencies, profiles, or active
overlay. The bundled control Skill is present but optional. To use another
location:

```sh
npx seiton@latest init ~/Tools/seiton
```

Ensure `~/.local/bin` is on `PATH`. The command is available globally; your
Skills are not installed globally.

## Use

Run commands from anywhere inside a Git repository:

```sh
seiton                         # current selection
seiton list                    # profiles and catalog
seiton use my-skill tdd        # exact Seiton-managed overlay
seiton use --profile my-work   # reusable selection
seiton use seiton              # explicitly enable the control Skill
seiton minimal                 # empty Seiton-managed overlay
seiton check                   # validate catalog and links
```

Use `--project PATH` to target another repository, `--json` for
machine-readable output, and `--dry-run` to preview `use` or `minimal`.

seiton links the selected Skills into:

- Codex and compatible agents: `<repo>/.agents/skills/<name>`
- Claude Code: `<repo>/.claude/skills/<name>`

These are machine-specific absolute symlinks. Add the generated directories to
each target repository's ignore rules unless that repository intentionally
tracks its own Skill links:

```gitignore
.agents/skills/
.claude/skills/
```

## Build your catalog

Add a Skill you maintain directly to the workspace:

```text
~/seiton/my-skill/SKILL.md
```

Keep a private or unverified Skill under the ignored `local/` directory:

```text
~/seiton/local/my-private-skill/SKILL.md
```

Add an open-source Skill from `external/`:

```sh
cd ~/seiton/external
npx skills add owner/repository \
  --skill skill-name \
  --agent codex \
  --agent claude-code \
  --yes
```

Commit `external/skills-lock.json`, not the downloaded source. Restore the
catalog on another machine with:

```sh
seiton restore
```

Define a reusable selection in `skillsets.toml`:

```toml
[profiles.my-work]
skills = ["my-skill", "tdd"]
```

Machine-specific profile overrides belong in the ignored
`.agent/skillsets.toml`. A local profile with the same name replaces the shared
profile.

## Conversational selection

The bundled control Skill is optional. After `seiton use seiton`, invoke
`$seiton` without arguments to
choose a profile, custom set, or minimal mode. It:

1. reads the catalog and current selection;
2. groups Skills by source;
3. previews the exact link and context changes;
4. asks for confirmation;
5. applies the selection and verifies the result.

Newly linked Skills can be used explicitly in the current session. Start a new
session only when you need native `$name` discovery or implicit triggering.
`minimal` changes future discovery; it cannot remove context already loaded by
the current session.

For a one-off open-source Skill that should not join the catalog, use
`npx skills use` directly.

## Context estimates

`status` and selection previews report a dependency-free approximation:

- discovery tokens: Skill `name` plus `description`;
- body tokens: full `SKILL.md` content if every active Skill were invoked.

References, scripts, tool output, system Skills, and plugin Skills are excluded.
These estimates help compare selections; they are not billing or
remaining-context measurements.

## Maintain the catalog

Update locked open-source Skills explicitly:

```sh
seiton update
seiton update tdd codebase-design
```

Commit the changed `external/skills-lock.json`. The lock records sources, Skill
paths, and hashes; current entries do not pin upstream commits.

Update an npm-installed seiton core without touching user content:

```sh
npx seiton@latest upgrade
```

Pass the workspace path after `upgrade` if it is not `~/seiton`. Core upgrades
replace only `scripts/` and `seiton/`. They preserve owned Skills, `local/`,
`external/skills-lock.json`, `skillsets.toml`, `.gitignore`, and the workspace
README. Maintainer clones should update with Git instead.

Run validation after catalog changes:

```sh
seiton check
```

## Development

Run the CLI tests, installer tests, repository check, and package boundary
audit:

```sh
npm test
npm run check
npm pack --dry-run
```

## License

seiton core and the original contents of this source repository are available
under the [MIT License](LICENSE). User-defined and open-source Skills retain
their own licenses.
