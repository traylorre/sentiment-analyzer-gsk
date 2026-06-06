# Tasks -- Feature 1341: Fix Green Dashboard Syndrome in chaos-cached-data.spec.ts

## Task Dependencies

```
T1 (cleanup infra) ──> T2 (T013 fixes)
                   ──> T3 (T014 fixes)
T1-T3 ─────────────> T4 (verification)
```

## Tasks

### T1: Add mock route cleanup infrastructure
**File**: `frontend/tests/e2e/chaos-cached-data.spec.ts`
**Action**: Add describe-level variable and afterEach hook
**Details**:

1. Add `let cleanupMocks: (() => Promise<void>) | undefined;` at the top of the
   `test.describe` block (after line 13).

2. Modify `beforeEach` to capture the cleanup function:
   ```typescript
   // BEFORE:
   await mockTickerDataApis(page);

   // AFTER:
   cleanupMocks = await mockTickerDataApis(page);
   ```

3. Add `afterEach` block after `beforeEach`:
   ```typescript
   test.afterEach(async () => {
     if (cleanupMocks) {
       await cleanupMocks();
       cleanupMocks = undefined;
     }
   });
   ```

**Acceptance**: `mockTickerDataApis` cleanup function is stored and called after each test.

---

### T2: Fix T013 -- content comparison and chart persistence
**File**: `frontend/tests/e2e/chaos-cached-data.spec.ts`
**Action**: Modify T013 test body (lines 39-66)
**Details**:

1. After `expect(textDuring!.length).toBeGreaterThan(10);` (line 65), add:
   ```typescript
   // Verify content identity -- same data, not just "some content"
   const fragment = textBefore!.substring(0, 20);
   expect(textDuring).toContain(fragment);
   ```

2. After the content comparison, add chart persistence check:
   ```typescript
   // Verify chart persists through outage
   const chartContainer = page.locator(
     '[role="img"][aria-label*="Price and sentiment chart"]',
   );
   await expect(chartContainer).toBeVisible({ timeout: 3000 });
   ```

**Acceptance**: Test fails if (a) content replaced during outage, or (b) chart vanishes.

---

### T3: Fix T014 -- content comparison and strict click
**File**: `frontend/tests/e2e/chaos-cached-data.spec.ts`
**Action**: Modify T014 test body (lines 69-97)
**Details**:

1. After `expect(textDuring!.length).toBeGreaterThan(10);` (line 84), add:
   ```typescript
   const fragment = textBefore!.substring(0, 20);
   expect(textDuring).toContain(fragment);
   ```

2. Replace lines 91-96 (click with catch):
   ```typescript
   // BEFORE:
   if (clickableCount > 0) {
     // Click the first interactive element -- should not throw
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

**Acceptance**: Test fails if interactive element vanishes or click throws. No silent error swallowing.

---

### T4: Verification
**Action**: Run test suite
**Details**:
```bash
cd frontend && npx playwright test chaos-cached-data.spec.ts --reporter=list
```

Verify:
- Both tests pass
- No `.catch()` remains on assertions
- `cleanupMocks` is called in afterEach
- Chart container checked after blockAllApi in T013
- Content fragment comparison present in both tests

**Acceptance**: All tests pass. Grep confirms no suppressed assertions remain.

---

## Appendix A: Adversarial Review #3 (Tasks)

### AR3-Q1: Task ordering -- can T2 and T3 run in parallel?
**Analysis**: T2 and T3 modify different tests within the same file. They're independent
of each other but both depend on T1 (cleanup infrastructure). Implementation will apply
all edits sequentially in a single pass.
**Verdict**: ACCEPT -- parallel within implementation, sequential for file edits.

### AR3-Q2: T2 chart selector -- is it identical to beforeEach?
**Verification**: beforeEach (line 28-29):
```typescript
const chartContainer = page.locator(
  '[role="img"][aria-label*="Price and sentiment chart"]',
);
```
T2 uses the exact same selector. Consistent.
**Verdict**: ACCEPT.

### AR3-Q3: T3 click without catch -- what if the first clickable element is a dropdown toggle?
**Analysis**: If clicking a dropdown toggle opens a dropdown, that's expected interactive
behavior. The test doesn't assert what happens after the click -- only that the click
completes without error. A dropdown opening is fine. A crash is not.
**Verdict**: ACCEPT.

### AR3-Q4: Is the task set complete?
**Audit**:
- Mock cleanup: T1 (afterEach -- fixed)
- T013 content: T2 (fragment comparison -- fixed)
- T013 chart: T2 (chart visibility -- fixed)
- T014 content: T3 (fragment comparison -- fixed)
- T014 click: T3 (strict assertion -- fixed)
- Verification: T4

All requirements mapped. No gaps.
**Verdict**: COMPLETE.

---

## READY FOR IMPLEMENTATION

All adversarial reviews passed. No blocking issues. Feature depends on 1339 (complete).
Single-file change with 3 edit tasks + verification.
