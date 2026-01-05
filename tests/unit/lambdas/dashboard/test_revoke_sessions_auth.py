"""Unit tests for /admin/sessions/revoke authorization (Feature 001).

Tests that the revoke_sessions_bulk endpoint is protected with @require_role("operator"):
- US1: Operators can revoke sessions (200)
- US2: Non-operators are blocked (403)
- US2: Unauthenticated requests are blocked (401)
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from src.lambdas.shared.middleware import AuthContext, AuthType


def mock_auth_context(
    user_id: str | None = "test-user-id",
    auth_type: AuthType = AuthType.AUTHENTICATED,
    roles: list[str] | None = None,
) -> AuthContext:
    """Create a mock AuthContext for testing."""
    return AuthContext(
        user_id=user_id,
        auth_type=auth_type,
        auth_method="bearer" if user_id else None,
        roles=roles,
    )


@pytest.fixture
def mock_table():
    """Mock DynamoDB table."""
    return MagicMock()


@pytest.fixture
def client():
    """Create a test client for the router."""
    # Import here to avoid circular imports
    from src.lambdas.dashboard.handler import app

    return TestClient(app, raise_server_exceptions=False)


@pytest.mark.unit
class TestRevokeSessionsAuthorization:
    """Tests for /admin/sessions/revoke endpoint authorization (Feature 001)."""

    def test_operator_can_revoke_sessions(self, client: TestClient) -> None:
        """US1: Operators with 'operator' role can revoke sessions (200)."""
        mock_ctx = mock_auth_context(roles=["free", "operator"])

        # Mock auth context and the service call
        with (
            patch(
                "src.lambdas.shared.middleware.require_role.extract_auth_context_typed",
                return_value=mock_ctx,
            ),
            patch(
                "src.lambdas.dashboard.router_v2.auth_service.revoke_sessions_bulk"
            ) as mock_revoke,
        ):
            mock_revoke.return_value = MagicMock(
                model_dump=lambda: {
                    "revoked_count": 2,
                    "failed_count": 0,
                    "failed_user_ids": [],
                }
            )

            response = client.post(
                "/api/v2/admin/sessions/revoke",
                json={"user_ids": ["user-1", "user-2"], "reason": "Security incident"},
            )

            assert response.status_code == 200
            assert response.json()["revoked_count"] == 2

    def test_non_operator_blocked_with_403(self, client: TestClient) -> None:
        """US2: Non-operators receive 403 Access denied."""
        mock_ctx = mock_auth_context(roles=["free"])

        with patch(
            "src.lambdas.shared.middleware.require_role.extract_auth_context_typed",
            return_value=mock_ctx,
        ):
            response = client.post(
                "/api/v2/admin/sessions/revoke",
                json={"user_ids": ["user-1"], "reason": "Test"},
            )

            assert response.status_code == 403
            assert response.json()["detail"] == "Access denied"

    def test_unauthenticated_blocked_with_401(self, client: TestClient) -> None:
        """US2: Unauthenticated requests receive 401 Authentication required."""
        mock_ctx = mock_auth_context(user_id=None, roles=None)

        with patch(
            "src.lambdas.shared.middleware.require_role.extract_auth_context_typed",
            return_value=mock_ctx,
        ):
            response = client.post(
                "/api/v2/admin/sessions/revoke",
                json={"user_ids": ["user-1"], "reason": "Test"},
            )

            assert response.status_code == 401
            assert response.json()["detail"] == "Authentication required"

    def test_paid_user_blocked_with_403(self, client: TestClient) -> None:
        """US2: Paid users (without operator role) receive 403."""
        mock_ctx = mock_auth_context(roles=["free", "paid"])

        with patch(
            "src.lambdas.shared.middleware.require_role.extract_auth_context_typed",
            return_value=mock_ctx,
        ):
            response = client.post(
                "/api/v2/admin/sessions/revoke",
                json={"user_ids": ["user-1"], "reason": "Test"},
            )

            assert response.status_code == 403
            assert response.json()["detail"] == "Access denied"

    def test_error_message_does_not_reveal_required_role(
        self, client: TestClient
    ) -> None:
        """Security: Error message should not reveal 'operator' role requirement."""
        mock_ctx = mock_auth_context(roles=["free"])

        with patch(
            "src.lambdas.shared.middleware.require_role.extract_auth_context_typed",
            return_value=mock_ctx,
        ):
            response = client.post(
                "/api/v2/admin/sessions/revoke",
                json={"user_ids": ["user-1"], "reason": "Test"},
            )

            detail = response.json()["detail"]
            assert "operator" not in detail.lower()
            assert detail == "Access denied"
