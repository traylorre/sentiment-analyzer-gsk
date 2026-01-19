# Research: Remove CloudFront Terraform Module

**Feature**: 1203-remove-cloudfront-module
**Date**: 2026-01-18
**Purpose**: Document all CloudFront references for complete removal

## Executive Summary

CloudFront infrastructure is vestigial - Amplify serves the frontend directly via Lambda Function URLs. The CloudFront distribution, S3 bucket, OAC, and all related IAM permissions serve no purpose and should be removed completely.

## Complete Reference Inventory

### 1. modules/cloudfront/ Directory (DELETE ENTIRELY)

**modules/cloudfront/main.tf** (~465 lines)
- S3 bucket for dashboard assets (lines 1-48)
- Origin Access Control (lines 51-60)
- S3 bucket policy allowing CloudFront (lines 66-87)
- Security headers policy (lines 93-133)
- CORS API policy (lines 144-173)
- CloudFront distribution (lines 179-465)
  - S3 origin for static assets
  - API Gateway origin
  - SSE Lambda origin
  - Cache behaviors for `/api/*`, `/health`, `/metrics`, `/static/*`
  - Custom error responses for SPA routing
  - Custom domain/SSL configuration
  - Access logging configuration

**modules/cloudfront/variables.tf** (~84 lines)
- `environment` (required)
- `project` (required)
- `api_gateway_domain` (required)
- `custom_domain` (optional)
- `acm_certificate_arn` (optional)
- `content_security_policy` (with CDN defaults)
- `enable_logging` (default: false)
- `logging_bucket` (optional)
- `price_class_override` (optional)
- `api_gateway_stage_path` (optional)
- `cors_allowed_origins` (optional)
- `sse_lambda_domain` (optional)

**modules/cloudfront/outputs.tf** (~34 lines)
- `distribution_id`
- `distribution_arn`
- `distribution_domain_name`
- `distribution_hosted_zone_id`
- `s3_bucket_name`
- `s3_bucket_arn`
- `dashboard_url`

### 2. main.tf (Root Configuration)

**Module Call (lines 93-119) - DELETE**
```hcl
# ===================================================================
# CloudFront CDN (Feature 006: Dashboard Deployment)
# ===================================================================

module "cloudfront" {
  source = "./modules/cloudfront"

  environment        = var.environment
  project           = var.project
  api_gateway_domain = split("/", module.api_gateway.api_url)[2]
  api_gateway_stage_path = "/${split("/", module.api_gateway.api_url)[3]}"

  # SSE streaming endpoint
  sse_lambda_domain = split("/", module.sse_lambda.function_url)[2]

  # CORS configuration
  cors_allowed_origins = var.cors_allowed_origins

  # Custom domain (optional)
  custom_domain       = var.cloudfront_custom_domain
  acm_certificate_arn = var.cloudfront_acm_certificate_arn
}
```

**Output References (lines 1176-1195) - DELETE**
```hcl
output "cloudfront_distribution_id" {
  description = "CloudFront distribution ID"
  value       = module.cloudfront.distribution_id
}

output "cloudfront_domain_name" {
  description = "CloudFront distribution domain name"
  value       = module.cloudfront.distribution_domain_name
}

output "dashboard_s3_bucket" {
  description = "S3 bucket for dashboard static assets"
  value       = module.cloudfront.s3_bucket_name
}

output "dashboard_url" {
  description = "Dashboard URL"
  value       = module.cloudfront.dashboard_url
}
```

**Dependency References - MODIFY/REMOVE**
- Line 129: CloudWatch RUM uses `module.cloudfront.distribution_domain_name` for domain
- Line 136: CloudWatch RUM has `depends_on = [module.cloudfront]`
- Line 559: Notification Lambda uses `module.cloudfront.distribution_domain_name` for DASHBOARD_URL
- Line 579: Notification Lambda has `depends_on = [..., module.cloudfront]`

### 3. variables.tf (Root Configuration)

**CloudFront Variables (lines 141-154) - DELETE**
```hcl
# CloudFront Configuration (Feature 006)
# ======================================

variable "cloudfront_custom_domain" {
  description = "Custom domain for CloudFront distribution (optional)"
  type        = string
  default     = ""
}

variable "cloudfront_acm_certificate_arn" {
  description = "ACM certificate ARN for custom domain (required if custom_domain is set)"
  type        = string
  default     = ""
}
```

**CORS Comment (line 66) - UPDATE**
```hcl
# Original: CloudFront domain (output as cloudfront_domain_name after first deploy)
# Update to remove CloudFront reference or delete entirely
```

### 4. ci-user-policy.tf (IAM Policies)

**Policy Split Comment (line 16) - UPDATE**
```hcl
# Original: "S3, CloudFront, ACM, Backup, Budgets, RUM, KMS"
# Update to: "S3, ACM, Backup, Budgets, RUM, KMS"
```

**Section Header (line 797) - UPDATE**
```hcl
# Original: "POLICY 3: Storage & CDN (S3, CloudFront, ACM, Backup, Budgets, RUM)"
# Update to: "POLICY 3: Storage (S3, ACM, Backup, Budgets, RUM)"
```

**CloudFront Distribution Operations (lines 882-907) - DELETE**
- Statement SID "CloudFrontDistribution"
- Actions: CreateDistribution, UpdateDistribution, DeleteDistribution, etc.
- Resource: `arn:aws:cloudfront::*:distribution/*`
- Tag conditions

**CloudFront Policies Operations (lines 909-937) - DELETE**
- Statement SID "CloudFrontPolicies"
- Actions: OAC CRUD, Cache Policy CRUD, Response Headers Policy CRUD
- Resources: OAC, cache policies, response headers policies

**CloudFront Read Operations (lines 939-957) - DELETE**
- Statement SID "CloudFrontRead"
- Actions: ListDistributions, ListOriginAccessControls, etc.
- Resource: `["*"]`

**Policy Description (line 1209) - UPDATE**
```hcl
# Original: "CI/CD storage and CDN: S3, CloudFront, ACM, Backup, Budgets, RUM, KMS"
# Update to: "CI/CD storage: S3, ACM, Backup, Budgets, RUM, KMS"
```

### 5. modules/cloudwatch-rum/variables.tf

**Domain Variable Description (line 7) - UPDATE**
```hcl
# Original: "Domain to monitor (e.g., dashboard.example.com or *.cloudfront.net)"
# Update to: "Domain to monitor (e.g., dashboard.example.com)"
```

## Dependencies Analysis

### What Depends on CloudFront

1. **CloudWatch RUM Module**
   - Uses `module.cloudfront.distribution_domain_name` as domain input
   - **Action**: This module call may need to be removed or reconfigured for Amplify domain

2. **Notification Lambda**
   - Uses `module.cloudfront.distribution_domain_name` for DASHBOARD_URL env var
   - **Action**: Replace with Amplify URL or remove

### What CloudFront Depends On

1. **API Gateway** - for api_gateway_domain
2. **SSE Lambda** - for sse_lambda_domain
3. **Variables** - environment, project, cors_allowed_origins, etc.

These dependencies don't need modification - CloudFront is a consumer, not a provider.

## Verification Commands

After removal, run:

```bash
# Validate configuration
cd infrastructure/terraform
terraform validate

# Check for remaining references
grep -ri "cloudfront" . --include="*.tf" | grep -v ".terraform"

# Preview destruction plan
terraform plan
```

## Expected Terraform Plan Output

After removal, `terraform plan` should show:
- CloudFront distribution: destroy
- S3 bucket (dashboard assets): destroy
- Origin Access Control: destroy
- Response Headers Policies: destroy
- No errors about missing modules or outputs

## Risk Assessment

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| Missed reference | Low | Medium | Comprehensive grep search |
| Breaking CloudWatch RUM | Medium | Low | Update to use Amplify domain |
| Breaking notification Lambda | Medium | Low | Update DASHBOARD_URL |
| Terraform validation failure | Low | Low | Run validate before commit |
