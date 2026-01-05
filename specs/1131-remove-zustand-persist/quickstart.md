# Quickstart: Remove Zustand Persist Middleware

**Feature**: 1131-remove-zustand-persist
**Date**: 2026-01-05

## What Changed

The auth store no longer persists authentication tokens (accessToken, refreshToken, idToken) to localStorage. This is a security fix to prevent XSS attacks from stealing user credentials.

## Impact on Users

### Before This Fix
- Tokens stored in localStorage
- XSS attacks could steal tokens
- Sessions persisted across browser restarts

### After This Fix
- Tokens stored in memory only
- XSS attacks cannot access tokens
- Sessions may require re-authentication on page refresh

## Impact on Developers

### No Code Changes Required

The auth store API remains unchanged. Your components continue to work:

```typescript
// This still works exactly the same
const { user, isAuthenticated, login, logout } = useAuthStore();
```

### Session Handling

If your code assumes tokens persist across page refresh, consider:

1. **httpOnly cookies**: Backend sessions via cookies still work
2. **Session validation**: The `isAuthenticated` flag still persists for UI hints
3. **Re-authentication**: Users may need to log in again after refresh

## Testing Your Integration

### Verify Token Non-Persistence

```typescript
// In browser DevTools Console
localStorage.getItem('auth-store');

// Should NOT contain "tokens", "accessToken", "refreshToken", or "idToken"
```

### Verify Application Works

1. Log in to the application
2. Navigate between pages (tokens work in-memory)
3. Refresh the page
4. Verify appropriate session handling (re-auth or cookie-based session)

## FAQ

**Q: Will users be logged out immediately?**
A: No. In-memory tokens work for the current session. Re-login may be needed after page refresh.

**Q: What about the httpOnly cookie mechanism?**
A: That's a separate feature. If implemented, it provides session continuity across refreshes.

**Q: Are any other fields affected?**
A: No. User profile and session flags (isAuthenticated, isAnonymous) still persist for UX.

**Q: How is this more secure?**
A: XSS attacks can read localStorage but cannot access JavaScript variables. Tokens in memory are safe from XSS.
