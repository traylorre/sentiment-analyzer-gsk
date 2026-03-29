# Research: Accessibility Timing Audit

**Feature**: 1272-a11y-timing-audit
**Date**: 2026-03-28

## R1: Playwright waitForTimeout Replacement Patterns

### Decision
Replace all `waitForTimeout()` calls with context-appropriate Playwright primitives.

### Rationale
Playwright's architecture is built around auto-waiting. Every `expect(locator)` assertion auto-retries until the timeout expires. The `waitForResponse()` method waits for a specific network event. These are deterministic and adapt to actual system timing, unlike blind waits that are either too short (causing flake) or too long (wasting CI minutes).

### Replacement Map

| Context | Blind Wait | Event-Based Replacement |
|---------|-----------|------------------------|
| After `page.goto('/')` | `waitForTimeout(2000)` | `page.waitForLoadState('networkidle')` |
| After `searchInput.fill('X')` in error scenario | `waitForTimeout(1500)` | `page.waitForResponse(resp => resp.url().includes('/api/'))` |
| After error boundary trigger | `waitForTimeout(1000)` | Remove entirely -- subsequent `toBeVisible({ timeout })` handles the wait |
| After recovery action (fill + route change) | `waitForTimeout(2000)` | `page.waitForResponse()` on the success route |
| SSE reconnection wait | `waitForTimeout(5000)` | `expect.poll(() => counter, { timeout: 10000 })` |
| After `blockAllApi()` to observe effect | `waitForTimeout(2000)` | `page.waitForLoadState('networkidle')` or subsequent `expect().toBeVisible()` |

### Alternatives Considered

1. **Increase blind wait times**: Rejected -- makes tests slower and still non-deterministic on resource-constrained CI runners.
2. **page.waitForSelector()**: Rejected -- lower-level API than `expect(locator)`. The locator-based API is Playwright's recommended approach.
3. **Custom retry loops**: Rejected -- `expect.poll()` already provides this pattern with built-in timeout and error messages.

## R2: ARIA Assertion Timeout Behavior

### Decision
Add `{ timeout: 3000 }` to all ARIA attribute assertions that follow visibility checks.

### Rationale
Playwright's `toHaveAttribute()` has two modes:
1. **Value check**: `toHaveAttribute('aria-pressed', 'true')` -- auto-retries because it's comparing against an expected value
2. **Existence check**: `toHaveAttribute('aria-pressed')` -- may resolve immediately if the attribute exists with any value, but the attribute may not yet exist in the accessibility tree

The race condition is: `toBeVisible()` resolves (element is in DOM and viewport), but the browser has not yet computed ARIA attributes from React's virtual DOM updates. Adding an explicit timeout ensures the assertion retries long enough for the accessibility tree to catch up.

3000ms was chosen because:
- The axe-core race condition in Feature 1270 was resolved with 5000ms for complex scans
- Simple attribute checks need less time than full axe scans
- 3000ms provides 30x margin over typical 100ms tree stabilization

### Alternatives Considered
1. **Use `waitForAccessibilityTree()` from Feature 1270**: Rejected for non-axe cases -- overkill for simple attribute assertions. The helper uses `page.waitForFunction()` which is heavier than the built-in assertion retry.
2. **Use default timeout (5000ms)**: The default only applies to value-based assertions. Existence checks may not retry. Explicit is better than implicit.

## R3: triggerHealthBanner() Refactoring

### Decision
Replace blind waits with `Promise.all([waitForResponse(), searchInput.fill()])` pattern.

### Rationale
The helper calls `page.route('**/api/**', handler)` which intercepts all API calls and fulfills them with 503. When `searchInput.fill('X')` triggers a React Query fetch, the route handler fulfills immediately. `waitForResponse()` resolves when the browser receives that 503 response, proving the failure was recorded by the health store.

The `Promise.all` pattern is a standard Playwright idiom for "do action and wait for its side effect":
```typescript
await Promise.all([
  page.waitForResponse(resp => resp.url().includes('/api/')),
  searchInput.fill('AAPL'),
]);
```

### Risk Assessment
- **Low**: The route handler fulfills synchronously, so `waitForResponse` resolves almost immediately after the fetch fires
- **Medium**: React Query's 500ms debounce delays the actual fetch. `waitForResponse` handles this naturally (it waits for the response, whenever it arrives)
- **Low**: Other callers of `triggerHealthBanner()` (chaos-error-boundary.spec.ts) will run faster because they no longer wait 4.5s of blind delays

### Alternatives Considered
1. **Keep blind waits in helper, only fix callers**: Rejected -- cosmetic fix. The same anti-pattern executes indirectly.
2. **Add a parameter to opt into event-based waiting**: Rejected -- overengineered. All callers benefit from the fix.

## R4: Files Affected and Instance Counts

| File | waitForTimeout Count | ARIA Race Count | Total Changes |
|------|---------------------|-----------------|---------------|
| chaos-helpers.ts (triggerHealthBanner) | 3 | 0 | 3 |
| chaos-degradation.spec.ts | 7 | 1 | 8 |
| error-visibility-banner.spec.ts | 19 | 1 | 20 |
| chaos-cross-browser.spec.ts | 3 | 1 | 4 |
| chaos-accessibility.spec.ts | 3 | 0 | 3 |
| sanity.spec.ts | 0 | 5 | 5 |
| **Total** | **35** | **8** | **43** |
