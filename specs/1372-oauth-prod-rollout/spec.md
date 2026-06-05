# Feature 1372: Prod OAuth Rollout + Verification

**Status**: Draft
**Created**: 2026-04-29
**Source**: `specs/oauth-provisioning-plan.md` (W2, W3-prod, W10)
**Depends On**: 1371 (preprod must be browser-tested green; if R6 fired in 1371, this feature inherits the same scope decision)
**Blocks**: none

## Summary

Mirror 1371's procedure for the prod environment. Provision separate Google
Cloud OAuth credentials (in a "sentiment-prod" project) and a separate GitHub
OAuth App (only if 1371 didn't trigger R6 deferral), populate prod Secrets
Manager values, deploy via Terraform, and verify end-to-end on the prod
Amplify URL.

## Differences from 1371

This feature is structurally identical to 1371 except:

| Aspect | 1371 (preprod) | 1372 (prod) |
|---|---|---|
| AWS account | preprod (218795110243) | prod (TBD — discovered via `aws sts get-caller-identity` from operator's prod profile) |
| Google Cloud project | `sentiment-preprod` | `sentiment-prod` (separate project, separate consent screen) |
| GitHub OAuth App name | `sentiment-analyzer-preprod` | `sentiment-analyzer-prod` |
| Cognito user pool | preprod pool | prod pool |
| Amplify URL | `https://main.d29tlmksqcx494.amplifyapp.com` | TBD prod Amplify URL |
| Consent screen mode | Testing OK | **Production** (must be moved out of Testing for real users) |
| Secrets path | `preprod/sentiment-analyzer/google-oauth` | `prod/sentiment-analyzer/google-oauth` |
| Var file | `preprod.tfvars` | `prod.tfvars` |
| Verification script arg | `preprod` | `prod` |

## User Stories

Same as 1371's US1-US6 with prod substitutions. Each story's acceptance
criteria reads identically except for the env-specific values.

## Requirements

### R1: Google Cloud bootstrap (prod)

Same as 1371 R1, but:
- Use a **separate Google Cloud project** named `sentiment-prod`. Distinct
  project = distinct revocation blast radius. Do NOT reuse the preprod
  project.
- Move the consent screen to **In Production** (not Testing). This requires
  Google's verification process if requesting sensitive scopes; for
  `openid email profile` (basic OIDC), self-attestation is sufficient.

### R2: GitHub OAuth App bootstrap (prod) — CONDITIONAL

If 1371's R6 fired (GitHub OIDC broken in preprod), skip this requirement.
Set the prod GitHub secret to placeholder JSON. Defer until the GitHub OIDC
issue is fixed in a follow-up feature.

If 1371's R6 did NOT fire (GitHub worked in preprod), create a separate
prod-only GitHub OAuth App.

### R3: Apply Terraform to prod

```bash
cd infrastructure/terraform
terraform init
terraform plan -var-file=prod.tfvars -out=prod.plan
# Review CAREFULLY (production deploy, see AR#1 HIGH #1)
terraform apply prod.plan
```

### R4: Post-deploy verification

`scripts/verify-oauth-deploy.sh prod` (script created in 1371). Update
account ID mapping if 1371 left it as a TODO.

### R5: End-to-end browser test (prod)

Same as 1371 R5 but on the prod Amplify URL. Use a real Google account
(not just a test account). Verify the sign-in completes within 60 seconds
of clicking the button.

### R6: Rollback procedure

If anything goes wrong in prod, set both secrets to placeholder JSON, run
`terraform apply -var-file=prod.tfvars`. The IdPs are removed (count=0),
the env var becomes empty, the buttons hide. **The frontend continues to
work via magic-link** — no user lockout.

## Success Metrics

Same as 1371's metrics but for prod:
1. `aws secretsmanager get-secret-value --secret-id prod/sentiment-analyzer/google-oauth`
   returns real credentials.
2. `terraform plan -var-file=prod.tfvars` shows zero diff post-apply.
3. `scripts/verify-oauth-deploy.sh prod` exits 0.
4. A real user signs in with Google end-to-end on the prod URL.
5. Either GitHub works or is deferred per R6.

## Out of Scope

- All non-prod environments.
- Frontend changes (1373).
- Spec reconciliation (1374).

## Adversarial Review #1

**Reviewer**: Self (adversarial — production blast radius, rollback paths)
**Date**: 2026-04-29

### Findings

| Severity | Finding | Resolution |
|---|---|---|
| HIGH | Production deploys can disrupt active user sessions if the Cognito user pool client config is touched. The `aws_cognito_identity_provider` resource creation does NOT touch the user pool client, but if the apply unexpectedly drifts (e.g., a reviewer-missed change in main.tf), real users could be logged out. | Mitigation: review the `terraform plan` output line-by-line. Reject any unrelated diffs. Do the apply during a low-traffic window if possible. Post-apply, immediately verify existing sessions still work (load `/dashboard` with a stored access token). |
| HIGH | Google Cloud "In Production" requires a privacy policy URL and terms of service URL. The repo's frontend has `/terms` and `/privacy` routes (per signin/page.tsx:84,88). Are these pages live and content-complete? | Add a verification step to R1: load `https://<prod-amplify-url>/terms` and `/privacy`, confirm they return 200 with substantive content. If not, this feature is blocked on a content task. |
| HIGH | Reusing the preprod Google project for prod (despite the spec saying "separate project") is a tempting shortcut for an operator under deadline pressure. Cross-env credential reuse means a compromised preprod account = compromised prod sign-in. | Add an explicit gate in the runbook: the prod project's `client_id` value MUST start with a different numeric prefix than preprod's. (Google client IDs are `<numeric>-<random>.apps.googleusercontent.com`; the numeric prefix is the project number, which is unique per project.) The verification script can assert this difference. |
| HIGH | Operator runs `terraform apply` with `preprod.tfvars` against the prod state by accident (or vice versa). | The same account ID guard from 1371's `verify-oauth-deploy.sh` should run BEFORE `terraform apply`. Add a pre-apply checklist in the runbook: "Before running apply, run `bash scripts/verify-oauth-deploy.sh prod --pre-apply` to confirm AWS account matches the var file." (Implies: extend the verify script with a `--pre-apply` mode that only checks account, no other state.) |
| MEDIUM | The prod Cognito user pool may have stricter `aws_cognito_user_pool` configuration (e.g., MFA enforcement, password policies) that interacts with federated sign-in differently than preprod. | Manually review the prod user pool config before apply. Document any differences in this feature's quickstart. |
| MEDIUM | Real prod users may already exist with email-based magic-link accounts. Federated sign-in with the same email could collide with Feature 1182's auto-link logic. | 1371's R5 covers this in preprod with a duplicate-email test. If preprod test passed, prod inherits the same behavior. |
| MEDIUM | A subset of prod users may use Workspace (Google enterprise) accounts where the org admin restricts third-party OAuth. Sign-in fails with "Access blocked." | Document as a known limitation. Magic-link still works for these users. |
| LOW | `recovery_window_in_days = 7` in 1370 means a deleted prod secret has a 7-day recovery window. An attacker with `secretsmanager:DeleteSecret` could trigger a recoverable delete; legitimate ops would have 7 days to restore. | Acceptable. CloudTrail audits the action. |
| LOW | Google's verification process for "In Production" can take days/weeks. If this is the first time this team has gone through it, factor in lead time. | Add to runbook: confirm consent screen status BEFORE the deploy is scheduled. |

### Spec edits made in response

- **R1 updated** to require a privacy + terms URL check (HIGH #2).
- **R1 updated** to require distinct Google Cloud project + verification of
  numeric prefix difference (HIGH #3).
- **R3 updated** with pre-apply account ID check (HIGH #4).
- Implies: extend `scripts/verify-oauth-deploy.sh` from 1371 with a
  `--pre-apply` mode. Add as a task.

### Residual Risks

- Prod traffic disruption during apply (HIGH #1) — mitigated by plan review
  + low-traffic window.
- Workspace org-restricted accounts can't use OAuth (MEDIUM #3) — by design,
  not fixable in this feature.

### Gate

**0 CRITICAL, 0 HIGH unresolved.**
