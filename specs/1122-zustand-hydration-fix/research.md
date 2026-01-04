# Research: Zustand Persist Hydration Fix

**Feature**: 1122-zustand-hydration-fix
**Date**: 2026-01-03

## Research Tasks Completed

### 1. Zustand Persist Hydration Pattern

**Decision**: Use `onRehydrateStorage` callback with `_hasHydrated` flag

**Rationale**: This is the official zustand pattern for detecting hydration completion. The `onRehydrateStorage` callback receives the hydrated state and fires AFTER localStorage data is restored. This is the recommended approach per zustand documentation.

**Alternatives Considered**:
1. **Manual `hasHydrated()` method**: Requires polling or subscription - more complex, less React-idiomatic
2. **`skipHydration: true` + manual hydration**: Gives full control but requires rewriting persist middleware usage
3. **`useLayoutEffect` timing hack**: Unreliable, doesn't guarantee hydration complete

**Source**: zustand persist middleware documentation, community patterns

### 2. Next.js App Router SSR + Zustand Integration

**Decision**: Check `_hasHydrated` in components that read auth state before rendering auth-dependent UI

**Rationale**: Next.js App Router renders on server first with initial zustand state (empty). Client hydration mounts React, but zustand persist rehydrates asynchronously AFTER React mount. Components that read zustand state in early lifecycle (useEffect with empty deps) will see stale initial state.

**Key Insight**: The `useEffect(() => {...}, [])` pattern runs BEFORE zustand persist completes. The solution is to make the effect depend on `_hasHydrated` so it re-runs after hydration.

**Alternatives Considered**:
1. **`use client` directive everywhere**: Doesn't solve timing - client components still have async hydration
2. **Context Provider wrapper**: Adds complexity without solving the fundamental timing issue
3. **Dynamic import with ssr: false**: Prevents SSR benefits, slower initial load

### 3. React Query Integration with Hydration

**Decision**: Use `enabled` option with proper dependency tracking for userId transitions

**Rationale**: React Query's `enabled: !!userId` pattern works, but the query won't re-enable when userId transitions from null → valid. Need to track the transition and trigger refetch.

**Pattern**:
```typescript
const { data, refetch } = useQuery({
  queryKey: ['chart-data', userId],
  queryFn: fetchChartData,
  enabled: hasHydrated && !!userId,  // Wait for hydration + valid userId
})

// Trigger refetch when userId becomes available after hydration
useEffect(() => {
  if (hasHydrated && userId) {
    refetch()
  }
}, [hasHydrated, userId, refetch])
```

### 4. Progressive Hydration Best Practices

**Decision**: Each component handles own hydration state; no global blocking loader

**Rationale**: Per spec requirements (FR-011, FR-012), components hydrate independently. The Header renders immediately; only session-dependent elements (UserMenu) show skeleton during hydration.

**Pattern**:
```typescript
// UserMenu renders skeleton during hydration
function UserMenu() {
  const hasHydrated = useHasHydrated()
  const { user, isAuthenticated } = useAuth()

  if (!hasHydrated) {
    return <UserMenuSkeleton />  // Placeholder during hydration
  }

  if (!isAuthenticated) {
    return <SignInButton />
  }

  return <UserDropdown user={user} />
}
```

### 5. Timeout Fallback Strategy

**Decision**: 5-second timeout with inline error banner (not blocking modal)

**Rationale**: Per FR-006, if hydration/initialization exceeds 15 seconds, show inline error with retry. We implement a 5-second initial timeout for hydration specifically (hydration should be sub-second from localStorage), with separate 15-second timeout for API calls.

**Pattern**:
```typescript
const HYDRATION_TIMEOUT_MS = 5000

useEffect(() => {
  if (hasHydrated) return

  const timeout = setTimeout(() => {
    // Hydration timed out - localStorage may be blocked
    console.error('Zustand hydration timeout')
    // Proceed with empty state, let signInAnonymous handle it
  }, HYDRATION_TIMEOUT_MS)

  return () => clearTimeout(timeout)
}, [hasHydrated])
```

## Codebase Analysis

### Current Store Structure

| Store | File | Persistent | Hydration Concern |
|-------|------|------------|-------------------|
| auth-store | `stores/auth-store.ts` | Yes | **PRIMARY FIX TARGET** - needs `_hasHydrated` |
| config-store | `stores/config-store.ts` | Yes (partial) | Secondary - only persists activeConfigId |
| runtime-store | `stores/runtime-store.ts` | No | Not affected - fetches fresh each load |
| chart-store | `stores/chart-store.ts` | Check | May need hydration awareness |

### Components Requiring Modification

**Critical (Must Address)**:
1. `stores/auth-store.ts` - Add `_hasHydrated` + `onRehydrateStorage`
2. `hooks/use-session-init.ts` - Wait for hydration before init
3. `hooks/use-auth.ts` - Expose hasHydrated, wait for it in scheduling
4. `components/auth/protected-route.tsx` - Check hydration before auth
5. `hooks/use-chart-data.ts` - Re-enable on userId transition

**High (Should Address)**:
6. `components/auth/user-menu.tsx` - Skeleton during hydration

**Medium (Can Defer)**:
7. `app/(dashboard)/settings/page.tsx` - Hydration-aware rendering

## Testing Strategy

### Unit Tests Required

1. **auth-store.test.ts**:
   - `_hasHydrated` starts as false
   - `_hasHydrated` becomes true after persist rehydration simulation
   - `onRehydrateStorage` callback fires correctly

2. **use-session-init.test.ts**:
   - Does NOT call signInAnonymous before hydration
   - Calls signInAnonymous only after hydration if no session
   - Skips signInAnonymous if valid session exists after hydration

3. **protected-route.test.ts**:
   - Shows loading during hydration
   - Does NOT redirect during hydration
   - Redirects only after hydration + auth check fails

### Integration Test Considerations

- Mock localStorage with pre-populated session data
- Verify session restoration without API call
- Verify dashboard loads < 5 seconds with valid session

## References

- [Zustand Persist Middleware Docs](https://docs.pmnd.rs/zustand/integrations/persisting-store-data)
- [Next.js App Router Client Components](https://nextjs.org/docs/app/building-your-application/rendering/client-components)
- [React Query Dependent Queries](https://tanstack.com/query/latest/docs/react/guides/dependent-queries)
