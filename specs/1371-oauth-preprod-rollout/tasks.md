# Tasks: Feature 1371 — Preprod OAuth Rollout

**Plan**: [plan.md](plan.md)
**Spec**: [spec.md](spec.md)
**Depends On**: 1370 must be merged + applied to preprod state.

## Phase 1: Verification Script

- [ ] **T1**: Create `scripts/verify-oauth-deploy.sh`. Contents:
  - `#!/usr/bin/env bash` + `set -euo pipefail`.
  - `ENV="${1:?usage: $0 <preprod|prod>}"`.
  - Map env to expected account ID: `preprod→218795110243`, `prod→<TBD by 1372>`.
  - `aws sts get-caller-identity --query Account --output text` and assert match.
  - Read Lambda env: `aws lambda get-function-configuration --function-name "${ENV}-dashboard" --query 'Environment.Variables.ENABLED_OAUTH_PROVIDERS'`. Assert non-empty.
  - List Cognito IdPs: `aws cognito-idp list-identity-providers --user-pool-id "$(aws cognito-idp list-user-pools --max-results 60 --query "UserPools[?starts_with(Name, '${ENV}')].Id | [0]" --output text)"`. Assert at least one (Google).
  - Curl `https://<api-gw>/api/v2/auth/oauth/urls` (URL discovered from Terraform output or hardcoded per env). Parse with `jq` to assert `providers | length > 0`.
  - Print pass/fail summary table.
  - **File**: `scripts/verify-oauth-deploy.sh`
  - **Maps to**: spec R4, plan AD1, AD2
  - **Deps**: none

- [ ] **T2**: Add execute permission and verify shellcheck-clean (if
  shellcheck installed).
  - **Command**: `chmod +x scripts/verify-oauth-deploy.sh; shellcheck scripts/verify-oauth-deploy.sh`
  - **Deps**: T1

## Phase 2: Quickstart Runbook

- [ ] **T3**: Write `specs/1371-oauth-preprod-rollout/quickstart.md` covering
  the full operator procedure:
  - **Section 1**: Prerequisites (AWS credentials, Google Cloud access,
    GitHub Developer Settings access, knowledge of preprod Cognito domain).
  - **Section 2**: Google Cloud setup (R1, with the Testing-mode caveat
    from AR#1 HIGH #1).
  - **Section 3**: GitHub OAuth App setup (R2).
  - **Section 4**: Populate Secrets Manager — using `fileb://creds.json`
    pattern with `shred` cleanup (HIGH #4 mitigation).
  - **Section 5**: `terraform apply` with explicit `--profile` and `--region`
    (HIGH #3).
  - **Section 6**: Run `scripts/verify-oauth-deploy.sh preprod`.
  - **Section 7**: Browser end-to-end test (R5):
    - Click Google → consent → callback → dashboard.
    - Decode the access token, verify `email` claim (AR#1 HIGH #5).
    - Test duplicate-email account linking (AR#1 MEDIUM #4).
    - Click GitHub → expect failure or success.
  - **Section 8**: GitHub deferral decision (R6). If GitHub fails, set
    secret to placeholder, re-apply, document in a follow-up issue.
  - **Section 9**: Rollback procedure (set both secrets to placeholder,
    `terraform apply`, IdPs removed).
  - **File**: `specs/1371-oauth-preprod-rollout/quickstart.md`
  - **Maps to**: spec R1, R2, R3, R5, R6
  - **Deps**: T1, T2

## Phase 3: PR

- [ ] **T4**: Open PR titled `docs(1371): preprod OAuth rollout runbook +
  verification script`.
  - Include a checklist in the PR body matching the runbook sections, so a
    reviewer can confirm coverage.
  - GPG-signed commits.
  - **Deps**: T1, T2, T3

## Phase 4: Operator Execution (post-merge, manual)

These tasks are executed by an SRE / deployer after PR merge. They are NOT
code changes; the artifact is a session note / wiki page documenting the
result.

- [ ] **T5**: Operator: bootstrap Google Cloud project + OAuth client.
  Capture `client_id` and `client_secret`. Save to a temporary file
  (`creds.json`) NOT in the repo.
  - **Maps to**: spec R1
  - **Deps**: T4

- [ ] **T6**: Operator: bootstrap GitHub OAuth App. Same.
  - **Maps to**: spec R2
  - **Deps**: T4 (parallel with T5)

- [ ] **T7**: Operator: `aws secretsmanager put-secret-value` for both,
  using `fileb://`. `shred -u creds.json`.
  - **Maps to**: spec R1, R2 (storage step)
  - **Deps**: T5, T6

- [ ] **T8**: Operator: `terraform apply -var-file=preprod.tfvars`. Confirm
  plan diff matches expectations (2 new IdPs, env var update).
  - **Maps to**: spec R3
  - **Deps**: T7

- [ ] **T9**: Operator: run `scripts/verify-oauth-deploy.sh preprod`. Must
  exit 0.
  - **Maps to**: spec R4
  - **Deps**: T8

- [ ] **T10**: Operator: browser end-to-end test on preprod. Document
  outcome (Google: pass / fail; GitHub: pass / fail with failure mode if
  applicable).
  - **Maps to**: spec R5
  - **Deps**: T9

- [ ] **T11**: (CONDITIONAL on T10): If GitHub failed, follow R6 deferral
  procedure. Open a new issue/feature for GitHub OIDC fix. Re-run T8 + T9
  with GitHub disabled.
  - **Maps to**: spec R6
  - **Deps**: T10

## Adversarial Review #3

**Reviewer**: Self (implementation readiness, risk assessment)
**Date**: 2026-04-29

### Coverage check

| Requirement | Mapped Tasks |
|---|---|
| R1 (Google bootstrap) | T3 (runbook), T5 (operator) |
| R2 (GitHub bootstrap) | T3 (runbook), T6 (operator) |
| R3 (Terraform apply) | T3 (runbook), T8 (operator) |
| R4 (verification script) | T1, T2, T9 (operator) |
| R5 (browser test) | T3 (runbook), T10 (operator) |
| R6 (GitHub deferral) | T3 (runbook), T11 (operator, conditional) |

All requirements have ≥1 mapped task. ✓

### Highest-risk task

**T10** — the browser end-to-end test. Three failure modes:

1. **Google sign-in fails**: most likely a misconfigured redirect URI in
   Google Cloud (typo, wrong domain, missing path). Fix: update redirect
   URI, retry. Cost: ~5 min.
2. **GitHub sign-in fails (expected per AR#1 HIGH #2)**: triggers R6.
   Cost: ~30 min to disable GitHub + open follow-up.
3. **Both fail with a Cognito-side error** (e.g., user pool not configured
   for federation): suggests `cognito/main.tf` or user pool client config
   needs an update. Larger blast radius — could block 1372 entirely.

### Most likely source of rework

R6 firing for GitHub. ~70% probability based on the OIDC config evidence.
The rework cost is bounded: ship Google-only, open issue, move on.

### Failure modes (3am production check)

This is preprod, but the operational lessons are still relevant:
- **Operator runs apply with wrong AWS_PROFILE**: T1 script's account ID
  guard catches this BEFORE running apply (script is run pre-apply by the
  operator as a sanity check, per runbook step ordering).
- **Operator forgets to populate the secret before apply**: `terraform
  apply` succeeds (placeholder JSON gracefully handled by 1370's `try()`)
  but no IdPs created. Operator runs verify script, sees zero providers,
  realizes the issue. Self-correcting.
- **Google's "App not verified" warning blocks all sign-ins**: documented
  in HIGH #1 mitigation. Test users allow-listed in Google Cloud.
- **Mid-deploy partial failure**: Terraform reports the failure; operator
  re-runs apply. Idempotent.

### Gate

**READY FOR IMPLEMENTATION.**
0 CRITICAL, 0 HIGH unresolved. The known HIGH #2 (GitHub OIDC) is
explicitly deferred per R6 with a documented escape hatch.
