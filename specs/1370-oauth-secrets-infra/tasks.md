# Tasks: Feature 1370 — OAuth Secrets Infrastructure

**Plan**: [plan.md](plan.md)
**Spec**: [spec.md](spec.md)

## Phase 1: Secrets Module Resources

- [ ] **T1**: Add `aws_secretsmanager_secret.google_oauth` resource to
  `modules/secrets/main.tf`. Mirror the existing `dashboard_api_key` shape
  (KMS, recovery_window=7, prevent_destroy=true).
  - **File**: `infrastructure/terraform/modules/secrets/main.tf`
  - **Maps to**: spec R1
  - **Deps**: none

- [ ] **T2**: Add `aws_secretsmanager_secret_version.google_oauth_placeholder`
  with `secret_string = jsonencode({client_id="", client_secret=""})` and
  `lifecycle { ignore_changes = [secret_string] }`.
  - **File**: `infrastructure/terraform/modules/secrets/main.tf`
  - **Maps to**: spec R1, plan AD3
  - **Deps**: T1

- [ ] **T3**: Mirror T1 + T2 for `github_oauth`.
  - **File**: `infrastructure/terraform/modules/secrets/main.tf`
  - **Maps to**: spec R1
  - **Deps**: none (parallelizable with T1+T2)

- [ ] **T4**: Add outputs `google_oauth_secret_arn` and `github_oauth_secret_arn`
  to `modules/secrets/outputs.tf`.
  - **File**: `infrastructure/terraform/modules/secrets/outputs.tf`
  - **Maps to**: spec R2
  - **Deps**: T1, T3

## Phase 2: main.tf Wiring

- [ ] **T5**: Add `data "aws_secretsmanager_secret_version"` blocks for both
  OAuth secrets in `main.tf`.
  - **File**: `infrastructure/terraform/main.tf`
  - **Maps to**: spec R3
  - **Deps**: T4

- [ ] **T6**: Add `locals { google_oauth, github_oauth, enabled_oauth_providers }`
  using `try(jsondecode(...), {client_id="", client_secret=""})`.
  - **File**: `infrastructure/terraform/main.tf`
  - **Maps to**: spec R3, AR#1 MEDIUM #5
  - **Deps**: T5

- [ ] **T7**: Replace `var.google_oauth_client_id` with `local.google_oauth.client_id`
  at `main.tf:125`. Mirror for `var.google_oauth_client_secret` (line ~126),
  `var.github_oauth_client_id` (line 127), `var.github_oauth_client_secret`
  (~128).
  - **File**: `infrastructure/terraform/main.tf`
  - **Maps to**: spec R3
  - **Deps**: T6

- [ ] **T8**: Replace `ENABLED_OAUTH_PROVIDERS = join(",", compact([...]))`
  at `main.tf:433` with `ENABLED_OAUTH_PROVIDERS = local.enabled_oauth_providers`.
  - **File**: `infrastructure/terraform/main.tf`
  - **Maps to**: spec R3
  - **Deps**: T6

## Phase 3: Variable Cleanup

- [ ] **T9**: Delete the 4 `variable "*_oauth_*"` blocks at
  `variables.tf:112-138`.
  - **File**: `infrastructure/terraform/variables.tf`
  - **Maps to**: spec R4
  - **Deps**: T7, T8 (must remove references first)

- [ ] **T10**: Run `grep -rn "google_oauth_client_id\|github_oauth_client_id" infrastructure/`.
  Expect zero matches. If non-zero, address before continuing.
  - **Verification gate**, no file change
  - **Maps to**: plan C4
  - **Deps**: T9

## Phase 4: IAM Verification

- [ ] **T11**: Read `modules/lambda/iam.tf` (or wherever the dashboard
  Lambda's `secretsmanager:GetSecretValue` policy is defined). Confirm it
  uses a wildcard ARN (`arn:aws:secretsmanager:*:*:secret:${var.environment}/sentiment-analyzer/*`)
  or similar pattern that covers the new secrets.
  - **File**: read-only
  - **Maps to**: spec R5, plan C1
  - **Deps**: none (parallelizable)

- [ ] **T12**: (CONDITIONAL on T11) If the IAM policy lists specific ARNs,
  add the two new OAuth secret ARNs.
  - **File**: `modules/lambda/iam.tf` (or similar)
  - **Maps to**: spec R5
  - **Deps**: T11

## Phase 5: Validation

- [ ] **T13**: Run `cd infrastructure/terraform && terraform fmt -recursive`.
  - Verify zero diff (or apply formatting).
  - **Deps**: T1-T12

- [ ] **T14**: Run `cd infrastructure/terraform && terraform validate`.
  - Must pass.
  - **Deps**: T13

- [ ] **T15**: Run `terraform init` and `terraform plan -var-file=preprod.tfvars`
  against preprod state.
  - Expected diff: 2 secrets created, 2 secret versions created. IdPs
    unchanged (still count=0). Lambda env unchanged (still empty
    `ENABLED_OAUTH_PROVIDERS`). 4 vars removed from state.
  - **Deps**: T14

- [ ] **T16**: Run `make validate` (Bandit, Semgrep, ruff, terraform fmt +
  validate combined).
  - Must pass.
  - **Deps**: T13

## Phase 6: Quickstart + PR

- [ ] **T17**: Write `specs/1370-oauth-secrets-infra/quickstart.md`. Include:
  - One-time bootstrap steps (per env): `terraform import` if secret already
    exists; `aws secretsmanager put-secret-value --secret-id
    {env}/sentiment-analyzer/google-oauth --secret-string '{"client_id":"...","client_secret":"..."}'`
    once real credentials are in hand.
  - Manual rotation procedure (no rotation Lambda).
  - **File**: `specs/1370-oauth-secrets-infra/quickstart.md`
  - **Deps**: T1-T16

- [ ] **T18**: Open PR with title `feat(1370): OAuth secrets infrastructure`.
  Body includes the dependency graph (this PR blocks 1371, 1372). Tag the
  HIGH AR#1 finding about GitHub OIDC config in the PR description so reviewers
  know it's a known issue handled in 1371.
  - GPG-signed commits.
  - **Deps**: T17

## Adversarial Review #3

**Reviewer**: Self (implementation readiness, risk assessment)
**Date**: 2026-04-29

### Coverage check

| Requirement | Mapped Tasks |
|---|---|
| R1 (secrets resources) | T1, T2, T3 |
| R2 (outputs) | T4 |
| R3 (main.tf wiring + try wrapper) | T5, T6, T7, T8 |
| R4 (variable cleanup) | T9, T10 |
| R5 (IAM verification) | T11, T12 |

All requirements have ≥1 mapped task. ✓

### Highest-risk task

**T7** — replacing `var.*` with `local.*` at three call sites in `main.tf`.
The risk is a typo (e.g., `local.google_oauth.client_id` vs
`local.google_oauth_client_id`) that `terraform validate` won't catch
because Terraform validates syntax, not semantic correctness of `local.X.Y`
references. A subtle bug here causes the Cognito IdP to be created with the
WRONG credentials (e.g., GitHub credentials passed to Google IdP).

**Mitigation**: T15's plan diff inspection should show the IdP `provider_details.client_id`
field's planned value. If the plan output looks wrong, halt before apply.

### Most likely source of rework

**C1 / T11**: If the existing Lambda IAM policy is more restrictive than
expected (lists specific ARNs rather than a wildcard), T12 adds two ARNs.
Estimated 5-minute fix.

A more impactful rework risk: **post-deploy**, if 1371's smoke test confirms
the GitHub OIDC config is broken (AR#1 HIGH #1), this feature's GitHub
secret + wiring is wasted infra until a custom GitHub OIDC proxy is built.
Wasted state, not wasted PR — the secrets are harmless if unused.

### Failure modes (3am production check)

- **Terraform state drift if operator manually rotates**: handled by
  `ignore_changes = [secret_string]`.
- **KMS key rotation fails mid-deploy**: independent of this feature; KMS
  key is unchanged.
- **Secret JSON malformed by operator**: `try()` wrapper degrades to
  empty-credentials behavior (graceful — buttons hidden).
- **Lambda cold-start panic if `ENABLED_OAUTH_PROVIDERS` is malformed**:
  `auth.py:2046-2047` strips and lowercases each token; resilient to
  whitespace and case. Empty string produces empty set, not crash.

### Gate

**READY FOR IMPLEMENTATION.**
0 CRITICAL, 0 HIGH unresolved. C1 deferred to T11 (verification, not blocker).
