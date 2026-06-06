# Implementation Plan -- Feature 1342: Fix chaos-degradation.spec.ts Race Condition and Weak Assertions

## Files to Modify

### 1. `frontend/tests/e2e/chaos-degradation.spec.ts` (PRIMARY -- only file)

All changes are within this single test file.

## Technical Context

### Current State (line references)

| Line | Current Code | Problem |
|------|-------------|---------|
| 28 | `await page.waitForTimeout(2000)` | Arbitrary wait in beforeEach |
| 34 | `const consoleMessages = captureConsoleEvents(page)` | Captures ALL warnings, not structured |
| 45-48 | `consoleMessages.find(m => m.includes('api_health_banner_shown'))` | Substring match, no JSON validation |
| 69-72 | Same pattern for dismiss event | Same problem |
| 106 | `waitForRecovery(page, consoleMessages)` | Uses old-style console capture |
| 132 | `await page.waitForTimeout(1500)` (T010 first search) | Not response-driven |
| 137 | `await page.waitForTimeout(1500)` (T010 second search) | Not response-driven |
| 175-185 | 3x `waitForTimeout(1500)` (T011) | Not response-driven |
| 226 | `await page.waitForTimeout(2000)` (T012 recovery wait) | Not response-driven |
| 229 | `await page.unroute(...)` then immediately `triggerHealthBanner` | Race condition |

### Import Changes

Current:
```typescript
import {
  blockAllApi,
  unblockAllApi,
  triggerHealthBanner,
  waitForRecovery,
  captureConsoleEvents,
  getBannerLocator,
  getDismissButton,
} from './helpers/chaos-helpers';
```

If 1339's `captureTelemetryEvents` is available, add it to imports and replace
`captureConsoleEvents` usage. If not yet available, use inline JSON parsing.

### Approach: Check 1339 Availability

Before implementation, check if `captureTelemetryEvents` exists in chaos-helpers.ts:
```bash
grep -n 'captureTelemetryEvents' frontend/tests/e2e/helpers/chaos-helpers.ts
```

If present: import and use it. If absent: use inline JSON parsing pattern with TODO.

## Implementation Plan

### Step 1: Fix beforeEach (FR-006)

Replace:
```typescript
await page.waitForTimeout(2000);
```
With:
```typescript
await expect(page.locator('main')).toBeVisible({ timeout: 10000 });
```

### Step 2: Fix T007 telemetry assertion (FR-002)

**Option A (1339 helper available)**:
Replace `captureConsoleEvents(page)` with `captureTelemetryEvents(page)`:
```typescript
const telemetry = captureTelemetryEvents(page);
// ... test body ...
const bannerEvent = telemetry.findEvent('api_health_banner_shown');
expect(bannerEvent).toBeTruthy();
```

**Option B (inline fallback)**:
Keep `captureConsoleEvents` but validate structure:
```typescript
const consoleMessages = captureConsoleEvents(page);
// ... test body ...
const bannerEvent = consoleMessages.find((m) => {
  try {
    const parsed = JSON.parse(m);
    return parsed.event === 'api_health_banner_shown';
  } catch {
    return false;
  }
});
expect(bannerEvent).toBeTruthy();
```

### Step 3: Fix T008 telemetry assertion (FR-002)

Same pattern as Step 2 for the `api_health_banner_dismissed` event.

### Step 4: Fix T009 telemetry + recovery (FR-002)

Same pattern for `api_health_recovered` event in `waitForRecovery`. Note:
`waitForRecovery()` from chaos-helpers.ts takes `consoleMessages: string[]`. If using
1339's structured capture, the recovery check may need adjustment.

If 1339's `waitForRecovery` is updated to accept `TelemetryCapture`, use that.
Otherwise, keep `consoleMessages` for `waitForRecovery` and add a separate structured
assertion for the recovery event.

### Step 5: Fix T010 -- response-driven waits (FR-003)

Replace:
```typescript
await searchInput.fill('AAPL');
await page.waitForTimeout(1500);

await searchInput.fill('');
await searchInput.fill('GOOG');
await page.waitForTimeout(1500);
```

With:
```typescript
// First search fails (requestCount === 1 -> 500)
await searchInput.fill('AAPL');
await page.waitForResponse((r) =>
  r.url().includes('/tickers/search') && r.status() === 500,
);

// Second search succeeds (requestCount > 1 -> 200)
await searchInput.fill('');
await searchInput.fill('GOOG');
await page.waitForResponse((r) =>
  r.url().includes('/tickers/search') && r.status() === 200,
);
```

### Step 6: Fix T011 -- response-driven waits (FR-004)

Replace each `waitForTimeout(1500)` with appropriate `waitForResponse`:
```typescript
await searchInput.fill('AAPL');
await page.waitForResponse((r) => r.url().includes('/tickers/search'));
```
Repeat for GOOG and MSFT. The tickers endpoint always returns 200 per the mock.

### Step 7: Fix T012 -- race condition and recovery wait (FR-001, FR-005)

**Race condition fix** (line 229):
```typescript
// BEFORE:
await page.unroute('**/api/v2/tickers/search**');
await triggerHealthBanner(page);

// AFTER:
await page.unroute('**/api/v2/tickers/search**');
// Settle: ensure unroute is fully deregistered before triggering new degradation
await page.waitForTimeout(500);
await triggerHealthBanner(page);
```

**Recovery wait fix** (line 226):
```typescript
// BEFORE:
await page.waitForTimeout(2000);

// AFTER:
// Wait for a successful response to confirm recovery
await searchInput.fill('');
await searchInput.fill('TSLA');
await page.waitForResponse((r) =>
  r.url().includes('/tickers/search') && r.ok(),
  { timeout: 5000 },
);
```

## Risk Assessment

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| 1339 telemetry helper not yet available | Medium | Low | Inline JSON parsing fallback |
| T010 waitForResponse matches wrong request | Low | Medium | Pattern includes `/tickers/search` + specific status |
| T012 500ms settle not sufficient | Very Low | Medium | unroute is awaited; 500ms is extra safety |
| waitForRecovery signature mismatch with new capture | Medium | Low | Keep consoleMessages for waitForRecovery, add structured assertion separately |

---

## Appendix A: Adversarial Review #2 (Plan)

### AR2-Q1: Step 4 (T009) -- waitForRecovery takes string[]. How to bridge structured capture?
**Challenge**: `waitForRecovery(page, consoleMessages)` expects `string[]`. If we switch
to `captureTelemetryEvents`, the types don't match.
**Analysis**: Two options:
1. Keep `captureConsoleEvents` for tests that call `waitForRecovery`, and add a SEPARATE
   structured check for the specific event name.
2. Pass both captures (old string[] for `waitForRecovery`, new structured for event checks).

Option 1 is simpler. T009 uses `waitForRecovery` which already checks for
`api_health_recovered` in the string array. The structured check is redundant for T009.
Only T007 and T008 need structured event checks (they don't call waitForRecovery).
**Verdict**: ACCEPT option 1 -- keep `captureConsoleEvents` where `waitForRecovery` is
used. Use structured capture only in T007/T008.

### AR2-Q2: Step 5 (T010) -- requestCount is closure-scoped. Will waitForResponse race with it?
**Challenge**: The custom route handler uses `requestCount++` to decide 500 vs 200.
`waitForResponse` matches by status code. If a background refetch fires before the
explicit search fill, requestCount increments unexpectedly.
**Analysis**: The route is registered on `**/api/v2/tickers/search**` which only fires
on ticker search requests. Background refetches (e.g., React Query) don't call this
endpoint without user interaction. The search input fill triggers the request.
**Verdict**: ACCEPT -- no background requests to this endpoint.

### AR2-Q3: Step 7 recovery -- adding a search fill changes test semantics?
**Challenge**: The original T012 just waits 2s after unblocking. The fix adds a search
fill + waitForResponse. This changes the test from passive to active recovery check.
**Analysis**: T012's purpose is to verify the dismissed banner reappears on a NEW
degradation cycle. The recovery step between cycles needs to confirm the dashboard
actually recovered (not just that 2s passed). An active search with response verification
is more reliable. The search input state is reset with `fill('')` first.
**Verdict**: ACCEPT -- active recovery check is more reliable.

### AR2-Q4: Are there any T007-T012 tests NOT covered by this plan?
**Audit**:
- T007 (banner appears): Step 2 (telemetry fix)
- T008 (dismissal): Step 3 (telemetry fix)
- T009 (auto-clear): Step 4 (telemetry, kept as-is with consoleMessages for waitForRecovery)
- T010 (single failure): Step 5 (response waits)
- T011 (cross-endpoint): Step 6 (response waits)
- T012 (dismissed reappears): Step 7 (race fix + recovery wait)
- beforeEach: Step 1 (page ready)

All 6 tests covered.
**Verdict**: COMPLETE.
