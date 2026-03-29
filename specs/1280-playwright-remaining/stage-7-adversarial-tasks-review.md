# Stage 7: Adversarial Tasks Review — 1280-playwright-remaining

## Review Methodology

Adversarial review of tasks.md against:
1. Plan completeness (all plan items have corresponding tasks?)
2. Implementation accuracy (do the code snippets match actual file contents?)
3. Edge cases in task execution
4. Missing verification steps

## Findings

### Finding 1: Task 1.6 — InlineError Button Doesn't Have a RefreshCw Inside (MEDIUM)

**Issue**: Task 1.6 says to add `aria-hidden="true"` to RefreshCw icon on "line 158" of
InlineError. Looking at the actual code:

```tsx
{onRetry && (
  <Button
    variant="ghost"
    size="sm"
    onClick={onRetry}
    className="text-red-500 hover:text-red-600 hover:bg-red-500/10"
  >
    <RefreshCw className="w-4 h-4" />
  </Button>
)}
```

The RefreshCw IS inside the Button, but this button has NO text label — it's icon-only.
Adding `aria-hidden="true"` to the icon would make the button completely invisible to
screen readers. This is WRONG. For icon-only buttons, the icon should NOT be hidden.
Instead, the button needs an `aria-label`.

**Resolution**: For the InlineError retry button:
- Do NOT add `aria-hidden="true"` to the RefreshCw icon
- Add `aria-label="Retry"` to the Button itself
- The icon provides the only visual indicator of the button's purpose

For the InlineError AlertTriangle:
- DO add `aria-hidden="true"` — it's decorative (the error message text conveys the meaning)

**Action**: Fix Task 1.6 to use `aria-label="Retry"` on the button instead of `aria-hidden`
on the icon.

### Finding 2: Task 4.4 — test.fixme() Syntax (LOW)

**Issue**: The task proposes `test.fixme('title')` which is a valid Playwright API. However,
looking at the existing test structure, the test has a callback with real test logic inside.
Changing from `test(...)` to `test.fixme(...)` keeps the callback but marks it as fixme.

The simpler approach is to just add `test.fixme()` call inside the describe block:

```typescript
// Option A: Replace test() with test.fixme()
test.fixme('SSE reconnection...', async ({ page }) => { ... });

// Option B: Keep test() and add skip annotation
test('SSE reconnection...', async ({ page }) => {
  test.fixme();
  // ... rest of test
});
```

Option A is cleaner. The task uses Option A which is correct.

Actually, looking at Playwright docs more carefully, `test.fixme('title')` without a callback
just creates a placeholder. `test.fixme('title', async ({ page }) => { ... })` keeps the code
but skips it. Either works, but we should keep the test code for future reference.

**Action**: Use `test.fixme('SSE reconnection issues new fetch after connection drop', async ({ page }) => { ... })` — keep the callback code intact.

### Finding 3: Task 3.2 — Comment Placement (TRIVIAL)

**Issue**: The task shows adding a comment `// Ensure auth succeeds before any API mocks (must be before goto)` but the existing code already has a comment about Feature 1276. The new comment should fit the existing style.

**Action**: Adjust comment to match existing style. Minor.

### Finding 4: Missing Verification Task (MEDIUM)

**Issue**: No task for local verification before pushing. The plan mentions risk mitigation
("add console logging in the test beforeEach") but doesn't include a verification task.

**Resolution**: Verification will happen in CI (the entire purpose of the feature). Local
verification is optional because:
- The a11y fixes are straightforward (aria attributes)
- The auth mock shape matches the type definition exactly
- The test.fixme() is syntactically simple

However, we should verify the TypeScript compiles:
```bash
cd frontend && npx tsc --noEmit
```

**Action**: Add a verification sub-task to check TypeScript compilation.

### Finding 5: Task 4.2 — Cross-Browser beforeEach May Need Additional Wait (LOW)

**Issue**: The current cross-browser `beforeEach` has `await page.waitForTimeout(2000)`. With
`mockAuthSession` added, the auth happens instantly (mock responds immediately). The 2s wait
was presumably for the page to stabilize. With mock auth, stabilization should be faster, but
reducing the timeout could introduce flakiness.

**Resolution**: Keep the 2s wait. It's a safety margin. Removing it would be an unnecessary
optimization that risks flakiness.

**Action**: No change needed. The 2000ms wait is already in the existing code.

### Finding 6: Task 2.1 — Placement in File (LOW)

**Issue**: Task says "after the existing `mockTickerDataApis` function". But the current file
structure has the function at lines 137-170, ending with a cleanup return. The new function
should be placed after the closing brace of `mockTickerDataApis` and its return type.

**Action**: Place `mockAuthSession` after the `mockTickerDataApis` function (after line 170).

### Finding 7: Task 4 — blockAllApi Override Behavior (MEDIUM)

**Issue**: In the "cached data persists" test (cross-browser.spec.ts:35), the flow is:
1. `mockAuthSession(page)` — beforeEach registers `**/api/v2/auth/anonymous` -> 200
2. `page.goto('/')` — session init fires, auth mock responds with 200
3. `mockTickerDataApis(page)` — registers search, OHLC, sentiment mocks
4. Search + select AAPL
5. `blockAllApi(page, 503)` — registers `**/api/**` -> 503

Step 5 uses `**/api/**` which is broader than the data mocks. Playwright uses LIFO routing,
so `**/api/**` (registered last) takes priority over `**/api/v2/tickers/search**` (registered
earlier). This is correct — after step 5, ALL API calls return 503.

But what about the auth mock? It was registered first (step 1). After `blockAllApi`, the auth
mock is still registered but overridden by `**/api/**`. If React Query tries to refetch
(background refetch), the auth endpoint returns 503. But this is fine because the token is
already in memory.

**Action**: No change needed. Behavior is correct.

## Summary

| # | Finding | Severity | Resolution |
|---|---------|----------|------------|
| 1 | InlineError icon-only button | MEDIUM | Use aria-label instead of aria-hidden |
| 2 | test.fixme syntax | LOW | Keep callback code intact |
| 3 | Comment placement | TRIVIAL | Match existing style |
| 4 | Missing verification | MEDIUM | Add TypeScript check step |
| 5 | beforeEach wait time | LOW | Keep existing 2000ms |
| 6 | Function placement | LOW | After line 170 |
| 7 | Route override behavior | MEDIUM | Verified correct |

## Tasks Amendments

1. Task 1.6: Change InlineError retry button fix from `aria-hidden` on icon to
   `aria-label="Retry"` on button
2. Task 4.4: Keep test callback code in `test.fixme()` call
3. Add verification step: `cd frontend && npx tsc --noEmit` after all changes
