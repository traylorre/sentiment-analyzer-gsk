# Spec: CI Warmup Session Auth Alignment

**Feature ID**: 1047
**Priority**: P0 (Pipeline Blocker)
**Status**: Draft

## Problem Statement

PR #499 (Feature 1039) unified all dashboard endpoints to use session-based authentication, removing API key authentication. However, the CI warmup script in `deploy.yml` still uses `Authorization: Bearer ${API_KEY}` which is no longer valid.

**Current Behavior (BROKEN)**:
- CI warmup calls `/api/v2/metrics` with `Authorization: Bearer ${API_KEY}`
- Dashboard Lambda rejects this (API_KEY is not a UUID or JWT)
- Pipeline fails with HTTP 401

**Root Cause**:
- `extract_auth_context()` in `auth_middleware.py` expects:
  1. Bearer token to be a valid UUID (anonymous session) OR
  2. Bearer token to be a valid JWT (authenticated session)
- API_KEY secret is neither - it's an arbitrary string

## Solution

Align CI warmup to use session auth pattern: `X-User-ID: {uuid}` header.

This matches:
- Line 1281-1282 in deploy.yml which already correctly uses `X-User-ID` for sentiment endpoint
- The hybrid auth pattern documented in `auth_middleware.py`

## Changes Required

### File: `.github/workflows/deploy.yml`

**Line 1244**: Remove `API_KEY` env var (no longer needed for warmup)

**Lines 1250-1255**: Remove API_KEY validation block

**Lines 1265-1275**: Change from:
```bash
echo "2. Invoking /api/v2/metrics endpoint (authenticated)..."
HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" \
  -H "Authorization: Bearer ${API_KEY}" \
  "${DASHBOARD_URL}/api/v2/metrics" || echo "000")
echo "  HTTP $HTTP_CODE"
if [ "$HTTP_CODE" != "200" ]; then
  echo "❌ ERROR: /api/v2/metrics returned HTTP $HTTP_CODE (expected 200)"
  echo "Check DASHBOARD_API_KEY secret matches API_KEY in Lambda environment"
  exit 1
fi
```

To:
```bash
echo "2. Invoking /api/v2/metrics endpoint (session auth)..."
# Feature 1047: Use X-User-ID header for session auth (consistent with sentiment warmup)
WARMUP_USER_ID="ci-warmup-$(date +%s)"
HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" \
  -H "X-User-ID: ${WARMUP_USER_ID}" \
  "${DASHBOARD_URL}/api/v2/metrics" || echo "000")
echo "  HTTP $HTTP_CODE"
if [ "$HTTP_CODE" != "200" ]; then
  echo "❌ ERROR: /api/v2/metrics returned HTTP $HTTP_CODE (expected 200)"
  echo "This is a session auth failure. Check extract_auth_context() in auth_middleware.py"
  exit 1
fi
```

**Also update lines 1389-1395**: Remove `DASHBOARD_API_KEY` and `API_KEY` env vars from preprod-integration-tests job since they're no longer needed.

**Lines 1920-1926 (prod canary)**: Remove unnecessary `X-API-Key` header since `/health` is unauthenticated:
```bash
# Before
API_KEY="${{ secrets.DASHBOARD_API_KEY }}"
response=$(curl -f -s -w "\n%{http_code}" \
  "${API_URL}/health" \
  -H "X-API-Key: ${API_KEY}" || echo "FAILED")

# After
response=$(curl -f -s -w "\n%{http_code}" \
  "${API_URL}/health" || echo "FAILED")
```

**Line 1453**: Update error message to reference session auth instead of API key.

## Acceptance Criteria

1. CI warmup succeeds with HTTP 200 on `/api/v2/metrics`
2. All endpoints use consistent auth pattern (X-User-ID or Bearer UUID/JWT)
3. No `API_KEY` references in warmup logic
4. Pipeline passes on main

## Out of Scope

- Removing `DASHBOARD_API_KEY` secret from GitHub (may be used elsewhere)
- Changes to Lambda code (already correct)
- Frontend changes (already correct)

## Testing

- Deploy to preprod should succeed
- Warmup step should log HTTP 200 for metrics endpoint
- Preprod integration tests should pass

## Dependencies

- Feature 1039 (Unified Session Auth) - MERGED

## Risks

- **Low**: Simple header change, auth middleware already supports X-User-ID
