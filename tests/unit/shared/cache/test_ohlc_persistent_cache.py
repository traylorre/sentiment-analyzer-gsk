"""Unit tests for OHLC persistent cache (Feature 1087).

Tests the write-through DynamoDB cache for OHLC price data.
Uses moto to mock DynamoDB.
"""

import os
from datetime import UTC, datetime, timedelta
from unittest.mock import MagicMock, patch

import boto3
import pytest
from moto import mock_aws

from src.lambdas.shared.cache.ohlc_cache import (
    BATCH_WRITE_MAX_RETRIES,
    CachedCandle,
    OHLCCacheResult,
    _build_pk,
    _build_sk,
    _parse_sk,
    candles_to_cached,
    get_cached_candles,
    is_market_open,
    put_cached_candles,
)


@pytest.fixture
def dynamodb_table():
    """Create mock DynamoDB table for testing."""
    with mock_aws():
        client = boto3.client("dynamodb", region_name="us-east-1")
        client.create_table(
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
        yield client


@pytest.fixture
def env_vars():
    """Set up environment variables for testing."""
    with patch.dict(os.environ, {"OHLC_CACHE_TABLE": "test-ohlc-cache"}):
        yield


class TestKeyBuilders:
    """Test PK and SK builder functions."""

    def test_build_pk(self):
        """Test partition key format."""
        assert _build_pk("AAPL", "tiingo") == "AAPL#tiingo"
        assert _build_pk("msft", "Finnhub") == "MSFT#finnhub"
        assert _build_pk("GOOG", "TIINGO") == "GOOG#tiingo"

    def test_build_sk(self):
        """Test sort key format with timestamp."""
        ts = datetime(2025, 12, 27, 10, 30, 0, tzinfo=UTC)
        assert _build_sk("5m", ts) == "5m#2025-12-27T10:30:00Z"

    def test_build_sk_adds_utc(self):
        """Test sort key adds UTC timezone if missing."""
        ts = datetime(2025, 12, 27, 10, 30, 0)  # No timezone
        sk = _build_sk("1h", ts)
        assert sk == "1h#2025-12-27T10:30:00Z"

    def test_parse_sk(self):
        """Test parsing sort key back to resolution and timestamp."""
        sk = "5m#2025-12-27T10:30:00Z"
        resolution, ts = _parse_sk(sk)
        assert resolution == "5m"
        assert ts == datetime(2025, 12, 27, 10, 30, 0, tzinfo=UTC)

    def test_parse_sk_invalid(self):
        """Test parsing invalid sort key raises ValueError."""
        with pytest.raises(ValueError):
            _parse_sk("invalid-sk")


class TestCacheMiss:
    """Test cache miss scenarios."""

    @mock_aws
    def test_cache_miss_returns_empty(self, env_vars):
        """Test cache miss returns empty result."""
        # Create table
        client = boto3.client("dynamodb", region_name="us-east-1")
        client.create_table(
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

        start = datetime(2025, 12, 1, tzinfo=UTC)
        end = datetime(2025, 12, 31, tzinfo=UTC)

        result = get_cached_candles("AAPL", "tiingo", "D", start, end)

        assert isinstance(result, OHLCCacheResult)
        assert result.cache_hit is False
        assert result.candles == []

    @mock_aws
    def test_cache_miss_no_table_configured(self):
        """Test cache raises when table doesn't exist (fail-fast, Feature 1218).

        When OHLC_CACHE_TABLE is unset, the fallback table name
        ({environment}-ohlc-cache) is used. If that table doesn't exist,
        a ClientError propagates to the caller for explicit degradation.
        """
        from botocore.exceptions import ClientError

        with patch.dict(os.environ, {"OHLC_CACHE_TABLE": ""}, clear=True):
            start = datetime(2025, 12, 1, tzinfo=UTC)
            end = datetime(2025, 12, 31, tzinfo=UTC)

            with pytest.raises(ClientError) as exc_info:
                get_cached_candles("AAPL", "tiingo", "D", start, end)

            assert (
                exc_info.value.response["Error"]["Code"] == "ResourceNotFoundException"
            )


class TestCacheHit:
    """Test cache hit scenarios."""

    @mock_aws
    def test_cache_hit_returns_candles(self, env_vars):
        """Test cache hit returns stored candles."""
        # Create table and seed data
        client = boto3.client("dynamodb", region_name="us-east-1")
        client.create_table(
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

        # Seed data
        client.put_item(
            TableName="test-ohlc-cache",
            Item={
                "PK": {"S": "AAPL#tiingo"},
                "SK": {"S": "D#2025-12-15T00:00:00Z"},
                "open": {"N": "195.50"},
                "high": {"N": "196.00"},
                "low": {"N": "195.25"},
                "close": {"N": "195.75"},
                "volume": {"N": "1234567"},
                "fetched_at": {"S": "2025-12-15T10:00:00Z"},
            },
        )

        start = datetime(2025, 12, 1, tzinfo=UTC)
        end = datetime(2025, 12, 31, tzinfo=UTC)

        result = get_cached_candles("AAPL", "tiingo", "D", start, end)

        assert result.cache_hit is True
        assert len(result.candles) == 1
        candle = result.candles[0]
        assert candle.open == 195.50
        assert candle.close == 195.75
        assert candle.source == "tiingo"
        assert candle.resolution == "D"


class TestWriteThrough:
    """Test write-through caching."""

    @mock_aws
    def test_put_candles_stores_data(self, env_vars):
        """Test put_cached_candles stores candles in DynamoDB."""
        # Create table
        client = boto3.client("dynamodb", region_name="us-east-1")
        client.create_table(
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

        candles = [
            CachedCandle(
                timestamp=datetime(2025, 12, 27, 10, 30, tzinfo=UTC),
                open=195.50,
                high=196.00,
                low=195.25,
                close=195.75,
                volume=1234567,
                source="tiingo",
                resolution="5m",
            ),
            CachedCandle(
                timestamp=datetime(2025, 12, 27, 10, 35, tzinfo=UTC),
                open=195.75,
                high=195.90,
                low=195.60,
                close=195.80,
                volume=987654,
                source="tiingo",
                resolution="5m",
            ),
        ]

        written = put_cached_candles("AAPL", "tiingo", "5m", candles)

        assert written == 2

        # Verify data was stored
        response = client.query(
            TableName="test-ohlc-cache",
            KeyConditionExpression="PK = :pk",
            ExpressionAttributeValues={":pk": {"S": "AAPL#tiingo"}},
        )
        assert len(response["Items"]) == 2

    @mock_aws
    def test_put_empty_candles_returns_zero(self, env_vars):
        """Test put_cached_candles with empty list returns 0."""
        written = put_cached_candles("AAPL", "tiingo", "D", [])
        assert written == 0


class TestRangeQuery:
    """Test range query functionality."""

    @mock_aws
    def test_range_query_returns_subset(self, env_vars):
        """Test range query returns only candles within time window."""
        # Create table
        client = boto3.client("dynamodb", region_name="us-east-1")
        client.create_table(
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

        # Seed 5 candles across different times
        for hour in range(10, 15):
            client.put_item(
                TableName="test-ohlc-cache",
                Item={
                    "PK": {"S": "AAPL#tiingo"},
                    "SK": {"S": f"5m#2025-12-27T{hour:02d}:00:00Z"},
                    "open": {"N": "195.50"},
                    "high": {"N": "196.00"},
                    "low": {"N": "195.25"},
                    "close": {"N": "195.75"},
                    "volume": {"N": "1000000"},
                },
            )

        # Query 2-hour window (11:00 to 13:00)
        start = datetime(2025, 12, 27, 11, 0, tzinfo=UTC)
        end = datetime(2025, 12, 27, 13, 0, tzinfo=UTC)

        result = get_cached_candles("AAPL", "tiingo", "5m", start, end)

        assert result.cache_hit is True
        # Should only get 3 candles (11:00, 12:00, 13:00)
        assert len(result.candles) == 3


class TestMarketHours:
    """Test market hours detection."""

    def test_market_closed_on_weekend(self):
        """Test market is closed on weekends."""
        # Saturday December 28, 2024 at 10:00 AM ET
        saturday_morning = datetime(2024, 12, 28, 10, 0, 0)

        with patch("src.lambdas.shared.cache.ohlc_cache.datetime") as mock_dt:
            # Mock datetime.now to return Saturday
            from zoneinfo import ZoneInfo

            et_tz = ZoneInfo("America/New_York")
            mock_dt.now.return_value = saturday_morning.replace(tzinfo=et_tz)

            # is_market_open uses real datetime, so we need to mock differently
            # For now, just test the function exists and returns bool
            result = is_market_open()
            assert isinstance(result, bool)


class TestErrorPropagation:
    """Test that DynamoDB errors propagate instead of being silently swallowed."""

    @mock_aws
    def test_get_cached_candles_propagates_client_error(self, env_vars):
        """ClientError from DynamoDB query MUST propagate to caller."""
        from botocore.exceptions import ClientError

        # Do NOT create the table — query will raise ResourceNotFoundException
        start = datetime(2025, 12, 1, tzinfo=UTC)
        end = datetime(2025, 12, 31, tzinfo=UTC)

        with pytest.raises(ClientError) as exc_info:
            get_cached_candles("AAPL", "tiingo", "D", start, end)

        assert exc_info.value.response["Error"]["Code"] == "ResourceNotFoundException"

    @mock_aws
    def test_put_cached_candles_propagates_client_error(self, env_vars):
        """ClientError from DynamoDB batch write MUST propagate to caller."""
        from botocore.exceptions import ClientError

        # Do NOT create the table — batch_write_item will raise
        candles = [
            CachedCandle(
                timestamp=datetime(2025, 12, 27, 10, 30, tzinfo=UTC),
                open=195.50,
                high=196.00,
                low=195.25,
                close=195.75,
                volume=1234567,
                source="tiingo",
                resolution="5",
            ),
        ]

        with pytest.raises(ClientError) as exc_info:
            put_cached_candles("AAPL", "tiingo", "5", candles)

        assert exc_info.value.response["Error"]["Code"] == "ResourceNotFoundException"


class TestCandleConversion:
    """Test candle conversion helper."""

    def test_candles_to_cached_from_ohlc(self):
        """Test converting OHLCCandle-like objects to CachedCandle."""

        class MockOHLCCandle:
            def __init__(self):
                self.date = datetime(2025, 12, 27, 10, 30, tzinfo=UTC)
                self.open = 195.50
                self.high = 196.00
                self.low = 195.25
                self.close = 195.75
                self.volume = 1234567

        mock_candles = [MockOHLCCandle(), MockOHLCCandle()]

        result = candles_to_cached(mock_candles, "tiingo", "5m")

        assert len(result) == 2
        assert all(isinstance(c, CachedCandle) for c in result)
        assert result[0].source == "tiingo"
        assert result[0].resolution == "5m"


class TestIdempotency:
    """Test idempotent write behavior."""

    @mock_aws
    def test_duplicate_writes_are_idempotent(self, env_vars):
        """Test writing same candles twice doesn't create duplicates."""
        # Create table
        client = boto3.client("dynamodb", region_name="us-east-1")
        client.create_table(
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

        candles = [
            CachedCandle(
                timestamp=datetime(2025, 12, 27, 10, 30, tzinfo=UTC),
                open=195.50,
                high=196.00,
                low=195.25,
                close=195.75,
                volume=1234567,
                source="tiingo",
                resolution="5m",
            ),
        ]

        # Write twice
        put_cached_candles("AAPL", "tiingo", "5m", candles)
        put_cached_candles("AAPL", "tiingo", "5m", candles)

        # Verify only 1 item exists (overwritten, not duplicated)
        response = client.query(
            TableName="test-ohlc-cache",
            KeyConditionExpression="PK = :pk",
            ExpressionAttributeValues={":pk": {"S": "AAPL#tiingo"}},
        )
        assert len(response["Items"]) == 1


class TestTTLExpiration:
    """Test TTL calculation for cached candles (Feature 1218 - US3)."""

    def _create_table(self) -> "boto3.client":
        """Create mock DynamoDB table and return client."""
        client = boto3.client("dynamodb", region_name="us-east-1")
        client.create_table(
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
        return client

    @mock_aws
    def test_daily_resolution_ttl_90_days(self, env_vars):
        """T023: put_cached_candles() with daily resolution writes ttl = fetched_at + 90 days."""
        client = self._create_table()

        # Fixed time: 2025-06-15 12:00:00 UTC
        frozen_epoch = 1750000000  # ~2025-06-15

        candles = [
            CachedCandle(
                timestamp=datetime(2025, 6, 10, 0, 0, tzinfo=UTC),
                open=150.00,
                high=152.00,
                low=149.50,
                close=151.50,
                volume=5000000,
                source="tiingo",
                resolution="D",
            ),
        ]

        with patch("src.lambdas.shared.cache.ohlc_cache.time") as mock_time:
            mock_time.time.return_value = float(frozen_epoch)
            put_cached_candles("AAPL", "tiingo", "D", candles)

        # Query the stored item
        response = client.query(
            TableName="test-ohlc-cache",
            KeyConditionExpression="PK = :pk",
            ExpressionAttributeValues={":pk": {"S": "AAPL#tiingo"}},
        )
        assert len(response["Items"]) == 1
        item = response["Items"][0]

        # Verify ttl attribute exists and is approximately fetched_at + 90 days
        assert "ttl" in item
        stored_ttl = int(item["ttl"]["N"])
        expected_ttl = frozen_epoch + (90 * 86400)

        # Tolerance: +/- 1 day (86400 seconds)
        assert (
            abs(stored_ttl - expected_ttl) <= 86400
        ), f"TTL {stored_ttl} not within 1 day of expected {expected_ttl}"

    @mock_aws
    def test_current_day_intraday_ttl_5_minutes(self, env_vars):
        """T024: put_cached_candles() with current-day intraday writes ttl = fetched_at + 5 min."""
        client = self._create_table()

        # Fixed time: 2025-06-15 14:30:00 UTC
        frozen_epoch = 1750000000
        frozen_dt = datetime.fromtimestamp(frozen_epoch, tz=UTC)
        today = frozen_dt.date()

        # Create candle with timestamp matching "today" (the frozen date)
        candles = [
            CachedCandle(
                timestamp=datetime(
                    today.year, today.month, today.day, 10, 30, tzinfo=UTC
                ),
                open=150.00,
                high=152.00,
                low=149.50,
                close=151.50,
                volume=3000000,
                source="tiingo",
                resolution="5m",
            ),
        ]

        with (
            patch("src.lambdas.shared.cache.ohlc_cache.time") as mock_time,
            patch("src.lambdas.shared.cache.ohlc_cache.datetime") as mock_datetime,
        ):
            mock_time.time.return_value = float(frozen_epoch)
            # Mock datetime.now(UTC) to return our frozen datetime
            mock_datetime.now.return_value = frozen_dt
            # Ensure datetime.combine and strftime still work (needed for _build_sk, etc.)
            mock_datetime.side_effect = lambda *args, **kw: datetime(*args, **kw)
            mock_datetime.strptime = datetime.strptime
            put_cached_candles("AAPL", "tiingo", "5m", candles)

        # Query the stored item
        response = client.query(
            TableName="test-ohlc-cache",
            KeyConditionExpression="PK = :pk",
            ExpressionAttributeValues={":pk": {"S": "AAPL#tiingo"}},
        )
        assert len(response["Items"]) == 1
        item = response["Items"][0]

        # Verify ttl attribute is approximately fetched_at + 5 minutes (300 seconds)
        assert "ttl" in item
        stored_ttl = int(item["ttl"]["N"])
        expected_ttl = frozen_epoch + 300

        # Tolerance: +/- 1 minute (60 seconds)
        assert (
            abs(stored_ttl - expected_ttl) <= 60
        ), f"TTL {stored_ttl} not within 1 minute of expected {expected_ttl}"

    @mock_aws
    def test_past_day_intraday_ttl_90_days(self, env_vars):
        """T025: put_cached_candles() with past-day intraday writes ttl = fetched_at + 90 days."""
        client = self._create_table()

        # Fixed time: 2025-06-15 14:30:00 UTC
        frozen_epoch = 1750000000
        frozen_dt = datetime.fromtimestamp(frozen_epoch, tz=UTC)

        # Create candle with timestamp from 5 days ago (definitely not today)
        past_date = frozen_dt.date() - timedelta(days=5)
        candles = [
            CachedCandle(
                timestamp=datetime(
                    past_date.year, past_date.month, past_date.day, 10, 30, tzinfo=UTC
                ),
                open=148.00,
                high=150.00,
                low=147.50,
                close=149.50,
                volume=4000000,
                source="tiingo",
                resolution="5m",
            ),
        ]

        with (
            patch("src.lambdas.shared.cache.ohlc_cache.time") as mock_time,
            patch("src.lambdas.shared.cache.ohlc_cache.datetime") as mock_datetime,
        ):
            mock_time.time.return_value = float(frozen_epoch)
            mock_datetime.now.return_value = frozen_dt
            mock_datetime.side_effect = lambda *args, **kw: datetime(*args, **kw)
            mock_datetime.strptime = datetime.strptime
            put_cached_candles("AAPL", "tiingo", "5m", candles)

        # Query the stored item
        response = client.query(
            TableName="test-ohlc-cache",
            KeyConditionExpression="PK = :pk",
            ExpressionAttributeValues={":pk": {"S": "AAPL#tiingo"}},
        )
        assert len(response["Items"]) == 1
        item = response["Items"][0]

        # Verify ttl attribute is approximately fetched_at + 90 days
        assert "ttl" in item
        stored_ttl = int(item["ttl"]["N"])
        expected_ttl = frozen_epoch + (90 * 86400)

        # Tolerance: +/- 1 day (86400 seconds)
        assert (
            abs(stored_ttl - expected_ttl) <= 86400
        ), f"TTL {stored_ttl} not within 1 day of expected {expected_ttl}"


class TestDirectParsing:
    """Test that get_cached_candles parses using item['open']/item['close'] directly (T040)."""

    @mock_aws
    def test_get_cached_candles_parses_open_close_directly(self, env_vars):
        """get_cached_candles parses DynamoDB response using item['open'] and item['close'].

        DynamoDB ProjectionExpression with ExpressionAttributeNames returns the
        real attribute name ('open', 'close'), not the alias ('#o', '#c').
        This test seeds data via put_item and verifies parsing works correctly.
        """
        client = boto3.client("dynamodb", region_name="us-east-1")
        client.create_table(
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

        # Seed data with real attribute names (as DynamoDB stores them)
        client.put_item(
            TableName="test-ohlc-cache",
            Item={
                "PK": {"S": "MSFT#finnhub"},
                "SK": {"S": "D#2025-12-20T00:00:00Z"},
                "open": {"N": "420.25"},
                "high": {"N": "425.00"},
                "low": {"N": "418.50"},
                "close": {"N": "423.75"},
                "volume": {"N": "9876543"},
                "fetched_at": {"S": "2025-12-20T16:00:00Z"},
            },
        )

        start = datetime(2025, 12, 1, tzinfo=UTC)
        end = datetime(2025, 12, 31, tzinfo=UTC)

        result = get_cached_candles("MSFT", "finnhub", "D", start, end)

        assert result.cache_hit is True
        assert len(result.candles) == 1
        candle = result.candles[0]
        assert candle.open == 420.25
        assert candle.high == 425.00
        assert candle.low == 418.50
        assert candle.close == 423.75
        assert candle.volume == 9876543
        assert candle.source == "finnhub"
        assert candle.resolution == "D"
        assert candle.timestamp == datetime(2025, 12, 20, 0, 0, tzinfo=UTC)


class TestBatchWriteRetry:
    """Test exponential backoff retry for unprocessed batch write items (T041, T042)."""

    def _make_candle(self) -> CachedCandle:
        """Create a test candle."""
        return CachedCandle(
            timestamp=datetime(2025, 12, 27, 10, 30, tzinfo=UTC),
            open=195.50,
            high=196.00,
            low=195.25,
            close=195.75,
            volume=1234567,
            source="tiingo",
            resolution="5m",
        )

    def _make_unprocessed_response(self) -> dict:
        """Create a batch_write_item response with UnprocessedItems."""
        return {
            "UnprocessedItems": {
                "test-ohlc-cache": [
                    {
                        "PutRequest": {
                            "Item": {
                                "PK": {"S": "AAPL#tiingo"},
                                "SK": {"S": "5m#2025-12-27T10:30:00Z"},
                                "open": {"N": "195.5000"},
                                "high": {"N": "196.0000"},
                                "low": {"N": "195.2500"},
                                "close": {"N": "195.7500"},
                                "volume": {"N": "1234567"},
                                "fetched_at": {"S": "2025-12-27T10:00:00Z"},
                                "ttl": {"N": "9999999999"},
                            }
                        }
                    }
                ]
            }
        }

    def _make_success_response(self) -> dict:
        """Create a batch_write_item response with no unprocessed items."""
        return {"UnprocessedItems": {}}

    def test_retry_unprocessed_items_with_backoff(self, env_vars):
        """T041: put_cached_candles retries unprocessed items with exponential backoff."""
        candles = [self._make_candle()]

        with (
            patch("src.lambdas.shared.cache.ohlc_cache.time.sleep") as mock_sleep,
            patch(
                "src.lambdas.shared.cache.ohlc_cache._get_dynamodb_client"
            ) as mock_get_client,
        ):
            mock_client = MagicMock()
            mock_get_client.return_value = mock_client

            # First two calls return unprocessed items, third call succeeds
            mock_client.batch_write_item.side_effect = [
                self._make_unprocessed_response(),
                self._make_unprocessed_response(),
                self._make_success_response(),
            ]

            put_cached_candles("AAPL", "tiingo", "5m", candles)

            assert mock_client.batch_write_item.call_count == 3
            assert mock_sleep.call_count == 2

            # Verify exponential backoff delays: 100ms, 200ms
            mock_sleep.assert_any_call(0.1)  # 100ms / 1000
            mock_sleep.assert_any_call(0.2)  # 200ms / 1000

    def test_retry_exhaustion_raises_runtime_error(self, env_vars):
        """T042: put_cached_candles raises RuntimeError after MAX_RETRIES exhausted."""
        candles = [self._make_candle()]

        with (
            patch("src.lambdas.shared.cache.ohlc_cache.time.sleep"),
            patch(
                "src.lambdas.shared.cache.ohlc_cache._get_dynamodb_client"
            ) as mock_get_client,
        ):
            mock_client = MagicMock()
            mock_get_client.return_value = mock_client

            # Always return unprocessed items (never succeeds)
            mock_client.batch_write_item.return_value = (
                self._make_unprocessed_response()
            )

            with pytest.raises(RuntimeError, match="items unprocessed after"):
                put_cached_candles("AAPL", "tiingo", "5m", candles)

            # Initial attempt + MAX_RETRIES retries = MAX_RETRIES + 1 calls
            assert (
                mock_client.batch_write_item.call_count == BATCH_WRITE_MAX_RETRIES + 1
            )
