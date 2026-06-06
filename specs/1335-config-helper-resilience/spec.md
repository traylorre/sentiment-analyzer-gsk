# Feature Specification: Config Helper Resilience

**Feature Branch**: `1335-config-helper-resilience`
**Created**: 2026-04-05
**Status**: Draft
**Input**: Under parallel load (workers=2), `createTestConfig()` in `frontend/tests/e2e/helpers/clean-state.ts` sometimes fails silently -- the Create button stays disabled because the ticker search mock or form interaction doesn't complete. The helper doesn't throw on failure, so downstream tests that depend on a config existing fail with confusing errors.

## Problem Statement

The `createTestConfig()` helper in `frontend/tests/e2e/helpers/clean-state.ts` has a silent failure mode under parallel test execution. When the ticker option doesn't appear (mock timing) or the option click doesn't register, the "Create" submit button remains disabled. The current code calls `expect(submitButton).toBeEnabled({ timeout: 10000 })` which either:

1. Times out after 10s, but the error surfaces as a generic Playwright timeout rather than a descriptive helper failure
2. Gets caught by the test's own timeout (30-45s), producing a stack trace that points to the test, not the helper

Either way, the 8 downstream tests that call `createTestConfig()` fail with confusing errors that don't identify the root cause: the config was never actually created.

### Affected Tests (8)

| File | Tests calling `createTestConfig()` | Failure mode |
|------|-----------------------------------|--------------|
| `config-crud.spec.ts` | `config card click selects it`, `delete button opens confirmation`, `delete confirm removes config` | 3 tests: config doesn't exist, subsequent assertions fail |
| `alert-crud.spec.ts` | `alert form shows config-dependent tickers` | 1 test: no config in dropdown, no tickers to display |
| `dialog-dismissal.spec.ts` | `delete dialog: cancel preserves item`, `delete dialog: escape closes` | 2 tests: config doesn't exist, can't find delete button |

Total: 6 distinct test functions across 3 files rely on `createTestConfig()` succeeding.

### Root Cause Analysis

The `createTestConfig()` helper (lines 38-94 of `clean-state.ts`) has these weaknesses:

1. **No post-submit verification**: After clicking "Create" (line 89), the helper waits 1 second (`waitForTimeout(1000)`) then exits. It never checks whether the config was actually created (no toast check, no list check, no URL change check).

2. **Soft ticker selection failure**: Lines 78-83 wrap the ticker input visibility check in `.catch(() => false)`. If the ticker input isn't visible, the code silently skips adding a ticker. But without a ticker, the submit button stays disabled -- and the `toBeEnabled` assertion on line 88 is the only gate.

3. **No explicit throw on failure**: The helper returns `Promise<void>` and never explicitly throws. If any step fails, Playwright's internal assertion timeout fires, but the error message lacks context about which step failed.

4. **Race condition under parallel load**: With `workers=2`, two browser instances may be hitting the mocked routes simultaneously. The `page.route()` mock on line 43 is per-page, but the timing of `fill('AAPL')` -> option appearance -> `option.click()` is susceptible to event loop contention under parallel execution.

## Functional Requirements

### FR-001: Post-Submit Creation Verification

After clicking the "Create" submit button, the helper MUST verify the config was actually created before returning. Verification checks (in priority order):
1. Success toast appears (Sonner `data-type="success"`)
2. Config name appears in the config list
3. URL changes away from the form/dialog

If none of these signals appear within 5 seconds, the helper MUST throw an `Error` with a descriptive message including the config name and which verification step failed.

### FR-002: Ticker Selection Guard

After filling the ticker search input and clicking the option, the helper MUST verify the ticker was actually added. Indicators:
1. A chip/badge with the ticker symbol appears (e.g., "AAPL" in a tag element)
2. The submit button becomes enabled (already checked, but now with explicit error)

If ticker selection fails, the helper MUST throw immediately with a message like: `createTestConfig('${name}'): ticker AAPL selection failed -- option click did not register`.

### FR-003: Descriptive Error Messages

All failures in `createTestConfig()` MUST include:
- The helper function name (`createTestConfig`)
- The config name that was being created
- The specific step that failed (e.g., "form open", "name fill", "ticker selection", "submit", "creation verification")
- A hint about parallel execution if relevant

### FR-004: Network Idle After Submit

After clicking submit and before verification, the helper SHOULD call `page.waitForLoadState('networkidle')` to ensure the API request has completed. This replaces the current `waitForTimeout(1000)`.

### FR-005: Backward Compatibility

The function signature `createTestConfig(page: Page, name: string): Promise<void>` MUST NOT change. All 6 existing call sites must work without modification.

## Non-Functional Requirements

### NFR-001: No New Dependencies

The fix must use only Playwright built-in APIs. No new npm packages.

### NFR-002: Performance Budget

The helper must complete within 15 seconds total (up from ~12s current). The additional verification step adds at most 5 seconds.

### NFR-003: Deterministic Under Parallel Load

The fix must be resilient to `workers=4` parallel execution (see AR-001). No shared state between test workers.

## Success Criteria

| ID | Criterion | Verification |
|----|-----------|-------------|
| SC-001 | `createTestConfig()` throws descriptive error when config creation fails | Unit-style Playwright test with mocked failure |
| SC-002 | `createTestConfig()` throws descriptive error when ticker selection fails | Unit-style Playwright test with broken ticker mock |
| SC-003 | All 6 existing test call sites pass without modification | Run `npx playwright test config-crud alert-crud dialog-dismissal` |
| SC-004 | Error message includes helper name, config name, and failed step | Inspect thrown error in failure scenario |
| SC-005 | `waitForTimeout(1000)` replaced with `waitForLoadState('networkidle')` | Code review |
| SC-006 | No new npm dependencies added | `git diff package.json` is empty |

## Adversarial Review Findings

### AR-001: Workers Count Is 4, Not 2

The feature description says `workers=2`, but `playwright.config.ts` shows `workers: 4` with `fullyParallel: true`. This means **up to 20 parallel browser instances** (4 workers x 5 projects: Mobile Chrome, Mobile Safari, Desktop Chrome, Firefox, WebKit). The race condition is worse than initially described.

### AR-002: Silent Skip of Ticker Input

Lines 78-83 of `createTestConfig()` wrap the ticker input visibility check in `.catch(() => false)`. If the placeholder regex `/search for a ticker/i` doesn't match (e.g., the app changed the placeholder text), the entire ticker flow is silently skipped. The submit button will stay disabled, and the `toBeEnabled` timeout will fire 10 seconds later with no context about *why* it was disabled.

**Recommendation**: If the ticker input is not found, throw immediately with the placeholder text that was tried. Do NOT silently skip.

### AR-003: `waitForTimeout(1000)` Is a Code Smell But Not the Root Cause

Replacing `waitForTimeout(1000)` with `waitForLoadState('networkidle')` (FR-004) is correct, but `networkidle` can hang if the page has long-polling or SSE connections. The customer dashboard uses TanStack Query for data fetching with `refetchInterval`. If any query has auto-refetch enabled on the `/configs` page, `networkidle` will never resolve.

**Mitigation**: Use `waitForLoadState('networkidle')` with a timeout wrapper (5s max), then fall through to the verification checks regardless.

### AR-004: The `page.unroute()` at Line 93 Can Throw

If the route was never successfully registered (e.g., `page.route()` threw), `page.unroute()` at line 93 will throw an unhandled error. This should be wrapped in try/catch.

### AR-005: `deleteTestConfig()` Has the Same Pattern

`deleteTestConfig()` (lines 100-114) also uses `waitForTimeout(500)` and doesn't verify deletion. This is out of scope per the spec, but should be noted for a follow-up feature.

## Out of Scope

- Changes to `deleteTestConfig()` or `createTestAlert()` (separate features if needed)
- Changes to the production Next.js config form component
- Retry logic inside the helper (callers can retry if needed)
- Changes to Playwright test configuration (workers count, timeouts)

## Edge Cases

### EC-001: Form Component Not Rendered

If the CTA button ("Create Configuration" / "New") never appears, the helper already throws via `expect(cta.first()).toBeVisible({ timeout: 5000 })`. This is adequate but the error should be wrapped with helper context.

### EC-002: Ticker Search Mock Not Intercepted

If `page.route()` fails to register before the page navigates, the real ticker API is hit. Under rate limiting, it may return 429. The mock should be registered before `page.goto()` (currently correct -- line 43 before line 53).

### EC-003: Success Toast Auto-Dismisses

Sonner toasts auto-dismiss after ~4s by default. The verification must check for the toast quickly or use multiple signals (toast OR list entry OR URL change).
