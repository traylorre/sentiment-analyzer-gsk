"""
Tests for time-series write fanout.

Canonical References:
- [CS-001] AWS DynamoDB Best Practices: "Pre-aggregate at write time for known query patterns"
- [CS-003] Rick Houlihan re:Invent 2018: "Write amplification acceptable when reads >> writes"
- [CS-013] AWS DynamoDB TTL: "Use TTL to automatically expire items"
- [CS-014] AWS Architecture Blog: "Resolution-dependent retention policies"

TDD-FANOUT-001: Single score produces 6 resolution items
TDD-FANOUT-002: Each item has correctly aligned bucket timestamp
TDD-FANOUT-003: TTL varies by resolution (1m=6h, 5m=12h, 1h=7d, 24h=90d)
TDD-FANOUT-004: BatchWriteItem used (not individual PutItem)
"""

from datetime import UTC, datetime
from unittest.mock import MagicMock, patch

import boto3
import pytest
from botocore.exceptions import ClientError
from moto import mock_aws

from src.lib.timeseries import (
    Resolution,
    SentimentScore,
    generate_fanout_items,
    write_fanout,
    write_fanout_with_update,
)


def parse_iso(s: str) -> datetime:
    """Parse ISO8601 timestamp with timezone."""
    return datetime.fromisoformat(s.replace("Z", "+00:00"))


class TestWriteFanout:
    """
    Canonical: [CS-001] "Pre-aggregate at write time for known query patterns"
    [CS-003] "Write amplification acceptable when reads >> writes"
    """

    def test_fanout_creates_6_resolution_items(self):
        """Single sentiment score MUST produce 6 DynamoDB items (one per resolution)."""
        score = SentimentScore(
            ticker="AAPL",
            value=0.75,
            label="positive",
            timestamp=parse_iso("2025-12-21T10:35:47Z"),
        )
        items = generate_fanout_items(score)
        assert len(items) == 6
        resolutions = {item["PK"]["S"].split("#")[1] for item in items}
        assert resolutions == {"1m", "5m", "15m", "30m", "1h", "24h"}

    def test_fanout_bucket_timestamps_aligned(self):
        """Each resolution item MUST have correctly aligned bucket timestamp."""
        score = SentimentScore(
            ticker="AAPL",
            value=0.75,
            timestamp=parse_iso("2025-12-21T10:37:47Z"),
        )
        items = generate_fanout_items(score)

        # Find 1m bucket - should truncate to :37:00
        item_1m = next(i for i in items if "1m" in i["PK"]["S"])
        assert item_1m["SK"]["S"] == "2025-12-21T10:37:00+00:00"

        # Find 5m bucket - should truncate to :35:00
        item_5m = next(i for i in items if "5m" in i["PK"]["S"])
        assert item_5m["SK"]["S"] == "2025-12-21T10:35:00+00:00"

        # Find 1h bucket - should truncate to :00:00
        item_1h = next(i for i in items if "1h" in i["PK"]["S"])
        assert item_1h["SK"]["S"] == "2025-12-21T10:00:00+00:00"

    def test_fanout_includes_ohlc_values(self):
        """Fanout items MUST include OHLC values from score."""
        score = SentimentScore(
            ticker="TSLA",
            value=0.5,
            label="neutral",
            timestamp=parse_iso("2025-12-21T14:22:00Z"),
        )
        items = generate_fanout_items(score)

        # Check any item has OHLC values
        item = items[0]
        assert "open" in item
        assert "high" in item
        assert "low" in item
        assert "close" in item
        assert "count" in item
        assert float(item["open"]["N"]) == 0.5
        assert float(item["high"]["N"]) == 0.5
        assert float(item["low"]["N"]) == 0.5
        assert float(item["close"]["N"]) == 0.5
        assert int(item["count"]["N"]) == 1

    def test_fanout_includes_label_counts(self):
        """Fanout items MUST include label counts."""
        score = SentimentScore(
            ticker="AAPL",
            value=0.75,
            label="positive",
            timestamp=parse_iso("2025-12-21T10:35:00Z"),
        )
        items = generate_fanout_items(score)

        item = items[0]
        assert "label_counts" in item
        label_counts = item["label_counts"]["M"]
        assert "positive" in label_counts
        assert int(label_counts["positive"]["N"]) == 1

    def test_fanout_ttl_resolution_dependent(self):
        """
        TTL MUST vary by resolution per [CS-014]:
        - 1m: 6 hours
        - 5m: 12 hours
        - 1h: 7 days
        - 24h: 90 days
        """
        score = SentimentScore(
            ticker="AAPL",
            value=0.75,
            timestamp=parse_iso("2025-12-21T10:35:00Z"),
        )
        items = generate_fanout_items(score)

        item_1m = next(i for i in items if "1m" in i["PK"]["S"])
        item_24h = next(i for i in items if "24h" in i["PK"]["S"])

        # 1m TTL should be ~6 hours from bucket timestamp
        ttl_1m = int(item_1m["ttl"]["N"])
        expected_1m = int(parse_iso("2025-12-21T10:35:00Z").timestamp()) + (6 * 3600)
        assert ttl_1m == expected_1m

        # 24h TTL should be ~90 days from bucket timestamp
        ttl_24h = int(item_24h["ttl"]["N"])
        expected_24h = int(parse_iso("2025-12-21T00:00:00Z").timestamp()) + (90 * 86400)
        assert ttl_24h == expected_24h

    def test_fanout_ticker_in_pk(self):
        """PK MUST include ticker: {ticker}#{resolution}."""
        score = SentimentScore(
            ticker="MSFT",
            value=-0.25,
            timestamp=parse_iso("2025-12-21T08:00:00Z"),
        )
        items = generate_fanout_items(score)

        for item in items:
            pk = item["PK"]["S"]
            assert pk.startswith("MSFT#"), f"PK should start with MSFT#, got {pk}"

    def test_fanout_is_partial_true(self):
        """New fanout items MUST have is_partial=true."""
        score = SentimentScore(
            ticker="AAPL",
            value=0.75,
            timestamp=parse_iso("2025-12-21T10:35:00Z"),
        )
        items = generate_fanout_items(score)

        for item in items:
            assert item["is_partial"]["BOOL"] is True

    @mock_aws
    def test_fanout_uses_batch_write(self):
        """Fanout MUST use BatchWriteItem for efficiency, not individual PutItem."""
        # Setup
        dynamodb = boto3.client("dynamodb", region_name="us-east-1")
        dynamodb.create_table(
            TableName="test-timeseries",
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

        score = SentimentScore(
            ticker="AAPL",
            value=0.75,
            timestamp=datetime.now(UTC),
        )

        # Execute
        with patch.object(
            dynamodb, "batch_write_item", wraps=dynamodb.batch_write_item
        ) as mock_batch:
            write_fanout(dynamodb, "test-timeseries", score)
            mock_batch.assert_called_once()

        # Verify all items written
        response = dynamodb.scan(TableName="test-timeseries")
        assert response["Count"] == 6

    @mock_aws
    def test_fanout_update_existing_bucket(self):
        """
        Write to existing bucket MUST:
        1. Update OHLC (keep open, update high/low/close)
        2. Increment count
        3. Add to label_counts
        """
        dynamodb = boto3.client("dynamodb", region_name="us-east-1")
        dynamodb.create_table(
            TableName="test-timeseries",
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

        # First score
        score1 = SentimentScore(
            ticker="AAPL",
            value=0.5,
            label="neutral",
            timestamp=parse_iso("2025-12-21T10:35:30Z"),
        )
        write_fanout_with_update(dynamodb, "test-timeseries", score1)

        # Second score in same bucket
        score2 = SentimentScore(
            ticker="AAPL",
            value=0.8,
            label="positive",
            timestamp=parse_iso("2025-12-21T10:35:45Z"),
        )
        write_fanout_with_update(dynamodb, "test-timeseries", score2)

        # Check 1m bucket
        response = dynamodb.get_item(
            TableName="test-timeseries",
            Key={
                "PK": {"S": "AAPL#1m"},
                "SK": {"S": "2025-12-21T10:35:00+00:00"},
            },
        )

        item = response["Item"]
        # Open should be first value, close should be last
        assert float(item["open"]["N"]) == 0.5
        assert float(item["close"]["N"]) == 0.8
        assert float(item["high"]["N"]) == 0.8
        assert float(item["low"]["N"]) == 0.5
        assert int(item["count"]["N"]) == 2

        # Check label counts
        label_counts = item["label_counts"]["M"]
        assert int(label_counts["neutral"]["N"]) == 1
        assert int(label_counts["positive"]["N"]) == 1

    @mock_aws
    def test_fanout_all_resolutions_have_items(self):
        """All 6 resolutions MUST have items after write."""
        dynamodb = boto3.client("dynamodb", region_name="us-east-1")
        dynamodb.create_table(
            TableName="test-timeseries",
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

        score = SentimentScore(
            ticker="AAPL",
            value=0.75,
            timestamp=datetime.now(UTC),
        )
        write_fanout(dynamodb, "test-timeseries", score)

        # Verify we can query each resolution
        for resolution in Resolution:
            response = dynamodb.query(
                TableName="test-timeseries",
                KeyConditionExpression="PK = :pk",
                ExpressionAttributeValues={":pk": {"S": f"AAPL#{resolution.value}"}},
            )
            assert response["Count"] >= 1, f"No items for resolution {resolution.value}"

    def test_fanout_missing_ticker_raises(self):
        """Score without ticker MUST raise ValueError."""
        score = SentimentScore(
            value=0.75,
            timestamp=parse_iso("2025-12-21T10:35:00Z"),
        )
        with pytest.raises(ValueError, match="ticker"):
            generate_fanout_items(score)

    def test_fanout_source_tracking(self):
        """Fanout items MUST track data sources."""
        score = SentimentScore(
            ticker="AAPL",
            value=0.75,
            source="tiingo",
            timestamp=parse_iso("2025-12-21T10:35:00Z"),
        )
        items = generate_fanout_items(score)

        item = items[0]
        assert "sources" in item
        sources = item["sources"]["L"]
        assert {"S": "tiingo"} in sources


# 1220-xray-instrumentation-hardening: Fanout metric emission tests


class TestFanoutMetricEmission:
    """Verify SilentFailure/Count and ConditionalCheck/Count metrics."""

    SAMPLE_SCORE = SentimentScore(
        ticker="AAPL",
        value=0.75,
        source="tiingo",
        timestamp=datetime(2024, 1, 2, 10, 30, 0, tzinfo=UTC),
        label="positive",
    )

    def _client_error(self, code="InternalServerError"):
        return ClientError(
            error_response={"Error": {"Code": code, "Message": "test"}},
            operation_name="TestOp",
        )

    @patch("src.lib.timeseries.fanout.emit_metric")
    @patch("src.lib.timeseries.fanout.tracer")
    def test_batch_write_emits_silent_failure(self, mock_tracer, mock_emit):
        mock_dynamodb = MagicMock()
        mock_dynamodb.batch_write_item.side_effect = self._client_error()
        mock_tracer.provider.in_subsegment.return_value.__enter__ = MagicMock()
        mock_tracer.provider.in_subsegment.return_value.__exit__ = MagicMock(
            return_value=False
        )
        with pytest.raises(ClientError):
            write_fanout(mock_dynamodb, "t", self.SAMPLE_SCORE)
        mock_emit.assert_called_once_with(
            name="SilentFailure/Count",
            value=1,
            unit="Count",
            dimensions={"FailurePath": "fanout_batch_write"},
            namespace="SentimentAnalyzer/Reliability",
        )

    @patch("src.lib.timeseries.fanout.emit_metric")
    @patch("src.lib.timeseries.fanout.tracer")
    def test_base_update_emits_silent_failure(self, mock_tracer, mock_emit):
        mock_dynamodb = MagicMock()
        mock_dynamodb.update_item.side_effect = self._client_error()
        mock_tracer.provider.in_subsegment.return_value.__enter__ = MagicMock()
        mock_tracer.provider.in_subsegment.return_value.__exit__ = MagicMock(
            return_value=False
        )
        with pytest.raises(ClientError):
            write_fanout_with_update(mock_dynamodb, "t", self.SAMPLE_SCORE)
        mock_emit.assert_called_once_with(
            name="SilentFailure/Count",
            value=1,
            unit="Count",
            dimensions={"FailurePath": "fanout_base_update"},
            namespace="SentimentAnalyzer/Reliability",
        )

    @patch("src.lib.timeseries.fanout.emit_metric")
    @patch("src.lib.timeseries.fanout.tracer")
    def test_label_update_emits_silent_failure(self, mock_tracer, mock_emit):
        mock_dynamodb = MagicMock()
        mock_dynamodb.update_item.side_effect = [None, self._client_error()]
        mock_tracer.provider.in_subsegment.return_value.__enter__ = MagicMock()
        mock_tracer.provider.in_subsegment.return_value.__exit__ = MagicMock(
            return_value=False
        )
        with pytest.raises(ClientError):
            write_fanout_with_update(mock_dynamodb, "t", self.SAMPLE_SCORE)
        mock_emit.assert_called_once_with(
            name="SilentFailure/Count",
            value=1,
            unit="Count",
            dimensions={"FailurePath": "fanout_label_update"},
            namespace="SentimentAnalyzer/Reliability",
        )

    @patch("src.lib.timeseries.fanout.emit_metric")
    @patch("src.lib.timeseries.fanout.tracer")
    def test_conditional_emits_contention_metric(self, mock_tracer, mock_emit):
        mock_dynamodb = MagicMock()
        cond_err = self._client_error("ConditionalCheckFailedException")
        # write_fanout_with_update loops over 6 resolutions.
        # Each resolution: base_update, label_update, cond_high, cond_low = 4 calls.
        # We want all to succeed except conditional checks.
        # 6 resolutions * 4 calls = 24 calls. Simplify: use side_effect function.
        call_count = [0]

        def update_side_effect(**kwargs):
            call_count[0] += 1
            cond_expr = kwargs.get("ConditionExpression", "")
            if "#high <" in cond_expr or "#low >" in cond_expr:
                raise cond_err
            return {}

        mock_dynamodb.update_item.side_effect = update_side_effect
        write_fanout_with_update(mock_dynamodb, "t", self.SAMPLE_SCORE)
        calls = [
            c
            for c in mock_emit.call_args_list
            if c[1].get("name") == "ConditionalCheck/Count"
        ]
        # 6 resolutions * 2 conditional checks (high + low) = 12
        assert len(calls) == 12

    @patch("src.lib.timeseries.fanout.emit_metric")
    @patch("src.lib.timeseries.fanout.tracer")
    def test_conditional_unexpected_emits_silent_failure(self, mock_tracer, mock_emit):
        mock_dynamodb = MagicMock()
        mock_dynamodb.update_item.side_effect = [
            None,
            None,
            self._client_error("ThrottlingException"),
        ]
        mock_tracer.provider.in_subsegment.return_value.__enter__ = MagicMock()
        mock_tracer.provider.in_subsegment.return_value.__exit__ = MagicMock(
            return_value=False
        )
        with pytest.raises(ClientError):
            write_fanout_with_update(mock_dynamodb, "t", self.SAMPLE_SCORE)
        mock_emit.assert_called_once_with(
            name="SilentFailure/Count",
            value=1,
            unit="Count",
            dimensions={"FailurePath": "fanout_conditional_unexpected"},
            namespace="SentimentAnalyzer/Reliability",
        )

    @patch("src.lib.timeseries.fanout.emit_metric", side_effect=Exception("CW down"))
    @patch("src.lib.timeseries.fanout.tracer")
    def test_metric_failure_does_not_propagate(self, mock_tracer, mock_emit):
        mock_dynamodb = MagicMock()
        mock_dynamodb.batch_write_item.side_effect = self._client_error()
        mock_tracer.provider.in_subsegment.return_value.__enter__ = MagicMock()
        mock_tracer.provider.in_subsegment.return_value.__exit__ = MagicMock(
            return_value=False
        )
        with pytest.raises(ClientError):
            write_fanout(mock_dynamodb, "t", self.SAMPLE_SCORE)
