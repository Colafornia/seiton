---
name: takeaway
description: >
  Capture concise, reusable knowledge and lessons from a completed session or
  task, optionally extend a topic after asking the learner, and save the
  result as linked Obsidian notes. Use after a meaningful task produces a
  mechanism, decision, pattern, or mistake worth remembering. Do not use for
  verbatim transcripts, generic progress summaries, or ordinary task status.
---

# Takeaway

Produce only durable learning that a future session can use without rereading
the original conversation. First classify the item: its type determines what
counts as evidence, what must be recorded, and how it should be recalled.
Never force a concept into an incident template or an incident into a generic
definition.

## Use cases

Invoke this Skill at the end of one of these sessions:

1. **Assisted learning** — consolidate what was learned, expose the smallest
   remaining gap, and optionally hand the notes to `learn-anything` for
   retrieval and teach-back.
2. **Explaining an article, PR, or Issue** — separate the underlying knowledge
   from the proposed solution, engineering pattern, and tradeoffs. Capture the
   source and link back to it.
3. **Completing a development task** — make the engineer account for the
   problem solved, chosen approach, important constraints, verification, and
   remaining risk. This is a technical record, not a status update.

## Classify the learning

Use the smallest sufficient type. A session may produce more than one type;
keep them as separate notes or explicitly link them. Keep only these three
types:

| Type | Answers | Required shape |
| --- | --- | --- |
| **Knowledge** | What is it? Why does it work? | Minimal concept, mechanism or invariant, first-principles explanation, source, and boundary |
| **Experience** | What happened in a real situation, and what should I do next time? | STAR: Situation, Task, Action, Result, followed by a transferable lesson and trigger |
| **Decision / solution** | What problem did we solve, why this approach, and with what tradeoffs? | Problem, constraints, options, chosen approach, rejected alternative, result, and residual risk |

Use **Knowledge** for durable models such as “`apply_patch` matches surrounding
context to describe a file change”. Use **Experience** for lessons such as
“when a patch fails after the file changed, reread the current context and
rebuild the patch”. Use **Decision / solution** when the important thing is
the problem, the selected approach, and why it was preferable. A recurring
pattern belongs in Experience; a sequence belongs in a Decision / solution
note only when it explains how that solution works. Do not create additional
types for patterns or procedures.

## Quality contract

Write a note only when each retained item passes all of these tests:

1. **Correctly typed** — the note uses the template and evidence appropriate to
   its learning type.
2. **Reusable** — it applies beyond this exact task or names a boundary that
   prevents a repeat failure.
3. **Specific** — it names the actual tool, concept, decision, or constraint;
   remove generic advice such as “read the docs carefully”.
4. **Causal** — it explains why the behavior occurs, using mechanism →
   consequence → condition or boundary.
5. **Evidence-backed** — the conversation, inspected code, command output, or
   cited source supports the claim. Mark an inference or unresolved claim
   instead of presenting it as fact.
6. **Compact** — it can be recalled from a few short bullets; remove setup,
   chronology, and repeated context.
7. **Distinct** — it adds information to the existing Obsidian graph rather
   than restating an existing note.

Reject an item that fails any test. If all items fail, report “没有可沉淀的
可复用知识” and do not create a note. Prefer one strong item to several
plausible but weak observations.

## Writing contract

Write concise, professional Chinese technical prose:

- State the mechanism, consequence, and boundary directly.
- Separate fact, inference, and open question; do not overstate evidence.
- Define unfamiliar terms once and preserve identifiers, commands, paths, and
  API names exactly.
- Remove chronology, repetition, generic advice, and empty headings.

Read configuration from the repository where the current task is being
performed, not from the directory that contains this Skill. Resolve the active
repository before reading it: if the working directory is inside a Git
repository, use `git -C "$PWD" rev-parse --show-toplevel`; otherwise use the
working directory itself. If the task explicitly names a different repository,
resolve that repository instead. Use this lookup order:

1. `<resolved-repository>/.agent/takeaway.toml` (project override)
2. `~/.agent/takeaway.toml` (user-wide default for all repositories)

The first existing, valid file wins. Do not use the catalog repository, the
Skill installation directory, or the process launch directory unless it is also
the active repository. A shared Obsidian vault normally needs only the
user-wide file; create a project file only when that repository needs different
settings.

Use the configured limits when present. Unless the vault convention requires
otherwise, keep a note under 1,600 characters, use no more than three bullets
per section, and no more than three sentences per paragraph. Treat these as
compression limits, not targets: omit low-value material first.

## Knowledge notes

Read the relevant conversation, files, commands, and verification results. Do
not infer a lesson from the final answer alone when the reasoning or evidence
is available. A Knowledge note must contain:

- the shortest accurate concept statement;
- the smallest mechanism, invariant, or causal model that explains it;
- a source document, inspected code path, or explicit “source not verified”;
- one boundary, misconception, or counterexample when it changes application.

Express the core as:

```text
<keyword>: <what it is or does>; <how it works>; <when it matters or fails>
```

For example:

```text
apply_patch: describes how the model should change a file; it locates the
target from surrounding context rather than relying only on line numbers, so
small edits between reading and writing may still apply; it can fail when the
context is ambiguous or has drifted too far.
```

Keep implementation details only when they explain a future choice. Include a
minimal example, command, or link when it materially improves recall. Record
the source path or URL for claims that depend on external documentation. Do not
upgrade a plausible explanation into a fact merely because it sounds useful.

Do not use STAR for a pure Knowledge note. A concept is not made more reliable
by adding the chronology of the session that introduced it.

## Experience notes

For Experience, write STAR and then generalize it:

```markdown
## 背景
- <system state, context, trigger, and relevant constraints>
## 行动
- <what was tried, including the key reasoning or intervention>
## 结果
- <observable outcome, verification, and remaining uncertainty>
## 经验
- <if X happens, try Y because Z; boundary: ...>
```

`背景`, `行动`, and `结果` are optional when the session does not establish
them; `经验` is required. The experience must be narrower than a slogan and broader than a diary entry. Keep
the failed approach when it explains the decision boundary. A recurring
pattern can be expressed in the 经验 section as “when the signal appears, try this
because ...; counterexample: ...”.

## Decision / solution notes

Use this type for article, PR, Issue, and development-task summaries when the
valuable learning is a solution or engineering choice:

```markdown
## 问题
- <observable problem and intended outcome>
## 方案
- <selected approach and why it was adequate>
## 结果
- <verification and user-visible or operational consequence>
## 风险
- <remaining uncertainty, follow-up, or boundary>
```

`问题` and `方案` are required. Add `结果` and `风险` only when supported;
put constraints or rejected alternatives in `方案` when they explain the
choice instead of creating extra sections.

For an article, PR, or Issue, preserve the original source link and distinguish
what the source states from what was inferred during explanation. For a
completed development task, use the actual diff, tests, commands, and observed
behavior as evidence. Do not reduce the note to “implemented X”; record which
problem it solved and why the chosen change was adequate.

When an Experience or Decision / solution note involves branching behavior or
multiple actors, add a small Mermaid or ASCII flow diagram. Use the diagram to
expose decisions and state transitions; keep explanatory prose outside it. Do
not add a diagram to a simple concept merely for decoration.

## Optional extension

Extension is a separate deliverable from the core takeaway. After the core
items pass the quality contract, identify at most two adjacent topics and ask
whether to pursue one. Offer clear choices such as:

- save the core takeaway only;
- extend one named topic with a concise explanation and sources;
- turn the takeaway into a review question.

Do not research stable basics by default. Research current, unfamiliar,
uncertain, or decision-critical claims only when the learner chooses
extension. Label every extended claim as verified, inferred, or still open,
and keep it tied to the original concept.

## Note contract

Before writing, read the first valid file from the lookup order above. It is the
source of truth for the Obsidian directory, filename template, date format,
topic naming rule, and section format. Treat both paths as machine-specific
configuration; never copy either into a committed Skill or replace them with a
guessed default. If neither config exists, either config is invalid, or the
directory is unavailable, produce a ready-to-paste note and state that it was
not saved. Do not write to an arbitrary fallback path.

With the configured `date_format = "%m%d"` and
`filename_template = "{date} {topic}.md"`, a topic named `Apply_Patch 是什么`
on September 24 becomes `0924 Apply_Patch 是什么.md`. Use the exact configured
template; do not add session IDs or automatic slugs.

Search for an existing canonical note before creating one. Update that note
when the new insight belongs to the same concept; create a new note only when
it has a distinct concept or durable boundary. Link related concepts with
`[[wikilinks]]` and prefer existing note names. Avoid duplicate aliases and
session-specific titles. Preserve existing correct content and add only the
new evidence or boundary.

The saved note must make the appropriate facts visible without the original
session. Sections are optional: create only sections supported by useful
evidence, never empty headings. The configured required sections are the
minimum shape, not a demand to fill every possible field:

- Knowledge: `核心` and `原理`; add `来源`, `边界`, or `例子` only when useful.
- Experience: `经验`; add `背景`, `行动`, and `结果` when they explain it.
- Decision / solution: `问题` and `方案`; add `结果` or `风险` when supported.

Use the matching compact shape and the configured section names, adapting only
when the vault already has an established convention. Omit unsupported
optional sections.
For Knowledge:

```markdown
# <Concept>

核心：<可复述的核心认识>

## 原理
- <最小机制或第一性解释>

## 来源
- <仅在有可靠来源时保留>

## 边界
- <仅在边界会改变应用时保留>

## 例子
- <仅在例子能帮助理解时保留>
```

For Experience, use the STAR shape above. For Decision / solution, use its
problem-to-risk shape. Do not put a Knowledge definition and an Experience or
Decision narrative in the same note unless one directly explains the other;
link them with `[[wikilinks]]` instead.

Use keywords and short sentences. Remove repeated context, greetings,
process narration, and claims that do not change future understanding. Add a
date or session source only when the vault convention requires it.

Before saving, perform a final audit: can a future reader explain the claim,
predict when it applies, and distinguish evidence from inference in under a
minute? If not, revise or omit it. Saving is the last step, not proof of
quality.

## Connect with learning

When the user wants to review, hand the note or its core concepts to
`learn-anything` when that Skill is available. Start with one free-text
retrieval question, then use teach-back, a targeted repair question, and a
small application or counterexample. Do not put the answer in the question's
choices. If the user asks for a direct recap or wants to skip questions, give
the recap immediately.

The takeaway note is the durable reference; the review dialogue is temporary.
Keep unresolved gaps in the note only when they are actionable, and suggest a
later self-test rather than pretending one session provides spaced repetition.
