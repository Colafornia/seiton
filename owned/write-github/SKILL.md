---
name: write-github
description: Write clear, evidence-based GitHub issue and pull request titles and bodies. Use when the user asks to draft, revise, or publish an issue or PR.
---

# Write GitHub

Write for the reader's decision. Explain the problem and outcome before implementation details.

## 1. Build the evidence

In a Git repository, inspect the evidence before writing:

- Read the repository's issue or PR template as the required contract.
- Read the linked issue, including its user problem and expected behavior.
- For a PR, inspect the diff, commit message, changed areas, and existing verification results.
- Search GitHub for three to five recent examples of the same item type and product area. Use them only for conventions that repeat.

Use `gh repo view`, `gh issue view`, `gh issue list`, `gh pr list`, or equivalent GitHub tools. If GitHub is unavailable, use the fallback structure and state that repository style was unavailable.

Use existing verification evidence. Run new checks only when the user requests verification or publishing requires it.

Done when every material claim maps to the user request, issue, diff, repository convention, or recorded check result.

## 2. Find the message

For a user-visible bug, use this causal order when each part helps review:

1. observable problem
2. expected product or platform behavior
3. root cause
4. correction
5. unchanged behavior and scope boundaries
6. verification

Start the summary with the user's action and the observable result. Introduce props, helpers, files, and internal mechanisms only when explaining the cause or change.

For internal or mechanical work, state the problem, outcome, material changes, and verification.

Concise means removing repetition. Keep the problem, cause, outcome, and boundaries that a reviewer needs.

Write one title in the repository's primary language and title format. Describe the observable correction with a concrete action verb and product term.

Prefer direct verbs such as `add`, `remove`, `enable`, `disable`, `prevent`, and `preserve`. Replace abstract verbs such as `align`, `converge`, `honor`, and `respect` when a direct action is available. Keep implementation categories such as “programmatic scrolling” in the body unless users know them as product terms.

Prefer:

```text
fix(desktop): disable scroll animation for reduced motion
```

over:

```text
fix(ui): honor scroll policy for programmatic navigation
```

Done when a reader can understand what changed and why without reconstructing the diff.

## 3. Write natural technical English

Apply ASD-STE100 principles without turning the text into a maintenance procedure:

- Use common, specific words and active voice.
- Give each term one meaning. Keep product and code names exact.
- Put one topic in each sentence and paragraph.
- Keep descriptive sentences at 25 words or fewer when clarity permits.
- Write reproduction and action steps as short imperative sentences.
- Put a necessary condition before its result or action.
- Define an unfamiliar technical term once, or replace it with user-facing language.

Use natural product language. Prefer an explicit actor, behavior, and consequence to abstract verbs or implementation shorthand.

Done when the wording is plain, precise, natural, and technically accurate.

## 4. Match format and language

Follow the repository template and recurring conventions. Otherwise use only the relevant fallback sections:

- Bug issue: `Summary`, `Steps to reproduce`, `Expected behavior`, `Actual behavior`
- Change issue: `Problem`, `Desired outcome`, `Acceptance criteria`
- PR: `Summary`, `Verification`

Add a bilingual body when the user asks or the repository consistently uses one. GitHub still has one title; add another title only when repository precedent requires it. Follow the observed body wrapper. Without one, use expanded English and collapsed Chinese `<details>` blocks.

Keep both languages equivalent: same sections, facts, commands, numbers, links, and checklist states. For Chinese, inspect existing UI copy, platform terminology, or documentation for established terms. Before returning, scan every Latin phrase in Chinese prose. Keep only commands, identifiers, and fixed product names; translate the rest.

Done when the structure matches the repository and each language communicates the same evidence naturally.

## 5. Audit verification

Map each changed area to its relevant check, result, and checklist claim.

- Report the scope that actually ran, not the scope implied by a command name.
- Treat type checking, behavior tests, and real-window verification as different evidence.
- Treat one package's result as evidence for that package only.
- Check a template item only when evidence supports every clause.
- Leave unsupported items unchecked and name relevant checks that were not run.
- Name the actual missing check. Keep drafting activity out of the verification text.

Done when every verification statement and checkbox is exactly supported by recorded output.

## 6. Return or publish

Return a complete draft with these copy-ready blocks:

````markdown
Title
```text
<single-line title>
```

Description
```markdown
<GitHub Markdown body>
```
````

When revising, return only the requested replacement and preserve accepted content. When publishing, use `--body-file`, verify the published item, and return its URL, title, and status.

Use actual line feeds and blank lines. Keep each paragraph on one source line. Preserve code with backticks or fenced blocks. Omit literal `\\n`, HTML line breaks, trailing spaces, and manual hard wrapping.

Done when the response matches the request and GitHub renders the Markdown as intended.
