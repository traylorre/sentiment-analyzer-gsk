# Research: OAuth Session Persistence (1381)

## R1 — Where the 401 is actually emitted

`refresh_tokens()` (`src/lambdas/dashboard/router_v2.py:639-688`) returns 401 in exactly two places:
- `router_v2.py:663-664`: no refresh token found in cookie or body → `error_response(401, "Refresh token not found ...")`.
- `router_v2.py:670-671`: `result.error` truthy → `error_response(401, result.message or result.error)`.

`/refresh` is CSRF-exempt (`src/lambdas/shared/auth/csrf.py:38`), so CSRF (403) is ruled out. Therefore the console 401 is one of the two above.

## R2 — Guest vs OAuth refresh divergence

`refresh_access_tokens` (`src/lambdas/dashboard/auth.py:2898-2944`):
- Blocklist check first (FR-007 of Feature 1188): `auth.py:2913-2924`.
- Anonymous branch: `refresh_token.startswith("anon.")` → `_refresh_anonymous_session` (`auth.py:2928-2929`). Fully local, self-describing token. **No external call → reliable.**
- Cognito branch: `cognito_refresh_tokens(config, refresh_token)` (`auth.py:2931-2944`) → HTTP POST to Cognito token endpoint (`cognito.py:213-284`). Non-200 → `TokenError` (`cognito.py:257-265`) → router 401.

This is the OAuth-specific failure surface. The guest path can't hit it.

## R3 — Cognito token call mechanics

`cognito.py:213-284`:
- Basic auth header from `client_id:client_secret` when `config.client_secret` is set (`cognito.py:236-239`); else `client_id` in the body (`cognito.py:246-247`).
- `CognitoConfig.from_env` reads `COGNITO_CLIENT_ID` (required) and `COGNITO_CLIENT_SECRET` (optional) (`cognito.py:51-56`).
- Cognito refresh does NOT rotate the refresh token: returns `refresh_token=None` (`cognito.py:273`). Router leaves the existing cookie untouched (`router_v2.py:678`).

**Failure modes that yield 401 here:** app-client mismatch (token issued under Hosted-UI client X, refreshed under client Y), missing/incorrect client secret, or a confidential-vs-public client mismatch → Cognito `invalid_grant`/`invalid_client`.

## R4 — Feature 1290 env freeze (critical operational constraint)

`infrastructure/terraform/modules/lambda` carries `lifecycle { ignore_changes = [image_uri, environment] }`. Terraform CANNOT set the dashboard Lambda env. Env changes flow through the CI "Step 2.5" sync in `.github/workflows/deploy.yml` or a manual `aws lambda update-function-configuration`. Consequence: the live `COGNITO_CLIENT_ID`/`COGNITO_CLIENT_SECRET` can diverge from Terraform. Any config correction must be verified against `aws lambda get-function-configuration`.

## R5 — Defect B: missing `user_id` in the Cognito refresh response

`RefreshTokenResponse` (`auth.py:1504-1520`) defaults `user_id=None`, `auth_type=None`. The Cognito branch (`auth.py:2934-2939`) never sets them. The frontend `restoreSession` (`frontend/src/stores/auth-store.ts:157-161`) returns `false` when `!data.userId`, forcing `signInAnonymous()`. So the persistence chain breaks at the response contract even when the Cognito call succeeds.

**Server-side source of `user_id`:** `decode_id_token(tokens.id_token)` yields `sub` (cognito_sub); map that to the internal `user_id` via the existing `get_user_by_provider_sub(table, provider, sub)` helper (`auth.py:527`) and/or the `by_cognito_sub` GSI (Feature 1222). ACCURACY NOTE: `get_user_by_cognito_sub` does **not** exist in `auth.py` (only `get_user_by_id:411`, `get_user_by_email_gsi:476`, `get_user_by_provider_sub:527`); implementation reuses `get_user_by_provider_sub` (provider from the id-token identity claim), adding a small `by_cognito_sub` GSI query helper only if provider is unavailable at refresh. This keeps `user_id` derived from validated token claims (SR-005), not client input.

## R6 — Frontend restore contract

`restoreSession` branches:
- Anonymous: `data.authType === 'anonymous' && data.userId` → rebuild guest (`auth-store.ts:116-139`).
- Cognito/OAuth: needs `data.userId`; then `getProfile()` for the rest, best-effort (`auth-store.ts:141-193`).
- Catch/`!accessToken`/`!userId` → `false` → caller runs `signInAnonymous()` (`use-session-init.ts`).

Fixing FR-002 (backend returns `user_id` + `auth_type` for OAuth) satisfies the existing frontend contract with **no frontend change required** for the core fix — a strong argument for a backend-first, low-blast-radius fix.

## R7 — Cookie scope on the deployed topology (to verify, not assume)

`_cookie_path_prefix` (`router_v2.py:150-163`) derives the Path prefix from `requestContext.stage`. For API Gateway REST with an explicit stage, the browser-visible path includes `/{stage}`; the helper matches it. If a custom domain / base-path mapping fronts the API, the stage-derived Path may not match the browser path, and the cookie would not be sent → the `router_v2.py:664` 401. This is the only cookie-side item left to confirm at runtime and is covered by FR-008 and the US1 diagnostic task.

## Decision Summary

- **Primary fix (backend, low risk)**: FR-002/FR-003 — populate `user_id`/`auth_type` in the Cognito refresh response, sourced from validated id-token claims. Unblocks persistence the moment `/refresh` returns 200.
- **Enabling diagnostic (backend, first)**: FR-007 — logging to split absent-cookie vs Cognito-reject, so the 401 cause is identified on the live deployment before touching Cognito config.
- **Config remediation (ops, gated by diagnosis)**: FR-009 — correct Cognito client/secret via CI Step 2.5 / manual update if the diagnostic shows a Cognito reject; verify against live config.
- **Cookie confirmation (verify-only unless mismatch found)**: FR-008.
- **No frontend code change expected** for the core fix; US2 verification confirms the nav/identity symptoms clear once restore succeeds.
