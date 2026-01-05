"""Tests for /admin/sessions/revoke endpoint authorization (Feature 1148).

Verifies that the bulk session revocation endpoint is properly protected
by @require_role("operator") decorator.
"""

from unittest.mock import MagicMock, patch

import pytest
from fastapi import FastAPI
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
def mock_users_table() -> MagicMock:
    """Mock DynamoDB users table."""
    return MagicMock()


@pytest.fixture
def app(mock_users_table: MagicMock) -> FastAPI:
    """Create a FastAPI app with the admin router for testing."""
    from src.lambdas.dashboard.router_v2 import admin_router, get_users_table

    test_app = FastAPI()
    test_app.include_router(admin_router)

    # Override the users table dependency
    test_app.dependency_overrides[get_users_table] = lambda: mock_users_table

    return test_app


@pytest.fixture
def client(app: FastAPI) -> TestClient:
    """Create a test client for the app."""
    return TestClient(app, raise_server_exceptions=False)


class TestAdminSessionsRevokeAuth:
    """Tests for /admin/sessions/revoke authorization (Feature 1148)."""

    def test_revoke_without_jwt_returns_401(self, client: TestClient) -> None:
        """Unauthenticated requests should return 401 Authentication required."""
        mock_ctx = mock_auth_context(user_id=None, roles=None)

        with patch(
            "src.lambdas.shared.middleware.require_role.extract_auth_context_typed",
            return_value=mock_ctx,
        ):
            response = client.post(
                "/api/v2/admin/sessions/revoke",
                json={"user_ids": ["user-1"], "reason": "test"},
            )
            assert response.status_code == 401
            assert response.json()["detail"] == "Authentication required"

    def test_revoke_without_operator_role_returns_403(self, client: TestClient) -> None:
        """Authenticated users without operator role should get 403."""
        mock_ctx = mock_auth_context(roles=["free"])

        with patch(
            "src.lambdas.shared.middleware.require_role.extract_auth_context_typed",
            return_value=mock_ctx,
        ):
            response = client.post(
                "/api/v2/admin/sessions/revoke",
                json={"user_ids": ["user-1"], "reason": "test"},
            )
            assert response.status_code == 403
            assert response.json()["detail"] == "Access denied"

    def test_revoke_with_paid_role_returns_403(self, client: TestClient) -> None:
        """Paid users without operator role should still get 403."""
        mock_ctx = mock_auth_context(roles=["free", "paid"])

        with patch(
            "src.lambdas.shared.middleware.require_role.extract_auth_context_typed",
            return_value=mock_ctx,
        ):
            response = client.post(
                "/api/v2/admin/sessions/revoke",
                json={"user_ids": ["user-1"], "reason": "test"},
            )
            assert response.status_code == 403
            assert response.json()["detail"] == "Access denied"

    def test_revoke_with_operator_role_succeeds(
        self, client: TestClient, mock_users_table: MagicMock
    ) -> None:
        """Operators should be able to access the revoke endpoint."""
        mock_ctx = mock_auth_context(roles=["free", "operator"])

        # Mock the auth service to return a successful response
        with (
            patch(
                "src.lambdas.shared.middleware.require_role.extract_auth_context_typed",
                return_value=mock_ctx,
            ),
            patch(
                "src.lambdas.dashboard.router_v2.auth_service.revoke_sessions_bulk"
            ) as mock_revoke,
        ):
            # Create a mock response
            mock_response = MagicMock()
            mock_response.model_dump.return_value = {
                "revoked_count": 1,
                "failed_count": 0,
                "failed_user_ids": [],
            }
            mock_revoke.return_value = mock_response

            response = client.post(
                "/api/v2/admin/sessions/revoke",
                json={"user_ids": ["user-1"], "reason": "security incident"},
            )
            assert response.status_code == 200
            assert response.json()["revoked_count"] == 1

    def test_error_message_does_not_enumerate_roles(self, client: TestClient) -> None:
        """403 error should NOT reveal required role (security requirement)."""
        mock_ctx = mock_auth_context(roles=["free"])

        with patch(
            "src.lambdas.shared.middleware.require_role.extract_auth_context_typed",
            return_value=mock_ctx,
        ):
            response = client.post(
                "/api/v2/admin/sessions/revoke",
                json={"user_ids": ["user-1"], "reason": "test"},
            )
            detail = response.json()["detail"]
            # Must NOT contain the required role name
            assert "operator" not in detail.lower()
            assert detail == "Access denied"

    def test_expired_token_returns_401(self, client: TestClient) -> None:
        """Expired JWT tokens should return 401."""
        # Simulate expired token by returning anonymous context with no user
        mock_ctx = mock_auth_context(
            user_id=None,
            auth_type=AuthType.ANONYMOUS,
            roles=None,
        )

        with patch(
            "src.lambdas.shared.middleware.require_role.extract_auth_context_typed",
            return_value=mock_ctx,
        ):
            response = client.post(
                "/api/v2/admin/sessions/revoke",
                json={"user_ids": ["user-1"], "reason": "test"},
            )
            assert response.status_code == 401


class TestAdminSessionsRevokeIntegration:
    """Integration tests for bulk revocation with proper authorization."""

    def test_bulk_revocation_with_multiple_users(
        self, client: TestClient, mock_users_table: MagicMock
    ) -> None:
        """Operators can revoke multiple sessions at once."""
        mock_ctx = mock_auth_context(roles=["free", "operator"])

        with (
            patch(
                "src.lambdas.shared.middleware.require_role.extract_auth_context_typed",
                return_value=mock_ctx,
            ),
            patch(
                "src.lambdas.dashboard.router_v2.auth_service.revoke_sessions_bulk"
            ) as mock_revoke,
        ):
            mock_response = MagicMock()
            mock_response.model_dump.return_value = {
                "revoked_count": 3,
                "failed_count": 1,
                "failed_user_ids": ["user-4"],
            }
            mock_revoke.return_value = mock_response

            response = client.post(
                "/api/v2/admin/sessions/revoke",
                json={
                    "user_ids": ["user-1", "user-2", "user-3", "user-4"],
                    "reason": "security incident response",
                },
            )
            assert response.status_code == 200
            data = response.json()
            assert data["revoked_count"] == 3
            assert data["failed_count"] == 1
            assert data["failed_user_ids"] == ["user-4"]

    def test_revocation_reason_passed_to_service(
        self, client: TestClient, mock_users_table: MagicMock
    ) -> None:
        """Revocation reason should be passed to the service layer."""
        mock_ctx = mock_auth_context(roles=["free", "operator"])

        with (
            patch(
                "src.lambdas.shared.middleware.require_role.extract_auth_context_typed",
                return_value=mock_ctx,
            ),
            patch(
                "src.lambdas.dashboard.router_v2.auth_service.revoke_sessions_bulk"
            ) as mock_revoke,
        ):
            mock_response = MagicMock()
            mock_response.model_dump.return_value = {
                "revoked_count": 1,
                "failed_count": 0,
                "failed_user_ids": [],
            }
            mock_revoke.return_value = mock_response

            response = client.post(
                "/api/v2/admin/sessions/revoke",
                json={
                    "user_ids": ["user-1"],
                    "reason": "Compromised credentials detected",
                },
            )
            assert response.status_code == 200

            # Verify the reason was passed correctly
            mock_revoke.assert_called_once()
            call_kwargs = mock_revoke.call_args.kwargs
            assert call_kwargs["reason"] == "Compromised credentials detected"
            assert call_kwargs["user_ids"] == ["user-1"]
