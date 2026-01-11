# Implementation Plan: OAuth State/CSRF Validation

**Branch**: `1193-oauth-state-csrf` | **Date**: 2026-01-11 | **Spec**: [spec.md](./spec.md)

## Summary

Add OAuth state parameter handling for CSRF protection. Update frontend to extract provider-specific state from `/oauth/urls`, store state+provider in sessionStorage, and send state+redirect_uri in callback API request.

## Technical Context

**Language/Version**: TypeScript 5.x + Next.js 14.2.21
**Primary Dependencies**: Existing auth-store, authApi
**Storage**: sessionStorage for state (cross-tab isolation)
**Testing**: Vitest + React Testing Library
**Target Platform**: Web browser
**Project Type**: Frontend-only changes

## Constitution Check

- [x] No new external dependencies
- [x] No new data models (uses existing OAuth types)
- [x] No backend changes (frontend consuming existing backend API correctly)
- [x] Follows established security patterns (state validation)

## Implementation Approach

### Current State (Feature 1192)

- `signInWithOAuth`: Stores only `provider` in sessionStorage
- `getOAuthUrls`: Returns `{ google: string, github: string }` (authorize URLs only)
- `exchangeOAuthCode`: Sends only `{ provider, code }` to backend
- Callback page: Reads provider from sessionStorage, extracts code from URL

### Required Changes

1. **Update getOAuthUrls return type** to include provider-specific state
2. **Update signInWithOAuth** to store state per provider
3. **Update exchangeOAuthCode** to send state and redirect_uri
4. **Update callback page** to extract and send state from URL

### Phase 1: Update API Types and getOAuthUrls

**File**: `frontend/src/lib/api/auth.ts`

```typescript
// New response type matching backend
interface OAuthProviderInfo {
  authorize_url: string;
  icon: string;
  state: string;  // Provider-specific state
}

interface OAuthUrlsResponse {
  providers: {
    google: OAuthProviderInfo;
    github: OAuthProviderInfo;
  };
  state: string;  // Legacy compatibility
}

// Update getOAuthUrls
getOAuthUrls: async () => {
  const response = await api.get<OAuthUrlsResponse>('/api/v2/auth/oauth/urls');
  return response;
}
```

### Phase 2: Update signInWithOAuth

**File**: `frontend/src/stores/auth-store.ts`

```typescript
signInWithOAuth: async (provider: OAuthProvider) => {
  const urls = await authApi.getOAuthUrls();
  const providerInfo = urls.providers[provider];

  // Store provider AND state (Feature 1193: CSRF protection)
  sessionStorage.setItem('oauth_provider', provider);
  sessionStorage.setItem('oauth_state', providerInfo.state);

  window.location.href = providerInfo.authorize_url;
}
```

### Phase 3: Update exchangeOAuthCode

**File**: `frontend/src/lib/api/auth.ts`

```typescript
exchangeOAuthCode: async (
  provider: 'google' | 'github',
  code: string,
  state: string,
  redirectUri: string
): Promise<AuthResponse> => {
  const response = await api.post<OAuthCallbackResponse>('/api/v2/auth/oauth/callback', {
    provider,
    code,
    state,
    redirect_uri: redirectUri,
  });
  return mapOAuthCallbackResponse(response);
}
```

### Phase 4: Update Callback Page

**File**: `frontend/src/app/auth/callback/page.tsx`

```typescript
// Extract state from URL
const state = searchParams.get('state');

// Retrieve stored state for validation
const storedState = sessionStorage.getItem('oauth_state');
const provider = sessionStorage.getItem('oauth_provider');
sessionStorage.removeItem('oauth_state');
sessionStorage.removeItem('oauth_provider');

// Validate state matches (client-side check, backend also validates)
if (state !== storedState) {
  setStatus('error');
  setErrorMessage('Authentication session expired or invalid.');
  return;
}

// Get redirect URI (current page URL without query params)
const redirectUri = window.location.origin + window.location.pathname;

// Call with all required params
await handleCallback(code, provider, state, redirectUri);
```

### Phase 5: Update useAuth Hook

**File**: `frontend/src/hooks/use-auth.ts`

Update `handleCallback` signature to accept state and redirectUri:

```typescript
const handleCallback = useCallback(
  async (code: string, provider: OAuthProvider, state: string, redirectUri: string) => {
    await handleOAuthCallback(code, provider, state, redirectUri);
    router.push('/');
  },
  [handleOAuthCallback, router]
);
```

## File Changes Summary

| File | Change |
|------|--------|
| `frontend/src/lib/api/auth.ts` | Update types, getOAuthUrls, exchangeOAuthCode |
| `frontend/src/stores/auth-store.ts` | Store state, update handleOAuthCallback |
| `frontend/src/hooks/use-auth.ts` | Update handleCallback signature |
| `frontend/src/app/auth/callback/page.tsx` | Extract state from URL, validate, pass to API |
| `frontend/tests/unit/app/auth/callback.test.tsx` | Add state validation tests |

## Testing Strategy

1. Unit tests for state storage in signInWithOAuth
2. Unit tests for state extraction and validation in callback
3. Unit tests for state mismatch error handling
4. Integration with existing OAuth callback tests
