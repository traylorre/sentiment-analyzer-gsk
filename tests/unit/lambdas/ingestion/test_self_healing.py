"""
Unit Tests for Self-Healing Module
===================================

Tests for the self-healing functionality that detects and republishes
stale pending items that were ingested but never analyzed.

Test organization:
- TestQueryStalePendingItems: Tests for GSI query logic
- TestGetFullItems: Tests for fetching full item data
- TestRepublishItemsToSns: Tests for SNS batch publishing
- TestRunSelfHealingCheck: Tests for the main orchestration function
"""

from datetime import UTC, datetime, timedelta
from unittest.mock import MagicMock, patch

import pytest


@pytest.fixture
def mock_table():
    """Create a mock DynamoDB table resource."""
    table = MagicMock()
    return table


@pytest.fixture
def mock_sns_client():
    """Create a mock SNS client."""
    client = MagicMock()
    return client


@pytest.fixture
def sample_stale_item():
    """Create a sample stale pending item (from GSI - KEYS_ONLY)."""
    threshold = datetime.now(UTC) - timedelta(hours=2)
    return {
        "source_id": "finnhub:12345",
        "status": "pending",
        "timestamp": threshold.isoformat(),
    }


@pytest.fixture
def sample_full_item():
    """Create a sample full item (from base table GetItem)."""
    threshold = datetime.now(UTC) - timedelta(hours=2)
    return {
        "source_id": "finnhub:12345",
        "source_type": "finnhub",
        "status": "pending",
        "timestamp": threshold.isoformat(),
        "text_for_analysis": "Company XYZ reports record earnings",
        "matched_tickers": ["XYZ"],
        "metadata": {"title": "XYZ Earnings Report"},
    }


@pytest.fixture
def sample_analyzed_item():
    """Create a sample item that has already been analyzed."""
    threshold = datetime.now(UTC) - timedelta(hours=2)
    return {
        "source_id": "finnhub:99999",
        "source_type": "finnhub",
        "status": "analyzed",
        "timestamp": threshold.isoformat(),
        "text_for_analysis": "Already analyzed article",
        "matched_tickers": ["ABC"],
        "sentiment": "positive",  # Has sentiment = already analyzed
    }


class TestQueryStalePendingItems:
    """Tests for query_stale_pending_items function."""

    def test_returns_empty_list_when_no_stale_items(self, mock_table):
        """T008: Returns empty list when no stale items exist."""
        from src.lambdas.ingestion.self_healing import query_stale_pending_items

        mock_table.query.return_value = {"Items": []}

        result = query_stale_pending_items(mock_table)

        assert result == []
        mock_table.query.assert_called_once()

    def test_returns_items_older_than_threshold(self, mock_table, sample_stale_item):
        """T009: Returns items older than the threshold."""
        from src.lambdas.ingestion.self_healing import query_stale_pending_items

        mock_table.query.return_value = {"Items": [sample_stale_item]}

        result = query_stale_pending_items(mock_table, threshold_hours=1)

        assert len(result) == 1
        assert result[0]["source_id"] == "finnhub:12345"

    def test_respects_limit_parameter(self, mock_table):
        """Query respects the limit parameter."""
        from src.lambdas.ingestion.self_healing import query_stale_pending_items

        # Create 150 items
        items = [
            {
                "source_id": f"test:{i}",
                "status": "pending",
                "timestamp": "2025-01-01T00:00:00Z",
            }
            for i in range(150)
        ]
        mock_table.query.return_value = {"Items": items[:100]}

        result = query_stale_pending_items(mock_table, limit=100)

        assert len(result) <= 100

    def test_handles_pagination(self, mock_table):
        """Query handles DynamoDB pagination correctly."""
        from src.lambdas.ingestion.self_healing import query_stale_pending_items

        # First page returns items and LastEvaluatedKey
        mock_table.query.side_effect = [
            {
                "Items": [
                    {
                        "source_id": "test:1",
                        "status": "pending",
                        "timestamp": "2025-01-01T00:00:00Z",
                    }
                ],
                "LastEvaluatedKey": {"source_id": "test:1"},
            },
            {
                "Items": [
                    {
                        "source_id": "test:2",
                        "status": "pending",
                        "timestamp": "2025-01-01T00:00:00Z",
                    }
                ],
            },
        ]

        result = query_stale_pending_items(mock_table, limit=100)

        assert len(result) == 2
        assert mock_table.query.call_count == 2


class TestGetFullItems:
    """Tests for get_full_items function."""

    def test_excludes_items_with_sentiment_attribute(
        self, mock_table, sample_analyzed_item
    ):
        """T010: Excludes items that already have sentiment attribute."""
        from src.lambdas.ingestion.self_healing import get_full_items

        mock_table.get_item.return_value = {"Item": sample_analyzed_item}

        item_keys = [{"source_id": "finnhub:99999", "timestamp": "2025-12-13T09:00:00"}]
        result = get_full_items(mock_table, item_keys)

        # Should be empty because item has sentiment
        assert result == []
        # Verify GetItem called with composite key
        mock_table.get_item.assert_called_once()
        call_args = mock_table.get_item.call_args
        assert call_args.kwargs["Key"]["source_id"] == "finnhub:99999"
        assert call_args.kwargs["Key"]["timestamp"] == "2025-12-13T09:00:00"

    def test_includes_items_without_sentiment(self, mock_table, sample_full_item):
        """Returns items that don't have sentiment attribute."""
        from src.lambdas.ingestion.self_healing import get_full_items

        mock_table.get_item.return_value = {"Item": sample_full_item}

        item_keys = [{"source_id": "finnhub:12345", "timestamp": "2025-12-13T09:00:00"}]
        result = get_full_items(mock_table, item_keys)

        assert len(result) == 1
        assert result[0]["source_id"] == "finnhub:12345"
        # Verify GetItem called with composite key
        call_args = mock_table.get_item.call_args
        assert call_args.kwargs["Key"]["source_id"] == "finnhub:12345"
        assert call_args.kwargs["Key"]["timestamp"] == "2025-12-13T09:00:00"

    def test_returns_empty_for_empty_input(self, mock_table):
        """Returns empty list for empty input."""
        from src.lambdas.ingestion.self_healing import get_full_items

        result = get_full_items(mock_table, [])

        assert result == []
        mock_table.get_item.assert_not_called()

    def test_handles_missing_items_gracefully(self, mock_table):
        """Continues processing when some items are not found."""
        from src.lambdas.ingestion.self_healing import get_full_items

        mock_table.get_item.return_value = {"Item": None}

        item_keys = [{"source_id": "missing:123", "timestamp": "2025-12-13T09:00:00"}]
        result = get_full_items(mock_table, item_keys)

        assert result == []

    def test_skips_items_missing_timestamp(self, mock_table):
        """Skips items that are missing the timestamp key."""
        from src.lambdas.ingestion.self_healing import get_full_items

        # Item without timestamp should be skipped
        item_keys = [{"source_id": "missing:123"}]
        result = get_full_items(mock_table, item_keys)

        assert result == []
        mock_table.get_item.assert_not_called()

    def test_skips_items_missing_source_id(self, mock_table):
        """Skips items that are missing the source_id key."""
        from src.lambdas.ingestion.self_healing import get_full_items

        # Item without source_id should be skipped
        item_keys = [{"timestamp": "2025-12-13T09:00:00"}]
        result = get_full_items(mock_table, item_keys)

        assert result == []
        mock_table.get_item.assert_not_called()


class TestRepublishItemsToSns:
    """Tests for republish_items_to_sns function."""

    def test_publishes_batch_messages_correctly(
        self, mock_sns_client, sample_full_item
    ):
        """T012: Publishes items as batch messages to SNS."""
        from src.lambdas.ingestion.self_healing import republish_items_to_sns

        mock_sns_client.publish_batch.return_value = {
            "Successful": [{"Id": "0", "MessageId": "msg-123"}],
            "Failed": [],
        }

        result = republish_items_to_sns(
            sns_client=mock_sns_client,
            sns_topic_arn="arn:aws:sns:us-east-1:123456789:test-topic",
            items=[sample_full_item],
            model_version="v1.0.0",
        )

        assert result == 1
        mock_sns_client.publish_batch.assert_called_once()

        # Verify message structure
        call_args = mock_sns_client.publish_batch.call_args
        entries = call_args.kwargs["PublishBatchRequestEntries"]
        assert len(entries) == 1
        assert "republished" in entries[0]["MessageAttributes"]

    def test_handles_sns_failures_gracefully(self, mock_sns_client, sample_full_item):
        """T013: Handles SNS publish failures without raising exception."""
        from src.lambdas.ingestion.self_healing import republish_items_to_sns

        mock_sns_client.publish_batch.return_value = {
            "Successful": [],
            "Failed": [{"Id": "0", "Code": "InternalError", "Message": "Failed"}],
        }

        result = republish_items_to_sns(
            sns_client=mock_sns_client,
            sns_topic_arn="arn:aws:sns:us-east-1:123456789:test-topic",
            items=[sample_full_item],
        )

        # Should return 0 but not raise
        assert result == 0

    def test_returns_zero_for_empty_items(self, mock_sns_client):
        """Returns 0 when items list is empty."""
        from src.lambdas.ingestion.self_healing import republish_items_to_sns

        result = republish_items_to_sns(
            sns_client=mock_sns_client,
            sns_topic_arn="arn:aws:sns:us-east-1:123456789:test-topic",
            items=[],
        )

        assert result == 0
        mock_sns_client.publish_batch.assert_not_called()

    def test_returns_zero_for_empty_topic_arn(self, mock_sns_client, sample_full_item):
        """Returns 0 when SNS topic ARN is empty."""
        from src.lambdas.ingestion.self_healing import republish_items_to_sns

        result = republish_items_to_sns(
            sns_client=mock_sns_client,
            sns_topic_arn="",
            items=[sample_full_item],
        )

        assert result == 0
        mock_sns_client.publish_batch.assert_not_called()

    def test_batches_large_item_lists(self, mock_sns_client):
        """Batches items into groups of 10 (SNS limit)."""
        from src.lambdas.ingestion.self_healing import republish_items_to_sns

        # Create 25 items
        items = [
            {
                "source_id": f"test:{i}",
                "source_type": "test",
                "text_for_analysis": f"Article {i}",
                "matched_tickers": ["TEST"],
                "timestamp": "2025-01-01T00:00:00Z",
            }
            for i in range(25)
        ]

        mock_sns_client.publish_batch.return_value = {
            "Successful": [{"Id": str(i), "MessageId": f"msg-{i}"} for i in range(10)],
            "Failed": [],
        }

        republish_items_to_sns(
            sns_client=mock_sns_client,
            sns_topic_arn="arn:aws:sns:us-east-1:123456789:test-topic",
            items=items,
        )

        # Should call publish_batch 3 times (10 + 10 + 5)
        assert mock_sns_client.publish_batch.call_count == 3


class TestRunSelfHealingCheck:
    """Tests for run_self_healing_check function."""

    def test_returns_result_when_no_stale_items(self, mock_table, mock_sns_client):
        """T019: Returns SelfHealingResult even when no stale items found."""
        from src.lambdas.ingestion.self_healing import run_self_healing_check

        mock_table.query.return_value = {"Items": []}

        with patch("src.lambdas.ingestion.self_healing.emit_metric"):
            result = run_self_healing_check(
                table=mock_table,
                sns_client=mock_sns_client,
                sns_topic_arn="arn:aws:sns:us-east-1:123456789:test-topic",
            )

        assert result.items_found == 0
        assert result.items_republished == 0
        assert result.errors == []

    def test_orchestrates_full_workflow(
        self, mock_table, mock_sns_client, sample_stale_item, sample_full_item
    ):
        """Orchestrates query -> get_full -> republish workflow."""
        from src.lambdas.ingestion.self_healing import run_self_healing_check

        mock_table.query.return_value = {"Items": [sample_stale_item]}
        mock_table.get_item.return_value = {"Item": sample_full_item}
        mock_sns_client.publish_batch.return_value = {
            "Successful": [{"Id": "0", "MessageId": "msg-123"}],
            "Failed": [],
        }

        with patch("src.lambdas.ingestion.self_healing.emit_metric"):
            result = run_self_healing_check(
                table=mock_table,
                sns_client=mock_sns_client,
                sns_topic_arn="arn:aws:sns:us-east-1:123456789:test-topic",
            )

        assert result.items_found == 1
        assert result.items_republished == 1
        assert result.errors == []
        assert result.execution_time_ms > 0

    def test_logs_summary_with_item_counts(
        self, mock_table, mock_sns_client, sample_stale_item, sample_full_item
    ):
        """T027: Logs summary with item counts."""
        from src.lambdas.ingestion.self_healing import run_self_healing_check

        mock_table.query.return_value = {"Items": [sample_stale_item]}
        mock_table.get_item.return_value = {"Item": sample_full_item}
        mock_sns_client.publish_batch.return_value = {
            "Successful": [{"Id": "0", "MessageId": "msg-123"}],
            "Failed": [],
        }

        with patch("src.lambdas.ingestion.self_healing.emit_metric"):
            with patch("src.lambdas.ingestion.self_healing.logger") as mock_logger:
                run_self_healing_check(
                    table=mock_table,
                    sns_client=mock_sns_client,
                    sns_topic_arn="arn:aws:sns:us-east-1:123456789:test-topic",
                )

                # Verify info log was called with summary
                mock_logger.info.assert_called()
                call_args = mock_logger.info.call_args_list[-1]
                assert "Self-healing completed" in str(call_args)

    def test_emits_metrics(
        self, mock_table, mock_sns_client, sample_stale_item, sample_full_item
    ):
        """T028: Emits CloudWatch metrics."""
        from src.lambdas.ingestion.self_healing import run_self_healing_check

        mock_table.query.return_value = {"Items": [sample_stale_item]}
        mock_table.get_item.return_value = {"Item": sample_full_item}
        mock_sns_client.publish_batch.return_value = {
            "Successful": [{"Id": "0", "MessageId": "msg-123"}],
            "Failed": [],
        }

        with patch("src.lambdas.ingestion.self_healing.emit_metric") as mock_emit:
            run_self_healing_check(
                table=mock_table,
                sns_client=mock_sns_client,
                sns_topic_arn="arn:aws:sns:us-east-1:123456789:test-topic",
            )

            # Verify metrics were emitted
            metric_names = [call[0][0] for call in mock_emit.call_args_list]
            assert "SelfHealingItemsFound" in metric_names
            assert "SelfHealingItemsRepublished" in metric_names
            assert "SelfHealingExecutionTime" in metric_names

    def test_handles_errors_gracefully(self, mock_table, mock_sns_client):
        """T021: Self-healing errors don't propagate to caller."""
        from src.lambdas.ingestion.self_healing import run_self_healing_check

        mock_table.query.side_effect = Exception("DynamoDB error")

        with patch("src.lambdas.ingestion.self_healing.emit_metric"):
            result = run_self_healing_check(
                table=mock_table,
                sns_client=mock_sns_client,
                sns_topic_arn="arn:aws:sns:us-east-1:123456789:test-topic",
            )

        # Should return result with error, not raise
        assert len(result.errors) == 1
        assert "DynamoDB error" in result.errors[0]


class TestExcludesItemsNewerThanThreshold:
    """Tests for threshold filtering logic."""

    def test_excludes_items_newer_than_threshold(self, mock_table):
        """T011: Excludes items that are newer than the threshold."""
        from src.lambdas.ingestion.self_healing import query_stale_pending_items

        # Recent item (30 minutes ago) should NOT be returned by query
        # because the KeyConditionExpression filters by timestamp < threshold
        mock_table.query.return_value = {"Items": []}

        result = query_stale_pending_items(mock_table, threshold_hours=1)

        assert result == []
        # Verify the query used correct threshold
        call_args = mock_table.query.call_args
        assert ":threshold" in str(call_args)
