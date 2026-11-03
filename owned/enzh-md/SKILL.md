---
name: enzh-md
description: >
  Format Markdown content bilingually in English and Chinese using
  collapsible details/summary blocks, with English expanded by default and
  Chinese collapsed. Use when the user asks for dual-language, bilingual, or
  中英对照 Markdown output. Do not use for single-language documents.
---

# Bilingual Markdown

Wrap the document body in two collapsible blocks: English first and expanded,
Chinese second and collapsed.

## Template

```markdown
<details open>
<summary>English</summary>

<English content — ordinary Markdown: headings, lists, tables, code blocks>

</details>

<details>
<summary>中文</summary>

<对应的中文内容，结构保持一致>

</details>
```

## Rules

- Use `<details open>` for English and plain `<details>` for Chinese so the
  English version renders expanded and the Chinese version collapsed.
- Keep a blank line after `<summary>` and before `</details>`; without them
  many renderers treat the inner Markdown as raw HTML instead of rendering it.
- Keep the two versions structurally identical: same sections, same order.
  Translate prose; keep code, commands, paths, and identifiers verbatim in
  both blocks.
- Never hard-wrap the prose. The content is natural language, not a log:
  keep each paragraph or list item on a single line and let the viewer wrap
  it. Do not apply an 80-column line limit.
- For a short document wrap the whole body in one pair of blocks; for a long
  document repeat the pair per top-level section instead of nesting blocks.
- When the source exists in only one language, translate it faithfully to
  produce the other block; do not emit two blocks in the same language.
