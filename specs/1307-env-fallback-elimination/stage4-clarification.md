# Stage 4: Clarification — Terraform Cross-Check

## Cross-Check Results

### Ingestion Lambda (`module "ingestion_lambda"`, main.tf:276-326)

| Variable | Terraform Line | Source | Verdict |
|----------|---------------|--------|---------|
| `SNS_TOPIC_ARN` | 301 | `module.sns.topic_arn` | SAFE -- always set by SNS module |
| `TIINGO_SECRET_ARN` | 302 | `module.secrets.tiingo_secret_arn` | SAFE -- always set by secrets module |
| `FINNHUB_SECRET_ARN` | 303 | `module.secrets.finnhub_secret_arn` | SAFE -- always set by secrets module |

### Dashboard Lambda (`module "dashboard_lambda"`, main.tf:389-489)

| Variable | Terraform Line | Source | Verdict |
|----------|---------------|--------|---------|
| `COGNITO_USER_POOL_ID` | 426 | `module.cognito.user_pool_id` | SAFE -- always set by Cognito module |
| `COGNITO_CLIENT_ID` | 427 | `module.cognito.client_id` | SAFE -- always set by Cognito module |
| `COGNITO_DOMAIN` | 429 | `module.cognito.domain` | SAFE -- always set by Cognito module |
| `COGNITO_REDIRECT_URI` | 431 | Conditional on `cognito_callback_urls` | SAFE -- variable default is `["http://localhost:3000/auth/callback"]` so length > 0 |
| `SSE_LAMBDA_URL` | 466 | `module.sse_streaming_lambda.function_url` | SAFE -- always set by SSE Lambda module |
| `FRONTEND_URL` | 434 | `var.frontend_url` | PRESENT but defaults to `""` -- see note below |
| `DASHBOARD_URL` | NOT PRESENT | N/A | **DEAD CODE** in security_headers.py -- remove |

### Notification Lambda (`module "notification_lambda"`, main.tf:544-599)

| Variable | Terraform Line | Source | Verdict |
|----------|---------------|--------|---------|
| `SENDGRID_SECRET_ARN` | 570 | `module.secrets.sendgrid_secret_arn` | SAFE -- always set by secrets module |
| `DASHBOARD_URL` | 575 | `var.frontend_url` (+ post-creation wiring at line 1341) | SAFE -- set by variable or wiring script |

## Edge Cases Found

### Edge Case 1: FRONTEND_URL defaults to empty string

`var.frontend_url` defaults to `""` in `variables.tf:143`. This means in dev
environments (where `frontend_url` is not set in tfvars), `FRONTEND_URL` will be
present in the Lambda env but with value `""`.

**Impact**: `os.environ["FRONTEND_URL"]` succeeds (key exists) but returns `""`.
The existing code in `_resolve_redirect_uri` already handles empty by falling back
to localhost:3000 -- which is correct for local dev.

**Risk**: In production, if `frontend_url` is not set in prod.tfvars, OAuth
redirects go to localhost. But this is a Terraform configuration issue, not a code
issue.

**Decision**: Keep as Category A. The change from `get("FRONTEND_URL", "")` to
`os.environ["FRONTEND_URL"]` is still correct because:
1. The key is always present (no crash risk)
2. It communicates "this should be configured"
3. The function already handles empty correctly for dev

### Edge Case 2: COGNITO_REDIRECT_URI conditional

`COGNITO_REDIRECT_URI = length(var.cognito_callback_urls) > 0 ? var.cognito_callback_urls[0] : ""`

If someone explicitly sets `cognito_callback_urls = []`, the env var would be `""`.
But `os.environ["COGNITO_REDIRECT_URI"]` would still succeed (key present, value
empty). The Cognito OAuth flow would fail with a Cognito-level error about redirect
mismatch, which is appropriate.

**Decision**: Keep as Category A. The default ensures this never happens in practice.

### Edge Case 3: DASHBOARD_URL dead code in security_headers.py

`DASHBOARD_URL` at line 34 of security_headers.py is:
- Defined at module level
- Never referenced in the file
- Never imported by any other file
- NOT in the dashboard Lambda's Terraform env block

This variable is dead code from a previous refactoring. Removing it is the correct
action (not changing to fail-fast, which would crash the dashboard Lambda since the
key doesn't exist in its env block).

## Conclusion

All 12 Category A variables are confirmed present in their respective Terraform
env blocks. One (DASHBOARD_URL in security_headers.py) is dead code and should be
removed. No variables need to be downgraded to Category B or C.

**Proceed with implementation as planned.**
