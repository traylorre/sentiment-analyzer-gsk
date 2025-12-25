# Research: Dashboard Lambda KMS Decrypt Permission

**Feature**: 1058-dashboard-kms-decrypt
**Date**: 2025-12-25

## Summary

This feature requires adding KMS decrypt permission to the dashboard Lambda's secrets policy. The pattern already exists in the codebase (ingestion Lambda), so no external research was needed.

## Existing Pattern Analysis

### Ingestion Lambda Pattern (modules/iam/main.tf, lines 79-87)

```hcl
# KMS decrypt required when secrets use customer-managed KMS keys
var.secrets_kms_key_arn != "" ? [
  {
    Effect = "Allow"
    Action = [
      "kms:Decrypt"
    ]
    Resource = var.secrets_kms_key_arn
  }
] : []
```

**Key Features**:
1. Conditional on `secrets_kms_key_arn != ""` - graceful handling when KMS not used
2. Single action: `kms:Decrypt` - minimal permission
3. Single resource: `var.secrets_kms_key_arn` - least privilege, not wildcard
4. Empty list when not needed - no unnecessary permissions

### Dashboard Lambda Current State (modules/iam/main.tf, lines 381-403)

The dashboard_secrets policy currently lacks this conditional block, causing GetSecretValue calls to fail when secrets use customer-managed KMS encryption.

## Decision

**Approach**: Replicate the ingestion Lambda pattern in the dashboard_secrets policy.

**Rationale**:
- Proven pattern already working in production
- Maintains consistency across Lambda IAM policies
- Follows AWS best practice for Secrets Manager + KMS
- Minimal change surface area

## Alternatives Considered

| Alternative | Rejected Because |
|-------------|------------------|
| Shared secrets policy | Violates per-role isolation; harder to audit which Lambda has which permissions |
| KMS key policy grant | Affects all principals with key access; less precise than IAM policy |
| AWS managed KMS key | Would require changing secrets encryption; larger change scope |

## Validation Strategy

1. **terraform validate** - Syntax check
2. **terraform plan** - Verify expected policy change
3. **IAM validator** - Confirm least-privilege compliance
4. **Unit test** - Verify policy structure
