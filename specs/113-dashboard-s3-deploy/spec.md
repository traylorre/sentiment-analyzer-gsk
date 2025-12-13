# Feature 113: Deploy Dashboard to S3

## Problem Statement

The "View Live Dashboard" button in the Interview Dashboard returns 403 AccessDenied because the CloudFront S3 bucket is empty. The dashboard files in `src/dashboard/` are never deployed.

## Solution

Add a step to the deploy workflow that:
1. Uploads `src/dashboard/*` files to the CloudFront S3 bucket
2. Sets appropriate cache headers (no-cache for HTML, long-cache for JS/CSS)
3. Invalidates CloudFront cache for immediate updates

## Changes

### .github/workflows/deploy.yml

Add "Deploy Dashboard to S3 (Preprod)" step after "Get Preprod Outputs":
- Get `dashboard_s3_bucket` and `cloudfront_distribution_id` from Terraform outputs
- `aws s3 sync` dashboard files with cache headers
- Override HTML files with no-cache headers
- Create CloudFront invalidation

## Files Deployed

| File | Purpose | Cache |
|------|---------|-------|
| index.html | Main dashboard | no-cache |
| chaos.html | Chaos engineering dashboard | no-cache |
| app.js | Application logic | 1 year |
| config.js | Configuration | 1 year |
| styles.css | Styles | 1 year |

## Success Criteria

| ID | Criterion | Verification |
|----|-----------| -------------|
| SC-001 | CloudFront root returns 200 | `curl -I https://d2z9uvoj5xlbd2.cloudfront.net/` |
| SC-002 | Dashboard loads in browser | Visual test |
| SC-003 | Cache headers set correctly | Check S3 object metadata |
| SC-004 | CloudFront invalidation created | Check deploy logs |
