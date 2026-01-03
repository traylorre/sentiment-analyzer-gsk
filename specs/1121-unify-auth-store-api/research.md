# Research: Unify Auth-Store API Client

**Feature**: 1121-unify-auth-store-api
**Date**: 2026-01-03

## Problem Analysis

The `auth-store.ts` file uses raw `fetch()` with relative URLs for most auth operations, while `signInAnonymous` correctly uses `authApi.createAnonymousSession()`. This inconsistency causes authentication failures.

### Root Cause

When using relative URLs with `fetch()` in Next.js:
- URL like `/api/v2/auth/magic-link` resolves to the Next.js frontend server
- Next.js has no route handler for `/api/v2/auth/*`
- Result: 404 Not Found

The `authApi` client correctly prepends `NEXT_PUBLIC_API_URL` (Lambda Function URL) to endpoints.

## Method Signature Analysis

### 1. signInWithMagicLink

**Current (broken)**:
```typescript
const response = await fetch('/api/v2/auth/magic-link', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({ email, captchaToken }),
});
```

**authApi signature**:
```typescript
requestMagicLink: (email: string) => api.post<MagicLinkResponse>('/api/v2/auth/magic-link', { email })
```

**Adaptation**: Current code passes `captchaToken` but authApi only passes `email`. Need to check if backend expects captchaToken.

**Decision**: The authApi signature is authoritative. If backend needs captchaToken, authApi should be updated separately. For this fix, use authApi as-is.

### 2. verifyMagicLink

**Current (broken)**:
```typescript
const response = await fetch('/api/v2/auth/magic-link/verify', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({ token }),
});
```

**authApi signature**:
```typescript
verifyMagicLink: (token: string, sig: string) => api.post<AuthResponse>('/api/v2/auth/magic-link/verify', { token, sig })
```

**Adaptation**: Store method only passes token, authApi expects token + sig. The store's `verifyMagicLink(token)` signature needs to accept sig parameter or extract from current state.

**Decision**: Update store method signature to accept both parameters.

### 3. signInWithOAuth

**Current (broken)**:
```typescript
const response = await fetch('/api/v2/auth/oauth/urls');
const urls = await response.json();
window.location.href = urls[provider];
```

**authApi signature**:
```typescript
getOAuthUrls: () => api.get<{ google: string; github: string }>('/api/v2/auth/oauth/urls')
```

**Adaptation**: Direct replacement. Response shape matches.

**Decision**: Replace fetch with `authApi.getOAuthUrls()`.

### 4. handleOAuthCallback

**Current (broken)**:
```typescript
const response = await fetch('/api/v2/auth/oauth/callback', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({ provider, code }),
});
```

**authApi signature**:
```typescript
exchangeOAuthCode: (provider: 'google' | 'github', code: string) => api.post<AuthResponse>('/api/v2/auth/oauth/callback', { provider, code })
```

**Adaptation**: Direct replacement. Parameters match.

**Decision**: Replace fetch with `authApi.exchangeOAuthCode(provider, code)`.

### 5. refreshSession

**Current (broken)**:
```typescript
const response = await fetch('/api/v2/auth/refresh', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({ refreshToken: tokens.refreshToken }),
});
```

**authApi signature**:
```typescript
refreshToken: (refreshToken: string) => api.post<RefreshTokenResponse>('/api/v2/auth/refresh', { refreshToken })
```

**Adaptation**: Direct replacement. Parameters match.

**Decision**: Replace fetch with `authApi.refreshToken(tokens.refreshToken)`.

### 6. signOut

**Current (broken)**:
```typescript
await fetch('/api/v2/auth/signout', {
  method: 'POST',
  headers: {
    'Content-Type': 'application/json',
    Authorization: `Bearer ${tokens.accessToken}`,
  },
});
```

**authApi signature**:
```typescript
signOut: () => api.post<void>('/api/v2/auth/signout')
```

**Adaptation**: authApi doesn't explicitly set Authorization header. Need to verify that the api client adds it automatically via interceptor or that `setAccessToken()` handles this.

**Decision**: The api client should handle Authorization header via the token set by `setAccessToken()`. Replace with `authApi.signOut()`.

## Response Type Mapping

| Method | authApi Returns | Store Expects | Action |
|--------|----------------|---------------|--------|
| requestMagicLink | `MagicLinkResponse` | N/A (just success) | None |
| verifyMagicLink | `AuthResponse` | `{user, tokens, sessionExpiresAt}` | Map response |
| getOAuthUrls | `{google, github}` | Same | None |
| exchangeOAuthCode | `AuthResponse` | `{user, tokens, sessionExpiresAt}` | Map response |
| refreshToken | `RefreshTokenResponse` | `{tokens, sessionExpiresAt}` | Map response |
| signOut | `void` | N/A | None |

## Alternatives Considered

1. **Fix authApi to match store signatures**: Rejected - authApi is the authoritative contract
2. **Update NEXT_PUBLIC_API_URL at runtime**: Rejected - doesn't solve the routing issue
3. **Add Next.js API routes as proxy**: Rejected - adds unnecessary complexity

## Final Decision

Replace all raw `fetch()` calls with `authApi` methods, adapting store code where response shapes differ. This is the minimal change that fixes the routing issue.
