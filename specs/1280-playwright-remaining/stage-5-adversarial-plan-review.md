# Stage 5: Adversarial Plan Review — 1280-playwright-remaining

## Review Methodology

Adversarial review of plan.md against:
1. Spec completeness (all requirements addressed?)
2. Code reality (do proposed changes match actual code structure?)
3. Edge cases in implementation
4. Missing steps

## Findings

### Finding 1: mockAuthSession Cleanup Missing (LOW)

**Issue**: `mockTickerDataApis()` returns a cleanup function that removes routes. The proposed
`mockAuthSession()` does NOT return a cleanup function.

**Impact**: If a test needs to simulate auth failure AFTER initial success (e.g., token expiry),
there's no way to remove the auth mock.

**Resolution**: Accept for now. No test in scope requires auth cleanup. The function signature
can be extended later if needed. All Playwright route mocks are automatically cleaned up
when the page context is destroyed between tests.

### Finding 2: Cross-Browser beforeEach Does Not Mock Auth (MEDIUM)

**Issue**: The plan says to add `mockAuthSession(page)` to the "cached data persists" test in
`chaos-cross-browser.spec.ts`. But this file has a shared `beforeEach` that navigates to `/`
with a 2s wait. The "cached data persists" test at line 35 then calls `mockTickerDataApis(page)`
inside the test body.

The `beforeEach` navigates to `/` which triggers session init. Without `mockAuthSession`, the
session may fail. Adding `mockAuthSession` inside the test body (after `goto`) won't help because
session init already fired.

**Resolution**: Two options:
1. Add `mockAuthSession(page)` to the cross-browser `beforeEach` (affects all 3 tests)
2. Add `mockAuthSession(page)` in the test body before calling `mockTickerDataApis`

Option 1 is cleaner but may affect the "health banner" test which relies on real API failures.
Actually, `mockAuthSession` only mocks `POST /api/v2/auth/anonymous` — it doesn't affect
`GET /api/v2/tickers/search` or other endpoints. The health banner test triggers failures by
calling `triggerHealthBanner(page)` which routes `**/api/**` to 503. This broader pattern
overrides the auth mock (Playwright LIFO routing), so the auth mock won't interfere.

Wait — but the auth mock is set up BEFORE the `**/api/**` block. Playwright uses LIFO (last
registered route takes priority). So when `triggerHealthBanner` registers `**/api/**` -> 503,
it overrides `**/api/v2/auth/anonymous` -> 200. That's fine for the banner test.

But there's a subtlety: the `beforeEach` runs BEFORE the test body. If `mockAuthSession` is
in `beforeEach`, it's registered first. Then `page.goto('/')` fires session init which hits
the auth mock (200). Then the test can do whatever it wants. This is correct.

**Action**: Add `mockAuthSession(page)` to the cross-browser `beforeEach`. This is safe because:
- It only mocks one specific endpoint
- Other tests that need API failures use broader patterns that override it
- Auth is needed for all cross-browser tests that load data

Actually wait — the "health banner appears after 3 failures" test at line 27 does NOT need
auth. It just needs the page to load and then triggers failures. Adding auth mock to beforeEach
won't hurt because the auth endpoint is only called once during session init. The broader
`**/api/**` block from `triggerHealthBanner` doesn't match `POST /api/v2/auth/anonymous`
because session init already completed.

**Action**: Add `mockAuthSession(page)` to cross-browser `beforeEach`, BEFORE `page.goto('/')`.

### Finding 3: Plan Doesn't Address InlineError Component (TRIVIAL)

**Issue**: The `error-boundary.tsx` file also exports `InlineError` component. It has a retry
button without `type="button"` and an `AlertTriangle` icon without `aria-hidden`.

**Impact**: None for this feature. The a11y tests only test `ErrorFallback`, not `InlineError`.
However, it's good practice to fix both while we're in the file.

**Action**: Fix `InlineError` as well (add `aria-hidden` to icon, add `type="button"` to
retry button). Low effort, zero risk.

### Finding 4: The cross-browser beforeEach Navigates Before Auth Mock (CRITICAL)

**Issue**: Re-reading `chaos-cross-browser.spec.ts` lines 21-24:

```typescript
test.beforeEach(async ({ page }) => {
    await page.goto('/');
    await page.waitForTimeout(2000);
  });
```

The `beforeEach` calls `page.goto('/')` BEFORE any route mocking. The session init happens
during `page.goto('/')`. By the time the test body calls `mockAuthSession(page)`, the auth
request has already been made (and potentially failed).

If we add `mockAuthSession(page)` to the `beforeEach` BEFORE `page.goto('/')`, it works:

```typescript
test.beforeEach(async ({ page }) => {
    await mockAuthSession(page);  // Must be before goto
    await page.goto('/');
    await page.waitForTimeout(2000);
  });
```

**Action**: The plan already says "BEFORE page.goto()" but the implementation must ensure
the mock is registered before navigation. Verified this is doable by adding to beforeEach.

### Finding 5: SSE test.fixme() Preserves Test Count (LOW)

**Issue**: `test.fixme()` marks the test as "known failing" but still counts in the test suite.
Playwright reports it as "fixme" (not "skipped", not "failed"). This is correct behavior and
doesn't affect CI pass/fail.

However, the 1279 results show the test was retried 3 times (tests 18-20). With `test.fixme()`,
it won't be retried. This is correct — no wasted CI time.

**Action**: Accept. `test.fixme()` is the right choice.

### Finding 6: Need to Update mockTickerDataApis Cleanup (TRIVIAL)

**Issue**: `mockTickerDataApis` returns a cleanup function that unroutes the 3 data endpoints.
If `mockAuthSession` is used alongside it, the auth route isn't cleaned up. But as noted in
Finding 1, this is fine because Playwright cleans up routes between tests.

**Action**: Accept. No change needed.

## Summary

| # | Finding | Severity | Resolution |
|---|---------|----------|------------|
| 1 | Auth mock no cleanup | LOW | Accept — auto-cleanup between tests |
| 2 | Cross-browser beforeEach placement | MEDIUM | Add mockAuthSession to beforeEach before goto |
| 3 | InlineError a11y | TRIVIAL | Fix while in the file |
| 4 | beforeEach ordering | CRITICAL | Ensure mock before goto (plan is correct, verify implementation) |
| 5 | test.fixme behavior | LOW | Accept |
| 6 | Cleanup coverage | TRIVIAL | Accept |

## Plan Amendments

1. Add `mockAuthSession(page)` to cross-browser `beforeEach` (before `page.goto`)
2. Also fix `InlineError` component a11y in `error-boundary.tsx`
3. Emphasize in tasks: route mock MUST be registered before `page.goto('/')`
