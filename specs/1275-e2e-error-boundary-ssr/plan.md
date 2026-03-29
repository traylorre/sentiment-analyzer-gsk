# Feature 1275: e2e-error-boundary-ssr - Implementation Plan

## Architecture Decision

### Approach: useState + useEffect (Post-Mount State Flip)

The fix uses React's standard client-side lifecycle to defer the flag check until after hydration:

1. Component renders normally during SSR and hydration (no mismatch)
2. `useEffect` fires after mount, checks `window.__TEST_FORCE_ERROR`
3. If flag is set, `setShouldError(true)` triggers a re-render
4. Re-render throws synchronously, caught by ErrorBoundary

### Why Not Alternatives

| Approach | Rejected Because |
|----------|-----------------|
| `useLayoutEffect` | React warns about it during SSR; unnecessary for visual transitions |
| `useSyncExternalStore` | Overengineered for a boolean test flag |
| `dynamic({ ssr: false })` | Changes loading behavior for non-test scenarios |
| Fix in tests (not component) | Tests are correct; component is the bug |
| `suppressHydrationWarning` | Masks the problem; doesn't fix the timing issue |

## Implementation Steps

### Step 1: Modify ErrorTrigger Component

**File**: `frontend/src/components/ui/error-trigger.tsx`

**Changes**:
1. Add `useState` and `useEffect` imports
2. Add `shouldError` state initialized to `false`
3. Move `window.__TEST_FORCE_ERROR` check into `useEffect` (runs after mount)
4. Keep the synchronous throw based on state (React can catch this in render)
5. Keep production early-return unchanged (no hooks in production path -- wait, hooks can't be conditional. See note below.)

**Important**: React hooks cannot be called conditionally. The production early-return BEFORE hooks would violate Rules of Hooks. Two solutions:

**Option A**: Move production check after hooks (hooks are no-ops in production):
```tsx
export function ErrorTrigger({ children }: ErrorTriggerProps) {
  const [shouldError, setShouldError] = useState(false);

  useEffect(() => {
    if (
      process.env.NODE_ENV !== 'production' &&
      typeof window !== 'undefined' &&
      window.__TEST_FORCE_ERROR
    ) {
      setShouldError(true);
    }
  }, []);

  if (shouldError) {
    throw new Error('TEST_FORCE_ERROR: Intentional error triggered by E2E test');
  }

  return <>{children}</>;
}
```

**Option B**: Split into two components -- inner with hooks, outer production gate:
```tsx
function ErrorTriggerInner({ children }: ErrorTriggerProps) {
  const [shouldError, setShouldError] = useState(false);
  useEffect(() => {
    if (typeof window !== 'undefined' && window.__TEST_FORCE_ERROR) {
      setShouldError(true);
    }
  }, []);
  if (shouldError) {
    throw new Error('TEST_FORCE_ERROR: ...');
  }
  return <>{children}</>;
}

export function ErrorTrigger({ children }: ErrorTriggerProps) {
  if (process.env.NODE_ENV === 'production') {
    return <>{children}</>;
  }
  return <ErrorTriggerInner>{children}</ErrorTriggerInner>;
}
```

**Decision**: Option B. It preserves zero-overhead in production (no hooks allocated) while keeping hooks unconditional in the inner component. The outer component is a simple conditional wrapper that tree-shakers can eliminate.

### Step 2: Verify Tests

Run both test suites to confirm:
1. `chaos-accessibility.spec.ts` T026, T027 now pass
2. `chaos-error-boundary.spec.ts` T022, T023, T024 still pass

No test modifications needed.

## Component Interaction Diagram

```
Server Render:
  ErrorTrigger -> ErrorTriggerInner -> renders {children}
  (useEffect doesn't fire on server)

Client Hydration:
  ErrorTrigger -> ErrorTriggerInner -> renders {children} (matches server)
  useEffect fires -> detects flag -> setShouldError(true)

Re-render:
  ErrorTriggerInner -> shouldError is true -> throws Error
  ErrorBoundary.getDerivedStateFromError -> hasError: true
  ErrorBoundary.render -> ErrorFallback UI

Test sees: "Something went wrong" heading + action buttons
```

## Rollback Plan

If the fix causes unexpected issues:
1. Revert `error-trigger.tsx` to the synchronous check
2. The tests will revert to their current flaky/failing state
3. No production impact in either direction

## Verification Matrix

| Test | File | Expected Result |
|------|------|----------------|
| T022 | chaos-error-boundary.spec.ts | PASS (existing) |
| T023 | chaos-error-boundary.spec.ts | PASS (existing) |
| T024 | chaos-error-boundary.spec.ts | PASS (existing) |
| T025 | chaos-accessibility.spec.ts | PASS (unrelated to error boundary) |
| T026 | chaos-accessibility.spec.ts | PASS (currently FAIL) |
| T027 | chaos-accessibility.spec.ts | PASS (currently FAIL) |
