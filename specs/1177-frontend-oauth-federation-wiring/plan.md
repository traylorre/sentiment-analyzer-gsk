# Implementation Plan: Frontend OAuth Federation Wiring

**Branch**: `1177-frontend-oauth-federation-wiring` | **Date**: 2025-01-09 | **Spec**: [spec.md](./spec.md)

## Summary

Add mapping from backend `OAuthCallbackResponse` (snake_case) to frontend `User` type (camelCase) so federation fields are properly extracted and stored in auth store after OAuth authentication.

## Technical Context

**Language/Version**: TypeScript 5.x
**Primary Dependencies**: React, Zustand (auth-store)
**Testing**: Jest/Vitest
**Project Type**: Next.js frontend

## Implementation Approach

### Step 1: Add Backend Response Interface

Add `OAuthCallbackResponse` interface in `frontend/src/lib/api/auth.ts`:

```typescript
interface OAuthCallbackResponse {
  status: string;
  email_masked: string | null;
  auth_type: string | null;
  tokens: {
    id_token: string;
    access_token: string;
    expires_in: number;
  } | null;
  merged_anonymous_data: boolean;
  is_new_user: boolean;
  conflict: boolean;
  existing_provider: string | null;
  message: string | null;
  error: string | null;
  // Feature 1176: Federation fields
  role: string;
  verification: string;
  linked_providers: string[];
  last_provider_used: string | null;
}
```

### Step 2: Add Mapping Function

Add `mapOAuthCallbackResponse()` function:

```typescript
function mapOAuthCallbackResponse(response: OAuthCallbackResponse): AuthResponse {
  return {
    user: {
      userId: '', // Not provided in OAuth response
      authType: (response.auth_type ?? 'anonymous') as User['authType'],
      email: response.email_masked ?? undefined,
      createdAt: new Date().toISOString(), // Not provided
      configurationCount: 0, // Not provided
      alertCount: 0, // Not provided
      emailNotificationsEnabled: false, // Not provided
      // Feature 1177: Federation fields
      role: response.role as User['role'],
      linkedProviders: response.linked_providers as User['linkedProviders'],
      verification: response.verification as User['verification'],
      lastProviderUsed: (response.last_provider_used ?? undefined) as User['lastProviderUsed'],
    },
    tokens: response.tokens ? {
      idToken: response.tokens.id_token,
      accessToken: response.tokens.access_token,
      expiresIn: response.tokens.expires_in,
    } : { idToken: '', accessToken: '', expiresIn: 0 },
  };
}
```

### Step 3: Update exchangeOAuthCode

```typescript
exchangeOAuthCode: async (provider: 'google' | 'github', code: string) => {
  const response = await api.post<OAuthCallbackResponse>('/api/v2/auth/oauth/callback', { provider, code });
  return mapOAuthCallbackResponse(response);
},
```

### Step 4: Add Unit Tests

Create tests in `frontend/tests/unit/lib/test-auth-api.ts` (or similar) to verify mapping.

## Files to Modify

| File | Changes |
|------|---------|
| `frontend/src/lib/api/auth.ts` | Add interface + mapping function + update exchangeOAuthCode |
| `frontend/tests/unit/lib/test-auth-api.ts` | Add unit tests for mapping (new file if needed) |
