# Quickstart: Remove CloudFront Terraform Module

**Feature**: 1203-remove-cloudfront-module
**Time Estimate**: Implementation only (no time estimates per guidelines)

## Pre-Flight Check

```bash
cd /home/zeebo/projects/sentiment-analyzer-gsk/infrastructure/terraform

# Verify current state is clean
terraform validate
terraform plan  # Note current CloudFront resources
```

## Step-by-Step Deletion

### Step 1: Delete CloudFront Module Directory

```bash
rm -rf modules/cloudfront/
```

This removes:
- `modules/cloudfront/main.tf`
- `modules/cloudfront/variables.tf`
- `modules/cloudfront/outputs.tf`

### Step 2: Remove Module Call from main.tf

Delete lines containing the `module "cloudfront"` block (approximately lines 93-119).

Remove the following outputs:
- `cloudfront_distribution_id`
- `cloudfront_domain_name`
- `dashboard_s3_bucket`
- `dashboard_url`

Update references that use `module.cloudfront.*`:
- CloudWatch RUM domain input
- Notification Lambda DASHBOARD_URL

### Step 3: Remove Variables from variables.tf

Delete:
- `cloudfront_custom_domain` variable
- `cloudfront_acm_certificate_arn` variable

Update CORS comment to remove CloudFront reference.

### Step 4: Remove IAM Permissions from ci-user-policy.tf

Delete these statements:
- `CloudFrontDistribution` (SID)
- `CloudFrontPolicies` (SID)
- `CloudFrontRead` (SID)

Update comments and descriptions to remove "CloudFront" mentions.

### Step 5: Update CloudWatch RUM Module

Update `modules/cloudwatch-rum/variables.tf`:
- Remove `*.cloudfront.net` from domain variable description

### Step 6: Validate

```bash
# Syntax validation
terraform validate

# Search for any remaining references
grep -ri "cloudfront" . --include="*.tf" | grep -v ".terraform"
# Expected: 0 matches

# Preview changes
terraform plan
```

## Expected Outcomes

### Terraform Validate
```
Success! The configuration is valid.
```

### Grep Search
```
# No output (zero matches)
```

### Terraform Plan
```
Plan: 0 to add, 0 to change, X to destroy.

  # aws_cloudfront_distribution.dashboard will be destroyed
  # aws_cloudfront_origin_access_control.dashboard will be destroyed
  # aws_cloudfront_response_headers_policy.security will be destroyed
  # aws_cloudfront_response_headers_policy.cors_api will be destroyed
  # aws_s3_bucket.dashboard will be destroyed
  # aws_s3_bucket_policy.dashboard will be destroyed
  # aws_s3_bucket_public_access_block.dashboard will be destroyed
```

## Post-Implementation

After PR merge and `terraform apply`:
- CloudFront distribution will be destroyed
- S3 dashboard bucket will be destroyed
- All CloudFront IAM permissions will be removed from CI user

## Rollback Plan

If issues arise:
1. Revert the commit via `git revert`
2. Push revert to trigger re-deployment
3. CloudFront resources will be recreated on `terraform apply`

Note: This rollback requires a new `terraform apply` to recreate resources.
