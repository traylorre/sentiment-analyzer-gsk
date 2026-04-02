# Feature 1305: Implementation Plan

## Technical Context

### Current State (Broken)

```
Root main.tf (line 829):
  lambda_invoke_arn = module.dashboard_lambda.invoke_arn
                      ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
                      This is aws_lambda_function.this.invoke_arn
                      = arn:aws:apigateway:...:function:preprod-sentiment-dashboard/invocations
                      (invokes $LATEST, no qualifier)

API Gateway permission (line 722):
  qualifier = "live"
  => Only allows invoke of function:preprod-sentiment-dashboard:live

Result: API Gateway invokes unqualified ARN -> permission denies -> 500
```

### Target State (Fixed)

```
Root main.tf (line 829):
  lambda_invoke_arn = module.dashboard_lambda.alias_invoke_arn
                      ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
                      This is aws_lambda_alias.live.invoke_arn
                      = arn:aws:apigateway:...:function:preprod-sentiment-dashboard:live/invocations
                      (invokes via "live" alias qualifier)

API Gateway permission (line 722):
  qualifier = "live"  (unchanged)
  => Allows invoke of function:preprod-sentiment-dashboard:live

Result: API Gateway invokes alias ARN -> permission allows -> 200
```

### Architecture Diagram

```
Before (broken):
  Client -> API GW -> Integration URI (unqualified) -> Lambda permission (alias only) -> DENIED

After (fixed):
  Client -> API GW -> Integration URI (:live alias) -> Lambda permission (alias) -> ALLOWED -> Lambda :live
```

## Implementation Steps

### Step 1: Add `alias_invoke_arn` output to Lambda module

**File**: `infrastructure/terraform/modules/lambda/outputs.tf`
**Action**: Add new output after line 17 (after existing `invoke_arn` output)

```hcl
output "alias_invoke_arn" {
  description = "Invoke ARN for the live alias (use this for API Gateway integrations)"
  value       = aws_lambda_alias.live.invoke_arn
}
```

**Rationale**: The alias resource is unconditional (Feature 1300), so no conditional logic needed. Preserves existing `invoke_arn` output for backward compatibility.

### Step 2: Update root main.tf to pass alias ARN

**File**: `infrastructure/terraform/main.tf`
**Action**: Change line 829

```hcl
# Before:
lambda_invoke_arn    = module.dashboard_lambda.invoke_arn

# After:
lambda_invoke_arn    = module.dashboard_lambda.alias_invoke_arn
```

**Rationale**: This is the single-line root cause fix. All 6 integration resources in the api_gateway module already reference `var.lambda_invoke_arn`, so they automatically pick up the alias ARN.

### Step 3: Update deployment trigger to include URI content

**File**: `infrastructure/terraform/modules/api_gateway/main.tf`
**Action**: Add `var.lambda_invoke_arn` to the deployment trigger hash at line 742

```hcl
# Before (line 741-754):
redeployment = sha1(jsonencode(concat(
  [
    aws_api_gateway_resource.proxy.id,
    ...
  ],
  local.public_route_resource_ids,
)))

# After:
redeployment = sha1(jsonencode(concat(
  [
    var.lambda_invoke_arn,
    aws_api_gateway_resource.proxy.id,
    ...
  ],
  local.public_route_resource_ids,
)))
```

**Rationale**: Ensures any change to the integration URI forces a new API Gateway deployment, even if the integration resource IDs remain the same (in-place update). This is a defense-in-depth measure identified in Adversarial Review #1 (AR1-2).

### Step 4: Verify with terraform plan

**Action**: Run `terraform plan` and verify:
- Lambda module: 1 new output (`alias_invoke_arn`)
- API Gateway module: 6 integration resources updated (URI change)
- API Gateway: 1 deployment resource replaced (trigger hash change)
- **Zero** Lambda function or alias changes
- **Zero** permission resource changes

### Step 5: Apply and smoke test

**Action**: Run `terraform apply`, then verify:
```bash
curl -s -o /dev/null -w '%{http_code}' https://<api-gw-url>/v1/health
# Expected: 200

curl -s -o /dev/null -w '%{http_code}' https://<api-gw-url>/v1/api/v2/auth/anonymous
# Expected: 200 (or appropriate auth response, NOT 500)
```

## Data Model Changes

None. This is purely an infrastructure wiring fix.

## Files Changed

| File | Change Type | Lines Affected |
|------|-------------|----------------|
| `infrastructure/terraform/modules/lambda/outputs.tf` | ADD | New output after line 17 |
| `infrastructure/terraform/main.tf` | MODIFY | Line 829 |
| `infrastructure/terraform/modules/api_gateway/main.tf` | MODIFY | Line 742 (add to trigger array) |

## Rollback Plan

### Rollback Steps
1. Revert line 829 in `main.tf`: change `alias_invoke_arn` back to `invoke_arn`
2. Remove `var.lambda_invoke_arn` from deployment trigger hash (line 742)
3. Run `terraform apply`
4. **WARNING**: This restores the 500 error bug. Only roll back if the fix introduces a worse problem (e.g., alias-related permission issue in a different environment).

### Rollback Risk
LOW. The change is additive (new output) + a single-line wiring change. The rollback restores the known-broken state, which is the pre-existing condition.

### Safer Rollback Alternative
If the alias invoke ARN causes issues in a specific environment, the safer fix is to add a second `aws_lambda_permission` for the unqualified function (without `qualifier`) rather than reverting the URI change. This would allow both qualified and unqualified invocations.

## Risk Assessment

| Risk | Probability | Impact | Mitigation |
|------|-------------|--------|------------|
| In-place update misses deployment trigger | Medium | HIGH (stale deployment) | Step 3 adds URI to trigger hash |
| Integration URI change causes brief 500 during apply | Low | LOW (seconds, create_before_destroy) | `create_before_destroy` on deployment resource |
| Other modules depend on unqualified `invoke_arn` | Low | LOW (output preserved) | FR-005: existing output unchanged |
| CI/CD alias-flip conflicts with apply | Very Low | LOW | `ignore_changes` on alias version |
| Alias does not exist at plan time | Very Low | NONE (plan fails clearly) | Alias is unconditional per Feature 1300 |

## Dependencies

- Feature 1300: Lambda alias unconditionally created (already merged)
- Feature 1224.4: Lambda alias `live` exists (already merged)
- Feature 1253: Public routes configuration (already merged, no conflicts)
- Feature 1295: Lambda permission uses `qualifier = "live"` (already merged, this fix completes the intent)

## Adversarial Review #2

### Review Date: 2026-04-02

### Drift Analysis: Spec vs Plan

| Check | Result | Notes |
|-------|--------|-------|
| FR-001 maps to implementation step | PASS | Step 1 adds `alias_invoke_arn` output |
| FR-002 maps to implementation step | PASS | Step 2 changes line 829 |
| FR-003 covered (no-op verification) | PASS | Plan notes 6 integrations auto-inherit |
| FR-004 covered (no-change guard) | PASS | Plan explicitly lists zero permission changes expected |
| FR-005 covered (preserve existing) | PASS | Step 1 adds new output, does not modify existing |
| NFR-001 covered | PASS | Step 4 verification includes zero Lambda/alias changes |
| NFR-002 covered | PASS | Steps 4-5 describe standard plan+apply |
| NFR-003 covered | PASS | Step 3 adds URI to trigger hash |
| NFR-004 covered | PASS | No new variables in api_gateway module |
| Edge cases reflected in risks | PASS | All 5 edge cases map to risk table rows |
| Clarifications reflected in plan | PASS | Q3 confirms Step 3 necessity |
| Rollback plan complete | PASS | Includes warning about restoring broken state |

### Findings

| # | Severity | Finding | Resolution |
|---|----------|---------|------------|
| AR2-1 | LOW | Rollback plan says "Remove `var.lambda_invoke_arn` from trigger hash" but the output addition (Step 1) doesn't need reverting. This could confuse operators. | ACCEPTED: The rollback plan correctly focuses on the breaking changes only. The output addition is harmless to leave in place. Plan is clear enough. |
| AR2-2 | LOW | Plan Step 4 says "1 new output" but terraform plan will show the output as a change on the module, not as a separate resource. | ACCEPTED: Minor wording nuance. The intent is clear. |
| AR2-3 | INFO | No Terraform test (`.tftest.hcl`) is specified. This is acceptable for a 3-file wiring fix but worth noting. | ACCEPTED: The fix is trivially verifiable via `terraform plan` output inspection. No test infrastructure needed. |

### Gate: PASS

No drift detected between spec and plan. All requirements traceable to implementation steps. No new artifacts needed (Stage 6 skipped).
