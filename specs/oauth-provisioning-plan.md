# Plan: OAuth Provisioning (preprod + prod)

## Goal

Make the Google and GitHub OAuth buttons functional on the customer dashboard
sign-in page in preprod and prod. They are currently hidden because
`ENABLED_OAUTH_PROVIDERS` deploys as the empty string (root cause traced below).

## Root Cause Recap

1. `infrastructure/terraform/variables.tf:112-138` — `google_oauth_client_id`,
   `google_oauth_client_secret`, `github_oauth_client_id`,
   `github_oauth_client_secret` all default to `""` and are `sensitive`.
2. `infrastructure/terraform/preprod.tfvars` and `prod.tfvars` — neither file
   sets these vars.
3. No GitHub Actions workflow injects `TF_VAR_*` for these vars at deploy.
4. `infrastructure/terraform/main.tf:433` —
   `ENABLED_OAUTH_PROVIDERS = join(",", compact([... ? "google" : "", ... ? "github" : ""]))`
   resolves to `""` when both client IDs are empty.
5. `src/lambdas/dashboard/auth.py:2046-2050` — empty env var returns
   `OAuthURLsResponse(providers={}, state="")`.
6. `frontend/src/app/auth/signin/page.tsx:69` — gates the entire
   `<OAuthButtons>` block on `hasOAuthProviders`, which is false.
7. `infrastructure/terraform/modules/cognito/{google,github}.tf:9-11` —
   `aws_cognito_identity_provider` resources are gated `count = ... != "" ? 1 : 0`,
   so Cognito isn't aware of Google/GitHub either.

So both the render path (no env var → no providers in API → no button) and the
Cognito path (no identity provider resource created) fail at the same upstream
input. Provisioning credentials lights up both at once.

## Work Items

### W1. Provision Google OAuth client (preprod)

- Create OAuth 2.0 Client ID in Google Cloud Console under a dedicated
  "sentiment-preprod" project.
- Authorized redirect URI: the preprod Cognito user pool domain's
  `/oauth2/idpresponse` (Cognito format, not the Amplify URL).
- Capture `client_id` and `client_secret`.

### W2. Provision Google OAuth client (prod)

Same as W1 but separate Google Cloud project ("sentiment-prod") and separate
client. Keeping the two environments on distinct credentials matters for
revocation blast radius and audit trails.

### W3. Provision GitHub OAuth app (preprod + prod)

- Two OAuth Apps in GitHub Developer Settings, one per environment.
- Authorization callback URL: same `/oauth2/idpresponse` pattern on the
  matching Cognito domain.
- Capture both client IDs and secrets.

### W4. Decide credential storage strategy

Two options. The repo already uses AWS Secrets Manager for `newsapi` and
`dashboard-api-key`, so the precedent is set, but each option has a tradeoff:

| Option | Pro | Con |
|---|---|---|
| AWS Secrets Manager + Terraform `data` source | Matches existing pattern, secret rotation visible in AWS, no GHA write access required | Adds a `data.aws_secretsmanager_secret_version` block per credential, slight Terraform complexity |
| GitHub Actions secrets exported as `TF_VAR_*` env in deploy job | Simpler Terraform (no data block), credential never touches AWS until apply | Secret lives in two places (GHA + AWS post-apply), rotation requires updating GHA secret |

Default recommendation: AWS Secrets Manager, to stay consistent with the
existing `module.secrets` pattern.

### W5. Store credentials in Secrets Manager

Four secrets, one per credential per env:

- `preprod/sentiment-analyzer/google-oauth` (JSON: `{"client_id":..., "client_secret":...}`)
- `preprod/sentiment-analyzer/github-oauth`
- `prod/sentiment-analyzer/google-oauth`
- `prod/sentiment-analyzer/github-oauth`

Create via AWS CLI initially (manual one-time bootstrap), then `terraform import`
into the secrets module so subsequent applies don't recreate them.

### W6. Wire secrets into Terraform variables

- Add `data "aws_secretsmanager_secret_version"` blocks for each credential.
- Wire `local.google_oauth_client_id = jsondecode(...).client_id`, etc.
- Replace `var.google_oauth_client_id` references at `main.tf:125,127,433` with
  the locals.

Trade-off here: dropping the `var.*` indirection makes the deploy
self-contained (no caller needs to pass `-var=...`) but couples the Terraform
to AWS Secrets Manager. That's fine for this repo — local dev already mocks
this path via spec 1323.

### W7. Deploy preprod

- `terraform apply` with `-var-file=preprod.tfvars`.
- Verify the deployed dashboard Lambda env var:
  `aws lambda get-function-configuration --function-name preprod-dashboard --query 'Environment.Variables.ENABLED_OAUTH_PROVIDERS'`
- Verify Cognito IDPs:
  `aws cognito-idp list-identity-providers --user-pool-id <preprod-pool>`

### W8. Smoke test the API

- `curl -i https://<preprod-api-gw>/api/v2/auth/oauth/urls`
- Expected: 200 with `providers.google.authorize_url` and
  `providers.github.authorize_url` populated.

### W9. End-to-end browser test on preprod

- Visit `https://main.d29tlmksqcx494.amplifyapp.com/auth/signin`.
- Verify "Continue with Google" and "Continue with GitHub" buttons render
  above the email form.
- Click Google, complete the consent flow, land on `/auth/callback`, confirm
  session is created (Zustand `useAuthStore` shows `user.email`,
  `useAuth().isAuthenticated === true`).
- Repeat for GitHub.

### W10. Deploy prod (gated on W9 passing)

Same as W7-W9 but with `prod.tfvars` and the prod Cognito + Google + GitHub
credentials.

### W11. Frontend error visibility hardening

The silent `catch` at `frontend/src/app/auth/signin/page.tsx:25-29` collapses
"backend errored", "no providers configured", and "CORS blocked the request"
into the same UI state. After provisioning works, add:

- `console.error('OAuth providers fetch failed:', err)` inside the catch.
- Optional: surface a small "Sign in with email" hint when the catch fires
  (distinct from the case where providers really are configured to be off).

This is genuinely separate work from provisioning, but the audit found it as a
contributing factor and it should ride along.

### W12. Reconcile with existing OAuth specs

- `specs/1323-oauth-buttons-local-dev/` covers local dev. After provisioning
  works, decide whether to land 1323 (mock values for local) or whether to
  point local at a real Google "sentiment-local" client. Mock values are
  faster; real client is more honest.
- `specs/1331-auth-oauth-fixes/` is 9 Playwright test fixes. Some assertions
  (B1-B4) can land independently. The OAuth-flow test (A5/A5b) needs the
  `/urls` mock that's only shaped correctly once we know the real response
  format from W8.

## Out of Scope

- Adding new OAuth providers beyond Google and GitHub.
- Changing the Cognito user pool's federation behavior, account linking
  rules, or token lifetimes.
- OAuth scope changes (currently `openid email profile`).
- Local-dev OAuth (covered by 1323).
- Test fixes (covered by 1331).

## Constraints

- No client secrets in git, ever. tfvars stays clean of credentials.
- Preprod and prod must use distinct OAuth clients (separate Google projects,
  separate GitHub apps).
- Cognito redirect URI registered with Google/GitHub must exactly match what
  the Cognito user pool domain expects (`https://<domain>.auth.<region>.amazoncognito.com/oauth2/idpresponse`).
- All commits GPG-signed (per `CLAUDE.md` git policy).

## Acceptance Criteria

1. `curl https://<preprod-api-gw>/api/v2/auth/oauth/urls` returns 200 with
   both providers populated.
2. `curl https://<prod-api-gw>/api/v2/auth/oauth/urls` returns 200 with both
   providers populated.
3. Google sign-in completes end-to-end on preprod, creating a session.
4. GitHub sign-in completes end-to-end on preprod, creating a session.
5. Same for prod.
6. No client secrets appear in git history.
7. `terraform plan` shows no diff after a fresh apply (idempotent).
