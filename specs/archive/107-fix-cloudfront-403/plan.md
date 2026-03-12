# Feature 107: Implementation Plan

## Summary

Add `origin_path` to CloudFront API Gateway origin to prepend stage prefix.

## Changes Required

### 1. modules/cloudfront/variables.tf
Add new variable for API Gateway stage path.

### 2. modules/cloudfront/main.tf
Add `origin_path` attribute to the dynamic API Gateway origin block.

### 3. main.tf
Pass `api_gateway_stage_path = "/${module.api_gateway.stage_name}"` to cloudfront module.

## Implementation Order

1. Add variable to cloudfront module
2. Add origin_path to cloudfront origin
3. Pass value from main.tf
4. Deploy and invalidate cache

## Verification

```bash
# After deploy:
aws cloudfront create-invalidation --distribution-id E14HOKHFRMG5XG --paths "/api/*"

# Wait for invalidation, then test:
curl -s "https://d2z9uvoj5xlbd2.cloudfront.net/api/v2/auth/anonymous"
# Expected: JSON response, not XML
```

## Rollback

If issues occur, set `api_gateway_stage_path = ""` to revert to previous behavior.
