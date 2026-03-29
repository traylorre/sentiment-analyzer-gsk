# Feature 1275: Adversarial Review

## Review Focus: Correctness and Completeness

### Finding 1: Rules of Hooks Violation in Original Code
**Severity**: Critical (would cause runtime error)
**Status**: RESOLVED in plan

The original code has an early return before any hooks. If we naively add hooks after the production check, we'd violate Rules of Hooks (conditional hook calls). The plan correctly identifies this and uses the two-component pattern (Option B) to avoid it.

**Verification**: The outer `ErrorTrigger` never calls hooks. The inner `ErrorTriggerInner` always calls hooks unconditionally. Rules of Hooks satisfied.

### Finding 2: useEffect Dependency Array
**Severity**: Medium
**Status**: RESOLVED in plan

The `useEffect` uses an empty dependency array `[]`, meaning it only runs once on mount. This is correct because:
- `window.__TEST_FORCE_ERROR` is set by `addInitScript` before any JS runs
- The flag doesn't change during the page lifecycle
- We only need to check once

If someone later wants to toggle the flag dynamically (unlikely for a test flag), they'd need to add a polling mechanism. This is acceptable for the use case.

### Finding 3: Flash of Content Before Error Boundary
**Severity**: Low
**Status**: ACCEPTED

With `useEffect`, there will be a single frame where `{children}` renders before the error boundary kicks in. This is imperceptible to users and doesn't affect test assertions because:
- Tests use `await expect(...).toBeVisible({ timeout: 5000 })` which polls
- The error boundary renders within milliseconds of mount
- No visual flicker is detectable in E2E tests

### Finding 4: React StrictMode Double-Effect
**Severity**: Low
**Status**: VERIFIED SAFE

`reactStrictMode: true` in `next.config.js` causes `useEffect` to fire twice in development (mount -> unmount -> mount). This means:
1. First mount: `setShouldError(true)` -> throws -> ErrorBoundary catches
2. StrictMode unmounts and remounts: but ErrorBoundary already has `hasError: true`

The ErrorBoundary is a class component using `getDerivedStateFromError`, which persists through StrictMode re-renders. No issue.

### Finding 5: Could the Test Still Be Flaky?
**Severity**: Medium
**Status**: MITIGATED

The `useEffect` approach adds one render cycle of latency (vs synchronous throw). Could this cause tests to time out?

Analysis:
- `useEffect` fires in the same event loop tick as paint (microtask)
- The re-render from `setShouldError(true)` happens immediately after
- Total additional latency: <16ms (one frame)
- Tests have 5000ms timeout for visibility check
- 16ms << 5000ms: No timeout risk

### Finding 6: Production Bundle Size
**Severity**: None
**Status**: VERIFIED SAFE

The outer `ErrorTrigger` checks `process.env.NODE_ENV === 'production'` before rendering `ErrorTriggerInner`. In production builds:
- Next.js replaces `process.env.NODE_ENV` with `'production'` at build time
- The `if` branch is always true, the `else` (with `ErrorTriggerInner`) is dead code
- Tree shaking removes `ErrorTriggerInner` entirely from production bundle
- Zero overhead confirmed

### Finding 7: Test Files Don't Need Changes
**Severity**: Informational
**Status**: VERIFIED

Both test files use the same pattern:
```ts
await page.addInitScript(() => { (window as any).__TEST_FORCE_ERROR = true; });
await page.goto('/');
```

This pattern sets the flag before any page JS runs. The flag is available when `useEffect` fires. No test changes needed.

## Overall Assessment

**APPROVED**: The fix is minimal, correct, and addresses the root cause. The two-component pattern respects Rules of Hooks while maintaining zero production overhead. All edge cases (StrictMode, timing, tree-shaking) are handled.

## Recommendations

1. Add a brief comment in `ErrorTriggerInner` explaining why `useEffect` is used instead of a synchronous render check
2. The existing JSDoc already mentions SSR; update it to note the hydration-safe pattern
