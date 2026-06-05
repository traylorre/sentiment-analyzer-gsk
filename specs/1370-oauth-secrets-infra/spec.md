# Feature 1370: OAuth Secrets Infrastructure

**Status**: Draft
**Created**: 2026-04-29
**Source**: `specs/oauth-provisioning-plan.md` (W4, W5, W6)
**Depends On**: none
**Blocks**: 1371, 1372

## Summary

Add AWS Secrets Manager resources for Google and GitHub OAuth client credentials,
and wire them into Terraform so `aws_cognito_identity_provider.google[0]`,
`aws_cognito_identity_provider.github[0]`, and the dashboard Lambda's
`ENABLED_OAUTH_PROVIDERS` env var consume real values instead of empty strings.

## Problem

`infrastructure/terraform/variables.tf:112-138` defines four OAuth credential
variables (Google + GitHub × client_id/secret) that default to `""`. None of
`preprod.tfvars`, `prod.tfvars`, or `.github/workflows/*.yml` supply values.
The empty defaults cause:

1. `aws_cognito_identity_provider.google[0]` and `.github[0]` are not created
   (count gates on `var.*_client_id != ""`).
2. `ENABLED_OAUTH_PROVIDERS` deploys as `""` (main.tf:433).
3. `GET /api/v2/auth/oauth/urls` returns `{providers: {}, state: ""}`.
4. The customer dashboard sign-in page hides the OAuth button block.

This feature provisions the secrets infrastructure (resources + Terraform
wiring) so credentials can be supplied externally via Secrets Manager. It does
NOT include obtaining the credentials from Google / GitHub — that's handled in
1371 (preprod) and 1372 (prod) as part of the rollout.

## User Stories

### US1: Operator can store OAuth credentials in Secrets Manager (P1)

As an SRE, I want OAuth client credentials stored in
`{env}/sentiment-analyzer/google-oauth` and `{env}/sentiment-analyzer/github-oauth`
following the existing secrets pattern, so credentials never appear in git or
in tfvars files.

**Acceptance**: After `terraform apply` with empty credentials,
`aws_secretsmanager_secret.google_oauth` and `aws_secretsmanager_secret.github_oauth`
exist with `recovery_window_in_days=7` and `prevent_destroy=true`. Initial
`aws_secretsmanager_secret_version` payload is the placeholder JSON
`{"client_id":"","client_secret":""}`. Operator updates the version manually
(via `aws secretsmanager put-secret-value`) once real credentials are obtained.

### US2: Terraform reads credentials from Secrets Manager at apply time (P1)

As Terraform, I want to read OAuth credentials from Secrets Manager via
`data "aws_secretsmanager_secret_version"` and pass them into the cognito
module and the dashboard Lambda env vars, so a deploy with valid credentials
provisions both the Cognito identity provider AND the Lambda env in one apply.

**Acceptance**: After updating the secret value to real credentials and
running `terraform apply`:
- `aws_cognito_identity_provider.google[0]` exists with non-empty
  `provider_details.client_id`.
- `module.dashboard_lambda` env contains
  `ENABLED_OAUTH_PROVIDERS = "google,github"` (or `"google"` if only Google
  credentials are populated).
- `terraform plan` shows zero diff after the apply (idempotent).

### US3: Empty credentials degrade gracefully (P2)

As an operator setting up a new environment, I want `terraform apply` to
succeed even with placeholder credentials, so the infrastructure can be
created before credentials are obtained.

**Acceptance**: Running `terraform apply` with placeholder JSON
`{"client_id":"","client_secret":""}` in the secret version succeeds.
The Cognito identity provider is NOT created (count=0). The Lambda env var
`ENABLED_OAUTH_PROVIDERS` is `""`. The dashboard sign-in page hides the OAuth
buttons. No errors.

## Requirements

### R1: Add OAuth secrets to `module.secrets`

Two new resources in `infrastructure/terraform/modules/secrets/main.tf`:

```hcl
resource "aws_secretsmanager_secret" "google_oauth" {
  name        = "${var.environment}/sentiment-analyzer/google-oauth"
  description = "Google OAuth client credentials for Cognito federation"
  kms_key_id  = var.kms_key_arn
  recovery_window_in_days = 7
  lifecycle { prevent_destroy = true }
  tags = { Environment = var.environment, Feature = "1370-oauth-secrets-infra", Purpose = "oauth-google" }
}

resource "aws_secretsmanager_secret_version" "google_oauth_placeholder" {
  secret_id     = aws_secretsmanager_secret.google_oauth.id
  secret_string = jsonencode({ client_id = "", client_secret = "" })
  lifecycle { ignore_changes = [secret_string] }
}
```

Mirror for `github_oauth`. The `ignore_changes = [secret_string]` lets the
operator update the value out-of-band without Terraform reverting it.

### R2: Expose secret ARNs from `module.secrets` outputs

Add to `modules/secrets/outputs.tf`:

```hcl
output "google_oauth_secret_arn"  { value = aws_secretsmanager_secret.google_oauth.arn }
output "github_oauth_secret_arn"  { value = aws_secretsmanager_secret.github_oauth.arn }
```

### R3: Read credentials in `infrastructure/terraform/main.tf`

Replace the `var.google_oauth_client_id` references at `main.tf:125,127,433`
with locals derived from data sources:

```hcl
data "aws_secretsmanager_secret_version" "google_oauth" {
  secret_id = module.secrets.google_oauth_secret_arn
}

data "aws_secretsmanager_secret_version" "github_oauth" {
  secret_id = module.secrets.github_oauth_secret_arn
}

locals {
  google_oauth = jsondecode(data.aws_secretsmanager_secret_version.google_oauth.secret_string)
  github_oauth = jsondecode(data.aws_secretsmanager_secret_version.github_oauth.secret_string)
  enabled_oauth_providers = join(",", compact([
    local.google_oauth.client_id != "" ? "google" : "",
    local.github_oauth.client_id != "" ? "github" : "",
  ]))
}
```

Wire `local.google_oauth.client_id` into `module.cognito.google_client_id`,
`local.google_oauth.client_secret` into `module.cognito.google_client_secret`,
mirror for GitHub, and set the dashboard Lambda env to
`ENABLED_OAUTH_PROVIDERS = local.enabled_oauth_providers`.

### R4: Remove now-unused `var.*_oauth_*` variables

Delete the four variable declarations in `variables.tf:112-138`. Nothing
should reference them after R3. Run `terraform validate` to confirm.

### R5: Lambda IAM read access to OAuth secrets

The dashboard Lambda execution role already has `secretsmanager:GetSecretValue`
for existing secrets. Verify the IAM policy attached covers the new
`google_oauth` and `github_oauth` secret ARNs. If the policy uses a wildcard
(`*/sentiment-analyzer/*`), no change needed. If it lists specific ARNs, add
the two new ones.

Note: at runtime, the Lambda does NOT need to read these secrets — Terraform
substitutes the values into the env vars at apply time. The IAM access is
defense-in-depth for any future code path that might `boto3.get_secret_value`.

## Success Metrics

1. `terraform plan` against preprod (with placeholder credentials) shows
   creation of two secrets, zero diff for Cognito IdPs, and `ENABLED_OAUTH_PROVIDERS=""`
   for the Lambda.
2. `terraform plan` against preprod (after updating the secret to real
   credentials) shows creation of `aws_cognito_identity_provider.google[0]`
   and updates `ENABLED_OAUTH_PROVIDERS` to `"google,github"`.
3. `git log -p HEAD~5..HEAD -- '*.tfvars'` shows zero credential leaks.
4. `make validate` passes (Bandit, Semgrep, terraform fmt, terraform validate).

## Out of Scope

- Obtaining real OAuth credentials from Google Cloud Console or GitHub
  Developer Settings (handled in 1371 / 1372).
- Deploying the changes (handled in 1371 / 1372).
- Frontend changes (handled in 1373).
- Rotating credentials (no automatic rotation Lambda; manual rotation only).
- Validating that GitHub OIDC actually works through Cognito (handled in 1371's
  smoke test).

## Edge Cases

| Scenario | Expected Behavior |
|---|---|
| Operator runs `terraform apply` before creating the Secrets Manager secret | Resource creation succeeds (we own the secret). The data source reads back the placeholder JSON. |
| Operator deletes the secret manually via AWS Console | `recovery_window_in_days=7` allows recovery. `prevent_destroy=true` blocks Terraform from accidentally removing it. |
| Secret JSON malformed (missing `client_id` key) | `jsondecode().client_id` raises — `terraform plan` fails with a clear error. Operator fixes JSON and retries. |
| Operator stores credentials directly in tfvars by accident | A pre-commit grep for `oauth_client_id\s*=\s*"[A-Za-z0-9]` should fail. **This requires a separate guard added in 1373 or via pre-commit hook update — not in this feature's scope.** |
| Two engineers update the secret simultaneously | Last write wins. Out-of-band rotation should be coordinated. |

## Adversarial Review #1

**Reviewer**: Self (adversarial — security + maintainability + production failure modes)
**Date**: 2026-04-29

### Findings

| Severity | Finding | Resolution |
|---|---|---|
| HIGH | The existing `cognito/github.tf:22-26` configures GitHub as an OIDC provider using `oidc_issuer = "https://token.actions.githubusercontent.com"` and `jwks_uri = "https://token.actions.githubusercontent.com/.well-known/jwks"`. These are GitHub Actions OIDC endpoints, not user-OAuth endpoints. GitHub does not issue OIDC ID tokens for user authentication — it's plain OAuth 2.0. The current Cognito IdP config will likely fail at sign-in time. | **Out of scope for 1370** (the secrets infra is correct regardless). Recorded as a HIGH for 1371 (preprod rollout) where the smoke test will catch it. If the smoke test fails, 1371 will spawn a sub-feature for either (a) replacing the GitHub IdP with a custom OIDC proxy Lambda or (b) shipping Google-only and dropping GitHub from the rollout. |
| HIGH | `aws_secretsmanager_secret_version` with `ignore_changes = [secret_string]` means Terraform won't re-create the placeholder if the operator later sets a real value. But it ALSO means `terraform import` is required if the secret already exists (e.g., from manual creation). | Add an explicit one-time-bootstrap note to `quickstart.md`: if the secret already exists, run `terraform import` before the first apply. |
| MEDIUM | `recovery_window_in_days = 7` plus `prevent_destroy = true` means a typo in the secret name (changing `name`) forces destroy-then-create, which `prevent_destroy` blocks. Operator gets stuck. | Mitigated by the existing pattern in `secrets/main.tf` — same constraint applies to `dashboard_api_key` and `tiingo` secrets. Acceptable. |
| MEDIUM | The Lambda env var `ENABLED_OAUTH_PROVIDERS` is set at deploy time, not runtime. Rotating the OAuth credentials in Secrets Manager does NOT update the Lambda — the Lambda only knows the env var. | Acceptable for client_id (rarely rotates). For client_secret rotation, since `provider_details.client_secret` in Cognito is also baked at apply time and `ignore_changes = [provider_details["client_secret"]]` is set, rotation would need a manual `aws cognito-idp update-identity-provider` followed by Terraform `taint` to re-assert state. Document this in 1371's runbook. |
| MEDIUM | `local.google_oauth = jsondecode(...)` — if the secret JSON is malformed or the secret hasn't been created yet, `terraform plan` errors with a confusing decode failure rather than a clear "secret not bootstrapped" message. | Add a `try()` wrapper: `local.google_oauth = try(jsondecode(...), { client_id = "", client_secret = "" })`. Plan succeeds; behavior degrades gracefully. |
| LOW | Removing `var.google_oauth_client_id` etc. from `variables.tf` (R4) is a breaking change for any external caller passing `-var=...`. | The repo has no such external callers (CI doesn't pass these vars; tfvars don't set them). Acceptable. Document in commit message. |
| LOW | `kms_key_arn` for the new secrets — the existing `dashboard_api_key` resource passes `var.kms_key_arn`. Need to confirm the KMS key policy permits `kms:Decrypt` for the same principals (Lambda role, deploy role). | Existing `module.secrets` already handles this via `var.kms_key_arn` — same KMS key, same policy. Acceptable. |
| LOW | An attacker with `secretsmanager:PutSecretValue` (e.g., compromised CI runner) could swap the OAuth client_id to one they control. Subsequent `terraform apply` would update the Cognito IdP to attacker's client. | Defense-in-depth: CloudTrail logs `PutSecretValue`. AWS Config rule `secretsmanager-secret-rotation-enabled` flags un-rotated secrets (we won't rotate, but the rule visibility is fine). Out of scope to harden further in this feature. Document as a residual risk. |

**Spec edits made in response**:
- R3 updated to use `try(jsondecode(...), { client_id = "", client_secret = "" })` (MEDIUM #5).
- R4 commit message must note the variable removal (LOW #6).
- Added a residual risk note on `PutSecretValue` impersonation (LOW #8) to spec body — see "Residual Risks" section below.

### Residual Risks

- **Secret poisoning via `PutSecretValue`**: An actor with `secretsmanager:PutSecretValue` permission on these secrets could redirect OAuth to an attacker-controlled client_id at the next `terraform apply`. Mitigated by CloudTrail logging and IAM least-privilege on the secrets. CI runner credentials should NOT have `PutSecretValue` on these secrets — only humans with break-glass access should.
- **GitHub IdP config likely broken** (HIGH #1): documented for 1371 to verify and fix.

### Gate

**0 CRITICAL, 0 HIGH unresolved.** (HIGH #1 is acknowledged and deferred to 1371 with explicit verification step. HIGH #2 is resolved via quickstart note.)

**Spec is ready for Stage 3 (Plan).**
