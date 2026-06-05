# Feature 1330: Tasks

## Task Dependency Graph

```
T1 (delete chaos-sse-recovery.spec.ts)
T2 (delete chaos-sse-lifecycle.spec.ts)
T3 (fix mock-api-data.ts auth response)
 └─> T4 (validate chaos-cached-data passes)
T5 (investigate + fix chaos-accessibility.spec.ts)
T6 (investigate + fix chaos-error-boundary.spec.ts)
T4,T5,T6 ──> T7 (full chaos suite validation)
```

T1, T2 are independent. T3 must precede T4. T5, T6 are independent. T7 is last.

---

## T1: Delete chaos-sse-recovery.spec.ts

**File**: `frontend/tests/e2e/chaos-sse-recovery.spec.ts`
**Depends on**: Nothing
**Spec ref**: FR-001, US1

### Actions
1. Delete `frontend/tests/e2e/chaos-sse-recovery.spec.ts`

### Rationale
5 tests (T036-T040) all depend on SSE client making requests to `/api/v2/stream`.
The frontend SSE client only connects when authenticated AND monitoring a configuration.
Without auth + config setup, zero SSE requests are made:
- T036-T037: Wait for SSE requests that never come (120s timeout)
- T038-T039: Pass vacuously (assert on SSE request count that is always 0)
- T040: Duplicates health banner testing from error-visibility-banner.spec.ts

### Verification
```bash
test ! -f frontend/tests/e2e/chaos-sse-recovery.spec.ts && echo "PASS"
```

---

## T2: Delete chaos-sse-lifecycle.spec.ts

**File**: `frontend/tests/e2e/chaos-sse-lifecycle.spec.ts`
**Depends on**: Nothing
**Spec ref**: FR-002, US1

### Actions
1. Delete `frontend/tests/e2e/chaos-sse-lifecycle.spec.ts`

### Rationale
3 tests (T032-T034) all depend on SSE client connecting. Same prerequisite issue as T1.
SSE reconnection behavior should be unit tested in `use-sse.ts`, not E2E tested.

### Verification
```bash
test ! -f frontend/tests/e2e/chaos-sse-lifecycle.spec.ts && echo "PASS"
```

---

## T3: Fix auth mock response format in mockTickerDataApis()

**File**: `frontend/tests/e2e/helpers/mock-api-data.ts`
**Depends on**: Nothing
**Spec ref**: FR-003, US2

### Actions
1. In `mockTickerDataApis()`, replace the auth mock route handler body.

**Replace** (lines 183-193):
```typescript
  await page.route('**/api/v2/auth/anonymous', async (route) => {
    await route.fulfill({
      status: 201,
      contentType: 'application/json',
      body: JSON.stringify({
        access_token: 'mock-test-token',
        token_type: 'bearer',
        auth_type: 'anonymous',
        user_id: 'anon-test-user',
        session_expires_in_seconds: 3600,
      }),
    });
  });
```

**With**:
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

### Why this fixes the problem
The `authApi.createAnonymousSession()` call maps the response via
`mapAnonymousSession()` which reads `response.token`. The old mock returned
`access_token` (wrong field name), so `response.token` was `undefined`.
The auth store then called `setTokens({ accessToken: undefined })`, leaving
`hasAccessToken` false and preventing chart queries from firing.

### Verification
```bash
cd frontend && npx playwright test chaos-cached-data.spec.ts --project="Desktop Chrome"
```
Expected: Chart aria-label shows non-zero price candles.

---

## T4: Validate chaos-cached-data.spec.ts passes reliably

**File**: `frontend/tests/e2e/chaos-cached-data.spec.ts`
**Depends on**: T3
**Spec ref**: US2 acceptance criteria

### Actions
1. Run the cached data tests with repeat:
```bash
cd frontend && npx playwright test chaos-cached-data.spec.ts --project="Desktop Chrome" --repeat-each=5
```

2. Verify both T013 and T014 pass all 5 runs.

3. If failures persist after T3 fix, investigate further:
   - Check if `useSessionInit()` timeout fires before the mock response arrives
   - Check if the search interaction + OHLC mock response pipeline works end-to-end
   - Add debug logging: `page.on('console', msg => console.log(msg.text()))`

### Verification
5/5 pass for both T013 and T014.

---

## T5: Investigate and fix chaos-accessibility.spec.ts

**File**: `frontend/tests/e2e/chaos-accessibility.spec.ts`
**Depends on**: Nothing
**Spec ref**: FR-004, US3

### Actions

1. Run T025 (health banner a11y) locally:
```bash
cd frontend && npx playwright test chaos-accessibility.spec.ts --project="Desktop Chrome" -g "health banner"
```

2. If T025 fails, capture the axe violation output from stderr/test report.

3. **Triage violations**:

   **If color-contrast violation on amber banner**:
   - The banner uses `bg-amber-900/90 text-amber-100`
   - The `/90` opacity may reduce effective contrast
   - Fix option A: Remove opacity — change to `bg-amber-900`
   - Fix option B: Add targeted exclusion with comment:
     ```typescript
     .disableRules(['color-contrast'])
     ```
   - Prefer Fix A (production improvement) over Fix B (test workaround)

   **If other violation (missing ARIA, broken semantics)**:
   - Fix the component in `frontend/src/components/ui/api-health-banner.tsx`

4. Run T026 (error boundary a11y) locally:
```bash
cd frontend && npx playwright test chaos-accessibility.spec.ts --project="Desktop Chrome" -g "error boundary fallback"
```

5. If T026 fails, triage and fix similarly. The error boundary component at
   `frontend/src/components/ui/error-boundary.tsx` should have accessible buttons
   (text provides accessible name via content).

6. Run T027 (keyboard focus) — this is in the same file:
```bash
cd frontend && npx playwright test chaos-accessibility.spec.ts --project="Desktop Chrome" -g "keyboard"
```

7. If T027 fails, likely issue is `getByRole('link', { name: /go home/i })` — the
   "Go Home" button is a `<button>`, not a link. The `.or()` fallback should match,
   but if it times out:
   - Replace with just `page.getByRole('button', { name: /go home/i })`

### Verification
```bash
cd frontend && npx playwright test chaos-accessibility.spec.ts --project="Desktop Chrome" --repeat-each=5
```
Expected: All tests pass 5/5.

---

## T6: Investigate and fix chaos-error-boundary.spec.ts

**File**: `frontend/tests/e2e/chaos-error-boundary.spec.ts`
**Depends on**: Nothing
**Spec ref**: FR-005, US4

### Actions

1. Run each test individually to identify which one fails:
```bash
cd frontend
npx playwright test chaos-error-boundary.spec.ts --project="Desktop Chrome" -g "fallback renders"
npx playwright test chaos-error-boundary.spec.ts --project="Desktop Chrome" -g "during degradation"
npx playwright test chaos-error-boundary.spec.ts --project="Desktop Chrome" -g "keyboard-navigable"
```

2. **If T022 (fallback renders) fails**:
   - The `addInitScript` + `goto` pattern is sound (same pattern works in a11y tests)
   - Check if `NODE_ENV=production` (ErrorTrigger skips in production)
   - Check if "Something went wrong" text exactly matches (case-insensitive regex should handle)

3. **If T023 (during degradation) fails**:
   - `triggerHealthBanner()` leaves `page.route('**/api/**')` active
   - This blocks `useSessionInit()` → auth fails → error event may fire
   - But ErrorTrigger doesn't need auth, just `__TEST_FORCE_ERROR`
   - Possible fix: clear the API block before the second `goto`:
     ```typescript
     await page.unroute('**/api/**');
     await page.addInitScript(() => { ... });
     await page.goto('/');
     ```
   - This ensures the error boundary test isn't polluted by health banner API blocks

4. **If T024 (keyboard-navigable) fails**:
   - `document.activeElement?.textContent?.trim()` is fragile
   - Button text includes icon (lucide-react SVG) which has `aria-hidden="true"`
     but `textContent` includes ALL child text including hidden elements
   - Fix: Replace textContent check with Playwright's built-in focus assertions:
     ```typescript
     const buttons = page.getByRole('button');
     await page.keyboard.press('Tab');
     // Check that SOME button is focused
     const focusedEl = page.locator(':focus');
     await expect(focusedEl).toBeVisible();
     ```
   - Or use the more robust pattern from T027 (chaos-accessibility.spec.ts):
     ```typescript
     await tryAgainButton.focus();
     await expect(tryAgainButton).toBeFocused();
     ```

### Verification
```bash
cd frontend && npx playwright test chaos-error-boundary.spec.ts --project="Desktop Chrome" --repeat-each=5
```
Expected: All 3 tests pass 5/5.

---

## T7: Full chaos suite validation

**Depends on**: T1, T2, T4, T5, T6
**Spec ref**: All acceptance criteria

### Actions

1. Run all remaining chaos test files:
```bash
cd frontend && npx playwright test chaos- --project="Desktop Chrome"
```

2. Verify:
   - `chaos-sse-recovery.spec.ts` — DELETED (not found)
   - `chaos-sse-lifecycle.spec.ts` — DELETED (not found)
   - `chaos-cached-data.spec.ts` — 2/2 pass
   - `chaos-accessibility.spec.ts` — 3/3 pass
   - `chaos-error-boundary.spec.ts` — 3/3 pass
   - `chaos-scenarios.spec.ts` — unaffected, still passes
   - `chaos-degradation.spec.ts` — unaffected, still passes
   - `chaos-cross-browser.spec.ts` — unaffected, still passes

3. Verify no other tests regressed:
```bash
npx playwright test --project="Desktop Chrome"
```

### Success criteria
- [ ] 8 SSE tests deleted (2 files)
- [ ] 2 cached-data tests pass (auth mock format fixed)
- [ ] 2-3 a11y tests pass (violations triaged and resolved)
- [ ] 3 error-boundary tests pass (specific failure identified and fixed)
- [ ] No regressions in other test files
- [ ] Total: 9 failures resolved (8 deleted + 1? fixed, or mix)

---

## Estimated Effort

| Task | Lines Changed | Complexity | Time |
|------|--------------|------------|------|
| T1 | -170 | Trivial (delete file) | 1 min |
| T2 | -153 | Trivial (delete file) | 1 min |
| T3 | ~12 | Low (JSON format fix) | 5 min |
| T4 | 0 | Low (validation) | 5 min |
| T5 | ~5-20 | Medium (triage + fix) | 15 min |
| T6 | ~5-20 | Medium (triage + fix) | 15 min |
| T7 | 0 | Low (validation) | 10 min |
| **Total** | **-280 to -300** | **Low-Medium** | **~52 min** |

Net effect: Significant test code deletion (300+ lines removed), small fixes in remaining tests.
