# Feature 1275: e2e-error-boundary-ssr

## Status: Draft
## Priority: High (blocks accessibility test suite)
## Type: Bug Fix

## Problem

Two E2E tests in `chaos-accessibility.spec.ts` fail because the `ErrorTrigger` component checks `window.__TEST_FORCE_ERROR` synchronously during render. Next.js server-side renders the component first (where `typeof window === 'undefined'` skips the check), then React 18 hydration may not reliably re-execute the render in a way that triggers the error. The error boundary fallback never appears, and the tests time out.

The identical `addInitScript` + `goto('/')` pattern works in `chaos-error-boundary.spec.ts`, but the mechanism is fundamentally fragile due to hydration timing.

## Acceptance Criteria

### AC-1: ErrorTrigger is SSR-safe
**Given** `window.__TEST_FORCE_ERROR` is set via `addInitScript`,
**When** Next.js server-renders the page and React hydrates on the client,
**Then** `ErrorTrigger` detects the flag after hydration completes and throws, triggering the `ErrorBoundary` fallback.

### AC-2: chaos-accessibility.spec.ts T026 passes
**Given** the error boundary is triggered via `__TEST_FORCE_ERROR`,
**When** the accessibility test scans for WCAG 2.1 AA violations,
**Then** the test finds the "Something went wrong" heading, runs AxeBuilder, and reports zero critical/serious violations.

### AC-3: chaos-accessibility.spec.ts T027 passes
**Given** the error boundary is triggered via `__TEST_FORCE_ERROR`,
**When** the test checks keyboard focusability,
**Then** "Try Again", "Reload Page", and "Go Home" buttons are all visible and focusable.

### AC-4: chaos-error-boundary.spec.ts continues to pass
**Given** the existing error boundary tests use the same `__TEST_FORCE_ERROR` mechanism,
**When** ErrorTrigger is updated to use SSR-safe state management,
**Then** all existing tests in `chaos-error-boundary.spec.ts` (T022, T023, T024) continue to pass.

### AC-5: No production behavior change
**Given** `ErrorTrigger` checks `process.env.NODE_ENV === 'production'` first,
**When** the app runs in production,
**Then** ErrorTrigger is a transparent passthrough with zero overhead (no hooks, no state).

## Technical Design

### Current Implementation (broken)

```tsx
export function ErrorTrigger({ children }: ErrorTriggerProps) {
  if (process.env.NODE_ENV === 'production') {
    return <>{children}</>;
  }
  // PROBLEM: This check runs during render. SSR skips it (no window).
  // Hydration may not re-execute this reliably.
  if (typeof window !== 'undefined' && window.__TEST_FORCE_ERROR) {
    throw new Error('TEST_FORCE_ERROR: ...');
  }
  return <>{children}</>;
}
```

### Fixed Implementation

```tsx
export function ErrorTrigger({ children }: ErrorTriggerProps) {
  if (process.env.NODE_ENV === 'production') {
    return <>{children}</>;
  }

  const [shouldError, setShouldError] = useState(false);

  useEffect(() => {
    if (typeof window !== 'undefined' && window.__TEST_FORCE_ERROR) {
      setShouldError(true);
    }
  }, []);

  if (shouldError) {
    throw new Error('TEST_FORCE_ERROR: Intentional error triggered by E2E test');
  }

  return <>{children}</>;
}
```

**How this fixes the issue:**
1. First render (SSR): `shouldError` is `false`, renders `{children}` -- matches server HTML
2. Hydration: React attaches to server HTML, `shouldError` is still `false` -- no mismatch
3. `useEffect` fires after mount: Detects the flag, sets `shouldError = true`
4. Re-render: `shouldError` is `true`, component throws
5. `ErrorBoundary.getDerivedStateFromError` catches the error, renders fallback

### Why `useEffect` (not `useLayoutEffect`)

- `useEffect` fires after paint, which is fine because the error boundary transition is visual
- `useLayoutEffect` warns in SSR contexts and is unnecessary here
- The brief flash of children before error boundary is imperceptible (single frame)

## Scope

### In Scope
- Fix `ErrorTrigger` component to be SSR-hydration-safe
- Verify all error boundary E2E tests pass

### Out of Scope
- Modifying test files (tests are correct; the component is the bug)
- Production code paths (production returns early, never touches hooks)
- Other error boundary behaviors (reset, reload, go home actions)

## Dependencies
- None. Single-file change to `error-trigger.tsx`.

## Risk
- **Low**: Test-only component, production path unchanged
- **Regression risk**: Mitigated by verifying both test suites pass
