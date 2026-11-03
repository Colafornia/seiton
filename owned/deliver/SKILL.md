---
name: deliver
description: >
  Orchestrate end-to-end delivery of a non-trivial production change as a thin
  router over specialized skills. Use when explicitly invoked, or when the user
  asks to take an issue through planning, implementation, review, verification,
  and closeout. Do not use for explanations, diagnosis-only work, docs-only
  edits, or trivial mechanical changes.
---

# Deliver

You are a **thin router**, not a super-skill. Own phase transitions and
completion conditions only. Each specialized skill is the single source of
truth for its own procedure; do not restate or override it.

- Decide which phase you are in.
- Call the matching skill when its entry condition is met.
- Do not advance until that skill's completion condition is met.
- You own the gating, not the technique inside any phase.

## State machine

```
intake → investigate → decide → plan → implement → review → adjudicate → verify → close
```

Skip a phase when its entry condition is not satisfied. Never force a task
through the full machine for "completeness".

## Routing map

```
deliver
  ├─ Explicit request to write/revise/review a goal? → goal-writer (contract only)
  ├─ Material unresolved choice?        → shape
  ├─ Material solution uncertainty?     → compare-solutions
  ├─ Runtime flow or ownership unclear? → how
  ├─ Bug?                               → debug  → tdd
  ├─ Feature / behavior change?         → plan checkpoint → tdd
  ├─ Behavior-preserving refactor?      → tdd (green net, then REFACTOR while green)
  ├─ Implementation ready for review?   → pr-review
  ├─ Review findings already exist?     → review-feedback
  ├─ Producing a performance claim?     → benchmark-checklist
  ├─ No reusable real-app verification? → create-verification-skill
  └─ Delivery done?                     → wrap-up
```

`review-feedback` adjudicates feedback that already exists; it never launches a
review.

## 1. Intake

Understand the requested outcome in the user's words and record it. State which
phases this task will and will not visit.
For a long-running task, keep one observable acceptance decision across slices
and sessions. If the user explicitly asks to write, revise, or review a goal,
use `goal-writer` to produce that contract; otherwise record acceptance here
without invoking it. A supplied or written contract is the completion gate,
not a plan, an activated goal, or permission for additional actions. Do not
substitute the next milestone for the full outcome.
If the user separately asks to start a tracked goal, hand the contract to the
available goal mechanism under its own authorization and status rules.
Done when the outcome and acceptance are stated and the likely phase set is named.

## 2. Investigate

Inspect the repository and available evidence before asking the user. Note what
is known, assumed, and genuinely unknown.
Use `how` when understanding subsystem behavior, runtime flow, or ownership
requires a code walkthrough; skip it when the relevant path is already clear.
Done when the evidence base is sufficient to classify the work, or an honest
blocker is recorded.

## 3. Decide

Classify the work as: bug fix; feature or behavior change; behavior-preserving
refactor; or mechanical / documentation change. Record observable completion
criteria and explicit exclusions.

If unresolved user-owned decisions would materially change scope,
compatibility, reversibility, or outcome, use `shape` and do not proceed until
its shared-plan postcondition is met. Skip when remaining choices are factual,
reversible, or local.

If multiple credible technical approaches materially differ in architecture,
compatibility, data, security, or rework risk, use `compare-solutions` before
Plan. Skip it when repository precedent or a small reversible choice already
determines the path.

## 4. Plan

For non-trivial work record: current evidence; desired behavior; invariants and
natural owners; compatibility constraints; vertical implementation slices;
verification per slice; exclusions.

Require confirmation only when the plan contains a material user-owned
decision or expands authorized scope. This is the `plan checkpoint`.
Done when the plan is recorded and, where required, confirmed.

## 5. Implement

- Bug → `debug`; once the cause is supported, `tdd` for the regression and
  minimal fix.
- Feature or behavior change → `tdd`, one vertical slice at a time.
- Refactor → `tdd` to establish or verify a green safety net; the REFACTOR step
  lives in `tdd`'s RED/GREEN/REFACTOR cycle.
- Mechanical or docs-only work → edit directly and run proportional checks.

Before leaving Implement, inspect the production and test diff:

- Keep production code readable, idiomatic, and consistent with nearby code:
  clear names, straightforward control flow, and no unnecessary duplication or
  abstraction.
- Require every test case to protect a distinct behavior or risk. Together the
  cases must cover the acceptance criteria and relevant boundaries or failures;
  remove duplicate cases and assertions.

Do not advance while the relevant skill's completion condition is unmet.

## 6. Review

Prepare a reviewer packet containing only: goal and acceptance criteria;
relevant diff; verification already run; known exclusions.

Use `pr-review` with the reviewer packet and an exact base/head or fixed patch
snapshot, including local changes when no PR exists. State unavailable PR
metadata as gaps. `pr-review` owns review technique, evidence, severity, and
reporting. Use `cross-model-code-review` when explicitly requested or when a
high-risk change warrants independent reviewers; it uses the same contract.
Done when the review accounts for problem evidence, solution correctness, and
the smallest complete solution, with supported findings or none, evidence gaps,
and a next step. Refresh a snapshot before acting if the reviewed state may
have changed.

## 7. Adjudicate

When review feedback exists, use `review-feedback`. Do not treat findings as
patch instructions; implement only verified and accepted actions. Re-review only
when changes materially alter the reviewed behavior or the prior round found a
systemic issue.
Done when every finding is accepted, rejected with reason, or deferred with an
owner.

## 8. Verify

Run the strongest verification proportional to the requested outcome — the
level that would actually catch a regression of this change, not a formality.

Use an existing project verification skill or harness first. When repeated
real-app verification is needed and the project has no reusable entry point,
use `create-verification-skill`, then run the generated project skill. Follow
the repository's skill-location rules and the current runtime's mapping.
Use `benchmark-checklist` before reporting or acting on a measured performance
claim. On macOS, use platform equivalents such as `sysctl -n hw.ncpu` for
`nproc`; keep the measurement requirements intact.

Ablate: for each abstraction or design element the change introduced, check
whether the outcome still holds with it removed. If it does, the element is
unnecessary — route back to Implement to delete it. Keep only what the
outcome demonstrably needs.
Done when that verification passes and every remaining abstraction earns its
place, or a failure is routed back to Implement.

## 9. Close

Use `wrap-up`. Done means the observable outcome is verified, every review
finding is accounted for, and no unexplained session-owned residue remains.

## Per-task paths

- **Bug:** `debug` → `tdd` → `pr-review` → `review-feedback` → `wrap-up`.
- **Feature:** `shape` (major choices only) → plan checkpoint → `tdd` (slices) →
  `pr-review` → `review-feedback` → `wrap-up`. Insert
  `compare-solutions` before the checkpoint only for material technical
  uncertainty.
- **Refactor:** confirm behavior invariance and public boundary → `tdd` (green
  net, then REFACTOR while green) → `pr-review` (architecture/compat) →
  `review-feedback` → `wrap-up`.
- **Mechanical:** direct edit → targeted verification. Do not invoke the full
  chain.

## Persisting plan across sessions

Within one session, use built-in plan state. Across sessions, persist a minimal
carrier — a GitHub issue/claim comment, PR body, an implementation note in the
repo, or the reviewer packet. Store:

```
Goal:
Decisions:
Invariants:
Current phase:
Completed verification:
Open findings:
Next slice:
Remaining acceptance gaps:
Exclusions:
```

For long-running work, preserve the goal's full acceptance condition in `Goal`
and update the next slice and remaining gaps alongside the evidence. On
resumption, check the carrier against the current repository state
before continuing. A completed slice or written goal is not completion; close
only when the full acceptance condition is verified. When blocked, continue
independent in-scope work and report the remaining blocker honestly.

Do not store full dialogue or model reasoning. A new reviewer should receive
goals and evidence, not the implementer's defense or reasoning anchors.

## Scope

`architect`, `blast-radius`, and `correct` are available on demand. Use
`architect` when the user chooses sketch-led design and implementation; it
continues into implementation by default, so request its checkpoint for a
design-only task. Keep `compare-solutions` for read-only approach selection
and avoid running both for the same decision. Use `blast-radius` for material
downstream compatibility risk, and `correct` for demonstrated repeated error
classes within the authorized scope.

When reading a linked pstack skill, resolve its source directory before
following sibling references. Supporting skills remain in the central catalog
even when they are absent from the active selection. Reading a platform or
subagent reference in `poteto-mode` does not select its overall workflow.

Do not turn agent or model diversity into routine ceremony. Use it for material
pre-implementation solution exploration or the independent review conditions
above, and never create parallel implementation branches by default.
