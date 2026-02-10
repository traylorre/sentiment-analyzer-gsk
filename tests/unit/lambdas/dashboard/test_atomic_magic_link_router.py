"""Unit tests for atomic magic link router integration (Feature 1129).

Tests that the router correctly uses atomic token verification:
- Router calls verify_magic_link with client_ip
- Client IP is extracted from X-Forwarded-For or requestContext
- Error responses map correctly (409, 410)
- Successful verification returns 200 with tokens
"""

import json
from unittest.mock import MagicMock, patch

import pytest

from src.lambdas.dashboard.handler import lambda_handler
from src.lambdas.shared.errors.session_errors import (
    TokenAlreadyUsedError,
    TokenExpiredError,
)
from tests.conftest import make_event


@pytest.mark.unit
@pytest.mark.session_us1
class TestMagicLinkRouterAtomicIntegration:
    """Tests for router integration with atomic token verification (Feature 1129)."""

    @pytest.fixture
    def mock_table(self):
        """Mock DynamoDB table."""
        return MagicMock()

    @patch("src.lambdas.dashboard.router_v2.get_users_table")
    @patch("src.lambdas.dashboard.router_v2.auth_service")
    def test_router_calls_verify_magic_link_with_client_ip(
        self, mock_auth_service, mock_get_table, mock_table, mock_lambda_context
    ):
        """T002: Router calls verify_magic_link with client_ip parameter."""
        mock_get_table.return_value = mock_table
        mock_response = MagicMock()
        mock_response.refresh_token_for_cookie = "mock-refresh-token"
        mock_response.model_dump.return_value = {
            "status": "verified",
            "email_masked": "t***@example.com",
        }
        mock_auth_service.verify_magic_link.return_value = mock_response
        mock_auth_service.ErrorResponse = type("ErrorResponse", (), {})

        event = make_event(
            method="POST",
            path="/api/v2/auth/magic-link/verify",
            query_params={"token": "test-token-123"},
        )
        lambda_handler(event, mock_lambda_context)

        # Verify verify_magic_link was called with client_ip
        mock_auth_service.verify_magic_link.assert_called_once()
        call_kwargs = mock_auth_service.verify_magic_link.call_args.kwargs
        assert "client_ip" in call_kwargs

    @patch("src.lambdas.dashboard.router_v2.get_users_table")
    @patch("src.lambdas.dashboard.router_v2.auth_service")
    def test_router_extracts_client_ip_from_x_forwarded_for(
        self, mock_auth_service, mock_get_table, mock_table, mock_lambda_context
    ):
        """T002: Router extracts first IP from X-Forwarded-For header."""
        mock_get_table.return_value = mock_table
        mock_response = MagicMock()
        mock_response.refresh_token_for_cookie = "mock-refresh-token"
        mock_response.model_dump.return_value = {"status": "verified"}
        mock_auth_service.verify_magic_link.return_value = mock_response
        mock_auth_service.ErrorResponse = type("ErrorResponse", (), {})

        event = make_event(
            method="POST",
            path="/api/v2/auth/magic-link/verify",
            query_params={"token": "test-token-123"},
            headers={"X-Forwarded-For": "10.0.0.1, 192.168.1.1"},
        )
        lambda_handler(event, mock_lambda_context)

        call_kwargs = mock_auth_service.verify_magic_link.call_args.kwargs
        # Should extract first IP from "10.0.0.1, 192.168.1.1"
        assert call_kwargs["client_ip"] == "10.0.0.1"

    @patch("src.lambdas.dashboard.router_v2.get_users_table")
    @patch("src.lambdas.dashboard.router_v2.auth_service")
    def test_router_returns_409_on_token_already_used(
        self, mock_auth_service, mock_get_table, mock_table, mock_lambda_context
    ):
        """T002: TokenAlreadyUsedError returns 409 Conflict."""
        from datetime import UTC, datetime

        mock_get_table.return_value = mock_table
        mock_auth_service.verify_magic_link.side_effect = TokenAlreadyUsedError(
            token_id="test-token", used_at=datetime.now(UTC)
        )

        event = make_event(
            method="POST",
            path="/api/v2/auth/magic-link/verify",
            query_params={"token": "test-token-123"},
        )
        response = lambda_handler(event, mock_lambda_context)
        assert response["statusCode"] == 409
        body = json.loads(response["body"])
        assert "already" in body.get("detail", body.get("message", "")).lower()

    @patch("src.lambdas.dashboard.router_v2.get_users_table")
    @patch("src.lambdas.dashboard.router_v2.auth_service")
    def test_router_returns_410_on_token_expired(
        self, mock_auth_service, mock_get_table, mock_table, mock_lambda_context
    ):
        """T002: TokenExpiredError returns 410 Gone."""
        from datetime import UTC, datetime, timedelta

        mock_get_table.return_value = mock_table
        mock_auth_service.verify_magic_link.side_effect = TokenExpiredError(
            token_id="test-token",
            expired_at=datetime.now(UTC) - timedelta(hours=1),
        )

        event = make_event(
            method="POST",
            path="/api/v2/auth/magic-link/verify",
            query_params={"token": "test-token-123"},
        )
        response = lambda_handler(event, mock_lambda_context)
        assert response["statusCode"] == 410
        body = json.loads(response["body"])
        assert "expired" in body.get("detail", body.get("message", "")).lower()

    @patch("src.lambdas.dashboard.router_v2.get_users_table")
    @patch("src.lambdas.dashboard.router_v2.auth_service")
    def test_router_returns_200_with_tokens_on_success(
        self, mock_auth_service, mock_get_table, mock_table, mock_lambda_context
    ):
        """T002: Successful verification returns 200 with tokens."""
        mock_get_table.return_value = mock_table
        mock_response = MagicMock()
        mock_response.refresh_token_for_cookie = "mock-refresh-token"
        mock_response.model_dump.return_value = {
            "status": "verified",
            "email_masked": "t***@example.com",
            "tokens": {"id_token": "mock-id-token"},
        }
        mock_auth_service.verify_magic_link.return_value = mock_response
        mock_auth_service.ErrorResponse = type("ErrorResponse", (), {})

        event = make_event(
            method="POST",
            path="/api/v2/auth/magic-link/verify",
            query_params={"token": "test-token-123"},
        )
        response = lambda_handler(event, mock_lambda_context)
        assert response["statusCode"] == 200

    @patch("src.lambdas.dashboard.router_v2.get_users_table")
    @patch("src.lambdas.dashboard.router_v2.auth_service")
    def test_router_sets_httponly_cookie_on_success(
        self, mock_auth_service, mock_get_table, mock_table, mock_lambda_context
    ):
        """T002: Successful verification sets HttpOnly refresh_token cookie."""
        mock_get_table.return_value = mock_table
        mock_response = MagicMock()
        mock_response.refresh_token_for_cookie = "secret-refresh-token"
        mock_response.model_dump.return_value = {
            "status": "verified",
            "tokens": {"id_token": "mock-id-token"},
        }
        mock_auth_service.verify_magic_link.return_value = mock_response
        mock_auth_service.ErrorResponse = type("ErrorResponse", (), {})

        event = make_event(
            method="POST",
            path="/api/v2/auth/magic-link/verify",
            query_params={"token": "test-token-123"},
        )
        response = lambda_handler(event, mock_lambda_context)

        # Check that cookie was set via multiValueHeaders
        cookies = response.get("multiValueHeaders", {}).get("Set-Cookie", [])
        cookie_str = "; ".join(cookies)
        assert "refresh_token" in cookie_str
        assert "httponly" in cookie_str.lower()

    @patch("src.lambdas.dashboard.router_v2.get_users_table")
    @patch("src.lambdas.dashboard.router_v2.auth_service")
    def test_router_handles_unknown_client_ip(
        self, mock_auth_service, mock_get_table, mock_table, mock_lambda_context
    ):
        """T002: Router handles case where client IP cannot be determined."""
        mock_get_table.return_value = mock_table
        mock_response = MagicMock()
        mock_response.refresh_token_for_cookie = None
        mock_response.model_dump.return_value = {"status": "verified"}
        mock_auth_service.verify_magic_link.return_value = mock_response
        mock_auth_service.ErrorResponse = type("ErrorResponse", (), {})

        # Event with no X-Forwarded-For; sourceIp comes from requestContext
        event = make_event(
            method="POST",
            path="/api/v2/auth/magic-link/verify",
            query_params={"token": "test-token-123"},
        )
        lambda_handler(event, mock_lambda_context)

        call_kwargs = mock_auth_service.verify_magic_link.call_args.kwargs
        # Should use sourceIp from requestContext (make_event sets "127.0.0.1")
        assert call_kwargs["client_ip"] in ("127.0.0.1", "unknown")
