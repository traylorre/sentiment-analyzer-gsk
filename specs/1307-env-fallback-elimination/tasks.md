# Feature 1307: Tasks

## Dependencies

```
T1 (dead code removal) → independent
T2 (cognito fail-fast) → independent
T3 (notification fail-fast) → independent
T4 (dashboard handler fail-fast) → independent
T5 (dashboard auth fail-fast) → independent
T6 (ingestion handler fail-fast) → independent
T7 (chaos.py logging) → independent
T8 (CORS logging) → depends on T4 (same file)
T9 (test updates) → depends on T1-T6
T10 (validation run) → depends on T1-T9
```

Tasks T1-T6 are independent and can be implemented in parallel. T7-T8 are Category B
enhancements. T9 ensures tests pass. T10 is the final validation gate.

---

## T1: Remove dead DASHBOARD_URL from security_headers.py

**File**: `src/lambdas/shared/middleware/security_headers.py`
**Type**: Dead code removal

Remove line 34:
```python
# REMOVE:
DASHBOARD_URL = os.environ.get("DASHBOARD_URL", "")
```

Also remove the comment on line 33 (`# Pre-chaos stability: ...`) since it references
the removed variable.

**Verification**: `grep -r "DASHBOARD_URL" src/lambdas/shared/middleware/` returns nothing.

---

## T2: Cognito env vars to fail-fast

**File**: `src/lambdas/shared/auth/cognito.py`
**Type**: Category A fail-fast

Change `CognitoConfig.from_env()` (lines 54-59):

```python
# FROM:
user_pool_id=os.environ.get("COGNITO_USER_POOL_ID", ""),
client_id=os.environ.get("COGNITO_CLIENT_ID", ""),
domain=os.environ.get("COGNITO_DOMAIN", ""),
redirect_uri=os.environ.get("COGNITO_REDIRECT_URI", ""),

# TO:
user_pool_id=os.environ["COGNITO_USER_POOL_ID"],
client_id=os.environ["COGNITO_CLIENT_ID"],
domain=os.environ["COGNITO_DOMAIN"],
redirect_uri=os.environ["COGNITO_REDIRECT_URI"],
```

Leave unchanged:
- `COGNITO_CLIENT_SECRET` (line 56) -- truly optional (None default)
- `AWS_REGION` (line 58) -- meaningful default "us-east-1"

**Terraform verification**: Lines 426-431 in main.tf confirm all 4 vars present.

---

## T3: Notification handler env vars to fail-fast

**File**: `src/lambdas/notification/handler.py`
**Type**: Category A fail-fast

Change lines 39 and 43:

```python
# FROM:
SENDGRID_SECRET_ARN = os.environ.get("SENDGRID_SECRET_ARN", "")
DASHBOARD_URL = os.environ.get("DASHBOARD_URL", "")

# TO:
SENDGRID_SECRET_ARN = os.environ["SENDGRID_SECRET_ARN"]
DASHBOARD_URL = os.environ["DASHBOARD_URL"]
```

Also remove the comment on line 42 (`# Pre-chaos stability: ...`) since the fallback
pattern is eliminated.

**Terraform verification**: Lines 570 and 575 in main.tf confirm both vars present.

---

## T4: Dashboard handler SSE_LAMBDA_URL to fail-fast

**File**: `src/lambdas/dashboard/handler.py`
**Type**: Category A fail-fast

Change line 105:

```python
# FROM:
SSE_LAMBDA_URL = os.environ.get("SSE_LAMBDA_URL", "")

# TO:
SSE_LAMBDA_URL = os.environ["SSE_LAMBDA_URL"]
```

**Terraform verification**: Line 466 in main.tf confirms var present.

---

## T5: Dashboard auth FRONTEND_URL to fail-fast

**File**: `src/lambdas/dashboard/auth.py`
**Type**: Category A fail-fast

Change line 2014:

```python
# FROM:
frontend_url = os.environ.get("FRONTEND_URL", "").rstrip("/")

# TO:
frontend_url = os.environ["FRONTEND_URL"].rstrip("/")
```

**Terraform verification**: Line 434 in main.tf confirms var present.
**Note**: Key is always present; empty string behavior unchanged (localhost fallback
in dev is by design).

---

## T6: Ingestion handler env vars to fail-fast

**File**: `src/lambdas/ingestion/handler.py`
**Type**: Category A fail-fast

Change lines 593, 597, 598 in `_get_config()`:

```python
# FROM:
"sns_topic_arn": os.environ.get("SNS_TOPIC_ARN", ""),
"tiingo_secret_arn": os.environ.get("TIINGO_SECRET_ARN", ""),
"finnhub_secret_arn": os.environ.get("FINNHUB_SECRET_ARN", ""),

# TO:
"sns_topic_arn": os.environ["SNS_TOPIC_ARN"],
"tiingo_secret_arn": os.environ["TIINGO_SECRET_ARN"],
"finnhub_secret_arn": os.environ["FINNHUB_SECRET_ARN"],
```

Leave unchanged:
- `USERS_TABLE` (line 592) -- has valid fallback to DATABASE_TABLE
- `ALERT_TOPIC_ARN` (line 594) -- optional operational alerts
- `MODEL_VERSION` (line 599) -- meaningful default "v1.0.0"

**Terraform verification**: Lines 301-303 in main.tf confirm all 3 vars present.

---

## T7: Add chaos.py env var validation logging (Category B)

**File**: `src/lambdas/dashboard/chaos.py`
**Type**: Category B visibility enhancement

After the existing env var reads (line 52), add validation call:

```python
from src.lambdas.shared.env_validation import validate_critical_env_vars
# Chaos features are optional — log when disabled for observability
_missing_chaos_vars = validate_critical_env_vars(
    ["CHAOS_EXPERIMENTS_TABLE", "CHAOS_REPORTS_TABLE"]
)
```

**Note**: This emits CloudWatch-extractable warnings when chaos is not configured,
improving observability. Does not crash the Lambda.

---

## T8: Add CORS_ORIGINS empty warning (Category B)

**File**: `src/lambdas/dashboard/handler.py`
**Type**: Category B visibility enhancement

After line 113 (the CORS_ORIGINS set comprehension), add:

```python
if not _CORS_ALLOWED_ORIGINS:
    logger.warning(
        "CORS_ORIGINS is empty — cross-origin requests will use Lambda URL CORS config only",
        extra={"environment": ENVIRONMENT},
    )
```

---

## T9: Update test fixtures for fail-fast env vars

**Files**: Test files that reference the changed env vars
**Type**: Test maintenance

For each changed variable, ensure test fixtures set the env var (not rely on
`get()` default). Check:

1. Tests importing `cognito.py` -- ensure `COGNITO_USER_POOL_ID`, `COGNITO_CLIENT_ID`,
   `COGNITO_DOMAIN`, `COGNITO_REDIRECT_URI` are in test env
2. Tests importing `notification/handler.py` -- ensure `SENDGRID_SECRET_ARN`,
   `DASHBOARD_URL` are set
3. Tests importing `dashboard/handler.py` -- ensure `SSE_LAMBDA_URL` is set
4. Tests importing `dashboard/auth.py` -- ensure `FRONTEND_URL` is set
5. Tests importing `ingestion/handler.py` -- ensure `SNS_TOPIC_ARN`,
   `TIINGO_SECRET_ARN`, `FINNHUB_SECRET_ARN` are set

**Strategy**: Search test conftest.py files and test files for `monkeypatch.setenv`
or `os.environ` patterns that need updating.

---

## T10: Validation gate

**Command**: `make test-local`
**Type**: Gate

Run full test suite to verify:
1. No `KeyError` in tests (all env vars properly set in fixtures)
2. No import errors (dead code removal doesn't break anything)
3. Category B logging doesn't cause side effects

If tests fail, fix the test fixtures (T9) and re-run.

---

## Execution Order

```
Phase 1 (parallel): T1, T2, T3, T4, T5, T6
Phase 2 (parallel): T7, T8
Phase 3 (sequential): T9 (test fixes based on Phase 1 results)
Phase 4 (gate): T10
```

## Summary

| Task | File | Action | Category |
|------|------|--------|----------|
| T1 | security_headers.py | Remove dead DASHBOARD_URL | A (dead code) |
| T2 | cognito.py | 4 vars to fail-fast | A |
| T3 | notification/handler.py | 2 vars to fail-fast | A |
| T4 | dashboard/handler.py | 1 var to fail-fast | A |
| T5 | dashboard/auth.py | 1 var to fail-fast | A |
| T6 | ingestion/handler.py | 3 vars to fail-fast | A |
| T7 | dashboard/chaos.py | Add validation logging | B |
| T8 | dashboard/handler.py | Add CORS warning | B |
| T9 | tests/ | Update env var fixtures | Test |
| T10 | (make target) | Validation gate | Gate |
