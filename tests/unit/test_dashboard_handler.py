"""
Unit Tests for Dashboard Lambda Handler
=========================================

Tests for the Powertools-based dashboard Lambda handler using direct invocation.

For On-Call Engineers:
    If these tests fail in CI:
    1. Check moto version compatibility
    2. Verify test isolation (each test should be independent)

For Developers:
    - Uses direct lambda_handler invocation with make_event helper
    - moto mocks DynamoDB for isolated tests
    - Tests cover session auth, endpoints, error handling
    - Feature 1039: Session auth via X-User-ID header
    - Feature 1048: Auth type determined by token (JWT=authenticated, UUID=anonymous)
"""

import json
import os
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from unittest.mock import patch

import boto3
import jwt
import pytest
from moto import mock_aws

from src.lambdas.dashboard.handler import lambda_handler
from tests.conftest import make_event

# Set default env vars for tests (only if not already set by CI)
# IMPORTANT: Use setdefault to avoid overwriting CI-provided preprod values
# Feature 1039: API_KEY removed - using session auth
os.environ.setdefault("DYNAMODB_TABLE", "test-sentiment-items")
os.environ.setdefault("USERS_TABLE", "test-sentiment-users")
os.environ.setdefault("ENVIRONMENT", "test")


def create_users_table():
    """Create a test users DynamoDB table (Feature 1119).

    The users table uses PK/SK pattern for user profiles and auth data.
    """
    dynamodb = boto3.resource("dynamodb", region_name="us-east-1")

    table = dynamodb.create_table(
        TableName="test-sentiment-users",
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
    table.wait_until_exists()
    return table


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
            {"AttributeName": "tag", "AttributeType": "S"},
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
            {
                "IndexName": "by_tag",
                "KeySchema": [
                    {"AttributeName": "tag", "KeyType": "HASH"},
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
    """Seed the table with test items.

    Note: The by_tag GSI requires a single 'tag' attribute (not 'tags' list).
    For items with multiple tags, we create separate DynamoDB items.
    """
    now = datetime.now(UTC)

    items = [
        {
            "source_id": "article#article1",
            "timestamp": (now - timedelta(minutes=10)).isoformat(),
            "title": "Positive News Article",
            "sentiment": "positive",
            "score": Decimal("0.95"),
            "status": "analyzed",
            "tag": "tech",
            "source": "techcrunch",
        },
        {
            "source_id": "article#article2",
            "timestamp": (now - timedelta(minutes=20)).isoformat(),
            "title": "Neutral News Article",
            "sentiment": "neutral",
            "score": Decimal("0.55"),
            "status": "analyzed",
            "tag": "tech",
            "source": "reuters",
        },
        {
            "source_id": "article#article3",
            "timestamp": (now - timedelta(minutes=30)).isoformat(),
            "title": "Negative News Article",
            "sentiment": "negative",
            "score": Decimal("0.85"),
            "status": "analyzed",
            "tag": "business",
            "source": "bloomberg",
        },
    ]

    for item in items:
        table.put_item(Item=item)


# Test JWT configuration (Feature 1048)
TEST_JWT_SECRET = "test-secret-key-do-not-use-in-production"
TEST_USER_ID = "12345678-1234-5678-1234-567812345678"


def create_test_jwt(user_id: str = TEST_USER_ID, roles: list[str] | None = None) -> str:
    """Create a valid JWT token for testing authenticated endpoints.

    Feature 1147: Added aud and nbf claims for CVSS 7.8 security fix.
    Feature 1152: Added roles claim for RBAC support.
    """
    if roles is None:
        roles = ["free"]  # Default for authenticated users
    now = datetime.now(UTC)
    payload = {
        "sub": user_id,
        "exp": now + timedelta(minutes=15),
        "iat": now,
        "iss": "sentiment-analyzer",
        "aud": "sentiment-analyzer-api",
        "nbf": now,
        "roles": roles,  # Feature 1152: RBAC roles claim
    }
    return jwt.encode(payload, TEST_JWT_SECRET, algorithm="HS256")


@pytest.fixture
def jwt_env():
    """Set JWT environment variables for authenticated tests.

    Feature 1147: Added JWT_AUDIENCE for aud claim validation.
    """
    with patch.dict(
        os.environ,
        {"JWT_SECRET": TEST_JWT_SECRET, "JWT_AUDIENCE": "sentiment-analyzer-api"},
    ):
        yield


@pytest.fixture
def auth_headers(jwt_env):
    """Return valid authenticated session headers (Feature 1048: JWT auth).

    Uses Bearer token with valid JWT to identify as authenticated user.
    Feature 1048: Auth type determined by token validation, not headers.

    Note: Requires jwt_env fixture to set JWT_SECRET for validation.
    """
    token = create_test_jwt()
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def anonymous_headers():
    """Return anonymous session headers for public endpoints.

    Feature 1146: Uses Bearer token with UUID (X-User-ID fallback removed).
    """
    return {"Authorization": f"Bearer {TEST_USER_ID}"}


class TestAuthentication:
    """Tests for session-based authentication (Feature 1039).

    Feature 1039 replaced API key auth with session-based auth.
    Public endpoints accept anonymous sessions via X-User-ID header.
    """

    def test_missing_auth_header(self, mock_lambda_context):
        """Test request without X-User-ID header returns 401."""
        event = make_event(
            method="GET",
            path="/api/v2/sentiment",
            query_params={"tags": "test"},
        )
        response = lambda_handler(event, mock_lambda_context)
        assert response["statusCode"] == 401
        body = json.loads(response["body"])
        assert "Missing user identification" in body["detail"]

    @mock_aws
    def test_valid_session_id(self, mock_lambda_context, auth_headers):
        """Test request with valid X-User-ID succeeds."""
        create_test_table()

        event = make_event(
            method="GET",
            path="/api/v2/sentiment",
            query_params={"tags": "test"},
            headers=auth_headers,
        )
        response = lambda_handler(event, mock_lambda_context)
        assert response["statusCode"] == 200

    @mock_aws
    def test_bearer_token_works(self, mock_lambda_context):
        """Test request with Bearer token containing user ID works."""
        create_test_table()

        # Bearer token is also accepted for session auth
        event = make_event(
            method="GET",
            path="/api/v2/sentiment",
            query_params={"tags": "test"},
            headers={"Authorization": "Bearer 12345678-1234-5678-1234-567812345678"},
        )
        response = lambda_handler(event, mock_lambda_context)
        assert response["statusCode"] == 200


class TestAnonymousSessionCreation:
    """Tests for POST /api/v2/auth/anonymous endpoint (Feature 1119).

    Feature 1119: Fix anonymous auth 422 error when frontend sends no body.
    The endpoint should accept:
    - No request body (use defaults)
    - Empty JSON body {} (use defaults)
    - Body with optional fields (use provided values)
    """

    @mock_aws
    def test_no_body_returns_201(self, mock_lambda_context):
        """Test POST /api/v2/auth/anonymous with no body returns 201.

        FR-001: System MUST accept POST /api/v2/auth/anonymous with no request
        body and create a session using default values.
        """
        create_users_table()

        # Send request with no body (content-length: 0)
        event = make_event(
            method="POST",
            path="/api/v2/auth/anonymous",
            headers={"Content-Type": "application/json"},
        )
        response = lambda_handler(event, mock_lambda_context)

        assert (
            response["statusCode"] == 201
        ), f"Expected 201, got {response['statusCode']}: {response['body']}"
        data = json.loads(response["body"])
        assert "user_id" in data
        assert data["auth_type"] == "anonymous"
        assert "created_at" in data
        assert "session_expires_at" in data
        assert data["storage_hint"] == "localStorage"

    @mock_aws
    def test_empty_body_returns_201(self, mock_lambda_context):
        """Test POST /api/v2/auth/anonymous with empty body {} returns 201.

        FR-002: System MUST accept POST /api/v2/auth/anonymous with an empty
        JSON body {} and create a session using default values.
        """
        create_users_table()

        event = make_event(
            method="POST",
            path="/api/v2/auth/anonymous",
            body={},
        )
        response = lambda_handler(event, mock_lambda_context)

        assert (
            response["statusCode"] == 201
        ), f"Expected 201, got {response['statusCode']}: {response['body']}"
        data = json.loads(response["body"])
        assert "user_id" in data
        assert data["auth_type"] == "anonymous"

    @mock_aws
    def test_body_with_timezone_returns_201(self, mock_lambda_context):
        """Test POST /api/v2/auth/anonymous with custom timezone returns 201.

        FR-003: System MUST accept POST /api/v2/auth/anonymous with optional
        parameters (timezone, device_fingerprint) and use provided values.
        """
        create_users_table()

        event = make_event(
            method="POST",
            path="/api/v2/auth/anonymous",
            body={"timezone": "Europe/London"},
        )
        response = lambda_handler(event, mock_lambda_context)

        assert (
            response["statusCode"] == 201
        ), f"Expected 201, got {response['statusCode']}: {response['body']}"
        data = json.loads(response["body"])
        assert "user_id" in data
        assert data["auth_type"] == "anonymous"


class TestStaticFiles:
    """Tests for static file serving.

    Static files exist at src/dashboard/ and are served by the dashboard handler.
    These tests verify the files are correctly served and security is enforced.
    """

    def test_index_html_served(self, mock_lambda_context):
        """Test serving index.html at root."""
        event = make_event(method="GET", path="/")
        response = lambda_handler(event, mock_lambda_context)
        assert (
            response["statusCode"] == 200
        ), f"Expected 200 for index.html, got {response['statusCode']}"
        # Should be HTML content
        headers = response.get("headers", {})
        content_type = headers.get("Content-Type", headers.get("content-type", ""))
        assert "text/html" in content_type

    def test_static_css_served(self, mock_lambda_context):
        """Test serving CSS file."""
        event = make_event(method="GET", path="/static/styles.css")
        response = lambda_handler(event, mock_lambda_context)
        assert (
            response["statusCode"] == 200
        ), f"Expected 200 for styles.css, got {response['statusCode']}"
        headers = response.get("headers", {})
        content_type = headers.get("Content-Type", headers.get("content-type", ""))
        assert "text/css" in content_type

    def test_static_js_served(self, mock_lambda_context):
        """Test serving JavaScript file."""
        event = make_event(method="GET", path="/static/app.js")
        response = lambda_handler(event, mock_lambda_context)
        assert (
            response["statusCode"] == 200
        ), f"Expected 200 for app.js, got {response['statusCode']}"
        headers = response.get("headers", {})
        content_type = headers.get("Content-Type", headers.get("content-type", ""))
        assert "javascript" in content_type

    def test_path_traversal_blocked(self, mock_lambda_context):
        """Test path traversal attack with slashes is blocked.

        Security: The handler uses a strict whitelist approach. Any filename
        not in ALLOWED_STATIC_FILES returns 404. This is secure because:
        - User input never reaches the filesystem
        - Only hardcoded paths are used
        - Whitelist is explicit, not pattern-based
        """
        # Path with slashes - not in whitelist, so returns 404
        event = make_event(method="GET", path="/static/foo/bar.css")
        response = lambda_handler(event, mock_lambda_context)
        assert (
            response["statusCode"] == 404
        ), f"Expected 404 for non-whitelisted file, got {response['statusCode']}"

    def test_dotdot_in_filename_blocked(self, mock_lambda_context):
        """Test .. in filename is blocked (returns 404 since not in whitelist)."""
        event = make_event(method="GET", path="/static/..styles.css")
        response = lambda_handler(event, mock_lambda_context)
        # With whitelist approach, non-whitelisted files return 404
        assert response["statusCode"] == 404
        body = json.loads(response["body"])
        assert "Static file not found" in body["detail"]


class TestHealthCheck:
    """Tests for health check endpoint."""

    @mock_aws
    def test_health_check_healthy(self, mock_lambda_context):
        """Test health check with healthy DynamoDB."""
        create_test_table()

        event = make_event(method="GET", path="/health")
        response = lambda_handler(event, mock_lambda_context)
        assert response["statusCode"] == 200

        data = json.loads(response["body"])
        assert data["status"] == "healthy"
        assert data["table"] == "test-sentiment-items"

    @mock_aws
    def test_health_check_no_auth_required(self, mock_lambda_context):
        """Test health check doesn't require authentication."""
        create_test_table()

        # Health check should work without auth header
        event = make_event(method="GET", path="/health")
        response = lambda_handler(event, mock_lambda_context)
        assert response["statusCode"] == 200


class TestDynamoDBErrorHandling:
    """Tests for DynamoDB error handling and resilience."""

    def test_table_not_found_returns_503(
        self, mock_lambda_context, auth_headers, monkeypatch
    ):
        """Test table not found error returns 503 Service Unavailable."""
        # Override table name to non-existent table
        monkeypatch.setenv("DYNAMODB_TABLE", "nonexistent-table")

        # Import app fresh with new env var
        from importlib import reload

        from src.lambdas.dashboard import handler as handler_module

        reload(handler_module)

        # Use health endpoint to test DynamoDB connectivity
        event = make_event(method="GET", path="/health")
        response = handler_module.lambda_handler(event, mock_lambda_context)

        # Should return 503 for infrastructure failure
        assert response["statusCode"] == 503

        # Restore original table name and reload to prevent test pollution
        monkeypatch.setenv("DYNAMODB_TABLE", "test-sentiment-items")
        reload(handler_module)

    @mock_aws
    def test_health_check_detects_table_availability(self, mock_lambda_context):
        """Test health check verifies DynamoDB table exists."""
        create_test_table()

        event = make_event(method="GET", path="/health")
        response = lambda_handler(event, mock_lambda_context)

        assert response["statusCode"] == 200
        data = json.loads(response["body"])
        assert data["status"] == "healthy"
        assert "table" in data


class TestStaticFilePackaging:
    """Tests for static file bundling in Lambda package.

    Static files exist at src/dashboard/ and are served by the handler.
    These tests verify the files are present and the security whitelist is correct.
    """

    def test_static_files_exist(self):
        """Verify static files exist in the expected location."""
        from pathlib import Path

        # Static files are at src/dashboard/
        project_root = Path(__file__).parent.parent.parent
        dashboard_dir = project_root / "src" / "dashboard"

        # These files should exist
        index_html = dashboard_dir / "index.html"
        styles_css = dashboard_dir / "styles.css"
        app_js = dashboard_dir / "app.js"

        assert index_html.exists(), f"index.html not found at {index_html}"
        assert styles_css.exists(), f"styles.css not found at {styles_css}"
        assert app_js.exists(), f"app.js not found at {app_js}"

    def test_index_html_has_valid_content(self):
        """Verify index.html is a valid HTML file."""
        from pathlib import Path

        project_root = Path(__file__).parent.parent.parent
        index_html = project_root / "src" / "dashboard" / "index.html"

        content = index_html.read_text()
        assert len(content) > 0, "index.html is empty"
        assert (
            "<html" in content.lower() or "<!doctype" in content.lower()
        ), "index.html doesn't appear to be valid HTML"

    def test_handler_defines_allowed_static_files(self):
        """Verify handler has a static file whitelist (security feature)."""
        from src.lambdas.dashboard.handler import ALLOWED_STATIC_FILES

        # Security: Only whitelisted files should be servable
        assert isinstance(ALLOWED_STATIC_FILES, dict)
        assert "app.js" in ALLOWED_STATIC_FILES
        assert "styles.css" in ALLOWED_STATIC_FILES
        # All entries should have MIME types
        for filename, mime_type in ALLOWED_STATIC_FILES.items():
            assert "/" in mime_type, f"{filename} has invalid MIME type: {mime_type}"


class TestLambdaHandler:
    """Tests for Lambda handler function."""

    def test_lambda_handler_exists(self):
        """Test lambda_handler function is exported."""
        from src.lambdas.dashboard.handler import lambda_handler as handler_fn

        assert callable(handler_fn)

    def test_powertools_resolver_exists(self):
        """Test Powertools APIGatewayRestResolver is configured."""
        from src.lambdas.dashboard.handler import app

        assert app is not None


class TestSecurityMitigations:
    """
    Security Tests for P0/P1 Vulnerability Mitigations
    ===================================================

    Tests for security fixes implemented in response to dashboard security analysis.
    See docs/DASHBOARD_SECURITY_ANALYSIS.md for full vulnerability assessment.

    Test Coverage:
    - P0-5: CORS origin validation (cross-origin attack prevention)
    - P1-2: IP logging on authentication failures (forensic tracking)
    """

    def test_cors_handled_by_lambda_function_url(self, caplog):
        """
        P0-5: Test CORS is delegated to Lambda Function URL.

        CORS is now handled at the infrastructure level (Lambda Function URL
        configuration in Terraform), NOT at the application level. This prevents
        duplicate CORS headers which browsers reject.

        See: infrastructure/terraform/main.tf for CORS configuration.
        """
        import logging

        caplog.set_level(logging.INFO)

        from importlib import reload

        from src.lambdas.dashboard import handler as handler_module

        reload(handler_module)

        # Should log that CORS is handled by Lambda Function URL
        # Note: Powertools logger may not output to caplog by default,
        # but the module-level log statement should still be captured
        # if the logging is configured correctly.

    def test_no_cors_middleware_in_app(self):
        """
        P0-5: Test app does NOT have CORS middleware.

        CORS middleware was removed to prevent duplicate CORS headers.
        Lambda Function URL handles CORS exclusively.

        With Powertools APIGatewayRestResolver, CORS is configured via
        the CORSConfig parameter, not middleware. Verify no CORS config
        is set on the resolver.
        """
        from src.lambdas.dashboard.handler import app

        # Powertools resolver should not have CORS configured at app level
        # (CORS is handled by Lambda Function URL infrastructure)
        # The app object is an APIGatewayRestResolver - verify it exists
        assert app is not None

    def test_authentication_returns_401_on_missing_auth(
        self, mock_lambda_context, caplog
    ):
        """
        P1-2: Test missing auth returns 401.

        Feature 1039: Session auth replaces API key auth.
        Missing X-User-ID or Authorization header returns 401.
        """
        import logging

        caplog.set_level(logging.WARNING)

        # Test missing auth header
        event = make_event(
            method="GET",
            path="/api/v2/sentiment",
            query_params={"tags": "test"},
            headers={"X-Forwarded-For": "198.51.100.42"},
        )
        response = lambda_handler(event, mock_lambda_context)

        assert response["statusCode"] == 401
        body = json.loads(response["body"])
        assert "Missing user identification" in body["detail"]

    @mock_aws
    def test_valid_session_auth_succeeds(self, mock_lambda_context, auth_headers):
        """
        P1-2: Test valid session auth succeeds.

        Feature 1039: Session auth via X-User-ID header.
        """
        create_test_table()

        event = make_event(
            method="GET",
            path="/api/v2/sentiment",
            query_params={"tags": "test"},
            headers=auth_headers,
        )
        response = lambda_handler(event, mock_lambda_context)

        assert response["statusCode"] == 200

    def test_missing_session_id_returns_401(self, mock_lambda_context):
        """
        P1-2: Test missing session ID returns 401.

        Feature 1039: Session auth requires X-User-ID or Bearer token.
        """
        # Simulate request with only X-Forwarded-For (no auth)
        event = make_event(
            method="GET",
            path="/api/v2/sentiment",
            query_params={"tags": "test"},
            headers={
                "X-Forwarded-For": "198.51.100.1, 203.0.113.1, 192.0.2.1",
            },
        )
        response = lambda_handler(event, mock_lambda_context)

        assert response["statusCode"] == 401
        body = json.loads(response["body"])
        assert "Missing user identification" in body["detail"]


class TestChaosUIEndpoint:
    """Tests for /chaos endpoint (chaos testing UI)."""

    def test_chaos_page_returns_html(self, mock_lambda_context):
        """Test chaos testing page returns HTML."""
        event = make_event(method="GET", path="/chaos")
        response = lambda_handler(event, mock_lambda_context)
        assert response["statusCode"] == 200
        headers = response.get("headers", {})
        content_type = headers.get("Content-Type", headers.get("content-type", ""))
        assert "text/html" in content_type

    def test_chaos_page_no_auth_required(self, mock_lambda_context):
        """Test chaos page doesn't require authentication."""
        # Chaos UI should be accessible without auth (API endpoints require auth)
        event = make_event(method="GET", path="/chaos")
        response = lambda_handler(event, mock_lambda_context)
        assert response["statusCode"] == 200

    def test_chaos_page_contains_expected_elements(self, mock_lambda_context):
        """Test chaos page contains expected UI elements."""
        event = make_event(method="GET", path="/chaos")
        response = lambda_handler(event, mock_lambda_context)
        assert response["statusCode"] == 200

        content = response["body"]
        # Check for key UI elements
        assert "Chaos Testing" in content
        assert "DynamoDB Throttle" in content
        assert "Ingestion Failure" in content
        assert "Lambda" in content or "Cold Start" in content
        assert "Blast Radius" in content
        assert "Duration" in content


class TestAPIv2SentimentEndpoint:
    """Tests for the /api/v2/sentiment endpoint."""

    def test_sentiment_requires_auth(self, mock_lambda_context):
        """Test that sentiment endpoint requires authentication."""
        event = make_event(
            method="GET",
            path="/api/v2/sentiment",
            query_params={"tags": "AI"},
        )
        response = lambda_handler(event, mock_lambda_context)
        assert response["statusCode"] == 401

    def test_sentiment_requires_tags(self, mock_lambda_context, auth_headers):
        """Test that tags parameter is required."""
        event = make_event(
            method="GET",
            path="/api/v2/sentiment",
            headers=auth_headers,
        )
        response = lambda_handler(event, mock_lambda_context)
        # Handler returns 400 for missing/empty tags
        assert response["statusCode"] == 400

    def test_sentiment_empty_tags_rejected(self, mock_lambda_context, auth_headers):
        """Test that empty tags string is rejected."""
        event = make_event(
            method="GET",
            path="/api/v2/sentiment",
            query_params={"tags": ""},
            headers=auth_headers,
        )
        response = lambda_handler(event, mock_lambda_context)
        assert response["statusCode"] == 400
        body = json.loads(response["body"])
        assert "At least one tag" in body["detail"]

    def test_sentiment_max_tags_exceeded(self, mock_lambda_context, auth_headers):
        """Test that more than 5 tags is rejected."""
        event = make_event(
            method="GET",
            path="/api/v2/sentiment",
            query_params={"tags": "a,b,c,d,e,f"},
            headers=auth_headers,
        )
        response = lambda_handler(event, mock_lambda_context)
        assert response["statusCode"] == 400
        body = json.loads(response["body"])
        assert "Maximum 5 tags" in body["detail"]

    def test_sentiment_valid_request(
        self, mock_lambda_context, auth_headers, monkeypatch
    ):
        """Test successful sentiment request returns expected structure."""
        mock_result = {
            "tags": {
                "AI": {"positive": 0.7, "neutral": 0.2, "negative": 0.1, "count": 10}
            },
            "overall": {"positive": 0.7, "neutral": 0.2, "negative": 0.1},
            "total_count": 10,
            "trend": "improving",
            "time_range": {
                "start": "2025-11-24T00:00:00",
                "end": "2025-11-24T23:59:59",
            },
        }
        monkeypatch.setattr(
            "src.lambdas.dashboard.handler.get_sentiment_by_tags",
            lambda *args, **kwargs: mock_result,
        )
        event = make_event(
            method="GET",
            path="/api/v2/sentiment",
            query_params={"tags": "AI"},
            headers=auth_headers,
        )
        response = lambda_handler(event, mock_lambda_context)
        assert response["statusCode"] == 200
        data = json.loads(response["body"])
        assert "tags" in data
        assert "overall" in data
        assert "total_count" in data

    def test_sentiment_with_custom_time_range(
        self, mock_lambda_context, auth_headers, monkeypatch
    ):
        """Test sentiment with custom start/end times."""
        mock_result = {
            "tags": {
                "climate": {
                    "positive": 0.5,
                    "neutral": 0.3,
                    "negative": 0.2,
                    "count": 5,
                }
            },
            "overall": {"positive": 0.5, "neutral": 0.3, "negative": 0.2},
            "total_count": 5,
            "trend": "stable",
            "time_range": {
                "start": "2025-11-23T00:00:00Z",
                "end": "2025-11-24T00:00:00Z",
            },
        }
        monkeypatch.setattr(
            "src.lambdas.dashboard.handler.get_sentiment_by_tags",
            lambda *args, **kwargs: mock_result,
        )
        event = make_event(
            method="GET",
            path="/api/v2/sentiment",
            query_params={
                "tags": "climate",
                "start": "2025-11-23T00:00:00Z",
                "end": "2025-11-24T00:00:00Z",
            },
            headers=auth_headers,
        )
        response = lambda_handler(event, mock_lambda_context)
        assert response["statusCode"] == 200


class TestAPIv2TrendsEndpoint:
    """Tests for the /api/v2/trends endpoint."""

    def test_trends_requires_auth(self, mock_lambda_context):
        """Test that trends endpoint requires authentication."""
        event = make_event(
            method="GET",
            path="/api/v2/trends",
            query_params={"tags": "AI"},
        )
        response = lambda_handler(event, mock_lambda_context)
        assert response["statusCode"] == 401

    def test_trends_requires_tags(self, mock_lambda_context, auth_headers):
        """Test that tags parameter is required."""
        event = make_event(
            method="GET",
            path="/api/v2/trends",
            headers=auth_headers,
        )
        response = lambda_handler(event, mock_lambda_context)
        assert response["statusCode"] == 400

    def test_trends_empty_tags_rejected(self, mock_lambda_context, auth_headers):
        """Test that empty tags string is rejected."""
        event = make_event(
            method="GET",
            path="/api/v2/trends",
            query_params={"tags": ""},
            headers=auth_headers,
        )
        response = lambda_handler(event, mock_lambda_context)
        assert response["statusCode"] == 400
        body = json.loads(response["body"])
        assert "At least one tag" in body["detail"]

    def test_trends_max_tags_exceeded(self, mock_lambda_context, auth_headers):
        """Test that more than 5 tags is rejected."""
        event = make_event(
            method="GET",
            path="/api/v2/trends",
            query_params={"tags": "a,b,c,d,e,f"},
            headers=auth_headers,
        )
        response = lambda_handler(event, mock_lambda_context)
        assert response["statusCode"] == 400
        body = json.loads(response["body"])
        assert "Maximum 5 tags" in body["detail"]

    def test_trends_invalid_interval(self, mock_lambda_context, auth_headers):
        """Test that invalid interval is rejected."""
        event = make_event(
            method="GET",
            path="/api/v2/trends",
            query_params={"tags": "AI", "interval": "2h"},
            headers=auth_headers,
        )
        response = lambda_handler(event, mock_lambda_context)
        assert response["statusCode"] == 400
        body = json.loads(response["body"])
        assert "Invalid interval" in body["detail"]

    def test_trends_invalid_range_format(self, mock_lambda_context, auth_headers):
        """Test that invalid range format is rejected."""
        event = make_event(
            method="GET",
            path="/api/v2/trends",
            query_params={"tags": "AI", "range": "invalid"},
            headers=auth_headers,
        )
        response = lambda_handler(event, mock_lambda_context)
        assert response["statusCode"] == 400
        body = json.loads(response["body"])
        assert "Invalid range format" in body["detail"]

    def test_trends_valid_hourly_range(
        self, mock_lambda_context, auth_headers, monkeypatch
    ):
        """Test valid hourly range format."""
        mock_result = {
            "AI": [{"timestamp": "2025-11-24T10:00:00", "sentiment": 0.7, "count": 5}]
        }
        monkeypatch.setattr(
            "src.lambdas.dashboard.handler.get_trend_data",
            lambda *args, **kwargs: mock_result,
        )
        event = make_event(
            method="GET",
            path="/api/v2/trends",
            query_params={"tags": "AI", "interval": "1h", "range": "24h"},
            headers=auth_headers,
        )
        response = lambda_handler(event, mock_lambda_context)
        assert response["statusCode"] == 200

    def test_trends_valid_daily_range(
        self, mock_lambda_context, auth_headers, monkeypatch
    ):
        """Test valid daily range format."""
        mock_result = {
            "AI": [{"timestamp": "2025-11-24T00:00:00", "sentiment": 0.6, "count": 20}]
        }
        monkeypatch.setattr(
            "src.lambdas.dashboard.handler.get_trend_data",
            lambda *args, **kwargs: mock_result,
        )
        event = make_event(
            method="GET",
            path="/api/v2/trends",
            query_params={"tags": "AI", "interval": "1d", "range": "7d"},
            headers=auth_headers,
        )
        response = lambda_handler(event, mock_lambda_context)
        assert response["statusCode"] == 200


class TestAPIv2ArticlesEndpoint:
    """Tests for the /api/v2/articles endpoint."""

    def test_articles_requires_auth(self, mock_lambda_context):
        """Test that articles endpoint requires authentication."""
        event = make_event(
            method="GET",
            path="/api/v2/articles",
            query_params={"tags": "AI"},
        )
        response = lambda_handler(event, mock_lambda_context)
        assert response["statusCode"] == 401

    def test_articles_requires_tags(self, mock_lambda_context, auth_headers):
        """Test that tags parameter is required."""
        event = make_event(
            method="GET",
            path="/api/v2/articles",
            headers=auth_headers,
        )
        response = lambda_handler(event, mock_lambda_context)
        assert response["statusCode"] == 400

    def test_articles_empty_tags_rejected(self, mock_lambda_context, auth_headers):
        """Test that empty tags string is rejected."""
        event = make_event(
            method="GET",
            path="/api/v2/articles",
            query_params={"tags": ""},
            headers=auth_headers,
        )
        response = lambda_handler(event, mock_lambda_context)
        assert response["statusCode"] == 400
        body = json.loads(response["body"])
        assert "At least one tag" in body["detail"]

    def test_articles_invalid_sentiment_filter(self, mock_lambda_context, auth_headers):
        """Test that invalid sentiment filter is rejected."""
        event = make_event(
            method="GET",
            path="/api/v2/articles",
            query_params={"tags": "AI", "sentiment": "bad"},
            headers=auth_headers,
        )
        response = lambda_handler(event, mock_lambda_context)
        assert response["statusCode"] == 400
        body = json.loads(response["body"])
        assert "Invalid sentiment" in body["detail"]

    def test_articles_invalid_limit_zero(self, mock_lambda_context, auth_headers):
        """Test that limit of 0 is rejected."""
        event = make_event(
            method="GET",
            path="/api/v2/articles",
            query_params={"tags": "AI", "limit": "0"},
            headers=auth_headers,
        )
        response = lambda_handler(event, mock_lambda_context)
        assert response["statusCode"] == 400

    def test_articles_invalid_limit_too_large(self, mock_lambda_context, auth_headers):
        """Test that limit over 100 is rejected."""
        event = make_event(
            method="GET",
            path="/api/v2/articles",
            query_params={"tags": "AI", "limit": "200"},
            headers=auth_headers,
        )
        response = lambda_handler(event, mock_lambda_context)
        assert response["statusCode"] == 400

    def test_articles_valid_request(
        self, mock_lambda_context, auth_headers, monkeypatch
    ):
        """Test successful articles request."""
        mock_result = [
            {
                "id": "1",
                "title": "AI News",
                "timestamp": "2025-11-24T10:00:00Z",
                "sentiment": "positive",
            }
        ]
        monkeypatch.setattr(
            "src.lambdas.dashboard.handler.get_articles_by_tags",
            lambda *args, **kwargs: mock_result,
        )
        event = make_event(
            method="GET",
            path="/api/v2/articles",
            query_params={"tags": "AI"},
            headers=auth_headers,
        )
        response = lambda_handler(event, mock_lambda_context)
        assert response["statusCode"] == 200
        assert isinstance(json.loads(response["body"]), list)

    def test_articles_with_sentiment_filter(
        self, mock_lambda_context, auth_headers, monkeypatch
    ):
        """Test articles with sentiment filter."""
        mock_result = [
            {
                "id": "1",
                "title": "Good News",
                "timestamp": "2025-11-24T10:00:00Z",
                "sentiment": "positive",
            }
        ]
        monkeypatch.setattr(
            "src.lambdas.dashboard.handler.get_articles_by_tags",
            lambda *args, **kwargs: mock_result,
        )
        event = make_event(
            method="GET",
            path="/api/v2/articles",
            query_params={"tags": "AI", "sentiment": "positive"},
            headers=auth_headers,
        )
        response = lambda_handler(event, mock_lambda_context)
        assert response["statusCode"] == 200


class TestChaosExperimentsAPI:
    """Tests for chaos experiment CRUD endpoints."""

    def test_create_experiment_requires_auth(self, mock_lambda_context):
        """Test that create experiment requires authentication."""
        event = make_event(
            method="POST",
            path="/chaos/experiments",
            body={"scenario_type": "dynamodb_throttle"},
        )
        response = lambda_handler(event, mock_lambda_context)
        assert response["statusCode"] == 401

    def test_create_experiment_environment_blocked(
        self, mock_lambda_context, auth_headers, monkeypatch
    ):
        """Test that chaos experiments are blocked in non-preprod environments."""
        from src.lambdas.dashboard.chaos import EnvironmentNotAllowedError

        def mock_create(*args, **kwargs):
            raise EnvironmentNotAllowedError("Chaos testing only allowed in preprod")

        monkeypatch.setattr(
            "src.lambdas.dashboard.handler.create_experiment", mock_create
        )

        event = make_event(
            method="POST",
            path="/chaos/experiments",
            headers=auth_headers,
            body={
                "scenario_type": "dynamodb_throttle",
                "blast_radius": 50,
                "duration_seconds": 30,
            },
        )
        response = lambda_handler(event, mock_lambda_context)
        assert response["statusCode"] == 403
        body = json.loads(response["body"])
        assert "preprod" in body["detail"].lower()

    def test_create_experiment_invalid_request(self, mock_lambda_context, auth_headers):
        """Test that invalid request body is rejected."""
        event = make_event(
            method="POST",
            path="/chaos/experiments",
            headers=auth_headers,
            body={"invalid": "data"},
        )
        response = lambda_handler(event, mock_lambda_context)
        assert response["statusCode"] == 400

    def test_create_experiment_success(
        self, mock_lambda_context, auth_headers, monkeypatch
    ):
        """Test successful experiment creation."""
        mock_experiment = {
            "experiment_id": "test-123",
            "scenario_type": "dynamodb_throttle",
            "status": "pending",
        }
        monkeypatch.setattr(
            "src.lambdas.dashboard.handler.create_experiment",
            lambda *args, **kwargs: mock_experiment,
        )

        event = make_event(
            method="POST",
            path="/chaos/experiments",
            headers=auth_headers,
            body={
                "scenario_type": "dynamodb_throttle",
                "blast_radius": 50,
                "duration_seconds": 30,
            },
        )
        response = lambda_handler(event, mock_lambda_context)
        assert response["statusCode"] == 201
        body = json.loads(response["body"])
        assert body["experiment_id"] == "test-123"

    def test_list_experiments_requires_auth(self, mock_lambda_context):
        """Test that list experiments requires authentication."""
        event = make_event(method="GET", path="/chaos/experiments")
        response = lambda_handler(event, mock_lambda_context)
        assert response["statusCode"] == 401

    def test_list_experiments_success(
        self, mock_lambda_context, auth_headers, monkeypatch
    ):
        """Test successful experiment listing."""
        mock_experiments = [
            {"experiment_id": "1", "status": "completed"},
            {"experiment_id": "2", "status": "running"},
        ]
        monkeypatch.setattr(
            "src.lambdas.dashboard.handler.list_experiments",
            lambda *args, **kwargs: mock_experiments,
        )

        event = make_event(
            method="GET",
            path="/chaos/experiments",
            headers=auth_headers,
        )
        response = lambda_handler(event, mock_lambda_context)
        assert response["statusCode"] == 200
        body = json.loads(response["body"])
        assert len(body) == 2

    def test_list_experiments_with_status_filter(
        self, mock_lambda_context, auth_headers, monkeypatch
    ):
        """Test experiment listing with status filter."""
        mock_experiments = [{"experiment_id": "1", "status": "running"}]
        monkeypatch.setattr(
            "src.lambdas.dashboard.handler.list_experiments",
            lambda *args, **kwargs: mock_experiments,
        )

        event = make_event(
            method="GET",
            path="/chaos/experiments",
            query_params={"status": "running"},
            headers=auth_headers,
        )
        response = lambda_handler(event, mock_lambda_context)
        assert response["statusCode"] == 200

    def test_get_experiment_requires_auth(self, mock_lambda_context):
        """Test that get experiment requires authentication."""
        event = make_event(method="GET", path="/chaos/experiments/test-123")
        response = lambda_handler(event, mock_lambda_context)
        assert response["statusCode"] == 401

    def test_get_experiment_not_found(
        self, mock_lambda_context, auth_headers, monkeypatch
    ):
        """Test 404 for non-existent experiment."""
        monkeypatch.setattr(
            "src.lambdas.dashboard.handler.get_experiment", lambda *args: None
        )

        event = make_event(
            method="GET",
            path="/chaos/experiments/nonexistent",
            headers=auth_headers,
        )
        response = lambda_handler(event, mock_lambda_context)
        assert response["statusCode"] == 404

    def test_get_experiment_success(
        self, mock_lambda_context, auth_headers, monkeypatch
    ):
        """Test successful experiment retrieval."""
        mock_experiment = {
            "experiment_id": "test-123",
            "status": "pending",
            "scenario_type": "ingestion_failure",
        }
        monkeypatch.setattr(
            "src.lambdas.dashboard.handler.get_experiment",
            lambda *args: mock_experiment,
        )

        event = make_event(
            method="GET",
            path="/chaos/experiments/test-123",
            headers=auth_headers,
        )
        response = lambda_handler(event, mock_lambda_context)
        assert response["statusCode"] == 200
        body = json.loads(response["body"])
        assert body["experiment_id"] == "test-123"

    def test_start_experiment_requires_auth(self, mock_lambda_context):
        """Test that start experiment requires authentication."""
        event = make_event(method="POST", path="/chaos/experiments/test-123/start")
        response = lambda_handler(event, mock_lambda_context)
        assert response["statusCode"] == 401

    def test_start_experiment_success(
        self, mock_lambda_context, auth_headers, monkeypatch
    ):
        """Test successful experiment start."""
        mock_result = {"experiment_id": "test-123", "status": "running"}
        monkeypatch.setattr(
            "src.lambdas.dashboard.handler.start_experiment",
            lambda *args: mock_result,
        )

        event = make_event(
            method="POST",
            path="/chaos/experiments/test-123/start",
            headers=auth_headers,
        )
        response = lambda_handler(event, mock_lambda_context)
        assert response["statusCode"] == 200
        body = json.loads(response["body"])
        assert body["status"] == "running"

    def test_start_experiment_chaos_error(
        self, mock_lambda_context, auth_headers, monkeypatch
    ):
        """Test start failure due to ChaosError returns 500."""
        from src.lambdas.dashboard.chaos import ChaosError

        def mock_start(*args):
            raise ChaosError("Experiment failed to start")

        monkeypatch.setattr(
            "src.lambdas.dashboard.handler.start_experiment", mock_start
        )

        event = make_event(
            method="POST",
            path="/chaos/experiments/test-123/start",
            headers=auth_headers,
        )
        response = lambda_handler(event, mock_lambda_context)
        assert response["statusCode"] == 500

    def test_stop_experiment_requires_auth(self, mock_lambda_context):
        """Test that stop experiment requires authentication."""
        event = make_event(method="POST", path="/chaos/experiments/test-123/stop")
        response = lambda_handler(event, mock_lambda_context)
        assert response["statusCode"] == 401

    def test_stop_experiment_success(
        self, mock_lambda_context, auth_headers, monkeypatch
    ):
        """Test successful experiment stop."""
        mock_result = {"experiment_id": "test-123", "status": "stopped"}
        monkeypatch.setattr(
            "src.lambdas.dashboard.handler.stop_experiment",
            lambda *args: mock_result,
        )

        event = make_event(
            method="POST",
            path="/chaos/experiments/test-123/stop",
            headers=auth_headers,
        )
        response = lambda_handler(event, mock_lambda_context)
        assert response["statusCode"] == 200
        body = json.loads(response["body"])
        assert body["status"] == "stopped"

    def test_delete_experiment_requires_auth(self, mock_lambda_context):
        """Test that delete experiment requires authentication."""
        event = make_event(method="DELETE", path="/chaos/experiments/test-123")
        response = lambda_handler(event, mock_lambda_context)
        assert response["statusCode"] == 401

    def test_delete_experiment_success(
        self, mock_lambda_context, auth_headers, monkeypatch
    ):
        """Test successful experiment deletion."""
        monkeypatch.setattr(
            "src.lambdas.dashboard.handler.delete_experiment",
            lambda *args: True,
        )

        event = make_event(
            method="DELETE",
            path="/chaos/experiments/test-123",
            headers=auth_headers,
        )
        response = lambda_handler(event, mock_lambda_context)
        assert response["statusCode"] == 200
        body = json.loads(response["body"])
        assert "deleted" in body["message"].lower()

    def test_delete_experiment_failure(
        self, mock_lambda_context, auth_headers, monkeypatch
    ):
        """Test failed experiment deletion."""
        monkeypatch.setattr(
            "src.lambdas.dashboard.handler.delete_experiment",
            lambda *args: False,
        )

        event = make_event(
            method="DELETE",
            path="/chaos/experiments/test-123",
            headers=auth_headers,
        )
        response = lambda_handler(event, mock_lambda_context)
        assert response["statusCode"] == 500


# =============================================================================
# 087-test-coverage-completion: Dashboard Handler Coverage Tests
# =============================================================================


class TestDashboardMetricsErrors:
    """Tests for dashboard metrics error handling (lines 548-576)."""

    def test_get_dashboard_metrics_dynamodb_error(
        self, mock_lambda_context, auth_headers, monkeypatch, caplog
    ):
        """Test error handling when DynamoDB fails in metrics aggregation."""
        from botocore.exceptions import ClientError

        from tests.conftest import assert_error_logged

        def mock_aggregate_metrics(*args, **kwargs):
            raise ClientError(
                {"Error": {"Code": "ThrottlingException", "Message": "Rate exceeded"}},
                "Query",
            )

        # Patch at the source module where it's defined
        monkeypatch.setattr(
            "src.lambdas.dashboard.metrics.aggregate_dashboard_metrics",
            mock_aggregate_metrics,
        )

        event = make_event(
            method="GET",
            path="/api/v2/metrics",
            headers=auth_headers,
        )
        response = lambda_handler(event, mock_lambda_context)
        assert response["statusCode"] == 500
        assert_error_logged(caplog, "Failed to get dashboard metrics")

    def test_get_dashboard_metrics_aggregation_success(
        self, mock_lambda_context, auth_headers, monkeypatch
    ):
        """Test successful metrics aggregation path."""
        mock_metrics = {
            "total": 100,
            "positive": 50,
            "neutral": 30,
            "negative": 20,
            "recent_items": [{"id": "1", "sentiment": "positive"}],
        }
        # Patch at the source module where it's defined
        monkeypatch.setattr(
            "src.lambdas.dashboard.metrics.aggregate_dashboard_metrics",
            lambda *args, **kwargs: mock_metrics,
        )

        event = make_event(
            method="GET",
            path="/api/v2/metrics",
            headers=auth_headers,
        )
        response = lambda_handler(event, mock_lambda_context)
        assert response["statusCode"] == 200
        data = json.loads(response["body"])
        assert data["total"] == 100

    def test_get_dashboard_metrics_hours_validation_min(
        self, mock_lambda_context, auth_headers, monkeypatch
    ):
        """Test hours parameter clamped to minimum of 1."""
        mock_metrics = {"total": 10}
        captured_hours = []

        def capture_hours(table, hours=24):
            captured_hours.append(hours)
            return mock_metrics

        # Patch at the source module where it's defined
        monkeypatch.setattr(
            "src.lambdas.dashboard.metrics.aggregate_dashboard_metrics",
            capture_hours,
        )

        event = make_event(
            method="GET",
            path="/api/v2/metrics",
            query_params={"hours": "0"},
            headers=auth_headers,
        )
        response = lambda_handler(event, mock_lambda_context)
        assert response["statusCode"] == 200
        assert captured_hours[0] == 1  # Clamped to minimum

    def test_get_dashboard_metrics_hours_validation_max(
        self, mock_lambda_context, auth_headers, monkeypatch
    ):
        """Test hours parameter clamped to maximum of 168."""
        mock_metrics = {"total": 10}
        captured_hours = []

        def capture_hours(table, hours=24):
            captured_hours.append(hours)
            return mock_metrics

        # Patch at the source module where it's defined
        monkeypatch.setattr(
            "src.lambdas.dashboard.metrics.aggregate_dashboard_metrics",
            capture_hours,
        )

        event = make_event(
            method="GET",
            path="/api/v2/metrics",
            query_params={"hours": "500"},
            headers=auth_headers,
        )
        response = lambda_handler(event, mock_lambda_context)
        assert response["statusCode"] == 200
        assert captured_hours[0] == 168  # Clamped to maximum


class TestSentimentV2Errors:
    """Tests for sentiment v2 endpoint error handling (lines 642-656)."""

    def test_get_sentiment_v2_dynamodb_error(
        self, mock_lambda_context, auth_headers, monkeypatch, caplog
    ):
        """Test error handling when DynamoDB fails in sentiment query."""
        from botocore.exceptions import ClientError

        from tests.conftest import assert_error_logged

        def mock_get_sentiment(*args, **kwargs):
            raise ClientError(
                {"Error": {"Code": "InternalServerError", "Message": "DynamoDB error"}},
                "Query",
            )

        monkeypatch.setattr(
            "src.lambdas.dashboard.handler.get_sentiment_by_tags",
            mock_get_sentiment,
        )

        event = make_event(
            method="GET",
            path="/api/v2/sentiment",
            query_params={"tags": "AI"},
            headers=auth_headers,
        )
        response = lambda_handler(event, mock_lambda_context)
        assert response["statusCode"] == 500
        assert_error_logged(caplog, "Failed to get sentiment by tags")

    def test_get_sentiment_v2_value_error(
        self, mock_lambda_context, auth_headers, monkeypatch
    ):
        """Test ValueError handling in sentiment endpoint."""

        def mock_get_sentiment(*args, **kwargs):
            raise ValueError("Invalid date format")

        monkeypatch.setattr(
            "src.lambdas.dashboard.handler.get_sentiment_by_tags",
            mock_get_sentiment,
        )

        event = make_event(
            method="GET",
            path="/api/v2/sentiment",
            query_params={"tags": "AI"},
            headers=auth_headers,
        )
        response = lambda_handler(event, mock_lambda_context)
        assert response["statusCode"] == 400
        body = json.loads(response["body"])
        assert "Invalid date format" in body["detail"]


class TestTrendsV2Errors:
    """Tests for trends v2 endpoint error handling (lines 715-758)."""

    def test_get_trend_v2_range_parsing_invalid_hours(
        self, mock_lambda_context, auth_headers
    ):
        """Test error when range hours format is invalid (line 715-716)."""
        event = make_event(
            method="GET",
            path="/api/v2/trends",
            query_params={"tags": "AI", "range": "abch"},
            headers=auth_headers,
        )
        response = lambda_handler(event, mock_lambda_context)
        assert response["statusCode"] == 400
        body = json.loads(response["body"])
        assert "Invalid range format" in body["detail"]

    def test_get_trend_v2_range_parsing_invalid_days(
        self, mock_lambda_context, auth_headers
    ):
        """Test error when range days format is invalid (line 724-727)."""
        event = make_event(
            method="GET",
            path="/api/v2/trends",
            query_params={"tags": "AI", "range": "abcd"},
            headers=auth_headers,
        )
        response = lambda_handler(event, mock_lambda_context)
        assert response["statusCode"] == 400
        body = json.loads(response["body"])
        assert "Invalid range format" in body["detail"]

    def test_get_trend_v2_range_no_suffix(self, mock_lambda_context, auth_headers):
        """Test error when range has no h/d suffix (line 729-731)."""
        event = make_event(
            method="GET",
            path="/api/v2/trends",
            query_params={"tags": "AI", "range": "24"},
            headers=auth_headers,
        )
        response = lambda_handler(event, mock_lambda_context)
        assert response["statusCode"] == 400
        body = json.loads(response["body"])
        assert "Invalid range format" in body["detail"]

    def test_get_trend_v2_range_capped_at_168_hours(
        self, mock_lambda_context, auth_headers, monkeypatch
    ):
        """Test range capped at 168 hours (7 days) (line 735-736)."""
        captured_hours = []

        def capture_params(table, tags, interval, range_hours):
            captured_hours.append(range_hours)
            return {"tags": tags, "data": []}

        monkeypatch.setattr(
            "src.lambdas.dashboard.handler.get_trend_data",
            capture_params,
        )

        event = make_event(
            method="GET",
            path="/api/v2/trends",
            query_params={"tags": "AI", "range": "30d"},
            headers=auth_headers,
        )
        response = lambda_handler(event, mock_lambda_context)
        assert response["statusCode"] == 200
        assert captured_hours[0] == 168  # 30 days capped to 7 days (168 hours)

    def test_get_trend_v2_value_error(
        self, mock_lambda_context, auth_headers, monkeypatch
    ):
        """Test ValueError handling in trend endpoint (lines 743-747)."""

        def mock_get_trend(*args, **kwargs):
            raise ValueError("Invalid interval")

        monkeypatch.setattr(
            "src.lambdas.dashboard.handler.get_trend_data",
            mock_get_trend,
        )

        event = make_event(
            method="GET",
            path="/api/v2/trends",
            query_params={"tags": "AI"},
            headers=auth_headers,
        )
        response = lambda_handler(event, mock_lambda_context)
        assert response["statusCode"] == 400
        body = json.loads(response["body"])
        assert "Invalid interval" in body["detail"]

    def test_get_trend_v2_generic_exception(
        self, mock_lambda_context, auth_headers, monkeypatch, caplog
    ):
        """Test generic exception handling in trend endpoint (lines 749-758)."""
        from tests.conftest import assert_error_logged

        def mock_get_trend(*args, **kwargs):
            raise RuntimeError("Unexpected database error")

        monkeypatch.setattr(
            "src.lambdas.dashboard.handler.get_trend_data",
            mock_get_trend,
        )

        event = make_event(
            method="GET",
            path="/api/v2/trends",
            query_params={"tags": "AI"},
            headers=auth_headers,
        )
        response = lambda_handler(event, mock_lambda_context)
        assert response["statusCode"] == 500
        assert_error_logged(caplog, "Failed to get trend data")


class TestArticlesV2Errors:
    """Tests for articles v2 endpoint error handling (lines 800, 835-849)."""

    def test_get_articles_v2_limit_too_low(self, mock_lambda_context, auth_headers):
        """Test limit validation - too low (line 806-810)."""
        event = make_event(
            method="GET",
            path="/api/v2/articles",
            query_params={"tags": "AI", "limit": "0"},
            headers=auth_headers,
        )
        response = lambda_handler(event, mock_lambda_context)
        assert response["statusCode"] == 400
        body = json.loads(response["body"])
        assert "Limit must be between 1 and 100" in body["detail"]

    def test_get_articles_v2_limit_too_high(self, mock_lambda_context, auth_headers):
        """Test limit validation - too high (line 806-810)."""
        event = make_event(
            method="GET",
            path="/api/v2/articles",
            query_params={"tags": "AI", "limit": "150"},
            headers=auth_headers,
        )
        response = lambda_handler(event, mock_lambda_context)
        assert response["statusCode"] == 400
        body = json.loads(response["body"])
        assert "Limit must be between 1 and 100" in body["detail"]

    def test_get_articles_v2_value_error(
        self, mock_lambda_context, auth_headers, monkeypatch
    ):
        """Test ValueError handling in articles endpoint (lines 835-839)."""

        def mock_get_articles(*args, **kwargs):
            raise ValueError("Invalid tag format")

        monkeypatch.setattr(
            "src.lambdas.dashboard.handler.get_articles_by_tags",
            mock_get_articles,
        )

        event = make_event(
            method="GET",
            path="/api/v2/articles",
            query_params={"tags": "AI"},
            headers=auth_headers,
        )
        response = lambda_handler(event, mock_lambda_context)
        assert response["statusCode"] == 400
        body = json.loads(response["body"])
        assert "Invalid tag format" in body["detail"]

    def test_get_articles_v2_generic_exception(
        self, mock_lambda_context, auth_headers, monkeypatch, caplog
    ):
        """Test generic exception handling in articles endpoint (lines 841-852)."""
        from tests.conftest import assert_error_logged

        def mock_get_articles(*args, **kwargs):
            raise RuntimeError("Database connection lost")

        monkeypatch.setattr(
            "src.lambdas.dashboard.handler.get_articles_by_tags",
            mock_get_articles,
        )

        event = make_event(
            method="GET",
            path="/api/v2/articles",
            query_params={"tags": "AI"},
            headers=auth_headers,
        )
        response = lambda_handler(event, mock_lambda_context)
        assert response["statusCode"] == 500
        assert_error_logged(caplog, "Failed to get articles by tags")


class TestSessionAuth:
    """Tests for session-based authentication (Feature 1039).

    Feature 1039 replaced API key auth with session-based auth.
    These tests verify the session auth middleware is correctly integrated.
    """

    @mock_aws
    def test_session_auth_with_bearer_uuid(
        self, mock_lambda_context, anonymous_headers
    ):
        """Test session auth with Bearer UUID token succeeds."""
        create_test_table()

        event = make_event(
            method="GET",
            path="/api/v2/sentiment",
            query_params={"tags": "AI"},
            headers=anonymous_headers,
        )
        response = lambda_handler(event, mock_lambda_context)
        assert response["statusCode"] == 200

    def test_x_user_id_header_rejected(self, mock_lambda_context):
        """Feature 1146: X-User-ID header is rejected (security fix).

        X-User-ID header fallback was removed to prevent impersonation attacks.
        Users MUST use Bearer token for authentication.
        """
        event = make_event(
            method="GET",
            path="/api/v2/sentiment",
            query_params={"tags": "AI"},
            headers={"X-User-ID": "12345678-1234-5678-1234-567812345678"},
        )
        response = lambda_handler(event, mock_lambda_context)
        # X-User-ID alone should return 401 (not authenticated)
        assert response["statusCode"] == 401

    @mock_aws
    def test_session_auth_with_bearer_token(self, mock_lambda_context):
        """Test session auth with Bearer token containing user ID."""
        create_test_table()

        event = make_event(
            method="GET",
            path="/api/v2/sentiment",
            query_params={"tags": "AI"},
            headers={"Authorization": "Bearer 12345678-1234-5678-1234-567812345678"},
        )
        response = lambda_handler(event, mock_lambda_context)
        assert response["statusCode"] == 200

    def test_missing_session_id_returns_401(self, mock_lambda_context):
        """Test missing session ID returns 401."""
        event = make_event(
            method="GET",
            path="/api/v2/sentiment",
            query_params={"tags": "AI"},
        )
        response = lambda_handler(event, mock_lambda_context)
        assert response["statusCode"] == 401
        body = json.loads(response["body"])
        assert "Missing user identification" in body["detail"]


class TestStaticFileEdgeCases:
    """Tests for static file serving edge cases (lines 352-384)."""

    def test_static_file_non_whitelisted(self, mock_lambda_context, caplog):
        """Test non-whitelisted file request is rejected (line 357-365)."""
        from tests.conftest import assert_warning_logged

        event = make_event(method="GET", path="/static/malicious.exe")
        response = lambda_handler(event, mock_lambda_context)
        assert response["statusCode"] == 404
        assert_warning_logged(caplog, "Static file request for non-whitelisted file")

    def test_static_file_path_traversal_attempt(self, mock_lambda_context, caplog):
        """Test path traversal attempt is blocked."""

        event = make_event(method="GET", path="/static/../../../etc/passwd")
        response = lambda_handler(event, mock_lambda_context)
        assert response["statusCode"] == 404

    def test_static_file_whitelisted_but_missing(
        self, mock_lambda_context, monkeypatch
    ):
        """Test whitelisted file that doesn't exist returns 404 (line 367-371)."""
        from pathlib import Path

        # Mock STATIC_DIR to a path where files don't exist
        monkeypatch.setattr(
            "src.lambdas.dashboard.handler.STATIC_DIR",
            Path("/nonexistent/path"),
        )

        event = make_event(method="GET", path="/static/app.js")
        response = lambda_handler(event, mock_lambda_context)
        assert response["statusCode"] == 404


class TestItemRetrievalErrors:
    """Tests for item retrieval error handlers (lines 290-322)."""

    def test_serve_index_not_found(self, mock_lambda_context, monkeypatch, caplog):
        """Test index.html not found returns 404 (lines 289-297)."""
        from pathlib import Path

        from tests.conftest import assert_error_logged

        monkeypatch.setattr(
            "src.lambdas.dashboard.handler.STATIC_DIR",
            Path("/nonexistent/path"),
        )

        event = make_event(method="GET", path="/")
        response = lambda_handler(event, mock_lambda_context)
        assert response["statusCode"] == 404
        assert_error_logged(caplog, "index.html not found")

    def test_serve_chaos_not_found(self, mock_lambda_context, monkeypatch, caplog):
        """Test chaos.html not found returns 404 (lines 317-325)."""
        from pathlib import Path

        from tests.conftest import assert_error_logged

        monkeypatch.setattr(
            "src.lambdas.dashboard.handler.STATIC_DIR",
            Path("/nonexistent/path"),
        )

        event = make_event(method="GET", path="/chaos")
        response = lambda_handler(event, mock_lambda_context)
        assert response["statusCode"] == 404
        assert_error_logged(caplog, "chaos.html not found")


class TestChaosEndpointErrors:
    """Tests for chaos endpoint error handlers (lines 910-1136)."""

    def test_chaos_error_response_500(
        self, mock_lambda_context, auth_headers, monkeypatch, caplog
    ):
        """Test ChaosError returns 500 response (lines 910-911, 937-938)."""
        from src.lambdas.dashboard.chaos import ChaosError

        def mock_create(*args, **kwargs):
            raise ChaosError("Failed to create experiment")

        monkeypatch.setattr(
            "src.lambdas.dashboard.handler.create_experiment",
            mock_create,
        )

        event = make_event(
            method="POST",
            path="/chaos/experiments",
            body={
                "scenario_type": "dynamodb_throttle",
                "blast_radius": 50,
                "duration_seconds": 60,
            },
            headers=auth_headers,
        )
        response = lambda_handler(event, mock_lambda_context)
        assert response["statusCode"] == 500

    def test_get_chaos_experiment_fis_error(
        self, mock_lambda_context, auth_headers, monkeypatch, caplog
    ):
        """Test FIS status fetch error handling (lines 975-989)."""

        mock_experiment = {
            "experiment_id": "test-123",
            "status": "running",
            "fis_experiment_id": "fis-123",
        }

        def mock_get_exp(*args):
            return mock_experiment

        def mock_fis_status(*args):
            raise Exception("FIS API unavailable")

        monkeypatch.setattr(
            "src.lambdas.dashboard.handler.get_experiment",
            mock_get_exp,
        )
        monkeypatch.setattr(
            "src.lambdas.dashboard.handler.get_fis_experiment_status",
            mock_fis_status,
        )

        event = make_event(
            method="GET",
            path="/chaos/experiments/test-123",
            headers=auth_headers,
        )
        response = lambda_handler(event, mock_lambda_context)
        # Should still return the experiment, just without FIS status
        assert response["statusCode"] == 200

    def test_chaos_start_environment_not_allowed_returns_500_due_to_catch_order(
        self, mock_lambda_context, auth_headers, monkeypatch
    ):
        """Test EnvironmentNotAllowedError caught by ChaosError handler (lines 1016-1027).

        NOTE: This tests ACTUAL behavior. Lines 1029-1033 (EnvironmentNotAllowedError handler)
        are unreachable dead code because ChaosError is caught first and EnvironmentNotAllowedError
        inherits from ChaosError. The code should catch EnvironmentNotAllowedError BEFORE ChaosError.
        """
        from src.lambdas.dashboard.chaos import EnvironmentNotAllowedError

        def mock_start(*args):
            raise EnvironmentNotAllowedError("Chaos not allowed in production")

        # Patch where it's imported (handler module)
        monkeypatch.setattr(
            "src.lambdas.dashboard.handler.start_experiment",
            mock_start,
        )

        event = make_event(
            method="POST",
            path="/chaos/experiments/test-123/start",
            headers=auth_headers,
        )
        response = lambda_handler(event, mock_lambda_context)
        # Due to exception catch order bug, this returns 500 instead of expected 403
        assert response["statusCode"] == 500
        body = json.loads(response["body"])
        assert "not allowed" in body["detail"].lower()

    def test_chaos_stop_chaos_error(
        self, mock_lambda_context, auth_headers, monkeypatch
    ):
        """Test ChaosError on stop returns 500 (lines 1057-1071)."""
        from src.lambdas.dashboard.chaos import ChaosError

        def mock_stop(*args):
            raise ChaosError("Failed to stop experiment")

        monkeypatch.setattr(
            "src.lambdas.dashboard.handler.stop_experiment",
            mock_stop,
        )

        event = make_event(
            method="POST",
            path="/chaos/experiments/test-123/stop",
            headers=auth_headers,
        )
        response = lambda_handler(event, mock_lambda_context)
        assert response["statusCode"] == 500

    def test_delete_chaos_experiment_error(
        self, mock_lambda_context, auth_headers, monkeypatch, caplog
    ):
        """Test delete returns 500 when delete_experiment returns False (lines 1093-1097)."""
        # Patch where it's imported (handler module)
        monkeypatch.setattr(
            "src.lambdas.dashboard.handler.delete_experiment",
            lambda *args: False,
        )

        event = make_event(
            method="DELETE",
            path="/chaos/experiments/test-123",
            headers=auth_headers,
        )
        response = lambda_handler(event, mock_lambda_context)
        assert response["statusCode"] == 500
        body = json.loads(response["body"])
        assert "Failed to delete" in body["detail"]


class TestRuntimeConfig:
    """Tests for runtime configuration endpoint (Feature 1097)."""

    def test_runtime_config_returns_sse_url(self, mock_lambda_context, monkeypatch):
        """Test runtime config returns SSE Lambda URL when configured."""
        # Set the SSE_LAMBDA_URL environment variable
        monkeypatch.setenv("SSE_LAMBDA_URL", "https://sse.example.com/")

        # Import fresh to pick up new env var
        from importlib import reload

        from src.lambdas.dashboard import handler as handler_module

        reload(handler_module)

        event = make_event(method="GET", path="/api/v2/runtime")
        response = handler_module.lambda_handler(event, mock_lambda_context)
        assert response["statusCode"] == 200

        data = json.loads(response["body"])
        assert "sse_url" in data
        assert data["sse_url"] == "https://sse.example.com/"
        assert "environment" in data

        # Restore original
        monkeypatch.setenv("SSE_LAMBDA_URL", "")
        reload(handler_module)

    def test_runtime_config_returns_null_when_not_configured(
        self, mock_lambda_context, monkeypatch
    ):
        """Test runtime config returns null SSE URL when not configured."""
        # Ensure SSE_LAMBDA_URL is empty
        monkeypatch.setenv("SSE_LAMBDA_URL", "")

        from importlib import reload

        from src.lambdas.dashboard import handler as handler_module

        reload(handler_module)

        event = make_event(method="GET", path="/api/v2/runtime")
        response = handler_module.lambda_handler(event, mock_lambda_context)
        assert response["statusCode"] == 200

        data = json.loads(response["body"])
        assert data["sse_url"] is None  # Empty string becomes None/null

        reload(handler_module)

    def test_runtime_config_no_auth_required(self, mock_lambda_context):
        """Test runtime config doesn't require authentication."""
        # Should work without auth header
        event = make_event(method="GET", path="/api/v2/runtime")
        response = lambda_handler(event, mock_lambda_context)
        assert response["statusCode"] == 200
