# Tasks: Feature 1372 — Prod OAuth Rollout

**Plan**: [plan.md](plan.md)
**Spec**: [spec.md](spec.md)
**Depends On**: 1371 must be browser-tested green (for Google at minimum);
GitHub-conditional (skip if 1371 R6 fired).

## Phase 1: Script Extension

- [ ] **T1**: Extend `scripts/verify-oauth-deploy.sh` (created in 1371) with
  a `--pre-apply` flag. When set, the script checks ONLY the AWS account ID
  match, exits 0 if account matches, non-zero otherwise. Skips IdP/Lambda
  checks (which don't yet exist pre-apply).
  - Update env→account map to include prod (operator supplies the prod
    account ID via `EXPECTED_PROD_ACCOUNT` env var or hardcodes after C1
    resolves).
  - **File**: `scripts/verify-oauth-deploy.sh`
  - **Maps to**: spec AR#1 HIGH #4, plan AD1
  - **Deps**: 1371 T1 must be merged

## Phase 2: Quickstart Runbook

- [ ] **T2**: Write `specs/1372-oauth-prod-rollout/quickstart.md`. Sections:
  - **Section 1**: Prerequisites (prod AWS profile, prod Google account
    access with project-creation permission, GitHub admin access if R2
    applies).
  - **Section 2**: Verify the live `/terms` and `/privacy` routes return
    200 with content. Block apply if missing (AR#1 HIGH #2).
  - **Section 3**: Create distinct Google Cloud project `sentiment-prod`.
    Move consent screen to In Production. Verify the resulting `client_id`
    has a different numeric prefix than preprod's (AR#1 HIGH #3).
  - **Section 4**: GitHub OAuth App setup — CONDITIONAL on 1371's R6.
  - **Section 5**: Pre-apply account check:
    `bash scripts/verify-oauth-deploy.sh prod --pre-apply`.
  - **Section 6**: Populate Secrets Manager with prod credentials.
  - **Section 7**: `terraform plan -var-file=prod.tfvars -out=prod.plan`.
    Review with second pair of eyes.
  - **Section 8**: `terraform apply prod.plan`.
  - **Section 9**: `bash scripts/verify-oauth-deploy.sh prod` (post-apply).
  - **Section 10**: Browser end-to-end test on prod URL.
  - **Section 11**: Rollback procedure.
  - **File**: `specs/1372-oauth-prod-rollout/quickstart.md`
  - **Maps to**: spec R1-R6
  - **Deps**: T1

## Phase 3: PR

- [ ] **T3**: Open PR titled `docs(1372): prod OAuth rollout runbook +
  pre-apply guard`.
  - GPG-signed commits.
  - **Deps**: T1, T2

## Phase 4: Operator Execution (post-merge, post-1371-success)

- [ ] **T4**: Operator: verify `/terms` and `/privacy` content on prod
  Amplify URL.
  - **Deps**: T3, 1371 complete

- [ ] **T5**: Operator: bootstrap Google Cloud `sentiment-prod` project +
  OAuth client. Move consent screen to In Production.
  - **Deps**: T4

- [ ] **T6**: Operator: bootstrap GitHub OAuth App (CONDITIONAL on 1371 R6
  not firing).
  - **Deps**: T4

- [ ] **T7**: Operator: pre-apply check —
  `bash scripts/verify-oauth-deploy.sh prod --pre-apply`. Must exit 0.
  - **Deps**: T5

- [ ] **T8**: Operator: populate prod Secrets Manager values.
  - **Deps**: T5, T6, T7

- [ ] **T9**: Operator: `terraform plan -var-file=prod.tfvars -out=prod.plan`.
  Have a second engineer review the plan output.
  - **Deps**: T8

- [ ] **T10**: Operator: `terraform apply prod.plan`.
  - **Deps**: T9

- [ ] **T11**: Operator: post-apply verification —
  `bash scripts/verify-oauth-deploy.sh prod`.
  - **Deps**: T10

- [ ] **T12**: Operator: browser end-to-end test on prod URL with a real
  Google account.
  - **Deps**: T11

- [ ] **T13**: (CONDITIONAL): If anything fails, execute rollback per spec
  R6. Document the failure mode.
  - **Deps**: T12

## Adversarial Review #3

**Reviewer**: Self
**Date**: 2026-04-29

### Coverage check

| Requirement | Mapped Tasks |
|---|---|
| R1 (Google bootstrap, distinct project) | T2 (runbook), T5 (operator) |
| R2 (GitHub bootstrap, conditional) | T2, T6 |
| R3 (apply with pre-apply check) | T1 (script), T7, T9, T10 |
| R4 (post-deploy verification) | T11 |
| R5 (browser test) | T12 |
| R6 (rollback) | T2 (documented), T13 (conditional execution) |

All requirements have ≥1 mapped task. ✓

### Highest-risk task

**T10** — `terraform apply` against prod state. Risks:

1. **Concurrent apply collision**: per CLAUDE.md "Terraform State Management"
   section, S3 native locking is in place. Two operators can't apply
   simultaneously. Acceptable.
2. **Plan drift mid-review**: someone merges to main between `terraform
   plan -out=prod.plan` and `terraform apply prod.plan`. The saved plan
   file would still apply correctly (it's a snapshot), but the result
   could differ from current main. Acceptable — that's why we use
   `-out`.
3. **Apply succeeds, post-deploy verification fails**: indicates IAM /
   policy / unrelated Lambda config issue. Rollback per R6.

### Most likely source of rework

**T4** (terms/privacy content check). If the prod pages are placeholder
content, this blocks the entire feature until copy is written. Ideally
discovered before the operator sits down to deploy — push to verify well
in advance.

### Failure modes (3am production check)

This IS the production check. Unique concerns:
- **Active session loss**: HIGH #1. Plan review and low-traffic window
  mitigate.
- **Customer-facing OAuth callback failure**: graceful degradation to
  magic-link is in place (1373's hint surfaces this).
- **Cognito throttling under unexpected sign-in load**: service quota
  limits (default 30 sign-ins/sec). preprod won't surface this. If prod
  hits the limit on day 1, request a quota increase. Document as a known
  watch item.

### Gate

**READY FOR IMPLEMENTATION (when 1371 is green).**
0 CRITICAL, 0 HIGH unresolved.
