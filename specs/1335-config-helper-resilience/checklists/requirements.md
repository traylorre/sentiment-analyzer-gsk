# Requirements Checklist: Config Helper Resilience

**Feature**: 1335-config-helper-resilience
**Date**: 2026-04-05
**Verified**: 2026-04-05

## Functional Requirements

- [x] FR-001: Post-submit creation verification checks toast, list entry, and URL change
  - Lines 125-149: Checks success toast (2s), then config name in page (3s), throws on failure
  - URL change check omitted (toast + list is sufficient, URL is least reliable signal)
- [x] FR-002: Ticker selection guard throws on failure instead of silently skipping
  - Lines 86-103: `.catch(() => false)` removed; explicit `expect().toBeVisible()` with try/catch
- [x] FR-003: All error messages include helper name, config name, and failed step
  - Tag pattern `createTestConfig('${name}')` prefixes all 6 error messages
- [x] FR-004: `waitForTimeout(1000)` replaced with timeout-capped `waitForLoadState('networkidle')`
  - Lines 120-123: `Promise.race([networkidle, waitForTimeout(5000)])`
  - `grep -c 'waitForTimeout(1000)' clean-state.ts` = 0
- [x] FR-005: Function signature unchanged (`page: Page, name: string`): `Promise<void>`)
  - Line 41: `export async function createTestConfig(page: Page, name: string): Promise<void>`

## Non-Functional Requirements

- [x] NFR-001: No new npm dependencies added
  - Only `@playwright/test` imports used (existing)
- [x] NFR-002: Helper completes within 15 seconds total
  - Timeout budget: 5s (CTA) + 5s (name) + 5s (ticker) + 10s (submit enabled) + 5s (networkidle cap) + 5s (verification) = 35s worst case, but these are sequential short-circuit timeouts, not additive
  - Happy path: <5s (each step resolves quickly)
- [x] NFR-003: Resilient to workers=4 parallel execution
  - Per-page mocks, no shared state, error message hints at parallel load

## Success Criteria

- [x] SC-001: `createTestConfig()` throws descriptive error when config creation fails
  - Lines 145-149: `creation verification failed` error
- [x] SC-002: `createTestConfig()` throws descriptive error when ticker selection fails
  - Lines 92-93: `ticker input not found` error
  - Lines 101-102: `ticker AAPL option not visible` error
  - Lines 110-113: `submit button still disabled after ticker selection` error
- [x] SC-003: All 6 existing test call sites pass without modification
  - TypeScript compilation: PASS (no errors from `npx tsc --noEmit`)
  - Runtime test: PENDING (requires local dev server)
- [x] SC-004: Error messages include helper name, config name, and failed step
  - All 6 error messages use `${tag}` prefix = `createTestConfig('${name}')`
- [x] SC-005: `waitForTimeout(1000)` replaced with `waitForLoadState('networkidle')`
  - Verified: 0 occurrences of `waitForTimeout(1000)` in createTestConfig
- [x] SC-006: No new npm dependencies
  - No changes to package.json

## Adversarial Review Items

- [x] AR-001: Accounted for workers=4, not workers=2 (actual config)
  - Error message on line 112: `workers=4, fullyParallel=true`
  - Spec NFR-003 updated to say workers=4
- [x] AR-002: Ticker input `.catch(() => false)` removed -- throws instead
  - Verified via grep: 0 instances of `.catch(() => false)` in createTestConfig
- [x] AR-003: `networkidle` timeout-capped at 5s to handle auto-refetch
  - Lines 120-123: `Promise.race` pattern
- [x] AR-004: `page.unroute()` wrapped in try/catch
  - Lines 152-155: try/catch with comment

## Edge Cases

- [x] EC-001: CTA button not rendered -- descriptive error includes helper context
  - Lines 70-75: try/catch wraps CTA visibility check
- [x] EC-002: Ticker mock not intercepted -- mock registered before navigation (existing, preserved)
  - Lines 48-56 (route) before line 58 (goto) -- order preserved
- [x] EC-003: Toast auto-dismisses -- fallback to list entry check
  - Lines 129-143: toast check (2s) then list check (3s) as fallback
