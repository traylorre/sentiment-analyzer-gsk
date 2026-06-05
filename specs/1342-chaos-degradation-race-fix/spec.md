# Feature 1342: Fix chaos-degradation.spec.ts Race Condition and Weak Assertions

## Status: DRAFT

## Problem Statement

`chaos-degradation.spec.ts` contains 6 tests (T007-T012) that validate the health banner
lifecycle during API degradation. The test suite has two categories of issues:

1. **Race condition** (T012, line 229): `page.unroute()` is called immediately before
   `triggerHealthBanner()`. The unroute may not take effect before the next route handler
   fires, causing the success mock to still intercept requests that should hit the
   blocked-all pattern.

2. **Weak telemetry assertions**: `captureConsoleEvents()` captures ALL `console.warn`
   messages (including non-telemetry warnings like `[authStore] fail`). Tests check for
   substring matches (`m.includes('api_health_banner_shown')`) which could false-positive
   on unrelated messages. Console event JSON structure is never validated.

3. **Timing brittleness**: All 6 tests use `waitForTimeout` for search interactions (in
   T010, T011, T012 directly; T007-T009 via `triggerHealthBanner()` which was already
   fixed in 1339 to use `waitForResponse`). The `beforeEach` uses `waitForTimeout(2000)`.

## User Stories

### US-001: Race-Safe Route Restoration (T012)
**As a** chaos test author,
**I want** the success mock route to be fully removed before triggering new degradation,
**So that** the second degradation cycle uses the blocked-all pattern, not a stale success mock.

### US-002: Structured Telemetry Validation
**As a** chaos test author,
**I want** console event assertions to parse JSON and validate the `event` field,
**So that** non-telemetry console.warn messages don't cause false positives.

### US-003: Response-Driven Search Waits
**As a** chaos test author,
**I want** search interaction waits in T010, T011, T012 to use `waitForResponse` instead
of `waitForTimeout`,
**So that** tests are deterministic and faster.

### US-004: Page-Ready beforeEach
**As a** chaos test author,
**I want** `beforeEach` to wait for an actual page ready signal instead of
`waitForTimeout(2000)`,
**So that** tests don't have a 2s floor on every run.

## Requirements

### Functional Requirements

| ID | Requirement | Source |
|----|-------------|--------|
| FR-001 | T012: Add settle wait between `page.unroute()` and `triggerHealthBanner()` | US-001 |
| FR-002 | T007/T008/T009: Parse console events as JSON, check for `event` field before asserting | US-002 |
| FR-003 | T010: Replace `waitForTimeout(1500)` with `waitForResponse` (200 or 500 depending on fill index) | US-003 |
| FR-004 | T011: Replace `waitForTimeout(1500)` with `waitForResponse` | US-003 |
| FR-005 | T012: Replace `waitForTimeout(2000)` recovery wait with response-based wait | US-003 |
| FR-006 | `beforeEach`: Replace `waitForTimeout(2000)` with `expect(page.locator('main')).toBeVisible({ timeout: 10000 })` | US-004 |

### Non-Functional Requirements

| ID | Requirement |
|----|-------------|
| NFR-001 | No new dependencies added |
| NFR-002 | All 6 tests must still pass against current dashboard |
| NFR-003 | `triggerHealthBanner()` is NOT modified (already fixed in 1339) |
| NFR-004 | Use 1339's `captureTelemetryEvents()` if available; otherwise inline JSON parsing |

## Success Criteria

1. T012 second degradation cycle reliably triggers banner (race condition eliminated)
2. Telemetry assertions validate JSON structure, not just substring presence
3. No `waitForTimeout` in test bodies for search interactions (T010, T011, T012)
4. beforeEach uses page-ready signal

## Edge Cases

| Case | Expected Behavior |
|------|-------------------|
| Console.warn contains valid JSON without `event` field | Ignored by structured capture |
| Console.warn contains non-JSON text | Ignored by structured capture |
| T012 unroute + triggerHealthBanner race window | Settle wait (500ms) prevents stale handler firing |
| T010 first request returns 500, second returns 200 | waitForResponse matches the appropriate status per fill |

## Out of Scope

- Modifying chaos-helpers.ts (triggerHealthBanner already fixed in 1339)
- Adding new test scenarios
- Changing the health banner component
- Restructuring test organization

---

## Appendix A: Adversarial Review #1 (Spec)

### AR1-Q1: Is a 500ms settle wait sufficient for the race condition?
**Risk**: 500ms might not be enough if Playwright's route handler deregistration is async.
**Analysis**: `page.unroute()` is awaited -- it returns a Promise that resolves when the
handler is deregistered. The 500ms settle is extra safety for in-flight requests that
may have already matched the route before it was removed. Playwright's route matching is
synchronous per-request, so once `unroute` resolves, no NEW requests will match. The
settle covers requests already in the pipeline.
**Verdict**: ACCEPT -- 500ms is conservative. Could even be 100ms, but 500ms avoids
any debate.

### AR1-Q2: Should we use 1339's captureTelemetryEvents() or inline the logic?
**Risk**: If 1339 is complete, we should use its helper. If we inline, we create
divergence.
**Analysis**: Feature 1339 adds `captureTelemetryEvents()` to chaos-helpers.ts. This
feature should import and use it. If 1339's implementation isn't available yet, fall back
to inline JSON parsing with a TODO comment. The plan will check for availability.
**Verdict**: ACCEPT -- use 1339 helper, with inline fallback.

### AR1-Q3: T010/T011 use a custom route handler (not triggerHealthBanner). Is waitForResponse correct?
**Risk**: T010 has a custom handler that returns 500 for request 1 and 200 for subsequent.
T011 has two handlers (one for sentiment, one for tickers). The `waitForResponse` pattern
needs to match the correct response.
**Analysis**: For T010, after the first fill, wait for response with status 500. After
the second fill, wait for response with status 200. For T011, after each fill, wait for
ANY response on the tickers/search endpoint (which always returns 200 per the mock).
**Verdict**: ACCEPT -- waitForResponse patterns are endpoint+status specific.

### AR1-Q4: Is FR-002 (structured telemetry) breaking the existing test pattern?
**Risk**: Existing tests use `consoleMessages.find(m => m.includes('event_name'))`.
Changing to JSON parsing changes what passes.
**Analysis**: The telemetry events are emitted via `emitErrorEvent()` which outputs
`console.warn(JSON.stringify({event, timestamp, details}))`. The structured capture
parses JSON and checks the `event` field. This is strictly more precise than substring
matching. Any message that passed before will still pass -- the event name is in the
JSON `event` field. Non-JSON warnings that happened to contain the event name would
no longer match, which is correct (they were false positives).
**Verdict**: ACCEPT -- more precise is better.

---

## Appendix B: Clarifications

### C1: Why not restructure T012 to avoid the race entirely?
T012 tests "dismissed banner reappears on new degradation cycle." The current flow is:
1. Trigger banner
2. Dismiss
3. Recover (unblock + success mock)
4. Unroute success mock
5. Trigger new degradation

The race is between step 4 and 5. An alternative would be to use `page.route(pattern, handler, { times: N })` to auto-expire the success mock. However, Playwright's `times` option is relatively new and not yet stable across all versions. The settle wait is simpler and sufficient.

### C2: Should T010's waitForResponse match the custom handler's status codes?
Yes. The custom handler returns 500 for `requestCount === 1` and 200 for subsequent.
After the first fill, wait for `status() === 500`. After the second fill, wait for
`status() === 200`.
