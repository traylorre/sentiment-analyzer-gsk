# Implementation Plan: Feature 1174

## Overview

Update auth store to populate federation fields in user state.

## Implementation Steps

### Step 1: Update Anonymous Session Initialization

**File:** `frontend/src/stores/auth-store.ts`
**Location:** Lines 100-107 (setUser call in signInAnonymous)

Add federation field defaults:
- `role: 'anonymous'`
- `linkedProviders: []`
- `verification: 'none'`
- `lastProviderUsed: undefined`

### Step 2: Add API Response Mapper

**File:** `frontend/src/lib/api/auth.ts`

Add function to map `/api/v2/auth/me` response:
- Handle snake_case → camelCase conversion
- Include all federation fields

### Step 3: Add Profile Refresh Action

**File:** `frontend/src/stores/auth-store.ts`

Add `refreshUserProfile()` action that:
- Calls `/api/v2/auth/me`
- Maps response
- Updates user state

### Step 4: Update OAuth/Magic Link Handlers

Ensure `setUser()` calls include federation fields from API response.

## File Changes

| File | Change Type | Description |
|------|-------------|-------------|
| `frontend/src/stores/auth-store.ts` | Edit | Add federation defaults and refresh action |
| `frontend/src/lib/api/auth.ts` | Edit | Add response mapper if needed |

## Validation

- [ ] `npm run typecheck` passes
- [ ] `npm run lint` passes
- [ ] `npm run test` passes

## Rollback

Federation fields are optional, so removing them won't break existing code.
