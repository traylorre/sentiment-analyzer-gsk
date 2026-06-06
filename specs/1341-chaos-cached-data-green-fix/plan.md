# Implementation Plan -- Feature 1341: Fix Green Dashboard Syndrome in chaos-cached-data.spec.ts

## Files to Modify

### 1. `frontend/tests/e2e/chaos-cached-data.spec.ts` (PRIMARY -- only file)

All changes are within this single test file. No helper changes needed.

## Technical Context

### Current State (line references)

| Line | Current Code | Problem |
|------|-------------|---------|
| 18 | `await mockTickerDataApis(page)` | Return value (cleanup fn) discarded |
| 48-50 | `textBefore` captured but only checked for length | No comparison to textDuring |
| 63-65 | `textDuring` checked for `length > 10` only | No comparison to textBefore |
| 72 | `textBefore` captured but only checked truthy | No comparison to textDuring |
| 82-84 | `textDuring` checked for `length > 10` only | No comparison to textBefore |
| 93-96 | `.catch(() => {...})` on click | Swallows all errors |
| N/A | No chart check after blockAllApi | Chart may vanish undetected |
| N/A | No afterEach cleanup | Mock routes leak |

### Change Strategy

Four categories of change:
1. **Structural**: Add `afterEach` hook for cleanup, capture cleanup function
2. **Content comparison**: Add fragment comparison in both T013 and T014
3. **Chart persistence**: Add chart locator re-check in T013 after blocking
4. **Click assertion**: Remove catch, add visibility assert before click

## Implementation Plan

### Step 1: Add cleanup infrastructure

Add a `let` variable at describe scope to hold the cleanup function, and add `afterEach`:

```typescript
test.describe('Chaos: Cached Data Resilience', () => {
  let cleanupMocks: (() => Promise<void>) | undefined;

  test.beforeEach(async ({ page }) => {
    cleanupMocks = await mockTickerDataApis(page);
    // ... rest of beforeEach unchanged
  });

  test.afterEach(async () => {
    if (cleanupMocks) {
      await cleanupMocks();
      cleanupMocks = undefined;
    }
  });
```

### Step 2: Fix T013 -- content comparison and chart persistence

After existing `textDuring` assertions (line 65), add:
```typescript
// Verify content identity -- same data, not just "some content"
const fragment = textBefore!.substring(0, 20);
expect(textDuring).toContain(fragment);

// Verify chart persists through outage
const chartContainer = page.locator(
  '[role="img"][aria-label*="Price and sentiment chart"]',
);
await expect(chartContainer).toBeVisible({ timeout: 3000 });
```

### Step 3: Fix T014 -- content comparison and strict click

After existing `textDuring` assertions (line 84), add:
```typescript
const fragment = textBefore!.substring(0, 20);
expect(textDuring).toContain(fragment);
```

Replace lines 91-96 (click with catch):
```typescript
// BEFORE:
if (clickableCount > 0) {
  await clickableElements.first().click({ timeout: 3000 }).catch(() => {
    // Click may fail if element navigates -- that's OK, no crash is the test
  });
}

// AFTER:
if (clickableCount > 0) {
  // Assert element is still interactive during outage
  await expect(clickableElements.first()).toBeVisible({ timeout: 3000 });
  await clickableElements.first().click({ timeout: 3000 });
}
```

## Risk Assessment

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| Cleanup function call errors in afterEach | Very Low | Low | Guarded by `if (cleanupMocks)` check |
| Chart container selector mismatch | Very Low | Medium | Same selector used in beforeEach (proven working) |
| Click throws during outage | Low | Medium | If it throws, that's a real UX bug worth catching |
| Fragment comparison flaky with dynamic content | Low | Low | First 20 chars are stable header/ticker text |

---

## Appendix A: Adversarial Review #2 (Plan)

### AR2-Q1: Adding afterEach -- does this interact with Playwright's test isolation?
**Challenge**: Playwright creates a new browser context per test by default. Does
afterEach cleanup matter if the page is destroyed?
**Analysis**: Yes it matters because `mockTickerDataApis` calls `page.route()` which
registers handlers on the page object. Even though the page is destroyed, explicitly
cleaning up is good hygiene and prevents issues if test isolation changes. More
importantly, it documents the intent that these routes should be cleaned up.
**Verdict**: ACCEPT.

### AR2-Q2: Chart container check uses 3s timeout -- is that enough?
**Challenge**: The chart was already verified in beforeEach. After `blockAllApi`, we just
need to confirm it didn't vanish. The chart canvas is already rendered in the DOM and
React Query doesn't remove it on failed refetch.
**Analysis**: 3s is generous for a "still there?" check. The chart doesn't re-render on
failed refetches; it retains its last successful render.
**Verdict**: ACCEPT.

### AR2-Q3: Removing catch from click -- what if element is an `<a>` that navigates?
**Challenge**: The original comment says "Click may fail if element navigates." If the
click triggers navigation, Playwright may throw.
**Analysis**: During an API outage with `blockAllApi`, navigation links that hit API
endpoints will fail. But the element locator `'button, a, [role="button"]'` includes
links. A navigation during outage IS a bug (user gets lost). However, to be safe, the
fix asserts visibility first, then clicks. If the click navigates, the next test's
beforeEach will handle page state. The test already passed its content assertions.
**Verdict**: ACCEPT -- navigation during outage is either (a) handled by error boundary
or (b) a bug. Either way, the test should not swallow it.

### AR2-Q4: Is `cleanupMocks` variable shared across tests correctly?
**Challenge**: The `let cleanupMocks` is at describe scope. In parallel test mode,
could tests clobber each other?
**Analysis**: Playwright runs tests within a `test.describe` block sequentially by
default. The `beforeEach`/`afterEach` lifecycle ensures `cleanupMocks` is set before
and cleared after each test. No parallelism issue within the describe block.
**Verdict**: ACCEPT.
