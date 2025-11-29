# API Gateway and Lambda Integration Audit

Comprehensive audit for API Gateway configurations and Lambda integrations to identify routing, dependency, and deployment issues before they cause production failures.

## User Input

```text
$ARGUMENTS
```

Consider user input for specific focus areas (e.g., "smoke test failures", "502 errors", specific Lambda name).

## Goal

Identify and prevent API Gateway integration issues including:
- Missing Lambda dependencies causing import errors (502s)
- CloudFront routing misconfigurations (403s on wrong paths)
- API Gateway stage/path mismatches
- Smoke test targeting wrong endpoints

## Audit Steps

### 1. Lambda Dependency Audit

For each Lambda function, verify ALL imported modules are in the CI build:

```bash
# Find all Lambda handlers
find src/lambdas/*/handler.py -type f

# For each handler, extract imports
grep -h "^from\|^import" src/lambdas/*/handler.py | sort | uniq
```

**Critical dependencies to verify in deploy.yml:**

| Lambda | Required Packages | Verified in CI? |
|--------|-------------------|-----------------|
| dashboard | fastapi, mangum, sse-starlette, pydantic, boto3, aws-xray-sdk | |
| ingestion | boto3, requests, pydantic, aws-xray-sdk | |
| analysis | boto3, pydantic, aws-xray-sdk | |
| notification | boto3, sendgrid, pydantic, aws-xray-sdk | |
| metrics | boto3 | |

**Detection command:**
```bash
# Check what's imported vs what's installed
for lambda in dashboard ingestion analysis notification metrics; do
  echo "=== $lambda ==="
  grep "^from\|^import" src/lambdas/$lambda/handler.py 2>/dev/null | head -20
done
```

### 2. CloudFront Routing Audit

Verify CloudFront behaviors match expected paths:

| Path Pattern | Expected Origin | Current Config |
|--------------|-----------------|----------------|
| `/api/*` | API Gateway | |
| `/static/*` | S3 | |
| `/health` | ??? (TRAP!) | |
| `/*` (default) | S3 | |

**Common Issue:** `/health` endpoint exists on Lambda but CloudFront routes it to S3 (403).

**Detection:**
```bash
# Check CloudFront behaviors
grep -A20 "ordered_cache_behavior\|default_cache_behavior" infrastructure/terraform/modules/cloudfront/main.tf
```

**Fix options:**
1. Use API Gateway URL directly for health checks (recommended)
2. Add `/health` behavior to CloudFront
3. Move health endpoint to `/api/health`

### 3. Smoke Test Endpoint Audit

Verify smoke tests target correct endpoints:

| Environment | Test URL Source | Endpoint Path | Expected to Work? |
|-------------|-----------------|---------------|-------------------|
| Dev | `dashboard_api_url` | `/health` | Yes (API Gateway) |
| Preprod | `dashboard_api_url` | `/health` | Yes (API Gateway) |
| Prod | `api_url` | `/health` | Yes (API Gateway) |

**Detection:**
```bash
# Check what URLs smoke tests use
grep -B5 -A10 "Smoke Test\|health" .github/workflows/deploy.yml
```

**Common Issues:**
- Using CloudFront URL for health check (403 if /health not routed)
- Using Lambda Function URL instead of API Gateway
- Mixing up output variable names

### 4. API Gateway Stage/Path Audit

Verify API Gateway stage matches expected paths:

```bash
# Check API Gateway stage configuration
grep -A10 "aws_api_gateway_stage\|stage_name" infrastructure/terraform/modules/api_gateway/main.tf
```

**Common Issue:** Stage path (e.g., `/v1`) included in endpoint URL may cause double-pathing.

### 5. Lambda X-Ray Tracing Audit

All Lambdas using X-Ray must have `aws-xray-sdk` in dependencies:

```bash
# Find Lambdas using X-Ray
grep -l "aws_xray_sdk\|xray_recorder\|patch_all" src/lambdas/*/handler.py

# Verify X-Ray SDK in each Lambda's pip install
grep -A20 "Packaging.*Lambda" .github/workflows/deploy.yml | grep "aws-xray-sdk"
```

**Error signature when missing:**
```
[ERROR] Runtime.ImportModuleError: Unable to import module 'handler': No module named 'aws_xray_sdk'
```

This causes API Gateway to return HTTP 502.

## Findings Report Template

```markdown
## API Gateway Integration Audit Report

### Lambda Dependency Status
| Lambda | Missing Dependencies | Status |
|--------|---------------------|--------|
| dashboard | | |
| ingestion | | |
| analysis | | |
| notification | | |
| metrics | | |

### CloudFront Routing Status
- [ ] `/api/*` routes to API Gateway
- [ ] `/health` accessible (via API Gateway URL, not CloudFront)
- [ ] Static assets route to S3

### Smoke Test Configuration
- [ ] Dev uses API Gateway URL for health check
- [ ] Preprod uses API Gateway URL for health check
- [ ] Prod canary uses API Gateway URL for health check

### Critical Issues Found
1. [CRITICAL] ...
2. [HIGH] ...
3. [MEDIUM] ...

### Recommended Fixes
1. ...
2. ...
```

## Quick Fix Commands

### Add missing X-Ray SDK to Lambda build:
```yaml
pip install \
  ... existing deps ... \
  aws-xray-sdk==2.14.0 \
  -t packages/LAMBDA-deps/
```

### Switch smoke test to API Gateway URL:
```yaml
- name: Capture Terraform Outputs
  run: |
    api_url=$(terraform output -raw dashboard_api_url || echo "")
    echo "api_url=${api_url}" >> $GITHUB_OUTPUT

- name: Smoke Test
  run: |
    api_url="${{ steps.outputs.outputs.api_url }}"
    curl -s "${api_url}/health"
```

### Add health behavior to CloudFront (alternative):
```hcl
ordered_cache_behavior {
  path_pattern     = "/health"
  target_origin_id = "api-gateway"
  # ... same config as /api/*
}
```

## Prevention Checklist

Before merging Lambda changes:
- [ ] All imports in handler.py have corresponding pip installs in deploy.yml
- [ ] X-Ray SDK included if handler uses `patch_all()` or `xray_recorder`
- [ ] Smoke tests use API Gateway URL (not CloudFront) for health checks
- [ ] CloudFront behaviors match expected routing

## Context

$ARGUMENTS
