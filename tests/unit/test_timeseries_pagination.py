"""TDD tests for time-series pagination functionality.

Canonical References:
[CS-001] "Design your application to process one partition key at a time"
         - AWS DynamoDB Best Practices
         - Efficient pagination uses LastEvaluatedKey for cursor-based paging

[CS-008] "IndexedDB optimal for large structured datasets with indexes"
         - MDN IndexedDB
         - Client caches paginated results for smooth scrolling

These tests MUST FAIL initially per TDD methodology.
"""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from src.lib.timeseries import Resolution


class TestTimeseriesPagination:
    """Test pagination for historical time-series queries.

    User Story 3: View Historical Sentiment Trends
    - Smooth historical scrolling with seamless preloading
    - Scroll back 24 hours of 1-minute data, no loading interruptions
    """

    @pytest.fixture
    def mock_dynamodb_table(self) -> MagicMock:
        """Create a mock DynamoDB table."""
        return MagicMock()

    @pytest.fixture
    def sample_items(self) -> list[dict[str, Any]]:
        """Generate sample DynamoDB items for testing pagination."""
        items = []
        base_time = datetime(2025, 12, 21, 10, 0, 0, tzinfo=UTC)
        for i in range(100):  # 100 minutes of data
            ts = base_time.replace(minute=i % 60, hour=10 + i // 60)
            items.append(
                {
                    "pk": "AAPL#1m",
                    "sk": ts.isoformat().replace("+00:00", "Z"),
                    "ticker": "AAPL",
                    "resolution": "1m",
                    "open": Decimal("0.65"),
                    "high": Decimal("0.85"),
                    "low": Decimal("0.55"),
                    "close": Decimal("0.75"),
                    "sum": Decimal("7.5"),
                    "count": 10,
                    "label_counts": {"positive": 6, "negative": 2, "neutral": 2},
                    "is_partial": False,
                }
            )
        return items

    def test_query_returns_paginated_results(
        self, mock_dynamodb_table: MagicMock
    ) -> None:
        """
        Given: 100 buckets exist for AAPL#1m
        When: Querying with limit=20
        Then: Returns exactly 20 buckets with pagination cursor
        """
        from src.lambdas.dashboard.timeseries import TimeseriesQueryService

        mock_dynamodb_table.query.return_value = {
            "Items": [
                {
                    "pk": "AAPL#1m",
                    "sk": f"2025-12-21T10:{i:02d}:00Z",
                    "ticker": "AAPL",
                    "resolution": "1m",
                    "open": Decimal("0.65"),
                    "high": Decimal("0.85"),
                    "low": Decimal("0.55"),
                    "close": Decimal("0.75"),
                    "sum": Decimal("7.5"),
                    "count": 10,
                    "label_counts": {"positive": 6, "negative": 2, "neutral": 2},
                    "is_partial": False,
                }
                for i in range(20)
            ],
            "LastEvaluatedKey": {"pk": "AAPL#1m", "sk": "2025-12-21T10:19:00Z"},
        }

        with patch("boto3.resource") as mock_boto:
            mock_boto.return_value.Table.return_value = mock_dynamodb_table
            service = TimeseriesQueryService("test-table", use_cache=False)

            # Query with limit parameter
            response = service.query(
                ticker="AAPL",
                resolution=Resolution.ONE_MINUTE,
                limit=20,
            )

            assert len(response.buckets) == 20
            assert response.next_cursor is not None
            assert response.has_more is True

    def test_query_with_cursor_continues_from_position(
        self, mock_dynamodb_table: MagicMock
    ) -> None:
        """
        Given: Previous query returned cursor "2025-12-21T10:19:00Z"
        When: Querying with that cursor
        Then: Returns next page starting after cursor position
        """
        from src.lambdas.dashboard.timeseries import TimeseriesQueryService

        mock_dynamodb_table.query.return_value = {
            "Items": [
                {
                    "pk": "AAPL#1m",
                    "sk": f"2025-12-21T10:{20 + i:02d}:00Z",
                    "ticker": "AAPL",
                    "resolution": "1m",
                    "open": Decimal("0.65"),
                    "high": Decimal("0.85"),
                    "low": Decimal("0.55"),
                    "close": Decimal("0.75"),
                    "sum": Decimal("7.5"),
                    "count": 10,
                    "label_counts": {"positive": 6, "negative": 2, "neutral": 2},
                    "is_partial": False,
                }
                for i in range(20)
            ],
            "LastEvaluatedKey": {"pk": "AAPL#1m", "sk": "2025-12-21T10:39:00Z"},
        }

        with patch("boto3.resource") as mock_boto:
            mock_boto.return_value.Table.return_value = mock_dynamodb_table
            service = TimeseriesQueryService("test-table", use_cache=False)

            response = service.query(
                ticker="AAPL",
                resolution=Resolution.ONE_MINUTE,
                limit=20,
                cursor="2025-12-21T10:19:00Z",
            )

            # Verify DynamoDB was called with ExclusiveStartKey
            mock_dynamodb_table.query.assert_called_once()
            call_kwargs = mock_dynamodb_table.query.call_args.kwargs
            assert "ExclusiveStartKey" in call_kwargs
            assert call_kwargs["ExclusiveStartKey"]["sk"] == "2025-12-21T10:19:00Z"

            # Verify response
            assert len(response.buckets) == 20
            assert response.buckets[0].timestamp == "2025-12-21T10:20:00Z"

    def test_query_last_page_has_no_cursor(
        self, mock_dynamodb_table: MagicMock
    ) -> None:
        """
        Given: Query returns fewer items than limit
        When: No more items exist
        Then: next_cursor is None and has_more is False
        """
        from src.lambdas.dashboard.timeseries import TimeseriesQueryService

        mock_dynamodb_table.query.return_value = {
            "Items": [
                {
                    "pk": "AAPL#1m",
                    "sk": f"2025-12-21T10:{i:02d}:00Z",
                    "ticker": "AAPL",
                    "resolution": "1m",
                    "open": Decimal("0.65"),
                    "high": Decimal("0.85"),
                    "low": Decimal("0.55"),
                    "close": Decimal("0.75"),
                    "sum": Decimal("7.5"),
                    "count": 10,
                    "label_counts": {"positive": 6, "negative": 2, "neutral": 2},
                    "is_partial": False,
                }
                for i in range(5)  # Only 5 items, less than limit
            ],
            # No LastEvaluatedKey means no more pages
        }

        with patch("boto3.resource") as mock_boto:
            mock_boto.return_value.Table.return_value = mock_dynamodb_table
            service = TimeseriesQueryService("test-table", use_cache=False)

            response = service.query(
                ticker="AAPL",
                resolution=Resolution.ONE_MINUTE,
                limit=20,
            )

            assert len(response.buckets) == 5
            assert response.next_cursor is None
            assert response.has_more is False

    def test_query_respects_time_range_with_pagination(
        self, mock_dynamodb_table: MagicMock
    ) -> None:
        """
        Given: Query with start and end time AND limit
        When: Paginating through time range
        Then: Only returns items within range, paginated correctly
        """
        from src.lambdas.dashboard.timeseries import TimeseriesQueryService

        start = datetime(2025, 12, 21, 10, 0, 0, tzinfo=UTC)
        end = datetime(2025, 12, 21, 11, 0, 0, tzinfo=UTC)

        mock_dynamodb_table.query.return_value = {
            "Items": [
                {
                    "pk": "AAPL#1m",
                    "sk": f"2025-12-21T10:{i:02d}:00Z",
                    "ticker": "AAPL",
                    "resolution": "1m",
                    "open": Decimal("0.65"),
                    "high": Decimal("0.85"),
                    "low": Decimal("0.55"),
                    "close": Decimal("0.75"),
                    "sum": Decimal("7.5"),
                    "count": 10,
                    "label_counts": {"positive": 6, "negative": 2, "neutral": 2},
                    "is_partial": False,
                }
                for i in range(30)
            ],
            "LastEvaluatedKey": {"pk": "AAPL#1m", "sk": "2025-12-21T10:29:00Z"},
        }

        with patch("boto3.resource") as mock_boto:
            mock_boto.return_value.Table.return_value = mock_dynamodb_table
            service = TimeseriesQueryService("test-table", use_cache=False)

            response = service.query(
                ticker="AAPL",
                resolution=Resolution.ONE_MINUTE,
                start=start,
                end=end,
                limit=30,
            )

            # Verify call includes both time range AND limit
            call_kwargs = mock_dynamodb_table.query.call_args.kwargs
            assert "Limit" in call_kwargs
            assert call_kwargs["Limit"] == 30

            assert len(response.buckets) == 30
            assert response.has_more is True

    def test_default_limit_is_reasonable(self, mock_dynamodb_table: MagicMock) -> None:
        """
        Given: No limit specified
        When: Querying time-series data
        Then: Uses default limit (e.g., 100 for 1-minute data)
        """
        from src.lambdas.dashboard.timeseries import TimeseriesQueryService

        mock_dynamodb_table.query.return_value = {"Items": []}

        with patch("boto3.resource") as mock_boto:
            mock_boto.return_value.Table.return_value = mock_dynamodb_table
            service = TimeseriesQueryService("test-table", use_cache=False)

            service.query(
                ticker="AAPL",
                resolution=Resolution.ONE_MINUTE,
            )

            # Default limit should be applied
            call_kwargs = mock_dynamodb_table.query.call_args.kwargs
            # Default limit for 1-minute should be ~60 (1 hour of data)
            assert "Limit" in call_kwargs
            assert call_kwargs["Limit"] >= 60


class TestTimeseriesResponsePagination:
    """Test that TimeseriesResponse includes pagination metadata."""

    def test_response_includes_pagination_fields(self) -> None:
        """TimeseriesResponse MUST include next_cursor and has_more fields."""
        from src.lambdas.dashboard.timeseries import TimeseriesResponse

        response = TimeseriesResponse(
            ticker="AAPL",
            resolution="1m",
            buckets=[],
            partial_bucket=None,
            cache_hit=False,
            query_time_ms=1.5,
            next_cursor="2025-12-21T10:59:00Z",
            has_more=True,
        )

        assert response.next_cursor == "2025-12-21T10:59:00Z"
        assert response.has_more is True

    def test_response_to_dict_includes_pagination(self) -> None:
        """to_dict() MUST include pagination fields for API response."""
        from src.lambdas.dashboard.timeseries import TimeseriesResponse

        response = TimeseriesResponse(
            ticker="AAPL",
            resolution="1m",
            buckets=[],
            partial_bucket=None,
            cache_hit=False,
            query_time_ms=1.5,
            next_cursor="2025-12-21T10:59:00Z",
            has_more=True,
        )

        d = response.to_dict()
        assert "next_cursor" in d
        assert "has_more" in d
        assert d["next_cursor"] == "2025-12-21T10:59:00Z"
        assert d["has_more"] is True


class TestEndpointPagination:
    """Test that the API endpoint supports pagination parameters."""

    def test_endpoint_accepts_limit_parameter(self) -> None:
        """
        GET /api/v2/timeseries/{ticker}?resolution=1m&limit=50
        Should accept limit query parameter
        """
        # This will test the router_v2.py endpoint
        # The function signature should accept limit
        import inspect

        from src.lambdas.dashboard.router_v2 import get_timeseries

        sig = inspect.signature(get_timeseries)
        param_names = list(sig.parameters.keys())
        assert "limit" in param_names

    def test_endpoint_accepts_cursor_parameter(self) -> None:
        """
        GET /api/v2/timeseries/{ticker}?resolution=1m&cursor=...
        Should accept cursor query parameter
        """
        import inspect

        from src.lambdas.dashboard.router_v2 import get_timeseries

        sig = inspect.signature(get_timeseries)
        param_names = list(sig.parameters.keys())
        assert "cursor" in param_names
