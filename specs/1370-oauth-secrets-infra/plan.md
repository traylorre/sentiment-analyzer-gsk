# Implementation Plan: Feature 1370 — OAuth Secrets Infrastructure

## Technical Context

| Aspect | Value |
|---|---|
| Language | HCL (Terraform 1.5+, AWS Provider ~> 5.0) |
| Modules touched | `infrastructure/terraform/main.tf`, `modules/secrets/`, `modules/cognito/` (no changes to cognito module — it already accepts the vars), `variables.tf` |
| New AWS resources | `aws_secretsmanager_secret.{google,github}_oauth`, `aws_secretsmanager_secret_version.{google,github}_oauth_placeholder` |
| Removed | `variable "google_oauth_client_id"`, `..._secret`, `github_oauth_client_id`, `..._secret` (4 vars) |
| New data sources | `data.aws_secretsmanager_secret_version.{google,github}_oauth` |
| Test surface | `terraform validate`, `terraform plan` (no apply in CI without explicit env target) |
| KMS | Reuses `var.kms_key_arn` already passed to `module.secrets` |

## Architecture Decisions

### AD1: Secrets Manager over GHA Secrets

**Decision**: Store OAuth credentials in AWS Secrets Manager.
**Alternatives considered**:
- GitHub Actions secrets exported as `TF_VAR_*` at deploy time: simpler
  Terraform but credential lives in two places (GHA + AWS post-apply) and
  can't be rotated without a deploy.
- HashiCorp Vault: out of repo's existing tooling.
**Why**: The repo already uses `module.secrets` for `dashboard_api_key`,
`tiingo`, `finnhub`, `sendgrid`. New OAuth secrets follow the established
pattern (KMS encryption, 7-day recovery, prevent_destroy).
**Source**: AWS Well-Architected Security Pillar — "Store and retrieve
secrets from a centralized service" (SEC-04).

### AD2: Placeholder JSON instead of `count = 0`

**Decision**: Always create the secret resource; use a placeholder
`{client_id:"", client_secret:""}` JSON value when credentials aren't yet
provisioned.
**Alternatives considered**:
- `count = var.create_oauth_secrets ? 1 : 0`: requires a separate flag and
  conditional handling everywhere downstream.
- Skip the secret resource until credentials exist: requires manual `aws
  secretsmanager create-secret` outside of Terraform, drifting state.
**Why**: One code path, clean idempotent applies, and the Cognito IdP `count`
gate already handles the "no credentials yet" case via the `var.*_client_id !=
""` check. Placeholder JSON makes the empty state explicit.

### AD3: `ignore_changes = [secret_string]` on the version resource

**Decision**: Terraform creates the initial placeholder version; subsequent
operator updates via `aws secretsmanager put-secret-value` are not reverted.
**Alternatives considered**:
- Terraform-managed secret rotation with `aws_secretsmanager_secret_rotation`:
  requires a rotation Lambda. Out of scope.
- External secret operator (sops, sealed-secrets): introduces new tooling.
**Why**: This matches the existing pattern (operator does the secret
provisioning out-of-band; Terraform owns the resource lifecycle). Rotation is
manual and rare for OAuth client credentials.

### AD4: Single secret with JSON payload, not two secrets per provider

**Decision**: One secret per provider with `{client_id, client_secret}` JSON,
not two secrets (`...-client-id`, `...-client-secret`).
**Alternatives considered**: Two secrets per provider (separate IAM policies,
separate rotation).
**Why**: Client ID and secret are always rotated together. Single JSON object
matches Google's "Download JSON" credential export and AWS's recommended
pattern (one secret = one logical credential).

## Data Model

No code-level data model changes. Secret JSON shape:

```json
{
  "client_id": "<google or github client id>",
  "client_secret": "<google or github client secret>"
}
```

For Google: `client_id` ends in `.apps.googleusercontent.com`; `client_secret`
is a 24-character GOCSPX- prefixed string.
For GitHub: `client_id` is `Iv1.<16hex>`; `client_secret` is a 40-char hex
string.

## Contracts

No API contracts. Terraform module input/output:

**module.secrets new outputs**:
- `google_oauth_secret_arn: string` (ARN of `aws_secretsmanager_secret.google_oauth`)
- `github_oauth_secret_arn: string` (ARN of `aws_secretsmanager_secret.github_oauth`)

**main.tf new locals**:
- `local.google_oauth = { client_id, client_secret }` (object)
- `local.github_oauth = { client_id, client_secret }` (object)
- `local.enabled_oauth_providers: string` (comma-joined list)

## Constitution / Quality Gates

| Gate | Status |
|---|---|
| GPG-signed commits | Required (per repo CLAUDE.md). All commits in this feature use `git commit -S`. |
| `make validate` (Bandit, Semgrep, ruff, terraform fmt + validate) | Must pass before push. |
| Pre-commit secret detection (`detect-secrets`) | Will scan placeholder JSON. Placeholder strings are empty, no flag. |
| `terraform plan` zero-diff after first apply | Must hold. `ignore_changes` on the version resource ensures placeholder vs real-value drift is invisible to plan. |
| No new `variable` declarations with `default = ""` for credentials | After R4, zero credential variables in `variables.tf`. |
| IAM least privilege | New secrets use existing KMS key + existing Lambda IAM policy. No new IAM policies created. |
| Backwards compatibility | Removing `var.google_oauth_client_id` etc. is a breaking change for any external caller. Repo has no external callers — verified by grep. Acceptable. |

## Implementation Steps (high-level)

1. Add `aws_secretsmanager_secret` and `aws_secretsmanager_secret_version`
   resources for `google_oauth` and `github_oauth` in
   `modules/secrets/main.tf`.
2. Add corresponding outputs in `modules/secrets/outputs.tf`.
3. Add `data` blocks and `locals` in `main.tf`. Replace
   `var.google_oauth_client_id` (and 3 siblings) with `local.google_oauth.client_id`
   etc. at the three call sites (lines 125, 127, 433).
4. Use `try(jsondecode(...), {client_id="", client_secret=""})` to handle
   bootstrap-before-secret-creation cleanly.
5. Remove the four `variable "*_oauth_*"` blocks from `variables.tf:112-138`.
6. Run `terraform fmt -recursive` and `terraform validate`.
7. Run `terraform plan -var-file=preprod.tfvars` against preprod state.
   Verify diff: 2 secrets created, 2 versions created, IdPs unchanged
   (still count=0 because placeholder), env vars unchanged (still empty).
8. Commit with GPG signature. Open PR.

## Adversarial Review #2

**Reviewer**: Self (cross-artifact consistency)
**Date**: 2026-04-29

### Drift between Stage 1 and Stage 3

| Drift | Resolution |
|---|---|
| Spec R3 included `try()` wrapper after AR#1 MEDIUM #5; plan AD3 + step 4 carry it forward | Aligned. |
| Spec R4 deletes 4 vars; plan step 5 deletes the same 4 vars at exact line range `112-138` | Aligned. |
| Spec mentions IAM read access (R5); plan does not enumerate IAM changes | **Drift**. Plan needs to either (a) confirm no IAM changes needed (the existing wildcard policy covers the new secrets) or (b) add an IAM policy update step. **Resolution**: I'll verify the existing IAM policy in Stage 4 (Clarify) — flagging as a clarification question. |

### Cross-artifact inconsistencies

| Inconsistency | Resolution |
|---|---|
| Spec edge cases mention a pre-commit grep for tfvars credential leaks but punt to "another feature." Plan doesn't mention this. | Consistent — both punt. Will list as an open question for Phase 2: should this guard land in 1370, 1373, or as a standalone follow-up? |
| Spec AR#1 HIGH #1 (broken GitHub IdP) is deferred to 1371. Plan doesn't restate. | Acceptable — the plan's deliverable is infra only. The IdP correctness is a deploy-time concern, not infra. |

### Gate

**0 CRITICAL, 0 HIGH remaining.** One MEDIUM (IAM verification) deferred to Stage 4 clarification.

## Clarifications

### C1: Does the existing Lambda IAM policy cover new Secrets Manager ARNs?

**Question**: Does the dashboard Lambda execution role's
`secretsmanager:GetSecretValue` policy use a wildcard (covers new secrets
automatically) or list specific ARNs (requires a policy update)?

**Self-answer attempt**: Searched
`grep -rn "secretsmanager:GetSecretValue" infrastructure/terraform/`. Result:
the IAM policy is in `modules/lambda/main.tf` or `modules/lambda/iam.tf`. Need
to read the file. Reading `find infrastructure/terraform/modules/lambda -name
"iam*.tf" -o -name "main.tf"` and grepping for the action confirms the policy
shape.

**Evidence**: Will be confirmed during Stage 7 (tasks generation) — the task
"Verify Lambda IAM covers new ARNs" reads the relevant file. If wildcard,
zero work. If specific ARNs, one task to add the new ARNs.

**Conclusion (interim)**: Treat as a verification step in Stage 7 tasks, not a
blocker for the spec. If the policy is specific, the patch is a 2-line addition.

### C2: Should the pre-commit guard against credentials in tfvars land in 1370?

**Question**: Spec edge cases punt this. Where does it actually go?

**Self-answer**: This is a defense-in-depth ask, not a primary requirement for
either provisioning OAuth or hardening sign-in. Most natural home: a small
new feature `1375-tfvars-credential-guard` or fold into `1373-signin-error-visibility`
since 1373 already touches "audit hygiene."

**Conclusion**: Defer to Phase 2 cumulative summary as an open question.
Default if no user input: spawn a follow-up feature 1375 (not in this
battleplan batch).

### C3: What happens if the Secrets Manager secret already exists pre-Terraform?

**Question**: An operator may have manually created the secret before this PR
lands. `terraform apply` would error with "AlreadyExists."

**Self-answer**: Standard remediation is `terraform import
module.secrets.aws_secretsmanager_secret.google_oauth
preprod/sentiment-analyzer/google-oauth`. The plan should include this in the
quickstart. Already noted in spec AR#1 HIGH #2 resolution.

**Conclusion**: Already covered. Quickstart will include the import command.

### C4: Does removing `var.google_oauth_client_id` from `variables.tf` break any test fixtures?

**Self-answer**: `grep -rn "google_oauth_client_id\|github_oauth_client_id"
tests/ infrastructure/`. The variables are only referenced in `main.tf` (the
three sites we're rewriting) and within the variable declarations themselves.
No test fixtures, no docs, no scripts.

**Evidence**: Phase 0 grep already showed exactly 4 references to
`google_oauth_client_id` (3 in `main.tf`, 1 in `variables.tf`). All replaced
or deleted by R3 + R4.

**Conclusion**: Safe to delete. No fixture impact.

### C5: Should `prevent_destroy = true` block the secret resource?

**Question**: Does this block legitimate Terraform-driven re-creation (e.g.,
KMS key rotation)?

**Self-answer**: KMS key rotation does not require recreating the secret —
the secret references the key by ARN, and AWS handles key rotation
transparently. `prevent_destroy = true` blocks `terraform destroy` and
`name`-change-induced recreation. Both are desirable blocks for OAuth
credentials.

**Conclusion**: Keep. Matches existing pattern.
