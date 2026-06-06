# Feature 1371: Preprod OAuth Rollout + Verification

**Status**: Draft
**Created**: 2026-04-29
**Source**: `specs/oauth-provisioning-plan.md` (W1, W3-preprod, W7, W8, W9)
**Depends On**: 1370 (must be merged + applied to preprod)
**Blocks**: 1372 (prod gated on this passing in browser), 1374

## Summary

Provision Google and GitHub OAuth credentials for the preprod environment,
populate the Secrets Manager values created by 1370, deploy via Terraform,
and verify end-to-end that:

1. The dashboard Lambda env contains `ENABLED_OAUTH_PROVIDERS=google,github`
   (or `google` only if GitHub federation proves broken — see AR#1).
2. `GET /api/v2/auth/oauth/urls` returns populated providers.
3. The customer dashboard sign-in page renders the OAuth buttons.
4. Clicking "Continue with Google" completes the full flow and creates a
   session.
5. Clicking "Continue with GitHub" either completes the flow OR fails in a
   diagnosable way (per the GitHub OIDC concern raised in 1370 AR#1).

## Problem

After 1370 ships, the secrets infrastructure exists but the secret values
are placeholder JSON (`{client_id:"", client_secret:""}`). No OAuth credentials
have been obtained from Google Cloud Console or GitHub Developer Settings.
Without this rollout, OAuth remains hidden on the live preprod site.

## User Stories

### US1: Operator obtains preprod Google OAuth credentials (P1)

As an SRE, I want a documented procedure for creating a Google Cloud project
"sentiment-preprod" with an OAuth 2.0 Client ID configured for the preprod
Cognito user pool, so I can populate the Secrets Manager value.

**Acceptance**: Procedure documented in `quickstart.md`. After completion,
the secret `preprod/sentiment-analyzer/google-oauth` contains a real
`client_id` and `client_secret` from Google. The Google client lists the
preprod Cognito user pool's `/oauth2/idpresponse` URL as an authorized
redirect URI.

### US2: Operator obtains preprod GitHub OAuth credentials (P1)

Same as US1 but for GitHub. Creates an OAuth App in GitHub Developer Settings
named "sentiment-analyzer-preprod" with the same Cognito callback URL.

**Acceptance**: Secret `preprod/sentiment-analyzer/github-oauth` populated
with real values. GitHub OAuth App's "Authorization callback URL" matches
the Cognito IdP response URL.

### US3: Terraform apply provisions Cognito IdPs and Lambda env (P1)

As Terraform, I want a `terraform apply -var-file=preprod.tfvars` against
the preprod state to create the Google and GitHub Cognito identity providers
and update the dashboard Lambda env in one operation.

**Acceptance**: After apply:
- `aws cognito-idp list-identity-providers --user-pool-id <preprod-pool>`
  shows Google (and GitHub, if not blocked by AR#1).
- `aws lambda get-function-configuration --function-name preprod-dashboard
  --query 'Environment.Variables.ENABLED_OAUTH_PROVIDERS'` returns
  `"google,github"` (or `"google"` if GitHub deferred).
- `terraform plan` shows zero diff after apply.

### US4: API smoke test confirms `/urls` returns providers (P1)

As CI / a QA engineer, I want `curl https://<preprod-api-gw>/api/v2/auth/oauth/urls`
to return 200 with both providers populated.

**Acceptance**: Response body contains `providers.google.authorize_url`
matching `https://<preprod-cognito-domain>.auth.us-east-1.amazoncognito.com/oauth2/authorize?...`.
Same for github (or absent if GitHub deferred). State value is non-empty.

### US5: Browser end-to-end Google sign-in (P1)

As a user visiting the preprod customer dashboard, I want to click "Continue
with Google", complete Google's consent screen, return to `/auth/callback`,
and be signed in.

**Acceptance**: A test Google account completes the flow end-to-end. The
post-callback page redirects to `/dashboard`. The Zustand auth store has
`user.email` populated. A subsequent API call (e.g.,
`GET /api/v2/configurations`) returns 200 with a valid Cognito token.

### US6: Browser end-to-end GitHub sign-in OR documented failure (P1)

As a user, I want "Continue with GitHub" to either work end-to-end OR fail
with a clear, diagnosable error that justifies a follow-up feature.

**Acceptance**: One of:
- (a) Successful sign-in mirroring US5.
- (b) Documented failure mode (HTTP error, Cognito error, OIDC parse
  error) with a captured trace, plus a follow-up issue created (1375 or
  similar) tracking the GitHub OIDC fix.

## Requirements

### R1: Google Cloud bootstrap procedure

Document in `quickstart.md`:

1. Create a Google Cloud project "sentiment-preprod" (or reuse an existing
   sandbox project — operator's call; document the choice in the secret tags).
2. Enable the "Google Identity" API (sometimes labeled "OAuth 2.0 API").
3. Configure OAuth consent screen (External, branding fields).
4. Create OAuth 2.0 Client ID:
   - Application type: Web application.
   - Name: `sentiment-analyzer-preprod`.
   - Authorized JavaScript origins: `https://<preprod-cognito-domain>.auth.us-east-1.amazoncognito.com`.
   - Authorized redirect URIs:
     `https://<preprod-cognito-domain>.auth.us-east-1.amazoncognito.com/oauth2/idpresponse`.
5. Download the JSON. Capture `client_id` and `client_secret`.
6. Store in Secrets Manager:
   ```
   aws secretsmanager put-secret-value \
     --secret-id preprod/sentiment-analyzer/google-oauth \
     --secret-string '{"client_id":"<from-google>","client_secret":"<from-google>"}'
   ```

### R2: GitHub bootstrap procedure

Document the parallel procedure for GitHub:

1. GitHub → Settings → Developer settings → OAuth Apps → New OAuth App.
2. Application name: `sentiment-analyzer-preprod`.
3. Homepage URL: `https://main.d29tlmksqcx494.amplifyapp.com` (preprod
   Amplify URL).
4. Authorization callback URL:
   `https://<preprod-cognito-domain>.auth.us-east-1.amazoncognito.com/oauth2/idpresponse`.
5. Capture client ID. Generate client secret. Capture immediately (GitHub
   shows once).
6. Store in Secrets Manager (same shape).

### R3: Apply Terraform to preprod

```bash
cd infrastructure/terraform
terraform init
terraform plan -var-file=preprod.tfvars -out=preprod.plan
# Review plan: 1 IdP added (Google), 1 IdP added (GitHub),
# Lambda env var ENABLED_OAUTH_PROVIDERS updated to "google,github".
terraform apply preprod.plan
```

### R4: Post-deploy verification (automated)

A script `scripts/verify-oauth-deploy.sh` (new) that, given an env name:

1. Reads the Lambda env via AWS CLI; assert `ENABLED_OAUTH_PROVIDERS` is
   non-empty.
2. Reads the Cognito user pool's IdPs; assert Google (and GitHub) exist.
3. Curls `https://<api-gw>/api/v2/auth/oauth/urls`; assert 200 + non-empty
   `providers`.
4. Exits 0 on all green, non-zero on any failure.

This is run manually post-apply for now. CI integration deferred to a
later feature.

### R5: Manual end-to-end browser test

Document a test plan executed by a human:

1. Open Chrome incognito, navigate to
   `https://main.d29tlmksqcx494.amplifyapp.com/auth/signin`.
2. Verify "Continue with Google" and "Continue with GitHub" buttons render.
3. Click Google. Complete consent with a test account.
4. Verify redirect to `/auth/callback` then `/dashboard`. Verify the user
   menu shows the email.
5. Sign out. Repeat with GitHub.
6. If GitHub fails: capture network tab + Cognito errors + console output.
   Open issue/feature for follow-up.

### R6: Decide on GitHub deferral if smoke fails

If the GitHub OIDC config in `cognito/github.tf:22-26` is broken (as flagged
in 1370 AR#1), the deploy may succeed but the click-through fails:

- Cognito redirects to GitHub.
- GitHub OAuth completes, redirects back to Cognito's
  `/oauth2/idpresponse`.
- Cognito tries to validate the OIDC ID token; GitHub doesn't issue one
  (they only do OAuth 2.0, not OIDC).
- User sees a Cognito error page.

If this happens, this feature ships **Google only**:

- Set `github_oauth` Secrets Manager value to placeholder
  `{client_id: "", client_secret: ""}`.
- This automatically removes GitHub from `ENABLED_OAUTH_PROVIDERS` and
  removes the `aws_cognito_identity_provider.github` resource on next
  apply.
- Open a follow-up feature to add a GitHub-specific federation path
  (custom OIDC proxy Lambda, or a non-Cognito GitHub OAuth flow).

## Success Metrics

1. `aws secretsmanager get-secret-value --secret-id preprod/sentiment-analyzer/google-oauth`
   returns real (non-placeholder) credentials.
2. `terraform plan -var-file=preprod.tfvars` shows zero diff after apply.
3. `scripts/verify-oauth-deploy.sh preprod` exits 0.
4. A real user can sign in with Google end-to-end on the preprod Amplify
   URL within 60 seconds of clicking the button (consent + redirect +
   session creation).
5. Either: GitHub works the same way, OR the GitHub failure is documented
   with a follow-up issue.

## Out of Scope

- Production environment (handled in 1372).
- Local dev (handled in 1323).
- Frontend error visibility (handled in 1373).
- Reconciliation with E2E test specs (handled in 1374).
- Building a custom OIDC proxy for GitHub (deferred to a separate feature
  if R6 is triggered).
- Documentation of the OAuth flow for end users (separate concern).

## Edge Cases

| Scenario | Expected Behavior |
|---|---|
| Operator sets only Google credentials | `ENABLED_OAUTH_PROVIDERS=google`. Only Google IdP created. Sign-in page shows only Google button. Acceptable. |
| Operator typos client_id JSON shape | `terraform plan` errors on `jsondecode` (handled by `try()` in 1370 — degrades to empty). Operator notices buttons missing, fixes JSON. |
| Google Cloud project's OAuth consent screen is in "Testing" mode (not "In Production") | Only allow-listed test accounts can sign in. Acceptable for preprod. Document in quickstart. |
| Cognito rejects the JWT from Google due to missing claim mapping | `attribute_mapping` in `cognito/google.tf` already covers `email` and `username`. Acceptable. |
| User signs in once, signs out, signs in again | Cognito creates the user on first sign-in; subsequent sign-ins find existing user via email match (per Feature 1182 email-to-OAuth linking). |
| User has same email in Google AND GitHub | Federation linking (Feature 1181) auto-links. Document this as a known behavior. |
| Cognito user pool's `/oauth2/idpresponse` URL changes (e.g., domain rename) | Operator must update Google + GitHub redirect URI. Document in quickstart. |
| Secret value contains trailing newline (common with shell heredocs) | `jsondecode` is whitespace-tolerant; `client_id` strings won't include the newline. Acceptable. |
| AWS Secrets Manager key rotation in flight during apply | KMS auto-handles this. Acceptable. |

## Adversarial Review #1

**Reviewer**: Self (adversarial — security, ops failure modes, real-world bugs)
**Date**: 2026-04-29

### Findings

| Severity | Finding | Resolution |
|---|---|---|
| HIGH | The Google Cloud consent screen in "Testing" mode (default for new projects) limits sign-ins to allow-listed test accounts. If the operator forgets to either move to "In Production" or add the test users, real users on preprod hit "Access blocked: This app is not verified." | Document explicitly in R1. Strongly recommend Testing mode for preprod (not Production), since preprod isn't externally trusted. List the test accounts in the runbook. |
| HIGH | The GitHub OIDC config in `cognito/github.tf` uses GitHub Actions OIDC endpoints, not user OAuth endpoints. Sign-in will fail at the Cognito → GitHub OIDC validation step. | Acknowledged via R6. If smoke test fails, ship Google only. Open follow-up for GitHub fix. |
| HIGH | Operator runs the wrong AWS profile / region during `aws secretsmanager put-secret-value`, populates prod with preprod credentials (or vice versa). | Mitigation: include `--region us-east-1 --profile sentiment-preprod` (or whatever profile naming the team uses) explicitly in every CLI snippet. Recommend `AWS_PROFILE=...` env var prefix. Add a guard at the top of `scripts/verify-oauth-deploy.sh` that confirms the AWS account ID matches the expected env. |
| HIGH | Real OAuth client_secret pasted into a terminal can leak into shell history. Operators may also paste into Slack/email by accident. | Document the use of `aws secretsmanager put-secret-value --secret-string fileb://creds.json` reading from a file (which can be `shred`-deleted after) instead of inline. Recommend creating the secrets via AWS Console UI for the most sensitive cases. |
| HIGH | A misconfigured Cognito `attribute_mapping` could result in the user's email not propagating to the JWT, breaking Feature 1182 (email-to-OAuth linking). The existing `cognito/google.tf:23-24` maps `email = "email"` and `username = "sub"`. Confirmed correct. | Resolved (existing config is correct). Add a verification step to R5: post-sign-in, decode the Cognito ID token and confirm `email` claim is present. |
| MEDIUM | Anyone with `cognito-idp:UpdateIdentityProvider` could rotate the client_secret out-of-band, breaking Cognito → IdP exchange silently. | CloudTrail logs the action. Out of scope to harden further. Document in residual risks. |
| MEDIUM | Google's OAuth quotas (default ~10k tokens/day for non-verified apps) could be exceeded during load testing. | preprod traffic should be far below this. Document the limit. |
| MEDIUM | A user signing in with Google when their email is already a magic-link user creates an account-linking question. Feature 1182 supposedly handles this. Verification needed: does it actually merge? | Add to R5: a test where the Google account email matches an existing magic-link account; verify post-sign-in user state. |
| MEDIUM | If the Lambda is redeployed mid-flow, a user's in-progress OAuth state token (DynamoDB-stored) could become orphaned. The state validation logic should reject expired/missing states cleanly. | Existing state validation (Feature 1185) handles this. Acceptable. |
| LOW | The runbook captures procedure as documented, but if Google changes its UI, the screenshots/labels may drift. | Use stable selectors ("OAuth 2.0 Client IDs", "Authorized redirect URIs"). Don't include screenshots — text is durable. |
| LOW | `scripts/verify-oauth-deploy.sh` is bash. Bash scripts in CI can hide errors via subshell exit codes. | Use `set -euo pipefail` at top. Verify in code review. |
| LOW | The runbook says "Chrome incognito" — Safari users may see different consent flows. | Pick one browser for the canonical test. Chrome is fine. Document why. |

### Spec edits made in response

- **R1 updated** to recommend Testing mode + test account allowlist (HIGH #1).
- **R3 updated** with explicit `--profile` and `--region` in the CLI snippet (HIGH #3).
- **R1, R2 updated** to use `--secret-string fileb://creds.json` pattern with `shred` (HIGH #4).
- **R5 updated** with a "decode the Cognito ID token" step (HIGH #5).
- **R5 updated** with a "duplicate-email account-linking" test (MEDIUM #4).

### Residual Risks

- GitHub OIDC sign-in will likely fail (HIGH #2). R6 governs the fallback.
- An attacker with `cognito-idp:UpdateIdentityProvider` can hijack the IdP
  config (MEDIUM #1). CloudTrail-only mitigation.
- Google's "Access blocked" page (Testing mode, account not allow-listed)
  could confuse users. Acceptable for preprod.

### Gate

**0 CRITICAL, 0 HIGH unresolved.**
HIGH #1 (Testing mode), #2 (GitHub OIDC), #3 (wrong-env apply), #4 (secret in
shell history), #5 (attribute_mapping verification) all addressed in spec
edits or R6 fallback.

**Spec is ready for Stage 3 (Plan).**
