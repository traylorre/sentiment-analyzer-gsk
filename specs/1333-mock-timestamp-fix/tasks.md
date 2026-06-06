# Feature 1333: Tasks

## Task 1: Rewrite generateCandles() to use UTC-only date math

**File:** `frontend/tests/e2e/helpers/mock-api-data.ts`
**Lines:** 28-63

**Before:**
```typescript
function generateCandles(count: number): Array<{...}> {
  const candles = [];
  const baseDate = new Date('2026-03-01');
  let price = 178.5;

  for (let i = 0; i < count; i++) {
    const date = new Date(baseDate);
    date.setDate(baseDate.getDate() + i);
    // Skip weekends
    if (date.getDay() === 0 || date.getDay() === 6) continue;
    // ...
    candles.push({
      date: date.toISOString().split('T')[0],
      // ...
    });
  }
  return candles;
}
```

**After:**
```typescript
function generateCandles(count: number): Array<{...}> {
  const candles = [];
  const baseMs = Date.UTC(2026, 2, 2); // March 2, 2026 (Monday) — UTC-only
  const DAY_MS = 86_400_000;
  let price = 178.5;

  for (let i = 0; i < count; i++) {
    const d = new Date(baseMs + i * DAY_MS);
    // Skip weekends (UTC day-of-week, not local)
    if (d.getUTCDay() === 0 || d.getUTCDay() === 6) continue;
    // ...
    candles.push({
      date: d.toISOString().split('T')[0],
      // ...
    });
  }
  return candles;
}
```

**Key changes:**
- `new Date('2026-03-01')` -> `Date.UTC(2026, 2, 2)` (March 2 Monday, returns ms)
- `new Date(baseDate)` + `setDate()` -> `new Date(baseMs + i * DAY_MS)` (ms arithmetic)
- `date.getDay()` -> `d.getUTCDay()` (UTC weekday check)
- `date.toISOString()` stays the same (already UTC)

**Preserves:**
- Return type signature (unchanged)
- FR-009: `i === 0` null-volume candle (i=0 is Monday, not skipped)
- Random price generation logic (unchanged)

---

## Task 2: Rewrite generateSentimentPoints() to use UTC-only date math

**File:** `frontend/tests/e2e/helpers/mock-api-data.ts`
**Lines:** 70-110

**Same pattern as Task 1.** Replace:
- `new Date('2026-03-01')` -> `Date.UTC(2026, 2, 2)`
- `new Date(baseDate)` + `setDate()` -> `new Date(baseMs + i * DAY_MS)`
- `date.getDay()` -> `d.getUTCDay()`

**Preserves:**
- Return type signature (unchanged)
- FR-007: Negative score at `i === 1` (i=1 is Tuesday, not skipped)
- FR-008: Multiple sentiment sources via modulo (unchanged)
- FR-009: `i === 0` null confidence/label (i=0 is Monday, not skipped)

---

## Task 3: Verify no other callers or hardcoded date expectations

**Action:** Grep for imports of `mock-api-data` and any hardcoded `2026-03-01` or
`2026-03-28` dates in test files.

**Expected result:** Only the 3 affected test files import from `mock-api-data.ts`.
The fallback dates in `MOCK_EMPTY_*_RESPONSE` are hardcoded but are for the empty-array
variants and don't need to change (they're never compared against generated data).

---

## Task 4: Run affected tests in UTC

```bash
cd frontend && TZ=UTC npx playwright test chaos-cached-data chaos-cross-browser ticker-search-gaps
```

**Expected:** 6 tests pass.

---

## Task 5: Run affected tests in PST

```bash
cd frontend && TZ=America/Los_Angeles npx playwright test chaos-cached-data chaos-cross-browser ticker-search-gaps
```

**Expected:** 6 tests pass with identical behavior to UTC run.

---

## Task 6: Run full E2E suite for regression check

```bash
cd frontend && npx playwright test
```

**Expected:** No new failures introduced.

---

## Adversarial Review #3 (AR#3): Final Readiness

### Checklist

- [x] **Single file change** — `mock-api-data.ts` only. Minimal blast radius.
- [x] **No signature changes** — `generateCandles()` and `generateSentimentPoints()`
      return types unchanged. `mockTickerDataApis()` unchanged.
- [x] **No export changes** — `MOCK_EMPTY_OHLC_RESPONSE` and
      `MOCK_EMPTY_SENTIMENT_RESPONSE` are hardcoded and unaffected.
- [x] **FR-009 preserved** — `i=0` and `i=1` are both weekdays in the new code,
      so null variants and negative score are correctly generated. (Actually an
      improvement: in PST, the old code skipped i=0 and i=1 because they were
      weekends, silently breaking FR-009.)
- [x] **No hardcoded count assertions** — All tests use regex patterns like
      `/[1-9]\d* price candles/` or presence checks.
- [x] **Deterministic across timezones** — UTC arithmetic produces identical
      output in any timezone. Verified with Node.js in UTC, PST, IST, NZDT.
- [x] **No new dependencies** — Uses built-in `Date.UTC()`, `getUTCDay()`,
      `toISOString()`.
- [x] **Diff is small** — ~8 lines changed across 2 functions. Easy to review.

### Remaining Risk

**None identified.** The fix is mechanical (local -> UTC method substitution) with
verified behavior. The only "behavioral" change is:
1. Candle count normalizes to 22 (was 20-21 depending on timezone)
2. FR-009 null variants are now correctly generated (were silently skipped in PST)

Both changes are improvements, not regressions.

### Ready for Implementation

Yes. Tasks 1-2 are the code changes. Tasks 3-6 are verification. No blockers.
