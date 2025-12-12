# Feature Specification: 095-iam-user-resource-pattern

**Branch**: `095-iam-user-resource-pattern` | **Date**: 2025-12-12

## Problem Statement

The Deploy Pipeline fails at terraform plan with:
```
User: arn:aws:iam::218795110243:user/sentiment-analyzer-preprod-deployer is not authorized
to perform: iam:ListAttachedUserPolicies on resource: user sentiment-analyzer-preprod-deployer
because no identity-based policy allows the iam:ListAttachedUserPolicies action
```

## Root Cause

The IAM policy resource constraint uses pattern `*-sentiment-deployer` (line 640 in ci-user-policy.tf):
```hcl
resources = [
  "arn:aws:iam::*:user/*-sentiment-deployer"
]
```

But the actual AWS IAM user names follow pattern `sentiment-analyzer-*-deployer`:
- `sentiment-analyzer-preprod-deployer`
- `sentiment-analyzer-prod-deployer`

The pattern mismatch means the deployer users cannot manage their own policy attachments.

## Solution

Update the resource constraint to match actual user names:
```hcl
resources = [
  "arn:aws:iam::*:user/sentiment-analyzer-*-deployer"
]
```

## Scope

| In Scope | Out of Scope |
|----------|--------------|
| Fix resource pattern in ci-user-policy.tf line 640 | Renaming AWS IAM users |
| Update comment on line 630 | Adding new IAM permissions |

## Success Criteria

| ID | Criterion | Verification |
|----|-----------|--------------|
| SC-001 | terraform plan succeeds without IAM errors | Pipeline passes |
| SC-002 | terraform apply succeeds | Deploy to Preprod completes |
| SC-003 | No new permissions added | Diff shows only resource pattern change |

## Technical Details

**File**: `infrastructure/terraform/ci-user-policy.tf`
**Lines**: 630, 640
**Change**: 1 string replacement

### Before (line 640)
```hcl
"arn:aws:iam::*:user/*-sentiment-deployer"
```

### After (line 640)
```hcl
"arn:aws:iam::*:user/sentiment-analyzer-*-deployer"
```

### Comment Update (line 630)
```hcl
# IAM User Policy Attachments (for CI deployer users managing their own policies)
# Pattern: sentiment-analyzer-*-deployer (preprod, prod)
```

## Clarifications

### Session 2025-12-12

No critical ambiguities detected. Spec is fully constrained:
- Exact file and line numbers specified
- Before/after code blocks provided
- Success criteria are testable via pipeline execution

## Dependencies

- Depends on: 094-ecr-auth-permission (IAM policy attachments in AWS)
- Blocks: Deploy Pipeline success
