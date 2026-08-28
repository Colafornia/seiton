#!/usr/bin/env bash
set -euo pipefail

if [[ $# -ne 3 ]]; then
  echo "usage: run.sh MODEL PROJECT_DIR RUN_DIR" >&2
  exit 2
fi

MODEL="$1"
PROJECT="$2"
RUN="$3"
BRIEF="$RUN/brief.md"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
DEADLINE_SECONDS="${OLLAMA_SUBAGENT_TIMEOUT_SECONDS:-600}"
CODEX_ARGS=(exec --profile ollama-launch -m "$MODEL" --json)

if [[ -n "${OLLAMA_SUBAGENT_REASONING_EFFORT:-}" ]]; then
  case "$OLLAMA_SUBAGENT_REASONING_EFFORT" in
    none|minimal|low|medium|high|max|xhigh|ultra) ;;
    *)
      echo "invalid reasoning effort: $OLLAMA_SUBAGENT_REASONING_EFFORT" >&2
      exit 2
      ;;
  esac
  CODEX_ARGS+=(-c "model_reasoning_effort=\"$OLLAMA_SUBAGENT_REASONING_EFFORT\"")
fi

CODEX_ARGS+=(--sandbox read-only --ephemeral --skip-git-repo-check
  -C "$PROJECT" -o "$RUN/last.md" -)

[[ -d "$PROJECT" ]] || { echo "project directory not found: $PROJECT" >&2; exit 2; }
[[ -d "$RUN" ]] || { echo "run directory not found: $RUN" >&2; exit 2; }
[[ -s "$BRIEF" ]] || { echo "brief missing or empty: $BRIEF" >&2; exit 2; }

for ARTIFACT in model.txt events.jsonl last.md stderr.log; do
  [[ ! -e "$RUN/$ARTIFACT" ]] || {
    echo "run directory is not fresh: $RUN/$ARTIFACT already exists" >&2
    exit 2
  }
done

printf '%s\n' "$MODEL" > "$RUN/model.txt"

set +e
python3 "$SCRIPT_DIR/run-with-deadline.py" "$DEADLINE_SECONDS" \
  codex "${CODEX_ARGS[@]}" \
  < "$BRIEF" > "$RUN/events.jsonl" 2> "$RUN/stderr.log"
STATUS=$?
set -e

[[ $STATUS -eq 0 ]] || exit "$STATUS"
[[ -s "$RUN/last.md" ]] || {
  echo "agent completed without a final response" >> "$RUN/stderr.log"
  exit 1
}
