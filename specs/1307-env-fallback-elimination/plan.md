# Feature 1307: Implementation Plan

## Terraform Verification Summary

Cross-reference of Category A variables against Terraform `environment_variables` blocks
in `infrastructure/terraform/main.tf`:

| Variable | Lambda | Terraform Line | Status |
|----------|--------|---------------|--------|
| `DASHBOARD_URL` (security_headers.py) | dashboard | NOT PRESENT | **DEAD CODE** -- variable defined but never used in security_headers.py or anywhere in dashboard Lambda. **Remove entirely.** |
| `COGNITO_USER_POOL_ID` | dashboard | 426 | Present (from `module.cognito.user_pool_id`) |
| `COGNITO_CLIENT_ID` | dashboard | 427 | Present (from `module.cognito.client_id`) |
| `COGNITO_DOMAIN` | dashboard | 429 | Present (from `module.cognito.domain`) |
| `COGNITO_REDIRECT_URI` | dashboard | 431 | Present (conditional, defaults to `""` if `cognito_callback_urls` empty -- but default ensures non-empty) |
| `SENDGRID_SECRET_ARN` | notification | 570 | Present (from `module.secrets.sendgrid_secret_arn`) |
| `DASHBOARD_URL` (notification/handler.py) | notification | 575 | Present (from `var.frontend_url`, also wired post-creation at line 1341) |
| `SSE_LAMBDA_URL` | dashboard | 466 | Present (from `module.sse_streaming_lambda.function_url`) |
| `FRONTEND_URL` | dashboard | 434 | Present (from `var.frontend_url`) |
| `SNS_TOPIC_ARN` (ingestion/handler.py) | ingestion | 301 | Present (from `module.sns.topic_arn`) |
| `TIINGO_SECRET_ARN` (ingestion/handler.py) | ingestion | 302 | Present (from `module.secrets.tiingo_secret_arn`) |
| `FINNHUB_SECRET_ARN` (ingestion/handler.py) | ingestion | 303 | Present (from `module.secrets.finnhub_secret_arn`) |

**Result**: All Category A variables are present in Terraform. One (DASHBOARD_URL in
security_headers.py) is dead code and should be removed rather than made fail-fast.

## Important Nuance: `os.environ["VAR"]` vs Empty String

`os.environ["VAR"]` only raises `KeyError` if the key is **absent**. If Terraform sets
`VAR = ""`, `os.environ["VAR"]` returns `""` without error. For variables where empty
string is also invalid, add explicit validation after the lookup.

Approach per variable:
- **A1 (DASHBOARD_URL in security_headers.py)**: Remove dead code entirely
- **A2-A5 (Cognito vars)**: Change to `os.environ["VAR"]` in `from_env()`. Add a
  `__post_init__` or validation method to CognitoConfig that checks for empty values.
- **A6-A7 (notification handler)**: Change to `os.environ["VAR"]`
- **A8 (SSE_LAMBDA_URL)**: Change to `os.environ["VAR"]`
- **A9 (FRONTEND_URL in auth.py)**: Change to `os.environ["VAR"]` (lazy load inside function -- must stay as function-level read, not module-level)
- **A10-A12 (ingestion handler)**: Change to `os.environ["VAR"]` in `_get_config()`

## File-by-File Changes

### File 1: `src/lambdas/shared/middleware/security_headers.py`

**Action**: Remove dead `DASHBOARD_URL` variable.

```python
# REMOVE line 34:
DASHBOARD_URL = os.environ.get("DASHBOARD_URL", "")
```

### File 2: `src/lambdas/shared/auth/cognito.py`

**Action**: Change 4 vars to fail-fast in `from_env()`.

```python
# Line 54: COGNITO_USER_POOL_ID
user_pool_id=os.environ["COGNITO_USER_POOL_ID"],
# Line 55: COGNITO_CLIENT_ID
client_id=os.environ["COGNITO_CLIENT_ID"],
# Line 57: COGNITO_DOMAIN
domain=os.environ["COGNITO_DOMAIN"],
# Line 59: COGNITO_REDIRECT_URI
redirect_uri=os.environ["COGNITO_REDIRECT_URI"],
```

Leave unchanged:
- Line 56: `COGNITO_CLIENT_SECRET` -- uses `get()` with `None` default (truly optional)
- Line 58: `AWS_REGION` -- has meaningful default "us-east-1"

### File 3: `src/lambdas/notification/handler.py`

**Action**: Change 2 vars to fail-fast.

```python
# Line 39:
SENDGRID_SECRET_ARN = os.environ["SENDGRID_SECRET_ARN"]
# Line 43:
DASHBOARD_URL = os.environ["DASHBOARD_URL"]
```

### File 4: `src/lambdas/dashboard/handler.py`

**Action**: Change 1 var to fail-fast.

```python
# Line 105:
SSE_LAMBDA_URL = os.environ["SSE_LAMBDA_URL"]
```

Leave unchanged:
- Line 103: `CHAOS_EXPERIMENTS_TABLE` -- Category B (optional chaos)
- Line 111: `CORS_ORIGINS` -- Category B (empty = no origins)

### File 5: `src/lambdas/dashboard/auth.py`

**Action**: Change 1 var to fail-fast.

```python
# Line 2014:
frontend_url = os.environ["FRONTEND_URL"].rstrip("/")
```

Note: This is inside a function (`_resolve_redirect_uri`), not module-level. The
function is called lazily, so this change means OAuth redirect fails immediately
(not at cold start) if FRONTEND_URL is missing. This is acceptable because:
1. FRONTEND_URL IS in Terraform (line 434)
2. A clear KeyError is better than falling through to localhost

### File 6: `src/lambdas/ingestion/handler.py`

**Action**: Change 3 vars to fail-fast in `_get_config()`.

```python
# Line 593:
"sns_topic_arn": os.environ["SNS_TOPIC_ARN"],
# Line 597:
"tiingo_secret_arn": os.environ["TIINGO_SECRET_ARN"],
# Line 598:
"finnhub_secret_arn": os.environ["FINNHUB_SECRET_ARN"],
```

Leave unchanged:
- Line 592: `USERS_TABLE` -- has fallback to `DATABASE_TABLE` (valid pattern)
- Line 594-596: `ALERT_TOPIC_ARN` -- optional operational alerts
- Line 599: `MODEL_VERSION` -- has meaningful default "v1.0.0"

### Category B Enhancements (optional, lower priority)

#### File 7: `src/lambdas/dashboard/chaos.py`

**Action**: Add `validate_critical_env_vars()` call for visibility.

```python
# After line 52, add:
from src.lambdas.shared.env_validation import validate_critical_env_vars
validate_critical_env_vars(["CHAOS_EXPERIMENTS_TABLE", "CHAOS_REPORTS_TABLE"])
```

#### File 8: `src/lambdas/dashboard/handler.py`

**Action**: Add logging for empty CORS_ORIGINS.

```python
# After line 113, add:
if not _CORS_ALLOWED_ORIGINS:
    logger.warning("CORS_ORIGINS is empty — all cross-origin requests will be rejected")
```

## Test Impact

Tests that mock or set these env vars need to ensure they're set, not just defaulted.
Check:
- `tests/unit/test_security_headers.py` -- remove DASHBOARD_URL references if any
- `tests/unit/test_cognito.py` -- ensure env vars set in fixtures
- `tests/unit/test_notification_handler.py` -- ensure env vars set
- `tests/unit/test_dashboard_handler.py` -- ensure SSE_LAMBDA_URL set
- `tests/unit/test_ingestion_handler.py` -- ensure SNS/Tiingo/Finnhub ARNs set

## Execution Order

1. Verify Terraform (Stage 4) -- already verified above
2. Remove dead code (A1: security_headers.py DASHBOARD_URL)
3. Change Category A vars (Files 2-6)
4. Add Category B logging (Files 7-8)
5. Update tests if needed
6. Run `make test-local` to verify
