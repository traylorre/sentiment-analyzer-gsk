# Tasks: OAuth Buttons Local Dev

**Feature ID**: 1323
**Created**: 2026-04-05
**Status**: Draft
**Plan**: [plan.md](plan.md)

## Task List

### T1: Add OAuth and Cognito env vars to run-local-api.py

**Status**: Pending
**File**: `scripts/run-local-api.py`
**Dependencies**: None

**Description**: Add 6 `os.environ.setdefault()` calls after the existing env var block (after line 88) and before `create_mock_tables()`:

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

**Acceptance**: File saves without syntax errors. `python -c "import ast; ast.parse(open('scripts/run-local-api.py').read())"` succeeds.

---

### T2: Verify OAuth URLs endpoint returns providers

**Status**: Pending
**Dependencies**: T1

**Description**: Start the local API server and verify the OAuth URLs endpoint returns populated provider data.

**Steps**:
1. Run `python scripts/run-local-api.py` (background)
2. Run `curl -s http://localhost:8000/api/v2/auth/oauth/urls | python -m json.tool`
3. Verify response contains:
   - `providers.google.authorize_url` starting with `https://local-auth.auth.us-east-1.amazoncognito.com/oauth2/authorize`
   - `providers.github.authorize_url` starting with `https://local-auth.auth.us-east-1.amazoncognito.com/oauth2/authorize`
   - `state` is a non-empty string
4. Stop the server

**Acceptance**: Response has 200 status, `providers` object has `google` and `github` keys with valid `authorize_url` values.

---

### T3: Verify E2E OAuth button visibility concept

**Status**: Pending
**Dependencies**: T2

**Description**: Confirm that the frontend signin page would render OAuth buttons given the API response from T2.

**Steps**:
1. Verify the frontend logic: `page.tsx:41` checks `availableProviders && availableProviders.length > 0`
2. The API response from T2 has `providers: {google: {...}, github: {...}}`
3. `Object.keys(data.providers)` returns `["google", "github"]` (length 2)
4. `hasOAuthProviders` evaluates to `true`
5. `<OAuthButtons>` and `<AuthDivider>` render

**Acceptance**: Logic trace confirms buttons will render. If a Playwright E2E test exists for OAuth button visibility, run it and confirm it passes.

---

## Summary

| Task | File(s) | Type | Estimate |
|------|---------|------|----------|
| T1 | `scripts/run-local-api.py` | Code change | 2 min |
| T2 | (manual verification) | Smoke test | 3 min |
| T3 | (logic verification) | Validation | 2 min |

**Total estimated effort**: 7 minutes

---

## AR#3: Adversarial Review - Tasks

**Reviewer**: Self (adversarial)
**Date**: 2026-04-05

### Findings

| Severity | Finding | Resolution |
|----------|---------|------------|
| HIGH | T2 assumes port 8000 is available. If another process uses it, the server won't start. | **Acceptable**: Port 8000 is the default in `run-local-api.py`. Developer can override with `PORT=8001`. This is standard local dev behavior, not specific to this feature. |
| MEDIUM | T2 does not account for server startup time. The `curl` may fire before the server is ready. | **Mitigated**: The server logs "Starting local API server on http://localhost:8000" when ready. Wait for that log line before curling. Alternatively, retry with a 1s delay. |
| MEDIUM | T3 is a logic trace, not an actual test execution. Should we run the actual E2E test? | **Acceptable for draft**: Running the full Playwright suite requires both API and frontend running with proper test fixtures. T3 validates the logic path. If a specific E2E test file exists, it should be run as part of the implementation verification, not task specification. |
| LOW | No rollback task defined. | **Not needed**: This is a single-file additive change. Rollback is `git revert`. |

### Gate

**PASS** -- Tasks are minimal, correctly ordered, and cover the full change + verification cycle. No gaps in coverage.
