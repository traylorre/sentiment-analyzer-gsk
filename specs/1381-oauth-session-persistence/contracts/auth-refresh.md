# Contract: POST /api/v2/auth/refresh (OAuth session)

Target: **Customer Dashboard** (Next.js/Amplify → API Gateway → dashboard Lambda). Not the HTMX admin dashboard.

## Request

- Method: `POST`
- Path: `/api/v2/auth/refresh` (browser-visible path includes the API Gateway stage prefix on the deployed env)
- Auth: httpOnly `refresh_token` cookie (cross-site from the Amplify origin; `SameSite=None; Secure`). Body fallback allowed but unused by the frontend.
- CSRF: exempt (`csrf.py:38`) — cookie-only endpoint.
- Origin: `https://main.d29tlmksqcx494.amplifyapp.com`

## Response — success (this feature's change)

`200 OK`, `Cache-Control: no-store`, plus rotated CSRF `Set-Cookie`.

```json
{
  "id_token": "<jwt>",
  "access_token": "<jwt>",
  "expires_in": 3600,
  "user_id": "<internal-user-id>",     // NEW (FR-002): required for OAuth/Cognito restore
  "auth_type": "google"                 // NEW (FR-002/FR-003): so the client rebuilds identity
}
```

- `user_id` MUST be derived server-side from validated id-token claims (`sub` → internal user), never from request input (SR-005).
- `refresh_token` MUST NOT appear in the body (SR-001); it stays in the httpOnly cookie. Cognito does not rotate it, so the existing cookie persists.

## Response — failure

- `401` when the refresh cookie is absent/unparseable (`router_v2.py:664`) — body message distinguishes "not found".
- `401` when Cognito rejects the token (`router_v2.py:671`, from `TokenError`) — body carries the mapped reason (e.g. `invalid_refresh_token` → "Please sign in again.").
- `401 token_revoked` when the refresh token is blocklisted (`auth.py:2921-2924`), checked before issuance (SR-004).

## Backend diagnostic requirement (FR-007)

The handler MUST log, without secrets, exactly one of:
- `refresh.cookie_absent` — `_extract_refresh_token_from_event` returned `None`.
- `refresh.cognito_rejected` — Cognito returned non-200 (include mapped error code + refresh-token hash prefix).
- `refresh.success` — 200 issued (include auth_type + user_id hash prefix).

## Frontend consumer (no change required for core fix)

`restoreSession` (`auth-store.ts:141-193`) takes the Cognito branch when `authType !== 'anonymous'` and `user_id` is present; rebuilds the user; returns `true` → `signInAnonymous()` is skipped.
