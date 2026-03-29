# Feature 1275: e2e-error-boundary-ssr - Research

## Problem Statement

Two E2E tests in `chaos-accessibility.spec.ts` fail because the error boundary fallback never renders, despite `addInitScript` correctly setting `window.__TEST_FORCE_ERROR = true`. The identical pattern works in `chaos-error-boundary.spec.ts`.

### Failing Tests
- T026: "error boundary fallback has zero critical accessibility violations" (line 68)
- T027: "error boundary buttons are keyboard-focusable with accessible labels" (line 109)

## Root Cause Analysis

### The ErrorTrigger Component

```tsx
// frontend/src/components/ui/error-trigger.tsx
export function ErrorTrigger({ children }: ErrorTriggerProps) {
  if (process.env.NODE_ENV === 'production') {
    return <>{children}</>;
  }
  if (typeof window !== 'undefined' && window.__TEST_FORCE_ERROR) {
    throw new Error('TEST_FORCE_ERROR: Intentional error triggered by E2E test');
  }
  return <>{children}</>;
}
```

### The SSR/Hydration Problem

1. **Server-side render**: Next.js renders `ErrorTrigger` on the server. `typeof window === 'undefined'` is `true`, so the flag check is skipped. Server emits clean HTML with `{children}` rendered.

2. **Client hydration**: React 18 receives the server HTML and hydrates. During hydration, React re-executes component render functions. `window.__TEST_FORCE_ERROR` is `true` (set by `addInitScript`), so `ErrorTrigger` throws.

3. **The race condition**: The throw during hydration is caught by `ErrorBoundary.getDerivedStateFromError()`. However, React 18's hydration error handling has a nuance: if a hydration error occurs, React may attempt to recover by doing a **full client-side re-render** (discarding server HTML). In concurrent mode (default in React 18), this recovery can race with component mounting.

### Why chaos-error-boundary.spec.ts Passes

Both files use the same `addInitScript` + `goto('/')` pattern. The difference is in the `beforeEach`:

| File | beforeEach | Error trigger timing |
|------|-----------|---------------------|
| `chaos-error-boundary.spec.ts` | `goto('/') + waitForTimeout(2000)` | `forceErrorBoundary()` adds init script + navigates again |
| `chaos-accessibility.spec.ts` | `goto('/') + waitForLoadState('networkidle')` | Test body adds init script + navigates again |

The structural pattern is the same. However, `chaos-error-boundary.spec.ts` may pass due to:
- Timing differences from `waitForTimeout(2000)` vs `waitForLoadState('networkidle')`
- Different test runner ordering/parallelism affecting page cache
- The passing tests might be flaky themselves (passing most of the time but not 100%)

### The Fundamental Fragility

The real issue is architectural: **checking a synchronous render-time flag is incompatible with SSR hydration**. The flag check happens during render, but:

1. SSR skips it (`typeof window === 'undefined'`)
2. Hydration may or may not re-execute the render depending on React's internal state reconciliation
3. React 18 Strict Mode double-renders in dev, adding another variable
4. The hydration mismatch (server rendered children, client wants to throw) triggers React's hydration error recovery, which has unpredictable timing

### The Correct Fix

Instead of checking `window.__TEST_FORCE_ERROR` synchronously during render, the component should:

1. **Render normally on first pass** (matching server HTML)
2. **Use `useEffect` + `useState` to check the flag after mount** (client-only)
3. **Trigger a re-render that throws** (caught by ErrorBoundary)

This approach:
- Avoids hydration mismatch (server and initial client render both return `{children}`)
- Guarantees the flag is checked only on the client
- Triggers a clean re-render that throws, which ErrorBoundary handles predictably

### Alternative Approaches Considered

1. **`useLayoutEffect` instead of `useEffect`**: Fires synchronously after DOM mutation but before paint. Would work but is warned against in SSR contexts by React.

2. **`useSyncExternalStore` with server snapshot**: Could provide different values for server vs client, but overengineered for a test-only flag.

3. **Next.js `dynamic()` with `ssr: false`**: Would skip SSR entirely for ErrorTrigger. Works but changes the component's loading behavior in non-test scenarios.

4. **Move the check to a `useEffect` that sets state, then throw on next render**: This is the recommended approach. Clean, predictable, SSR-safe.

## Test Infrastructure Analysis

### Playwright `addInitScript`

`addInitScript` adds a script that runs in the page context **before any page JavaScript**. This means:
- The flag IS set before React hydrates
- The flag IS available during the first client-side render
- The issue is that React 18 hydration may not always trigger a full re-render of every component

### React 18 Hydration Behavior

React 18 hydration has three relevant behaviors:
1. **Normal hydration**: Attaches event handlers to server HTML without re-rendering
2. **Hydration mismatch**: If client render differs from server HTML, React logs a warning and does client-side re-render
3. **Hydration error**: If client render throws, React discards server HTML and does full client render

The current code path triggers #3 (hydration error from throw), which is unpredictable in timing.

## Files Affected

| File | Change Type | Description |
|------|------------|-------------|
| `frontend/src/components/ui/error-trigger.tsx` | Modify | Use `useState` + `useEffect` for SSR-safe flag checking |
| `frontend/tests/e2e/chaos-accessibility.spec.ts` | Verify | Should pass without modification after component fix |
| `frontend/tests/e2e/chaos-error-boundary.spec.ts` | Verify | Should continue to pass after component fix |

## Risk Assessment

- **Low risk**: Change is isolated to a test-only component (`ErrorTrigger`)
- **No production impact**: Component is a passthrough in production (`NODE_ENV === 'production'`)
- **Backward compatible**: Same `window.__TEST_FORCE_ERROR` API, same `addInitScript` pattern in tests
- **No test changes needed**: Tests use the same trigger mechanism; only the component internals change
