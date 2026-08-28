---
name: compare-solutions
description: >
  Explore and compare independent implementation approaches before coding.
  Use when multiple credible solutions materially differ in architecture,
  compatibility, data, security, or rework risk. Do not use for routine local
  choices, implementation, or code review.
---

# Compare Solutions

Find the best supported approach before implementation. Produce a decision, not
code. Keep every participating agent read-only.

## 1. Confirm exploration is warranted

Use this skill only when another credible approach could materially change the
outcome or cost. Skip it when repository precedent or a small reversible choice
already determines the path.

## 2. Build a neutral packet

Gather:

- goal and acceptance criteria;
- repository evidence and similar implementations;
- invariants, compatibility constraints, and exclusions;
- relevant test seams and verification options;
- genuine unknowns.

For ASTRYX-based interface decisions, read
`references/astryx.md` and verify decision-changing details against upstream.

Do not include a preferred solution or the implementer's rationale.

## 3. Generate independent proposals

Resolve this Skill's real path and look for
`<catalog-root>/.agent/compare-solutions.md`. When it exists, read it to choose
the proposal agents. Otherwise use at least two available independent agents or
model contexts. Give every participant the same packet. They must not see each
other's work.

Let each participant explore independently, but keep tool output bounded:

- do not print entire large files, the full repository diff, or unbounded
  repository-wide search results;
- start with `rg`, `git diff --stat` or `--name-only`, and targeted `sed -n`
  ranges;
- batch independent read-only checks into one tool round when supported;
- establish relevance first, then expand the inspected range only when the
  evidence can affect the decision.

For an `Ollama model: <model>` entry, do not use a native custom-agent role.
Resolve and read the sibling `ollama-subagents` Skill, then use its runner with
a separate fresh run directory for each model. Start all participants before
reading any proposal. If a run fails, record the model as unavailable instead
of falling back to the parent's provider.

Require each proposal to contain:

```
Recommendation:
Repository evidence:
Assumptions:
Change surface:
Testing and verification:
Risks and failure modes:
Credible alternatives:
```

If a selected agent is unavailable, continue only when the remaining evidence
can still support a decision. Record missing independence or model diversity;
never imply that two generic responses used different models.

## 4. Evaluate with evidence

Compare the proposals on:

- correctness and acceptance-criteria coverage;
- consistency with repository patterns;
- readability and implementation simplicity;
- testability and regression detection;
- compatibility, reversibility, and operational risk;
- unsupported assumptions.

Verify decision-changing claims against the repository or an authoritative
source. Do not choose by vote, reputation, or superficial agreement. Do not
combine proposals unless the result remains internally coherent and simpler
than either alternative.

## 5. Hand off one decision

Report:

```
Decision:
Why:
Rejected alternatives:
Evidence checked:
Remaining uncertainty:
Implementation constraints:
```

If a material user-owned tradeoff remains, use `shape` rather than choosing for
the user. Otherwise hand the selected approach to Plan and then `tdd`.

Done when one evidence-backed approach is selected, or the unresolved decision
and its owner are explicit.
