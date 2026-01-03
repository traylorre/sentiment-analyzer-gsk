# Quickstart: Unify Auth-Store API Client

**Feature**: 1121-unify-auth-store-api
**Time**: ~30 minutes

## TL;DR

Replace raw `fetch()` calls in `auth-store.ts` with `authApi` methods to fix 404 errors.

## Changes Required

### File: `frontend/src/stores/auth-store.ts`

1. **signInWithMagicLink** (line ~118-143):
   ```typescript
   // Before: fetch('/api/v2/auth/magic-link', ...)
   // After:
   await authApi.requestMagicLink(email);
   ```

2. **verifyMagicLink** (line ~145-174):
   ```typescript
   // Before: fetch('/api/v2/auth/magic-link/verify', ...)
   // After:
   const data = await authApi.verifyMagicLink(token, sig);
   setUser(data.user);
   setTokens(data.tokens);
   ```

3. **signInWithOAuth** (line ~176-199):
   ```typescript
   // Before: fetch('/api/v2/auth/oauth/urls')
   // After:
   const urls = await authApi.getOAuthUrls();
   window.location.href = urls[provider];
   ```

4. **handleOAuthCallback** (line ~201-230):
   ```typescript
   // Before: fetch('/api/v2/auth/oauth/callback', ...)
   // After:
   const data = await authApi.exchangeOAuthCode(provider, code);
   setUser(data.user);
   setTokens(data.tokens);
   ```

5. **refreshSession** (line ~232-258):
   ```typescript
   // Before: fetch('/api/v2/auth/refresh', ...)
   // After:
   const data = await authApi.refreshToken(tokens.refreshToken);
   setTokens({ ...tokens, accessToken: data.accessToken, idToken: data.idToken });
   ```

6. **signOut** (line ~260-278):
   ```typescript
   // Before: fetch('/api/v2/auth/signout', ...)
   // After:
   await authApi.signOut();
   ```

## Verification

1. Run `npm run build` in frontend directory
2. Run `npm run lint` to check for type errors
3. Test OAuth flow: Click "Continue with Google" → should redirect to Google (not 404)
4. Test magic link: Enter email → should send request to backend (not 404)

## Why This Works

The `authApi` client prepends `NEXT_PUBLIC_API_URL` (Lambda Function URL) to all endpoints, ensuring requests go to the backend Lambda instead of the Next.js frontend server.
