---
name: structured-output
description: >
  Structure substantial technical explanations around conclusions, evidence,
  and causal or execution flow. Use for code explanations, analysis,
  diagnosis, design comparisons, reviews, and technical reports. Do not use
  for code-only responses, simple facts, casual or creative writing, or
  formats with no prose to organize.
---

# Structured Output

Shape the final answer as a continuous reader path. Investigation may be
iterative and divergent; reorganize the explanation around evidence,
causality, execution flow, or importance instead of replaying discovery order.
This skill governs presentation, not investigation, verification, or testing.

## Build the reader path

1. Use a flexible pyramid. Open with the smallest complete answer or
   best-supported current finding, including the main parts and relationships
   needed to understand it.
2. Build downward by grouping support in one governing order—causal,
   execution, chronological, or importance. Add detail only when it changes
   understanding or action.
3. Move from given information to new information. State the needed context
   immediately before the conclusion that depends on it.
4. Keep each paragraph to one main point and one abstraction level. Make
   transitions explicit when moving between system, component, and line-level
   behavior.
5. Place evidence beside the claim it supports. Separate observed facts and
   evidence from inferences, unverified hypotheses, uncertainty, and
   recommendations. Call an unverified root cause a hypothesis or current
   finding.
6. Explain complex mechanisms as input → transformation → state change →
   output when that path fits the system.
7. Use one minimal worked example when an abstraction remains hard to follow;
   carry one concrete case through the complete mechanism.
8. Use headings to name logical roles, bullets for genuinely parallel items,
   and numbers for ordered steps.
9. Keep terminology stable. Define an unfamiliar term at first use, then use
   the same name throughout.
10. Prefer concrete actors, actions, examples, and consequences. Remove
    tangents, filler, unsupported certainty, and conclusions already stated.
11. Provide concise, verifiable rationale and evidence rather than private
    chain-of-thought. Follow any explicit output format from the user instead.

## Write naturally

Write for a technically capable reader who may be unfamiliar with the local
codebase. Prefer clarity over brevity when shortening would make a claim
ambiguous.

- In Chinese, follow natural causal or temporal order; introduce the main
  actor and action early, split stacked modifiers, and replace ambiguous
  pronouns with their referents.
- In English, prefer plain words and active voice when the actor matters. Keep
  parallel items grammatically parallel; avoid nominalizations and deeply
  nested sentences.

Before sending, confirm that a reader can identify the conclusion, its support,
the connecting path, and the status of every material uncertainty without
reconstructing the investigation history.
