# Implementation Plan: Fix Zustand Persist Hydration

**Branch**: `1122-zustand-hydration-fix` | **Date**: 2026-01-03 | **Spec**: `specs/1122-zustand-hydration-fix/spec.md`
**Input**: Feature specification from `/specs/1122-zustand-hydration-fix/spec.md`

**Note**: This template is filled in by the `/speckit.plan` command. See `.specify/templates/commands/plan.md` for the execution workflow.

## Summary

Fix dashboard "Initializing session..." infinite hang by implementing proper zustand persist hydration handling. The root cause is that `useSessionInit` reads zustand state before the persist middleware completes async rehydration from localStorage. Solution implements progressive hydration with `_hasHydrated` flag exposed via `onRehydrateStorage` callback, ensuring auth-dependent components wait for hydration before evaluating state.

## Technical Context

**Language/Version**: TypeScript 5.x, React 18.x, Next.js 14.x (App Router)
**Primary Dependencies**: zustand 5.x, @tanstack/react-query, next-auth (not used - custom auth), tailwindcss
**Storage**: localStorage (zustand persist), React Query cache
**Testing**: vitest, @testing-library/react
**Target Platform**: Web (Next.js App Router with SSR)
**Project Type**: web (frontend + backend)
**Performance Goals**: Dashboard interactive within 5 seconds, returning users <2 seconds
**Constraints**: No "Initializing session..." visible for >3 seconds; UI must never flash incorrect auth state
**Scale/Scope**: ~11 files affected per spec breakage analysis

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Gate | Status | Notes |
|------|--------|-------|
| Implementation Accompaniment Rule | ✅ PASS | Unit tests required for all new hooks/components |
| External Dependency Mocking | ✅ PASS | Auth API calls mocked in tests |
| Deterministic Time Handling | ✅ PASS | No date.today() usage - session expiry uses fixed test values |
| Pre-Push Requirements | ✅ PASS | GPG-signed commits, feature branch workflow |
| Local SAST Requirement | ✅ PASS | No security-sensitive changes - UI-only hydration logic |
| Tech Debt Tracking | ✅ N/A | No shortcuts introduced |

## Project Structure

### Documentation (this feature)

```text
specs/1122-zustand-hydration-fix/
├── plan.md              # This file (/speckit.plan command output)
├── research.md          # Phase 0 output (/speckit.plan command)
├── data-model.md        # Phase 1 output (/speckit.plan command)
├── quickstart.md        # Phase 1 output (/speckit.plan command)
├── contracts/           # Phase 1 output (/speckit.plan command)
└── tasks.md             # Phase 2 output (/speckit.tasks command - NOT created by /speckit.plan)
```

### Source Code (repository root)

```text
frontend/
├── src/
│   ├── stores/
│   │   └── auth-store.ts        # Add _hasHydrated + onRehydrateStorage
│   ├── hooks/
│   │   ├── use-auth.ts          # Wait for _hasHydrated before auth checks
│   │   ├── use-session-init.ts  # Centralize init, wait for hydration
│   │   └── use-chart-data.ts    # Re-enable queries on userId transition
│   ├── components/
│   │   └── auth/
│   │       ├── protected-route.tsx  # Check _hasHydrated before auth state
│   │       └── user-menu.tsx        # Skeleton during hydration
│   └── app/
│       └── (dashboard)/
│           └── settings/
│               └── page.tsx     # Hydration-aware rendering
└── tests/
    └── unit/
        ├── stores/
        │   └── auth-store.test.ts
        └── hooks/
            ├── use-auth.test.ts
            └── use-session-init.test.ts
```

**Structure Decision**: Web application structure - frontend changes only. No backend modifications required.

## Complexity Tracking

> No constitution violations. Implementation follows established zustand patterns.

## Current Architecture Analysis

### Problem Root Cause

1. Page loads → Next.js SSR renders with zustand initial state (empty)
2. Client hydrates → React mounts components
3. `useSessionInit` hook runs in useEffect → reads `isAuthenticated: false` (zustand hasn't rehydrated yet)
4. Hook calls `signInAnonymous()` thinking there's no session
5. Meanwhile, zustand persist middleware asynchronously rehydrates from localStorage
6. Race condition: Which completes first - API call or localStorage read?
7. Result: State becomes inconsistent, `isInitialized` never set correctly, infinite loading

### Current Flow (Broken)

```
Mount → useEffect runs → reads empty state → signInAnonymous() → ???
                    ↓ (async, races)
         zustand persist rehydrates from localStorage
```

### Target Flow (Fixed)

```
Mount → zustand persist rehydrates → onRehydrateStorage fires → _hasHydrated: true
                                                                      ↓
                                            useSessionInit waits for _hasHydrated
                                                                      ↓
                                            Then reads state → valid session? skip API : signInAnonymous()
```

## Implementation Approach

### Phase 1: Auth Store Hydration Flag (FR-013)

Add `_hasHydrated` boolean to auth store state:

```typescript
interface AuthState {
  // ... existing fields
  _hasHydrated: boolean  // NEW: true after persist rehydrates
}

const useAuthStore = create<AuthState>()(
  persist(
    (set, get) => ({
      _hasHydrated: false,
      // ... existing state and actions
    }),
    {
      name: 'sentiment-auth-tokens',
      onRehydrateStorage: () => (state) => {
        // Called AFTER rehydration completes
        useAuthStore.setState({ _hasHydrated: true })
      },
      // ... existing config
    }
  )
)

// Export hook for components to check hydration status
export const useHasHydrated = () => useAuthStore((s) => s._hasHydrated)
```

### Phase 2: Hook Modifications

**use-session-init.ts** (FR-016):
- Wait for `_hasHydrated === true` before reading auth state
- Use `useEffect` dependency on `_hasHydrated` to trigger init only after hydration
- Prevent multiple init attempts via ref

**use-auth.ts**:
- Expose `_hasHydrated` in return value for components
- Session refresh scheduling waits for hydration

**use-chart-data.ts** (FR-015):
- Add `refetch` trigger when userId transitions from null → valid value
- Use React Query's `enabled` option with proper dependency

### Phase 3: Component Updates

**ProtectedRoute** (FR-014):
- Check `_hasHydrated` BEFORE evaluating `isAuthenticated`
- Show skeleton/spinner during hydration phase
- Only redirect after hydration complete + auth check fails

**UserMenu** (FR-017):
- Render skeleton during `_hasHydrated === false`
- Never flash "Sign in" button for returning authenticated users

**Settings Page** (FR-018):
- Add hydration boundary to prevent fallback UI flash

## Risk Mitigation

| Risk | Mitigation |
|------|------------|
| Breaking existing auth flow | Unit tests for all modified hooks/components |
| Infinite loading if hydration fails | Timeout fallback after 5 seconds (FR-006 compatible) |
| Multiple component instances racing init | useRef guard in useSessionInit |
| localStorage unavailable | Graceful fallback to in-memory (FR-004) |

## Dependencies

- zustand 5.x `onRehydrateStorage` callback (documented pattern)
- React 18 concurrent features (already in use)
- No new dependencies required
