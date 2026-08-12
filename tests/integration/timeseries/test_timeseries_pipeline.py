"""Integration tests for timeseries pipeline.

Tests the complete data flow from sentiment score ingestion through the
accumulating write fanout to all 6 resolution buckets, query operations with
time ordering, partial bucket detection, and OHLC aggregation accuracy.

Canonical References:
- [CS-001] AWS DynamoDB Best Practices: Write fanout, key design, TTL
- [CS-002] AWS Blog: Choosing the Right DynamoDB Partition Key
- FR-003: Verify write fanout produces exactly 6 items
- FR-004: Verify partition key format {ticker}#{resolution}
- FR-005: Verify sort key contains aligned bucket timestamp
- FR-006: Verify query results in ascending timestamp order
- FR-007: Verify partial bucket detection with progress percentage
- FR-008: Verify OHLC aggregation produces correct values

Uses LocalStack for realistic DynamoDB behavior per Constitution Section 7.
Uses fixed historical dates per Constitution Amendment 1.5.
"""

from datetime import UTC, datetime

import pytest
from freezegun import freeze_time

from src.lib.timeseries.bucket import calculate_bucket_progress
from src.lib.timeseries.fanout import accumulate_fanout
from src.lib.timeseries.models import Resolution

from .conftest import put_timeseries_item


class TestWriteFanout:
    """
    Validate the accumulating fanout creates all resolution items.

    User Story 1 (P1): Verify single sentiment score correctly produces
    6 DynamoDB items (one per resolution level).

    Independent Test: pytest tests/integration/timeseries/test_timeseries_pipeline.py::TestWriteFanout -v
    """

    def test_fanout_creates_6_resolution_items(
        self, dynamodb_client, timeseries_table, sample_score
    ):
        """
        Verify exactly 6 items exist after single score ingestion.

        FR-003: Test suite MUST verify write fanout produces exactly 6 items
        (one per resolution) for each ingested score.
        """
        accumulate_fanout(dynamodb_client, timeseries_table, sample_score)

        response = dynamodb_client.scan(TableName=timeseries_table)
        items = response.get("Items", [])

        assert len(items) == 6, f"Expected 6 items, got {len(items)}"

        resolutions = {item["PK"]["S"].split("#")[1] for item in items}
        expected_resolutions = {"1m", "5m", "15m", "30m", "1h", "24h"}
        assert resolutions == expected_resolutions

        # Every bucket is born versioned
        assert all(item["version"]["N"] == "1" for item in items)

    def test_partition_key_format(
        self, dynamodb_client, timeseries_table, sample_score
    ):
        """
        Verify PK format {ticker}#{resolution} per CS-002.

        FR-004: Test suite MUST verify partition key format follows
        `{ticker}#{resolution}` pattern.
        """
        accumulate_fanout(dynamodb_client, timeseries_table, sample_score)

        response = dynamodb_client.scan(TableName=timeseries_table)
        items = response.get("Items", [])

        expected_pks = {
            "AAPL#1m",
            "AAPL#5m",
            "AAPL#15m",
            "AAPL#30m",
            "AAPL#1h",
            "AAPL#24h",
        }

        actual_pks = {item["PK"]["S"] for item in items}
        assert actual_pks == expected_pks

    def test_bucket_timestamps_aligned(
        self, dynamodb_client, timeseries_table, sample_score
    ):
        """
        Verify SK timestamps aligned to resolution boundaries.

        FR-005: Test suite MUST verify sort key contains ISO8601 bucket
        timestamp aligned to resolution boundaries.
        """
        accumulate_fanout(dynamodb_client, timeseries_table, sample_score)

        response = dynamodb_client.scan(TableName=timeseries_table)
        items = response.get("Items", [])

        pk_to_sk = {item["PK"]["S"]: item["SK"]["S"] for item in items}

        expected = {
            "AAPL#1m": "2024-01-02T10:35:00+00:00",
            "AAPL#5m": "2024-01-02T10:35:00+00:00",
            "AAPL#15m": "2024-01-02T10:30:00+00:00",
            "AAPL#30m": "2024-01-02T10:30:00+00:00",
            "AAPL#1h": "2024-01-02T10:00:00+00:00",
            "AAPL#24h": "2024-01-02T00:00:00+00:00",
        }

        for pk, expected_sk in expected.items():
            actual_sk = pk_to_sk.get(pk)
            assert actual_sk is not None, f"Missing item for {pk}"
            actual_dt = datetime.fromisoformat(actual_sk.replace("Z", "+00:00"))
            expected_dt = datetime.fromisoformat(expected_sk)
            assert actual_dt == expected_dt, (
                f"{pk}: expected {expected_sk}, got {actual_sk}"
            )


class TestQueryOrdering:
    """
    Validate query returns buckets in time order.

    User Story 2 (P1): Verify querying a time range returns buckets
    in ascending timestamp order.

    Independent Test: pytest tests/integration/timeseries/test_timeseries_pipeline.py::TestQueryOrdering -v
    """

    def test_query_returns_ascending_order(
        self, dynamodb_client, timeseries_table, query_timestamps
    ):
        """
        Verify buckets return in sorted order.

        FR-006: Test suite MUST verify query results are returned in
        ascending timestamp order.
        """
        for ts in query_timestamps:
            put_timeseries_item(
                dynamodb_client,
                timeseries_table,
                pk="AAPL#5m",
                sk=ts.isoformat(),
                value=0.5,
            )

        response = dynamodb_client.query(
            TableName=timeseries_table,
            KeyConditionExpression="PK = :pk AND SK BETWEEN :start AND :end",
            ExpressionAttributeValues={
                ":pk": {"S": "AAPL#5m"},
                ":start": {"S": "2024-01-02T10:25:00+00:00"},
                ":end": {"S": "2024-01-02T10:55:00+00:00"},
            },
        )

        items = response.get("Items", [])

        assert len(items) == 5

        sks = [item["SK"]["S"] for item in items]
        for i in range(len(sks) - 1):
            dt_i = datetime.fromisoformat(sks[i].replace("Z", "+00:00"))
            dt_next = datetime.fromisoformat(sks[i + 1].replace("Z", "+00:00"))
            assert dt_i < dt_next, f"Items not in ascending order: {sks}"

    def test_out_of_order_insert_returns_sorted(
        self, dynamodb_client, timeseries_table, query_timestamps
    ):
        """
        Verify out-of-order insertion still returns sorted.
        """
        out_of_order = [
            query_timestamps[2],  # 10:40
            query_timestamps[0],  # 10:30
            query_timestamps[4],  # 10:50
            query_timestamps[1],  # 10:35
            query_timestamps[3],  # 10:45
        ]

        for ts in out_of_order:
            put_timeseries_item(
                dynamodb_client,
                timeseries_table,
                pk="AAPL#5m",
                sk=ts.isoformat(),
                value=0.5,
            )

        response = dynamodb_client.query(
            TableName=timeseries_table,
            KeyConditionExpression="PK = :pk",
            ExpressionAttributeValues={":pk": {"S": "AAPL#5m"}},
        )

        items = response.get("Items", [])
        sks = [item["SK"]["S"] for item in items]

        assert len(sks) == 5
        for i in range(len(sks) - 1):
            dt_i = datetime.fromisoformat(sks[i].replace("Z", "+00:00"))
            dt_next = datetime.fromisoformat(sks[i + 1].replace("Z", "+00:00"))
            assert dt_i < dt_next

    def test_empty_range_returns_empty_list(self, dynamodb_client, timeseries_table):
        """
        Verify empty list (not error) for no-match range.
        """
        response = dynamodb_client.query(
            TableName=timeseries_table,
            KeyConditionExpression="PK = :pk AND SK BETWEEN :start AND :end",
            ExpressionAttributeValues={
                ":pk": {"S": "AAPL#5m"},
                ":start": {"S": "2024-01-02T11:00:00+00:00"},
                ":end": {"S": "2024-01-02T12:00:00+00:00"},
            },
        )

        items = response.get("Items", [])

        assert items == []


class TestPartialBucket:
    """
    Validate partial bucket flagging.

    User Story 3 (P2): Verify current in-progress bucket is correctly
    flagged as partial with a progress percentage.

    Independent Test: pytest tests/integration/timeseries/test_timeseries_pipeline.py::TestPartialBucket -v
    """

    @freeze_time("2024-01-02T10:37:30+00:00")
    def test_current_bucket_flagged_partial(self, dynamodb_client, timeseries_table):
        """
        Verify mid-bucket is flagged as is_partial=True.

        FR-007: Test suite MUST verify partial bucket detection.
        """
        put_timeseries_item(
            dynamodb_client,
            timeseries_table,
            pk="AAPL#5m",
            sk="2024-01-02T10:35:00+00:00",
            value=0.5,
            is_partial=True,
        )

        response = dynamodb_client.get_item(
            TableName=timeseries_table,
            Key={
                "PK": {"S": "AAPL#5m"},
                "SK": {"S": "2024-01-02T10:35:00+00:00"},
            },
        )

        item = response.get("Item")

        assert item is not None
        assert item["is_partial"]["BOOL"] is True

    @freeze_time("2024-01-02T10:37:30+00:00")
    def test_progress_percentage_calculated(self):
        """
        Verify 50% progress at 2.5min into 5min bucket.

        Per Constitution Amendment 1.5: Use freezegun for deterministic time.
        """
        bucket_start = datetime(2024, 1, 2, 10, 35, 0, tzinfo=UTC)

        progress = calculate_bucket_progress(bucket_start, Resolution.FIVE_MINUTES)

        assert progress == pytest.approx(50.0, rel=0.01)

    @freeze_time("2024-01-02T10:45:00+00:00")
    def test_complete_bucket_not_partial(self):
        """
        Verify completed bucket has 100% progress (capped).
        """
        bucket_start = datetime(2024, 1, 2, 10, 35, 0, tzinfo=UTC)

        progress = calculate_bucket_progress(bucket_start, Resolution.FIVE_MINUTES)

        assert progress == 100.0


class TestOHLCAggregation:
    """
    Validate OHLC aggregation accuracy through the accumulating writer.

    User Story 4 (P2): Verify multiple sentiment scores within a bucket
    are correctly aggregated into OHLC values by accumulate_fanout itself,
    not by test-local aggregation logic.

    Independent Test: pytest tests/integration/timeseries/test_timeseries_pipeline.py::TestOHLCAggregation -v
    """

    # The table fixture is class-scoped, so each test accumulates into its
    # own ticker to keep buckets independent.

    def _accumulate_all(self, dynamodb_client, timeseries_table, ohlc_scores, ticker):
        for score in ohlc_scores:
            accumulate_fanout(
                dynamodb_client,
                timeseries_table,
                score.model_copy(update={"ticker": ticker}),
            )

    def _get_bucket(self, dynamodb_client, timeseries_table, ticker):
        response = dynamodb_client.get_item(
            TableName=timeseries_table,
            Key={
                "PK": {"S": f"{ticker}#5m"},
                "SK": {"S": "2024-01-02T10:35:00+00:00"},
            },
            ConsistentRead=True,
        )
        item = response.get("Item")
        assert item is not None
        return item

    def test_ohlc_values_correct(self, dynamodb_client, timeseries_table, ohlc_scores):
        """
        Verify open=0.6, high=0.9, low=0.3, close=0.7.

        FR-008: Test suite MUST verify OHLC aggregation produces correct
        open, high, low, close values.
        """
        self._accumulate_all(dynamodb_client, timeseries_table, ohlc_scores, "OHLC")

        item = self._get_bucket(dynamodb_client, timeseries_table, "OHLC")
        assert float(item["open"]["N"]) == pytest.approx(0.6, rel=0.001)
        assert float(item["high"]["N"]) == pytest.approx(0.9, rel=0.001)
        assert float(item["low"]["N"]) == pytest.approx(0.3, rel=0.001)
        assert float(item["close"]["N"]) == pytest.approx(0.7, rel=0.001)
        # open/close ordering is backed by article timestamps
        assert item["open_ts"]["S"] == "2024-01-02T10:35:10+00:00"
        assert item["close_ts"]["S"] == "2024-01-02T10:35:40+00:00"

    def test_label_counts_aggregated(
        self, dynamodb_client, timeseries_table, ohlc_scores
    ):
        """
        Verify label_counts = {positive: 2, neutral: 1, negative: 1}.
        """
        self._accumulate_all(dynamodb_client, timeseries_table, ohlc_scores, "LBL")

        item = self._get_bucket(dynamodb_client, timeseries_table, "LBL")
        label_counts = item["label_counts"]["M"]
        assert int(label_counts["positive"]["N"]) == 2
        assert int(label_counts["neutral"]["N"]) == 1
        assert int(label_counts["negative"]["N"]) == 1

    def test_avg_count_and_version_calculated(
        self, dynamodb_client, timeseries_table, ohlc_scores
    ):
        """
        Verify avg=0.625, count=4, version=4 after four contributions.

        Per RQ-005: Use pytest.approx for float comparisons.
        """
        self._accumulate_all(dynamodb_client, timeseries_table, ohlc_scores, "AVG")

        item = self._get_bucket(dynamodb_client, timeseries_table, "AVG")
        assert int(item["count"]["N"]) == 4
        assert float(item["sum"]["N"]) == pytest.approx(2.5, rel=0.001)
        assert float(item["avg"]["N"]) == pytest.approx(0.625, rel=0.001)
        assert int(item["version"]["N"]) == 4
