#!/bin/bash
# Terraform version guard: one pinned version, everywhere.
#
# Pass 1 checks the local binary against the pin. Pass 2 checks every other
# place the repo declares a terraform version, so a pin bump that misses a
# declaration fails here rather than drifting silently. No network, no writes.

set -u

PIN_FILE=".terraform-version"
DEPLOY_WF=".github/workflows/deploy.yml"
PR_WF=".github/workflows/pr-checks.yml"
ROOT_MODULES=("infrastructure/terraform/main.tf" "infrastructure/terraform/bootstrap/main.tf")
DEPLOY_EXPECTED_COUNT=3

fail() {
    echo "check-terraform-version: FAIL: $*" >&2
    exit 1
}

# --- Failure class: pin declaration absent/empty/malformed ---
[ -f "$PIN_FILE" ] || fail "pin file $PIN_FILE not found; it is the single authoritative terraform version declaration"
PIN=$(head -n1 "$PIN_FILE" | tr -d '[:space:]')
[ -n "$PIN" ] || fail "pin file $PIN_FILE is empty"
echo "$PIN" | grep -Eq '^[0-9]+\.[0-9]+\.[0-9]+$' || fail "pin file $PIN_FILE is malformed: '$PIN' is not a plain semver like 1.9.8"

# --- Failure class: comparison tooling absent ---
command -v jq >/dev/null 2>&1 || fail "jq not found; the guard derives the local version from 'terraform version -json' and needs jq"

# --- Failure class: binary absent ---
command -v terraform >/dev/null 2>&1 || fail "terraform not found on PATH (pin $PIN_FILE expects $PIN)"

# --- Failure class: binary mismatch ---
FOUND=$(terraform version -json 2>/dev/null | jq -r '.terraform_version // empty')
[ -n "$FOUND" ] || fail "could not derive local terraform version from 'terraform version -json'"
if [ "$FOUND" != "$PIN" ]; then
    fail "local terraform is $FOUND, pin is $PIN (declared in $PIN_FILE). Install $PIN ahead of the current binary."
fi

# --- Failure class: deploy workflow declaration drift ---
mapfile -t DEPLOY_PINS < <(grep -oE 'terraform_version: [0-9.]+' "$DEPLOY_WF" | awk '{print $2}')
if [ "${#DEPLOY_PINS[@]}" -ne "$DEPLOY_EXPECTED_COUNT" ]; then
    fail "$DEPLOY_WF declares ${#DEPLOY_PINS[@]} terraform_version pins, expected $DEPLOY_EXPECTED_COUNT"
fi
for v in "${DEPLOY_PINS[@]}"; do
    [ "$v" = "$PIN" ] || fail "$DEPLOY_WF pins terraform_version $v, pin is $PIN; drifted line(s): $(grep -n "terraform_version: $v" "$DEPLOY_WF" | tr '\n' ' ')"
done

# --- Failure class: PR workflow missing the pin-file read ---
# Anchored to a terraform_version key so a stray comment cannot satisfy it.
grep -Eq 'terraform_version:.*steps\.tfver\.outputs\.version' "$PR_WF" || fail "$PR_WF does not read the pin file (expected setup-terraform to consume steps.tfver.outputs.version)"

# --- Failure class: root module constraint drift ---
for mod in "${ROOT_MODULES[@]}"; do
    CONSTRAINT=$(grep -oE 'required_version = "[^"]+"' "$mod" | head -n1 | sed 's/.*"\(.*\)"/\1/')
    [ "$CONSTRAINT" = "$PIN" ] || fail "$mod has required_version \"$CONSTRAINT\", pin is $PIN"
done

echo "check-terraform-version: OK: terraform $PIN everywhere"
exit 0
