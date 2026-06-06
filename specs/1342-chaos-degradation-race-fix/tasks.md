# Tasks -- Feature 1342: Fix chaos-degradation.spec.ts Race Condition and Weak Assertions

## Task Dependencies

```
T1 (beforeEach) ──> T2 (T007 telemetry)
                ──> T3 (T008 telemetry)
                ──> T4 (T009 telemetry -- assessment only)
                ──> T5 (T010 waits)
                ──> T6 (T011 waits)
                ──> T7 (T012 race + recovery)
T1-T7 ──────────> T8 (verification)
```

## Tasks

### T1: Fix beforeEach page-ready wait
**File**: `frontend/tests/e2e/chaos-degradation.spec.ts`
**Action**: Replace line 28
**Details**:
- Remove `await page.waitForTimeout(2000);`
- Replace with `await expect(page.locator('main')).toBeVisible({ timeout: 10000 });`

**Acceptance**: beforeEach waits for main element, not arbitrary timeout.

---

### T2: Fix T007 -- structured telemetry assertion
**File**: `frontend/tests/e2e/chaos-degradation.spec.ts`
**Action**: Modify T007 test body (lines 31-49)
**Details**:

**Pre-check**: Verify if `captureTelemetryEvents` exists in chaos-helpers.ts.

**If available** (1339 complete):
1. Update import to include `captureTelemetryEvents` (remove `captureConsoleEvents` if no other test uses it)
2. Replace `const consoleMessages = captureConsoleEvents(page);` with:
   ```typescript
   const telemetry = captureTelemetryEvents(page);
   ```
3. Replace substring match (lines 45-48):
   ```typescript
   // BEFORE:
   const bannerEvent = consoleMessages.find((m) =>
     m.includes('api_health_banner_shown'),
   );
   expect(bannerEvent).toBeTruthy();

   // AFTER:
   const bannerEvent = telemetry.findEvent('api_health_banner_shown');
   expect(bannerEvent).toBeTruthy();
   ```

**If not available** (inline fallback):
Replace substring match with JSON-parsing check:
```typescript
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

**Acceptance**: Telemetry event assertion validates JSON structure, not just substring.

---

### T3: Fix T008 -- structured telemetry assertion
**File**: `frontend/tests/e2e/chaos-degradation.spec.ts`
**Action**: Modify T008 test body (lines 52-73)
**Details**:

Same pattern as T2 but for `api_health_banner_dismissed` event:

**If 1339 helper available**:
```typescript
const telemetry = captureTelemetryEvents(page);
// ... test body ...
const dismissEvent = telemetry.findEvent('api_health_banner_dismissed');
expect(dismissEvent).toBeTruthy();
```

**If inline fallback**:
```typescript
const dismissEvent = consoleMessages.find((m) => {
  try {
    const parsed = JSON.parse(m);
    return parsed.event === 'api_health_banner_dismissed';
  } catch {
    return false;
  }
});
expect(dismissEvent).toBeTruthy();
```

**Acceptance**: Dismiss event assertion validates JSON structure.

---

### T4: Assess T009 telemetry (no change needed)
**File**: `frontend/tests/e2e/chaos-degradation.spec.ts`
**Action**: Assessment only -- document decision
**Details**:

T009 calls `waitForRecovery(page, consoleMessages)` which accepts `string[]`. The
`waitForRecovery` function in chaos-helpers.ts already checks for `api_health_recovered`
via substring match. Changing T009 to structured capture would require modifying
`waitForRecovery`'s signature, which is out of scope (FR: this spec file only).

**Decision**: Keep `captureConsoleEvents` for T009. Add a code comment:
```typescript
// T009 uses captureConsoleEvents (not captureTelemetryEvents) because
// waitForRecovery() expects string[]. See 1339 for future structured migration.
```

If T007/T008 switch to `captureTelemetryEvents`, T009 is the only consumer of
`captureConsoleEvents`. Keep the import.

**Acceptance**: T009 unchanged. Decision documented in code.

---

### T5: Fix T010 -- response-driven waits
**File**: `frontend/tests/e2e/chaos-degradation.spec.ts`
**Action**: Modify T010 test body (lines 110-142)
**Details**:

Replace both `waitForTimeout(1500)` calls:
```typescript
// BEFORE:
await searchInput.fill('AAPL');
await page.waitForTimeout(1500);

await searchInput.fill('');
await searchInput.fill('GOOG');
await page.waitForTimeout(1500);

// AFTER:
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

**Acceptance**: No `waitForTimeout` in T010 body. Waits match expected status codes.

---

### T6: Fix T011 -- response-driven waits
**File**: `frontend/tests/e2e/chaos-degradation.spec.ts`
**Action**: Modify T011 test body (lines 145-190)
**Details**:

Replace all 3 `waitForTimeout(1500)` calls:
```typescript
// BEFORE (repeated 3 times):
await searchInput.fill('AAPL');
await page.waitForTimeout(1500);

// AFTER (repeated 3 times):
await searchInput.fill('AAPL');
await page.waitForResponse((r) => r.url().includes('/tickers/search'));
```

Apply for AAPL, GOOG, and MSFT fills. The tickers/search endpoint always returns 200
(per the mock route).

**Acceptance**: No `waitForTimeout` in T011 body.

---

### T7: Fix T012 -- race condition and recovery wait
**File**: `frontend/tests/e2e/chaos-degradation.spec.ts`
**Action**: Modify T012 test body (lines 193-234)
**Details**:

1. **Recovery wait fix** (line 226):
   Replace `await page.waitForTimeout(2000);` with response-driven recovery:
   ```typescript
   // Trigger a search to confirm recovery (success mock is active)
   const searchInput = page.getByPlaceholder(/search tickers/i);
   await searchInput.fill('');
   await searchInput.fill('TSLA');
   await page.waitForResponse(
     (r) => r.url().includes('/tickers/search') && r.ok(),
     { timeout: 5000 },
   );
   ```
   Note: `searchInput` may already be declared earlier in the test. Check scope and
   reuse if available.

2. **Race condition fix** (line 229):
   Add settle wait after unroute:
   ```typescript
   // BEFORE:
   await page.unroute('**/api/v2/tickers/search**');
   await triggerHealthBanner(page);

   // AFTER:
   await page.unroute('**/api/v2/tickers/search**');
   // Settle: ensure route deregistration completes before re-blocking
   await page.waitForTimeout(500);
   await triggerHealthBanner(page);
   ```

**Acceptance**: Race condition mitigated with settle wait. Recovery verified via response.

---

### T8: Verification
**Action**: Run test suite
**Details**:
```bash
cd frontend && npx playwright test chaos-degradation.spec.ts --reporter=list
```

Verify:
- All 6 tests pass
- No `waitForTimeout` in T010, T011 bodies
- T012 has settle wait between unroute and triggerHealthBanner
- Telemetry assertions in T007/T008 validate JSON structure
- T009 documented decision about consoleMessages

**Acceptance**: All tests pass. Grep confirms no unguarded `waitForTimeout` in search
interaction blocks.

---

## Appendix A: Adversarial Review #3 (Tasks)

### AR3-Q1: T5 -- what if requestCount increments from a refetch before the explicit fill?
**Analysis**: The route `**/api/v2/tickers/search**` only fires on search endpoint
requests. React Query's refetch logic calls the search endpoint only when the user types
in the search input. No background/periodic refetch for this endpoint. The first `fill`
is the first request.
**Verdict**: ACCEPT.

### AR3-Q2: T7 -- is `searchInput` already declared in T012?
**Analysis**: Looking at lines 193-234, `searchInput` is declared on line 223:
```typescript
const searchInput = page.getByPlaceholder(/search tickers/i);
```
The recovery fix (step 1) happens around line 226 and can reuse this declaration. The
race fix (step 2) happens after line 229, after `searchInput` scope. No shadowing issue.
**Verdict**: ACCEPT -- reuse existing declaration.

### AR3-Q3: T4 decision to keep captureConsoleEvents -- does this leave T009 weaker?
**Analysis**: T009's telemetry assertion goes through `waitForRecovery()` which checks
for `api_health_recovered` in the string array. The substring match is less precise but
the risk of false positive is low (no other console.warn message would contain
`api_health_recovered`). Fixing this properly requires modifying `waitForRecovery`'s
interface in chaos-helpers.ts, which is a 1339 concern.
**Verdict**: ACCEPT -- documented tech debt, not a blocking issue.

### AR3-Q4: Is the task set complete?
**Audit**:
- beforeEach: T1 (page ready -- fixed)
- T007: T2 (structured telemetry -- fixed)
- T008: T3 (structured telemetry -- fixed)
- T009: T4 (assessed, kept as-is with documentation)
- T010: T5 (response waits -- fixed)
- T011: T6 (response waits -- fixed)
- T012: T7 (race + recovery -- fixed)
- Verification: T8

All 6 tests covered. No gaps.
**Verdict**: COMPLETE.

---

## READY FOR IMPLEMENTATION

All adversarial reviews passed. No blocking issues. Feature depends on 1339 (complete).
Single-file change with 7 edit tasks + verification.
