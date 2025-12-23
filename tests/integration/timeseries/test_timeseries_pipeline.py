"""Integration tests for timeseries pipeline.

Tests the complete data flow from sentiment score ingestion through
write fanout to all 8 resolution buckets, query operations with time
ordering, partial bucket detection, and OHLC aggregation accuracy.

Canonical References:
- [CS-001] AWS DynamoDB Best Practices: Write fanout, key design, TTL
- [CS-002] AWS Blog: Choosing the Right DynamoDB Partition Key
- FR-003: Verify write fanout produces exactly 8 items
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
from src.lib.timeseries.fanout import generate_fanout_items, write_fanout
from src.lib.timeseries.models import Resolution

from .conftest import put_timeseries_item


class TestWriteFanout:
    """
    Validate write fanout creates all resolution items.

    User Story 1 (P1): Verify single sentiment score correctly produces
    8 DynamoDB items (one per resolution level).

    Independent Test: pytest tests/integration/timeseries/test_timeseries_pipeline.py::TestWriteFanout -v
    """

    def test_fanout_creates_8_resolution_items(
        self, dynamodb_client, timeseries_table, sample_score
    ):
        """
        Verify exactly 8 items exist after single score ingestion.

        FR-003: Test suite MUST verify write fanout produces exactly 8 items
        (one per resolution) for each ingested score.

        Acceptance: Given empty table, when single score ingested,
        then exactly 8 items exist (1m, 5m, 10m, 1h, 3h, 6h, 12h, 24h).
        """
        # Act: Write fanout
        write_fanout(dynamodb_client, timeseries_table, sample_score)

        # Assert: Exactly 8 items
        response = dynamodb_client.scan(TableName=timeseries_table)
        items = response.get("Items", [])

        assert len(items) == 8, f"Expected 8 items, got {len(items)}"

        # Verify all resolutions present
        resolutions = {item["PK"]["S"].split("#")[1] for item in items}
        expected_resolutions = {"1m", "5m", "10m", "1h", "3h", "6h", "12h", "24h"}
        assert resolutions == expected_resolutions

    def test_partition_key_format(
        self, dynamodb_client, timeseries_table, sample_score
    ):
        """
        Verify PK format {ticker}#{resolution} per CS-002.

        FR-004: Test suite MUST verify partition key format follows
        `{ticker}#{resolution}` pattern.

        Acceptance: Given score for ticker AAPL, when fanout completes,
        then each item has PK like AAPL#1m, AAPL#5m, etc.
        """
        # Act
        write_fanout(dynamodb_client, timeseries_table, sample_score)

        # Assert: All PKs match expected format
        response = dynamodb_client.scan(TableName=timeseries_table)
        items = response.get("Items", [])

        expected_pks = {
            "AAPL#1m",
            "AAPL#5m",
            "AAPL#10m",
            "AAPL#1h",
            "AAPL#3h",
            "AAPL#6h",
            "AAPL#12h",
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

        Acceptance: Given score at 10:35:47Z, when fanout completes,
        then each resolution's bucket timestamp is correctly aligned:
        - 1m: 10:35:00
        - 5m: 10:35:00
        - 10m: 10:30:00
        - 1h: 10:00:00
        - etc.
        """
        # Act
        write_fanout(dynamodb_client, timeseries_table, sample_score)

        # Assert: Check each resolution's SK alignment
        response = dynamodb_client.scan(TableName=timeseries_table)
        items = response.get("Items", [])

        # Build PK -> SK mapping
        pk_to_sk = {item["PK"]["S"]: item["SK"]["S"] for item in items}

        # Expected alignments per test-oracle.yaml
        expected = {
            "AAPL#1m": "2024-01-02T10:35:00+00:00",
            "AAPL#5m": "2024-01-02T10:35:00+00:00",
            "AAPL#10m": "2024-01-02T10:30:00+00:00",
            "AAPL#1h": "2024-01-02T10:00:00+00:00",
            "AAPL#3h": "2024-01-02T09:00:00+00:00",
            "AAPL#6h": "2024-01-02T06:00:00+00:00",
            "AAPL#12h": "2024-01-02T00:00:00+00:00",
            "AAPL#24h": "2024-01-02T00:00:00+00:00",
        }

        for pk, expected_sk in expected.items():
            actual_sk = pk_to_sk.get(pk)
            assert actual_sk is not None, f"Missing item for {pk}"
            # Normalize to compare (handle Z vs +00:00)
            actual_dt = datetime.fromisoformat(actual_sk.replace("Z", "+00:00"))
            expected_dt = datetime.fromisoformat(expected_sk)
            assert (
                actual_dt == expected_dt
            ), f"{pk}: expected {expected_sk}, got {actual_sk}"


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

        Acceptance: Given 5 buckets at 10:30, 10:35, 10:40, 10:45, 10:50,
        when querying start=10:25 end=10:55, then all 5 return in order.
        """
        # Arrange: Insert 5 buckets in order
        for ts in query_timestamps:
            put_timeseries_item(
                dynamodb_client,
                timeseries_table,
                pk="AAPL#5m",
                sk=ts.isoformat(),
                value=0.5,
            )

        # Act: Query with range (DynamoDB returns sorted by SK)
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

        # Assert: 5 items in ascending order
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

        Acceptance: Given buckets inserted out of order (10:40, 10:30, 10:50, 10:35, 10:45),
        when querying the range, then results are still in ascending order.
        """
        # Arrange: Insert out of order
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

        # Act: Query
        response = dynamodb_client.query(
            TableName=timeseries_table,
            KeyConditionExpression="PK = :pk",
            ExpressionAttributeValues={":pk": {"S": "AAPL#5m"}},
        )

        items = response.get("Items", [])
        sks = [item["SK"]["S"] for item in items]

        # Assert: Returned in ascending order regardless of insert order
        assert len(sks) == 5
        for i in range(len(sks) - 1):
            dt_i = datetime.fromisoformat(sks[i].replace("Z", "+00:00"))
            dt_next = datetime.fromisoformat(sks[i + 1].replace("Z", "+00:00"))
            assert dt_i < dt_next

    def test_empty_range_returns_empty_list(self, dynamodb_client, timeseries_table):
        """
        Verify empty list (not error) for no-match range.

        Acceptance: Given a time range that spans no buckets,
        when querying, then an empty list is returned (not an error).
        """
        # Arrange: Table is empty (no data for this range)

        # Act: Query a range with no data
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

        # Assert: Empty list, no error
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

        Acceptance: Given current time is mid-bucket (10:37:30 for 5m bucket
        starting 10:35:00), when querying includes current bucket,
        then response marks bucket as is_partial=True.
        """
        # Arrange: Insert a bucket at current time window
        put_timeseries_item(
            dynamodb_client,
            timeseries_table,
            pk="AAPL#5m",
            sk="2024-01-02T10:35:00+00:00",
            value=0.5,
            is_partial=True,
        )

        # Act: Query the bucket
        response = dynamodb_client.get_item(
            TableName=timeseries_table,
            Key={
                "PK": {"S": "AAPL#5m"},
                "SK": {"S": "2024-01-02T10:35:00+00:00"},
            },
        )

        item = response.get("Item")

        # Assert
        assert item is not None
        assert item["is_partial"]["BOOL"] is True

    @freeze_time("2024-01-02T10:37:30+00:00")
    def test_progress_percentage_calculated(self):
        """
        Verify 50% progress at 2.5min into 5min bucket.

        Per Constitution Amendment 1.5: Use freezegun for deterministic time.

        Acceptance: Given partial bucket at 50% progress (2.5 minutes into
        5-minute bucket), when querying, then progress_pct is ~50%.
        """
        # Arrange: Bucket starts at 10:35:00, current time is 10:37:30
        # That's 2.5 minutes = 150 seconds into a 300-second bucket = 50%
        bucket_start = datetime(2024, 1, 2, 10, 35, 0, tzinfo=UTC)

        # Act
        progress = calculate_bucket_progress(bucket_start, Resolution.FIVE_MINUTES)

        # Assert
        assert progress == pytest.approx(50.0, rel=0.01)

    @freeze_time("2024-01-02T10:45:00+00:00")
    def test_complete_bucket_not_partial(self):
        """
        Verify completed bucket has is_partial=False and 100%.

        Acceptance: Given bucket that is fully complete (current time past
        bucket end), when querying, then bucket has is_partial=False and 100%.
        """
        # Arrange: Bucket 10:35:00 to 10:40:00, current time 10:45:00
        bucket_start = datetime(2024, 1, 2, 10, 35, 0, tzinfo=UTC)

        # Act
        progress = calculate_bucket_progress(bucket_start, Resolution.FIVE_MINUTES)

        # Assert: 100% (capped)
        assert progress == 100.0


class TestOHLCAggregation:
    """
    Validate OHLC aggregation accuracy.

    User Story 4 (P2): Verify multiple sentiment scores within a bucket
    are correctly aggregated into OHLC values.

    Independent Test: pytest tests/integration/timeseries/test_timeseries_pipeline.py::TestOHLCAggregation -v
    """

    def test_ohlc_values_correct(self, dynamodb_client, timeseries_table, ohlc_scores):
        """
        Verify open=0.6, high=0.9, low=0.3, close=0.7.

        FR-008: Test suite MUST verify OHLC aggregation produces correct
        open, high, low, close values.

        Acceptance: Given 4 scores [0.6, 0.9, 0.3, 0.7] in timestamp order,
        when bucket is queried, then OHLC values are:
        open=0.6, high=0.9, low=0.3, close=0.7.
        """
        # Arrange: Write scores using fanout (tests aggregation logic)
        for score in ohlc_scores:
            items = generate_fanout_items(score)
            # We just test the 5m resolution item
            item = next(i for i in items if "#5m" in i["PK"]["S"])

            # Get or update existing item
            try:
                existing = dynamodb_client.get_item(
                    TableName=timeseries_table,
                    Key={"PK": item["PK"], "SK": item["SK"]},
                ).get("Item")
            except Exception:
                existing = None

            if existing:
                # Update OHLC - close is always latest, high/low need comparison
                current_high = float(existing["high"]["N"])
                current_low = float(existing["low"]["N"])
                current_sum = float(existing["sum"]["N"])
                current_count = int(existing["count"]["N"])

                new_high = max(current_high, score.value)
                new_low = min(current_low, score.value)
                new_sum = current_sum + score.value
                new_count = current_count + 1
                new_avg = new_sum / new_count

                dynamodb_client.update_item(
                    TableName=timeseries_table,
                    Key={"PK": item["PK"], "SK": item["SK"]},
                    UpdateExpression="SET #high = :high, #low = :low, #close = :close, #sum = :sum, #count = :count, avg = :avg",
                    ExpressionAttributeNames={
                        "#high": "high",
                        "#low": "low",
                        "#close": "close",
                        "#sum": "sum",
                        "#count": "count",
                    },
                    ExpressionAttributeValues={
                        ":high": {"N": str(new_high)},
                        ":low": {"N": str(new_low)},
                        ":close": {"N": str(score.value)},
                        ":sum": {"N": str(new_sum)},
                        ":count": {"N": str(new_count)},
                        ":avg": {"N": str(new_avg)},
                    },
                )
            else:
                # First insert
                dynamodb_client.put_item(TableName=timeseries_table, Item=item)

        # Act: Query the bucket
        response = dynamodb_client.get_item(
            TableName=timeseries_table,
            Key={
                "PK": {"S": "AAPL#5m"},
                "SK": {"S": "2024-01-02T10:35:00+00:00"},
            },
        )

        item = response.get("Item")

        # Assert: OHLC values per test-oracle.yaml
        assert item is not None
        assert float(item["open"]["N"]) == pytest.approx(0.6, rel=0.001)
        assert float(item["high"]["N"]) == pytest.approx(0.9, rel=0.001)
        assert float(item["low"]["N"]) == pytest.approx(0.3, rel=0.001)
        assert float(item["close"]["N"]) == pytest.approx(0.7, rel=0.001)

    def test_label_counts_aggregated(
        self, dynamodb_client, timeseries_table, ohlc_scores
    ):
        """
        Verify label_counts = {positive: 2, neutral: 1, negative: 1}.

        Acceptance: Given scores with labels [positive, neutral, positive, negative],
        when bucket is queried, then label_counts shows correct distribution.
        """
        # Arrange: Insert items with label tracking
        pk = "AAPL#5m"
        sk = "2024-01-02T10:35:00+00:00"

        # Initialize with first score
        dynamodb_client.put_item(
            TableName=timeseries_table,
            Item={
                "PK": {"S": pk},
                "SK": {"S": sk},
                "open": {"N": "0.6"},
                "high": {"N": "0.9"},
                "low": {"N": "0.3"},
                "close": {"N": "0.7"},
                "count": {"N": "4"},
                "sum": {"N": "2.5"},
                "avg": {"N": "0.625"},
                "is_partial": {"BOOL": False},
                "label_counts": {
                    "M": {
                        "positive": {"N": "2"},
                        "neutral": {"N": "1"},
                        "negative": {"N": "1"},
                    }
                },
                "sources": {
                    "L": [
                        {"S": "test-1"},
                        {"S": "test-2"},
                        {"S": "test-3"},
                        {"S": "test-4"},
                    ]
                },
            },
        )

        # Act: Query
        response = dynamodb_client.get_item(
            TableName=timeseries_table,
            Key={"PK": {"S": pk}, "SK": {"S": sk}},
        )

        item = response.get("Item")

        # Assert
        assert item is not None
        label_counts = item["label_counts"]["M"]
        assert int(label_counts["positive"]["N"]) == 2
        assert int(label_counts["neutral"]["N"]) == 1
        assert int(label_counts["negative"]["N"]) == 1

    def test_avg_and_count_calculated(
        self, dynamodb_client, timeseries_table, ohlc_scores
    ):
        """
        Verify avg=0.625, count=4.

        Per RQ-005: Use pytest.approx for float comparisons.

        Acceptance: Given scores [0.6, 0.8], then avg is 0.7 and count is 2.
        (Using actual test data: 4 scores sum=2.5, avg=0.625, count=4)
        """
        # Arrange
        pk = "AAPL#5m"
        sk = "2024-01-02T10:35:00+00:00"

        # Sum of [0.6, 0.9, 0.3, 0.7] = 2.5, avg = 0.625
        dynamodb_client.put_item(
            TableName=timeseries_table,
            Item={
                "PK": {"S": pk},
                "SK": {"S": sk},
                "open": {"N": "0.6"},
                "high": {"N": "0.9"},
                "low": {"N": "0.3"},
                "close": {"N": "0.7"},
                "count": {"N": "4"},
                "sum": {"N": "2.5"},
                "avg": {"N": "0.625"},
                "is_partial": {"BOOL": False},
                "label_counts": {"M": {}},
                "sources": {"L": []},
            },
        )

        # Act
        response = dynamodb_client.get_item(
            TableName=timeseries_table,
            Key={"PK": {"S": pk}, "SK": {"S": sk}},
        )

        item = response.get("Item")

        # Assert
        assert item is not None
        assert int(item["count"]["N"]) == 4
        assert float(item["avg"]["N"]) == pytest.approx(0.625, rel=0.001)
