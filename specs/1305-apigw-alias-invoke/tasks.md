# Feature 1305: Tasks

## Implementation Tasks

### Task 1: Add `alias_invoke_arn` output to Lambda module
- **File**: `infrastructure/terraform/modules/lambda/outputs.tf`
- **Action**: Add new output block after the existing `invoke_arn` output (after line 17)
- **Code**:
  ```hcl
  output "alias_invoke_arn" {
    description = "Invoke ARN for the live alias (use this for API Gateway integrations)"
    value       = aws_lambda_alias.live.invoke_arn
  }
  ```
- **Validates**: FR-001, FR-005 (existing output preserved)
- **Dependencies**: None
- **Risk**: None (purely additive)

### Task 2: Wire alias ARN to API Gateway module
- **File**: `infrastructure/terraform/main.tf`
- **Action**: Change line 829 from `invoke_arn` to `alias_invoke_arn`
- **Before**: `lambda_invoke_arn    = module.dashboard_lambda.invoke_arn`
- **After**: `lambda_invoke_arn    = module.dashboard_lambda.alias_invoke_arn`
- **Validates**: FR-002, FR-003 (6 integrations auto-inherit), NFR-004 (no interface change)
- **Dependencies**: Task 1 (output must exist)
- **Risk**: This is the root cause fix. Without Task 1, this fails at plan time.

### Task 3: Add integration URI to deployment trigger hash
- **File**: `infrastructure/terraform/modules/api_gateway/main.tf`
- **Action**: Add `var.lambda_invoke_arn` as the first element in the trigger hash array (line 743)
- **Before** (line 742-743):
  ```hcl
  redeployment = sha1(jsonencode(concat(
    [
      aws_api_gateway_resource.proxy.id,
  ```
- **After**:
  ```hcl
  redeployment = sha1(jsonencode(concat(
    [
      var.lambda_invoke_arn,  # Feature 1305: Force redeploy on integration URI change
      aws_api_gateway_resource.proxy.id,
  ```
- **Validates**: NFR-003 (deployment trigger fires on URI change)
- **Dependencies**: None (can be done in parallel with Tasks 1-2)
- **Risk**: Changes deployment trigger hash, forcing an API Gateway redeployment on next apply. This is intentional.

### Task 4: Run `terraform plan` and verify expected changes
- **Action**: Execute `terraform plan` in the preprod workspace
- **Expected output**:
  - `module.dashboard_lambda`: output added (`alias_invoke_arn`)
  - `module.api_gateway.aws_api_gateway_integration.lambda_proxy`: URI updated (`:live` suffix)
  - `module.api_gateway.aws_api_gateway_integration.lambda_root`: URI updated (`:live` suffix)
  - `module.api_gateway.aws_api_gateway_integration.fr012_lambda[*]`: URI updated
  - `module.api_gateway.aws_api_gateway_integration.public_leaf_lambda[*]`: URI updated
  - `module.api_gateway.aws_api_gateway_integration.public_proxy_lambda[*]`: URI updated
  - `module.api_gateway.aws_api_gateway_integration.fr012_proxy_lambda[*]`: URI updated
  - `module.api_gateway.aws_api_gateway_deployment.dashboard`: replaced (trigger hash changed)
  - Zero Lambda function/alias/permission changes
- **Abort criteria**: Any Lambda function recreation, alias destruction, or permission changes
- **Validates**: NFR-001, NFR-002, Success Criteria #1
- **Dependencies**: Tasks 1, 2, 3

### Task 5: Apply and smoke test
- **Action**: Execute `terraform apply`, then run:
  ```bash
  # Health check
  curl -s -o /dev/null -w '%{http_code}' https://<api-gw-url>/v1/health
  # Expected: 200

  # Anonymous auth
  curl -s -o /dev/null -w '%{http_code}' https://<api-gw-url>/v1/api/v2/auth/anonymous
  # Expected: 200 (or auth response, NOT 500)
  ```
- **Validates**: Success Criteria #2-5
- **Dependencies**: Task 4 (plan verified)

## Dependency Graph

```
Task 1 ──┐
         ├──> Task 4 ──> Task 5
Task 2 ──┘       ▲
                  │
Task 3 ───────────┘
```

Tasks 1+2 are sequential (2 depends on 1). Task 3 is independent. All three must complete before Task 4.

## Estimated Effort

| Task | Effort | Notes |
|------|--------|-------|
| Task 1 | 2 min | Add 4 lines to outputs.tf |
| Task 2 | 1 min | Change 1 word on 1 line |
| Task 3 | 1 min | Add 1 line to trigger array |
| Task 4 | 5 min | Terraform plan + review |
| Task 5 | 10 min | Apply + smoke test |
| **Total** | **~19 min** | |

## Adversarial Review #3

### Review Date: 2026-04-02

### Cross-Artifact Consistency

| Check | Result | Notes |
|-------|--------|-------|
| Every FR has a task | PASS | FR-001->T1, FR-002->T2, FR-003->T2 (auto), FR-004->T4 (verify), FR-005->T1 |
| Every NFR has a task | PASS | NFR-001->T4, NFR-002->T4, NFR-003->T3, NFR-004->T2 |
| Task dependencies correct | PASS | T2 depends on T1, T4 depends on T1+T2+T3, T5 depends on T4 |
| Plan steps map to tasks | PASS | Steps 1-5 map to Tasks 1-5 1:1 |
| Edge cases covered | PASS | EC-1: T4 abort criteria, EC-4: T3, EC-2/3/5: documented in spec |
| Rollback documented | PASS | In plan.md, not duplicated in tasks |

### Risk Assessment

| Risk | Probability | Impact | Status |
|------|-------------|--------|--------|
| Wrong output attribute name | Very Low | Plan fails clearly | MITIGATED: `invoke_arn` is a documented Terraform attribute on `aws_lambda_alias` |
| Deployment trigger hash collision | Negligible | Stale deployment | MITIGATED: SHA1 of full content array |
| Apply during traffic spike | Low | Brief elevated error rate | MITIGATED: `create_before_destroy` on deployment |
| Missing `for_each` integration URIs | None | N/A | All 6 integrations use `var.lambda_invoke_arn` (verified by grep) |

### Final Checklist

- [x] Spec complete with requirements, edge cases, out of scope
- [x] AR#1 resolved all CRITICAL and HIGH findings
- [x] Plan has exact file paths and line numbers
- [x] AR#2 found no drift between spec and plan
- [x] Tasks are ordered with correct dependencies
- [x] Effort estimate is realistic (3 file changes, ~19 min total)
- [x] No scope creep (3 files modified, 0 new files beyond outputs)
- [x] Rollback plan documented with warning about restoring broken state

### Gate: READY

Feature 1305 is ready for implementation. Three files, minimal blast radius, clear verification criteria.
