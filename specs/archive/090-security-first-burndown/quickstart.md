# Quickstart: Security-First Drift Burndown

**Feature**: 090-security-first-burndown
**Date**: 2025-12-11

## Prerequisites

### AWS IAM User Creation (Manual Admin Step)

This feature requires two new IAM users to be created manually by an AWS administrator before CI/CD credentials can be updated.

#### Option 1: AWS Console

1. Navigate to IAM Console: https://console.aws.amazon.com/iam/
2. Click "Users" → "Create user"
3. Create user: `preprod-sentiment-deployer`
   - Select "Programmatic access"
   - Attach existing policy: `preprod-sentiment-deployer-policy`
4. Repeat for: `prod-sentiment-deployer`
   - Attach existing policy: `prod-sentiment-deployer-policy`
5. Download access keys for each user

#### Option 2: AWS CLI

```bash
# Create preprod deployer
aws iam create-user --user-name preprod-sentiment-deployer
aws iam attach-user-policy \
  --user-name preprod-sentiment-deployer \
  --policy-arn arn:aws:iam::$(aws sts get-caller-identity --query Account --output text):policy/preprod-sentiment-deployer-policy

# Create access key
aws iam create-access-key --user-name preprod-sentiment-deployer

# Create prod deployer
aws iam create-user --user-name prod-sentiment-deployer
aws iam attach-user-policy \
  --user-name prod-sentiment-deployer \
  --policy-arn arn:aws:iam::$(aws sts get-caller-identity --query Account --output text):policy/prod-sentiment-deployer-policy

# Create access key
aws iam create-access-key --user-name prod-sentiment-deployer
```

### GitHub Secrets Update

After creating IAM users and obtaining access keys:

```bash
# Update preprod secrets
gh secret set AWS_ACCESS_KEY_ID_PREPROD -b "AKIA..."
gh secret set AWS_SECRET_ACCESS_KEY_PREPROD -b "..."

# Update prod secrets
gh secret set AWS_ACCESS_KEY_ID_PROD -b "AKIA..."
gh secret set AWS_SECRET_ACCESS_KEY_PROD -b "..."
```

**Note**: Verify secret names match workflow expectations by checking `.github/workflows/deploy.yml`.

## Development Setup

```bash
# Clone and checkout feature branch
git checkout 090-security-first-burndown

# Install dependencies
make install

# Run validation
make validate

# Check IAM patterns
make check-iam-patterns
```

## Implementation Order

1. **Phase 1**: Setup (this quickstart, T001-T002)
2. **Phase 2**: IAM Migration (T003-T006) - requires admin prerequisite
3. **Phase 3**: SRI Implementation (T007-T011)
4. **Phase 4**: SRI Methodology (T012-T017)
5. **Phase 5**: CSP Headers (T018-T021)
6. **Phase 6**: Dockerfile Security (T022-T025)
7. **Phase 7**: Polish (T026-T030)

## Verification Commands

```bash
# IAM legacy patterns (should be 0)
make check-iam-patterns | grep LEGACY | wc -l

# SRI attributes (should be 3)
grep -c integrity src/dashboard/*.html

# SRI methodology exists
ls .claude/commands/sri-validate.md

# Dockerfile non-root
grep -c "USER lambda" src/lambdas/sse_streaming/Dockerfile
```

## Rollback Plan

If issues arise with new IAM users:

1. Restore old GitHub secrets (backup before changing)
2. New users can be disabled: `aws iam update-login-profile --user-name preprod-sentiment-deployer --no-password-reset-required`
3. Legacy users remain functional until explicitly disabled

## References

- [AWS IAM Best Practices](https://docs.aws.amazon.com/IAM/latest/UserGuide/best-practices.html)
- [MDN: Subresource Integrity](https://developer.mozilla.org/en-US/docs/Web/Security/Subresource_Integrity)
- [AWS: CloudFront Response Headers](https://docs.aws.amazon.com/AmazonCloudFront/latest/DeveloperGuide/understanding-response-headers-policies.html)
