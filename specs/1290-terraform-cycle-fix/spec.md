# Feature 1290: Terraform Dependency Cycle Fix

## Problem Statement

The Terraform deploy pipeline has been broken since PRs #832-834 (CORS hardening) exposed a latent 5-module circular dependency. `terraform plan` fails with a cycle error, blocking ALL infrastructure deployments to preprod and prod. No security patches, feature deployments, or configuration changes can ship until this is resolved.

### The Cycle

```
amplify_frontend ──[api_gateway_url]──→ api_gateway
       ↑                                      │
       │                               [invoke_arn]
  [production_url]                             ↓
       │                              dashboard_lambda
notification_lambda                            │
       ↑                          [scheduler_role_arn]
       │                                       ↓
       └────────[function_arn]──────── chaos ──┘
```

Five modules form a cycle through Lambda environment variables and module inputs:
1. `api_gateway` needs `dashboard_lambda.invoke_arn` (HARD)
2. `dashboard_lambda` needs `chaos.chaos_scheduler_role_arn` (SOFT — env var)
3. `chaos` needs `notification_lambda.function_arn` (HARD — FIS target)
4. `notification_lambda` needs `amplify_frontend.production_url` (SOFT — env var)
5. `amplify_frontend` needs `api_gateway.api_endpoint` (HARD — frontend config)

### Root Cause

The cycle was latent — all edges existed before PRs #832-834. Adding `cors_allowed_origins` variable to the `api_gateway` module changed its internal topology, forcing Terraform to re-expand the module graph and detect the pre-existing cycle.

## Solution: Strategy 4 — Split Definition + Wiring

Break the two SOFT dependency edges by splitting Lambda creation (definition) from cross-module environment variable population (wiring).

**Definition phase**: Create all Lambda modules with placeholder values (`""`) for environment variables that reference other modules across the cycle boundary.

**Wiring phase**: After all modules exist, use `terraform_data` resources with `local-exec` provisioners to populate the actual cross-module values via `aws lambda update-function-configuration`.

**Cycle-breaking edges**:
- `dashboard_lambda.SCHEDULER_ROLE_ARN` — placeholder `""` at creation, patched with `module.chaos.chaos_scheduler_role_arn` after chaos exists
- `notification_lambda.DASHBOARD_URL` — placeholder `""` at creation, patched with `module.amplify_frontend[0].production_url` after Amplify exists

## User Stories

### US-1: Infrastructure Engineer
As an infrastructure engineer, I need `terraform plan` and `terraform apply` to succeed so that I can deploy security patches, features, and configuration changes to preprod and prod.

**Acceptance**: `terraform plan` completes without cycle error on preprod and prod configurations.

### US-2: DevOps Engineer (Observability)
As a DevOps engineer, I need to detect when Lambda environment variables are in a degraded state (placeholder values) so that I can intervene before users are affected.

**Acceptance**: CloudWatch metric emitted when critical env vars are empty. Alarm fires within 5 minutes.

### US-3: Developer (Feature Safety)
As a developer adding new features, I need the wiring pattern to be safe so that adding a new environment variable to a Lambda doesn't silently break in preprod/prod.

**Acceptance**: Wiring provisioner merges env vars (read-merge-write), never replaces the entire environment block.

### US-4: Security Engineer
As a security engineer, I need the new IAM permissions to follow least-privilege so that a compromised CI pipeline cannot modify arbitrary Lambda configurations.

**Acceptance**: `lambda:UpdateFunctionConfiguration` scoped to specific function ARNs, not `*`.

## Functional Requirements

### FR-001: Break the Terraform dependency cycle
Remove cross-module env var references from `dashboard_lambda` and `notification_lambda` module blocks. Replace with placeholder empty strings. Add `environment` to the existing `lifecycle { ignore_changes = [image_uri] }` in the Lambda module's `aws_lambda_function` resource. Remove `depends_on = [module.amplify_frontend]` from notification_lambda (the dependency was through the env var which is now removed).

### FR-002: Wiring resources for cross-module env vars
Create `terraform_data` resources that:
1. Depend on both the Lambda and the source module
2. Read existing Lambda env vars via `aws lambda get-function-configuration`
3. Merge the cross-module value into the existing env vars
4. Write back via `aws lambda update-function-configuration`
5. Use process substitution or pipe for JSON input (not temp files — prevents secret leakage on shared runners)
6. Suppress command output to prevent logging secret ARN values
7. After write, read back and verify the wired value matches expected (fail-fast if mismatch)

### FR-003: Global ignore_changes for environment
Add `environment` to the existing `ignore_changes = [image_uri]` list in `modules/lambda/main.tf`. This applies to ALL Lambdas using the shared module. Trade-off accepted: lose env var drift detection on all 6 Lambdas. Compensated by runtime validation (FR-005). Documented as tech debt.

### FR-004: IAM permission for CI (PRE-SATISFIED)
`lambda:UpdateFunctionConfiguration` and `lambda:GetFunctionConfiguration` already present in `ci-user-policy.tf:50,53`, scoped to `arn:aws:lambda:*:*:function:*-sentiment-*`. No implementation work needed.

### FR-005: Runtime env var validation
Add startup validation in dashboard_lambda and notification_lambda that:
1. Checks critical env vars are non-empty
2. Emits structured CloudWatch log with metric dimension `env_var_missing`
3. Continues execution (does not crash) — degraded but functional

### FR-006: CloudWatch alarm for env var degradation
Create CloudWatch metric filter + alarm that fires when `env_var_missing` metric > 0 for 5 minutes.

### FR-007: CloudTrail monitoring
Add EventBridge rule that matches `UpdateFunctionConfiguration` API calls outside the deploy pipeline's IAM role. Route to SNS for security team notification.

### FR-008: Documentation
Create `docs/terraform-patterns.md` documenting the split definition/wiring pattern with:
- When to use it (and when NOT to)
- The merge-not-replace requirement
- Cross-reference comments template
- Diagram of the pattern

### FR-009: Tech debt ticket
Create GitHub issue for long-term fix: migrate cross-module env vars to SSM Parameter Store for runtime resolution. Tag as tech-debt, priority medium.

## Success Criteria

### SC-001: Cycle resolved
`terraform plan -var-file=preprod.tfvars` completes without cycle error.

### SC-002: Wiring correctness
After `terraform apply`, `aws lambda get-function-configuration --function-name ${env}-sentiment-dashboard` shows `SCHEDULER_ROLE_ARN` with valid IAM role ARN (not empty string).

### SC-003: Wiring correctness (notification)
After `terraform apply`, `aws lambda get-function-configuration --function-name ${env}-sentiment-notification` shows `DASHBOARD_URL` with valid Amplify URL (not empty string).

### SC-004: Env var merge safety
Adding a new env var to `dashboard_lambda` module block and running `terraform apply` does NOT remove existing env vars set by the wiring provisioner.

### SC-005: IAM least privilege
The CI IAM policy for `lambda:UpdateFunctionConfiguration` does NOT match `Resource: "*"`.

### SC-006: Runtime detection
When SCHEDULER_ROLE_ARN is empty, dashboard_lambda emits a structured log containing `"metric": "env_var_missing"` within 1 invocation.

### SC-007: No existing functionality broken
All existing Playwright E2E tests pass after the change. All existing unit tests pass.

### SC-008: Deploy pipeline green
The full deploy pipeline (build → test → deploy-preprod → integration-test) succeeds end-to-end.

## Edge Cases

### EC-001: First-time deployment (no existing Lambda)
On first deployment, `aws lambda get-function-configuration` fails because the Lambda doesn't exist yet. The wiring provisioner must handle this gracefully — Terraform creates the Lambda first (T2), then runs the wiring (T6). The `depends_on` ensures ordering.

### EC-002: Amplify disabled (enable_amplify = false)
When Amplify is disabled, `module.amplify_frontend[0]` doesn't exist. The notification_lambda wiring resource must use `count` conditional or `try()` to skip wiring when Amplify is absent. DASHBOARD_URL remains at placeholder.

### EC-003: Chaos disabled (enable_chaos_testing = false internally)
When chaos is disabled, `module.chaos` exists but its outputs may be empty. The dashboard_lambda wiring must handle empty/null `chaos_scheduler_role_arn` by setting SCHEDULER_ROLE_ARN to `""` (same as placeholder).

### EC-004: Concurrent terraform apply
State locking (DynamoDB lock table) prevents concurrent applies. If lock fails, `terraform apply` exits with lock error before any resources are modified.

### EC-005: Provisioner fails mid-apply
If the wiring provisioner fails (throttling, permission error), `terraform apply` exits with error. Lambda exists with placeholder env vars. Next `terraform apply` retries the provisioner. No partial state corruption.

### EC-006: Manual env var change between applies
If someone manually edits Lambda env vars via console, the wiring provisioner will overwrite those changes on next apply (it reads current → merges → writes). Manual changes to wired env vars are not preserved. Manual changes to OTHER env vars are preserved (merge).

### EC-007: Lambda invoked during wiring window
During the 30-60s between Lambda creation and wiring, the Lambda has placeholder env vars. AWS Lambda env var updates are atomic — no partial reads. Impact: auto-restore disabled, email links empty. Both degrade gracefully.

## Non-Functional Requirements

### NFR-001: Zero additional AWS cost
No new AWS resources created (terraform_data is Terraform-only). AWS CLI API calls are free.

### NFR-002: Single-apply deployment
All changes (definition + wiring) execute in a single `terraform apply`. No two-phase manual process.

### NFR-003: Idempotent wiring
Running `terraform apply` multiple times produces the same result. The merge operation is idempotent (merging the same key twice = same value).

### NFR-004: No downtime during apply
Lambda Function URLs remain active during env var update. AWS handles this atomically.

## Out of Scope

- **SSM Parameter Store migration** — filed as tech debt (FR-009), not implemented in this feature
- **Restructuring module boundaries** — architectural change deferred to next quarter
- **CORS origin population** — separate concern; this feature only breaks the cycle
- **Playwright test gaps** — identified in analysis.md but implemented separately

## Adversarial Review #1

### Findings

| # | Severity | Finding | Resolution |
|---|----------|---------|------------|
| 1 | **CRITICAL** | FR-002 original spec used temp file (`/tmp/lambda-config.json`) for CLI input. On shared CI runners, another process could read secrets from this file. | **Resolved**: FR-002 updated to use process substitution or pipe. No temp files. |
| 2 | **HIGH** | FR-003 requires per-instance `ignore_changes` but Lambda module is shared by 5+ Lambdas. No mechanism to opt-in selectively. | **Resolved**: FR-003 updated to add `ignore_environment_changes` variable (bool, default false) to Lambda module. |
| 3 | **HIGH** | FR-002 provisioner could silently succeed (exit 0) without actually updating. `terraform plan` would show no drift due to `ignore_changes`. | **Resolved**: FR-002 updated to add read-back verification step after write. Provisioner fails if wired value doesn't match expected. |
| 4 | **HIGH** | FR-002 provisioner logs could contain secret ARN values (DASHBOARD_API_KEY_SECRET_ARN, JWT_SECRET, etc.) if the merge step echoes the full env var set. | **Resolved**: FR-002 updated to suppress command output. |
| 5 | **MEDIUM** | SC-004 (merge safety) difficult to test in CI — requires two sequential `terraform apply` runs. | **Resolved**: Add unit test for the merge script in isolation (bash test that verifies JSON merge produces expected output). |
| 6 | **MEDIUM** | FR-005 runtime validation adds code to Lambda handler hot path. If validation is slow (e.g., regex checks), it adds latency to every invocation. | **Resolved**: Validation runs once at module import time (cold start only), not per-invocation. Uses simple `os.environ.get()` + `len() > 0` check. |
| 7 | **LOW** | EC-002 (Amplify disabled) — spec says "use `count` conditional or `try()`" but doesn't specify which. Ambiguity. | **Resolved**: Use `count = var.enable_amplify ? 1 : 0` on the wiring resource. Consistent with existing Amplify module pattern. |
| 8 | **LOW** | FR-007 (CloudTrail monitoring) adds operational complexity. May generate false positives if devs test locally. | **Accepted**: CloudTrail rule should filter by source IP (CI runner CIDR) or IAM role. False positives are acceptable initially — tune threshold after first week. |

### Spec Edits Made
- FR-002: Added items 5-7 (process substitution, suppress output, read-back verification)
- FR-003: Added `ignore_environment_changes` variable mechanism

### Gate Statement
**0 CRITICAL remaining, 0 HIGH remaining.** All findings resolved. Spec passes AR#1.

## Clarifications

### Q1: Does the Lambda module already have `ignore_changes`?
**Answer**: Yes. `modules/lambda/main.tf:108-110` already has `lifecycle { ignore_changes = [image_uri] }`. We add `environment` to this list: `ignore_changes = [image_uri, environment]`.
**Evidence**: Direct code inspection of `modules/lambda/main.tf`.

### Q2: Does the CI role already have `lambda:UpdateFunctionConfiguration`?
**Answer**: Yes. `ci-user-policy.tf:50` already includes it, scoped to `arn:aws:lambda:*:*:function:*-sentiment-*`. Both `GetFunctionConfiguration` (line 53) and `UpdateFunctionConfiguration` (line 50) are present.
**Evidence**: Direct code inspection of `ci-user-policy.tf`.
**Impact on plan**: FR-004 (IAM permission) is already satisfied. The resource scoping (`*-sentiment-*`) is sufficient. No IAM changes needed.

### Q3: Is the `update-function-configuration` replace-all behavior documented?
**Answer**: Yes, extensively. Feature 1219 (X-Ray) documented this as R22/FR-181 — `update-function-configuration` REPLACES ALL env vars, not merge. The capture-first procedure is already a known best practice in this codebase.
**Evidence**: `specs/1219-xray-exclusive-tracing/spec.md:934`, `docs/x-ray/HL-x-ray-remediation-checklist.md:749`.
**Impact on plan**: Validates the merge-not-replace approach. The codebase already knows this danger — our wiring script is the correct pattern.

### Q4: Does the `notification_lambda` depends_on include `amplify_frontend`?
**Answer**: Yes. `main.tf:611` has `depends_on = [module.iam, module.amplify_frontend]`. This explicit `depends_on` must be removed as part of breaking the cycle (the env var reference is already removed). The only remaining dependency is `module.iam`.
**Evidence**: Direct code inspection.

### Q5: Are there other cross-module env var references that could create future cycles?
**Answer**: Checked all Lambda environment_variables blocks. No other cross-module references form cycles. `module.sse_streaming_lambda.function_url` in dashboard_lambda env vars is a one-directional dependency (dashboard → SSE, SSE doesn't reference dashboard).
**Evidence**: Full grep of `module.` references within environment_variables blocks in main.tf.

All 5 questions self-answered from codebase. No deferred questions for user.
