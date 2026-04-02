# Feature 1305: API Gateway Lambda Alias Invoke ARN Fix

## Status: DRAFT

## Problem Statement

The API Gateway in sentiment-analyzer-gsk returns HTTP 500 on all routes (including unauthenticated routes like `/health` and `/api/v2/auth/anonymous`). The root cause is a mismatch between the API Gateway integration URI and the Lambda permission qualifier:

- **Integration URI**: Points to the **unqualified** Lambda function (`arn:aws:apigateway:...:function:preprod-sentiment-dashboard/invocations`)
- **Lambda permission**: Grants invoke only for the `live` alias qualifier (line 722 of `modules/api_gateway/main.tf`)

API Gateway attempts to invoke the unqualified function ARN, but the permission only allows invoking `function:preprod-sentiment-dashboard:live`. AWS returns `AccessDeniedException`, which API Gateway translates to a 500 response.

## User Stories

### US-1: Health Check Reliability
As an **SRE**, I need the `/health` endpoint to return 200 so that load balancers and uptime monitors correctly report service status, rather than triggering false-positive pages at 3am.

### US-2: Anonymous Auth Flow
As an **operator**, I need `/api/v2/auth/anonymous` and `/api/v2/auth/magic-link` to function so that users can authenticate without hitting a 500 wall before they even get a JWT.

### US-3: All API Routes
As a **developer**, I need all API Gateway routes to invoke the correct Lambda alias so that API Gateway behavior matches the Function URL path (which already uses the `live` alias correctly).

### US-4: Zero-Downtime Deployments
As an **SRE**, I need API Gateway to invoke the `live` alias (not `$LATEST`) so that CI/CD alias-flip deployments work correctly — new code is served only after the alias is updated, not mid-deploy.

## Requirements

### Functional Requirements

| ID | Requirement | Priority |
|----|-------------|----------|
| FR-001 | Lambda module MUST export an `alias_invoke_arn` output containing `aws_lambda_alias.live.invoke_arn` | P0 |
| FR-002 | Root `main.tf` MUST pass `module.dashboard_lambda.alias_invoke_arn` to the `api_gateway` module's `lambda_invoke_arn` variable | P0 |
| FR-003 | All 6 integration resources in `modules/api_gateway/main.tf` (lines 303, 372, 444, 513, 707, 718) MUST receive the alias invoke ARN via `var.lambda_invoke_arn` (no changes needed — they already reference the variable) | P0 |
| FR-004 | The `aws_lambda_permission.api_gateway` resource (line 722) MUST continue using `qualifier = "live"` — this is already correct and must not be changed | P0 |
| FR-005 | The existing `invoke_arn` output MUST be preserved (other consumers may depend on the unqualified ARN) | P1 |

### Non-Functional Requirements

| ID | Requirement | Priority |
|----|-------------|----------|
| NFR-001 | Change MUST NOT trigger Lambda function recreation or alias destruction | P0 |
| NFR-002 | Change MUST be deployable via standard `terraform plan && terraform apply` without manual intervention | P0 |
| NFR-003 | Deployment trigger hash MUST update if the integration URI changes, forcing API Gateway redeployment | P1 |
| NFR-004 | The fix MUST be backward-compatible — no changes to the `api_gateway` module's variable interface (reuse existing `lambda_invoke_arn` variable) | P1 |

## Success Criteria

1. `terraform plan` shows only changes to:
   - New output `alias_invoke_arn` in lambda module
   - Updated `lambda_invoke_arn` value in `module.api_gateway` (from unqualified to alias ARN)
   - API Gateway integration URI updates (6 resources)
   - API Gateway deployment (triggered by integration URI change)
2. After `terraform apply`, all routes return expected responses (not 500)
3. `/health` returns 200
4. `/api/v2/auth/anonymous` returns the expected auth response (not 500)
5. Authenticated routes (e.g., `/api/v2/sentiments`) continue to work with valid JWT

## Edge Cases

### EC-1: Alias Does Not Exist
**Scenario**: Lambda alias `live` is destroyed or never created.
**Impact**: `aws_lambda_alias.live.invoke_arn` reference fails at plan time with a clear Terraform error — no silent failure.
**Mitigation**: The alias resource is unconditional (not gated by any `count` or `for_each`) per Feature 1300. This is a non-issue under normal operation.

### EC-2: Rollback to Previous State
**Scenario**: Need to revert the change.
**Impact**: Reverting `main.tf` line 829 from `alias_invoke_arn` back to `invoke_arn` restores the broken state (500 errors). This is expected — the previous state is the bug.
**Mitigation**: Rollback should be to a known-good state, not to the broken state. Document that "reverting this change restores the 500 bug."

### EC-3: CI/CD Alias Flip Race Condition
**Scenario**: `terraform apply` runs concurrently with CI alias-flip (`aws lambda update-alias`).
**Impact**: None. Terraform's `ignore_changes = [function_version]` on the alias resource prevents version conflicts. The integration URI references the alias name, not a specific version.
**Mitigation**: No action needed — the design already handles this.

### EC-4: API Gateway Deployment Not Triggered
**Scenario**: Integration URI changes but deployment trigger hash does not update.
**Impact**: Stale deployment serves requests to old (unqualified) function ARN.
**Mitigation**: The deployment trigger uses `aws_api_gateway_integration.lambda_proxy.id` and `aws_api_gateway_integration.lambda_root.id`. When the URI changes, Terraform replaces the integration resources, generating new IDs, which triggers redeployment. Verify this in `terraform plan` output.

### EC-5: Other Lambda Modules
**Scenario**: Other Lambda modules in the project also need `alias_invoke_arn`.
**Impact**: This change only adds the output — other modules can adopt it independently.
**Mitigation**: The output addition is non-breaking.

## Out of Scope

1. **Changing the API Gateway module's variable interface** — We reuse the existing `lambda_invoke_arn` variable. No new variables needed.
2. **Modifying the Lambda permission resource** — The `qualifier = "live"` is already correct. The bug is in the integration URI, not the permission.
3. **Function URL changes** — The Function URL already points to the alias correctly (Feature 1224.4).
4. **Multi-alias support** — No need for canary/weighted alias routing. Single `live` alias is sufficient.
5. **Cognito authorizer changes** — Auth configuration is orthogonal to this fix.
6. **CloudFront or WAF changes** — Upstream routing is unaffected.

## Adversarial Review #1

### Review Date: 2026-04-02

### Findings

| # | Severity | Finding | Resolution |
|---|----------|---------|------------|
| AR1-1 | CRITICAL | **Terraform plan may show in-place update vs replace**: If changing the integration URI causes Terraform to *replace* (destroy+create) the integration resources rather than update in-place, there will be a brief window where routes return 500 during apply. | RESOLVED: AWS API Gateway integrations support in-place URI updates. Terraform performs `Update` not `ForceNew` for `uri` changes on `aws_api_gateway_integration`. Verified: `uri` is not a ForceNew attribute in the AWS provider schema. The deployment trigger ensures the stage picks up the new URI. |
| AR1-2 | HIGH | **Deployment trigger may not fire**: The trigger hash uses `.id` attributes of integration resources. If the URI update is in-place (not replace), the `.id` stays the same, and the deployment is NOT triggered. | RESOLVED: Added NFR-003 to address this. The deployment trigger hash must be updated to include the integration URI or a content hash. However, reviewing the trigger more carefully: Terraform DOES trigger redeployment when integration resources are modified because `depends_on` includes the integrations, and the `sha1(jsonencode(...))` of the resource IDs would change if resources are recreated. For in-place updates, we need to verify. **MITIGATION**: Add `var.lambda_invoke_arn` to the deployment trigger hash to ensure any URI change forces redeployment. This is a code change to add to the plan. |
| AR1-3 | HIGH | **Missing terraform plan verification**: Spec requires verification that plan shows expected changes but does not define what "unexpected" changes look like. | RESOLVED: Success Criteria #1 now explicitly lists expected resources. Anything beyond those (e.g., Lambda function recreation, alias destruction, permission changes) is unexpected and should abort the apply. |
| AR1-4 | MEDIUM | **No integration test defined**: How do we verify the fix works post-apply? | RESOLVED: Success Criteria #3-5 define endpoint-level verification. Implementation should include a post-apply smoke test: `curl -s -o /dev/null -w '%{http_code}' https://<api-gw-url>/v1/health` returns 200. |
| AR1-5 | LOW | **Output naming convention**: `alias_invoke_arn` vs `live_invoke_arn` — which is more discoverable? | RESOLVED: `alias_invoke_arn` is preferred because it's generic (if alias name changes from `live` to something else, the output name still makes sense). The alias name is an implementation detail. |
| AR1-6 | MEDIUM | **3am scenario: What if alias points to a broken version?** | OUT OF SCOPE: This is a CI/CD concern (alias-flip validation), not an infrastructure wiring concern. The fix ensures the wiring is correct; version correctness is CI/CD's responsibility. |

### AR1-2 Resolution Detail: Deployment Trigger Update

The deployment trigger at lines 739-755 must be updated to ensure a URI change forces redeployment even for in-place updates. Add `var.lambda_invoke_arn` to the trigger hash:

```hcl
triggers = {
  redeployment = sha1(jsonencode(concat(
    [
      var.lambda_invoke_arn,  # Force redeploy on URI change
      aws_api_gateway_resource.proxy.id,
      # ... existing entries ...
    ],
    local.public_route_resource_ids,
  )))
}
```

This addresses the edge case where Terraform updates the integration URI in-place without recreating the resource (same `.id`).

### Gate: PASS

All CRITICAL and HIGH findings resolved. Spec is ready for planning.

## Clarifications

### Q1: Is `module.dashboard_lambda.invoke_arn` consumed by anything other than the API Gateway module?

**Answer**: No. Grep of `main.tf` shows `module.dashboard_lambda.invoke_arn` appears only on line 829 (the `api_gateway` module call). Other references to `module.dashboard_lambda` use `.function_name`, `.function_arn`, or `.function_url` -- never `.invoke_arn`. The change is safe with zero blast radius beyond the intended fix.

### Q2: Are there other Lambda modules in this project that also need an `alias_invoke_arn` output?

**Answer**: The `dashboard_lambda` is the only Lambda module consumed by `api_gateway`. No other Lambda module passes an `invoke_arn` to any API Gateway integration. The output addition is specific to the dashboard lambda module.

### Q3: Does the `aws_api_gateway_integration` resource treat `uri` as ForceNew (destroy+create) or Update-in-place?

**Answer**: The AWS provider treats `uri` on `aws_api_gateway_integration` as an update-in-place attribute (not ForceNew). The `rest_api_id`, `resource_id`, and `http_method` are the ForceNew attributes. This means the integration resource ID will NOT change, confirming AR1-2's finding that the deployment trigger must include `var.lambda_invoke_arn` to detect the URI change.

### Q4: Is the Lambda alias `live` unconditionally created, or can it be absent?

**Answer**: Per Feature 1300 (visible in `modules/lambda/main.tf` line 122-137), the `aws_lambda_alias.live` resource is unconditional -- no `count` or `for_each` gating. The comment explicitly states: "Decoupled from create_function_url -- the alias is needed by API Gateway regardless of whether a Function URL exists." The alias will always exist.

### Q5: Will the `terraform plan` output show the integration URI change as a diff, or will it be hidden?

**Answer**: Yes, `terraform plan` will show `uri` changing from `arn:aws:apigateway:...:function:<name>/invocations` to `arn:aws:apigateway:...:function:<name>:live/invocations` on all 6 integration resources. This is a visible, reviewable diff. The `:live` qualifier suffix is the key visual indicator that the fix is correct.
