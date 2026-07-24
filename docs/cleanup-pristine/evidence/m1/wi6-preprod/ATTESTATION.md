# M1 WI-6 — Google OAuth Enablement: Go-Live Attestation (preprod)

**Date:** 2026-07-24 · **Environment:** preprod (AWS account 218795110243)
**Scope of this attestation:** OAuth *enablement* + a real Google login completing end-to-end.
Honest boundary: this is a **go-live functional attestation**, NOT the full `auth-oauth-01..05`
instrumented-harness attestation. Rows 04/05 (session persistence / restore) are deferred — see
"Known gaps" below — because a real post-login defect (`/auth/refresh` 401) prevents the OAuth
session from persisting across reload. That defect and four others are tracked for follow-up.

## What is live and verified (reproducible)

Infra checks via `./scripts/verify-oauth-deploy.sh preprod` (captured in
`verify-oauth-deploy.txt`, all PASS):

- Lambda `preprod-sentiment-dashboard` env `ENABLED_OAUTH_PROVIDERS=google`
- Cognito user pool `us-east-1_9wiDkddRF` identity providers: `["Google"]`
- Dashboard app client `2jhl4evlv0qk8cf05jiugj9bb6` supported IdPs: `["COGNITO","Google"]`
- `GET /api/v2/auth/oauth/urls` → 200 with the Google provider (Cognito authorize URL, PKCE
  `code_challenge` + `state`, `identity_provider=Google`)
- Live dashboard Lambda `live` alias → version 110

Independently queryable via the AWS APIs above at attestation time.

## Human-witnessed login (row 01–03 equivalent)

The repository owner completed a **real Google OAuth sign-in** on the customer frontend
`https://main.d29tlmksqcx494.amplifyapp.com` in a clean private-browsing context, using their own
Google account as the federated test user. Observed: the "Continue with Google" button rendered,
the Google consent flow completed, Cognito redirected to the Amplify `/auth/callback` with a valid
authorization `code` + `state`, the backend exchanged the code for tokens
(`POST /api/v2/auth/oauth/callback` → 200), and the app displayed the signed-in identity
("Signed in via Google"). No "Invalid state" / CSRF error occurred.

No screenshots, tokens, authorization codes, or email addresses are sealed here (FR-9). The federated
account email is the owner's own; it is referenced only as "the owner's Google test account".

## Fixes that made this work (all on main unless noted)

- **PR #935** — deployer IAM: `cognito-idp:CreateIdentityProvider` was tag-gated (unenforceable at
  create) → moved IdP write actions to the unconditional statement; preempted the
  `cognito-identity:CreateIdentityPool` twin.
- **PR #936** — CI dashboard-deploy Step 2.5 syncs the Lambda `ENABLED_OAUTH_PROVIDERS` env from a
  new terraform output (terraform cannot manage it: `modules/lambda` `ignore_changes=[environment]`).
- **PR #937** — `verify-oauth-deploy.sh` used the wrong function name (`{env}-dashboard` →
  `{env}-sentiment-dashboard`), producing a false FAIL.
- **PR #938** — `useSessionInit` (root-layout `SessionProvider`) cleared the callback's
  `oauth_provider`/`oauth_state` sessionStorage on every page → every OAuth sign-in failed
  "session expired". Guarded to skip `/auth/callback`. (Documented Feature-1363 production fix.)
- **Live env sets** (out-of-band; `ignore_changes=[environment]` makes them persist, pending the
  tfvars/CI durability follow-up): `FRONTEND_URL` and `COGNITO_REDIRECT_URI` set to the Amplify
  callback so the authorize and token-exchange `redirect_uri` match (fixed `unauthorized_client`).

## Known gaps (tracked; NOT part of this go-live seal)

1. Google `picture` claim not shown in the UserMenu (no avatar).
2. Settings page shows "Anonymous/Guest" while the nav shows the signed-in Google user.
3. Left-nav becomes unresponsive after entering Settings.
4. `POST /auth/refresh` returns 401 for the OAuth session → session-init falls back to guest.
   **Root cause of #2/#3; OAuth session does not persist across reload.**
5. API Gateway CORS preflight omits `PATCH` (`modules/api_gateway/main.tf:628`) → "Save Changes"
   (notification preferences) blocked for all users.

Row 04/05 harness attestation to be produced after #4 is fixed and the OAuth session persists.

## Basis of attestation

Infra state is script-reproducible and independently queryable; the login was human-witnessed by
the owner. This seal records the go-live as functionally complete and honestly scopes the remaining
post-login auth hardening as open follow-up work.
