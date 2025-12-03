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
            service = PollingService()
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
            service = PollingService()
            metrics = service._aggregate_metrics(mock_dynamodb_table.scan()["Items"])

        assert metrics.by_tag["AAPL"] == 2
        assert metrics.by_tag["MSFT"] == 1

    def test_aggregate_metrics_empty_items(self):
        """Should handle empty item list."""
        from src.lambdas.sse_streaming.polling import PollingService

        with patch.object(PollingService, "_get_table", return_value=MagicMock()):
            service = PollingService()
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
            with patch.dict("os.environ", {}, clear=True):
                service = PollingService()

        assert service.poll_interval == 5

    def test_custom_poll_interval(self):
        """Should respect SSE_POLL_INTERVAL env var."""
        from src.lambdas.sse_streaming.polling import PollingService

        with patch.object(PollingService, "_get_table", return_value=MagicMock()):
            with patch.dict("os.environ", {"SSE_POLL_INTERVAL": "10"}):
                service = PollingService()

        assert service.poll_interval == 10


class TestMetricsChange:
    """Tests for detecting metrics changes."""

    def test_detects_change_in_total(self):
        """Should detect when total changes."""
        from src.lambdas.sse_streaming.polling import PollingService

        with patch.object(PollingService, "_get_table", return_value=MagicMock()):
            service = PollingService()

        old = MetricsEventData(total=100, positive=50, neutral=30, negative=20)
        new = MetricsEventData(total=101, positive=51, neutral=30, negative=20)

        assert service._metrics_changed(old, new) is True

    def test_no_change_when_same(self):
        """Should return False when metrics unchanged."""
        from src.lambdas.sse_streaming.polling import PollingService

        with patch.object(PollingService, "_get_table", return_value=MagicMock()):
            service = PollingService()

        old = MetricsEventData(total=100, positive=50, neutral=30, negative=20)
        new = MetricsEventData(total=100, positive=50, neutral=30, negative=20)

        assert service._metrics_changed(old, new) is False

    def test_detects_change_in_by_tag(self):
        """Should detect when by_tag changes."""
        from src.lambdas.sse_streaming.polling import PollingService

        with patch.object(PollingService, "_get_table", return_value=MagicMock()):
            service = PollingService()

        old = MetricsEventData(
            total=100, positive=50, neutral=30, negative=20, by_tag={"AAPL": 50}
        )
        new = MetricsEventData(
            total=100, positive=50, neutral=30, negative=20, by_tag={"AAPL": 51}
        )

        assert service._metrics_changed(old, new) is True
