# AR#3: Final Adversarial Review

## Scope Verification

### Comprehensive Grep Audit

A full grep of `os.environ.get(.*"")` across `src/lambdas/` found 29 instances.
All are accounted for:

| Count | Category | Disposition |
|-------|----------|-------------|
| 11 | A (fail-fast) | Changing to `os.environ["VAR"]` (T2-T6) |
| 1 | A (dead code) | Removing entirely (T1) |
| 6 | B (optional) | Keep with logging enhancements (T7-T8) |
| 11 | C (justified) | Leave as-is |
| **29** | **Total** | **All accounted for** |

### Instances Not in Original Task Description

Two instances found by comprehensive grep that were not in the original task:
1. `ohlc_cache.py:112` -- `OHLC_CACHE_TABLE` -- Category C (has meaningful fallback)
2. `alert_evaluator.py:38` -- `INTERNAL_API_KEY` -- Category B (optional auth key)

Both correctly excluded from Category A. No action needed.

## Adversarial Questions

### Q1: Could the Cognito `from_env()` change break the import chain?

`CognitoConfig.from_env()` is a classmethod, not module-level code. It only
executes when called (e.g., `config = CognitoConfig.from_env()` in auth.py:2043).
The `os.environ["VAR"]` calls happen inside the method body, not at import time.

**Risk**: If `from_env()` is called at module level somewhere (not inside a function),
it would crash on import.

**Verification**: `from_env()` is called at:
- `dashboard/auth.py:2043` -- inside function `get_oauth_urls()` (lazy, safe)

**Verdict**: SAFE. No module-level calls to `from_env()`.

### Q2: Could the notification handler module-level changes crash other Lambdas?

`SENDGRID_SECRET_ARN` and `DASHBOARD_URL` are defined at module level in
`notification/handler.py` (lines 39, 43). These execute at import time.

**Risk**: If another Lambda imports `notification/handler.py`, it would crash if those
env vars are missing from that Lambda's env block.

**Verification**: The notification handler is a standalone Lambda entry point. Other
Lambdas import from `src/lambdas/shared/` but not from `src/lambdas/notification/`.

```
grep -r "from src.lambdas.notification" src/lambdas/ --include="*.py"
```

**Verdict**: SAFE. Only the notification Lambda imports this module.

### Q3: Could the ingestion `_get_config()` changes affect the legacy config.py path?

`ingestion/handler.py:_get_config()` and `ingestion/config.py:get_config()` are
separate functions. The legacy `config.py:get_config()` already validates
`SNS_TOPIC_ARN` in `_validate()`. The new handler's `_get_config()` is independent.

**Verdict**: SAFE. No cross-contamination.

### Q4: What about tests that import these modules without setting env vars?

This is the highest-risk area. When tests import `notification/handler.py`, the
module-level `os.environ["SENDGRID_SECRET_ARN"]` executes immediately.

**Mitigation**: Task T9 specifically addresses this. Common patterns:
- `conftest.py` fixtures that set env vars via `monkeypatch.setenv()`
- `@pytest.fixture(autouse=True)` that sets required env vars
- `mock.patch.dict(os.environ, {...})` in test classes

Tests that currently work (because `get("VAR", "")` returns `""`) will fail with
`KeyError` if the env var isn't set in the test environment. This is EXPECTED and
DESIRED -- it surfaces tests that were running against phantom empty defaults.

**Verdict**: T9 handles this. Budget time for test fixture updates.

### Q5: Is there a risk of partial deployment (code deployed, Terraform not applied)?

If the code change deploys before `terraform apply` runs, and a NEW env var was added
to Terraform, the Lambda would crash.

**Analysis**: This feature does NOT add new Terraform env vars. All Category A variables
are already present in Terraform. The code change only makes the Python code stricter
about their absence. Since Terraform already provides them, partial deployment is safe.

**Verdict**: SAFE. No new Terraform vars needed.

### Q6: Could the dead code removal (T1) break anything?

Removing `DASHBOARD_URL = os.environ.get("DASHBOARD_URL", "")` from security_headers.py.

- The variable is not referenced in the file
- The variable is not in `__all__` or exported
- No other file imports `DASHBOARD_URL` from security_headers
- The `get_cors_headers()` function is deprecated and returns `{}`

**Verdict**: SAFE. Pure dead code removal.

### Q7: Are there any race conditions with module-level vs function-level changes?

- T1, T3, T4: Module-level changes (execute at cold start)
- T2, T5, T6: Function-level changes (execute at call time)

Module-level changes are the highest risk (crash on cold start vs crash on first
invocation). But all module-level variables are confirmed present in Terraform, so
the risk is theoretical.

**Verdict**: SAFE.

## Risk Summary

| Risk | Severity | Likelihood | Mitigation |
|------|----------|------------|------------|
| Test failures from missing env vars | Medium | High | T9 (test fixture updates) |
| Lambda crash from missing Terraform var | Critical | None | All vars verified present |
| Dead code removal breaks import | Low | None | Variable never used |
| Partial deployment mismatch | Critical | None | No new Terraform vars |

## Final Verdict

**APPROVED FOR IMPLEMENTATION.** All adversarial questions resolved. Primary work
item during implementation will be T9 (test fixture updates), which is expected and
budgeted in the task plan.

## Implementation Notes

1. Start with T1 (dead code removal) -- smallest, safest change to validate the
   approach
2. T2-T6 can be done in parallel -- each touches a different file
3. Run tests after each file change to catch fixture gaps early
4. T7-T8 (Category B logging) are optional enhancements; can be deferred if time
   is tight
