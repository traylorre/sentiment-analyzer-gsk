# Implementation Plan: Feature 1371 — Preprod OAuth Rollout

## Technical Context

| Aspect | Value |
|---|---|
| Type | Runbook + verification script (no application code) |
| Code deliverables | `scripts/verify-oauth-deploy.sh` (new), `quickstart.md` (procedure docs) |
| Operators | Account admin (Google + GitHub), AWS deployer (Terraform + Secrets Manager), QA (browser test) |
| Environments | preprod ONLY (prod is feature 1372) |
| Reversibility | Operator can set secret back to placeholder JSON, run apply, IdP gets removed via count=0. Forward and reverse both clean. |
| Time estimate | 30-60 min for the operator (Google setup ~10 min, GitHub setup ~5 min, Terraform apply ~5 min, browser test ~10 min, verification ~5 min). |

## Architecture Decisions

### AD1: Verification script in bash, not Python

**Decision**: `scripts/verify-oauth-deploy.sh` is bash with `aws` + `curl` + `jq`.
**Why**: Three-line script, no need for boto3 ceremony. Bash is universal in
this team. `set -euo pipefail` covers the bash-error-hiding concern from
AR#1 LOW #11.
**Alternatives**: Python pytest fixture using boto3 + httpx. Heavier; harder
to run ad-hoc.

### AD2: AWS Account ID guard in the verification script

**Decision**: First line after `set -euo pipefail`:
```bash
EXPECTED_ACCOUNT="${EXPECTED_ACCOUNT:-218795110243}"  # preprod
ACTUAL_ACCOUNT="$(aws sts get-caller-identity --query Account --output text)"
[[ "$ACTUAL_ACCOUNT" == "$EXPECTED_ACCOUNT" ]] || { echo "Wrong AWS account"; exit 1; }
```
**Why**: HIGH #3 (wrong-env apply). The same AWS account ID is used by the
preprod Terraform state bucket (per CLAUDE.md `Terraform State Management`
section: `sentiment-analyzer-terraform-state-218795110243`). Hardcoding for
preprod, parametrizing for prod (1372).

### AD3: GitHub deferral logic baked into runbook, not script

**Decision**: The "fall back to Google-only" decision is a manual step in
the runbook, not automated.
**Why**: It's a judgment call (not all GitHub failures are the OIDC bug;
some could be Google Cloud config issues). Operator decides based on the
captured failure mode.

### AD4: Don't add this verification to the deploy CI workflow yet

**Decision**: `scripts/verify-oauth-deploy.sh` is run manually post-apply,
not from `.github/workflows/deploy.yml`.
**Why**: Until OAuth provisioning is in steady state, automating this in CI
risks false-positive deploy failures (e.g., during the gap between secret
update and Terraform apply). Adding to CI is a future feature once the
flow is well-exercised.

## Data Model

No application data model changes. Cognito user pool gains identity
provider records (per the existing `cognito/google.tf` and `github.tf`
templates).

## Contracts

No API contract changes. The `GET /api/v2/auth/oauth/urls` response shape
already exists (`OAuthURLsResponse`). After provisioning, the response body
goes from `{providers: {}, state: ""}` to `{providers: {google: {...}, github: {...}}, state: "..."}`.

## Constitution / Quality Gates

| Gate | Status |
|---|---|
| GPG-signed commits | Required for the script + runbook PR. The deploy itself is gated on the existing CI workflow which uses GPG. |
| `make validate` | The new bash script should pass shellcheck (if installed) and Bandit (no-op for bash). |
| Pre-commit `detect-secrets` | The runbook must NOT contain real client_id values, even as examples. Use `<from-google>` placeholders. |
| Plan idempotency | `terraform plan` after apply must show zero diff. |
| Browser test sign-off | Required before 1372 unlocks. |

## Implementation Steps

1. Write `scripts/verify-oauth-deploy.sh` with account ID guard, env var
   read, IdP list check, `/urls` curl + jq parse.
2. Write `specs/1371-oauth-preprod-rollout/quickstart.md` with the full
   operator runbook (R1, R2, R3, R5, R6 in order).
3. Open PR for the script + runbook (no Terraform changes — those landed
   in 1370).
4. After PR merge, operator executes the runbook:
   a. Google Cloud bootstrap (R1).
   b. GitHub OAuth App bootstrap (R2).
   c. `aws secretsmanager put-secret-value` for both providers.
   d. `terraform apply -var-file=preprod.tfvars`.
   e. `bash scripts/verify-oauth-deploy.sh preprod`.
   f. Browser test (R5).
   g. Decision point on R6 (GitHub deferral).
5. Document runbook execution in a session note or wiki page; update this
   plan with notes on what worked / what changed.

## Adversarial Review #2

**Reviewer**: Self (cross-artifact, drift detection)
**Date**: 2026-04-29

### Drift between Stage 1 (spec) and Stage 3 (plan)

| Drift | Resolution |
|---|---|
| Spec R4 says "script run manually post-apply, CI integration deferred." Plan AD4 makes this explicit. | Aligned. |
| Spec R3 includes `--profile` in CLI snippets per AR#1 HIGH #3. Plan AD2 adds account ID guard at script level too. | Both layers of defense are in place. Aligned. |
| Spec R6 deferral is described at the requirement level. Plan AD3 documents it as a manual judgment call, not automated. | Aligned. |

### Cross-artifact inconsistencies

| Inconsistency | Resolution |
|---|---|
| Spec R5 mentions "decode Cognito ID token to verify email claim." Plan steps don't explicitly include this. | Add to runbook step 4f (browser test). |
| Spec R5 mentions "duplicate-email account-linking test." Plan steps don't include this. | Add to runbook step 4f. |

### Drift recap

Two minor additions to the runbook (4f) — handled in the quickstart.md, not
in plan.md or spec.md edits.

### Gate

**0 CRITICAL, 0 HIGH remaining.**

## Clarifications

### C1: Which AWS profile name does the team use for preprod?

**Self-answer**: Repo doesn't mandate one. Common conventions: `sentiment-preprod`,
`sentiment-analyzer-preprod`, or just `default` if the operator's default
context is preprod. Plan AD2 uses account ID instead of profile name as the
guard, which is profile-agnostic.

**Conclusion**: Document the account ID in the script. Operators set their
own `AWS_PROFILE` env var.

### C2: Is there a preferred test Google account for preprod?

**Self-answer**: Unknown — depends on team's existing testing accounts.
Document as an open question in the Phase 2 summary; operator can substitute.

**Conclusion**: Defer to Phase 2 summary as user-input question.

### C3: Where does the post-sign-in `attribute_mapping` verification fit?

**Self-answer**: It's a manual decode step. The Cognito access token is in
the browser's Authorization header after sign-in. Operator can copy it from
DevTools and decode at jwt.io (or via `aws cognito-idp get-user`).

**Conclusion**: Document the procedure inline in step 4f of the runbook.

### C4: GitHub OAuth callback URL — does Cognito's `/oauth2/idpresponse`
work for the GitHub OAuth (non-OIDC) flow?

**Self-answer**: This is the heart of HIGH #2. Cognito always uses
`/oauth2/idpresponse` for IdP-issued credentials, but the IdP must be either
SAML, an actual OIDC provider, or one of the supported social providers
(Google, Apple, Facebook, Amazon). GitHub is not in the supported list.
The repo configured GitHub as `provider_type = "OIDC"`, which Cognito will
attempt to validate as OIDC — and fail.

**Conclusion**: Browser test will reveal the failure. R6 governs fallback.

### C5: Does the script need to handle the case where Cognito IdPs exist but Lambda env is stale (e.g., apply mid-deploy)?

**Self-answer**: Yes — the script checks both. If they're inconsistent,
exit non-zero with a clear message ("IdPs created but Lambda env stale —
redeploy the dashboard Lambda").

**Conclusion**: Add explicit consistency check in the script.
