# Tasks: Frontend OAuth Federation Wiring

**Branch**: `1177-frontend-oauth-federation-wiring` | **Date**: 2025-01-09

## Tasks

### Task 1: Add OAuthCallbackResponse Interface
- [x] Add `OAuthCallbackResponse` interface with all backend fields
- [x] Include federation fields: role, verification, linked_providers, last_provider_used

**File**: `frontend/src/lib/api/auth.ts` (lines 39-59)

### Task 2: Add mapOAuthCallbackResponse Function
- [x] Create mapping function from snake_case backend response to camelCase User type
- [x] Handle null/undefined fields with sensible defaults
- [x] Map tokens from snake_case to camelCase
- [x] Handle error and conflict responses by throwing errors

**File**: `frontend/src/lib/api/auth.ts` (lines 85-127)

### Task 3: Update exchangeOAuthCode
- [x] Change to async function with explicit return type
- [x] Call `mapOAuthCallbackResponse()` to transform response
- [x] Return `AuthResponse` with mapped User and tokens

**File**: `frontend/src/lib/api/auth.ts` (lines 190-193)

### Task 4: Add Unit Tests
- [x] Test: mapOAuthCallbackResponse correctly maps all fields
- [x] Test: Federation fields (role, verification, linkedProviders, lastProviderUsed) mapped
- [x] Test: Default values used when fields are minimal
- [x] Test: Error response throws error
- [x] Test: Conflict response throws error

**File**: `frontend/tests/unit/lib/api/auth.test.ts` (5 tests)

## Verification

```bash
cd frontend
npm run typecheck  # TypeScript passes
npm run test       # 419/419 tests pass
```

## Status: COMPLETE

All tasks completed. 5 new tests, 419/419 frontend tests passing.
