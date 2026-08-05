#!/usr/bin/env python3
"""Classify the difference between two detect-secrets baselines.

Exit 0 when the two differ only in per-finding line_number values and the
top-level generated_at stamp (or not at all); exit 1 when the difference is
substantive; exit 2 on a comparison crash, so a broken comparison can never
masquerade as a verdict.

Shared by scripts/detect-secrets-autostage.sh (local pre-commit) and the
"Detect secrets" step in .github/workflows/pr-checks.yml, so the two gates
cannot drift apart on what counts as volatile.

Usage: baseline-volatile-compare.py BEFORE AFTER
"""

import json
import sys


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
