"""Unit tests for configuration-specific SSE stream authentication.

Tests that config streams require authentication (Bearer token, X-User-ID header,
or user_token query param) per FR-014 (global stream is public, config streams
require auth).

Migrated from FastAPI TestClient to direct handler invocation (001-fastapi-purge).
"""

import json
from unittest.mock import MagicMock, patch

from src.lambdas.sse_streaming.handler import handler
from tests.conftest import make_function_url_event, parse_streaming_response


class TestConfigStreamAuthentication:
    """Tests for config stream authentication requirements."""

    def test_config_stream_requires_user_id(self):
        """Test that config stream returns 401 without any authentication.

        Per FR-014: Configuration-specific streams require authentication.
        Per T034: Implement X-User-ID header validation.
        """
        event = make_function_url_event(
            path="/api/v2/configurations/test-config/stream"
        )
        gen = handler(event, None)
        metadata, body = parse_streaming_response(gen)

        assert metadata["statusCode"] == 401
        data = json.loads(body)
        assert "Authentication required" in data["detail"]

    def test_config_stream_empty_user_id_returns_401(self):
        """Test that empty X-User-ID header returns 401."""
        event = make_function_url_event(
            path="/api/v2/configurations/test-config/stream",
            headers={"X-User-ID": ""},
        )
        gen = handler(event, None)
        metadata, body = parse_streaming_response(gen)

        assert metadata["statusCode"] == 401

    def test_config_stream_whitespace_user_id_returns_401(self):
        """Test that whitespace-only X-User-ID returns 401."""
        event = make_function_url_event(
            path="/api/v2/configurations/test-config/stream",
            headers={"X-User-ID": "   "},
        )
        gen = handler(event, None)
        metadata, body = parse_streaming_response(gen)

        assert metadata["statusCode"] == 401

    def test_config_stream_validates_config_ownership(self):
        """Test that users can only access their own configs.

        Per T037: Return 404 if configuration not found.
        """
        with patch(
            "src.lambdas.sse_streaming.handler.config_lookup_service"
        ) as mock_lookup:
            mock_lookup.validate_user_access.return_value = (False, None)

            event = make_function_url_event(
                path="/api/v2/configurations/other-users-config/stream",
                headers={"X-User-ID": "user-123"},
            )
            gen = handler(event, None)
            metadata, body = parse_streaming_response(gen)

            assert metadata["statusCode"] == 404
            data = json.loads(body)
            assert "not found" in data["detail"].lower()

    def test_config_stream_returns_404_for_nonexistent_config(self):
        """Test that config stream returns 404 for non-existent config.

        Per T037: Return 404 if configuration not found.
        """
        with patch(
            "src.lambdas.sse_streaming.handler.config_lookup_service"
        ) as mock_lookup:
            mock_lookup.validate_user_access.return_value = (False, None)

            event = make_function_url_event(
                path="/api/v2/configurations/nonexistent-config/stream",
                headers={"X-User-ID": "user-123"},
            )
            gen = handler(event, None)
            metadata, body = parse_streaming_response(gen)

            assert metadata["statusCode"] == 404

    def test_global_stream_does_not_require_auth(self):
        """Test that global stream endpoint is public (no auth required).

        Per FR-014: Global stream at /api/v2/stream is public.
        We verify that calling /api/v2/stream without auth does NOT return 401.
        (It may return 503 if connection_manager.acquire returns None, but not 401.)
        """
        mock_mgr = MagicMock()
        mock_mgr.acquire.return_value = None
        mock_mgr.max_connections = 100

        with patch("src.lambdas.sse_streaming.handler.connection_manager", mock_mgr):
            with patch("src.lambdas.sse_streaming.handler.metrics_emitter"):
                event = make_function_url_event(path="/api/v2/stream")
                gen = handler(event, None)
                metadata, body = parse_streaming_response(gen)

                # Should NOT be 401 — global stream is public
                assert metadata["statusCode"] != 401
                # 503 is expected because acquire returns None
                assert metadata["statusCode"] == 503


class TestConfigStreamHeaderValidation:
    """Tests for X-User-ID header validation.

    Per T034: Implement X-User-ID header validation (401 if missing).
    """

    def test_empty_user_id_returns_401(self):
        """Test that empty X-User-ID header returns 401."""
        event = make_function_url_event(
            path="/api/v2/configurations/test-config/stream",
            headers={"X-User-ID": ""},
        )
        gen = handler(event, None)
        metadata, body = parse_streaming_response(gen)

        assert metadata["statusCode"] == 401
        data = json.loads(body)
        assert "Authentication required" in data["detail"]

    def test_missing_user_id_returns_401(self):
        """Test that missing X-User-ID header returns 401."""
        event = make_function_url_event(
            path="/api/v2/configurations/test-config/stream",
        )
        gen = handler(event, None)
        metadata, body = parse_streaming_response(gen)

        assert metadata["statusCode"] == 401

    def test_config_stream_route_handles_get(self):
        """Test that config stream path is handled by the handler for GET requests."""
        # Verify the handler routes /api/v2/configurations/{id}/stream correctly
        # by checking that it returns 401 (auth required), not 404 (not found)
        event = make_function_url_event(
            path="/api/v2/configurations/test-config-id/stream",
        )
        gen = handler(event, None)
        metadata, body = parse_streaming_response(gen)

        # 401 means the route was matched (auth is checked first)
        assert metadata["statusCode"] == 401

    def test_bearer_token_authentication(self):
        """Test that Bearer token is accepted for authentication."""
        with patch(
            "src.lambdas.sse_streaming.handler.config_lookup_service"
        ) as mock_lookup:
            mock_lookup.validate_user_access.return_value = (False, None)

            event = make_function_url_event(
                path="/api/v2/configurations/test-config/stream",
                headers={"Authorization": "Bearer my-token-123"},
            )
            gen = handler(event, None)
            metadata, body = parse_streaming_response(gen)

            # Should get 404 (config not found), not 401 (auth required)
            assert metadata["statusCode"] == 404
            # Verify the token was used as user_id
            mock_lookup.validate_user_access.assert_called_once_with(
                "my-token-123", "test-config"
            )

    def test_user_token_query_param_authentication(self):
        """Test that user_token query param is accepted for authentication."""
        with patch(
            "src.lambdas.sse_streaming.handler.config_lookup_service"
        ) as mock_lookup:
            mock_lookup.validate_user_access.return_value = (False, None)

            event = make_function_url_event(
                path="/api/v2/configurations/test-config/stream",
                query_params={"user_token": "query-token-456"},
            )
            gen = handler(event, None)
            metadata, body = parse_streaming_response(gen)

            # Should get 404, not 401
            assert metadata["statusCode"] == 404
            mock_lookup.validate_user_access.assert_called_once_with(
                "query-token-456", "test-config"
            )


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
