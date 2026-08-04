# Repository instructions

- Keep user-owned Skills as direct children of `owned/`.
- Manage open-source Skills only through `npx skills` from `external/`; do not
  edit generated copies directly.
- Keep unverified or private Skills under ignored `local/`.
- Keep third-party copies and project links ignored; commit only
  `external/skills-lock.json`.
- Use `scripts/use.py` to inspect, restore, and activate project Skill sets.
- Keep profiles minimal. A profile is a convenience list, not a dependency
  resolver.
- Keep local agent preferences under ignored `.agent/`.
- Run `python3 scripts/use.py check` after changing layout, profiles, locks, or
  links.
- Run `python3 -m unittest scripts/test_use.py` after changing activation
  behavior.
- Run the Skill Creator `quick_validate.py` after changing a `SKILL.md`.
