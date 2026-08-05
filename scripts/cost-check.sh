#!/usr/bin/env bash
# Cost gate: infracost diff against the committed baseline, thresholds enforced by
# parsing the JSON output. The tool's exit code is never the breach signal: infracost
# exits 1 for its own errors too, so exit-code gating cannot tell "over budget" from
# "diff never ran". Every failure class here is fail-closed and names its remedy.

set -euo pipefail

TF_PATH="infrastructure/terraform"
BASELINE="$TF_PATH/infracost-baseline.json"
MONTHLY_LIMIT="${COST_MONTHLY_LIMIT:-50}"
DELTA_LIMIT="${COST_DELTA_LIMIT:-10}"

fail() {
    echo "cost-check: FAIL: $*" >&2
    exit 1
}

is_number() {
    [[ "$1" =~ ^-?[0-9]+(\.[0-9]+)?$ ]]
}

# Gate one `infracost diff --format json` document. Separated from the tool-dependent
# flow so the seeded fixture tests can drive it by sourcing this file.
gate_diff_json() {
    local json="$1" total delta
    is_number "$MONTHLY_LIMIT" || fail "COST_MONTHLY_LIMIT '$MONTHLY_LIMIT' is not a number"
    is_number "$DELTA_LIMIT" || fail "COST_DELTA_LIMIT '$DELTA_LIMIT' is not a number"
    jq -e . "$json" >/dev/null 2>&1 || fail "diff output $json is not valid JSON"
    total=$(jq -r '.totalMonthlyCost // empty' "$json")
    delta=$(jq -r '.diffTotalMonthlyCost // "0"' "$json")
    is_number "${total:-}" || fail "diff output has no numeric totalMonthlyCost (got '${total:-<absent>}'); regenerate the baseline with 'make cost-baseline' and rerun"
    is_number "$delta" || fail "diff output has a non-numeric diffTotalMonthlyCost ('$delta')"
    if jq -en --arg v "$total" --argjson lim "$MONTHLY_LIMIT" '($v|tonumber) > $lim' >/dev/null; then
        fail "projected monthly total \$${total} exceeds COST_MONTHLY_LIMIT \$${MONTHLY_LIMIT}"
    fi
    if jq -en --arg v "$delta" --argjson lim "$DELTA_LIMIT" '($v|tonumber) > $lim' >/dev/null; then
        fail "projected monthly delta \$${delta} exceeds COST_DELTA_LIMIT \$${DELTA_LIMIT}"
    fi
    echo "cost-check: OK: total \$${total}/month (limit \$${MONTHLY_LIMIT}), delta \$${delta}/month (limit \$${DELTA_LIMIT})"
}

# Tool and auth guards, shared by the gate and by `make cost` (which runs this with
# --preflight so a missing or unauthenticated tool fails loudly with one message set).
preflight() {
    command -v jq >/dev/null 2>&1 || fail "jq not found; the gate parses infracost JSON output and needs it"

    if ! command -v infracost >/dev/null 2>&1; then
        fail "infracost not found. Install the pinned v0.10.45: download infracost-linux-amd64.tar.gz from https://github.com/infracost/infracost/releases/tag/v0.10.45, verify its SHA256 against the checksums file published on that release, and place the binary on PATH (or use a package manager pinned to 0.10.45). Never install via a script piped from the network."
    fi

    if [[ -z "${INFRACOST_API_KEY:-}" ]]; then
        local key
        key=$(infracost configure get api_key 2>/dev/null || true)
        [[ -n "$key" ]] || fail "infracost is not authenticated: run 'infracost auth login' or export INFRACOST_API_KEY"
    fi
}

main() {
    preflight

    [[ -f "$BASELINE" ]] || fail "baseline $BASELINE not found; regenerate it with 'make cost-baseline'"
    jq -e . "$BASELINE" >/dev/null 2>&1 || fail "baseline $BASELINE is not valid JSON; regenerate it with 'make cost-baseline'"

    # Not local: the EXIT trap runs after main returns, where a local would already be
    # gone and set -u would turn the cleanup itself into a failure exit.
    TMP_OUT=$(mktemp)
    trap 'rm -f "${TMP_OUT:-}"' EXIT
    infracost diff --path "$TF_PATH" --compare-to "$BASELINE" --format json --out-file "$TMP_OUT" \
        || fail "infracost diff failed (exit $?); the gate cannot decide anything from a failed diff"

    gate_diff_json "$TMP_OUT"
}

# Sourcing loads gate_diff_json for fixture tests; only direct execution runs the flow.
if [[ "${BASH_SOURCE[0]}" == "$0" ]]; then
    if [[ "${1:-}" == "--preflight" ]]; then
        preflight
    else
        main "$@"
    fi
fi
