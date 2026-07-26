# SC-001 + SC-006 evidence: refresh-classification drill PASS

**When**: 2026-07-26 ~06:45 UTC, after PR #966 (SuppressFilter boundary fix)
deployed via run 30190532233 (Deploy-to-Preprod success).
**How**: `AWS_REGION=us-east-1 .venv/bin/python scripts/verify-log-visibility.py`
against `preprod-sentiment-dashboard:live`.

Output (verbatim tail):

```
probe (c): anon mint -> replay cookie -> expect refresh.success
  -> 200 (must be 2xx for the branch to log success)
  FOUND: refresh.success
  FOUND: refresh.rejected
  FOUND: refresh.cookie_absent
  FOUND: logging configured: root INFO visibility active (feature 001)

PASS — all three refresh classifications + C-8 self-test visible (SC-006).
```

Discrimination context: the identical script FAILED against pre-deploy
preprod (all four lines MISSING, probes 401/401/200 — recorded in the
Phase 5 commit message) and FAILED between #965 and #966 (C-8 found, three
refresh lines missing — the SuppressFilter layer). The pre→post flip is the
SC-001 evidence; the three classification lines queryable is SC-006.
