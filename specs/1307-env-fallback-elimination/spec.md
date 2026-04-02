# Feature 1307: Environment Variable Fallback Elimination

## Problem Statement

After PRs #857 (ENVIRONMENT fallbacks) and #854 (test fallbacks) established the
`os.environ["VAR"]` fail-fast pattern, approximately 15 instances of
`os.environ.get("VAR", "")` remain in production Lambda code under `src/lambdas/`.
These empty-string fallbacks mask misconfiguration: the Lambda starts successfully
but silently fails at runtime (broken CORS, broken OAuth, broken notifications).

## Existing Pattern

- **Fail-fast**: `os.environ["ENVIRONMENT"]` (PR #857) -- Lambda crashes on cold
  start if missing, immediately surfacing misconfiguration.
- **Validation utility**: `validate_critical_env_vars()` in
  `src/lambdas/shared/env_validation.py` (Feature 1290) -- logs warnings for missing
  vars but does **not** crash (degraded mode).

## Categorized Inventory

### Category A -- Required Variables (change to fail-fast)

These variables cause broken functionality when empty. An empty string means the
feature is non-functional, not degraded. Change from `os.environ.get("VAR", "")`
to `os.environ["VAR"]`.

| # | File | Line | Variable | Impact if Empty |
|---|------|------|----------|-----------------|
| A1 | `src/lambdas/shared/middleware/security_headers.py` | 34 | `DASHBOARD_URL` | Broken CORS -- empty Allow-Origin |
| A2 | `src/lambdas/shared/auth/cognito.py` | 54 | `COGNITO_USER_POOL_ID` | Broken OAuth -- invalid Cognito URL |
| A3 | `src/lambdas/shared/auth/cognito.py` | 55 | `COGNITO_CLIENT_ID` | Broken OAuth -- token exchange fails |
| A4 | `src/lambdas/shared/auth/cognito.py` | 57 | `COGNITO_DOMAIN` | Broken OAuth -- invalid auth URL |
| A5 | `src/lambdas/shared/auth/cognito.py` | 59 | `COGNITO_REDIRECT_URI` | Broken OAuth -- redirect mismatch |
| A6 | `src/lambdas/notification/handler.py` | 39 | `SENDGRID_SECRET_ARN` | Broken notifications -- can't fetch secret |
| A7 | `src/lambdas/notification/handler.py` | 43 | `DASHBOARD_URL` | Broken notification links -- empty URLs |
| A8 | `src/lambdas/dashboard/handler.py` | 105 | `SSE_LAMBDA_URL` | Broken SSE routing -- empty endpoint |
| A9 | `src/lambdas/dashboard/auth.py` | 2014 | `FRONTEND_URL` | Broken OAuth redirects -- falls through to localhost |
| A10 | `src/lambdas/ingestion/handler.py` | 593 | `SNS_TOPIC_ARN` | Broken publish -- empty TopicArn |
| A11 | `src/lambdas/ingestion/handler.py` | 597 | `TIINGO_SECRET_ARN` | Broken ingestion -- can't fetch API key |
| A12 | `src/lambdas/ingestion/handler.py` | 598 | `FINNHUB_SECRET_ARN` | Broken ingestion -- can't fetch API key |

### Category B -- Optional Variables (keep get(), add logging where missing)

These variables enable optional features. Empty string is a valid "disabled" state.

| # | File | Line | Variable | Rationale |
|---|------|------|----------|-----------|
| B1 | `src/lambdas/shared/dependencies.py` | 132 | `TICKER_CACHE_BUCKET` | Already has validation at line 133 (`if not bucket: return None`) |
| B2 | `src/lambdas/dashboard/chaos.py` | 51 | `CHAOS_EXPERIMENTS_TABLE` | Chaos is optional; empty = chaos disabled |
| B3 | `src/lambdas/dashboard/chaos.py` | 52 | `CHAOS_REPORTS_TABLE` | Chaos is optional; empty = reporting disabled |
| B4 | `src/lambdas/dashboard/chaos.py` | 54 | `SCHEDULER_ROLE_ARN` | Chaos auto-restore optional |
| B5 | `src/lambdas/dashboard/handler.py` | 103 | `CHAOS_EXPERIMENTS_TABLE` | Chaos is optional in dashboard |
| B6 | `src/lambdas/dashboard/handler.py` | 111 | `CORS_ORIGINS` | Empty = no CORS origins (set comprehension produces empty set) |

### Category C -- Justified Exceptions (leave as-is)

These have existing validation or are legitimately optional at the runtime level.

| # | File | Line | Variable | Justification |
|---|------|------|----------|---------------|
| C1 | `src/lambdas/shared/auth/stripe_utils.py` | 24 | `STRIPE_WEBHOOK_SECRET_ARN` | Already has `if not: raise RuntimeError` at line 25-26 |
| C2 | `src/lambdas/canary/handler.py` | 84 | `_X_AMZN_TRACE_ID` | AWS-injected at runtime; may legitimately be empty |
| C3 | `src/lambdas/sse_streaming/tracing.py` | 125 | `_X_AMZN_TRACE_ID` | AWS-injected at runtime; may legitimately be empty |
| C4 | `src/lambdas/dashboard/auth.py` | 2046 | `ENABLED_OAUTH_PROVIDERS` | Optional comma-separated list; empty = no providers enabled |
| C5 | `src/lambdas/ingestion/config.py` | 147 | `WATCH_TAGS` | Validated in `_validate()` (raises ConfigurationError) |
| C6 | `src/lambdas/ingestion/config.py` | 152 | `SNS_TOPIC_ARN` | Validated in `_validate()` (raises ConfigurationError at line 94-95) |
| C7 | `src/lambdas/shared/auth/cognito.py` | 56 | `COGNITO_CLIENT_SECRET` | Uses `get()` with `None` default (not ""); truly optional for public clients |
| C8 | `src/lambdas/shared/auth/cognito.py` | 58 | `AWS_REGION` | Has meaningful default "us-east-1"; not a silent failure |
| C9 | `src/lambdas/ingestion/handler.py` | 594-596 | `ALERT_TOPIC_ARN` | Operational alerts are optional; empty = no alerts |
| C10 | `src/lambdas/ingestion/handler.py` | 599 | `MODEL_VERSION` | Has meaningful default "v1.0.0"; not a silent failure |
| C11 | `src/lambdas/dashboard/chaos.py` | 57 | `AWS_LAMBDA_FUNCTION_NAME` | AWS-injected at runtime; self-reference construction |
| C12 | `src/lambdas/dashboard/chaos.py` | 58-59 | `AWS_REGION`/`AWS_DEFAULT_REGION` | AWS-injected with meaningful fallback |

## Approach

### Category A Changes

For each variable:
1. **Verify** the variable exists in the Lambda's Terraform `environment` block
2. **Change** `os.environ.get("VAR", "")` to `os.environ["VAR"]`
3. Special case: `CognitoConfig.from_env()` -- change 4 fields in one method
4. Special case: `ingestion/handler.py:_get_config()` -- change 3 fields in one function

### Category B Changes

For variables missing logging, add `validate_critical_env_vars()` calls or inline
`logger.info()` at module level to surface when optional features are disabled.
Specifically:
- B2-B4 (chaos.py): Add a single `validate_critical_env_vars()` call for chaos tables
- B5 (handler.py): Already logged via init block at line 116
- B6 (CORS_ORIGINS): Add warning log if empty

### Category C -- No Changes

Already validated, AWS-injected, or have meaningful defaults.

## Risk

**Primary risk**: Category A changes will cause Lambda to crash on cold start if
the corresponding Terraform `environment` block is missing the variable. This is
intentional (fail-fast) but must be verified before deployment.

**Mitigation**: Stage 4 cross-checks every Category A variable against Terraform.

## Success Criteria

1. All Category A variables use `os.environ["VAR"]` (fail-fast)
2. All Category B variables have explicit logging when empty/disabled
3. Category C unchanged
4. All Category A variables confirmed present in Terraform env blocks
5. Existing tests pass (may need env var fixtures updated)
