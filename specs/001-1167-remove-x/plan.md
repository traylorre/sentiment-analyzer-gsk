# Implementation Plan: Remove X-User-ID from OHLC API

**Feature**: 001-1167-remove-x
**Status**: Ready for Implementation

## Overview

Remove the insecure X-User-ID header from OHLC and sentiment history API calls. The Bearer token authentication is already in place via client.ts interceptor - we just need to stop sending the redundant vulnerable header.

## Implementation Steps

### Step 1: Update ohlc.ts Functions

**File**: `frontend/src/lib/api/ohlc.ts`

1. Remove `userId: string` parameter from `fetchOHLCData` function signature (line 39)
2. Remove `headers: { 'X-User-ID': userId }` from the request options (lines 48-50)
3. Remove `userId: string` parameter from `fetchSentimentHistory` function signature (line 65)
4. Remove `headers: { 'X-User-ID': userId }` from the request options (lines 74-76)

**Verification**: TypeScript will error on callers that still pass userId - this is intentional.

### Step 2: Update useChartData Hook

**File**: `frontend/src/hooks/use-chart-data.ts`

1. Remove `const userId = useAuthStore((state) => state.user?.userId);` (line 92)
2. Add `const hasAccessToken = useAuthStore((state) => !!state.tokens?.accessToken);`
3. Update `fetchOHLCData` call to remove userId argument (line 96)
4. Update `fetchSentimentHistory` call to remove userId argument (line 104)
5. Change `enabled` condition from `!!userId` to `hasAccessToken`

**Verification**: Hook now gates on actual authentication, not just userId presence.

### Step 3: Update Unit Tests

**File**: `frontend/tests/unit/stores/auth-store.test.ts`

1. Locate test at lines 553-566: "should support X-User-ID header for anonymous sessions"
2. Remove or update this test - X-User-ID is no longer used
3. Consider replacing with a test that verifies Bearer token is used instead

**Verification**: `npm run test` passes.

### Step 4: Verify No X-User-ID Remains

**Command**: `grep -r "X-User-ID" frontend/src --include="*.ts" --include="*.tsx"`

Expected: Zero matches in production code (test files may have historical references).

## Dependency Order

```
Step 1 (ohlc.ts) → Step 2 (use-chart-data.ts) → Step 3 (tests) → Step 4 (verify)
```

Step 1 must complete first because Step 2 callers will have TypeScript errors until Step 1 removes the parameters.

## Risk Assessment

| Risk | Mitigation |
|------|------------|
| Breaking chart functionality | Bearer token already works via client.ts - no new auth flow needed |
| TypeScript errors in other files | Search for all callers of fetchOHLCData/fetchSentimentHistory before changes |
| Test failures | Update tests to match new behavior |

## Rollback Plan

If issues discovered post-merge:
1. Revert the PR
2. Investigate which callers still depend on userId parameter
3. Re-implement with proper migration path

## Estimated Scope

- **Files Changed**: 3
- **Lines Changed**: ~20
- **Complexity**: Low (removing code, not adding)
