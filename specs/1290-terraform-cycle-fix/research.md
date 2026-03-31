# Feature 1290: Research

## Decision Log

### D-1: Why Strategy 4 over Strategy 2 (extract to root)?
**Decision**: Strategy 4 (Split Definition + Wiring)
**Alternatives considered**:
- Strategy 1: Post-creation patching (terraform_data + local-exec) — same mechanism as Strategy 4 but without the definition/wiring conceptual split
- Strategy 2: Extract CORS gateway responses to root — doesn't address the actual cycle (which is env vars, not CORS)
- Strategy 6: Data sources — fails on first apply
- Strategy 7: try() — doesn't break dependency edges in graph

**Rationale**: Strategy 4 was selected because:
1. It addresses the actual cycle edges (env vars, not CORS)
2. It's consistent with the existing Cognito patch pattern
3. It's a single `terraform apply` (no two-phase)
4. It preserves module encapsulation (modules unchanged except Lambda lifecycle)

### D-2: Why accept global `ignore_changes = [environment]`?
**Decision**: Add `environment` to `ignore_changes` on the shared Lambda module for ALL Lambdas, not just the two wired ones.
**Rationale**: Terraform does not support dynamic `lifecycle` blocks. Cannot conditionally enable `ignore_changes` per module instance. The alternatives (duplicate module, root-level override) are worse than the trade-off.
**Trade-off**: Lose env var drift detection on all 6 Lambdas. Compensated by runtime validation (FR-005).

### D-3: Why not SSM Parameter Store now?
**Decision**: Defer SSM to tech debt ticket. Implement provisioner-based wiring now.
**Rationale**: SSM migration requires:
1. Creating SSM parameters for each cross-module value
2. Adding IAM permissions for each Lambda to read SSM
3. Modifying Lambda code to read from SSM instead of env vars
4. Testing cold start latency impact (SSM call adds 50-100ms)
5. Handling SSM unavailability gracefully

This is a 2-3 day effort across Terraform + Python + tests. The cycle fix needs to ship today to unblock all deployments.

**Long-term**: SSM is the right answer because:
- Lambda reads values at runtime, no Terraform dependency
- SSM supports versioning and audit trail
- No `ignore_changes` needed
- No provisioner scripts to maintain
- Values can be updated without `terraform apply`

### D-4: Why read-merge-write instead of replace?
**Decision**: Wiring script reads existing env vars, merges the wired key, writes back.
**Rationale**: Dashboard Lambda has 25+ env vars. The wiring provisioner only manages 1 (SCHEDULER_ROLE_ARN). If we replaced instead of merged, we'd need to replicate ALL 25 env vars in the provisioner script, creating a maintenance nightmare and violating DRY.

### D-5: Why process substitution over temp files?
**Decision**: Use bash process substitution (`<(command)`) or pipe instead of writing to `/tmp/`.
**Rationale**: CI runners may be shared. A temp file containing the full env var set (which includes secret ARNs, JWT secrets) could be read by another process. Process substitution keeps data in memory only.

## Terraform Lifecycle Constraints

### What `ignore_changes` does
- Tells Terraform: "If this attribute changes in the real infrastructure, don't try to revert it"
- Applied per-resource, not per-attribute-value
- `ignore_changes = [environment]` ignores ALL env var changes, not just specific keys
- Cannot be conditional (no `count`, no `for_each`, no variable interpolation)

### What `terraform_data` with `provisioner` does
- `terraform_data` is a managed resource in Terraform state
- `triggers_replace` causes the resource to be replaced (and provisioner re-run) when the value changes
- `local-exec` provisioner runs a shell command on the machine running `terraform apply`
- Provisioner failure marks the resource as tainted — next apply will retry

### Existing pattern: Cognito callback patch (main.tf:1294)
```hcl
resource "terraform_data" "cognito_callback_patch" {
  triggers_replace = [
    module.amplify_frontend[0].production_url,
    module.cognito.client_id,
  ]
  provisioner "local-exec" {
    command = <<-EOT
      aws cognito-idp update-user-pool-client \
        --user-pool-id ${module.cognito.user_pool_id} \
        --client-id ${module.cognito.client_id} \
        --callback-urls '["${module.amplify_frontend[0].production_url}/auth/callback"]' \
        --logout-urls '["${module.amplify_frontend[0].production_url}"]'
    EOT
  }
  depends_on = [module.cognito, module.amplify_frontend]
}
```

Our wiring resources follow this exact pattern but for Lambda env vars instead of Cognito.

## AWS Lambda Environment Variable Update Semantics

### Atomicity
- `update-function-configuration` is atomic — concurrent invocations see either old or new env vars, never partial
- `LastUpdateStatus` transitions: `InProgress` → `Successful` or `Failed`
- During `InProgress`, new cold starts wait for the update to complete
- Warm instances continue using old env vars until recycled

### Merge behavior
- AWS CLI `--environment` flag REPLACES the entire environment block
- There is no native "merge" — we must read, merge locally, then write
- `get-function-configuration` returns the full current environment
- Race condition between read and write: extremely unlikely during Terraform apply (no other writers)

### IAM permission
- Requires `lambda:UpdateFunctionConfiguration` on the function ARN
- Also requires `lambda:GetFunctionConfiguration` for the read step
