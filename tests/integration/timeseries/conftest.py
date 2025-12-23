"""Timeseries integration test fixtures.

Provides class-scoped fixtures for DynamoDB table lifecycle and test data.

Canonical References:
- RQ-001: Class-scoped fixtures for table lifecycle (per research.md)
- RQ-002: Freezegun for deterministic time handling
- RQ-003: Deterministic fixtures with known values

Uses LocalStack DynamoDB for realistic AWS behavior.
"""

import uuid
from datetime import UTC, datetime
from typing import Any

import pytest

from src.lib.timeseries.models import SentimentScore

# Fixed test timestamps per Constitution Amendment 1.5
# Using 2024-01-02 (Tuesday) - a known trading day
TEST_BASE_DATE = datetime(2024, 1, 2, 10, 35, 47, tzinfo=UTC)
TEST_BUCKET_5M_START = datetime(2024, 1, 2, 10, 35, 0, tzinfo=UTC)


@pytest.fixture(scope="class")
def timeseries_test_run_id() -> str:
    """Class-scoped test run ID for timeseries integration tests.

    We need class scope to match the timeseries_table fixture scope.
    The parent conftest's test_run_id has function scope which causes
    a ScopeMismatch error.
    """
    return uuid.uuid4().hex[:8]


@pytest.fixture(scope="class")
def timeseries_table(dynamodb_client, timeseries_test_run_id) -> str:
    """
    Create and tear down a DynamoDB timeseries table per test class.

    Canonical: RQ-001 - Class-scoped fixtures for table lifecycle

    The table schema matches production:
    - PK: {ticker}#{resolution} (String)
    - SK: Bucket timestamp ISO8601 (String)

    Args:
        dynamodb_client: LocalStack DynamoDB client from parent conftest
        timeseries_test_run_id: Class-scoped unique test run identifier

    Yields:
        str: Table name for test use
    """
    table_name = f"test-timeseries-{timeseries_test_run_id}"

    # Create table
    dynamodb_client.create_table(
        TableName=table_name,
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

    # Wait for table to be active
    waiter = dynamodb_client.get_waiter("table_exists")
    waiter.wait(TableName=table_name, WaiterConfig={"Delay": 1, "MaxAttempts": 30})

    yield table_name

    # Teardown: delete table
    try:
        dynamodb_client.delete_table(TableName=table_name)
    except Exception:
        pass  # Best effort cleanup


@pytest.fixture
def sample_score() -> SentimentScore:
    """
    Return a single SentimentScore with fixed timestamp.

    Canonical: RQ-003 - Deterministic fixtures with known values
    Per test-oracle.yaml: timestamp 2024-01-02T10:35:47Z

    Returns:
        SentimentScore: Test score for fanout validation
    """
    return SentimentScore(
        ticker="AAPL",
        value=0.75,
        label="positive",
        timestamp=TEST_BASE_DATE,
        source="test-source",
    )


@pytest.fixture
def ohlc_scores() -> list[SentimentScore]:
    """
    Return list of 4 scores for OHLC aggregation testing.

    Canonical: RQ-003 - Per test-oracle.yaml
    Values: [0.6, 0.9, 0.3, 0.7]
    Labels: [positive, neutral, positive, negative]

    Expected OHLC:
    - open: 0.6 (first)
    - high: 0.9 (max)
    - low: 0.3 (min)
    - close: 0.7 (last)
    - avg: 0.625
    - count: 4
    - label_counts: {positive: 2, neutral: 1, negative: 1}

    Returns:
        list[SentimentScore]: 4 scores for aggregation testing
    """
    return [
        SentimentScore(
            ticker="AAPL",
            value=0.6,
            label="positive",
            timestamp=datetime(2024, 1, 2, 10, 35, 10, tzinfo=UTC),
            source="test-1",
        ),
        SentimentScore(
            ticker="AAPL",
            value=0.9,
            label="neutral",
            timestamp=datetime(2024, 1, 2, 10, 35, 20, tzinfo=UTC),
            source="test-2",
        ),
        SentimentScore(
            ticker="AAPL",
            value=0.3,
            label="positive",
            timestamp=datetime(2024, 1, 2, 10, 35, 30, tzinfo=UTC),
            source="test-3",
        ),
        SentimentScore(
            ticker="AAPL",
            value=0.7,
            label="negative",
            timestamp=datetime(2024, 1, 2, 10, 35, 40, tzinfo=UTC),
            source="test-4",
        ),
    ]


@pytest.fixture
def query_timestamps() -> list[datetime]:
    """
    Return 5 timestamps for query ordering tests.

    Per test-oracle.yaml query_tests.ascending_order.
    These are bucket-aligned timestamps for 5m resolution.

    Returns:
        list[datetime]: 5 bucket timestamps in order
    """
    return [
        datetime(2024, 1, 2, 10, 30, 0, tzinfo=UTC),
        datetime(2024, 1, 2, 10, 35, 0, tzinfo=UTC),
        datetime(2024, 1, 2, 10, 40, 0, tzinfo=UTC),
        datetime(2024, 1, 2, 10, 45, 0, tzinfo=UTC),
        datetime(2024, 1, 2, 10, 50, 0, tzinfo=UTC),
    ]


def put_timeseries_item(
    dynamodb_client: Any,
    table_name: str,
    pk: str,
    sk: str,
    value: float = 0.5,
    label: str = "neutral",
    is_partial: bool = False,
) -> None:
    """
    Helper to insert a single timeseries item for testing.

    Args:
        dynamodb_client: LocalStack DynamoDB client
        table_name: Target table
        pk: Partition key (ticker#resolution)
        sk: Sort key (ISO8601 timestamp)
        value: Sentiment value for OHLC fields
        label: Sentiment label
        is_partial: Whether this is a partial bucket
    """
    item: dict[str, Any] = {
        "PK": {"S": pk},
        "SK": {"S": sk},
        "open": {"N": str(value)},
        "high": {"N": str(value)},
        "low": {"N": str(value)},
        "close": {"N": str(value)},
        "count": {"N": "1"},
        "sum": {"N": str(value)},
        "avg": {"N": str(value)},
        "is_partial": {"BOOL": is_partial},
        "label_counts": {"M": {label: {"N": "1"}}},
        "sources": {"L": [{"S": "test"}]},
    }

    dynamodb_client.put_item(TableName=table_name, Item=item)
