# Stage 6: Re-Plan Based on Drift

## Drift Items Found

### D1: A1 reclassified from "fail-fast" to "remove dead code"

**Original plan**: Change `DASHBOARD_URL = os.environ.get("DASHBOARD_URL", "")` to
`os.environ["DASHBOARD_URL"]` in security_headers.py.

**Problem**: `DASHBOARD_URL` is NOT in the dashboard Lambda's Terraform env block.
Changing to `os.environ["DASHBOARD_URL"]` would crash the dashboard Lambda on cold
start with `KeyError: 'DASHBOARD_URL'`.

**Root cause**: `DASHBOARD_URL` was defined in security_headers.py but is never
referenced anywhere in the file or imported by any other module. It is dead code.

**Updated plan**: Remove the dead variable entirely from security_headers.py.

### D2: A9 nuance -- FRONTEND_URL empty in dev is intentional

**Original assumption**: Empty FRONTEND_URL = broken OAuth redirects.

**Actual behavior**: `_resolve_redirect_uri()` intentionally falls back to
`http://localhost:3000` when FRONTEND_URL is empty. This is correct for local dev.

**Impact on plan**: None. The change from `get("FRONTEND_URL", "")` to
`os.environ["FRONTEND_URL"]` is still correct because:
1. The key is always present (no crash)
2. Empty-string behavior is unchanged
3. The `rstrip("/")` call works on empty string without error

## Plan Adjustments

| Item | Original | Updated | Reason |
|------|----------|---------|--------|
| A1 | Change to `os.environ["DASHBOARD_URL"]` | Remove dead variable | Not in dashboard TF env; never used |
| A9 | Change to `os.environ["FRONTEND_URL"]` | Same (no change) | Confirmed safe -- key always present |
| All others | No change | No change | Terraform verified |

## Conclusion

One plan adjustment (A1: remove dead code instead of fail-fast). All other items
proceed as originally planned. No re-scoping needed.
