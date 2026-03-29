# Research: Fix Mock OHLC/Sentiment Data Format

## Decision 1: Date Format Convention

**Decision**: Use ISO 8601 datetime strings with UTC `Z` suffix for intraday OHLC candles (e.g., `"2026-03-28T14:30:00Z"`), and `YYYY-MM-DD` strings for daily OHLC candles and all sentiment dates (e.g., `"2026-03-28"`).
**Rationale**: The backend Pydantic models serialize intraday candle dates as full ISO 8601 datetime with timezone. Daily candle dates and sentiment dates are date-only strings. Using `Z` (UTC) avoids timezone parsing ambiguity between Python's `datetime.isoformat()` and JavaScript's `Date()` constructor. FR-011 explicitly requires this.
**Alternatives considered**:
- Offset notation (`+00:00`) — valid ISO 8601 but `Z` is shorter and universally parsed by all JS Date implementations.
- Naive datetime without timezone — rejected because it creates timezone ambiguity; browser assumes local timezone, backend assumes UTC.
- Unix timestamps — rejected because the API contract uses string dates, not numeric timestamps.

## Decision 2: Enum Value Derivation

**Decision**: Enum values in mock data are derived from the backend Pydantic model definitions, not invented independently.
**Rationale**: FR-010 requires that mock enum values come from the API contract models. The known values are:
- OHLC `source`: `"tiingo"` | `"finnhub"` (from `OHLCResponse.source`)
- Sentiment `source`: `"tiingo"` | `"finnhub"` | `"our_model"` | `"aggregated"` (from `SentimentPoint.source`)
- Sentiment `label`: `"positive"` | `"neutral"` | `"negative"` (from `SentimentPoint.label`)
**Alternatives considered**:
- Hardcoded string literals without tracing to source — rejected because new enum values added to the backend would silently diverge from mocks.
- TypeScript string union types enforcing enum values — out of scope per spec, but would be a good follow-up for contract drift prevention.

## Decision 3: Empty Array Handling

**Decision**: Include one mock response variant per type (OHLC and sentiment) with an empty `candles`/`history` array, `count: 0`, and `start_date`/`end_date` set to the request's date range parameters.
**Rationale**: FR-012 requires explicit handling of empty responses. The edge case section in the spec calls out that `count` should be 0 and dates should still be valid. Setting dates to the request range (rather than null or empty string) matches production behavior where the API echoes back the requested range even when no data exists for it.
**Alternatives considered**:
- Null dates for empty responses — rejected because the backend always returns valid date strings even when no data matches the range.
- Omitting empty-response variants — rejected because this is an explicit edge case in the spec that exercises null-handling and empty-state rendering code paths.

## Decision 4: Nullable Field Coverage

**Decision**: Include at least one PriceCandle with `volume: null` and at least one SentimentPoint with both `confidence: null` and `label: null` in the mock data.
**Rationale**: FR-009 requires mock data to exercise null-handling code paths. The frontend must handle nullable fields gracefully (e.g., not rendering volume bars when volume is null, showing "N/A" for missing confidence). Having both null and non-null variants in the same response array exercises the mixed-data rendering path.
**Alternatives considered**:
- Separate mock responses for null vs non-null variants — rejected because production data frequently mixes null and non-null values within a single response array. The mock should reflect this reality.
- Using `undefined` instead of `null` — rejected because the JSON API returns explicit `null` for optional fields, and `undefined` has different semantics in TypeScript/JavaScript.

## Decision 5: Count Field Derivation

**Decision**: The `count` field in mock responses is set to the literal length of the `candles`/`history` array, not an independent value.
**Rationale**: FR-005 requires `count === array.length`. This is a production invariant — the backend computes `count` from the array length. Hardcoding a mismatched count would mask bugs in frontend code that relies on `count` for pagination or display.
**Alternatives considered**:
- Intentionally mismatched count for negative testing — out of scope per spec ("this spec fixes mock data shape, not error handling").

## Decision 6: cache_expires_at Format

**Decision**: Use ISO 8601 datetime with `Z` suffix for the `cache_expires_at` field in OHLCResponse (e.g., `"2026-03-28T15:00:00Z"`).
**Rationale**: This field is a datetime representing when the cached data expires. It follows the same UTC convention as intraday candle dates. The frontend may use this to display staleness indicators or decide whether to refetch.
**Alternatives considered**:
- Unix timestamp — rejected because the API contract serializes this as an ISO string.
- Relative TTL in seconds — rejected because the API provides an absolute expiry time.
