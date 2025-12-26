# Implementation Tasks: OHLC Intraday Resolution Support

**Feature**: 1055-ohlc-resolution-selector
**Created**: 2025-12-26
**Spec**: [spec.md](./spec.md) | **Plan**: [plan.md](./plan.md)

## Dependencies

```
T001 (setup) → T002 (adapter) → T003, T004 (handler, tests can run in parallel)
```

## Phase 1: Setup

- [X] T001 Verify Tiingo IEX endpoint works with current API key (already verified via testing)

## Phase 2: Core Implementation

- [X] T002 Add `get_intraday_ohlc()` method to TiingoAdapter in `src/lambdas/shared/adapters/tiingo.py`
  - Endpoint: `https://api.tiingo.com/iex/{ticker}/prices`
  - Parameters: `startDate`, `resampleFreq`, `token`
  - Resolution mapping: '1'→'1min', '5'→'5min', '15'→'15min', '30'→'30min', '60'→'1hour'
  - Use 5-minute cache TTL (intraday data changes frequently)
  - Parse IEX response format to OHLCCandle

- [X] T003 Update OHLC handler to use Tiingo for intraday in `src/lambdas/dashboard/ohlc.py`
  - For resolutions 1, 5, 15, 30, 60: Call `tiingo.get_intraday_ohlc()`
  - For resolution D: Keep existing `tiingo.get_ohlc()` call
  - Remove Finnhub fallback for intraday (Finnhub 403s on free tier)
  - Set source="tiingo" for all responses

## Phase 3: Tests

- [X] T004 [P] Add unit tests for `get_intraday_ohlc()` in `tests/unit/shared/adapters/test_tiingo.py`
  - Test successful intraday data fetch
  - Test resolution mapping (all 5 intraday resolutions)
  - Test empty response handling
  - Test error handling (network, API errors)
  - Test caching behavior

## Phase 4: Validation

- [X] T005 Run existing OHLC tests to ensure no regressions (199 dashboard tests, 25 Tiingo adapter tests pass)
- [ ] T006 Test manually: curl OHLC endpoint with resolution=5 and verify intraday candles returned

## Parallel Execution

- T003 and T004 can run in parallel after T002 completes
- T005 and T006 can run in parallel after T003 completes

## Implementation Notes

### Resolution Mapping (T002)

```python
RESOLUTION_TO_TIINGO = {
    '1': '1min',
    '5': '5min',
    '15': '15min',
    '30': '30min',
    '60': '1hour',
}
```

### IEX Response Format (T002)

```json
[
  {
    "date": "2025-12-22T14:30:00.000Z",
    "open": 272.86,
    "high": 273.915,
    "low": 272.72,
    "close": 273.43
  }
]
```

### Cache TTL (T002)

Use 5-minute TTL for intraday data (more frequent updates than daily data which uses 1-hour TTL).
