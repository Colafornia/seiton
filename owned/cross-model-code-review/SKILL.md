---
name: cross-model-code-review
description: >
  Review one fixed change independently with multiple external model families,
  then verify and consolidate their findings using the existing code-review
  standards. Use when the user explicitly asks for cross-model or multi-model
  code review, or when a high-risk change warrants independent reviewers. Do
  not use for routine review, solution comparison, or review adjudication.
---

# Cross-Model Code Review

Produce one evidence-backed review. Do not modify code. External reviewers are
inputs to the review, not votes.

## 1. Load the review contract

Resolve and read the available `code-review` Skill. Prefer
`<catalog-root>/local/code-review/SKILL.md` when it exists. Use its scope,
Standards, Spec, Temporal correctness, evidence, and reporting rules as the
single review contract. Stop if that Skill is unavailable.

For this workflow, the external models are the independent reviewers. Do not
recursively launch additional reviewers for the three axes.

## 2. Fix one review packet

Resolve the fixed point or diff scope before launching reviewers. Build one
packet containing only:

- the review scope or merge-base;
- goal, acceptance criteria, invariants, and exclusions when available;
- verification already run;
- paths to repository instructions and the resolved `code-review` Skill.

Do not include the implementer's rationale, parent findings, or a preferred
outcome. Tell reviewers that known paths are non-exhaustive and that they must
inspect the repository independently.

Require bounded tool use:

- do not print entire large files, the full repository diff, or unbounded
  repository-wide search results;
- start with `rg`, `git diff --stat` or `--name-only`, and targeted `sed -n`
  ranges;
- batch independent read-only checks into one tool round when supported;
- establish relevance first, then expand only for decision-changing evidence.

Every reviewer receives the byte-identical packet and must return:

```text
Standards:
Spec:
Temporal correctness:
Verification performed:
UNVERIFIED:
```

Each finding includes its location, evidence, impact, and severity. Explicitly
say when an axis has no findings, is unavailable, or does not apply.

## 3. Launch blind external reviews

Use `kimi-k3:cloud` and `glm-5.3-flash:cloud` unless the user names different
models. Resolve and read the sibling `ollama-subagents` Skill. Give each model
a separate fresh run directory containing the same `brief.md`, then start both
runners before reading either result.

If fewer than two model runs complete successfully, disclose that cross-model
review was not achieved. Do not relabel a parent-model review as the missing
external model and do not silently substitute another provider.

## 4. Verify and consolidate

After all runs stop, anonymize the proposals as A/B before comparing them.
Normalize findings by affected behavior and location, then:

1. verify every decision-changing claim against the fixed diff, surrounding
   call path, repository evidence, and the smallest relevant check;
2. reject unsupported, out-of-scope, deterministic-tool, and duplicate
   findings;
3. keep a minority finding when its evidence is stronger; never decide by
   model agreement, verbosity, or reputation;
4. report supported findings under the three `code-review` axes, ordered by
   severity, followed by verification and remaining uncertainty;
5. disclose model IDs, run failures, and whether two independent model reviews
   actually completed.

If no supported findings remain, say so and identify residual testing or
evidence gaps. Done when every axis is accounted for and every reported finding
has been independently verified.
