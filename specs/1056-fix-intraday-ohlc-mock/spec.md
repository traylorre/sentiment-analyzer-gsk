# Feature 1056: Fix Intraday OHLC 500 Error

## Problem Statement

The OHLC endpoint returns 500 Internal Server Error for intraday resolutions (1, 5, 15, 30, 60 min) while daily (D) resolution works correctly.

## Root Cause Analysis

1. **MockTiingoAdapter Missing Method**: The `MockTiingoAdapter` class extends `TiingoAdapter` but does not override `get_intraday_ohlc()`. When called, it falls through to the parent class method which tries to use `self.api_key` - a property never set in the mock.

2. **Integration Test Gap**: Integration tests only test daily resolution, not intraday. This allowed the bug to slip through.

3. **Production Impact**: When `tiingo.get_intraday_ohlc()` is called in production, an AttributeError is raised, causing 500 error.

## Solution

### S1: Add get_intraday_ohlc to MockTiingoAdapter

Add a mock implementation that returns synthetic intraday candle data, consistent with the existing `get_ohlc` pattern.

### S2: Add Integration Tests for Intraday Resolutions

Add parameterized tests covering all intraday resolutions (1, 5, 15, 30, 60 min) to prevent regression.

## Requirements

| ID | Requirement | Priority |
|----|-------------|----------|
| R1 | MockTiingoAdapter.get_intraday_ohlc returns synthetic candles | P0 |
| R2 | Integration tests cover all intraday resolutions | P0 |
| R3 | Intraday endpoint returns valid data in production | P0 |

## Success Criteria

- [ ] All intraday resolutions (1, 5, 15, 30, 60 min) return valid OHLC data
- [ ] No 500 errors when switching resolution buttons in UI
- [ ] All unit and integration tests pass

## Related

- Feature 1055: Use Tiingo IEX for intraday resolutions
- File: `tests/fixtures/mocks/mock_tiingo.py`
- File: `tests/integration/ohlc/test_happy_path.py`
