# Feature 1333: mock-timestamp-fix

## Status: SPECIFIED

## User Story

As a developer running Playwright E2E tests, I need `generateCandles()` and
`generateSentimentPoints()` to produce unique, strictly ascending dates regardless
of the host machine's timezone, so that lightweight-charts never crashes with
"data must be asc ordered by time" and all 6 affected tests pass reliably.

## Problem Statement

`generateCandles()` in `frontend/tests/e2e/helpers/mock-api-data.ts` uses
`new Date('2026-03-01')` which parses as UTC midnight. `setDate()` operates in
local time. `toISOString()` outputs UTC.

In PST (UTC-8), the local date is Feb 28 (Saturday), so `baseDate.getDate()` returns
28 instead of 1. Combined with DST spring-forward on March 8, 2026:

- `i=7`: local Sat Mar 7 16:00 PST -> ISO `2026-03-08T00:00:00Z` -> date `2026-03-08`
- `i=8`: local Sun Mar 8 16:00 PDT -> ISO `2026-03-08T23:00:00Z` -> date `2026-03-08`

Both iterations produce ISO date `2026-03-08`. Although both are weekends and get
skipped by the current code, the local/UTC mismatch also causes:

1. Weekend filtering uses `getDay()` (local time) but dates use `toISOString()` (UTC),
   so candle dates can land on UTC weekends (e.g., local Friday = UTC Saturday).
2. The candle count varies by timezone (20 in PST, 21 in UTC, 21 in IST) because the
   starting day shifts.
3. In edge timezones or if the weekend-skip logic is slightly different, duplicate
   timestamps pass through to lightweight-charts, causing the crash.

`generateSentimentPoints()` has the identical pattern and identical vulnerability.

## Affected Files

| File | Role |
|------|------|
| `frontend/tests/e2e/helpers/mock-api-data.ts` | Contains both buggy functions |

## Affected Tests (6)

| Test File | Count | How Affected |
|-----------|-------|--------------|
| `chaos-cached-data.spec.ts` | 2 | Uses `mockTickerDataApis` -> chart crash |
| `chaos-cross-browser.spec.ts` | 1 | Uses `mockTickerDataApis` -> chart crash |
| `ticker-search-gaps.spec.ts` | 3 | Uses `mockTickerDataApis` -> chart crash |

## Requirements

### R1: No Duplicate Timestamps (Critical)
All candle dates and sentiment point dates MUST be unique within their respective arrays.
No two entries may share the same `date` string value.

### R2: Strictly Ascending Order
Date strings MUST be in strictly ascending chronological order. Each date must be later
than the previous.

### R3: Timezone Invariance
The output of `generateCandles(N)` and `generateSentimentPoints(N)` MUST be identical
regardless of the host machine's timezone. Running in UTC, PST, EST, IST, JST, or any
other timezone must produce byte-for-byte identical results.

### R4: Weekend Exclusion Correctness
Weekend filtering must use UTC day-of-week, not local day-of-week, to ensure candle
dates never land on UTC Saturdays or Sundays.

### R5: Preserve Existing Contracts
- Return type signatures must not change
- FR-009 null-volume and null-confidence/label behavior must be preserved
- FR-007 negative score coverage must be preserved
- FR-008 multiple sentiment sources must be preserved
- FR-012 empty response variants must not be affected
- The `mockTickerDataApis()` function signature and behavior must not change

### R6: Deterministic Count
`generateCandles(30)` must produce a deterministic number of candles (22 trading days
in the 30-calendar-day window starting March 2, 2026). The count must be the same in
every timezone.

## Success Criteria

### SC1: Tests pass in UTC
All 6 affected tests pass with `TZ=UTC`.

### SC2: Tests pass in PST
All 6 affected tests pass with `TZ=America/Los_Angeles`.

### SC3: Tests pass in EST
All 6 affected tests pass with `TZ=America/New_York`.

### SC4: Tests pass in IST
All 6 affected tests pass with `TZ=Asia/Kolkata`.

### SC5: No test regressions
No other E2E tests break as a result of this change.

### SC6: Identical output across timezones
`generateCandles(30)` produces the exact same array in all timezones listed above.

## Non-Goals

- Changing the base date (March 2026 is fine)
- Adding holiday exclusion (weekends only is sufficient for mock data)
- Changing the random price generation algorithm
- Modifying any test assertions

---

## Adversarial Review #1 (AR#1): Impact Analysis

### Q: Could the fix break other tests?

**No.** The change is confined to `mock-api-data.ts` which is only imported by:
- `chaos-cached-data.spec.ts`
- `chaos-cross-browser.spec.ts`
- `ticker-search-gaps.spec.ts`

No other test files import from `mock-api-data.ts`. The `MOCK_EMPTY_OHLC_RESPONSE` and
`MOCK_EMPTY_SENTIMENT_RESPONSE` exports use hardcoded empty arrays and are unaffected.

### Q: What if the candle count changes?

The current count varies by timezone (20 in PST, 21 in UTC/IST). The fix normalizes
to 22 (using March 2 Monday as base, counting 30 calendar days = 4 full weeks + 2 days,
yielding 4*5 + 2 = 22 weekdays).

**Test assertions checked:**
- `chaos-cached-data.spec.ts` line 33: `/[1-9]\d* price candles/` -- matches any count >= 1
- `chaos-cross-browser.spec.ts` line 51: `/[1-9]\d* price candles/` -- matches any count >= 1
- `ticker-search-gaps.spec.ts` line 137: `[aria-label*="candle"]` -- presence check only
- `MOCK_OHLC_RESPONSE.count` uses `CANDLES.length` dynamically -- auto-adjusts

**Verdict:** Count change from 20-21 to 22 breaks zero assertions.

### Q: What about `Math.random()` in price generation?

`Math.random()` is timezone-independent. The price values will differ between runs
regardless (not seeded), but that's existing behavior and no test asserts exact prices.

### Q: What about the `start_date` and `end_date` in mock responses?

These use `CANDLES[0]?.date` and `CANDLES[CANDLES.length - 1]?.date` with fallbacks.
After the fix, `start_date` will be `2026-03-02` (Monday) and `end_date` will be
`2026-03-31` (Tuesday). The fallback strings (`2026-03-01`, `2026-03-28`) are only used
if the array is empty, which won't happen with count=30.

No test asserts exact start/end dates. The assertions check for chart rendering, not
date values.

### Q: Does the `i === 0` / `i === 1` logic for FR-009 null variants still work?

Yes. With UTC math, `i=0` and `i=1` correspond to March 2 (Mon) and March 3 (Tue) --
both weekdays, not skipped. The null-volume candle (`i === 0`) and null-confidence
sentiment point (`i === 0`) will be generated correctly. The negative score (`i === 1`)
will also be generated correctly.

In the current PST code, `i=0` and `i=1` are weekends (Feb 28 Sat, Mar 1 Sun) and get
skipped, meaning FR-009 null variants are NOT being generated at all. The fix actually
RESTORES correct FR-009 behavior.
