# Feature Specification: SSE Reconnect Race Condition Fix

**Feature Branch**: `1274-sse-reconnect-race`
**Created**: 2026-03-28
**Status**: Draft
**Input**: Fix SSE reconnection test in `chaos-cross-browser.spec.ts` that fails because `waitForTimeout(5000)` + count assertion races against exponential backoff timing.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - SSE Reconnection Test Passes Deterministically (Priority: P1)

A developer pushes a PR that touches frontend chaos test code. The CI pipeline runs the Playwright E2E suite across Mobile Chrome, Mobile Safari, Desktop Chrome, Firefox, and WebKit projects. The "SSE reconnection issues new fetch after connection drop" test passes on the first attempt without relying on CI retries. Currently, the test uses `waitForTimeout(5000)` followed by a count assertion (`sseRequests.length >= 2`), which races against the app's exponential backoff timing -- if backoff starts at 1000ms base with jitter, the second reconnection attempt may not arrive within the 5-second window.

**Why this priority**: This test failure blocks the chaos testing suite and causes CI flake. The fix aligns with the anti-pattern elimination established in Feature 1271 (a11y-timing-audit).

**Independent Test**: Run `chaos-cross-browser.spec.ts` with `--retries=0` across all 5 browser projects. The SSE reconnection test passes on the first attempt every time.

**Acceptance Scenarios**:

1. **Given** the page is loaded and SSE connections are being aborted with `connectionreset`, **When** the test waits for reconnection attempts, **Then** it uses `expect.poll()` with a generous timeout (15s) instead of `waitForTimeout(5000)` + count assertion.
2. **Given** the app's SSE reconnection uses exponential backoff (base 1000ms + jitter), **When** the first reconnection fires at ~1000-2000ms and the second at ~2000-4000ms, **Then** the test's polling mechanism captures both attempts regardless of exact timing.
3. **Given** `expect.poll()` is polling for `sseRequests.length >= 2`, **When** exactly 2 requests have been captured, **Then** the backoff interval assertion (`interval > 100ms`) still executes correctly.
4. **Given** the SSE reconnection mechanism is completely broken (0 reconnection attempts), **When** the poll timeout (15s) expires, **Then** the test fails with a clear message indicating no reconnection attempts were observed.

---

### User Story 2 - Consistent Pattern with Adjacent Chaos Tests (Priority: P2)

A developer reading `chaos-cross-browser.spec.ts` sees the same `expect.poll()` pattern used in `chaos-sse-recovery.spec.ts` (T036). The two files that test SSE reconnection behavior use the same waiting strategy, making the test suite internally consistent and easier to maintain.

**Why this priority**: Pattern consistency reduces cognitive load and prevents future developers from copying the broken `waitForTimeout` + count pattern into new tests.

**Independent Test**: Grep both files for `waitForTimeout` and confirm zero instances remain in the SSE reconnection tests.

**Acceptance Scenarios**:

1. **Given** `chaos-sse-recovery.spec.ts` T036 already uses `expect.poll()` for SSE reconnection counting, **When** the fix is applied to `chaos-cross-browser.spec.ts` T043, **Then** both tests use `expect.poll()` with similar structure.
2. **Given** the `beforeEach` block in `chaos-cross-browser.spec.ts` has a `waitForTimeout(2000)`, **When** the feature scope is limited to the SSE reconnection test, **Then** the `beforeEach` `waitForTimeout` is NOT modified (it is out of scope for this feature; Feature 1271 handles that file's other `waitForTimeout` calls).

---

### Edge Cases

- What if the app makes 0 SSE requests in the test window? The `expect.poll()` timeout (15s) expires and the test fails with a clear diagnostic message. This is correct behavior -- it means SSE reconnection is broken.
- What if the app makes exactly 1 SSE request? The poll continues waiting until timeout. This correctly catches the scenario where initial connection works but reconnection does not fire.
- What if exponential backoff produces a 4s+ delay between first and second attempt? The 15s timeout accommodates this. With base delay 1000ms, the worst case for 2 attempts is ~1000ms + jitter (first) + ~2000ms + jitter (second) = ~4s total, well within 15s.
- What if the request listener misses the first SSE request because it was in flight before `page.route` was set up? The listener is attached at the start of the test, before `page.route` is called. The route intercept triggers the abort, which triggers reconnection, which the listener captures. The initial connection attempt (before route) is also captured.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The SSE reconnection test ("SSE reconnection issues new fetch after connection drop") MUST replace `await page.waitForTimeout(5000)` with `expect.poll()` that polls `sseRequests.length` until `>= 2`.
- **FR-002**: The `expect.poll()` MUST use a timeout of 15000ms to accommodate exponential backoff with jitter.
- **FR-003**: The `expect.poll()` MUST include a descriptive `message` parameter for clear failure diagnostics.
- **FR-004**: The backoff interval assertion (`interval > 100ms`) MUST still execute when 2+ requests are captured.
- **FR-005**: The test MUST NOT use `waitForTimeout` for waiting on SSE reconnection attempts.

### Non-Functional Requirements

- **NFR-001**: The fix MUST NOT change the app's SSE reconnection logic (only the test code changes).
- **NFR-002**: The fix MUST be scoped to the single failing test -- other tests in `chaos-cross-browser.spec.ts` are not modified.
- **NFR-003**: The test MUST pass across all 5 Playwright browser projects (Mobile Chrome, Mobile Safari, Desktop Chrome, Firefox, WebKit).

### Out of Scope

- Replacing `waitForTimeout` calls in other tests within `chaos-cross-browser.spec.ts` (covered by Feature 1271).
- Modifying the SSE connection/reconnection logic in `sse-connection.ts` or `sse.ts`.
- Adding new chaos helpers or modifying existing ones.

## Technical Design

### Root Cause Analysis

The `SSEConnection` class in `sse-connection.ts` uses exponential backoff with jitter:

```typescript
// Line 252: baseDelay defaults to 1000ms
const exponential = this.options.baseDelay * Math.pow(2, this.reconnectAttempts);
const jitter = Math.random() * this.options.baseDelay;
return Math.min(exponential + jitter, this.options.maxDelay);
```

For the first reconnection attempt (`reconnectAttempts = 0`): delay = 1000 * 2^0 + random(0-1000) = 1000-2000ms.
For the second attempt (`reconnectAttempts = 1`): delay = 1000 * 2^1 + random(0-1000) = 2000-3000ms.

Total time to see 2 reconnection attempts: 3000-5000ms. With a 5000ms waitForTimeout, the second attempt may land right at or after the deadline, causing a race condition.

### Fix Implementation

Replace lines 64-67 in `chaos-cross-browser.spec.ts`:

```typescript
// BEFORE (racy):
await page.waitForTimeout(5000);
expect(sseRequests.length).toBeGreaterThanOrEqual(2);

// AFTER (deterministic):
await expect
  .poll(() => sseRequests.length, {
    message: 'Expected 2+ SSE reconnection attempts',
    timeout: 15000,
    intervals: [500],
  })
  .toBeGreaterThanOrEqual(2);
```

The `intervals: [500]` parameter polls every 500ms, which is frequent enough to catch requests as they arrive without excessive overhead.

### Files Changed

| File | Change |
|------|--------|
| `frontend/tests/e2e/chaos-cross-browser.spec.ts` | Replace `waitForTimeout(5000)` + count assertion with `expect.poll()` |

### Risks

- **Low**: The 15s timeout is conservative. If the SSE reconnection mechanism is working, 2 attempts should occur within 5s. The extra 10s is buffer for slow CI runners.
- **None**: No production code changes. Test-only modification.
