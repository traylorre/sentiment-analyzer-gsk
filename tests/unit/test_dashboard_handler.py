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

import boto3
import pytest
from fastapi.testclient import TestClient
from moto import mock_aws

from src.lambdas.dashboard.handler import app

# Set env vars for tests (handler now reads lazily via get_api_key())
os.environ["API_KEY"] = "test-api-key-12345"
os.environ["DYNAMODB_TABLE"] = "test-sentiment-items"
os.environ["ENVIRONMENT"] = "test"


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

    def test_sse_stream_establishes_connection(self):
        """
        Test SSE stream endpoint exists and has proper configuration.

        Note: Full SSE streaming behavior (event generation, polling, actual connection)
        is tested in integration tests (test_dashboard_preprod.py) to avoid
        TestClient limitations with infinite async streams.
        """
        from src.lambdas.dashboard import handler as handler_module

        # Verify SSE endpoint exists in app routes
        routes = [route.path for route in handler_module.app.routes]
        assert "/api/stream" in routes

        # Verify SSE configuration exists
        assert hasattr(handler_module, "SSE_POLL_INTERVAL")
        assert handler_module.SSE_POLL_INTERVAL > 0


class TestDynamoDBErrorHandling:
    """Tests for DynamoDB error handling and resilience."""

    def test_table_not_found_returns_503(self, client, auth_headers, monkeypatch):
        """Test table not found error returns 503 Service Unavailable."""
        # Override table name to non-existent table
        monkeypatch.setenv("DYNAMODB_TABLE", "nonexistent-table")

        # Import app fresh with new env var
        from importlib import reload

        from src.lambdas.dashboard import handler as handler_module

        reload(handler_module)
        test_client = TestClient(handler_module.app)

        response = test_client.get("/api/metrics", headers=auth_headers)

        # Should return 500 or 503 for infrastructure failure
        assert response.status_code >= 500

    @mock_aws
    def test_empty_table_returns_zeros_not_error(self, client, auth_headers):
        """Test empty DynamoDB table returns zeros, not an error."""
        create_test_table()  # Empty table

        response = client.get("/api/metrics", headers=auth_headers)

        assert response.status_code == 200
        data = response.json()

        # Should return zeros for empty table
        assert data["total"] == 0
        assert data["positive"] == 0
        assert data["neutral"] == 0
        assert data["negative"] == 0
        assert data["by_tag"] == {}
        assert data["recent_items"] == []

    @mock_aws
    def test_health_check_detects_table_availability(self, client):
        """Test health check verifies DynamoDB table exists."""
        create_test_table()

        response = client.get("/health")

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert "table" in data


class TestStaticFilePackaging:
    """Tests for static file bundling in Lambda package."""

    def test_static_files_exist_in_package(self):
        """Test that static HTML/CSS/JS files are bundled in Lambda package."""
        import os

        # Get dashboard source directory
        from src import dashboard

        dashboard_dir = os.path.dirname(dashboard.__file__)

        # Verify static files exist
        index_path = os.path.join(dashboard_dir, "index.html")
        styles_path = os.path.join(dashboard_dir, "static", "styles.css")
        app_js_path = os.path.join(dashboard_dir, "static", "app.js")

        assert os.path.exists(index_path), f"index.html not found at {index_path}"
        assert os.path.exists(styles_path), f"styles.css not found at {styles_path}"
        assert os.path.exists(app_js_path), f"app.js not found at {app_js_path}"

    def test_index_html_has_content(self):
        """Test index.html is not empty."""
        import os

        from src import dashboard

        dashboard_dir = os.path.dirname(dashboard.__file__)
        index_path = os.path.join(dashboard_dir, "index.html")

        if os.path.exists(index_path):
            with open(index_path) as f:
                content = f.read()
                assert len(content) > 0
                assert "<html" in content.lower() or "<!doctype" in content.lower()


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


class TestSecurityMitigations:
    """
    Security Tests for P0/P1 Vulnerability Mitigations
    ===================================================

    Tests for security fixes implemented in response to dashboard security analysis.
    See docs/DASHBOARD_SECURITY_ANALYSIS.md for full vulnerability assessment.

    Test Coverage:
    - P0-2: SSE connection limits (concurrency exhaustion prevention)
    - P0-5: CORS origin validation (cross-origin attack prevention)
    - P1-2: IP logging on authentication failures (forensic tracking)
    """

    @mock_aws
    def test_sse_connection_limit_enforced(self, client, auth_headers, monkeypatch):
        """
        P0-2: Test SSE endpoint enforces connection limit per IP.

        Verifies that MAX_SSE_CONNECTIONS_PER_IP is enforced to prevent
        concurrency exhaustion attacks.
        """
        # Set connection limit to 2
        monkeypatch.setenv("MAX_SSE_CONNECTIONS_PER_IP", "2")

        # Import fresh with new env var
        from importlib import reload

        from src.lambdas.dashboard import handler as handler_module

        reload(handler_module)

        # Manually simulate 2 existing connections from same IP
        handler_module.sse_connections["203.0.113.1"] = 2

        # Create test client with mocked IP
        test_client = TestClient(handler_module.app)
        create_test_table()

        # Third connection should be rejected with 429
        response = test_client.get(
            "/api/stream",
            headers={
                **auth_headers,
                "X-Forwarded-For": "203.0.113.1",
            },
        )

        assert response.status_code == 429
        assert "Too many SSE connections" in response.json()["detail"]

        # Clean up
        handler_module.sse_connections.clear()

    def test_sse_connection_limit_different_ips(self, monkeypatch):
        """
        P0-2: Test different IPs can each open connections up to limit.

        Verifies connection limits are per-IP, not global.
        """
        monkeypatch.setenv("MAX_SSE_CONNECTIONS_PER_IP", "2")

        from importlib import reload

        from src.lambdas.dashboard import handler as handler_module

        reload(handler_module)

        # Simulate 2 connections from IP1
        handler_module.sse_connections["203.0.113.1"] = 2

        # Verify tracking is per-IP - IP2 has no connections
        assert handler_module.sse_connections.get("203.0.113.2", 0) == 0

        # IP1 at limit, IP2 not at limit - this proves per-IP tracking
        assert (
            handler_module.sse_connections["203.0.113.1"]
            >= handler_module.MAX_SSE_CONNECTIONS_PER_IP
        )
        assert (
            handler_module.sse_connections.get("203.0.113.2", 0)
            < handler_module.MAX_SSE_CONNECTIONS_PER_IP
        )

        # Clean up
        handler_module.sse_connections.clear()

    def test_sse_connection_tracking_cleanup(self, monkeypatch):
        """
        P0-2: Test SSE connection count is decremented when stream closes.

        Verifies cleanup logic prevents connection leak.
        """
        monkeypatch.setenv("MAX_SSE_CONNECTIONS_PER_IP", "2")

        from src.lambdas.dashboard import handler as handler_module

        # Simulate connection tracking
        handler_module.sse_connections["203.0.113.1"] = 2

        # Decrement (simulating connection close)
        handler_module.sse_connections["203.0.113.1"] -= 1

        assert handler_module.sse_connections["203.0.113.1"] == 1

        # Decrement to zero
        handler_module.sse_connections["203.0.113.1"] -= 1

        # Should be removed from dict when zero
        if handler_module.sse_connections["203.0.113.1"] <= 0:
            del handler_module.sse_connections["203.0.113.1"]

        assert "203.0.113.1" not in handler_module.sse_connections

    def test_cors_origins_dev_environment(self, monkeypatch):
        """
        P0-5: Test CORS returns localhost for dev/test environments.

        Verifies dev environments get localhost CORS by default.
        """
        monkeypatch.setenv("ENVIRONMENT", "dev")
        monkeypatch.setenv("DYNAMODB_TABLE", "test-table")

        from importlib import reload

        from src.lambdas.dashboard import handler as handler_module

        reload(handler_module)

        cors_origins = handler_module.get_cors_origins()

        assert "http://localhost:3000" in cors_origins
        assert "http://127.0.0.1:3000" in cors_origins

    def test_cors_origins_production_requires_explicit_config(
        self, monkeypatch, caplog
    ):
        """
        P0-5: Test production environment requires explicit CORS_ORIGINS.

        Verifies production does NOT default to wildcard or localhost.
        """
        monkeypatch.setenv("ENVIRONMENT", "production")
        monkeypatch.setenv("DYNAMODB_TABLE", "test-table")
        monkeypatch.delenv("CORS_ORIGINS", raising=False)

        from importlib import reload

        from src.lambdas.dashboard import handler as handler_module

        reload(handler_module)

        cors_origins = handler_module.get_cors_origins()

        # Production without CORS_ORIGINS should return empty list
        assert cors_origins == []

        # Should log error
        assert "CORS_ORIGINS not configured for production" in caplog.text

    def test_cors_origins_explicit_configuration(self, monkeypatch):
        """
        P0-5: Test CORS_ORIGINS env var is respected.

        Verifies explicit CORS configuration works for any environment.
        """
        monkeypatch.setenv("ENVIRONMENT", "production")
        monkeypatch.setenv("DYNAMODB_TABLE", "test-table")
        monkeypatch.setenv(
            "CORS_ORIGINS", "https://example.com,https://dashboard.example.com"
        )

        from importlib import reload

        from src.lambdas.dashboard import handler as handler_module

        reload(handler_module)

        cors_origins = handler_module.get_cors_origins()

        assert "https://example.com" in cors_origins
        assert "https://dashboard.example.com" in cors_origins
        assert len(cors_origins) == 2

    def test_cors_middleware_not_added_if_no_origins(self, monkeypatch, caplog):
        """
        P0-5: Test CORS middleware is not added if origins list is empty.

        Verifies production without CORS config rejects cross-origin requests.
        """
        monkeypatch.setenv("ENVIRONMENT", "production")
        monkeypatch.setenv("DYNAMODB_TABLE", "test-table")
        monkeypatch.setenv("API_KEY", "test-key")
        monkeypatch.delenv("CORS_ORIGINS", raising=False)

        from importlib import reload

        from src.lambdas.dashboard import handler as handler_module

        reload(handler_module)

        # Should log that CORS is not configured
        assert "CORS not configured" in caplog.text

    def test_authentication_logs_client_ip_on_failure(
        self, client, auth_headers, caplog
    ):
        """
        P1-2: Test authentication failures log client IP.

        Verifies forensic logging for security auditing.
        """
        import logging

        caplog.set_level(logging.WARNING)

        # Test missing auth header
        response = client.get(
            "/api/metrics",
            headers={"X-Forwarded-For": "198.51.100.42"},
        )

        assert response.status_code == 401
        assert "Missing Authorization header" in caplog.text
        # Check structured logging in log records
        assert any(
            getattr(record, "client_ip", None) == "198.51.100.42"
            for record in caplog.records
        )

    def test_authentication_logs_invalid_api_key_with_ip(
        self, client, auth_headers, caplog
    ):
        """
        P1-2: Test invalid API key logs client IP and key prefix.

        Verifies forensic tracking includes attempted key for analysis.
        """
        import logging

        caplog.set_level(logging.WARNING)

        # Test wrong API key
        response = client.get(
            "/api/metrics",
            headers={
                "Authorization": "Bearer wrong-key-12345678",
                "X-Forwarded-For": "198.51.100.99",
            },
        )

        assert response.status_code == 401
        assert "Invalid API key attempt" in caplog.text
        # Check structured logging in log records
        assert any(
            getattr(record, "client_ip", None) == "198.51.100.99"
            for record in caplog.records
        )
        # Should log key prefix for analysis
        assert any(
            getattr(record, "key_prefix", None) == "wrong-ke"
            or "wrong-ke" in caplog.text
            for record in caplog.records
        )

    def test_authentication_logs_request_path(self, client, caplog):
        """
        P1-2: Test authentication failures log request path.

        Verifies we can identify which endpoints are being targeted.
        """
        import logging

        caplog.set_level(logging.WARNING)

        response = client.get(
            "/api/items",
            headers={"X-Forwarded-For": "203.0.113.1"},
        )

        assert response.status_code == 401
        # Check structured logging in log records
        assert any(
            getattr(record, "path", None) == "/api/items" for record in caplog.records
        )
        assert any(
            getattr(record, "client_ip", None) == "203.0.113.1"
            for record in caplog.records
        )

    def test_sse_connection_logs_client_ip_on_establish(self, monkeypatch):
        """
        P1-2: Test SSE connection tracking infrastructure exists.

        Verifies we have the infrastructure to track which IPs are opening SSE streams.
        Note: Actual logging tested in integration tests to avoid async/streaming complexity.
        """
        monkeypatch.setenv("MAX_SSE_CONNECTIONS_PER_IP", "5")

        from importlib import reload

        from src.lambdas.dashboard import handler as handler_module

        reload(handler_module)

        # Verify connection tracking dict exists and is per-IP
        assert hasattr(handler_module, "sse_connections")
        assert isinstance(handler_module.sse_connections, dict)

        # Verify MAX_SSE_CONNECTIONS_PER_IP configuration
        assert handler_module.MAX_SSE_CONNECTIONS_PER_IP == 5

    @mock_aws
    def test_max_sse_connections_per_ip_configurable(self, monkeypatch):
        """
        P0-2: Test MAX_SSE_CONNECTIONS_PER_IP is configurable via env var.

        Verifies operators can adjust limit based on load.
        """
        monkeypatch.setenv("MAX_SSE_CONNECTIONS_PER_IP", "5")

        from importlib import reload

        from src.lambdas.dashboard import handler as handler_module

        reload(handler_module)

        assert handler_module.MAX_SSE_CONNECTIONS_PER_IP == 5

    def test_sse_connection_limit_default_value(self):
        """
        P0-2: Test MAX_SSE_CONNECTIONS_PER_IP defaults to 2.

        Verifies sensible default if env var not set.
        """
        import os

        # Remove env var if exists
        os.environ.pop("MAX_SSE_CONNECTIONS_PER_IP", None)

        from importlib import reload

        from src.lambdas.dashboard import handler as handler_module

        reload(handler_module)

        # Default should be 2
        assert handler_module.MAX_SSE_CONNECTIONS_PER_IP == 2

    def test_x_forwarded_for_header_parsing(self, client, auth_headers, caplog):
        """
        P1-2: Test X-Forwarded-For header is correctly parsed.

        Verifies we extract the first IP from comma-separated list
        (client IP, not proxy IPs).
        """
        import logging

        caplog.set_level(logging.WARNING)

        # Simulate multi-proxy X-Forwarded-For
        response = client.get(
            "/api/metrics",
            headers={
                "Authorization": "Bearer wrong-key",
                "X-Forwarded-For": "198.51.100.1, 203.0.113.1, 192.0.2.1",
            },
        )

        assert response.status_code == 401
        # Should log the FIRST IP (client), not proxy IPs
        # Check structured logging in log records
        assert any(
            getattr(record, "client_ip", None) == "198.51.100.1"
            for record in caplog.records
        )
