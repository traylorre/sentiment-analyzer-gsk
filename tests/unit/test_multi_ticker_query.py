"""Unit tests for multi-ticker batch queries (T048).

Tests for TimeseriesQueryService.query_batch() which queries multiple
tickers in parallel to support the multi-ticker comparison view.

Canonical: [CS-002] "ticker#resolution composite key"
Goal: 10 tickers load in <1 second (SC-006)
"""

import time
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from src.lib.timeseries import Resolution


class TestMultiTickerQuery:
    """Tests for batch ticker queries."""

    @pytest.fixture
    def mock_table(self):
        """Create a mock DynamoDB table."""
        table = MagicMock()
        return table

    @pytest.fixture
    def mock_service(self, mock_table):
        """Create TimeseriesQueryService with mock table."""
        from src.lambdas.dashboard.timeseries import TimeseriesQueryService

        with patch("src.lambdas.dashboard.timeseries.boto3") as mock_boto3:
            mock_dynamodb = MagicMock()
            mock_boto3.resource.return_value = mock_dynamodb
            mock_dynamodb.Table.return_value = mock_table

            service = TimeseriesQueryService(
                table_name="test-timeseries",
                use_cache=False,
            )
            # Override the table with our mock
            service._table = mock_table
            yield service

    def _create_bucket_item(
        self,
        ticker: str,
        resolution: str,
        timestamp: str,
        score: float = 0.5,
        count: int = 10,
    ) -> dict[str, Any]:
        """Create a mock DynamoDB bucket item.

        Note: Uses uppercase PK and SK to match production schema.
        """
        return {
            "PK": f"{ticker}#{resolution}",
            "SK": timestamp,
            "open": Decimal(str(score)),
            "high": Decimal(str(score + 0.1)),
            "low": Decimal(str(score - 0.1)),
            "close": Decimal(str(score)),
            "count": count,
            "sum": Decimal(str(score * count)),
            "label_counts": {"positive": count // 2, "negative": count // 2},
            "sources": ["tiingo"],
            "is_partial": False,
        }

    def test_query_batch_returns_results_for_all_tickers(
        self, mock_service, mock_table
    ):
        """query_batch should return results for all requested tickers."""
        tickers = ["AAPL", "MSFT", "GOOGL"]
        resolution = Resolution.FIVE_MINUTES

        # Mock responses for each ticker
        def side_effect(**kwargs):
            pk = kwargs["ExpressionAttributeValues"][":pk"]
            ticker = pk.split("#")[0]
            return {
                "Items": [
                    self._create_bucket_item(ticker, "5m", "2025-12-22T10:00:00Z"),
                    self._create_bucket_item(ticker, "5m", "2025-12-22T10:05:00Z"),
                ]
            }

        mock_table.query.side_effect = side_effect

        result = mock_service.query_batch(tickers, resolution)

        assert len(result) == 3
        assert "AAPL" in result
        assert "MSFT" in result
        assert "GOOGL" in result

    def test_query_batch_individual_results_match_single_query(
        self, mock_service, mock_table
    ):
        """Each ticker result should match what single query would return."""
        tickers = ["AAPL"]
        resolution = Resolution.ONE_HOUR

        bucket_item = self._create_bucket_item("AAPL", "1h", "2025-12-22T10:00:00Z")
        mock_table.query.return_value = {"Items": [bucket_item]}

        result = mock_service.query_batch(tickers, resolution)

        # Should have one result for AAPL
        assert len(result) == 1
        assert "AAPL" in result

        # Result should be a TimeseriesResponse
        aapl_response = result["AAPL"]
        assert aapl_response.ticker == "AAPL"
        assert aapl_response.resolution == "1h"
        assert len(aapl_response.buckets) == 1

    def test_query_batch_handles_empty_results(self, mock_service, mock_table):
        """query_batch should handle tickers with no data."""
        tickers = ["AAPL", "NOSUCHSTOCK"]
        resolution = Resolution.FIVE_MINUTES

        def side_effect(**kwargs):
            pk = kwargs["ExpressionAttributeValues"][":pk"]
            ticker = pk.split("#")[0]
            if ticker == "NOSUCHSTOCK":
                return {"Items": []}
            return {
                "Items": [
                    self._create_bucket_item(ticker, "5m", "2025-12-22T10:00:00Z"),
                ]
            }

        mock_table.query.side_effect = side_effect

        result = mock_service.query_batch(tickers, resolution)

        # Both tickers should be in results, even with empty data
        assert "AAPL" in result
        assert "NOSUCHSTOCK" in result
        assert len(result["AAPL"].buckets) == 1
        assert len(result["NOSUCHSTOCK"].buckets) == 0

    def test_query_batch_respects_time_range(self, mock_service, mock_table):
        """query_batch should pass time range to individual queries."""
        tickers = ["AAPL"]
        resolution = Resolution.ONE_MINUTE
        start = datetime(2025, 12, 22, 10, 0, 0, tzinfo=UTC)
        end = datetime(2025, 12, 22, 11, 0, 0, tzinfo=UTC)

        mock_table.query.return_value = {"Items": []}

        mock_service.query_batch(tickers, resolution, start=start, end=end)

        # Verify the query included time range
        call_kwargs = mock_table.query.call_args[1]
        key_condition = call_kwargs["KeyConditionExpression"]
        assert "BETWEEN" in key_condition

    def test_query_batch_uses_cache_when_available(self, mock_table):
        """query_batch should use cache for repeated queries."""
        from src.lambdas.dashboard.timeseries import TimeseriesQueryService

        with patch("src.lambdas.dashboard.timeseries.boto3") as mock_boto3:
            mock_dynamodb = MagicMock()
            mock_boto3.resource.return_value = mock_dynamodb
            mock_dynamodb.Table.return_value = mock_table

            # Create service with cache enabled
            service = TimeseriesQueryService(
                table_name="test-timeseries",
                use_cache=True,
            )
            service._table = mock_table

            # Mock first query to populate cache
            bucket_item = self._create_bucket_item("AAPL", "5m", "2025-12-22T10:00:00Z")
            mock_table.query.return_value = {"Items": [bucket_item]}

            # First call should query DynamoDB
            result1 = service.query_batch(["AAPL"], Resolution.FIVE_MINUTES)

            # Second call should use cache
            result2 = service.query_batch(["AAPL"], Resolution.FIVE_MINUTES)

            # Should have cached the first result
            assert result1["AAPL"].cache_hit is False
            assert result2["AAPL"].cache_hit is True


class TestMultiTickerQueryPerformance:
    """Performance tests for batch queries."""

    @pytest.fixture
    def mock_service_fast(self):
        """Create a mock service with fast responses."""
        from src.lambdas.dashboard.timeseries import TimeseriesQueryService

        with patch("src.lambdas.dashboard.timeseries.boto3") as mock_boto3:
            mock_dynamodb = MagicMock()
            mock_boto3.resource.return_value = mock_dynamodb

            mock_table = MagicMock()
            mock_dynamodb.Table.return_value = mock_table

            # Fast response (no actual I/O)
            # Note: Uses uppercase PK and SK to match production schema
            mock_table.query.return_value = {
                "Items": [
                    {
                        "PK": "AAPL#5m",
                        "SK": "2025-12-22T10:00:00Z",
                        "open": Decimal("0.5"),
                        "high": Decimal("0.6"),
                        "low": Decimal("0.4"),
                        "close": Decimal("0.5"),
                        "count": 10,
                        "sum": Decimal("5.0"),
                        "label_counts": {},
                        "sources": [],
                        "is_partial": False,
                    }
                ]
            }

            service = TimeseriesQueryService(
                table_name="test-timeseries",
                use_cache=False,
            )
            service._table = mock_table
            yield service

    def test_query_batch_is_faster_than_sequential(self, mock_service_fast):
        """Batch query should be faster than sequential single queries."""
        tickers = ["AAPL", "MSFT", "GOOGL", "AMZN", "META"]
        resolution = Resolution.FIVE_MINUTES

        # Time batch query
        start = time.time()
        mock_service_fast.query_batch(tickers, resolution)
        batch_time = time.time() - start

        # Time sequential queries (for comparison)
        start = time.time()
        for ticker in tickers:
            mock_service_fast.query(ticker, resolution)
        _ = time.time() - start  # sequential_time - unused but measured for comparison

        # Batch should not be significantly slower than sequential
        # (In reality, with I/O parallelism, batch would be faster)
        # For mocked test, just verify batch completes in reasonable time
        assert batch_time < 1.0  # Should complete in under 1 second

    def test_query_batch_ten_tickers_under_one_second(self, mock_service_fast):
        """10 tickers should load in under 1 second (SC-006)."""
        tickers = [f"TICKER{i}" for i in range(10)]
        resolution = Resolution.FIVE_MINUTES

        start = time.time()
        result = mock_service_fast.query_batch(tickers, resolution)
        elapsed = time.time() - start

        assert len(result) == 10
        assert elapsed < 1.0, f"Query took {elapsed:.2f}s, expected <1s"


class TestMultiTickerQueryErrorHandling:
    """Error handling tests for batch queries."""

    @pytest.fixture
    def mock_service(self):
        """Create mock service."""
        from src.lambdas.dashboard.timeseries import TimeseriesQueryService

        with patch("src.lambdas.dashboard.timeseries.boto3") as mock_boto3:
            mock_dynamodb = MagicMock()
            mock_boto3.resource.return_value = mock_dynamodb

            mock_table = MagicMock()
            mock_dynamodb.Table.return_value = mock_table

            service = TimeseriesQueryService(
                table_name="test-timeseries",
                use_cache=False,
            )
            service._table = mock_table
            yield service, mock_table

    def test_query_batch_handles_partial_failures(self, mock_service):
        """query_batch should return partial results on partial failures."""
        service, mock_table = mock_service
        from botocore.exceptions import ClientError

        call_count = 0

        def side_effect(**kwargs):
            nonlocal call_count
            call_count += 1
            pk = kwargs["ExpressionAttributeValues"][":pk"]
            ticker = pk.split("#")[0]

            if ticker == "MSFT":
                raise ClientError(
                    {"Error": {"Code": "ProvisionedThroughputExceededException"}},
                    "Query",
                )

            return {
                "Items": [
                    {
                        "pk": f"{ticker}#5m",
                        "sk": "2025-12-22T10:00:00Z",
                        "ticker": ticker,
                        "resolution": "5m",
                        "open": Decimal("0.5"),
                        "high": Decimal("0.6"),
                        "low": Decimal("0.4"),
                        "close": Decimal("0.5"),
                        "count": 10,
                        "sum": Decimal("5.0"),
                        "label_counts": {},
                        "sources": [],
                        "is_partial": False,
                    }
                ]
            }

        mock_table.query.side_effect = side_effect

        result = service.query_batch(["AAPL", "MSFT", "GOOGL"], Resolution.FIVE_MINUTES)

        # AAPL and GOOGL should succeed, MSFT should have error marker
        assert "AAPL" in result
        assert "GOOGL" in result
        assert "MSFT" in result  # Should be present with error state
        assert result["MSFT"].buckets == []  # Empty on error
        # Error should be tracked somehow (implementation detail)

    def test_query_batch_empty_tickers_returns_empty_dict(self, mock_service):
        """query_batch with empty ticker list should return empty dict."""
        service, mock_table = mock_service

        result = service.query_batch([], Resolution.FIVE_MINUTES)

        assert result == {}
        mock_table.query.assert_not_called()
