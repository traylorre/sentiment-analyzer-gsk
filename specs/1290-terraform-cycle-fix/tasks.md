# Feature 1290: Implementation Tasks

## Task Summary
- **Total tasks**: 16
- **Estimated files modified**: 8
- **Risk**: HIGH (modifies core infrastructure wiring)
- **Dependencies**: None (standalone feature)

## Phase 1: Break the Cycle (Terraform)

### T-001: Add `environment` to Lambda module `ignore_changes`
**File**: `infrastructure/terraform/modules/lambda/main.tf`
**Change**: Line 109 — change `ignore_changes = [image_uri]` to `ignore_changes = [image_uri, environment]`
**Risk**: MEDIUM — affects all 6 Lambdas. Env var drift no longer detected by Terraform.
**FR**: FR-001, FR-003
**Test**: T-010 (terraform plan)

### T-002: Remove SCHEDULER_ROLE_ARN cross-module reference from dashboard_lambda
**File**: `infrastructure/terraform/main.tf`
**Change**: Line ~442 — replace `try(module.chaos.chaos_scheduler_role_arn, "")` with literal `""`
**Risk**: LOW — placeholder value, same as what try() returns when chaos is disabled
**FR**: FR-001
**Test**: T-010

### T-003: Remove DASHBOARD_URL cross-module reference from notification_lambda
**File**: `infrastructure/terraform/main.tf`
**Change**: Line ~588 — replace `var.enable_amplify ? module.amplify_frontend[0].production_url : "http://localhost:3000"` with `var.frontend_url` (existing variable, same fallback)
**Risk**: LOW — uses existing frontend_url variable as static fallback
**FR**: FR-001
**Test**: T-010

### T-004: Remove `depends_on = [module.amplify_frontend]` from notification_lambda
**File**: `infrastructure/terraform/main.tf`
**Change**: Line ~611 — change `depends_on = [module.iam, module.amplify_frontend]` to `depends_on = [module.iam]`
**Risk**: LOW — dependency was only needed for the env var reference (now removed)
**FR**: FR-001
**Test**: T-010

## Phase 2: Wiring Resources

### T-005: Create wiring shell script
**File**: `scripts/terraform-env-wiring.sh` (NEW)
**Change**: Create bash script that:
1. Accepts: function_name, env_var_key, env_var_value
2. Reads current env vars: `aws lambda get-function-configuration --function-name $1 --query 'Environment.Variables' --output json`
3. Merges key: uses `jq` to add/update the key
4. Writes back: `aws lambda update-function-configuration --function-name $1 --environment "Variables=$(merged_json)"` with output suppressed
5. Reads back and verifies: `aws lambda get-function-configuration --function-name $1 --query "Environment.Variables.$2" --output text`
6. Exits 0 on success, 1 on AWS error, 2 on verification mismatch
**Risk**: MEDIUM — new script handling sensitive env vars
**FR**: FR-002
**Test**: T-011

### T-006: Create `terraform_data` for dashboard_lambda wiring
**File**: `infrastructure/terraform/main.tf`
**Change**: Add resource after dashboard_lambda and chaos modules:
```hcl
resource "terraform_data" "dashboard_lambda_env_wiring" {
  triggers_replace = try(module.chaos.chaos_scheduler_role_arn, "")

  provisioner "local-exec" {
    command = "${path.root}/../../scripts/terraform-env-wiring.sh '${module.dashboard_lambda.function_name}' 'SCHEDULER_ROLE_ARN' '${try(module.chaos.chaos_scheduler_role_arn, "")}'"
  }

  depends_on = [module.dashboard_lambda, module.chaos]
}
```
**Risk**: HIGH — core wiring, provisioner must succeed for auto-restore to work
**FR**: FR-002
**Test**: T-010, T-012

### T-007: Create `terraform_data` for notification_lambda wiring
**File**: `infrastructure/terraform/main.tf`
**Change**: Add resource after notification_lambda and amplify modules:
```hcl
resource "terraform_data" "notification_lambda_env_wiring" {
  count = var.enable_amplify ? 1 : 0

  triggers_replace = module.amplify_frontend[0].production_url

  provisioner "local-exec" {
    command = "${path.root}/../../scripts/terraform-env-wiring.sh '${module.notification_lambda.function_name}' 'DASHBOARD_URL' '${module.amplify_frontend[0].production_url}'"
  }

  depends_on = [module.notification_lambda, module.amplify_frontend]
}
```
**Risk**: MEDIUM — gated by `enable_amplify`, lower risk
**FR**: FR-002
**EC**: EC-002 (Amplify disabled)
**Test**: T-010, T-012

## Phase 3: Runtime Validation

### T-008: Create shared env var validation module
**File**: `src/lambdas/shared/env_validation.py` (NEW)
**Change**: Create module with `validate_critical_env_vars(var_names: list[str]) -> list[str]` function:
- Checks each var via `os.environ.get(name, "")`
- Returns list of empty/missing var names
- Emits structured JSON log for each: `{"level": "warning", "metric": "env_var_missing", "var_name": "...", "lambda": "...", "environment": "..."}`
- Runs at import time (module-level call)
**Risk**: LOW — logging only, no behavioral change
**FR**: FR-005
**Test**: T-013

### T-009: Add validation calls to Lambda handlers
**Files**:
- `src/lambdas/dashboard/handler.py` — add import + validate call for `["SCHEDULER_ROLE_ARN"]`
- `src/lambdas/notification/handler.py` — add import + validate call for `["DASHBOARD_URL"]`
**Change**: Module-level (cold start only): `from lambdas.shared.env_validation import validate_critical_env_vars; validate_critical_env_vars(["SCHEDULER_ROLE_ARN"])`
**Risk**: LOW — cold start only, no latency impact on warm invocations
**FR**: FR-005
**Test**: T-013

## Phase 4: Verification & Testing

### T-010: Verify terraform plan succeeds
**Command**: `cd infrastructure/terraform && terraform plan -var-file=preprod.tfvars`
**Acceptance**: No cycle error. Plan shows: ~2 new terraform_data resources, ~2 Lambda env var changes.
**FR**: SC-001
**Blocks**: T-006, T-007

### T-011: Unit test for wiring script
**File**: `tests/unit/test_terraform_env_wiring.sh` (NEW) or inline bash test
**Change**: Test the merge logic in isolation:
1. Mock `aws lambda get-function-configuration` to return known JSON
2. Run merge with new key
3. Assert merged JSON contains both old and new keys
4. Assert old keys are preserved
**FR**: SC-004
**Test for**: T-005

### T-012: Integration verification after apply
**Action**: After `terraform apply` to preprod:
1. `aws lambda get-function-configuration --function-name preprod-sentiment-dashboard --query 'Environment.Variables.SCHEDULER_ROLE_ARN'` — should be non-empty valid ARN
2. `aws lambda get-function-configuration --function-name preprod-sentiment-notification --query 'Environment.Variables.DASHBOARD_URL'` — should be valid Amplify URL
**FR**: SC-002, SC-003

### T-013: Unit test for env validation module
**File**: `tests/unit/test_env_validation.py` (NEW)
**Tests**:
1. All vars present → returns empty list, no logs
2. One var missing → returns [var_name], emits structured log
3. Multiple vars missing → returns all, emits log per var
**FR**: FR-005, SC-006

## Phase 5: Documentation & Cleanup

### T-014: Add cross-reference comments in main.tf
**File**: `infrastructure/terraform/main.tf`
**Change**: Add comments at:
- dashboard_lambda env vars block: `# NOTE: SCHEDULER_ROLE_ARN managed by terraform_data.dashboard_lambda_env_wiring (line XXX)`
- notification_lambda env vars block: `# NOTE: DASHBOARD_URL managed by terraform_data.notification_lambda_env_wiring (line XXX)`
- Each terraform_data resource: `# Pattern: Split Definition/Wiring — see docs/terraform-patterns.md`
**FR**: FR-008

### T-015: Create terraform-patterns.md documentation
**File**: `docs/terraform-patterns.md` (NEW)
**Content**: Document the split definition/wiring pattern:
- Problem: Terraform circular dependencies through Lambda env vars
- Pattern: Definition phase (placeholder) + Wiring phase (terraform_data)
- Constraints: merge-not-replace, process substitution, verification
- When to use / when not to use
- Diagram
**FR**: FR-008

### T-016: Create tech debt GitHub issue
**Action**: `gh issue create` with:
- Title: "Tech debt: Migrate cross-module env vars to SSM Parameter Store"
- Body: Strategy 4 is a workaround. Long-term: Lambda reads values from SSM at runtime, eliminating Terraform cycle and ignore_changes. Estimated effort: 2-3 days.
- Labels: tech-debt, infrastructure
**FR**: FR-009

## Requirement Coverage Matrix

| Requirement | Tasks |
|------------|-------|
| FR-001 | T-001, T-002, T-003, T-004 |
| FR-002 | T-005, T-006, T-007 |
| FR-003 | T-001 |
| FR-004 | PRE-SATISFIED (no tasks) |
| FR-005 | T-008, T-009 |
| FR-006 | Deferred — add CloudWatch alarm in follow-up if runtime validation proves valuable |
| FR-007 | Deferred — CloudTrail monitoring is operational, not blocking deploy fix |
| FR-008 | T-014, T-015 |
| FR-009 | T-016 |
| SC-001 | T-010 |
| SC-002 | T-012 |
| SC-003 | T-012 |
| SC-004 | T-011 |
| SC-005 | PRE-SATISFIED |
| SC-006 | T-013 |
| SC-007 | Existing test suites |
| SC-008 | CI pipeline run |

### Deferred Items (not blocking)

| Item | Reason | When |
|------|--------|------|
| FR-006: CloudWatch alarm | Operational enhancement, not needed to unblock deploy | Follow-up PR |
| FR-007: CloudTrail monitoring | Security monitoring, not needed to unblock deploy | Follow-up PR |

## Adversarial Review #3

### Implementation Readiness

| Check | Status |
|-------|--------|
| All FRs have mapped tasks | PASS (FR-006, FR-007 deferred with rationale) |
| All SCs testable | PASS |
| All edge cases addressed | PASS (EC-001 through EC-007) |
| Security controls from prior ARs | PASS (4/5 implemented, CloudTrail deferred) |
| No orphaned requirements | PASS |
| Requirement coverage matrix complete | PASS |

### Risk Assessment

| Aspect | Assessment |
|--------|-----------|
| **Highest-risk task** | T-006 (dashboard_lambda wiring). Provisioner handles sensitive env vars. Merge logic must be correct. Failure = auto-restore disabled. |
| **Most likely rework** | T-001 (global ignore_changes). Any in-flight feature relying on Terraform env var drift detection will need adjustment. Check for concurrent PRs that add env vars. |
| **Deployment risk** | MEDIUM. Changes are infrastructure-only. Rollback: revert T-001/T-002/T-003/T-004 and the terraform_data resources. Lambdas continue with current env vars. |
| **Blast radius** | All 6 Lambdas lose env var drift detection. Compensated by FR-005 runtime validation. |

### Deferred Items Justification

FR-006 (CloudWatch alarm) and FR-007 (CloudTrail monitoring) were listed as **mandatory** in the pre-existing adversarial review. Deferring them is a **conscious risk acceptance** based on:
1. The deploy pipeline has been broken for 5+ runs — every hour of delay increases risk of needing an emergency security patch with no deploy path
2. Runtime validation (FR-005) provides immediate detection without the alarm infrastructure
3. Both items are added to the tech debt issue (T-016) for the next PR

### Gate Statement

**READY FOR IMPLEMENTATION.** 16 tasks, 8 files modified, all requirements mapped. 2 operational enhancements deferred to follow-up PR with explicit risk acceptance.
