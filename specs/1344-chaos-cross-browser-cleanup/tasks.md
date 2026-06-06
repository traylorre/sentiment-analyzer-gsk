# Tasks -- Feature 1344: Clean Up chaos-cross-browser.spec.ts

## Task Dependencies

```
T1 (delete SSE) ──> T5 (verify)
T2 (update JSDoc) ──> T5
T3 (fix beforeEach) ──> T5
T4 (fix cached data) ──> T5
```

All of T1-T4 are independent and can be applied in any order.

## Tasks

### T1: Delete SSE Reconnection Dead Code
**File**: `frontend/tests/e2e/chaos-cross-browser.spec.ts`
**Action**: Delete lines 68-104 (the entire `test.fixme()` block including FIXME comments)
**Details**:
- Remove the `// T043: SSE reconnection on WebKit` comment (line 68)
- Remove the `// FIXME(1280): ...` comment block (lines 69-73)
- Remove the entire `test.fixme('SSE reconnection...')` function (lines 74-104)
- Verify no imports become unused after deletion (all current imports are used by the
  remaining two tests)

**Acceptance**: File has exactly 2 `test(...)` calls. No `test.fixme` remains. No unused
imports. TypeScript compiles.

---

### T2: Update File-Level JSDoc and Test Comments
**File**: `frontend/tests/e2e/chaos-cross-browser.spec.ts`
**Action**: Rewrite the file-level JSDoc (lines 10-19) and update test-level comments
**Details**:

1. Replace file-level JSDoc with version that explicitly states these are cross-browser
   smoke tests duplicating primary tests intentionally. Include the Playwright project
   rationale (Mobile Chrome + Mobile Safari). Keep the WebKit caveat. Add Feature 1344
   reference.

2. Change banner test comment from:
   `// T042: Banner lifecycle works across browsers`
   to:
   `// T042: Cross-browser smoke test (primary: chaos-degradation.spec.ts T007)`

3. Change cached data test comment from:
   `// T042: Cached data persists across browsers`
   to:
   `// T042: Cross-browser smoke test (primary: chaos-cached-data.spec.ts T013)`

**Acceptance**: File-level JSDoc mentions "cross-browser smoke tests" and "duplication is
intentional." Both tests reference their primary test file and ID.

---

### T3: Replace beforeEach waitForTimeout with DOM-Ready Wait
**File**: `frontend/tests/e2e/chaos-cross-browser.spec.ts`
**Action**: Replace blind wait in `beforeEach` (line 23)
**Details**:
- Remove `await page.waitForTimeout(2000);`
- Add: wait for search input to be visible as DOM-ready signal
  ```typescript
  const searchInput = page.getByPlaceholder(/search tickers/i);
  await expect(searchInput).toBeVisible({ timeout: 5000 });
  ```
- `expect` is already imported from `@playwright/test` on line 2

**Acceptance**: No `waitForTimeout(2000)` in `beforeEach`. The `beforeEach` uses a
DOM-based assertion instead. Both tests still pass.

---

### T4: Fix Cached Data Test Content Comparison
**File**: `frontend/tests/e2e/chaos-cross-browser.spec.ts`
**Action**: Add content comparison after chaos injection in cached data test
**Details**:

1. Add a comment above the existing `waitForTimeout(500)` documenting why it's kept:
   ```typescript
   // Brief settle for in-flight React Query refetch requests to hit the route block.
   // Cannot use response-based wait here because requests may already be in-flight
   // before blockAllApi() installs the route handlers.
   ```

2. After the existing `expect(textDuring!.length).toBeGreaterThan(10)` line, add:
   ```typescript
   // Content comparison: verify cached data persists (not replaced by error page).
   // Uses substring check rather than exact match to tolerate dynamic timestamps.
   expect(textDuring).toContain('AAPL');
   ```

**Acceptance**: Cached data test now asserts `textDuring` contains 'AAPL'. A hypothetical
bug that replaces dashboard content with an error page would FAIL this assertion.

---

### T5: Verification
**Action**: Read-only verification (no file changes)
**Details**:
1. Count `test(` calls in file -- must be exactly 2
2. Count `test.fixme(` calls -- must be 0
3. Count `waitForTimeout` calls -- must be at most 1 (the 500ms settle), and it must
   have a comment explaining why
4. Verify `import` lines have no unused imports
5. Verify file-level JSDoc contains "cross-browser smoke test" or equivalent
6. Run `npx playwright test chaos-cross-browser --project=chromium` if local server available
7. Verify TypeScript compiles: `cd frontend && npx tsc --noEmit`

**Acceptance**: All 7 checks pass. Zero regressions.

---

## Appendix: Adversarial Review #3

### READY FOR IMPLEMENTATION gate

| Criterion | Status | Evidence |
|-----------|--------|----------|
| All FRs mapped to tasks | PASS | FR-001->T1, FR-002->T2, FR-003->T3, FR-004->T4, FR-005->T4 |
| All NFRs addressed | PASS | NFR-001->T1+T5, NFR-002->T3+T4, NFR-003->T1 |
| Success criteria testable | PASS | All 8 criteria map to T5 verification steps |
| No ambiguous acceptance criteria | PASS | Every task has concrete, measurable acceptance |
| Risk mitigations documented | PASS | Plan appendix covers all 3 changes with risk |
| Dependencies explicit | PASS | T1-T4 independent, T5 depends on all |
| File list complete | PASS | Single file: chaos-cross-browser.spec.ts |
| No scope creep | PASS | Does not modify primary test files or helpers |

**VERDICT: READY FOR IMPLEMENTATION**
