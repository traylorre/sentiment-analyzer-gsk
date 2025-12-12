# 094: ECR Authorization Permission Fix

## Problem Statement

The Deploy Pipeline is failing at the "Login to Amazon ECR" step with:

```
User: arn:aws:iam::218795110243:user/sentiment-analyzer-preprod-deployer is not authorized
to perform: ecr:GetAuthorizationToken on resource: * because no identity-based policy
allows the ecr:GetAuthorizationToken action
```

## Root Cause Analysis

**IAM User Name Mismatch**: The Terraform policy attachments reference a different user name than what exists in AWS.

| Environment | AWS (actual) | Terraform (incorrect) |
|-------------|--------------|----------------------|
| Preprod | `sentiment-analyzer-preprod-deployer` | `preprod-sentiment-deployer` |
| Prod | `sentiment-analyzer-prod-deployer` | `prod-sentiment-deployer` |

The `ecr:GetAuthorizationToken` permission exists in `ci_deploy_core` policy (line 327), but is attached to the wrong users.

## Impact

- **Severity**: CRITICAL - Deploy Pipeline completely blocked
- **Scope**: All preprod deployments fail at ECR login step
- **Duration**: Since last IAM policy change

## Proposed Solution

Update the IAM user references in `infrastructure/terraform/ci-user-policy.tf` to match the actual AWS IAM user names:

```hcl
# Before
user = "preprod-sentiment-deployer"

# After
user = "sentiment-analyzer-preprod-deployer"
```

## Success Criteria

- [ ] SC-001: Deploy Pipeline ECR login succeeds
- [ ] SC-002: All 4 preprod policy attachments updated
- [ ] SC-003: All 4 prod policy attachments updated
- [ ] SC-004: `terraform plan` shows only policy attachment changes
- [ ] SC-005: No new IAM permissions added (user name fix only)

## Canonical Source

AWS IAM Policy Attachment: The `user` attribute must match the exact IAM user name.
- https://registry.terraform.io/providers/hashicorp/aws/latest/docs/resources/iam_user_policy_attachment

## Risk Assessment

- **Low Risk**: Only changing user name references, not policy content
- **Rollback**: Revert user names in Terraform

## Out of Scope

- Creating/managing IAM users (users exist externally)
- Modifying IAM policy permissions
- Changing GitHub secrets configuration

## Clarifications

### Session 2025-12-12

- Q: What is the actual prod IAM user name in AWS? → A: `sentiment-analyzer-prod-deployer` (verified via `aws iam list-users`)
