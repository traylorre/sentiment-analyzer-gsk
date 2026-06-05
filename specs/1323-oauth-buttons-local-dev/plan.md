# Implementation Plan: OAuth Buttons Local Dev

**Feature ID**: 1323
**Created**: 2026-04-05
**Status**: Draft
**Spec**: [spec.md](spec.md)

## Summary

Single-file change to `scripts/run-local-api.py`. Add 6 environment variables (5 new, 1 for FRONTEND_URL) to the existing `os.environ.setdefault()` block so that `CognitoConfig.from_env()` and `_resolve_redirect_uri()` succeed, and `get_oauth_urls()` returns populated provider data.

## Change Details

### File: `scripts/run-local-api.py`

**Location**: After line 88 (`os.environ.setdefault("SSE_LAMBDA_URL", ...)`) and before the `create_mock_tables()` function definition.

**Add these lines**:

```python
# Feature 1323: OAuth button rendering in local dev
# These mock values allow CognitoConfig.from_env() to succeed and
# get_oauth_urls() to return provider URLs. The URLs point to a
# non-existent Cognito domain (expected — no real OAuth locally).
os.environ.setdefault("ENABLED_OAUTH_PROVIDERS", "google,github")
os.environ.setdefault("COGNITO_USER_POOL_ID", "local-user-pool")
os.environ.setdefault("COGNITO_CLIENT_ID", "local-client-id")
os.environ.setdefault("COGNITO_DOMAIN", "local-auth")
os.environ.setdefault("COGNITO_REDIRECT_URI", "http://localhost:3000/auth/callback")
os.environ.setdefault("FRONTEND_URL", "http://localhost:3000")
```

**Why `setdefault()`**: Consistent with all other env vars in the file. Allows override via `.env.local` or shell environment for developers who have real Cognito configured.

### Env Var Mapping to Code Consumers

| Env Var | Consumer | Line | Access |
|---------|----------|------|--------|
| `ENABLED_OAUTH_PROVIDERS` | `get_oauth_urls()` | `auth.py:2046` | `os.environ.get()` |
| `COGNITO_USER_POOL_ID` | `CognitoConfig.from_env()` | `cognito.py:54` | `os.environ[]` |
| `COGNITO_CLIENT_ID` | `CognitoConfig.from_env()` | `cognito.py:55` | `os.environ[]` |
| `COGNITO_DOMAIN` | `CognitoConfig.from_env()` | `cognito.py:57` | `os.environ[]` |
| `COGNITO_REDIRECT_URI` | `CognitoConfig.from_env()` | `cognito.py:59` | `os.environ[]` |
| `FRONTEND_URL` | `_resolve_redirect_uri()` | `auth.py:2014` | `os.environ[]` |

### What is NOT changed

- `COGNITO_CLIENT_SECRET` -- intentionally omitted. `CognitoConfig.from_env()` uses `os.environ.get()` which returns `None`. The code handles this gracefully (no basic auth header sent during token exchange).
- `AWS_REGION` -- already set to `us-east-1` on line 81. `CognitoConfig.from_env()` defaults to the same value.
- No backend code changes. No frontend code changes. No test changes.

## Risk Assessment

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| Mock values accidentally used in production | Very Low | High | Values are in `scripts/run-local-api.py` which is never imported in Lambda. `setdefault()` never overwrites real env vars. |
| `store_oauth_state()` fails on mock DynamoDB | Low | Medium | Uses PK/SK pattern on `local-users` table already created by `create_mock_tables()`. |
| Developer confusion when OAuth button click fails | Low | Low | Expected local dev behavior. Cognito URL contains "local-auth" making it obvious. |

## Dependencies

- None. All changes are additive to existing file.
- No new packages required.
- No infrastructure changes.

---

## AR#2: Adversarial Review - Plan

**Reviewer**: Self (adversarial)
**Date**: 2026-04-05

### Findings

| Severity | Finding | Resolution |
|----------|---------|------------|
| HIGH | If `store_oauth_state()` uses a table name other than `local-users`, the DynamoDB call will fail with `ResourceNotFoundException`. | **Verified**: `store_oauth_state()` uses the same users table (injected as `table` parameter from the handler). The handler resolves table name from `USERS_TABLE` env var, which is set to `local-users` on line 76. The mock table exists. No risk. |
| MEDIUM | The `generate_state()` function is called inside `get_oauth_urls()`. Does it depend on any unset env var? | **Verified**: `generate_state()` uses `secrets.token_urlsafe()` (stdlib). No env var dependency. Safe. |
| MEDIUM | Are there other code paths in the auth handler that call `CognitoConfig.from_env()`? Lines 2186 and 2805 also call it. | **Acceptable**: Those are in `handle_oauth_callback()` and token refresh flows, which are only triggered by POST requests after a real OAuth flow. Local dev won't reach them. If they are reached (developer manually testing), the env vars are already set. |
| LOW | `os.environ.setdefault()` placement matters -- must be before `from src.lambdas.dashboard.handler import lambda_handler`. | **Verified**: The import happens inside `_invoke_handler()` at runtime (line 235), well after module-level env setup. Safe. |

### Gate

**PASS** -- Single-file, additive change. No crash paths. All consumers verified.
