# Feature 1330: Implementation Plan (Second Pass)

## Overview

Delete 2 SSE test files (8 tests), fix 3 remaining files (up to 5 tests). Zero
production code changes expected (unless axe finds real a11y violations).

**Key finding from Stage 4**: The cached-data test failure is NOT an auth timing race.
It is a mock response format mismatch. The `mockTickerDataApis()` auth mock returns
`access_token` but the API contract expects `token`. This causes `hasAccessToken` to
stay false, so chart queries never fire.

## Phase 1: Delete SSE E2E Tests (US1)

### Step 1.1: Delete chaos-sse-recovery.spec.ts
- Delete `frontend/tests/e2e/chaos-sse-recovery.spec.ts` (5 tests: T036-T040)
- All 5 tests suffer from SSE prerequisite issue (no auth + no config = no SSE connection)
- T038-T039 are vacuous (pass trivially when SSE never connects)
- T040 duplicates health banner testing from other specs

### Step 1.2: Delete chaos-sse-lifecycle.spec.ts
- Delete `frontend/tests/e2e/chaos-sse-lifecycle.spec.ts` (3 tests: T032-T034)
- All 3 tests suffer from SSE prerequisite issue

### Step 1.3: Document deletion rationale
- Already documented in this spec and `spec.md`

## Phase 2: Fix Cached Data Tests — Mock Response Format (US2)

### Root Cause (confirmed in Stage 4)

`mockTickerDataApis()` in `frontend/tests/e2e/helpers/mock-api-data.ts` returns:

```json
{
  "access_token": "mock-test-token",
  "token_type": "bearer",
  "auth_type": "anonymous",
  "user_id": "anon-test-user",
  "session_expires_in_seconds": 3600
}
```

The actual `AnonymousSessionResponse` contract (`frontend/src/types/auth.ts:48-55`) is:

```json
{
  "user_id": "string",
  "token": "string",
  "auth_type": "anonymous",
  "created_at": "string",
  "session_expires_at": "string",
  "storage_hint": "localStorage"
}
```

The `mapAnonymousSession()` function reads `response.token`. The mock returns
`access_token` but NOT `token`. So `data.token` is `undefined`, `setTokens({ accessToken: undefined })`
leaves `hasAccessToken` false, and `useChartData` queries never fire.

### Step 2.1: Fix auth mock response in mockTickerDataApis()

**File**: `frontend/tests/e2e/helpers/mock-api-data.ts`

Replace the auth mock route handler (lines 182-194) with the correct response shape:

```typescript
await page.route('**/api/v2/auth/anonymous', async (route) => {
  await route.fulfill({
    status: 201,
    contentType: 'application/json',
    body: JSON.stringify({
      user_id: 'anon-test-user',
      token: 'mock-test-token',
      auth_type: 'anonymous',
      created_at: new Date().toISOString(),
      session_expires_at: new Date(Date.now() + 3600_000).toISOString(),
      storage_hint: 'localStorage',
    }),
  });
});
```

### Step 2.2: Validate chart renders candles

After fix, the `beforeEach` assertion should pass:
```typescript
await expect(chartContainer).toHaveAttribute(
  'aria-label',
  /[1-9]\d* price candles/,
  { timeout: 5000 },
);
```

### Cross-feature note

Feature 1329 (chart-auth-mock) plans to create `mockAnonymousAuth()` with the SAME wrong
response format. When 1329 is implemented, it must use the correct `AnonymousSessionResponse`
contract (with `token`, not `access_token`).

## Phase 3: Fix A11y Tests (US3)

### Step 3.1: Run a11y tests locally, capture violations

Run T025 and T026 individually. Capture full axe output.

**Prerequisite for T025**: `triggerHealthBanner()` must succeed. This requires the search
input to be visible and API calls to return 503. This should work with the local dev
server — the test blocks `**/api/**` before searching.

**Prerequisite for T026**: `addInitScript` + `goto('/')` must trigger ErrorBoundary.
This requires `NODE_ENV !== 'production'` which is true for the dev server.

### Step 3.2: Triage each violation

For each axe violation:
1. Check if it's a real WCAG failure (missing ARIA, broken semantics)
2. Check if it's a color contrast finding on intentionally styled warning/error UI
3. For real failures: fix the component
4. For intentional design choices: add targeted `.disableRules()` with documented justification

### Step 3.3: Apply fixes

If the health banner's amber-900/amber-100 color combination fails contrast:
- The banner uses `bg-amber-900/90 text-amber-100` — this is a 7.2:1 contrast ratio
  (passes AA and AAA). If axe flags it, it may be due to the `/90` opacity modifier
  reducing effective contrast against the page background.
- Fix: Remove opacity modifier or adjust colors.

If the error boundary has violations:
- Check that all buttons have accessible names (they should — text content provides it)
- Check for any missing landmark roles

## Phase 4: Fix Error Boundary Test (US4)

### Narrowing the failure

chaos-error-boundary.spec.ts has 3 tests (T022, T023, T024). The problem statement says
1 failure. Based on analysis:

- **T022** (fallback renders): Simple test, uses addInitScript + goto. Should work.
- **T023** (during degradation): triggerHealthBanner leaves API block active, then
  addInitScript + goto triggers ErrorBoundary. The API block from triggerHealthBanner
  persists. This could cause timeout if the page depends on API calls to render.
  However, ErrorBoundary catches the ErrorTrigger throw and renders the fallback
  regardless of API state. Should work.
- **T024** (keyboard navigation): Tabs through buttons and checks activeElement.
  This is the most fragile test — it depends on DOM focus order, icon rendering timing,
  and textContent of the focused element. If the Button component renders an icon + text,
  `textContent?.trim()` may include icon alt text or be empty if icons load async.

**Most likely failure: T024** — keyboard focus assertion depends on exact textContent
which may vary based on icon rendering.

### Step 4.1: Run T022, T023, T024 individually to identify exact failure

```bash
npx playwright test chaos-error-boundary.spec.ts --project="Desktop Chrome" -g "T022"
npx playwright test chaos-error-boundary.spec.ts --project="Desktop Chrome" -g "T023"
npx playwright test chaos-error-boundary.spec.ts --project="Desktop Chrome" -g "T024"
```

### Step 4.2: Fix based on findings

If T024 fails: The `textContent?.trim()` approach is fragile. Replace with Playwright's
`toHaveFocus()` or `getByRole('button').first().focus()` pattern used in
chaos-accessibility.spec.ts T027.

If T023 fails: Clean up the API block from triggerHealthBanner before the second goto:
```typescript
await page.unroute('**/api/**');
```

## Verification

### Local validation (per-phase)
```bash
cd frontend

# Phase 1: Verify deleted files don't exist
test ! -f tests/e2e/chaos-sse-recovery.spec.ts && echo "PASS" || echo "FAIL"
test ! -f tests/e2e/chaos-sse-lifecycle.spec.ts && echo "PASS" || echo "FAIL"

# Phase 2: Cached data tests
npx playwright test chaos-cached-data.spec.ts --project="Desktop Chrome" --repeat-each=5

# Phase 3: A11y tests
npx playwright test chaos-accessibility.spec.ts --project="Desktop Chrome" --repeat-each=5

# Phase 4: Error boundary tests
npx playwright test chaos-error-boundary.spec.ts --project="Desktop Chrome" --repeat-each=5
```

### Full chaos suite validation
```bash
npx playwright test chaos- --project="Desktop Chrome"
```

### CI validation
Push and verify all chaos tests pass in the PR pipeline.
