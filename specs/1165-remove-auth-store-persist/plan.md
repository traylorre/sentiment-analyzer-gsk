# Implementation Plan: Remove Auth Store persist() Middleware

**Branch**: `1165-remove-auth-store-persist` | **Date**: 2026-01-06 | **Spec**: [spec.md](./spec.md)
**Input**: Phase 2 C6 Security Fix - Remove localStorage from auth flow

## Summary

Remove the zustand persist() middleware from auth-store.ts, converting it to a memory-only store. Update useSessionInit to initialize immediately without waiting for hydration. Session restoration relies solely on httpOnly cookies via /refresh endpoint.

## Technical Context

**Language/Version**: TypeScript 5.x
**Primary Dependencies**: zustand (state management)
**Storage**: Memory only (remove localStorage)
**Testing**: Jest/Vitest for unit tests
**Target Platform**: Browser (Next.js frontend)
**Project Type**: Web application (frontend)

## Constitution Check

| Gate | Status | Notes |
|------|--------|-------|
| No localStorage for auth | FIXING | This feature addresses the violation |
| HTTPOnly cookie model | ALIGNING | Session restore via /refresh |
| Code simplification | PASS | Removing unused hydration logic |

## Project Structure

### Files to Modify

```text
frontend/src/stores/
└── auth-store.ts           # Remove persist(), _hasHydrated, hydration logic

frontend/src/hooks/
├── use-session-init.ts     # Remove hydration wait, simplify init
└── use-auth.ts             # Remove hasHydrated references

frontend/tests/unit/stores/
└── auth-store.test.ts      # Update tests for memory-only store
```

## Implementation Approach

### Phase 1: Remove persist() from auth-store.ts

**Current structure (simplified)**:
```typescript
export const useAuthStore = create<AuthStore>()(
  persist(
    (set, get) => ({
      _hasHydrated: false,
      // ... state and actions
    }),
    {
      name: TOKEN_STORAGE_KEY,
      storage: createJSONStorage(...),
      partialize: (state) => ({...}),
      onRehydrateStorage: () => {...},
    }
  )
);
```

**New structure**:
```typescript
export const useAuthStore = create<AuthStore>((set, get) => ({
  // ... state and actions (no _hasHydrated needed)
}));
```

**Removals**:
1. Remove `persist()` wrapper
2. Remove `TOKEN_STORAGE_KEY` constant
3. Remove `_hasHydrated` from state
4. Remove `createJSONStorage()` configuration
5. Remove `partialize` configuration
6. Remove `onRehydrateStorage` callback
7. Remove `useHasHydrated` selector hook

### Phase 2: Update useSessionInit

**Current behavior**: Wait for hydration, then check if valid session was restored from localStorage.

**New behavior**: Initialize immediately, call /refresh to restore session from cookie.

**Changes**:
1. Remove hydration timeout logic
2. Remove hasHydrated dependency
3. Always call /refresh on init (cookie-based restore)
4. Simplify initialization flow

### Phase 3: Update useAuth

**Changes**:
1. Remove `hasHydrated` from return value
2. Remove hydration-related logic
3. Keep session refresh scheduling

### Phase 4: Update Tests

**Changes**:
1. Remove tests for hydration behavior
2. Update tests to not mock localStorage
3. Add tests for memory-only behavior

## Risks and Mitigations

| Risk | Probability | Impact | Mitigation |
|------|-------------|--------|------------|
| Breaking session restore | Medium | High | /refresh endpoint must work |
| Test failures | Medium | Medium | Update tests alongside code |
| User experience regression | Low | Medium | Cookie-based restore is transparent |

## Definition of Done

- [ ] persist() removed from auth-store.ts
- [ ] _hasHydrated and hydration logic removed
- [ ] useSessionInit simplified
- [ ] useAuth updated
- [ ] All tests pass
- [ ] No localStorage usage for auth
- [ ] PR created and merged
