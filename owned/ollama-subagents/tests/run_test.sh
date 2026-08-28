#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
TMP="$(mktemp -d "${TMPDIR:-/tmp}/ollama-subagents-test.XXXXXX")"
trap 'rm -rf "$TMP"' EXIT
mkdir -p "$TMP/bin" "$TMP/project" "$TMP/run"
printf '%s\n' 'neutral packet' > "$TMP/run/brief.md"

cat > "$TMP/bin/codex" <<'EOF'
#!/usr/bin/env bash
set -euo pipefail
printf '%s\n' "$@" > "$TEST_TMP/args"
cat > "$TEST_TMP/stdin"
if [[ "${TEST_HANG:-0}" == 1 ]]; then
  sleep 30 &
  printf '%s\n' "$!" > "$TEST_TMP/child-pid"
  wait "$!"
fi
printf '%s\n' '{"type":"turn.completed"}'
[[ "${TEST_EMPTY:-0}" == 0 ]] || exit 0
while [[ $# -gt 0 ]]; do
  if [[ "$1" == "-o" ]]; then
    printf '%s\n' 'review' > "$2"
    exit 0
  fi
  shift
done
exit 2
EOF
chmod +x "$TMP/bin/codex"

TEST_TMP="$TMP" PATH="$TMP/bin:$PATH" \
  "$ROOT/scripts/run.sh" "glm-5.3-flash:cloud" "$TMP/project" "$TMP/run"

cmp -s "$TMP/run/brief.md" "$TMP/stdin"
grep -qx -- '--profile' "$TMP/args"
grep -qx -- 'ollama-launch' "$TMP/args"
grep -qx -- '--json' "$TMP/args"
grep -qx -- '--sandbox' "$TMP/args"
grep -qx -- 'read-only' "$TMP/args"
grep -qx -- 'glm-5.3-flash:cloud' "$TMP/args"
! grep -q -- 'model_reasoning_effort' "$TMP/args"
grep -qx -- 'glm-5.3-flash:cloud' "$TMP/run/model.txt"
grep -qx -- 'review' "$TMP/run/last.md"
grep -qx -- '{"type":"turn.completed"}' "$TMP/run/events.jsonl"

mkdir -p "$TMP/effort-run"
printf '%s\n' 'neutral packet' > "$TMP/effort-run/brief.md"
TEST_TMP="$TMP" PATH="$TMP/bin:$PATH" \
  OLLAMA_SUBAGENT_REASONING_EFFORT=high \
  "$ROOT/scripts/run.sh" "glm-5.3-flash:cloud" "$TMP/project" "$TMP/effort-run"
grep -qx -- 'model_reasoning_effort="high"' "$TMP/args"

mkdir -p "$TMP/invalid-effort-run"
printf '%s\n' 'neutral packet' > "$TMP/invalid-effort-run/brief.md"
set +e
TEST_TMP="$TMP" PATH="$TMP/bin:$PATH" \
  OLLAMA_SUBAGENT_REASONING_EFFORT=fast \
  "$ROOT/scripts/run.sh" "glm-5.3-flash:cloud" "$TMP/project" "$TMP/invalid-effort-run" \
  2> "$TMP/invalid-effort.log"
STATUS=$?
set -e
[[ $STATUS -eq 2 ]]
grep -qx -- 'invalid reasoning effort: fast' "$TMP/invalid-effort.log"

set +e
TEST_TMP="$TMP" PATH="$TMP/bin:$PATH" \
  "$ROOT/scripts/run.sh" "glm-5.3-flash:cloud" "$TMP/project" "$TMP/run" \
  2> "$TMP/not-fresh.log"
STATUS=$?
set -e
[[ $STATUS -eq 2 ]]
grep -q -- 'run directory is not fresh' "$TMP/not-fresh.log"

mkdir -p "$TMP/empty-run"
printf '%s\n' 'neutral packet' > "$TMP/empty-run/brief.md"
set +e
TEST_EMPTY=1 TEST_TMP="$TMP" PATH="$TMP/bin:$PATH" \
  "$ROOT/scripts/run.sh" "glm-5.3-flash:cloud" "$TMP/project" "$TMP/empty-run"
STATUS=$?
set -e
[[ $STATUS -eq 1 ]]
grep -qx -- 'agent completed without a final response' "$TMP/empty-run/stderr.log"

mkdir -p "$TMP/hanging-run"
printf '%s\n' 'neutral packet' > "$TMP/hanging-run/brief.md"
set +e
TEST_HANG=1 TEST_TMP="$TMP" PATH="$TMP/bin:$PATH" \
  OLLAMA_SUBAGENT_TIMEOUT_SECONDS=1 \
  "$ROOT/scripts/run.sh" "glm-5.3-flash:cloud" "$TMP/project" "$TMP/hanging-run"
STATUS=$?
set -e

[[ $STATUS -eq 124 ]]
grep -qx -- 'timed out after 1 seconds' "$TMP/hanging-run/stderr.log"
! kill -0 "$(cat "$TMP/child-pid")" 2>/dev/null
