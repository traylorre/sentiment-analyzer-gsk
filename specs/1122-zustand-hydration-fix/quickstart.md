# Quickstart: Zustand Persist Hydration Fix

**Feature**: 1122-zustand-hydration-fix
**Date**: 2026-01-03

## Overview

This fix implements proper hydration handling for zustand persist middleware in a Next.js App Router application. The solution uses the `onRehydrateStorage` callback to expose a `_hasHydrated` flag that components check before reading auth state.

## Key Concepts

### The Problem

```typescript
// BEFORE: Race condition
useEffect(() => {
  // This runs immediately on mount
  // But zustand persist hasn't rehydrated from localStorage yet!
  const { isAuthenticated } = useAuthStore.getState()
  if (!isAuthenticated) {
    signInAnonymous() // Wrong! We haven't checked localStorage yet
  }
}, [])
```

### The Solution

```typescript
// AFTER: Wait for hydration
const hasHydrated = useHasHydrated()
const { isAuthenticated } = useAuth()

useEffect(() => {
  if (!hasHydrated) return // Wait for zustand to rehydrate

  if (!isAuthenticated) {
    signInAnonymous() // Correct! We've checked localStorage
  }
}, [hasHydrated, isAuthenticated])
```

## Quick Reference

### Check Hydration Status

```typescript
import { useHasHydrated } from '@/stores/auth-store'

function MyComponent() {
  const hasHydrated = useHasHydrated()

  if (!hasHydrated) {
    return <Skeleton /> // Show placeholder during hydration
  }

  // Safe to read auth state now
  return <AuthDependentContent />
}
```

### Protect Routes

```typescript
import { ProtectedRoute } from '@/components/auth/protected-route'

// ProtectedRoute now checks _hasHydrated internally
// Shows loading state during hydration, then checks auth
function DashboardPage() {
  return (
    <ProtectedRoute>
      <Dashboard />
    </ProtectedRoute>
  )
}
```

### React Query with Hydration

```typescript
import { useQuery } from '@tanstack/react-query'
import { useHasHydrated } from '@/stores/auth-store'
import { useUser } from '@/stores/auth-store'

function useChartData() {
  const hasHydrated = useHasHydrated()
  const user = useUser()

  return useQuery({
    queryKey: ['chart-data', user?.userId],
    queryFn: fetchChartData,
    // Only enable after hydration AND user is available
    enabled: hasHydrated && !!user?.userId,
  })
}
```

## File Changes Summary

| File | Change |
|------|--------|
| `stores/auth-store.ts` | Add `_hasHydrated`, `onRehydrateStorage`, `useHasHydrated` |
| `hooks/use-session-init.ts` | Wait for `_hasHydrated` before init |
| `hooks/use-auth.ts` | Expose `hasHydrated` in return value |
| `hooks/use-chart-data.ts` | Add hydration check to `enabled` |
| `components/auth/protected-route.tsx` | Check hydration before auth |
| `components/auth/user-menu.tsx` | Show skeleton during hydration |

## Testing

### Unit Test: Hydration Flag

```typescript
import { useAuthStore } from '@/stores/auth-store'

test('_hasHydrated starts false', () => {
  expect(useAuthStore.getState()._hasHydrated).toBe(false)
})

test('_hasHydrated becomes true after rehydration', async () => {
  // Simulate persist rehydration
  await useAuthStore.persist.rehydrate()
  expect(useAuthStore.getState()._hasHydrated).toBe(true)
})
```

### Integration Test: Session Restoration

```typescript
test('returns existing session without API call', async () => {
  // Pre-populate localStorage
  localStorage.setItem('sentiment-auth-tokens', JSON.stringify({
    state: {
      user: mockUser,
      tokens: mockTokens,
      isAuthenticated: true,
    }
  }))

  // Render app
  render(<App />)

  // Should restore session, not call API
  await waitFor(() => {
    expect(screen.queryByText('Initializing...')).not.toBeInTheDocument()
  })

  expect(mockSignInAnonymous).not.toHaveBeenCalled()
})
```

## Debugging

### Check Hydration Status in DevTools

```javascript
// In browser console
window.__ZUSTAND_AUTH_STORE__ = useAuthStore
console.log(useAuthStore.getState()._hasHydrated)
```

### Common Issues

1. **Still stuck on "Initializing..."**
   - Check `localStorage` has valid `sentiment-auth-tokens` key
   - Verify `_hasHydrated` becomes true (check in devtools)
   - Ensure no errors in `onRehydrateStorage` callback

2. **Flash of sign-in button**
   - Verify `UserMenu` checks `hasHydrated` before rendering
   - Ensure skeleton is returned when `!hasHydrated`

3. **React Query not refetching**
   - Verify `enabled` includes `hasHydrated`
   - Check `queryKey` includes `userId` to trigger refetch on change
