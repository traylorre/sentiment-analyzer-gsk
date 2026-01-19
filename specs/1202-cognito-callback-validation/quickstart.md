# Quickstart: Cognito Callback URL Validation

**Feature**: 1202-cognito-callback-validation
**Estimated Changes**: 2 files, ~20 lines

## Files to Modify

### 1. Cognito Module Outputs

**File**: `infrastructure/terraform/modules/cognito/outputs.tf`

Add after existing outputs (around line 43):

```hcl
output "callback_urls" {
  description = "Configured callback URLs for OAuth redirects"
  value       = aws_cognito_user_pool_client.dashboard.callback_urls
}

output "logout_urls" {
  description = "Configured logout URLs for OAuth redirects"
  value       = aws_cognito_user_pool_client.dashboard.logout_urls
}
```

### 2. Root Module Outputs

**File**: `infrastructure/terraform/main.tf`

Add after existing Cognito outputs section (around line 1175):

```hcl
output "cognito_callback_urls" {
  description = "Cognito OAuth callback URLs (Terraform-configured values)"
  value       = module.cognito.callback_urls
}

output "cognito_logout_urls" {
  description = "Cognito OAuth logout URLs (Terraform-configured values)"
  value       = module.cognito.logout_urls
}
```

## Expected Output Names

After implementation, these outputs will be available:

| Output Name | Type | Description |
|-------------|------|-------------|
| `cognito_callback_urls` | list(string) | OAuth callback redirect URLs |
| `cognito_logout_urls` | list(string) | OAuth logout redirect URLs |

## Verification Commands

```bash
# Navigate to terraform directory
cd infrastructure/terraform

# Verify no breaking changes
terraform plan

# Apply (if in appropriate environment)
terraform apply

# Check new outputs
terraform output cognito_callback_urls
terraform output cognito_logout_urls

# Compare against actual AWS state (optional)
aws cognito-idp describe-user-pool-client \
  --user-pool-id $(terraform output -raw cognito_user_pool_id) \
  --client-id $(terraform output -raw cognito_client_id) \
  --query 'UserPoolClient.[CallbackURLs,LogoutURLs]'
```

## Expected Output Example

```bash
$ terraform output cognito_callback_urls
[
  "http://localhost:3000/auth/callback",
  "https://main.d29tlmksqcx494.amplifyapp.com/auth/callback"
]

$ terraform output cognito_logout_urls
[
  "http://localhost:3000",
  "https://main.d29tlmksqcx494.amplifyapp.com"
]
```

## Notes

- Outputs show Terraform-configured values, not patched AWS state
- The `terraform_data` provisioner patches these values after Amplify URL is known
- For full validation, use AWS CLI to check actual state
