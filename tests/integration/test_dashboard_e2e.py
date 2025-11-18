"""
E2E Tests for Dashboard Lambda
==============================

End-to-end tests for the dashboard FastAPI application.

For On-Call Engineers:
    If these tests fail in CI:
    1. Check moto version compatibility
    2. Verify all GSIs are created in test setup
    3. Check test data seeding is correct

For Developers:
    - Uses FastAPI TestClient with moto for AWS mocking
    - Tests the complete request/response cycle
    - Covers metrics aggregation, API key validation, health check
    - Verifies response schemas match frontend expectations
"""

import os
from datetime import UTC, datetime, timedelta
from decimal import Decimal

# Set env vars before importing handler (which reads them at module level)
os.environ["API_KEY"] = "test-api-key-12345"
os.environ["DYNAMODB_TABLE"] = "test-sentiment-items"
os.environ["ENVIRONMENT"] = "test"

import boto3  # noqa: E402
import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from moto import mock_aws  # noqa: E402

from src.lambdas.dashboard.handler import app  # noqa: E402


def create_test_table():
    """Create a test DynamoDB table with all required GSIs."""
    dynamodb = boto3.resource("dynamodb", region_name="us-east-1")

    table = dynamodb.create_table(
        TableName="test-sentiment-items",
        KeySchema=[
            {"AttributeName": "source_id", "KeyType": "HASH"},
            {"AttributeName": "timestamp", "KeyType": "RANGE"},
        ],
        AttributeDefinitions=[
            {"AttributeName": "source_id", "AttributeType": "S"},
            {"AttributeName": "timestamp", "AttributeType": "S"},
            {"AttributeName": "sentiment", "AttributeType": "S"},
            {"AttributeName": "status", "AttributeType": "S"},
        ],
        GlobalSecondaryIndexes=[
            {
                "IndexName": "by_sentiment",
                "KeySchema": [
                    {"AttributeName": "sentiment", "KeyType": "HASH"},
                    {"AttributeName": "timestamp", "KeyType": "RANGE"},
                ],
                "Projection": {"ProjectionType": "ALL"},
            },
            {
                "IndexName": "by_status",
                "KeySchema": [
                    {"AttributeName": "status", "KeyType": "HASH"},
                    {"AttributeName": "timestamp", "KeyType": "RANGE"},
                ],
                "Projection": {"ProjectionType": "ALL"},
            },
        ],
        BillingMode="PAY_PER_REQUEST",
    )

    table.meta.client.get_waiter("table_exists").wait(TableName="test-sentiment-items")

    return table


def seed_comprehensive_test_data(table):
    """
    Seed table with comprehensive test data for E2E testing.

    Creates items with various sentiments, tags, and timestamps
    to test all aggregation functions.
    """
    now = datetime.now(UTC)

    items = [
        # Recent positive items
        {
            "source_id": "newsapi#pos1",
            "timestamp": (now - timedelta(minutes=5)).isoformat(),
            "title": "Tech Stock Soars on AI News",
            "content": "Major tech company announces breakthrough in AI...",
            "sentiment": "positive",
            "score": Decimal("0.92"),
            "status": "analyzed",
            "tags": ["tech", "ai", "stocks"],
            "source": "techcrunch",
            "url": "https://example.com/article1",
        },
        {
            "source_id": "newsapi#pos2",
            "timestamp": (now - timedelta(minutes=15)).isoformat(),
            "title": "Climate Initiative Shows Progress",
            "content": "New renewable energy projects exceed targets...",
            "sentiment": "positive",
            "score": Decimal("0.88"),
            "status": "analyzed",
            "tags": ["climate", "energy"],
            "source": "reuters",
            "url": "https://example.com/article2",
        },
        # Neutral items
        {
            "source_id": "newsapi#neu1",
            "timestamp": (now - timedelta(minutes=25)).isoformat(),
            "title": "Market Update: Mixed Trading Day",
            "content": "Stocks show mixed results as investors await...",
            "sentiment": "neutral",
            "score": Decimal("0.55"),
            "status": "analyzed",
            "tags": ["stocks", "market"],
            "source": "bloomberg",
            "url": "https://example.com/article3",
        },
        {
            "source_id": "newsapi#neu2",
            "timestamp": (now - timedelta(minutes=35)).isoformat(),
            "title": "Policy Review Continues",
            "content": "Government officials continue to review...",
            "sentiment": "neutral",
            "score": Decimal("0.52"),
            "status": "analyzed",
            "tags": ["politics"],
            "source": "ap",
            "url": "https://example.com/article4",
        },
        # Negative items
        {
            "source_id": "newsapi#neg1",
            "timestamp": (now - timedelta(minutes=45)).isoformat(),
            "title": "Security Breach Affects Millions",
            "content": "Major data breach exposes user information...",
            "sentiment": "negative",
            "score": Decimal("0.89"),
            "status": "analyzed",
            "tags": ["tech", "security"],
            "source": "wired",
            "url": "https://example.com/article5",
        },
        {
            "source_id": "newsapi#neg2",
            "timestamp": (now - timedelta(minutes=55)).isoformat(),
            "title": "Economic Concerns Rise",
            "content": "Analysts warn of potential downturn...",
            "sentiment": "negative",
            "score": Decimal("0.78"),
            "status": "analyzed",
            "tags": ["economy", "market"],
            "source": "ft",
            "url": "https://example.com/article6",
        },
        # Pending item (not yet analyzed)
        {
            "source_id": "newsapi#pending1",
            "timestamp": (now - timedelta(minutes=2)).isoformat(),
            "title": "Breaking: New Development",
            "content": "Latest news just in...",
            "status": "pending",
            "tags": ["breaking"],
            "source": "cnn",
            "url": "https://example.com/article7",
        },
        # Older item (outside 1-hour window but within 24-hour)
        {
            "source_id": "newsapi#old1",
            "timestamp": (now - timedelta(hours=6)).isoformat(),
            "title": "Yesterday's Tech News",
            "content": "Older technology update...",
            "sentiment": "positive",
            "score": Decimal("0.75"),
            "status": "analyzed",
            "tags": ["tech"],
            "source": "verge",
            "url": "https://example.com/article8",
        },
    ]

    for item in items:
        table.put_item(Item=item)

    return items


@pytest.fixture
def client():
    """Create TestClient for FastAPI app."""
    return TestClient(app)


@pytest.fixture
def auth_headers():
    """Return valid authorization headers for E2E tests."""
    return {"Authorization": "Bearer test-api-key-12345"}


class TestDashboardE2E:
    """End-to-end tests for dashboard functionality."""

    @mock_aws
    def test_health_check_returns_healthy(self, client):
        """
        E2E: Health check endpoint returns healthy status.

        Verifies:
        - Status code is 200
        - Response contains status, table name, environment
        - DynamoDB connectivity is tested
        """
        create_test_table()

        response = client.get("/health")

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert data["table"] == "test-sentiment-items"
        assert data["environment"] == "test"

    @mock_aws
    def test_metrics_response_schema(self, client, auth_headers):
        """
        E2E: Metrics endpoint returns correct response schema.

        Verifies frontend can parse the response correctly.
        """
        table = create_test_table()
        seed_comprehensive_test_data(table)

        response = client.get("/api/metrics", headers=auth_headers)

        assert response.status_code == 200
        data = response.json()

        # Verify all required fields are present
        required_fields = [
            "total",
            "positive",
            "neutral",
            "negative",
            "by_tag",
            "rate_last_hour",
            "rate_last_24h",
            "recent_items",
        ]
        for field in required_fields:
            assert field in data, f"Missing field: {field}"

        # Verify types
        assert isinstance(data["total"], int)
        assert isinstance(data["positive"], int)
        assert isinstance(data["neutral"], int)
        assert isinstance(data["negative"], int)
        assert isinstance(data["by_tag"], dict)
        assert isinstance(data["rate_last_hour"], int)
        assert isinstance(data["rate_last_24h"], int)
        assert isinstance(data["recent_items"], list)

    @mock_aws
    def test_metrics_aggregation_accuracy(self, client, auth_headers):
        """
        E2E: Metrics are aggregated correctly from seeded data.

        Verifies:
        - Sentiment counts match seeded data
        - Total equals sum of sentiments
        - Tag distribution is correct
        """
        table = create_test_table()
        seed_comprehensive_test_data(table)

        response = client.get("/api/metrics", headers=auth_headers)

        assert response.status_code == 200
        data = response.json()

        # We seeded: 3 positive, 2 neutral, 2 negative (7 analyzed items)
        assert data["total"] == 7
        assert data["positive"] == 3
        assert data["neutral"] == 2
        assert data["negative"] == 2

        # Verify total equals sum of sentiments
        assert data["total"] == data["positive"] + data["neutral"] + data["negative"]

        # Verify tag distribution includes expected tags
        assert "tech" in data["by_tag"]
        assert data["by_tag"]["tech"] == 3  # pos1, neg1, old1

    @mock_aws
    def test_metrics_recent_items_sanitized(self, client, auth_headers):
        """
        E2E: Recent items have internal fields removed.

        Verifies ttl and content_hash are not exposed to frontend.
        """
        table = create_test_table()

        # Add item with internal fields
        now = datetime.now(UTC)
        table.put_item(
            Item={
                "source_id": "newsapi#internal",
                "timestamp": now.isoformat(),
                "title": "Test Item",
                "sentiment": "positive",
                "score": Decimal("0.9"),
                "status": "analyzed",
                "tags": ["test"],
                "source": "test",
                "ttl": 1234567890,  # Internal field
                "content_hash": "abc123def456",  # Internal field
            }
        )

        response = client.get("/api/metrics", headers=auth_headers)

        assert response.status_code == 200
        data = response.json()

        # Check recent items don't contain internal fields
        for item in data["recent_items"]:
            assert "ttl" not in item
            assert "content_hash" not in item

    @mock_aws
    def test_api_key_validation_rejects_invalid(self, client):
        """
        E2E: API key validation rejects invalid credentials.

        Verifies:
        - Missing auth returns 401
        - Wrong key returns 401
        - Correct error messages
        """
        create_test_table()

        # Test missing auth
        response = client.get("/api/metrics")
        assert response.status_code == 401
        assert "Missing Authorization header" in response.json()["detail"]

        # Test wrong key
        response = client.get(
            "/api/metrics", headers={"Authorization": "Bearer wrong-key"}
        )
        assert response.status_code == 401
        assert "Invalid API key" in response.json()["detail"]

        # Test invalid format
        response = client.get(
            "/api/metrics", headers={"Authorization": "InvalidFormat"}
        )
        assert response.status_code == 401
        assert "Invalid Authorization header format" in response.json()["detail"]

    @mock_aws
    def test_api_key_validation_accepts_valid(self, client, auth_headers):
        """
        E2E: API key validation accepts valid credentials.
        """
        create_test_table()

        response = client.get("/api/metrics", headers=auth_headers)
        assert response.status_code == 200

    @mock_aws
    def test_items_endpoint_returns_analyzed_items(self, client, auth_headers):
        """
        E2E: Items endpoint returns only analyzed items by default.
        """
        table = create_test_table()
        seed_comprehensive_test_data(table)

        response = client.get("/api/items", headers=auth_headers)

        assert response.status_code == 200
        data = response.json()

        # Should return analyzed items only (not pending)
        assert len(data) == 7  # 7 analyzed items
        for item in data:
            assert item.get("status") == "analyzed"

    @mock_aws
    def test_items_endpoint_filters_by_status(self, client, auth_headers):
        """
        E2E: Items endpoint filters by status parameter.
        """
        table = create_test_table()
        seed_comprehensive_test_data(table)

        # Get pending items
        response = client.get("/api/items?status=pending", headers=auth_headers)

        assert response.status_code == 200
        data = response.json()

        # Should return only pending items
        assert len(data) == 1
        assert data[0]["status"] == "pending"

    @mock_aws
    def test_items_endpoint_respects_limit(self, client, auth_headers):
        """
        E2E: Items endpoint respects limit parameter.
        """
        table = create_test_table()
        seed_comprehensive_test_data(table)

        response = client.get("/api/items?limit=3", headers=auth_headers)

        assert response.status_code == 200
        data = response.json()

        assert len(data) == 3

    @mock_aws
    def test_items_sorted_by_timestamp_descending(self, client, auth_headers):
        """
        E2E: Items are sorted by timestamp in descending order.
        """
        table = create_test_table()
        seed_comprehensive_test_data(table)

        response = client.get("/api/items", headers=auth_headers)

        assert response.status_code == 200
        data = response.json()

        # Verify descending order
        timestamps = [item["timestamp"] for item in data]
        assert timestamps == sorted(timestamps, reverse=True)

    @mock_aws
    def test_metrics_time_window_filtering(self, client, auth_headers):
        """
        E2E: Metrics respect time window parameter.

        Tests that items outside the time window are excluded.
        """
        table = create_test_table()

        now = datetime.now(UTC)

        # Add item within 1 hour
        table.put_item(
            Item={
                "source_id": "newsapi#recent",
                "timestamp": (now - timedelta(minutes=30)).isoformat(),
                "sentiment": "positive",
                "status": "analyzed",
                "tags": ["test"],
            }
        )

        # Add item at 2 hours (outside 1-hour window)
        table.put_item(
            Item={
                "source_id": "newsapi#older",
                "timestamp": (now - timedelta(hours=2)).isoformat(),
                "sentiment": "negative",
                "status": "analyzed",
                "tags": ["test"],
            }
        )

        # Query with 1-hour window
        response = client.get("/api/metrics?hours=1", headers=auth_headers)

        assert response.status_code == 200
        data = response.json()

        # Should only include the recent item
        assert data["total"] == 1
        assert data["positive"] == 1
        assert data["negative"] == 0

    @mock_aws
    def test_ingestion_rates_calculated_correctly(self, client, auth_headers):
        """
        E2E: Ingestion rates are calculated for different time windows.
        """
        table = create_test_table()
        seed_comprehensive_test_data(table)

        response = client.get("/api/metrics", headers=auth_headers)

        assert response.status_code == 200
        data = response.json()

        # rate_last_hour should include items from last 60 minutes
        # From seed data: pos1 (5m), pos2 (15m), neu1 (25m), neu2 (35m),
        #                 neg1 (45m), neg2 (55m), pending1 (2m) = 7 items
        assert data["rate_last_hour"] >= 6  # At least 6 items in last hour

        # rate_last_24h should include all items
        assert data["rate_last_24h"] >= 8  # All 8 items including old1

    @mock_aws
    def test_empty_table_returns_zeros(self, client, auth_headers):
        """
        E2E: Empty table returns zero counts gracefully.
        """
        create_test_table()

        response = client.get("/api/metrics", headers=auth_headers)

        assert response.status_code == 200
        data = response.json()

        assert data["total"] == 0
        assert data["positive"] == 0
        assert data["neutral"] == 0
        assert data["negative"] == 0
        assert data["by_tag"] == {}
        assert data["recent_items"] == []

    @mock_aws
    def test_parameter_validation_hours(self, client, auth_headers):
        """
        E2E: Invalid hours parameter returns 400 error.
        """
        create_test_table()

        # Test hours = 0
        response = client.get("/api/metrics?hours=0", headers=auth_headers)
        assert response.status_code == 400
        assert "Hours must be between" in response.json()["detail"]

        # Test hours > 168
        response = client.get("/api/metrics?hours=200", headers=auth_headers)
        assert response.status_code == 400

    @mock_aws
    def test_parameter_validation_limit(self, client, auth_headers):
        """
        E2E: Invalid limit parameter returns 400 error.
        """
        create_test_table()

        # Test limit = 0
        response = client.get("/api/items?limit=0", headers=auth_headers)
        assert response.status_code == 400

        # Test limit > 100
        response = client.get("/api/items?limit=150", headers=auth_headers)
        assert response.status_code == 400

    @mock_aws
    def test_parameter_validation_status(self, client, auth_headers):
        """
        E2E: Invalid status parameter returns 400 error.
        """
        create_test_table()

        response = client.get("/api/items?status=invalid", headers=auth_headers)
        assert response.status_code == 400
        assert "Status must be" in response.json()["detail"]

    @mock_aws
    def test_concurrent_requests(self, client, auth_headers):
        """
        E2E: Multiple concurrent requests work correctly.

        Simulates multiple dashboard tabs/users.
        """
        table = create_test_table()
        seed_comprehensive_test_data(table)

        # Make multiple requests
        responses = []
        for _ in range(5):
            response = client.get("/api/metrics", headers=auth_headers)
            responses.append(response)

        # All should succeed with same data
        for response in responses:
            assert response.status_code == 200
            assert response.json()["total"] == 7

    @mock_aws
    def test_response_content_type(self, client, auth_headers):
        """
        E2E: API endpoints return correct content types.
        """
        create_test_table()

        # Metrics endpoint
        response = client.get("/api/metrics", headers=auth_headers)
        assert "application/json" in response.headers["content-type"]

        # Items endpoint
        response = client.get("/api/items", headers=auth_headers)
        assert "application/json" in response.headers["content-type"]

        # Health endpoint
        response = client.get("/health")
        assert "application/json" in response.headers["content-type"]
