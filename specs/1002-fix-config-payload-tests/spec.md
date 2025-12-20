# Spec 1002: Fix CONFIG_UNAVAILABLE Test Skips

## Problem Statement

19 E2E tests are skipped with "Config creation not available" because they use incorrect payload format for POST /api/v2/configurations.

**Root Cause**: Tests pass `"tickers": [{"symbol": "AAPL"}]` but API expects `"tickers": ["AAPL"]`.

## Evidence

API Schema (`src/lambdas/shared/models/configuration.py:ConfigurationCreate`):
```python
tickers: list[str] = Field(..., max_length=5)  # list of strings
```

Working tests use:
```python
synthetic_config.to_api_payload()  # Returns {"name": "...", "tickers": ["AAPL", "MSFT", "GOOGL"]}
```

Failing tests use:
```python
"tickers": [{"symbol": "AAPL"}]  # Wrong: list of dicts
```

## Fix

Update all 19 occurrences to use string list format:
- Change `[{"symbol": "AAPL"}]` to `["AAPL"]`

## Files to Update

| File | Line Numbers | Fix |
|------|--------------|-----|
| tests/e2e/test_anonymous_restrictions.py | 127, 174, 224, 332 | Change ticker format |

## Testing

After fix:
- Run `pytest tests/e2e/test_anonymous_restrictions.py -v --tb=short`
- Verify skipped tests now run (may pass or fail based on actual API behavior)

## Impact

Reduces E2E skip count from 61 to ~57 (4 of 19 CONFIG_UNAVAILABLE skips are in this file).
