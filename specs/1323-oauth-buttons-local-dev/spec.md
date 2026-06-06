# Feature Specification: OAuth Buttons Local Dev

**Feature ID**: 1323
**Created**: 2026-04-05
**Status**: Draft
**Input**: OAuth sign-in buttons (Google, GitHub) don't render on /auth/signin in local dev or CI because `ENABLED_OAUTH_PROVIDERS` and Cognito env vars are not set in `scripts/run-local-api.py`.

## Problem Statement

The OAuth sign-in buttons on `/auth/signin` do not render when running the local development API server (`scripts/run-local-api.py`). This is because:

1. `get_oauth_urls()` in `src/lambdas/dashboard/auth.py` (line 2046) reads `ENABLED_OAUTH_PROVIDERS` from the environment. When empty, it returns `{providers: {}, state: ""}`.
2. The frontend (`frontend/src/app/auth/signin/page.tsx`) fetches providers via `authApi.getOAuthUrls()`. When the response has zero providers, the `<OAuthButtons>` component is not rendered (line 69: `{hasOAuthProviders && ...}`).
3. Even if `ENABLED_OAUTH_PROVIDERS` were set, `CognitoConfig.from_env()` (line 2043) would crash because it reads four required env vars that are not set: `COGNITO_USER_POOL_ID`, `COGNITO_CLIENT_ID`, `COGNITO_DOMAIN`, and `COGNITO_REDIRECT_URI`.
4. `_resolve_redirect_uri()` (line 2014) reads `FRONTEND_URL` which is also unset.

**Impact**: E2E auth tests that assert OAuth button visibility fail. Developers cannot visually verify or iterate on the OAuth sign-in UI locally.

## User Scenarios & Testing

### US1 - OAuth Buttons Render in Local Dev (Priority: P1)

As a frontend developer, I want to see OAuth buttons (Google, GitHub) on `/auth/signin` when running the local API so I can develop and style the sign-in page accurately.

**Why this priority**: Without this, the local sign-in page looks different from production, and auth UI work requires deploying to preprod.

**Independent Test**: Start local API (`python scripts/run-local-api.py`), start frontend (`npm run dev`), navigate to `http://localhost:3000/auth/signin`, verify Google and GitHub OAuth buttons are visible.

**Acceptance Scenarios**:

1. **Given** the local API server is running, **When** the frontend fetches `/api/v2/auth/oauth/urls`, **Then** the response contains `providers.google` and `providers.github` with `authorize_url` values.
2. **Given** the OAuth buttons are visible, **When** user views the sign-in page, **Then** both "Sign in with Google" and "Sign in with GitHub" buttons render with correct icons.
3. **Given** the OAuth buttons are visible, **When** user clicks a button, **Then** the browser navigates to a Cognito authorize URL (which will fail since Cognito is not running locally, but the button click itself works).

---

### US2 - E2E Test "Should Show OAuth Buttons" Passes (Priority: P1)

As a CI pipeline, I want the E2E test asserting OAuth button visibility to pass so the test suite is green without skipping auth tests.

**Why this priority**: Failing or skipped tests erode confidence in the test suite.

**Independent Test**: Run `curl http://localhost:8000/api/v2/auth/oauth/urls` and verify the JSON response has non-empty `providers` object with `google` and `github` keys.

**Acceptance Scenarios**:

1. **Given** the local API is running with mock env vars, **When** `GET /api/v2/auth/oauth/urls` is called, **Then** response is 200 with `providers.google.authorize_url` and `providers.github.authorize_url`.
2. **Given** the E2E test loads the signin page, **When** it queries for OAuth buttons, **Then** both buttons are found in the DOM.

---

## Requirements

### R1: Set ENABLED_OAUTH_PROVIDERS in run-local-api.py

Add `os.environ.setdefault("ENABLED_OAUTH_PROVIDERS", "google,github")` to the environment variable block in `scripts/run-local-api.py` (after line 88).

### R2: Set All CognitoConfig Env Vars for URL Generation

`CognitoConfig.from_env()` (defined in `src/lambdas/shared/auth/cognito.py:51-60`) requires these environment variables:

| Env Var | Required | Source | Mock Value |
|---------|----------|--------|------------|
| `COGNITO_USER_POOL_ID` | Yes (`os.environ[]`) | `cognito.py:54` | `local-user-pool` |
| `COGNITO_CLIENT_ID` | Yes (`os.environ[]`) | `cognito.py:55` | `local-client-id` |
| `COGNITO_CLIENT_SECRET` | No (`os.environ.get()`) | `cognito.py:56` | Not set (None) |
| `COGNITO_DOMAIN` | Yes (`os.environ[]`) | `cognito.py:57` | `local-auth` |
| `AWS_REGION` | No (defaults `us-east-1`) | `cognito.py:58` | Already set |
| `COGNITO_REDIRECT_URI` | Yes (`os.environ[]`) | `cognito.py:59` | `http://localhost:3000/auth/callback` |

### R3: Set FRONTEND_URL for Redirect URI Resolution

`_resolve_redirect_uri()` (line 2014) reads `os.environ["FRONTEND_URL"]` (required, not `get()`). Must set `FRONTEND_URL=http://localhost:3000`.

## Edge Cases

| Scenario | Expected Behavior |
|----------|-------------------|
| User clicks OAuth button locally | Browser navigates to `https://local-auth.auth.us-east-1.amazoncognito.com/oauth2/authorize?...` which will fail (no real Cognito). This is expected for local dev. |
| `COGNITO_CLIENT_SECRET` not set | `CognitoConfig.from_env()` uses `os.environ.get()` which returns `None`. This is fine -- the code handles `None` gracefully (no basic auth header sent). |
| OAuth URLs endpoint called without DynamoDB state table | `store_oauth_state()` writes to the mock DynamoDB `local-users` table. Already handled by moto mocks. |
| Future provider added (e.g., Apple) | Only `google` and `github` are checked in `get_oauth_urls()`. Adding a provider requires code changes, not just env var changes. Out of scope. |

## Out of Scope

- Real OAuth flow completion (Cognito is not running locally)
- Cognito user pool setup or configuration
- Production deployment changes
- Mock OAuth callback handling (clicking buttons will navigate to a dead Cognito URL)
- Adding new OAuth providers beyond Google and GitHub

## Success Metrics

1. `curl http://localhost:8000/api/v2/auth/oauth/urls` returns JSON with `providers.google` and `providers.github`
2. OAuth buttons visible on `http://localhost:3000/auth/signin` when running local dev
3. E2E test asserting OAuth button visibility passes

---

## AR#1: Adversarial Review - Specification

**Reviewer**: Self (adversarial)
**Date**: 2026-04-05

### Findings

| Severity | Finding | Resolution |
|----------|---------|------------|
| CRITICAL | Are we leaking real secrets by setting mock Cognito values? | **No.** All values (`local-user-pool`, `local-client-id`, `local-auth`) are fabricated mock strings. They do not correspond to any real AWS Cognito resource. `COGNITO_CLIENT_SECRET` is intentionally left unset (None). No real credentials are introduced. |
| HIGH | If `CognitoConfig.from_env()` raises `KeyError` on a missing env var, the entire local server crashes on first OAuth URL request. | **Mitigated by R2.** All four required vars (`COGNITO_USER_POOL_ID`, `COGNITO_CLIENT_ID`, `COGNITO_DOMAIN`, `COGNITO_REDIRECT_URI`) are set via `os.environ.setdefault()` before the handler is imported. |
| HIGH | `_resolve_redirect_uri()` reads `os.environ["FRONTEND_URL"]` (hard `[]` access, not `.get()`). Missing this crashes the handler. | **Mitigated by R3.** `FRONTEND_URL` is added to the env var block. |
| MEDIUM | `store_oauth_state()` writes to DynamoDB. Does the mock table schema support it? | **Mitigated.** The `local-users` table is created with PK/SK string keys by `create_mock_tables()`. OAuth state uses PK=`STATE#{id}` pattern which fits the existing schema. |
| LOW | OAuth authorize URLs will point to `local-auth.auth.us-east-1.amazoncognito.com` which is a valid-looking but non-existent domain. Could confuse developers. | **Acceptable.** This is standard local dev behavior. The URL format clearly contains "local-auth" signaling it's not real. |

### Gate

**PASS** -- All critical and high findings have mitigations via R1-R3. No security risk from mock values. No crash paths remain.

---

## Clarifications

### C1: What env vars does CognitoConfig.from_env() need?

**Source**: `src/lambdas/shared/auth/cognito.py:51-60`

```python
@classmethod
def from_env(cls) -> "CognitoConfig":
    return cls(
        user_pool_id=os.environ["COGNITO_USER_POOL_ID"],      # Required
        client_id=os.environ["COGNITO_CLIENT_ID"],              # Required
        client_secret=os.environ.get("COGNITO_CLIENT_SECRET"),  # Optional
        domain=os.environ["COGNITO_DOMAIN"],                    # Required
        region=os.environ.get("AWS_REGION", "us-east-1"),       # Optional, defaulted
        redirect_uri=os.environ["COGNITO_REDIRECT_URI"],        # Required
    )
```

Four required (hard `os.environ[]`), two optional (`.get()` with defaults/None).

### C2: What does _resolve_redirect_uri() need?

**Source**: `src/lambdas/dashboard/auth.py:2014`

```python
frontend_url = os.environ["FRONTEND_URL"].rstrip("/")
```

Hard `os.environ[]` access. Must set `FRONTEND_URL`.

### C3: Does store_oauth_state() work with mock DynamoDB?

Yes. It writes to the users table (same table used for user records) using a `STATE#` PK prefix. The mock `local-users` table created by `create_mock_tables()` has PK/SK string attributes which is compatible.

### C4: What URL format do the OAuth buttons generate?

`CognitoConfig.get_authorize_url()` generates:
```
https://{domain}.auth.{region}.amazoncognito.com/oauth2/authorize?client_id=...&response_type=code&scope=openid+email+profile&redirect_uri=...&identity_provider=Google
```

With mock values this becomes:
```
https://local-auth.auth.us-east-1.amazoncognito.com/oauth2/authorize?client_id=local-client-id&...
```

This URL will fail to load (no real Cognito endpoint), which is expected behavior for local dev.
