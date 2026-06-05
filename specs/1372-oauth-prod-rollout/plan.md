# Implementation Plan: Feature 1372 — Prod OAuth Rollout

## Technical Context

| Aspect | Value |
|---|---|
| Type | Runbook + verification script extension |
| Code deliverables | `scripts/verify-oauth-deploy.sh` extension (`--pre-apply` mode), prod-specific quickstart |
| Differences from 1371 | Separate Google Cloud project, prod consent screen state, pre-apply account check, terms/privacy verification |

## Architecture Decisions

### AD1: Reuse 1371's verify script with a `--pre-apply` flag

**Decision**: Extend `scripts/verify-oauth-deploy.sh` (built in 1371) with
`--pre-apply` to check ONLY the AWS account ID, before any IdP/Lambda state
exists for the new env.
**Why**: Prevents the "wrong env apply" disaster. One script, two modes.

### AD2: Distinct Google Cloud project, enforce via project-number check

**Decision**: The prod Google OAuth `client_id` must have a different numeric
prefix than the preprod `client_id` (Google client IDs encode the project
number). Document the check in the runbook; optionally add to the verify
script.

### AD3: Plan review checkpoint before apply

**Decision**: The runbook explicitly requires a second pair of eyes on
`terraform plan -out=prod.plan` output before `terraform apply prod.plan`
runs. Not automated; relies on team norms.

## Implementation Steps

1. Extend `scripts/verify-oauth-deploy.sh` with `--pre-apply` mode (after
   1371 lands).
2. Write `specs/1372-oauth-prod-rollout/quickstart.md` covering:
   - All differences from 1371's runbook (separate Google project, prod
     consent screen, pre-apply check, terms/privacy verification).
   - Prod-specific Cognito domain and Amplify URL (operator fills in).
   - Conditional GitHub setup (skip if 1371 R6 fired).
   - Rollback procedure.
3. Open PR for the script extension + runbook.
4. After PR merge AND after 1371 has been browser-tested green, operator
   executes the prod runbook.

## Adversarial Review #2

**Reviewer**: Self
**Date**: 2026-04-29

### Drift between Stage 1 and Stage 3

| Drift | Resolution |
|---|---|
| Spec R1 + R3 imply `--pre-apply` exists. Plan AD1 makes it concrete. | Aligned. |
| Spec HIGH #3 (project-number check) — plan AD2 documents but doesn't make it scriptable. | Acceptable. The check is one-time per env (after credentials are first stored), not every-apply. Manual check in runbook is enough. |

### Cross-artifact inconsistencies

None identified.

### Gate

**0 CRITICAL, 0 HIGH remaining.**

## Clarifications

### C1: What is the prod AWS account ID?

**Self-answer**: Unknown from this conversation. Operator discovers via
`aws sts get-caller-identity` from prod profile. Update the verify script's
account ID map at that time.

**Conclusion**: Defer to Phase 2 summary as user-input question.

### C2: What is the prod Cognito domain and prod Amplify URL?

**Self-answer**: Unknown — depends on `var.environment` and Terraform
outputs for prod state. Operator captures via `terraform output -json` after
apply.

**Conclusion**: Document as a runbook step ("capture these values after
first apply").

### C3: Do the existing `/terms` and `/privacy` routes render content?

**Self-answer**: Need to load them in a browser to confirm. Spec AR#1 HIGH
#2 makes this a runbook prerequisite check.

**Conclusion**: Operator verifies before requesting Google "In Production"
consent screen status.

### C4: Has the team ever taken a Google Cloud project from Testing → In
Production for this app, and how long did verification take?

**Self-answer**: Unknown.

**Conclusion**: Defer to Phase 2 summary. May affect timeline.

### C5: Is the prod environment sized to handle a sudden OAuth rollout (cold-start spike from new sign-in users)?

**Self-answer**: OAuth sign-in goes through Cognito (not the dashboard
Lambda). The dashboard Lambda handles the `/oauth/urls` and `/oauth/callback`
endpoints — cold-start on these endpoints is the only risk. Both are
already in the dashboard Lambda's hot path. No additional capacity
concern.

**Conclusion**: No action needed.
