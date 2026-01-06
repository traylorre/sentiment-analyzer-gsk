# Feature 1159: Implementation Plan

## Overview

Change SameSite cookie attribute from Strict to None and enable CORS credentials for cross-origin cookie transmission between CloudFront frontend and Lambda Function URL backend.

## Files to Modify

### Backend (Python)
1. `src/lambdas/dashboard/router_v2.py`
   - Line ~439: Magic link verify cookie - change `samesite="strict"` → `"none"`
   - Line ~502: OAuth callback cookie - change `samesite="strict"` → `"none"`

### Infrastructure (Terraform)
2. `infrastructure/terraform/modules/cloudfront/main.tf`
   - Line ~151: Change `access_control_allow_credentials = false` → `true`
   - Line ~155: Add `"X-CSRF-Token"` to allow_headers

3. `infrastructure/terraform/main.tf`
   - Line ~448: Dashboard Lambda CORS - change `allow_credentials = false` → `true`
   - Line ~449: Add `"x-csrf-token"` to allow_headers
   - Line ~768: SSE Lambda CORS - change `allow_credentials = false` → `true`

### Frontend (TypeScript)
4. `frontend/src/lib/api/client.ts`
   - Add `credentials: 'include'` to fetch options

## Implementation Sequence

### Step 1: Backend Cookie Changes
Update router_v2.py to set SameSite=None on all auth cookies.

### Step 2: Infrastructure CORS Updates
Update Terraform configurations for CloudFront and Lambda Function URLs.

### Step 3: Frontend Credential Updates
Update API client to send credentials with cross-origin requests.

### Step 4: Unit Tests
Add/update tests to verify SameSite=None and credentials configuration.

## Rollback Plan

If issues arise:
1. Revert SameSite to Strict (breaks cross-origin but restores security)
2. Revert CORS credentials to false
3. Remove credentials: 'include' from frontend

## Testing Strategy

1. Unit tests for cookie attribute verification
2. Integration test for cross-origin cookie transmission
3. Manual browser test for CORS preflight handling
