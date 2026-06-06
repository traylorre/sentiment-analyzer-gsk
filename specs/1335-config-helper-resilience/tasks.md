# Tasks: Config Helper Resilience

**Branch**: `1335-config-helper-resilience` | **Date**: 2026-04-05
**Spec**: [spec.md](./spec.md) | **Plan**: [plan.md](./plan.md)

---

## Task 1: Wrap CTA and Form Steps with Descriptive Errors

**FR**: FR-003, FR-005
**SC**: SC-004
**File**: `frontend/tests/e2e/helpers/clean-state.ts`

### Description

Wrap the existing CTA button click and name input fill steps in try/catch blocks that re-throw with descriptive error messages including the helper name and config name.

### Subtasks

- [ ] 1.1: Wrap CTA button visibility and click (lines 65-68) in try/catch -- error: `createTestConfig('${name}'): form open failed -- CTA button not visible after 5s`
- [ ] 1.2: Wrap name input visibility and fill (lines 71-73) in try/catch -- error: `createTestConfig('${name}'): name input not found (placeholder 'my watchlist')`

### Acceptance Criteria

- CTA failure produces error with helper name and config name
- Name input failure produces error with helper name and tried placeholder

---

## Task 2: Remove Silent Ticker Skip and Add Selection Guard

**FR**: FR-002, FR-003
**SC**: SC-002, SC-004
**AR**: AR-002
**File**: `frontend/tests/e2e/helpers/clean-state.ts`

### Description

Remove the `.catch(() => false)` on ticker input visibility check. Replace with explicit failure. After clicking the ticker option, verify it was selected (chip/badge visible or submit button enabled).

### Subtasks

- [ ] 2.1: Remove `.catch(() => false)` on `tickerInput.first().isVisible()` -- replace with `await expect(tickerInput.first()).toBeVisible({ timeout: 5000 })` wrapped in try/catch
- [ ] 2.2: After `option.click()`, verify ticker was added: check for a chip/tag with "AAPL" text OR check submit button is enabled within 3s
- [ ] 2.3: If ticker input not visible, throw: `createTestConfig('${name}'): ticker input not found (tried placeholders: 'search for a ticker', 'add ticker|search')`
- [ ] 2.4: If ticker option click didn't register, throw: `createTestConfig('${name}'): ticker AAPL selection failed -- option click did not register`

### Acceptance Criteria

- Ticker input invisibility throws immediately (not silently skipped)
- Ticker option click failure throws with descriptive message
- Submit button disabled after ticker step produces clear error

---

## Task 3: Replace waitForTimeout with networkidle (Timeout-Capped)

**FR**: FR-004
**SC**: SC-005
**AR**: AR-003
**File**: `frontend/tests/e2e/helpers/clean-state.ts`

### Description

Replace `await page.waitForTimeout(1000)` after submit click with `await page.waitForLoadState('networkidle')` wrapped in a 5-second timeout cap using `Promise.race`.

### Subtasks

- [ ] 3.1: Replace line 90 (`waitForTimeout(1000)`) with timeout-capped networkidle wait
- [ ] 3.2: Implement as `await Promise.race([page.waitForLoadState('networkidle'), page.waitForTimeout(5000)])`
- [ ] 3.3: The timeout fallthrough is intentional -- if networkidle doesn't fire, verification in Task 4 will catch real failures

### Acceptance Criteria

- `waitForTimeout(1000)` is gone from the submit step
- `waitForLoadState('networkidle')` is present with 5s cap
- Helper doesn't hang if networkidle never fires

---

## Task 4: Add Post-Submit Creation Verification

**FR**: FR-001, FR-003
**SC**: SC-001, SC-004
**EC**: EC-003
**File**: `frontend/tests/e2e/helpers/clean-state.ts`

### Description

After submit + network wait, verify the config was actually created. Check three signals in sequence with short timeouts. If all fail, throw descriptive error.

### Subtasks

- [ ] 4.1: Check for success toast: `page.locator('[data-sonner-toaster] [data-type="success"]')` visible within 2s
- [ ] 4.2: If no toast, check config name in page: `page.getByText(name)` visible within 3s
- [ ] 4.3: If neither, throw: `createTestConfig('${name}'): creation verification failed -- no success toast, config name not found in page after submit`
- [ ] 4.4: Handle toast auto-dismiss (EC-003) by checking config name as primary fallback

### Acceptance Criteria

- At least one verification signal is checked after submit
- Verification failure throws with all signals that were tried
- Auto-dismissed toasts don't cause false negatives (fallback to list check)

---

## Task 5: Wrap page.unroute() in Try/Catch

**AR**: AR-004
**File**: `frontend/tests/e2e/helpers/clean-state.ts`

### Description

Wrap the `page.unroute('**/api/v2/tickers/search**')` call in try/catch to prevent unhandled errors if the route was never registered.

### Subtasks

- [ ] 5.1: Wrap line 93 in try/catch -- swallow the error (route cleanup is best-effort)
- [ ] 5.2: Optionally log a console.warn if unroute fails (helps debugging but doesn't block)

### Acceptance Criteria

- `page.unroute()` failure doesn't crash the helper
- Route cleanup is still attempted

---

## Task 6: Verification -- Run Existing Tests

**SC**: SC-003, SC-006
**File**: N/A (test execution only)

### Description

Run all tests that call `createTestConfig()` to verify backward compatibility. No test file modifications should be needed.

### Subtasks

- [ ] 6.1: Run `cd frontend && npx playwright test config-crud alert-crud dialog-dismissal --reporter=list`
- [ ] 6.2: Verify all 6 call sites pass (3 in config-crud, 1 in alert-crud, 2 in dialog-dismissal)
- [ ] 6.3: Verify no new npm dependencies: `git diff frontend/package.json` is empty
- [ ] 6.4: Review error output in a simulated failure scenario (optional -- requires breaking the mock)

### Acceptance Criteria

- All existing tests pass without modification
- No package.json changes
- `git diff` shows only `clean-state.ts` modified
