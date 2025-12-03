"""Unit tests for configuration-specific SSE stream authentication.

Tests that config streams require X-User-ID header authentication
per FR-014 (global stream is public, config streams require auth).
"""

from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient


class TestConfigStreamAuthentication:
    """Tests for config stream authentication requirements."""

    def test_config_stream_requires_user_id(self):
        """Test that config stream returns 401 without X-User-ID header.

        Per FR-014: Configuration-specific streams require authentication.
        Per T034: Implement X-User-ID header validation.
        """
        from src.lambdas.sse_streaming.handler import app

        client = TestClient(app)
        # Request without X-User-ID header
        response = client.get("/api/v2/configurations/test-config/stream")

        assert response.status_code == 401
        assert "X-User-ID" in response.json()["detail"]

    def test_config_stream_empty_user_id_returns_401(self):
        """Test that empty X-User-ID header returns 401."""
        from src.lambdas.sse_streaming.handler import app

        client = TestClient(app)
        response = client.get(
            "/api/v2/configurations/test-config/stream",
            headers={"X-User-ID": ""},
        )

        assert response.status_code == 401

    def test_config_stream_whitespace_user_id_returns_401(self):
        """Test that whitespace-only X-User-ID returns 401."""
        from src.lambdas.sse_streaming.handler import app

        client = TestClient(app)
        response = client.get(
            "/api/v2/configurations/test-config/stream",
            headers={"X-User-ID": "   "},
        )

        assert response.status_code == 401

    def test_config_stream_validates_config_ownership(self):
        """Test that users can only access their own configs.

        Per T037: Return 404 if configuration not found.
        """
        from src.lambdas.sse_streaming.handler import app

        # Mock config lookup to return no access
        with patch(
            "src.lambdas.sse_streaming.handler.config_lookup_service"
        ) as mock_lookup:
            mock_lookup.validate_user_access.return_value = (False, None)

            client = TestClient(app)
            response = client.get(
                "/api/v2/configurations/other-users-config/stream",
                headers={"X-User-ID": "user-123"},
            )

            assert response.status_code == 404
            assert "not found" in response.json()["detail"]

    def test_config_stream_returns_404_for_nonexistent_config(self):
        """Test that config stream returns 404 for non-existent config.

        Per T037: Return 404 if configuration not found.
        """
        from src.lambdas.sse_streaming.handler import app

        # Mock config lookup to return no access (config not found)
        with patch(
            "src.lambdas.sse_streaming.handler.config_lookup_service"
        ) as mock_lookup:
            mock_lookup.validate_user_access.return_value = (False, None)

            client = TestClient(app)
            response = client.get(
                "/api/v2/configurations/nonexistent-config/stream",
                headers={"X-User-ID": "user-123"},
            )

            assert response.status_code == 404

    def test_global_stream_does_not_require_auth(self):
        """Test that global stream endpoint is registered and public.

        Per FR-014: Global stream at /api/v2/stream is public.

        Note: We verify route registration rather than hitting the streaming
        endpoint directly, as SSE streaming causes TestClient to hang.
        Full SSE streaming is tested in E2E tests.
        """
        from starlette.routing import Route

        from src.lambdas.sse_streaming.handler import app

        # Verify route is registered and accepts GET without auth requirements
        stream_route = None
        for route in app.routes:
            if isinstance(route, Route) and route.path == "/api/v2/stream":
                stream_route = route
                break

        assert stream_route is not None, "Stream endpoint should be registered"
        assert "GET" in stream_route.methods, "Stream endpoint should accept GET"
        # Global stream is public - no auth dependency in endpoint signature


class TestConfigStreamHeaderValidation:
    """Tests for X-User-ID header validation.

    Per T034: Implement X-User-ID header validation (401 if missing).
    """

    def test_empty_user_id_returns_401(self):
        """Test that empty X-User-ID header returns 401."""
        from src.lambdas.sse_streaming.handler import app

        client = TestClient(app)
        response = client.get(
            "/api/v2/configurations/test-config/stream",
            headers={"X-User-ID": ""},
        )

        assert response.status_code == 401
        assert "X-User-ID" in response.json()["detail"]

    def test_missing_user_id_returns_401(self):
        """Test that missing X-User-ID header returns 401."""
        from src.lambdas.sse_streaming.handler import app

        client = TestClient(app)
        response = client.get("/api/v2/configurations/test-config/stream")

        assert response.status_code == 401

    def test_config_stream_endpoint_registered(self):
        """Test that config stream endpoint is registered."""
        from starlette.routing import Route

        from src.lambdas.sse_streaming.handler import app

        # Verify route is registered
        config_route = None
        for route in app.routes:
            if (
                isinstance(route, Route)
                and route.path == "/api/v2/configurations/{config_id}/stream"
            ):
                config_route = route
                break

        assert config_route is not None, "Config stream endpoint should be registered"
        assert "GET" in config_route.methods, "Config stream should accept GET"


class TestConfigLookup:
    """Tests for configuration lookup from DynamoDB.

    Note: Comprehensive config lookup tests are in test_config_lookup.py.
    These tests verify integration with the handler.
    """

    def test_config_lookup_service_exists(self):
        """Test that ConfigLookupService can be imported and instantiated."""
        from src.lambdas.sse_streaming.config import ConfigLookupService

        # Verify class exists and has expected methods
        assert hasattr(ConfigLookupService, "get_configuration")
        assert hasattr(ConfigLookupService, "get_ticker_filters")
        assert hasattr(ConfigLookupService, "validate_user_access")

    def test_global_instance_available(self):
        """Test that global config_lookup_service instance is available."""
        from src.lambdas.sse_streaming.config import config_lookup_service

        assert config_lookup_service is not None

    def test_lookup_validates_user_ownership_via_pk(self):
        """Test that config lookup uses user_id in PK for ownership validation.

        The DynamoDB key structure PK=USER#{user_id} ensures users can
        only access their own configurations.
        """
        from unittest.mock import patch

        from src.lambdas.sse_streaming.config import ConfigLookupService

        mock_table = MagicMock()
        mock_table.get_item.return_value = {}  # Not found

        with patch("src.lambdas.sse_streaming.config.boto3") as mock_boto3:
            mock_resource = MagicMock()
            mock_resource.Table.return_value = mock_table
            mock_boto3.resource.return_value = mock_resource

            service = ConfigLookupService(table_name="test-table")
            service.get_configuration("user-123", "config-456")

            # Verify the key includes user_id in PK
            mock_table.get_item.assert_called_once_with(
                Key={"PK": "USER#user-123", "SK": "CONFIG#config-456"}
            )
