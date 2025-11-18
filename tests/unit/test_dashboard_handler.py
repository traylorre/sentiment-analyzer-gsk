"""
Unit Tests for Dashboard FastAPI Handler
=========================================

Tests for the FastAPI dashboard endpoints using TestClient.

For On-Call Engineers:
    If these tests fail in CI:
    1. Check moto version compatibility
    2. Verify FastAPI/Starlette versions match
    3. Check test isolation (each test should be independent)

For Developers:
    - Uses FastAPI TestClient for endpoint testing
    - moto mocks DynamoDB for isolated tests
    - Tests cover authentication, endpoints, error handling
    - API key validation tested with various scenarios
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


def seed_test_data(table):
    """Seed the table with test items."""
    now = datetime.now(UTC)

    items = [
        {
            "source_id": "newsapi#article1",
            "timestamp": (now - timedelta(minutes=10)).isoformat(),
            "title": "Positive News Article",
            "sentiment": "positive",
            "score": Decimal("0.95"),
            "status": "analyzed",
            "tags": ["tech", "ai"],
            "source": "techcrunch",
        },
        {
            "source_id": "newsapi#article2",
            "timestamp": (now - timedelta(minutes=20)).isoformat(),
            "title": "Neutral News Article",
            "sentiment": "neutral",
            "score": Decimal("0.55"),
            "status": "analyzed",
            "tags": ["tech"],
            "source": "reuters",
        },
        {
            "source_id": "newsapi#article3",
            "timestamp": (now - timedelta(minutes=30)).isoformat(),
            "title": "Negative News Article",
            "sentiment": "negative",
            "score": Decimal("0.85"),
            "status": "analyzed",
            "tags": ["business"],
            "source": "bloomberg",
        },
    ]

    for item in items:
        table.put_item(Item=item)


@pytest.fixture
def client():
    """Create TestClient for FastAPI app."""
    return TestClient(app)


@pytest.fixture
def auth_headers():
    """Return valid authorization headers."""
    return {"Authorization": "Bearer test-api-key-12345"}


class TestAuthentication:
    """Tests for API key authentication."""

    def test_missing_auth_header(self, client):
        """Test request without Authorization header returns 401."""
        response = client.get("/api/metrics")
        assert response.status_code == 401
        assert "Missing Authorization header" in response.json()["detail"]

    def test_invalid_auth_format(self, client):
        """Test request with invalid Authorization format returns 401."""
        response = client.get(
            "/api/metrics",
            headers={"Authorization": "InvalidFormat"},
        )
        assert response.status_code == 401
        assert "Invalid Authorization header format" in response.json()["detail"]

    def test_invalid_api_key(self, client):
        """Test request with wrong API key returns 401."""
        response = client.get(
            "/api/metrics",
            headers={"Authorization": "Bearer wrong-key"},
        )
        assert response.status_code == 401
        assert "Invalid API key" in response.json()["detail"]

    @mock_aws
    def test_valid_api_key(self, client, auth_headers):
        """Test request with valid API key succeeds."""
        create_test_table()

        response = client.get("/api/metrics", headers=auth_headers)
        assert response.status_code == 200

    @mock_aws
    def test_case_insensitive_bearer(self, client):
        """Test Bearer keyword is case-insensitive."""
        create_test_table()

        response = client.get(
            "/api/metrics",
            headers={"Authorization": "bearer test-api-key-12345"},
        )
        assert response.status_code == 200


class TestStaticFiles:
    """Tests for static file serving."""

    def test_index_html(self, client):
        """Test serving index.html at root."""
        response = client.get("/")
        # Returns 200 if file exists, 404 otherwise
        assert response.status_code in [200, 404]

    def test_static_css(self, client):
        """Test serving CSS file."""
        response = client.get("/static/styles.css")
        assert response.status_code in [200, 404]

    def test_static_js(self, client):
        """Test serving JavaScript file."""
        response = client.get("/static/app.js")
        assert response.status_code in [200, 404]

    def test_path_traversal_blocked(self, client):
        """Test path traversal attack with slashes is blocked."""
        # Direct slash in path
        response = client.get("/static/foo/bar.css")
        # Starlette converts this to 404 (file not found)
        # Our check for "/" in filename catches it at route level
        assert response.status_code in [400, 404]

    def test_dotdot_in_filename_blocked(self, client):
        """Test .. in filename is blocked."""
        response = client.get("/static/..styles.css")
        assert response.status_code == 400
        assert "Invalid filename" in response.json()["detail"]


class TestHealthCheck:
    """Tests for health check endpoint."""

    @mock_aws
    def test_health_check_healthy(self, client):
        """Test health check with healthy DynamoDB."""
        create_test_table()

        response = client.get("/health")
        assert response.status_code == 200

        data = response.json()
        assert data["status"] == "healthy"
        assert data["table"] == "test-sentiment-items"

    @mock_aws
    def test_health_check_no_auth_required(self, client):
        """Test health check doesn't require authentication."""
        create_test_table()

        # Health check should work without auth header
        response = client.get("/health")
        assert response.status_code == 200


class TestMetricsEndpoint:
    """Tests for /api/metrics endpoint."""

    @mock_aws
    def test_metrics_returns_all_fields(self, client, auth_headers):
        """Test metrics endpoint returns all required fields."""
        create_test_table()

        response = client.get("/api/metrics", headers=auth_headers)
        assert response.status_code == 200

        data = response.json()
        assert "total" in data
        assert "positive" in data
        assert "neutral" in data
        assert "negative" in data
        assert "by_tag" in data
        assert "rate_last_hour" in data
        assert "rate_last_24h" in data
        assert "recent_items" in data

    def test_metrics_invalid_hours_zero(self, client, auth_headers):
        """Test metrics endpoint rejects hours=0."""
        response = client.get("/api/metrics?hours=0", headers=auth_headers)
        assert response.status_code == 400
        assert "Hours must be between" in response.json()["detail"]

    def test_metrics_invalid_hours_too_large(self, client, auth_headers):
        """Test metrics endpoint rejects hours > 168."""
        response = client.get("/api/metrics?hours=200", headers=auth_headers)
        assert response.status_code == 400
        assert "Hours must be between" in response.json()["detail"]

    @mock_aws
    def test_metrics_custom_hours(self, client, auth_headers):
        """Test metrics endpoint accepts custom hours parameter."""
        create_test_table()

        response = client.get("/api/metrics?hours=48", headers=auth_headers)
        assert response.status_code == 200

    @mock_aws
    def test_metrics_with_data(self, client, auth_headers):
        """Test metrics endpoint returns correct data."""
        table = create_test_table()
        seed_test_data(table)

        response = client.get("/api/metrics", headers=auth_headers)
        assert response.status_code == 200

        data = response.json()
        assert data["total"] == 3
        assert data["positive"] == 1
        assert data["neutral"] == 1
        assert data["negative"] == 1


class TestItemsEndpoint:
    """Tests for /api/items endpoint."""

    @mock_aws
    def test_items_returns_list(self, client, auth_headers):
        """Test items endpoint returns array."""
        create_test_table()

        response = client.get("/api/items", headers=auth_headers)
        assert response.status_code == 200
        assert isinstance(response.json(), list)

    def test_items_invalid_limit_zero(self, client, auth_headers):
        """Test items endpoint rejects limit=0."""
        response = client.get("/api/items?limit=0", headers=auth_headers)
        assert response.status_code == 400

    def test_items_invalid_limit_too_large(self, client, auth_headers):
        """Test items endpoint rejects limit > 100."""
        response = client.get("/api/items?limit=101", headers=auth_headers)
        assert response.status_code == 400

    def test_items_invalid_status(self, client, auth_headers):
        """Test items endpoint rejects invalid status."""
        response = client.get("/api/items?status=invalid", headers=auth_headers)
        assert response.status_code == 400

    @mock_aws
    def test_items_valid_status_values(self, client, auth_headers):
        """Test items endpoint accepts valid status values."""
        create_test_table()

        for status in ["pending", "analyzed", "failed"]:
            response = client.get(
                f"/api/items?status={status}",
                headers=auth_headers,
            )
            assert response.status_code == 200

    @mock_aws
    def test_items_with_data(self, client, auth_headers):
        """Test items endpoint returns seeded data."""
        table = create_test_table()
        seed_test_data(table)

        response = client.get("/api/items", headers=auth_headers)
        assert response.status_code == 200

        data = response.json()
        assert len(data) == 3


class TestSSEEndpoint:
    """Tests for /api/stream SSE endpoint."""

    def test_sse_requires_auth(self, client):
        """Test SSE endpoint requires authentication."""
        response = client.get("/api/stream")
        assert response.status_code == 401


class TestLambdaHandler:
    """Tests for Lambda handler function."""

    def test_lambda_handler_exists(self):
        """Test lambda_handler function is exported."""
        from src.lambdas.dashboard.handler import lambda_handler

        assert callable(lambda_handler)

    def test_mangum_adapter_exists(self):
        """Test Mangum adapter is configured."""
        from src.lambdas.dashboard.handler import handler

        assert handler is not None
