#!/usr/bin/env bash
# pip-audit gate (Feature 1400 — validator gating)
# ================================================
# Makes pip-audit BLOCKING (replaces the old advisory `|| true` + continue-on-error)
# while staying sustainable via a curated, auto-expiring ignore list.
#
# Behavior:
#   1. Parse .pip-audit-ignore. Each entry: VULN_ID  EXPIRY(YYYY-MM-DD)  justification
#      - Fail if any entry is malformed, missing a justification, or PAST its expiry.
#        (An expired ignore = red CI on its own, so the list can never rot silently.)
#   2. Run pip-audit against the requirements files with the surviving ignores.
#      Exit nonzero if any NON-ignored vulnerability is found.
#
# --no-deps rationale: audits the exact pinned top-level packages we control (the
# direct dependency surface). It avoids resolving/downloading the 2GB torch layer
# and avoids resolution failures on layer-built pins. Transitive-dep drift is
# covered by Dependabot. This is a strict improvement over the prior blanket pass.
#
# Usage: scripts/pip-audit-gate.sh   (run from repo root)
set -euo pipefail

IGNORE_FILE=".pip-audit-ignore"
REQ_FILES=("requirements.txt" "requirements-dev.txt")
TODAY_EPOCH="$(date -u +%s)"
IGNORE_ARGS=()
FAIL=0

if [[ -f "$IGNORE_FILE" ]]; then
  while IFS= read -r line || [[ -n "$line" ]]; do
    # strip comments / blank lines
    line="${line%%#*}"
    [[ -z "${line// }" ]] && continue
    read -r vid expiry justification <<<"$line"
    if [[ -z "${vid:-}" || -z "${expiry:-}" || -z "${justification:-}" ]]; then
      echo "::error::Malformed .pip-audit-ignore entry (need: ID EXPIRY justification): $line"
      FAIL=1
      continue
    fi
    if ! exp_epoch="$(date -u -d "$expiry" +%s 2>/dev/null)"; then
      echo "::error::Bad expiry date '$expiry' for $vid (want YYYY-MM-DD)"
      FAIL=1
      continue
    fi
    if (( exp_epoch < TODAY_EPOCH )); then
      echo "::error::pip-audit ignore for $vid EXPIRED on $expiry — re-evaluate (upgrade or renew with justification)"
      FAIL=1
      continue
    fi
    IGNORE_ARGS+=(--ignore-vuln "$vid")
  done < "$IGNORE_FILE"
fi

if (( FAIL )); then
  echo "pip-audit gate: ignore-list validation FAILED (see errors above)."
  exit 1
fi

echo "pip-audit gate: ${#IGNORE_ARGS[@]} ignore flag(s) active (2 per entry)."

for req in "${REQ_FILES[@]}"; do
  echo "=== pip-audit -r $req ==="
  pip-audit -r "$req" --no-deps --progress-spinner off "${IGNORE_ARGS[@]}"
done

echo "pip-audit gate: PASS — no unignored vulnerabilities."
