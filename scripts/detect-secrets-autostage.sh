#!/bin/bash
# Wrapper for detect-secrets-hook that keeps the committed baseline stable without
# ever masking a failure.
#
# The scanner rewrites per-finding line_number values and the top-level generated_at
# stamp whenever it writes the baseline, so unrelated line shifts used to dirty the
# file and stall commits. The wrapper snapshots the baseline before the scan and
# classifies any modification the scanner makes:
#   volatile-only (line_number/generated_at)  -> restore the snapshot byte-exact, exit 0
#   substantive                               -> stage the update and retry, bounded
#   hook failed, baseline untouched           -> real findings: exit 1
# Exit-code contract per pinned bc-detect-secrets 1.5.45: 1 = secrets found or
# unstaged baseline (emitted before any baseline write), 3 = baseline updated.

set -uo pipefail

BASELINE=".secrets.baseline"
MAX_RETRIES=3

fail() {
    echo "detect-secrets wrapper: ERROR: $*" >&2
    exit 1
}

command -v python3 >/dev/null 2>&1 || fail "python3 not found; it performs the volatile-vs-substantive baseline comparison"
command -v detect-secrets-hook >/dev/null 2>&1 || fail "detect-secrets-hook not found on PATH; install the pinned bc-detect-secrets before committing"
[ -f "$BASELINE" ] || fail "$BASELINE not found; the hook needs the committed baseline"
python3 -c 'import json,sys; json.load(open(sys.argv[1]))' "$BASELINE" 2>/dev/null \
    || fail "$BASELINE is not valid JSON; repair or regenerate it before committing"

SNAPSHOT=$(mktemp) || fail "mktemp failed"
trap 'rm -f "$SNAPSHOT"' EXIT

run_hook() {
    detect-secrets-hook --baseline "$BASELINE" "$@"
}

# Exit 0 when the two baselines differ only in per-finding line_number values and the
# top-level generated_at stamp; exit 1 when the difference is substantive; exit 2 on a
# comparison crash, so a broken comparison can never masquerade as a verdict.
volatile_only() {
    python3 - "$1" "$2" <<'PY'
import json, sys

def stripped(path):
    with open(path) as f:
        doc = json.load(f)
    doc.pop("generated_at", None)
    for findings in doc.get("results", {}).values():
        for finding in findings:
            finding.pop("line_number", None)
    return doc

try:
    sys.exit(0 if stripped(sys.argv[1]) == stripped(sys.argv[2]) else 1)
except SystemExit:
    raise
except Exception as exc:
    print(f"baseline comparison error: {exc}", file=sys.stderr)
    sys.exit(2)
PY
}

for attempt in $(seq 1 "$MAX_RETRIES"); do
    cp "$BASELINE" "$SNAPSHOT" || fail "could not snapshot $BASELINE"

    HOOK_EXIT=0
    run_hook "$@" || HOOK_EXIT=$?

    if [ "$HOOK_EXIT" -eq 0 ]; then
        exit 0
    fi
    if [ "$HOOK_EXIT" -eq 127 ]; then
        fail "detect-secrets-hook vanished mid-run (exit 127)"
    fi
    if [ "$HOOK_EXIT" -ne 1 ] && [ "$HOOK_EXIT" -ne 3 ]; then
        echo "detect-secrets wrapper: hook failed with unexpected exit $HOOK_EXIT; passing it through" >&2
        exit "$HOOK_EXIT"
    fi

    if cmp -s "$BASELINE" "$SNAPSHOT"; then
        # Hook output has already streamed above; classification comes after it.
        echo "detect-secrets wrapper: hook exit $HOOK_EXIT with no baseline modification: findings not in the baseline. Nothing was auto-staged; review the report above." >&2
        exit 1
    fi

    if ! python3 -c 'import json,sys; json.load(open(sys.argv[1]))' "$BASELINE" 2>/dev/null; then
        cp "$SNAPSHOT" "$BASELINE"
        fail "hook left $BASELINE malformed JSON; the pre-scan baseline was restored"
    fi

    VERDICT=0
    volatile_only "$SNAPSHOT" "$BASELINE" || VERDICT=$?

    if [ "$VERDICT" -ge 2 ]; then
        cp "$SNAPSHOT" "$BASELINE"
        fail "volatile-vs-substantive comparison crashed (exit $VERDICT); pre-scan baseline restored, nothing staged"
    fi

    if [ "$VERDICT" -eq 0 ]; then
        cp "$SNAPSHOT" "$BASELINE" || fail "could not restore $BASELINE from snapshot"
        # A volatile-only rewrite excuses exit 3 (baseline updated), never a real failure
        # code: exit 0 here on hook exit 1 would let findings through on any future tool
        # whose write ordering differs from the pinned 1.5.45.
        if [ "$HOOK_EXIT" -eq 3 ]; then
            echo "detect-secrets wrapper: baseline change was volatile-only (line_number/generated_at); restored byte-exact, nothing staged."
            exit 0
        fi
        echo "detect-secrets wrapper: hook exit $HOOK_EXIT with only a volatile baseline rewrite: treating as failure (see report above); baseline restored, nothing staged." >&2
        exit "$HOOK_EXIT"
    fi

    echo "detect-secrets wrapper: substantive baseline update; auto-staging (attempt $attempt/$MAX_RETRIES)..."
    git add "$BASELINE" || fail "git add $BASELINE failed"
done

fail "could not stabilize baseline after $MAX_RETRIES attempts"
