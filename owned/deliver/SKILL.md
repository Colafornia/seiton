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
  ├─ Material unresolved choice?        → shape
  ├─ Material solution uncertainty?     → compare-solutions
  ├─ Bug?                               → debug  → tdd
  ├─ Feature / behavior change?         → plan checkpoint → tdd
  ├─ Behavior-preserving refactor?      → tdd (green net, then REFACTOR while green)
  ├─ Implementation ready for review?   → code-review
  ├─ Review findings already exist?     → review-feedback
  └─ Delivery done?                     → wrap-up
```

`review-feedback` adjudicates feedback that already exists; it never launches a
review.

## 1. Intake

Understand the requested outcome in the user's words and record it. State which
phases this task will and will not visit.
Done when the outcome is stated and the likely phase set is named.

## 2. Investigate

Inspect the repository and available evidence before asking the user. Note what
is known, assumed, and genuinely unknown.
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

Use `code-review` with the reviewer packet and an explicit fixed point or change
scope. `code-review` owns review technique, repository comparison, test and
comment quality checks, and reviewer independence.
Done when `code-review` accounts for both Standards and Spec, or records an
honest blocker.

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
Done when that verification passes, or a failure is routed back to Implement.

## 9. Close

Use `wrap-up`. Done means the observable outcome is verified, every review
finding is accounted for, and no unexplained session-owned residue remains.

## Per-task paths

- **Bug:** `debug` → `tdd` → `code-review` → `review-feedback` → `wrap-up`.
- **Feature:** `shape` (major choices only) → plan checkpoint → `tdd` (slices) →
  `code-review` → `review-feedback` → `wrap-up`. Insert
  `compare-solutions` before the checkpoint only for material technical
  uncertainty.
- **Refactor:** confirm behavior invariance and public boundary → `tdd` (green
  net, then REFACTOR while green) → `code-review` (architecture/compat) →
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
Exclusions:
```

Do not store full dialogue or model reasoning. A new reviewer should receive
goals and evidence, not the implementer's defense or reasoning anchors.

## Scope

Do not turn agent or model diversity into routine ceremony. Use it only for
pre-implementation solution exploration where independent evidence can change
the decision, and never create parallel implementation branches by default.
