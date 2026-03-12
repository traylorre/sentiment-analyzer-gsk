# Fix: Cache Tests

**Parent:** [HL-cache-remediation-checklist.md](./HL-cache-remediation-checklist.md)
**Priority:** P4 (After all implementation fixes)
**Status:** [ ] TODO
**Depends On:** All previous fixes

---

## Overview

This document outlines the test strategy for validating the OHLC cache fixes. Tests are organized by:
1. **Unit tests** - Mock DynamoDB, test individual functions
2. **Integration tests** - Use moto, test full request flow
3. **E2E tests** - Playwright, test user-facing behavior

---

## Unit Tests

### 1. Cache Key Tests

```python
# tests/unit/dashboard/test_ohlc_cache_key.py

import pytest
from datetime import date
from src.lambdas.dashboard.ohlc import _get_ohlc_cache_key


class TestCacheKey:
    """Test cache key generation."""

    def test_predefined_range_includes_end_date(self):
        """Predefined ranges include end_date for day-anchoring."""
        key = _get_ohlc_cache_key(
            ticker="AAPL",
            resolution="D",
            time_range="1M",
            start_date=date(2025, 11, 23),
            end_date=date(2025, 12, 23),
        )
        assert key == "ohlc:AAPL:D:1M:2025-12-23"

    def test_different_days_different_keys(self):
        """Same range on different days produces different keys."""
        key1 = _get_ohlc_cache_key("AAPL", "D", "1W", date(2025, 12, 16), date(2025, 12, 23))
        key2 = _get_ohlc_cache_key("AAPL", "D", "1W", date(2025, 12, 22), date(2025, 12, 29))
        assert key1 != key2

    def test_custom_range_includes_both_dates(self):
        """Custom ranges include both start and end dates."""
        key = _get_ohlc_cache_key(
            ticker="AAPL",
            resolution="D",
            time_range="custom",
            start_date=date(2025, 1, 1),
            end_date=date(2025, 6, 30),
        )
        assert key == "ohlc:AAPL:D:custom:2025-01-01:2025-06-30"

    def test_ticker_normalized_to_uppercase(self):
        """Ticker is normalized to uppercase."""
        key = _get_ohlc_cache_key("aapl", "D", "1M", date(2025, 11, 23), date(2025, 12, 23))
        assert "AAPL" in key
        assert "aapl" not in key

    def test_different_resolutions_different_keys(self):
        """Different resolutions produce different keys."""
        key_daily = _get_ohlc_cache_key("AAPL", "D", "1M", date(2025, 11, 23), date(2025, 12, 23))
        key_5min = _get_ohlc_cache_key("AAPL", "5", "1M", date(2025, 11, 23), date(2025, 12, 23))
        assert key_daily != key_5min
```

### 2. Write-Through Tests

```python
# tests/unit/dashboard/test_ohlc_write_through.py

import pytest
from unittest.mock import patch, MagicMock
from src.lambdas.dashboard.ohlc import _write_through_to_dynamodb


class TestWriteThrough:
    """Test DynamoDB write-through behavior."""

    @patch("src.lambdas.dashboard.ohlc.put_cached_candles")
    @patch("src.lambdas.dashboard.ohlc.candles_to_cached")
    def test_writes_candles_to_dynamodb(self, mock_convert, mock_put):
        """Successful fetch writes candles to DynamoDB."""
        mock_candles = [MagicMock()] * 10
        mock_convert.return_value = mock_candles
        mock_put.return_value = 10

        _write_through_to_dynamodb(
            ticker="AAPL",
            source="tiingo",
            resolution="D",
            ohlc_candles=mock_candles,
        )

        mock_convert.assert_called_once()
        mock_put.assert_called_once_with(
            ticker="AAPL",
            source="tiingo",
            resolution="D",
            candles=mock_candles,
        )

    @patch("src.lambdas.dashboard.ohlc.put_cached_candles")
    @patch("src.lambdas.dashboard.ohlc.candles_to_cached")
    def test_empty_candles_skips_write(self, mock_convert, mock_put):
        """Empty candle list skips DynamoDB write."""
        mock_convert.return_value = []

        _write_through_to_dynamodb(
            ticker="AAPL",
            source="tiingo",
            resolution="D",
            ohlc_candles=[],
        )

        mock_put.assert_not_called()

    @patch("src.lambdas.dashboard.ohlc.put_cached_candles")
    @patch("src.lambdas.dashboard.ohlc.candles_to_cached")
    def test_write_failure_does_not_raise(self, mock_convert, mock_put):
        """Write failure logs but doesn't raise exception."""
        mock_convert.return_value = [MagicMock()]
        mock_put.side_effect = Exception("DynamoDB error")

        # Should not raise
        _write_through_to_dynamodb(
            ticker="AAPL",
            source="tiingo",
            resolution="D",
            ohlc_candles=[MagicMock()],
        )

    @patch("src.lambdas.dashboard.ohlc.put_cached_candles")
    @patch("src.lambdas.dashboard.ohlc.candles_to_cached")
    def test_logs_write_count(self, mock_convert, mock_put, caplog):
        """Successful write logs candle count."""
        mock_convert.return_value = [MagicMock()] * 25
        mock_put.return_value = 25

        _write_through_to_dynamodb("AAPL", "tiingo", "D", [MagicMock()] * 25)

        assert "candles_written" in caplog.text or "25" in caplog.text
```

### 3. Read-From-DynamoDB Tests

```python
# tests/unit/dashboard/test_ohlc_read_dynamodb.py

import pytest
from datetime import date, datetime, UTC
from unittest.mock import patch, MagicMock
from src.lambdas.dashboard.ohlc import _read_from_dynamodb
from src.lambdas.shared.models import OHLCResolution


class TestReadFromDynamoDB:
    """Test DynamoDB cache read behavior."""

    @patch("src.lambdas.dashboard.ohlc.get_cached_candles")
    def test_returns_candles_on_cache_hit(self, mock_get):
        """Cache hit returns converted candles."""
        mock_cached = MagicMock()
        mock_cached.timestamp = datetime(2025, 12, 23, tzinfo=UTC)
        mock_cached.open = 150.0
        mock_cached.high = 152.0
        mock_cached.low = 149.0
        mock_cached.close = 151.0
        mock_cached.volume = 1000000

        mock_result = MagicMock()
        mock_result.cache_hit = True
        mock_result.candles = [mock_cached] * 20  # ~80% of expected
        mock_get.return_value = mock_result

        result = _read_from_dynamodb(
            ticker="AAPL",
            source="tiingo",
            resolution=OHLCResolution.DAILY,
            start_date=date(2025, 11, 23),
            end_date=date(2025, 12, 23),
        )

        assert result is not None
        assert len(result) == 20

    @patch("src.lambdas.dashboard.ohlc.get_cached_candles")
    def test_returns_none_on_cache_miss(self, mock_get):
        """Cache miss returns None."""
        mock_result = MagicMock()
        mock_result.cache_hit = False
        mock_result.candles = []
        mock_get.return_value = mock_result

        result = _read_from_dynamodb(
            ticker="AAPL",
            source="tiingo",
            resolution=OHLCResolution.DAILY,
            start_date=date(2025, 11, 23),
            end_date=date(2025, 12, 23),
        )

        assert result is None

    @patch("src.lambdas.dashboard.ohlc.get_cached_candles")
    def test_returns_none_on_partial_hit(self, mock_get):
        """Partial hit (<80% coverage) returns None."""
        mock_cached = MagicMock()
        mock_cached.timestamp = datetime(2025, 12, 23, tzinfo=UTC)
        mock_cached.open = 150.0
        mock_cached.high = 152.0
        mock_cached.low = 149.0
        mock_cached.close = 151.0
        mock_cached.volume = 1000000

        mock_result = MagicMock()
        mock_result.cache_hit = True
        mock_result.candles = [mock_cached] * 5  # Only 5 candles, expected ~22
        mock_get.return_value = mock_result

        result = _read_from_dynamodb(
            ticker="AAPL",
            source="tiingo",
            resolution=OHLCResolution.DAILY,
            start_date=date(2025, 11, 23),
            end_date=date(2025, 12, 23),
        )

        assert result is None  # Treated as miss due to low coverage

    @patch("src.lambdas.dashboard.ohlc.get_cached_candles")
    def test_returns_none_on_query_failure(self, mock_get):
        """Query failure returns None (graceful degradation)."""
        mock_get.side_effect = Exception("DynamoDB error")

        result = _read_from_dynamodb(
            ticker="AAPL",
            source="tiingo",
            resolution=OHLCResolution.DAILY,
            start_date=date(2025, 11, 23),
            end_date=date(2025, 12, 23),
        )

        assert result is None
```

### 4. PriceCandle Converter Tests

```python
# tests/unit/shared/models/test_price_candle.py

import pytest
from datetime import datetime, UTC
from src.lambdas.shared.models import PriceCandle, OHLCResolution
from src.lambdas.shared.cache.ohlc_cache import CachedCandle


class TestPriceCandleFromCached:
    """Test PriceCandle.from_cached_candle() converter."""

    def test_converts_daily_candle(self):
        """Daily candle converts timestamp to date."""
        cached = CachedCandle(
            timestamp=datetime(2025, 12, 23, 14, 30, 0, tzinfo=UTC),
            open=150.0,
            high=152.0,
            low=149.0,
            close=151.0,
            volume=1000000,
            source="tiingo",
            resolution="D",
        )

        result = PriceCandle.from_cached_candle(cached, OHLCResolution.DAILY)

        assert result.date == datetime(2025, 12, 23, 14, 30, 0, tzinfo=UTC).date()
        assert result.open == 150.0
        assert result.close == 151.0

    def test_converts_intraday_candle(self):
        """Intraday candle preserves full timestamp."""
        cached = CachedCandle(
            timestamp=datetime(2025, 12, 23, 14, 30, 0, tzinfo=UTC),
            open=150.0,
            high=152.0,
            low=149.0,
            close=151.0,
            volume=1000000,
            source="tiingo",
            resolution="5",
        )

        result = PriceCandle.from_cached_candle(cached, OHLCResolution.FIVE_MINUTES)

        assert result.date == datetime(2025, 12, 23, 14, 30, 0, tzinfo=UTC)

    def test_handles_zero_volume(self):
        """Zero volume is preserved."""
        cached = CachedCandle(
            timestamp=datetime(2025, 12, 23, tzinfo=UTC),
            open=150.0,
            high=152.0,
            low=149.0,
            close=151.0,
            volume=0,
            source="tiingo",
            resolution="D",
        )

        result = PriceCandle.from_cached_candle(cached, OHLCResolution.DAILY)

        assert result.volume == 0


class TestDataConsistency:
    """Test data consistency between cache and API (Blind Spot #21)."""

    def test_round_trip_preserves_data(self):
        """Data survives OHLCCandle → CachedCandle → PriceCandle round-trip."""
        from src.lambdas.shared.adapters.base import OHLCCandle
        from src.lambdas.shared.cache.ohlc_cache import candles_to_cached

        # Original from API
        original = OHLCCandle(
            date=datetime(2025, 12, 23, 14, 30, 0, tzinfo=UTC),
            open=150.1234,
            high=152.5678,
            low=149.0001,
            close=151.9999,
            volume=12345678,
        )

        # Convert to cache format
        cached_list = candles_to_cached([original], "tiingo", "D")
        assert len(cached_list) == 1
        cached = cached_list[0]

        # Convert back to PriceCandle
        result = PriceCandle.from_cached_candle(cached, OHLCResolution.DAILY)

        # Verify data preserved (within DynamoDB decimal precision)
        assert abs(result.open - original.open) < 0.0001
        assert abs(result.high - original.high) < 0.0001
        assert abs(result.low - original.low) < 0.0001
        assert abs(result.close - original.close) < 0.0001
        assert result.volume == original.volume
```

---

## Integration Tests

### Full Request Flow with Moto

```python
# tests/integration/test_ohlc_cache_flow.py

import pytest
from datetime import date
from unittest.mock import patch
import boto3
from moto import mock_aws
from src.lambdas.dashboard.handler import lambda_handler


@pytest.fixture
def dynamodb_table():
    """Create mock OHLC cache table."""
    with mock_aws():
        dynamodb = boto3.resource("dynamodb", region_name="us-east-1")
        dynamodb.create_table(
            TableName="test-ohlc-cache",
            KeySchema=[
                {"AttributeName": "PK", "KeyType": "HASH"},
                {"AttributeName": "SK", "KeyType": "RANGE"},
            ],
            AttributeDefinitions=[
                {"AttributeName": "PK", "AttributeType": "S"},
                {"AttributeName": "SK", "AttributeType": "S"},
            ],
            BillingMode="PAY_PER_REQUEST",
        )
        yield dynamodb


@pytest.fixture
def mock_lambda_context():
    """Create mock Lambda context for handler invocation."""
    from unittest.mock import MagicMock
    context = MagicMock()
    context.function_name = "test-function"
    context.memory_limit_in_mb = 256
    context.invoked_function_arn = "arn:aws:lambda:us-east-1:123456789012:function:test-function"
    context.aws_request_id = "test-request-id"
    return context


class TestOHLCCacheFlow:
    """Integration tests for full OHLC cache flow."""

    @patch("src.lambdas.dashboard.ohlc.get_tiingo_adapter")
    def test_first_request_populates_dynamodb(self, mock_tiingo, test_client, dynamodb_table):
        """First request fetches from Tiingo and writes to DynamoDB."""
        # Setup mock Tiingo response
        mock_adapter = mock_tiingo.return_value
        mock_adapter.get_ohlc.return_value = [
            MagicMock(date=date(2025, 12, 23), open=150, high=152, low=149, close=151, volume=1000000)
        ]

        # Make request
        response = test_client.get(
            "/api/v2/tickers/AAPL/ohlc?range=1M&resolution=D",
            headers={"Authorization": "Bearer test-token"},
        )

        assert response.status_code == 200

        # Verify DynamoDB was written
        table = dynamodb_table.Table("test-ohlc-cache")
        items = table.scan()["Items"]
        assert len(items) > 0
        assert items[0]["PK"] == "AAPL#tiingo"

    @patch("src.lambdas.dashboard.ohlc.get_tiingo_adapter")
    def test_second_request_reads_from_dynamodb(self, mock_tiingo, test_client, dynamodb_table):
        """Second request reads from DynamoDB, not Tiingo."""
        # Pre-populate DynamoDB
        table = dynamodb_table.Table("test-ohlc-cache")
        table.put_item(Item={
            "PK": "AAPL#tiingo",
            "SK": "D#2025-12-23T00:00:00Z",
            "open": "150.0000",
            "high": "152.0000",
            "low": "149.0000",
            "close": "151.0000",
            "volume": "1000000",
            "fetched_at": "2025-12-23T16:00:00Z",
        })

        # Make request
        response = test_client.get(
            "/api/v2/tickers/AAPL/ohlc?range=1W&resolution=D",
            headers={"Authorization": "Bearer test-token"},
        )

        assert response.status_code == 200

        # Verify Tiingo was NOT called
        mock_tiingo.return_value.get_ohlc.assert_not_called()
```

---

## E2E Tests (Playwright)

### Test Cache Behavior in UI

```typescript
// frontend/tests/e2e/ohlc-cache.spec.ts

import { test, expect } from '@playwright/test';

test.describe('OHLC Cache Behavior', () => {
  test('chart loads data on first visit', async ({ page }) => {
    await page.goto('/');

    // Search and select ticker
    await page.getByRole('searchbox').fill('AAPL');
    await page.getByRole('option', { name: /AAPL/i }).click();

    // Wait for chart to load
    await expect(page.locator('canvas')).toBeVisible();

    // Verify price data is displayed (not "No data")
    await expect(page.getByText(/No price data/i)).not.toBeVisible();
  });

  test('chart loads quickly on repeat visit (cache hit)', async ({ page }) => {
    // First visit to populate cache
    await page.goto('/');
    await page.getByRole('searchbox').fill('GOOG');
    await page.getByRole('option', { name: /GOOG/i }).click();
    await expect(page.locator('canvas')).toBeVisible();

    // Navigate away
    await page.goto('/settings');

    // Come back - should be fast (cache hit)
    const startTime = Date.now();
    await page.goto('/');
    await page.getByRole('searchbox').fill('GOOG');
    await page.getByRole('option', { name: /GOOG/i }).click();
    await expect(page.locator('canvas')).toBeVisible();
    const loadTime = Date.now() - startTime;

    // Cache hit should be fast (under 2 seconds)
    expect(loadTime).toBeLessThan(2000);
  });

  test('time range change loads without API error', async ({ page }) => {
    await page.goto('/');
    await page.getByRole('searchbox').fill('MSFT');
    await page.getByRole('option', { name: /MSFT/i }).click();
    await expect(page.locator('canvas')).toBeVisible();

    // Change time range
    await page.getByRole('button', { name: '1W' }).click();
    await expect(page.locator('canvas')).toBeVisible();

    await page.getByRole('button', { name: '3M' }).click();
    await expect(page.locator('canvas')).toBeVisible();

    // No error messages should appear
    await expect(page.getByText(/error/i)).not.toBeVisible();
  });
});
```

---

## Test Coverage Goals

| Component | Target Coverage | Current |
|-----------|-----------------|---------|
| `_get_ohlc_cache_key()` | 100% | 0% |
| `_write_through_to_dynamodb()` | 90% | 0% |
| `_read_from_dynamodb()` | 90% | 0% |
| `PriceCandle.from_cached_candle()` | 100% | 0% |
| Integration flow | 80% | 0% |

---

## Running Tests

```bash
# Unit tests
pytest tests/unit/dashboard/test_ohlc_cache_key.py -v
pytest tests/unit/dashboard/test_ohlc_write_through.py -v
pytest tests/unit/dashboard/test_ohlc_read_dynamodb.py -v
pytest tests/unit/shared/models/test_price_candle.py -v

# Integration tests
pytest tests/integration/test_ohlc_cache_flow.py -v

# E2E tests
cd frontend && npx playwright test ohlc-cache.spec.ts --project="Desktop Chrome"

# All cache-related tests
pytest tests/ -v -k "ohlc" -k "cache"
```

---

## Related

- [HL-cache-remediation-checklist.md](./HL-cache-remediation-checklist.md) - Parent checklist
- All implementation fix documents
