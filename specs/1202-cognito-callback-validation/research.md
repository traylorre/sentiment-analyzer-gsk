# Research: Cognito Callback URL Validation

**Feature**: 1202-cognito-callback-validation
**Date**: 2026-01-18

## Research Questions

### Q1: How to access callback_urls from aws_cognito_user_pool_client?

**Decision**: Use direct attribute reference `aws_cognito_user_pool_client.dashboard.callback_urls`

**Rationale**: The `callback_urls` input argument is automatically exported as a readable attribute in Terraform. This is standard Terraform behavior for all resource arguments.

**Alternatives Considered**:
- Using a data source to read actual AWS state - rejected because it adds complexity and the primary use case is verifying Terraform configuration
- Reading from variables directly - rejected because it wouldn't reflect any dynamic values computed during apply

**Source**: [Terraform AWS Provider - aws_cognito_user_pool_client](https://registry.terraform.io/providers/hashicorp/aws/latest/docs/resources/cognito_user_pool_client)

---

### Q2: How does the lifecycle ignore_changes affect outputs?

**Decision**: Document that outputs show Terraform-configured values, not patched AWS state

**Rationale**: The Cognito module uses `lifecycle { ignore_changes = [callback_urls, logout_urls] }` because these values are patched post-creation by `terraform_data.cognito_callback_patch`. This means:
- Terraform state contains the **initial** values from input variables
- Actual AWS state may differ after the provisioner runs
- Outputs reflect Terraform state, not AWS state

**Implementation Note**: For full validation, engineers should use AWS CLI:
```bash
aws cognito-idp describe-user-pool-client \
  --user-pool-id <id> \
  --client-id <client-id> \
  --query 'UserPoolClient.[CallbackURLs,LogoutURLs]'
```

---

### Q3: Do we need conditional logic for the outputs?

**Decision**: No conditional logic needed

**Rationale**: Unlike the Amplify module which uses `count` for conditional deployment, the Cognito module is always deployed. Reviewing `infrastructure/terraform/main.tf`:
- `module "cognito"` has no `count` or `for_each`
- The module is always instantiated regardless of environment

**Comparison**: The Amplify outputs use conditionals:
```hcl
output "amplify_app_id" {
  value = var.enable_amplify ? module.amplify_frontend[0].app_id : ""
}
```

Cognito outputs do not need this pattern.

---

### Q4: What is the current output structure in the Cognito module?

**Decision**: Follow existing output patterns in the module

**Current outputs in `modules/cognito/outputs.tf`**:
- `user_pool_id`
- `client_id`
- `domain`
- `hosted_ui_url`
- `oauth_issuer`
- `jwks_uri`

**Pattern**: Simple value references with descriptions. New outputs will follow the same pattern.

---

## Key Findings

1. **Terraform state vs AWS state discrepancy**: Due to `ignore_changes`, Terraform outputs will show initial configuration, not patched values. This is acceptable for the validation use case.

2. **No conditional logic needed**: Cognito module is always deployed, unlike Amplify.

3. **List type outputs**: Both `callback_urls` and `logout_urls` are list types, which will display all configured URLs.

4. **Existing patterns**: The module already exports 6 outputs following a consistent pattern we can follow.

## Sources

- [Terraform AWS Provider - aws_cognito_user_pool_client](https://registry.terraform.io/providers/hashicorp/aws/latest/docs/resources/cognito_user_pool_client)
- [lgallard/terraform-aws-cognito-user-pool](https://github.com/lgallard/terraform-aws-cognito-user-pool) - Community module for reference
- Codebase: `infrastructure/terraform/modules/cognito/` - Current implementation
