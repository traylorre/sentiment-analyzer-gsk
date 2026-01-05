# Research: Remove Zustand Persist Middleware

**Feature**: 1131-remove-zustand-persist
**Date**: 2026-01-05

## Research Questions

### Q1: How does zustand persist() partialize work?

**Decision**: Use the `partialize` option to selectively exclude tokens from persistence.

**Rationale**:
- The zustand persist middleware's `partialize` function controls which state fields are saved
- Current code explicitly lists fields to persist - we can simply remove `tokens` from this list
- This is the intended pattern for partial persistence

**Current Code** (from auth-store.ts:305-311):
```typescript
partialize: (state) => ({
  user: state.user,
  tokens: state.tokens,           // REMOVE THIS LINE
  sessionExpiresAt: state.sessionExpiresAt,
  isAuthenticated: state.isAuthenticated,
  isAnonymous: state.isAnonymous,
}),
```

**Sources**:
- Zustand persist middleware documentation
- Existing codebase: `frontend/src/stores/auth-store.ts` lines 279-311

### Q2: How to handle migration of existing localStorage data?

**Decision**: Use the `onRehydrate` callback to clear any existing tokens from localStorage.

**Rationale**:
- Users who authenticated before this fix have tokens in localStorage
- Simply removing from partialize won't delete existing stored data
- The `onRehydrate` callback fires when the store loads from storage - perfect for cleanup

**Implementation**:
```typescript
onRehydrate: (state) => {
  // Migration: Clear any existing tokens from localStorage
  if (typeof window !== 'undefined') {
    const stored = localStorage.getItem('auth-store');
    if (stored) {
      try {
        const parsed = JSON.parse(stored);
        if (parsed.state?.tokens) {
          delete parsed.state.tokens;
          localStorage.setItem('auth-store', JSON.stringify(parsed));
        }
      } catch {
        // Ignore parse errors
      }
    }
  }
}
```

**Alternatives Rejected**:
- Manual localStorage.clear(): Would clear all app data, not just tokens
- Version-based migration: More complex than needed for this one-time fix

### Q3: What's the security improvement?

**Decision**: Removing tokens from localStorage eliminates XSS token theft vector.

**Rationale**:
- XSS attacks can read any data from localStorage via `localStorage.getItem()`
- With tokens in localStorage, a single XSS vulnerability leads to full account takeover
- In-memory storage is not accessible to XSS scripts (can't read JS variables)
- httpOnly cookies (separate mechanism) are also inaccessible to XSS

**Security Impact**:
- Before: XSS → Read localStorage → Steal tokens → Session hijack
- After: XSS → Cannot access tokens (in memory only) → Limited impact

**Sources**:
- OWASP XSS Prevention Cheat Sheet
- CWE-922: Insecure Storage of Sensitive Information

### Q4: What happens on page refresh?

**Decision**: Accept re-authentication as a security tradeoff.

**Rationale**:
- Without tokens in localStorage, page refresh loses the token
- User may need to re-authenticate depending on backend session handling
- This is an acceptable tradeoff for security (CVSS 8.6 vulnerability)
- httpOnly cookies can provide session continuity if backend supports it

**UX Mitigation**:
- Non-sensitive flags (`isAuthenticated`, `isAnonymous`) still persist
- App can show appropriate loading state while checking session
- Backend httpOnly cookies can re-establish session without re-login

## Key Findings Summary

| Topic | Decision | Key Benefit |
|-------|----------|-------------|
| Partialize modification | Remove `tokens` from partialize | Clean, intended pattern |
| Migration cleanup | onRehydrate callback | One-time cleanup on load |
| Security improvement | Memory-only tokens | Eliminates XSS token theft |
| Session continuity | Accept re-auth tradeoff | Security > convenience |
