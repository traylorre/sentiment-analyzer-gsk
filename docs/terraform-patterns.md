# Terraform Patterns

## Split Definition/Wiring (Feature 1290)

### Problem

Terraform modules that cross-reference each other's outputs through Lambda environment variables can create circular dependencies. Terraform's graph resolver cannot determine creation order when Module A needs Module B's output as an env var, and Module B (transitively) needs Module A.

### Pattern

Split Lambda configuration into two phases within a single `terraform apply`:

1. **Definition**: Create the Lambda with placeholder env vars (`""`) for cross-module values
2. **Wiring**: After all modules exist, a `terraform_data` resource with `local-exec` reads current env vars, merges the cross-module value, and writes back

```
┌──────────────────────┐       ┌──────────────────────┐
│  module "lambda_a"   │       │  module "lambda_b"    │
│  ENV_VAR = ""        │       │  (produces output)    │
│  ignore_changes =    │       │                       │
│    [environment]     │       │                       │
└──────────┬───────────┘       └──────────┬────────────┘
           │                              │
           └──────────┬───────────────────┘
                      ▼
           ┌──────────────────────┐
           │  terraform_data      │
           │  "lambda_a_wiring"   │
           │  depends_on = [a, b] │
           │  local-exec: merge   │
           └──────────────────────┘
```

### Current Usage

| Lambda | Wired Env Var | Source Module | Wiring Resource |
|--------|--------------|---------------|-----------------|
| dashboard_lambda | SCHEDULER_ROLE_ARN | chaos | terraform_data.dashboard_lambda_env_wiring |
| notification_lambda | DASHBOARD_URL | amplify_frontend | terraform_data.notification_lambda_env_wiring |

### Rules

1. **Merge, never replace.** `aws lambda update-function-configuration --environment` replaces ALL env vars. The wiring script (`scripts/terraform-env-wiring.sh`) reads current → merges → writes.

2. **Suppress output.** The merge step echoes all env vars including secret ARNs. All AWS CLI output is suppressed in the wiring script.

3. **Verify after write.** The wiring script reads back the value and compares. Exit code 2 on mismatch.

4. **No temp files.** Uses pipes and process substitution to avoid writing secrets to disk.

### When to Use

- Lambda env var references another module's output
- That reference creates a cycle in the Terraform dependency graph
- The env var is a SOFT dependency (Lambda functions without it, just with degraded behavior)

### When NOT to Use

- HARD dependencies (Lambda cannot be created without the value) — restructure modules instead
- Values needed at plan time (e.g., resource ARNs for IAM policies) — these must be direct references
- One-directional dependencies (no cycle) — use direct module output references

### Adding a New Wired Env Var

1. In the Lambda's `environment_variables` block: set the var to `""` with a comment pointing to the wiring resource
2. Create a new `terraform_data` resource following the existing pattern
3. Add the var name to the `validate_critical_env_vars()` call in the Lambda's handler
4. Test: `terraform plan` should show no cycle; after apply, verify the value is populated

### Tech Debt

This pattern is a workaround. The long-term fix is to migrate cross-module env vars to SSM Parameter Store, where Lambdas read values at runtime instead of receiving them as env vars. This eliminates the Terraform dependency entirely. See GitHub issue for tracking.

### Related

- `terraform_data.cognito_callback_patch` (main.tf) — similar pattern for Cognito ↔ Amplify cycle
- `docs/x-ray/HL-x-ray-remediation-checklist.md` R22 — documents the replace-all danger of `update-function-configuration`
