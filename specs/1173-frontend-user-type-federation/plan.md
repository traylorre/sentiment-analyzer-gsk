# Implementation Plan: Feature 1173

## Overview

Add federation type definitions to frontend `User` interface. Type-only changes, no runtime code.

## Implementation Steps

### Step 1: Add Type Aliases

**File:** `frontend/src/types/auth.ts`

Add new type aliases for federation fields:
- `UserRole`
- `VerificationStatus`
- Update `ProviderType` if not already defined

### Step 2: Update User Interface

**File:** `frontend/src/types/auth.ts`

Add optional fields:
- `role?: UserRole`
- `linkedProviders?: ProviderType[]`
- `verification?: VerificationStatus`
- `lastProviderUsed?: ProviderType`

### Step 3: Run TypeScript Compilation

Verify no compile errors introduced.

## File Changes

| File | Change Type | Description |
|------|-------------|-------------|
| `frontend/src/types/auth.ts` | Edit | Add type aliases and User fields |

## Validation

- [ ] `npm run typecheck` passes
- [ ] `npm run lint` passes
- [ ] Existing tests still pass
- [ ] No breaking changes to existing code

## Rollback

All new fields are optional, so no rollback needed. Removing fields would require updating any code that uses them.
