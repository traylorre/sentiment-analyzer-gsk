# Implementation Tasks: OAuth State/CSRF Validation

**Branch**: `1193-oauth-state-csrf` | **Spec**: [spec.md](./spec.md) | **Plan**: [plan.md](./plan.md)

## Task Summary

| ID | Task | Status | Estimate |
|----|------|--------|----------|
| T01 | Add OAuthUrlsResponse type with provider-specific state | Complete | S |
| T02 | Update getOAuthUrls to return full response | Complete | S |
| T03 | Update exchangeOAuthCode to accept state and redirectUri | Complete | S |
| T04 | Update auth-store signInWithOAuth to store state | Complete | S |
| T05 | Update auth-store handleOAuthCallback signature | Complete | S |
| T06 | Update use-auth handleCallback signature | Complete | S |
| T07 | Create/update callback page with state validation | Complete | M |
| T08 | Add unit tests for state validation | Complete | M |
| T09 | Add sonner dependency (bug fix from 1191) | Complete | S |

## Implementation Complete

All tasks completed. Key changes:

### API Layer (`frontend/src/lib/api/auth.ts`)
- Added `OAuthProviderInfo` and `OAuthUrlsResponse` types for provider-specific state
- Updated `getOAuthUrls()` return type to include state per provider
- Updated `exchangeOAuthCode()` to accept `state` and `redirectUri` parameters
- Backend callback now receives all required params: `{ provider, code, state, redirect_uri }`

### Auth Store (`frontend/src/stores/auth-store.ts`)
- `signInWithOAuth()` now stores both provider and state in sessionStorage
- `handleOAuthCallback()` signature updated to accept state and redirectUri

### Auth Hook (`frontend/src/hooks/use-auth.ts`)
- `handleCallback()` signature updated to pass state and redirectUri

### Callback Page (`frontend/src/app/auth/callback/page.tsx`)
- Extracts `state` parameter from OAuth callback URL
- Validates URL state matches stored state (CSRF check)
- Calculates `redirectUri` from window.location
- Passes all params to handleCallback for backend validation

### Tests (`frontend/tests/unit/app/auth/callback.test.tsx`)
- 19 tests covering state validation scenarios
- Tests for CSRF protection (state mismatch detection)
- Tests for error handling when state is missing
