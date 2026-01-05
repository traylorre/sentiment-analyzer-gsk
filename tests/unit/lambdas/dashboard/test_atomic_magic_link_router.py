"""Unit tests for atomic magic link router integration (Feature 1129).

Tests that the router correctly uses atomic token verification:
- Router calls verify_magic_link with client_ip
- Client IP is extracted from X-Forwarded-For or request.client
- Error responses map correctly (409, 410)
- Successful verification returns 200 with tokens
"""

from datetime import UTC, datetime, timedelta
from unittest.mock import MagicMock, patch

import pytest
from fastapi import HTTPException
from starlette.requests import Request

from src.lambdas.shared.errors.session_errors import (
    TokenAlreadyUsedError,
    TokenExpiredError,
)


@pytest.mark.unit
@pytest.mark.session_us1
class TestMagicLinkRouterAtomicIntegration:
    """Tests for router integration with atomic token verification (Feature 1129)."""

    @pytest.fixture
    def mock_table(self):
        """Mock DynamoDB table."""
        return MagicMock()

    @pytest.fixture
    def mock_request(self):
        """Mock FastAPI request with client IP."""
        request = MagicMock(spec=Request)
        request.headers = {}
        request.client = MagicMock()
        request.client.host = "192.168.1.100"
        return request

    @pytest.fixture
    def mock_request_with_forwarded_for(self):
        """Mock request with X-Forwarded-For header (from ALB/API Gateway)."""
        request = MagicMock(spec=Request)
        request.headers = {"X-Forwarded-For": "10.0.0.1, 192.168.1.1"}
        request.client = MagicMock()
        request.client.host = "192.168.1.100"
        return request

    @pytest.mark.asyncio
    async def test_router_calls_verify_magic_link_with_client_ip(
        self, mock_table, mock_request
    ):
        """T002: Router calls verify_magic_link with client_ip parameter."""
        from src.lambdas.dashboard.router_v2 import verify_magic_link

        # Mock the auth service
        with patch("src.lambdas.dashboard.router_v2.auth_service") as mock_auth_service:
            # Setup successful response
            mock_response = MagicMock()
            mock_response.refresh_token_for_cookie = "mock-refresh-token"
            mock_response.model_dump.return_value = {
                "status": "verified",
                "email_masked": "t***@example.com",
            }
            mock_auth_service.verify_magic_link.return_value = mock_response
            mock_auth_service.ErrorResponse = type("ErrorResponse", (), {})

            # Call the router endpoint
            with patch(
                "src.lambdas.dashboard.router_v2.get_users_table",
                return_value=mock_table,
            ):
                await verify_magic_link(
                    token="test-token-123",
                    request=mock_request,
                    table=mock_table,
                )

            # Verify verify_magic_link was called with client_ip
            mock_auth_service.verify_magic_link.assert_called_once()
            call_kwargs = mock_auth_service.verify_magic_link.call_args.kwargs
            assert "client_ip" in call_kwargs
            assert call_kwargs["client_ip"] == "192.168.1.100"

    @pytest.mark.asyncio
    async def test_router_extracts_client_ip_from_x_forwarded_for(
        self, mock_table, mock_request_with_forwarded_for
    ):
        """T002: Router extracts first IP from X-Forwarded-For header."""
        from src.lambdas.dashboard.router_v2 import verify_magic_link

        with patch("src.lambdas.dashboard.router_v2.auth_service") as mock_auth_service:
            mock_response = MagicMock()
            mock_response.refresh_token_for_cookie = "mock-refresh-token"
            mock_response.model_dump.return_value = {"status": "verified"}
            mock_auth_service.verify_magic_link.return_value = mock_response
            mock_auth_service.ErrorResponse = type("ErrorResponse", (), {})

            await verify_magic_link(
                token="test-token-123",
                request=mock_request_with_forwarded_for,
                table=mock_table,
            )

            call_kwargs = mock_auth_service.verify_magic_link.call_args.kwargs
            # Should extract first IP from "10.0.0.1, 192.168.1.1"
            assert call_kwargs["client_ip"] == "10.0.0.1"

    @pytest.mark.asyncio
    async def test_router_returns_409_on_token_already_used(
        self, mock_table, mock_request
    ):
        """T002: TokenAlreadyUsedError returns 409 Conflict."""
        from src.lambdas.dashboard.router_v2 import verify_magic_link

        with patch("src.lambdas.dashboard.router_v2.auth_service") as mock_auth_service:
            mock_auth_service.verify_magic_link.side_effect = TokenAlreadyUsedError(
                token_id="test-token", used_at=datetime.now(UTC)
            )

            with pytest.raises(HTTPException) as exc_info:
                await verify_magic_link(
                    token="test-token-123",
                    request=mock_request,
                    table=mock_table,
                )

            assert exc_info.value.status_code == 409
            assert "already" in exc_info.value.detail.lower()

    @pytest.mark.asyncio
    async def test_router_returns_410_on_token_expired(self, mock_table, mock_request):
        """T002: TokenExpiredError returns 410 Gone."""
        from src.lambdas.dashboard.router_v2 import verify_magic_link

        with patch("src.lambdas.dashboard.router_v2.auth_service") as mock_auth_service:
            mock_auth_service.verify_magic_link.side_effect = TokenExpiredError(
                token_id="test-token",
                expired_at=datetime.now(UTC) - timedelta(hours=1),
            )

            with pytest.raises(HTTPException) as exc_info:
                await verify_magic_link(
                    token="test-token-123",
                    request=mock_request,
                    table=mock_table,
                )

            assert exc_info.value.status_code == 410
            assert "expired" in exc_info.value.detail.lower()

    @pytest.mark.asyncio
    async def test_router_returns_200_with_tokens_on_success(
        self, mock_table, mock_request
    ):
        """T002: Successful verification returns 200 with tokens."""
        from src.lambdas.dashboard.router_v2 import verify_magic_link

        with patch("src.lambdas.dashboard.router_v2.auth_service") as mock_auth_service:
            mock_response = MagicMock()
            mock_response.refresh_token_for_cookie = "mock-refresh-token"
            mock_response.model_dump.return_value = {
                "status": "verified",
                "email_masked": "t***@example.com",
                "tokens": {"id_token": "mock-id-token"},
            }
            mock_auth_service.verify_magic_link.return_value = mock_response
            mock_auth_service.ErrorResponse = type("ErrorResponse", (), {})

            result = await verify_magic_link(
                token="test-token-123",
                request=mock_request,
                table=mock_table,
            )

            # JSONResponse contains the data
            assert result.status_code == 200

    @pytest.mark.asyncio
    async def test_router_sets_httponly_cookie_on_success(
        self, mock_table, mock_request
    ):
        """T002: Successful verification sets HttpOnly refresh_token cookie."""
        from src.lambdas.dashboard.router_v2 import verify_magic_link

        with patch("src.lambdas.dashboard.router_v2.auth_service") as mock_auth_service:
            mock_response = MagicMock()
            mock_response.refresh_token_for_cookie = "secret-refresh-token"
            mock_response.model_dump.return_value = {
                "status": "verified",
                "tokens": {"id_token": "mock-id-token"},
            }
            mock_auth_service.verify_magic_link.return_value = mock_response
            mock_auth_service.ErrorResponse = type("ErrorResponse", (), {})

            result = await verify_magic_link(
                token="test-token-123",
                request=mock_request,
                table=mock_table,
            )

            # Check that cookie was set
            # JSONResponse stores cookies in headers
            set_cookie_header = result.headers.get("set-cookie", "")
            assert "refresh_token" in set_cookie_header
            assert "httponly" in set_cookie_header.lower()

    @pytest.mark.asyncio
    async def test_router_handles_unknown_client_ip(self, mock_table):
        """T002: Router handles case where client IP cannot be determined."""
        from src.lambdas.dashboard.router_v2 import verify_magic_link

        # Request with no X-Forwarded-For and no client
        request = MagicMock(spec=Request)
        request.headers = {}
        request.client = None

        with patch("src.lambdas.dashboard.router_v2.auth_service") as mock_auth_service:
            mock_response = MagicMock()
            mock_response.refresh_token_for_cookie = None
            mock_response.model_dump.return_value = {"status": "verified"}
            mock_auth_service.verify_magic_link.return_value = mock_response
            mock_auth_service.ErrorResponse = type("ErrorResponse", (), {})

            await verify_magic_link(
                token="test-token-123",
                request=request,
                table=mock_table,
            )

            call_kwargs = mock_auth_service.verify_magic_link.call_args.kwargs
            # Should fall back to "unknown"
            assert call_kwargs["client_ip"] == "unknown"
