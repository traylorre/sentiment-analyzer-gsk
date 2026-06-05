# Feature 1341: Fix Green Dashboard Syndrome in chaos-cached-data.spec.ts

## Status: DRAFT

## Problem Statement

`chaos-cached-data.spec.ts` contains 2 tests (T013-T014) that validate cached data
resilience during API outages. Both tests capture `textBefore` and `textDuring` but only
check that `textDuring` has length > 10 -- they never compare the two values. A bug that
replaces dashboard content with an error page of >10 characters would pass both tests.

Additionally:
- T014's interactive element click wraps the entire click in `.catch(() => {...})`,
  silently accepting click failures
- Chart persistence is not verified after chaos -- the chart container is checked in
  `beforeEach` but never re-checked after `blockAllApi`
- `mockTickerDataApis()` returns a cleanup function that is never called, leaking mock
  routes between tests

## User Stories

### US-001: Content Identity Verification During Outage
**As a** chaos test author,
**I want** `textDuring` to be compared against `textBefore` (not just checked for length),
**So that** a bug replacing real data with an error page is caught.

### US-002: Chart Persistence After Chaos
**As a** chaos test author,
**I want** the chart container to be re-verified after API blocking,
**So that** chart disappearance during an outage is detected.

### US-003: Strict Interactive Element Assertion
**As a** chaos test author,
**I want** the interactive element click to assert success (or at minimum, element still
in DOM),
**So that** a crash triggered by clicking during outage is caught.

### US-004: Mock Route Cleanup
**As a** chaos test author,
**I want** `mockTickerDataApis()` cleanup function called in `afterEach`,
**So that** mock routes don't leak between tests.

## Requirements

### Functional Requirements

| ID | Requirement | Source |
|----|-------------|--------|
| FR-001 | T013: Assert `textDuring` contains a substring from `textBefore` (first 20 chars) | US-001 |
| FR-002 | T014: Assert `textDuring` contains a substring from `textBefore` (first 20 chars) | US-001 |
| FR-003 | T013: After `blockAllApi`, assert chart container locator is still visible | US-002 |
| FR-004 | T014: Remove `.catch(() => {...})` from interactive element click; assert element is visible before click | US-003 |
| FR-005 | Store cleanup function from `mockTickerDataApis()` and call it in `afterEach` | US-004 |

### Non-Functional Requirements

| ID | Requirement |
|----|-------------|
| NFR-001 | No new dependencies added |
| NFR-002 | Both tests must still pass against current dashboard |
| NFR-003 | Mock route cleanup must not interfere with chaos route blocking |

## Success Criteria

1. T013 FAILS if dashboard content is replaced by an error page during outage
2. T014 FAILS if the interactive element click crashes the page
3. Chart container is verified to still be visible after API blocking
4. No mock route leaks between tests (cleanup function called in afterEach)

## Edge Cases

| Case | Expected Behavior |
|------|-------------------|
| Chart container removed from DOM during outage | FR-003 assertion catches it |
| No clickable elements on page | T014 already handles this with `if (clickableCount > 0)` |
| Click triggers navigation that changes textContent | `textBefore` comparison would fail -- this IS a bug during outage |
| mockTickerDataApis cleanup runs after blockAllApi | blockAllApi uses `**/api/**` which is broader; cleanup removes specific routes that are already shadowed |

## Out of Scope

- Adding new test scenarios
- Modifying mock-api-data.ts
- Changing chaos-helpers.ts
- Testing chart canvas content (pixel-level)

---

## Appendix A: Adversarial Review #1 (Spec)

### AR1-Q1: Will calling cleanup in afterEach conflict with blockAllApi?
**Risk**: `afterEach` calls cleanup which unroutes specific mock endpoints. But
`blockAllApi` already overrides them via Playwright's LIFO route matching. Does unrouting
the mocks after the test cause issues?
**Analysis**: Route cleanup order doesn't matter after the test completes. The cleanup
runs after all assertions are done. Even if `blockAllApi`'s broader pattern is still
active, unrouting the specific mock patterns is harmless -- Playwright handles this
gracefully.
**Verdict**: ACCEPT -- no conflict.

### AR1-Q2: Is chart visibility check sufficient for "chart persistence"?
**Risk**: The chart container might be visible but empty (canvas with no data rendered).
**Analysis**: The `beforeEach` already asserts `aria-label` contains a candle count regex
(`/[1-9]\d* price candles/`). Adding a post-chaos re-check of the same aria-label would
be ideal, but checking visibility alone is sufficient for this fix scope. The chart
canvas retains its rendered state when the API goes down -- it's not re-rendered on
failed refetches.
**Verdict**: ACCEPT -- visibility check is the right scope for this fix. Full canvas
verification is a separate enhancement.

### AR1-Q3: Should T014's click test assert more than "didn't crash"?
**Risk**: The test's stated purpose is "Content should still be interactive (clicking
doesn't crash)." Making the click assertion strict could introduce false negatives if
the element becomes disabled during outage.
**Analysis**: The fix changes from "swallow all errors" to "assert element is visible,
then click." If the click itself fails (e.g., element is covered by a modal), that's
a legitimate UX issue during outage. But we should NOT assert the click "did something"
because the API is down. The assertion should be: element is visible + click doesn't
throw.
**Verdict**: ACCEPT -- assert visibility before click, remove catch, but don't assert
click outcome.

---

## Appendix B: Clarifications

### C1: Why 20 characters for fragment comparison?
Same rationale as Feature 1340: the first 20 characters of `main` textContent are
typically stable UI text (ticker symbol, section header). Dynamic values appear later.

### C2: Should chart check use the same aria-label regex as beforeEach?
For this feature, use `toBeVisible()` only. The aria-label check in beforeEach verifies
data loaded correctly. Post-chaos, we're verifying the chart didn't disappear. The
candle count in the aria-label shouldn't change during an outage since no new data
arrives.
