# Research: Pipeline Blockers Resolution

**Feature**: 041-pipeline-blockers
**Date**: 2025-12-06

## Unknowns Resolution

### 1. ECR Repository Import Syntax

**Question**: What is the correct terraform import command for ECR repositories?

**Decision**: Use `terraform import aws_ecr_repository.<resource_name> <repository_name>`

**Rationale**: AWS ECR repositories are imported by their name, not ARN.

**Command**:
```bash
terraform import aws_ecr_repository.sse_streaming preprod-sse-streaming-lambda
```

**Source**: [AWS Provider ECR Documentation](https://registry.terraform.io/providers/hashicorp/aws/latest/docs/resources/ecr_repository#import)

### 2. KMS Key Policy Requirements

**Question**: Why does AWS reject KMS key policies that only grant root access?

**Decision**: AWS requires the creating principal to have explicit key administration permissions in the key policy.

**Rationale**:
- When a KMS key is created, AWS validates that the calling principal can manage the key after creation
- Even though root has `kms:*`, the creating IAM user must also be explicitly included
- This prevents scenarios where keys become unmanageable if root access is restricted

**Required Actions for Key Administration**:
```
kms:Create*, kms:Describe*, kms:Enable*, kms:List*,
kms:Put*, kms:Update*, kms:Revoke*, kms:Disable*,
kms:Get*, kms:Delete*, kms:TagResource, kms:UntagResource,
kms:ScheduleKeyDeletion, kms:CancelKeyDeletion
```

**Source**: [AWS KMS Best Practices - Key Policies](https://docs.aws.amazon.com/kms/latest/developerguide/key-policies.html)

### 3. Handling Existing KMS Key in Failed State

**Question**: What if a KMS key already exists from a previous failed apply?

**Decision**: Check key state before apply; if in `PendingDeletion`, cancel deletion and import.

**Options**:
1. Key doesn't exist → Create normally
2. Key exists and active → Import into state
3. Key in `PendingDeletion` → `aws kms cancel-key-deletion --key-id <id>` then import

**Verification Command**:
```bash
aws kms describe-key --key-id alias/sentiment-analyzer-preprod 2>/dev/null || echo "Key not found"
```

## Best Practices Applied

### Terraform Import Best Practices

1. **Always run plan after import** - Verify no drift between state and config
2. **Import in isolation** - Don't mix imports with other changes
3. **Document imports** - Add comment in code noting the import was performed
4. **Backup state** - State is auto-versioned in S3, but verify bucket versioning enabled

### KMS Key Policy Best Practices

1. **Always include root** - Required fallback access
2. **Use explicit principals** - Avoid `Principal: "*"`
3. **Scope service access** - Only grant necessary operations per service
4. **Include creating principal** - Required for key manageability

## Alternatives Considered

### Alternative 1: Delete and Recreate ECR Repository

**Rejected Because**: May have existing images; import is non-destructive

### Alternative 2: Use IAM Policy Instead of Key Policy for KMS Access

**Rejected Because**: AWS requires key policy to allow the creating principal; IAM policies alone are insufficient for KMS key creation

### Alternative 3: Create KMS Key via Bootstrap Script

**Rejected Because**: Violates IaC principle; all resources should be terraform-managed

## Dependencies

| Dependency | Status | Notes |
|------------|--------|-------|
| S3 state bucket access | RESOLVED | Fixed in spec 019 |
| IAM policy for deployer | RESOLVED | Fixed in spec 019 |
| Terraform CLI | AVAILABLE | Version 1.5+ in CI |
| AWS credentials | AVAILABLE | Via GitHub Secrets |

## Risk Assessment

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| ECR import fails | LOW | LOW | Verify repo name matches; retry with correct name |
| KMS key already exists | MEDIUM | LOW | Check state; import or cancel deletion |
| Pipeline still fails | LOW | MEDIUM | Debug logs; iterate on permissions |

## Conclusion

All unknowns resolved. Implementation is straightforward:
1. ECR import is a single command
2. KMS fix requires adding one policy statement
3. Both CI deployers (preprod + prod) are included per FR-005
