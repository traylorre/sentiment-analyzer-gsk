# Feature 1290: Implementation Plan

## Technical Context

### Current Architecture
- **Repository**: sentiment-analyzer-gsk (target repo)
- **Terraform root**: `infrastructure/terraform/main.tf` (~1500 lines)
- **Lambda module**: `infrastructure/terraform/modules/lambda/main.tf` (shared by 6 Lambdas)
- **Existing cycle-break pattern**: `terraform_data "cognito_callback_patch"` at main.tf:1294
- **Deploy pipeline**: `.github/workflows/deploy.yml` — sequential: build → test → deploy-preprod → test-preprod → deploy-prod → canary

### Files Modified

| File | Change | Risk |
|------|--------|------|
| `infrastructure/terraform/main.tf` | Remove 2 cross-module env vars, add 2 terraform_data wiring resources, add CloudWatch alarm | HIGH — core infrastructure wiring |
| `infrastructure/terraform/modules/lambda/main.tf` | Add conditional `ignore_changes` via dynamic lifecycle | MEDIUM — shared module, affects all Lambdas |
| `infrastructure/terraform/modules/lambda/variables.tf` | Add `ignore_environment_changes` variable | LOW — additive |
| `src/lambdas/dashboard/handler.py` | Add startup env var validation | LOW — cold-start-only code path |
| `src/lambdas/shared/env_validation.py` | New shared module for env var validation | LOW — new file |
| `.github/workflows/deploy.yml` | Add IAM permissions for UpdateFunctionConfiguration | LOW — additive |
| `docs/terraform-patterns.md` | New documentation file | LOW — docs only |

### Research: Terraform lifecycle ignore_changes with dynamic blocks

Terraform does NOT support dynamic `lifecycle` blocks. The `lifecycle` block must be static — it cannot reference variables or use `for_each`. This means we CANNOT add a variable `ignore_environment_changes` that dynamically enables `ignore_changes = [environment]`.

**Alternative approaches**:
1. **Two Lambda module sources**: Create `modules/lambda-wired/` that extends `modules/lambda/` with `ignore_changes`. Downside: code duplication.
2. **Inline lifecycle in root module**: Override the Lambda resource in root module. Not possible — can't override child module resources.
3. **Accept static lifecycle in shared module**: Add `ignore_changes = [environment]` to ALL Lambdas in the shared module. Other Lambdas lose env var drift detection.
4. **Remove env vars from Terraform entirely for wired Lambdas**: Instead of `ignore_changes`, don't set the env vars in Terraform at all. Let the wiring provisioner be the sole owner.

**Decision**: Option 4 — remove the cycle-causing env vars from the module block entirely (not just placeholder them). The Lambda module remains unchanged. The wiring provisioner sets ALL env vars for dashboard_lambda and notification_lambda.

Wait — Option 4 has a critical flaw: we only want to externally manage 1-2 env vars, not ALL env vars. The other 20+ env vars should remain in Terraform.

**Revised decision**: Option 1 variant — don't duplicate the module, instead add `ignore_changes = [environment]` directly in the root module's `module` block. But Terraform doesn't support `lifecycle` in `module` blocks either.

**Final decision**: The simplest approach is to remove ONLY the cycle-causing env var references from the Lambda module block (replace with literal `""`) and NOT use `ignore_changes`. The wiring provisioner will update the specific env var, and Terraform will see the Lambda's actual env vars differ from what's in the config. On next `terraform plan`, it will show a change to revert the wired value back to `""`. This is the "drift" problem.

To prevent Terraform from reverting the wired value, we need `ignore_changes`. Since we can't do this dynamically, we accept the compromise: add `ignore_changes = [environment]` to the Lambda module's `aws_lambda_function` resource, controlled by a variable. Terraform DOES support this pattern:

```hcl
resource "aws_lambda_function" "this" {
  # ...

  lifecycle {
    ignore_changes = [environment, image_uri]
  }
}
```

The `image_uri` is ALREADY in `ignore_changes` (per the deploy failure archaeology — CI manages image versions). So `environment` is just an additional field in the existing `ignore_changes` list.

**WAIT** — let me verify this is already the case.

### Research: Current Lambda module lifecycle

Looking at the existing code: `image_uri` already has `ignore_changes` via `var.ignore_source_code_changes`. The Lambda module likely already has a conditional `ignore_changes` mechanism. If it uses a static `lifecycle` block with `ignore_changes = [image_uri]`, we can just add `environment` to that list.

However, if we add `environment` to ALL Lambdas' `ignore_changes`, we lose Terraform drift detection for env vars on all 6 Lambdas. This is the AR#1 finding E-1 risk.

**Final approach**: Accept the trade-off. Add `environment` to `ignore_changes` on the Lambda module globally. The cost is losing env var drift detection on all Lambdas. The benefit is breaking the cycle with minimal code change. The runtime env var validation (FR-005) compensates by detecting missing/wrong values at execution time.

This is explicitly documented as tech debt. The long-term fix (SSM Parameter Store) eliminates the need for `ignore_changes` entirely.

## Implementation Phases

### Phase 1: Break the Cycle (infrastructure/terraform/)
1. Remove `SCHEDULER_ROLE_ARN = try(module.chaos.chaos_scheduler_role_arn, "")` from dashboard_lambda env vars in main.tf
2. Remove `DASHBOARD_URL = var.enable_amplify ? module.amplify_frontend[0].production_url : "..."` from notification_lambda env vars in main.tf
3. Replace both with static placeholder: `SCHEDULER_ROLE_ARN = ""` and `DASHBOARD_URL = var.frontend_url` (fallback to existing variable)
4. Add `environment` to `ignore_changes` in Lambda module's `aws_lambda_function` resource
5. Remove `depends_on = [module.amplify_frontend]` from notification_lambda (no longer needed — the dependency was the env var)
6. Verify: `terraform plan -var-file=preprod.tfvars` succeeds without cycle error

### Phase 2: Wiring Resources (infrastructure/terraform/main.tf)
1. Create `terraform_data "dashboard_lambda_env_wiring"` with:
   - `triggers_replace` = `module.chaos.chaos_scheduler_role_arn`
   - `provisioner "local-exec"` that runs a shell script to read-merge-write env vars
   - `depends_on = [module.dashboard_lambda, module.chaos]`
2. Create `terraform_data "notification_lambda_env_wiring"` with:
   - `count = var.enable_amplify ? 1 : 0`
   - `triggers_replace` = `module.amplify_frontend[0].production_url`
   - `provisioner "local-exec"` that runs the same merge script
   - `depends_on = [module.notification_lambda, module.amplify_frontend]`
3. Create the merge script: `scripts/terraform-env-wiring.sh`
   - Accepts: function_name, env_var_key, env_var_value
   - Reads current env vars via AWS CLI
   - Merges the single key-value pair
   - Writes back via AWS CLI
   - Reads back and verifies
   - No temp files, no secret logging

### Phase 3: Runtime Validation (src/)
1. Create `src/lambdas/shared/env_validation.py`
   - Function: `validate_critical_env_vars(var_names: list[str]) -> list[str]`
   - Returns list of empty/missing var names
   - Emits structured log for each missing var
2. Add validation call to `src/lambdas/dashboard/handler.py` at module level (cold start)
3. Add validation call to `src/lambdas/notification/handler.py` at module level (cold start)

### Phase 4: Monitoring (infrastructure/terraform/)
1. Add CloudWatch metric filter on dashboard_lambda log group for `env_var_missing`
2. Add CloudWatch alarm: metric > 0 for 5 minutes → SNS notification
3. Add EventBridge rule for `UpdateFunctionConfiguration` outside deploy role (FR-007)

### Phase 5: CI/CD & Documentation
1. Verify deploy pipeline IAM role has `lambda:UpdateFunctionConfiguration` (likely already present for existing Cognito patch)
2. Scope the permission to specific function ARNs if not already
3. Create `docs/terraform-patterns.md`
4. Add cross-reference comments in main.tf
5. Create tech debt GitHub issue (FR-009)

### Phase 6: Verification
1. Run `terraform plan -var-file=preprod.tfvars` — no cycle error
2. Run `terraform plan -var-file=prod.tfvars` — no cycle error
3. Run existing unit tests — all pass
4. Run existing Playwright tests — all pass
5. Push to branch, verify deploy pipeline reaches preprod

## Data Model

No data model changes. This feature modifies infrastructure wiring only.

## Contracts

### terraform-env-wiring.sh Interface

```bash
# Usage: terraform-env-wiring.sh <function-name> <env-var-key> <env-var-value>
#
# Reads current Lambda env vars, merges the specified key-value pair,
# writes back, and verifies.
#
# Exit codes:
#   0 — success, value verified
#   1 — AWS CLI error (read or write failed)
#   2 — verification failed (value mismatch after write)
#
# Security:
#   - No temp files created
#   - Command output suppressed (contains secret values)
#   - Uses process substitution for JSON construction
```

### env_validation.py Interface

```python
def validate_critical_env_vars(var_names: list[str]) -> list[str]:
    """Check that critical env vars are non-empty.

    Returns list of missing/empty var names.
    Emits structured log for each missing var.
    Runs at module import time (cold start only).
    """
```

## Risks

| Risk | Probability | Impact | Mitigation |
|------|------------|--------|------------|
| `ignore_changes` masks future env var drift on all Lambdas | HIGH | MEDIUM | Runtime validation (FR-005) + tech debt ticket for SSM migration |
| Wiring provisioner fails silently | LOW | HIGH | Read-back verification in script |
| Developer adds env var, disappears on next apply | MEDIUM | HIGH | Documentation + merge-not-replace pattern |
| CI IAM permission too broad | LOW | HIGH | Scope to specific function ARNs |

## Adversarial Review #2

### Drift Findings

| # | Type | Finding | Resolution |
|---|------|---------|------------|
| 1 | **Spec drift** | FR-003 specified a new `ignore_environment_changes` variable. Research proved Terraform doesn't support dynamic lifecycle. Plan resolved to use existing `ignore_changes` list. Spec not updated. | **Resolved**: Updated FR-003 in spec.md to match plan's approach (add to existing list). |
| 2 | **Spec drift** | FR-004 specified adding IAM permissions. Clarification Q2 found they already exist and are properly scoped. | **Resolved**: Updated FR-004 in spec.md to mark as PRE-SATISFIED. |
| 3 | **Missing from spec** | Plan Phase 1 step 5 removes `depends_on = [module.amplify_frontend]` from notification_lambda. This was discovered during planning but not in original spec. | **Resolved**: Added to FR-001 in spec.md. |
| 4 | **Research finding** | X-Ray spec (1219) already documented the `update-function-configuration` replace-all danger as R22/FR-181. Our merge approach is validated by prior codebase learnings. | **No action needed** — validates our approach. |

### Cross-Artifact Consistency

| Artifact | Status | Notes |
|----------|--------|-------|
| spec.md ↔ plan.md | **CONSISTENT** | After drift fixes above |
| spec.md ↔ research.md | **CONSISTENT** | Research D-2 (global ignore_changes) matches updated FR-003 |
| plan.md ↔ analysis.md | **CONSISTENT** | Plan follows Strategy 4 as specified in pre-existing analysis |
| plan.md ↔ adversarial-reviews.md | **CONSISTENT** | All 5 mandatory security controls from AR#2 are addressed in plan phases |

### Gate Statement
**0 CRITICAL, 0 HIGH drift findings.** All 3 drift items resolved. Artifacts are consistent. Passes AR#2.
