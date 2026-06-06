# Feature 1333: Implementation Plan

## Approach Selection

### Option A: Date.UTC() + millisecond arithmetic (RECOMMENDED)

```typescript
const baseMs = Date.UTC(2026, 2, 2); // March 2, 2026 (Monday) UTC
const DAY_MS = 86_400_000;

for (let i = 0; i < count; i++) {
  const ms = baseMs + i * DAY_MS;
  const d = new Date(ms);
  const dow = d.getUTCDay();
  if (dow === 0 || dow === 6) continue;
  const dateStr = d.toISOString().split('T')[0];
  // ...
}
```

**Pros:**
- Uses built-in `Date.UTC()` -- no string manipulation for date creation
- `getUTCDay()` and `toISOString()` both operate in UTC -- no local/UTC mismatch
- Millisecond addition is DST-proof (86400000ms is always exactly one day in UTC)
- Simple, readable, minimal diff

**Cons:**
- Still uses Date objects (but UTC-only, so no timezone ambiguity)

### Option B: Pure arithmetic string generation

```typescript
const dateStr = `2026-03-${String(day).padStart(2, '0')}`;
```

**Pros:**
- Zero Date objects, zero timezone risk

**Cons:**
- Must handle month rollover manually (March has 31 days, so count=30 stays in March)
- Weekend detection requires Zeller's congruence or a lookup table
- More code, more error-prone, harder to read
- If count ever exceeds 30, month arithmetic gets complex

### Decision: Option A

Option A is simpler, more maintainable, and equally timezone-safe. The UTC family of
methods (`Date.UTC`, `getUTCDay`, `toISOString`) forms a closed system with no local
timezone leakage.

## Change Scope

**Single file:** `frontend/tests/e2e/helpers/mock-api-data.ts`

**Two functions to modify:**
1. `generateCandles()` (lines 28-63)
2. `generateSentimentPoints()` (lines 70-110)

**Changes per function:**
1. Replace `new Date('2026-03-01')` with `Date.UTC(2026, 2, 2)` (March 2 Monday)
2. Replace `new Date(baseDate)` + `setDate()` with `baseMs + i * DAY_MS`
3. Replace `date.getDay()` with `d.getUTCDay()`
4. Keep `d.toISOString().split('T')[0]` (already UTC)

**No other files change.**

## Risk Assessment

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| Count change breaks assertion | Low | Low | All assertions use regex/presence, not exact counts |
| Base date change breaks assertion | None | None | No test asserts exact dates |
| FR-009 null variant index shift | None | None | i=0 and i=1 are weekdays in new code |
| Random price values change | Certain | None | No test asserts exact prices |

## Verification Plan

1. Run `TZ=UTC npx playwright test` on affected 6 tests
2. Run `TZ=America/Los_Angeles npx playwright test` on affected 6 tests
3. Run full E2E suite to check for regressions
4. Manually verify output determinism with Node one-liner across timezones

---

## Adversarial Review #2 (AR#2): Cross-Check

### Q: Is March 2, 2026 actually a Monday?

Verified: `new Date(Date.UTC(2026, 2, 2)).getUTCDay()` returns 1 (Monday). Confirmed.

### Q: Does Date.UTC(2026, 2, 2) do what we think?

`Date.UTC(year, monthIndex, day)` -- monthIndex is 0-based, so 2 = March.
Returns milliseconds since epoch for 2026-03-02T00:00:00.000Z. Confirmed.

### Q: Is 86_400_000 exactly one UTC day?

Yes. UTC has no DST. Leap seconds are not reflected in JavaScript Date (it uses POSIX
time which ignores leap seconds). 86400 * 1000 = 86_400_000ms = 1 UTC day. Confirmed.

### Q: Could `toISOString().split('T')[0]` ever produce a different date than expected?

No. `toISOString()` always outputs in UTC (the Z suffix). Since we construct the Date
from UTC milliseconds, the split always yields the expected YYYY-MM-DD. Confirmed.

### Q: What about the `MOCK_OHLC_RESPONSE` and `MOCK_SENTIMENT_RESPONSE` wrappers?

They reference `CANDLES[0]?.date`, `CANDLES[CANDLES.length-1]?.date`, and
`CANDLES.length` -- all dynamically computed. They auto-adjust. No change needed.

### Q: What about `MOCK_EMPTY_OHLC_RESPONSE` and `MOCK_EMPTY_SENTIMENT_RESPONSE`?

These use hardcoded empty arrays and hardcoded date strings. They are separate exports
and not affected by this change at all.

### Q: Does the plan address generateSentimentPoints too?

Yes. Same pattern, same fix. Both functions are listed in the change scope.

### Q: Is there any risk of the base date being significant for other reasons?

The mock data simulates AAPL prices starting at $178.50. The exact dates don't matter --
they just need to be unique, ascending, and weekday-only. March 2 Monday is a clean
starting point.

### Drift check: Does spec.md align with plan.md?

- Spec R1 (no duplicates) -> UTC arithmetic guarantees uniqueness. Aligned.
- Spec R2 (ascending) -> Sequential i * DAY_MS guarantees ascending. Aligned.
- Spec R3 (timezone invariance) -> All-UTC operations guarantee invariance. Aligned.
- Spec R4 (weekend exclusion) -> `getUTCDay()` checks UTC weekday. Aligned.
- Spec R5 (preserve contracts) -> No signature or export changes. Aligned.
- Spec R6 (deterministic count) -> 22 candles in every timezone. Aligned.

No drift detected.
