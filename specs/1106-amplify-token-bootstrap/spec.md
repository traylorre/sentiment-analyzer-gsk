# 1106: Amplify GitHub Token Bootstrap

## Problem Statement

AWS Amplify app creation fails with:
```
BadRequestException: You should at least provide one valid token
```

The `aws_amplify_app` resource requires a valid `access_token` at creation time when connecting to a GitHub repository. The current approach attempts to create the app without a token and patch later via provisioner, which AWS rejects.

## Root Cause

Bootstrap chicken-and-egg problem:
1. Terraform needs the GitHub token to create the Amplify app
2. The token should be stored in Secrets Manager for security
3. But Secrets Manager secret doesn't exist until infrastructure is created

This circular dependency prevents clean Terraform-only provisioning.

## Solution

Break the cycle with a one-time manual pre-provisioning step.

### Phase 1: Manual Bootstrap (One-Time)

Create the GitHub token secret in AWS Secrets Manager before Terraform runs:

```bash
aws secretsmanager create-secret \
  --name "preprod/amplify/github-token" \
  --description "GitHub PAT for Amplify repository access" \
  --secret-string "ghp_XXXXXXXXXXXXXXXXXXXX" \
  --region us-east-1
```

**Token requirements**:
- GitHub Personal Access Token (classic)
- Scopes: `repo`, `admin:repo_hook`
- Owner: Repository owner with push access

### Phase 2: Terraform Changes

Modify Amplify module to read token from Secrets Manager at plan time.

## Files to Modify

### `infrastructure/terraform/modules/amplify/variables.tf`

Add variable:
```hcl
variable "github_token_secret_name" {
  description = "Name of Secrets Manager secret containing GitHub PAT"
  type        = string
  default     = "preprod/amplify/github-token"
}
```

### `infrastructure/terraform/modules/amplify/main.tf`

Add data source to read the pre-provisioned secret:
```hcl
data "aws_secretsmanager_secret_version" "github_token" {
  secret_id = var.github_token_secret_name
}
```

Update `aws_amplify_app` resource:
```hcl
resource "aws_amplify_app" "main" {
  name         = var.app_name
  repository   = var.repository_url
  access_token = data.aws_secretsmanager_secret_version.github_token.secret_string

  # ... rest of configuration
}
```

Remove any `local-exec` provisioner workarounds for token patching.

## Success Criteria

1. `terraform plan` reads token from Secrets Manager without error
2. `terraform apply` creates Amplify app with GitHub repository connected
3. Amplify Console shows repository link and branch detection working
4. No manual post-apply steps required

## Security Considerations

- Token stored in Secrets Manager, not in Terraform state as plaintext variable
- Secret access controlled via IAM policies
- Token value never appears in Terraform plan output (marked sensitive by AWS provider)

## Rollback

If needed, delete the Amplify app and secret:
```bash
terraform destroy -target=module.amplify
aws secretsmanager delete-secret --secret-id "preprod/amplify/github-token" --force-delete-without-recovery
```
