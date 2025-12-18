"""Unit tests for path normalization middleware.

Tests the PathNormalizationMiddleware that fixes Lambda Web Adapter
double-slash path issues (Fix 141).

Note: Starlette's TestClient normalizes URLs before sending, stripping
leading double slashes. The middleware works in production where Lambda
Web Adapter sends raw paths. These tests verify internal double-slash
handling which TestClient does preserve.
"""

import pytest
from starlette.testclient import TestClient


@pytest.fixture
def test_client():
    """Create a test client for the SSE streaming app."""
    # Import handler after conftest sets up the path
    from handler import app

    return TestClient(app)


class TestPathNormalization:
    """Tests for PathNormalizationMiddleware."""

    def test_health_single_slash(self, test_client):
        """Normal /health request should work."""
        response = test_client.get("/health")

        assert response.status_code == 200
        assert response.json()["status"] == "healthy"

    def test_debug_single_slash(self, test_client):
        """Normal /debug request should work."""
        response = test_client.get("/debug")

        assert response.status_code == 200
        assert response.json()["status"] == "debug"

    def test_api_v2_stream_status_single_slash(self, test_client):
        """Normal /api/v2/stream/status should work."""
        response = test_client.get("/api/v2/stream/status")

        assert response.status_code == 200
        # StreamStatus model uses 'connections' field
        assert "connections" in response.json()

    def test_api_path_internal_double_slash(self, test_client):
        """Internal double slashes /api//v2/stream/status should be normalized."""
        response = test_client.get("/api//v2/stream/status")

        assert response.status_code == 200
        assert "connections" in response.json()

    def test_multiple_internal_double_slashes(self, test_client):
        """Multiple internal double slashes should be normalized."""
        # /api//v2//stream//status -> /api/v2/stream/status
        response = test_client.get("/api//v2//stream//status")

        assert response.status_code == 200
        assert "connections" in response.json()

    def test_nonexistent_path_still_404(self, test_client):
        """Normalization should not make nonexistent paths return 200."""
        response = test_client.get("/nonexistent/path")

        assert response.status_code == 404

    def test_root_path_404(self, test_client):
        """Root path / should return 404 (no root handler)."""
        response = test_client.get("/")

        assert response.status_code == 404


class TestMiddlewarePathNormalizationDirect:
    """Direct tests for path normalization logic.

    Since TestClient normalizes leading slashes, we test the middleware
    dispatch logic directly using mock requests.
    """

    @pytest.mark.asyncio
    async def test_double_slash_normalized_in_scope(self):
        """Verify middleware modifies scope path for double slashes."""
        from handler import PathNormalizationMiddleware

        # Create a mock request scope
        scope = {
            "type": "http",
            "method": "GET",
            "path": "//health",
            "query_string": b"",
            "headers": [],
        }

        middleware = PathNormalizationMiddleware(app=None)

        # Mock call_next that captures the modified scope
        captured_path = None

        async def mock_call_next(request):
            nonlocal captured_path
            captured_path = request.scope.get("path")

            class MockResponse:
                pass

            return MockResponse()

        # Create a mock request
        from starlette.requests import Request

        request = Request(scope)

        # Call middleware dispatch
        await middleware.dispatch(request, mock_call_next)

        # Verify path was normalized
        assert captured_path == "/health"

    @pytest.mark.asyncio
    async def test_triple_slash_normalized(self):
        """Verify triple slashes are normalized."""
        from handler import PathNormalizationMiddleware

        scope = {
            "type": "http",
            "method": "GET",
            "path": "///api///health",
            "query_string": b"",
            "headers": [],
        }

        middleware = PathNormalizationMiddleware(app=None)
        captured_path = None

        async def mock_call_next(request):
            nonlocal captured_path
            captured_path = request.scope.get("path")

            class MockResponse:
                pass

            return MockResponse()

        from starlette.requests import Request

        request = Request(scope)
        await middleware.dispatch(request, mock_call_next)

        assert captured_path == "/api/health"

    @pytest.mark.asyncio
    async def test_single_slash_unchanged(self):
        """Verify single slashes are not modified."""
        from handler import PathNormalizationMiddleware

        scope = {
            "type": "http",
            "method": "GET",
            "path": "/health",
            "query_string": b"",
            "headers": [],
        }

        middleware = PathNormalizationMiddleware(app=None)
        captured_path = None

        async def mock_call_next(request):
            nonlocal captured_path
            captured_path = request.scope.get("path")

            class MockResponse:
                pass

            return MockResponse()

        from starlette.requests import Request

        request = Request(scope)
        await middleware.dispatch(request, mock_call_next)

        # Path should remain unchanged
        assert captured_path == "/health"
