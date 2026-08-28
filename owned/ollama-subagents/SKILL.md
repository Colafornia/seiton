---
name: ollama-subagents
description: >
  Launch an external Ollama-backed model as an isolated, read-only Codex agent
  with a deadline and captured run artifacts. Use as the execution dependency
  for multi-model workflows or when explicitly asked to run an Ollama model.
  Do not use to choose models, author task briefs, or adjudicate results.
---

# Ollama Subagents

Run one model behind a small, deterministic interface. The calling workflow
owns the task semantics and result evaluation.

## Interface

Prepare a fresh, model-specific run directory containing a non-empty
`brief.md`, then resolve this Skill's real path and run:

```text
scripts/run.sh MODEL PROJECT_DIR RUN_DIR
```

The local Codex profile `ollama-launch` must route models through Ollama. The
runner enforces a read-only, ephemeral Codex session and creates:

```text
model.txt       requested model ID
events.jsonl    Codex event stream
last.md         final agent message
stderr.log      diagnostics
```

The default deadline is 600 seconds. Set `OLLAMA_SUBAGENT_TIMEOUT_SECONDS` to a
positive finite number to override it. Timeout exits with status 124. Any
other non-zero status, an empty `last.md`, or a pre-existing output artifact is
a failed run.

Do not set a reasoning effort unless the caller requests one. When requested,
set `OLLAMA_SUBAGENT_REASONING_EFFORT` to the named effort for that runner
invocation. The runner passes it to Codex as `model_reasoning_effort`; do not
pass Ollama's `--think` flag to `codex exec`.

For parallel work, give every model a separate fresh run directory and start
all runners before reading any result. Never replace a failed external model
with the parent model or another provider under the same label.
