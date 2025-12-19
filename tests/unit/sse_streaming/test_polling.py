"""Unit tests for DynamoDB polling service.

Tests polling and metrics aggregation per FR-015.
"""

from decimal import Decimal
from unittest.mock import MagicMock, patch

import pytest

from src.lambdas.sse_streaming.models import MetricsEventData


class TestPollingService:
    """Tests for DynamoDB polling service."""

    @pytest.fixture
    def mock_dynamodb_table(self):
        """Create mock DynamoDB table."""
        mock_table = MagicMock()
        mock_table.scan.return_value = {
            "Items": [
                {
                    "pk": "SENTIMENT#item1",
                    "sk": "2025-12-02T10:00:00Z",
                    "ticker": "AAPL",
                    "sentiment": "positive",
                    "score": Decimal("0.85"),
                    "timestamp": "2025-12-02T10:00:00Z",
                },
                {
                    "pk": "SENTIMENT#item2",
                    "sk": "2025-12-02T10:01:00Z",
                    "ticker": "MSFT",
                    "sentiment": "neutral",
                    "score": Decimal("0.05"),
                    "timestamp": "2025-12-02T10:01:00Z",
                },
                {
                    "pk": "SENTIMENT#item3",
                    "sk": "2025-12-02T10:02:00Z",
                    "ticker": "AAPL",
                    "sentiment": "negative",
                    "score": Decimal("-0.65"),
                    "timestamp": "2025-12-02T10:02:00Z",
                },
            ]
        }
        return mock_table

    def test_aggregate_metrics_counts_sentiments(self, mock_dynamodb_table):
        """Should count positive/neutral/negative sentiments."""
        from src.lambdas.sse_streaming.polling import PollingService

        with patch.object(
            PollingService, "_get_table", return_value=mock_dynamodb_table
        ):
            service = PollingService(table_name="test-table")
            service._table = mock_dynamodb_table
            metrics = service._aggregate_metrics(mock_dynamodb_table.scan()["Items"])

        assert metrics.total == 3
        assert metrics.positive == 1
        assert metrics.neutral == 1
        assert metrics.negative == 1

    def test_aggregate_metrics_counts_by_tag(self, mock_dynamodb_table):
        """Should count items per ticker tag."""
        from src.lambdas.sse_streaming.polling import PollingService

        with patch.object(
            PollingService, "_get_table", return_value=mock_dynamodb_table
        ):
            service = PollingService(table_name="test-table")
            metrics = service._aggregate_metrics(mock_dynamodb_table.scan()["Items"])

        assert metrics.by_tag["AAPL"] == 2
        assert metrics.by_tag["MSFT"] == 1

    def test_aggregate_metrics_empty_items(self):
        """Should handle empty item list."""
        from src.lambdas.sse_streaming.polling import PollingService

        with patch.object(PollingService, "_get_table", return_value=MagicMock()):
            service = PollingService(table_name="test-table")
            metrics = service._aggregate_metrics([])

        assert metrics.total == 0
        assert metrics.positive == 0
        assert metrics.by_tag == {}


class TestPollingInterval:
    """Tests for polling interval configuration."""

    def test_default_poll_interval(self):
        """Default poll interval should be 5 seconds."""
        from src.lambdas.sse_streaming.polling import PollingService

        with patch.object(PollingService, "_get_table", return_value=MagicMock()):
            with patch.dict("os.environ", {"DYNAMODB_TABLE": "test-table"}, clear=True):
                service = PollingService()

        assert service.poll_interval == 5

    def test_custom_poll_interval(self):
        """Should respect SSE_POLL_INTERVAL env var."""
        from src.lambdas.sse_streaming.polling import PollingService

        with patch.object(PollingService, "_get_table", return_value=MagicMock()):
            with patch.dict(
                "os.environ",
                {"DYNAMODB_TABLE": "test-table", "SSE_POLL_INTERVAL": "10"},
            ):
                service = PollingService()

        assert service.poll_interval == 10

    def test_missing_dynamodb_table_raises_error(self):
        """Should raise ValueError if DYNAMODB_TABLE not set."""
        from src.lambdas.sse_streaming.polling import PollingService

        with patch.dict("os.environ", {}, clear=True):
            with pytest.raises(ValueError, match="DYNAMODB_TABLE.*required"):
                PollingService()


class TestPollMethod:
    """Tests for the async poll method.

    (502-gsi-query-optimization: Updated to mock table.query instead of table.scan)
    """

    @pytest.fixture
    def mock_dynamodb_table(self):
        """Create mock DynamoDB table with GSI query support."""
        mock_table = MagicMock()
        # Mock GSI query response (used by _query_by_sentiment)
        mock_table.query.return_value = {
            "Items": [
                {
                    "pk": "SENTIMENT#item1",
                    "ticker": "AAPL",
                    "sentiment": "positive",
                },
            ]
        }
        return mock_table

    @pytest.mark.asyncio
    async def test_poll_returns_metrics_and_changed_flag(self, mock_dynamodb_table):
        """Poll should return metrics and changed flag.

        Note: The mock returns 1 item per query, and the poll calls query 3 times
        (once for positive, neutral, negative sentiments), so total is 3.
        """
        from src.lambdas.sse_streaming.polling import PollingService

        service = PollingService(table_name="test-table")
        service._table = mock_dynamodb_table

        metrics, changed = await service.poll()

        assert metrics is not None
        # Mock returns 1 item per query * 3 sentiment types = 3 total
        assert metrics.total == 3
        assert changed is True  # First poll always changed

    @pytest.mark.asyncio
    async def test_poll_second_call_returns_not_changed(self, mock_dynamodb_table):
        """Second poll with same data should return changed=False."""
        from src.lambdas.sse_streaming.polling import PollingService

        service = PollingService(table_name="test-table")
        service._table = mock_dynamodb_table

        # First poll
        await service.poll()

        # Second poll - same data
        metrics, changed = await service.poll()

        assert changed is False

    @pytest.mark.asyncio
    async def test_poll_handles_dynamodb_error(self, mock_dynamodb_table):
        """Poll should handle DynamoDB errors gracefully.

        (502-gsi-query-optimization: Updated to use query error instead of scan)
        """
        from botocore.exceptions import ClientError

        from src.lambdas.sse_streaming.polling import PollingService

        mock_dynamodb_table.query.side_effect = ClientError(
            {"Error": {"Code": "InternalError", "Message": "Test error"}},
            "Query",
        )

        service = PollingService(table_name="test-table")
        service._table = mock_dynamodb_table

        # Should not raise, should return empty metrics
        metrics, changed = await service.poll()

        assert metrics.total == 0
        assert changed is False

    @pytest.mark.asyncio
    async def test_poll_returns_cached_metrics_on_error(self, mock_dynamodb_table):
        """Poll should return cached metrics when error occurs after first poll.

        (502-gsi-query-optimization: Updated to use query error instead of scan)
        """
        from botocore.exceptions import ClientError

        from src.lambdas.sse_streaming.polling import PollingService

        service = PollingService(table_name="test-table")
        service._table = mock_dynamodb_table

        # First successful poll
        metrics1, _ = await service.poll()
        # Mock returns 1 item per query * 3 sentiment types = 3 total
        assert metrics1.total == 3

        # Second poll fails
        mock_dynamodb_table.query.side_effect = ClientError(
            {"Error": {"Code": "InternalError", "Message": "Test error"}},
            "Query",
        )

        metrics2, changed = await service.poll()

        # Should return cached metrics
        assert metrics2.total == 3
        assert changed is False


class TestQueryBySentiment:
    """Tests for _query_by_sentiment method.

    (502-gsi-query-optimization: Replaced TestScanTable with GSI query tests)
    """

    def test_query_by_sentiment_uses_gsi(self):
        """Query should use by_sentiment GSI."""
        from src.lambdas.sse_streaming.polling import PollingService

        mock_table = MagicMock()
        mock_table.query.return_value = {"Items": []}

        service = PollingService(table_name="test-table")
        service._table = mock_table

        service._query_by_sentiment("positive")

        mock_table.query.assert_called_once()
        call_kwargs = mock_table.query.call_args[1]
        assert call_kwargs["IndexName"] == "by_sentiment"
        assert "sentiment = :sentiment" in call_kwargs["KeyConditionExpression"]
        assert call_kwargs["ExpressionAttributeValues"][":sentiment"] == "positive"


class TestMetricsChange:
    """Tests for detecting metrics changes."""

    def test_detects_change_in_total(self):
        """Should detect when total changes."""
        from src.lambdas.sse_streaming.polling import PollingService

        with patch.object(PollingService, "_get_table", return_value=MagicMock()):
            service = PollingService(table_name="test-table")

        old = MetricsEventData(total=100, positive=50, neutral=30, negative=20)
        new = MetricsEventData(total=101, positive=51, neutral=30, negative=20)

        assert service._metrics_changed(old, new) is True

    def test_no_change_when_same(self):
        """Should return False when metrics unchanged."""
        from src.lambdas.sse_streaming.polling import PollingService

        with patch.object(PollingService, "_get_table", return_value=MagicMock()):
            service = PollingService(table_name="test-table")

        old = MetricsEventData(total=100, positive=50, neutral=30, negative=20)
        new = MetricsEventData(total=100, positive=50, neutral=30, negative=20)

        assert service._metrics_changed(old, new) is False

    def test_detects_change_in_by_tag(self):
        """Should detect when by_tag changes."""
        from src.lambdas.sse_streaming.polling import PollingService

        with patch.object(PollingService, "_get_table", return_value=MagicMock()):
            service = PollingService(table_name="test-table")

        old = MetricsEventData(
            total=100, positive=50, neutral=30, negative=20, by_tag={"AAPL": 50}
        )
        new = MetricsEventData(
            total=100, positive=50, neutral=30, negative=20, by_tag={"AAPL": 51}
        )

        assert service._metrics_changed(old, new) is True
