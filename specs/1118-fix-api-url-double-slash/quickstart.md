# Quickstart: Fix Double-Slash URL in API Requests

**Feature**: 1118-fix-api-url-double-slash
**Date**: 2026-01-02

## Verification Steps

### 1. Local Development Verification

```bash
# Start the frontend dev server
cd frontend
npm run dev
```

1. Open browser to http://localhost:3000
2. Open DevTools Network tab (F12 → Network)
3. Filter by "auth" to see authentication requests
4. Verify the request URL shows single slash: `/api/v2/auth/anonymous`
5. Verify HTTP status is 200 or 201 (not 422)

### 2. Production Verification

1. Navigate to the deployed dashboard URL
2. Open DevTools Network tab
3. Refresh the page to trigger fresh authentication
4. Check the authentication request URL:
   - **Expected**: `https://<lambda-url>.lambda-url.us-east-1.on.aws/api/v2/auth/anonymous`
   - **Not expected**: `https://<lambda-url>.lambda-url.us-east-1.on.aws//api/v2/auth/anonymous`
5. Verify HTTP 200/201 response (not 422)

### 3. Edge Case Verification

Test URL normalization handles all cases:

| Test Case | Base URL | Endpoint | Expected Result |
|-----------|----------|----------|-----------------|
| Standard | `https://a.com` | `/api/v2/auth` | `https://a.com/api/v2/auth` |
| Both slashes | `https://a.com/` | `/api/v2/auth` | `https://a.com/api/v2/auth` |
| No slashes | `https://a.com` | `api/v2/auth` | `https://a.com/api/v2/auth` |
| Base slash only | `https://a.com/` | `api/v2/auth` | `https://a.com/api/v2/auth` |

### 4. Success Criteria Checklist

- [ ] Dashboard loads without 422 authentication errors
- [ ] Network tab shows no double-slash URLs (`//api/`)
- [ ] Anonymous authentication completes successfully
- [ ] All other API requests use properly formatted URLs

## Quick Test Commands

```bash
# Build and test locally
cd frontend
npm run build
npm run start

# Check for double-slash in codebase (should find nothing after fix)
grep -r "'//" frontend/src/lib/api/ || echo "No double-slash patterns found"
```
