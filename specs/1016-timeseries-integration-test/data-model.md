# Data Model: Timeseries Integration Test Fixtures

**Feature**: 1016-timeseries-integration-test
**Date**: 2025-12-22

## Test Fixture Definitions

### Timeseries Table Schema

The integration tests create a temporary DynamoDB table per test class:

```
Table Name: test-timeseries-{test_run_id}
Billing Mode: PAY_PER_REQUEST

Primary Key:
  - PK (String): Partition key in format "{ticker}#{resolution}"
  - SK (String): Sort key containing ISO8601 bucket timestamp

Attributes:
  - open (Number): First sentiment value in bucket
  - high (Number): Highest sentiment value in bucket
  - low (Number): Lowest sentiment value in bucket
  - close (Number): Last sentiment value in bucket
  - count (Number): Number of scores in bucket
  - sum (Number): Sum of scores for average calculation
  - avg (Number): Running average (sum/count)
  - ttl (Number): Unix timestamp for automatic expiration
  - is_partial (Boolean): True if bucket is still accumulating
  - sources (List): Source identifiers for scores
  - label_counts (Map): Count of each sentiment label
  - original_timestamp (String): Timestamp of last score added
```

### SentimentScore Fixture

```python
@dataclass
class SentimentScore:
    ticker: str           # e.g., "AAPL"
    value: float          # 0.0 to 1.0
    label: str            # "positive", "neutral", "negative"
    timestamp: datetime   # UTC timestamp
    source: str           # Optional source identifier
```

### Test Data Sets

#### Fanout Test Data

```python
FANOUT_TEST_SCORE = SentimentScore(
    ticker="AAPL",
    value=0.75,
    label="positive",
    timestamp=datetime(2024, 1, 2, 10, 35, 47, tzinfo=timezone.utc),
    source="test-source"
)
```

#### OHLC Test Data

```python
OHLC_TEST_SCORES = [
    SentimentScore(
        ticker="AAPL",
        value=0.6,
        label="positive",
        timestamp=datetime(2024, 1, 2, 10, 35, 10, tzinfo=timezone.utc),
        source="test-1"
    ),
    SentimentScore(
        ticker="AAPL",
        value=0.9,
        label="neutral",
        timestamp=datetime(2024, 1, 2, 10, 35, 20, tzinfo=timezone.utc),
        source="test-2"
    ),
    SentimentScore(
        ticker="AAPL",
        value=0.3,
        label="positive",
        timestamp=datetime(2024, 1, 2, 10, 35, 30, tzinfo=timezone.utc),
        source="test-3"
    ),
    SentimentScore(
        ticker="AAPL",
        value=0.7,
        label="negative",
        timestamp=datetime(2024, 1, 2, 10, 35, 40, tzinfo=timezone.utc),
        source="test-4"
    ),
]
```

#### Query Ordering Test Data

```python
QUERY_TEST_TIMESTAMPS = [
    "2024-01-02T10:30:00Z",
    "2024-01-02T10:35:00Z",
    "2024-01-02T10:40:00Z",
    "2024-01-02T10:45:00Z",
    "2024-01-02T10:50:00Z",
]
```

### Resolution Definitions

```python
RESOLUTIONS = {
    "1m": 60,      # 60 seconds
    "5m": 300,     # 5 minutes
    "10m": 600,    # 10 minutes
    "1h": 3600,    # 1 hour
    "3h": 10800,   # 3 hours
    "6h": 21600,   # 6 hours
    "12h": 43200,  # 12 hours
    "24h": 86400,  # 24 hours
}

RESOLUTION_TTLS = {
    "1m": 6 * 3600,       # 6 hours
    "5m": 12 * 3600,      # 12 hours
    "10m": 24 * 3600,     # 24 hours
    "1h": 7 * 86400,      # 7 days
    "3h": 14 * 86400,     # 14 days
    "6h": 30 * 86400,     # 30 days
    "12h": 60 * 86400,    # 60 days
    "24h": 90 * 86400,    # 90 days
}
```

## Fixture Relationships

```
timeseries_table (class-scoped)
    │
    ├── Provides: table_name, dynamodb_client
    │
    └── Used by:
        ├── TestWriteFanout.test_fanout_creates_8_resolution_items
        ├── TestWriteFanout.test_partition_key_format
        ├── TestWriteFanout.test_bucket_timestamps_aligned
        ├── TestQueryOrdering.test_query_returns_ascending_order
        ├── TestQueryOrdering.test_out_of_order_insert_returns_sorted
        ├── TestQueryOrdering.test_empty_range_returns_empty_list
        ├── TestPartialBucket.test_current_bucket_flagged_partial
        ├── TestPartialBucket.test_progress_percentage_calculated
        ├── TestPartialBucket.test_complete_bucket_not_partial
        ├── TestOHLCAggregation.test_ohlc_values_correct
        ├── TestOHLCAggregation.test_label_counts_aggregated
        └── TestOHLCAggregation.test_avg_and_count_calculated
```
