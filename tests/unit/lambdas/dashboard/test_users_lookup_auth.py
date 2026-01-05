"""Tests for /users/lookup endpoint authorization (Feature 1149).

Verifies that the user lookup endpoint is properly protected
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
    """Create a FastAPI app with the users router for testing."""
    from src.lambdas.dashboard.router_v2 import get_users_table, users_router

    test_app = FastAPI()
    test_app.include_router(users_router)

    # Override the users table dependency
    test_app.dependency_overrides[get_users_table] = lambda: mock_users_table

    return test_app


@pytest.fixture
def client(app: FastAPI) -> TestClient:
    """Create a test client for the app."""
    return TestClient(app, raise_server_exceptions=False)


class TestUsersLookupAuth:
    """Tests for /users/lookup authorization (Feature 1149)."""

    def test_lookup_without_jwt_returns_401(self, client: TestClient) -> None:
        """Unauthenticated requests should return 401 Authentication required."""
        mock_ctx = mock_auth_context(user_id=None, roles=None)

        with patch(
            "src.lambdas.shared.middleware.require_role.extract_auth_context_typed",
            return_value=mock_ctx,
        ):
            response = client.get(
                "/api/v2/users/lookup",
                params={"email": "test@example.com"},
            )
            assert response.status_code == 401
            assert response.json()["detail"] == "Authentication required"

    def test_lookup_without_operator_role_returns_403(self, client: TestClient) -> None:
        """Authenticated users without operator role should get 403."""
        mock_ctx = mock_auth_context(roles=["free"])

        with patch(
            "src.lambdas.shared.middleware.require_role.extract_auth_context_typed",
            return_value=mock_ctx,
        ):
            response = client.get(
                "/api/v2/users/lookup",
                params={"email": "test@example.com"},
            )
            assert response.status_code == 403
            assert response.json()["detail"] == "Access denied"

    def test_lookup_with_paid_role_returns_403(self, client: TestClient) -> None:
        """Paid users without operator role should still get 403."""
        mock_ctx = mock_auth_context(roles=["free", "paid"])

        with patch(
            "src.lambdas.shared.middleware.require_role.extract_auth_context_typed",
            return_value=mock_ctx,
        ):
            response = client.get(
                "/api/v2/users/lookup",
                params={"email": "test@example.com"},
            )
            assert response.status_code == 403
            assert response.json()["detail"] == "Access denied"

    def test_lookup_with_operator_role_succeeds(
        self, client: TestClient, mock_users_table: MagicMock
    ) -> None:
        """Operators should be able to access the lookup endpoint."""
        mock_ctx = mock_auth_context(roles=["free", "operator"])

        # Mock the auth service to return a found user
        with (
            patch(
                "src.lambdas.shared.middleware.require_role.extract_auth_context_typed",
                return_value=mock_ctx,
            ),
            patch(
                "src.lambdas.dashboard.router_v2.auth_service.get_user_by_email_gsi"
            ) as mock_lookup,
        ):
            # Create a mock user object
            mock_user = MagicMock()
            mock_user.user_id = "found-user-id"
            mock_user.auth_type = "oauth"
            mock_user.email = "test@example.com"
            mock_lookup.return_value = mock_user

            # Mock the mask_email function
            with patch(
                "src.lambdas.dashboard.router_v2.auth_service._mask_email",
                return_value="t***@example.com",
            ):
                response = client.get(
                    "/api/v2/users/lookup",
                    params={"email": "test@example.com"},
                )
                assert response.status_code == 200
                data = response.json()
                assert data["found"] is True
                assert data["user_id"] == "found-user-id"

    def test_lookup_user_not_found_returns_200_with_found_false(
        self, client: TestClient, mock_users_table: MagicMock
    ) -> None:
        """Operators looking up non-existent users should get 200 with found=false."""
        mock_ctx = mock_auth_context(roles=["free", "operator"])

        with (
            patch(
                "src.lambdas.shared.middleware.require_role.extract_auth_context_typed",
                return_value=mock_ctx,
            ),
            patch(
                "src.lambdas.dashboard.router_v2.auth_service.get_user_by_email_gsi",
                return_value=None,
            ),
        ):
            response = client.get(
                "/api/v2/users/lookup",
                params={"email": "nonexistent@example.com"},
            )
            assert response.status_code == 200
            data = response.json()
            assert data["found"] is False
            assert data["user_id"] is None

    def test_error_message_does_not_enumerate_roles(self, client: TestClient) -> None:
        """403 error should NOT reveal required role (security requirement)."""
        mock_ctx = mock_auth_context(roles=["free"])

        with patch(
            "src.lambdas.shared.middleware.require_role.extract_auth_context_typed",
            return_value=mock_ctx,
        ):
            response = client.get(
                "/api/v2/users/lookup",
                params={"email": "test@example.com"},
            )
            detail = response.json()["detail"]
            # Must NOT contain the required role name
            assert "operator" not in detail.lower()
            assert detail == "Access denied"

    def test_anonymous_token_returns_401(self, client: TestClient) -> None:
        """Anonymous tokens should return 401."""
        mock_ctx = mock_auth_context(
            user_id=None,
            auth_type=AuthType.ANONYMOUS,
            roles=None,
        )

        with patch(
            "src.lambdas.shared.middleware.require_role.extract_auth_context_typed",
            return_value=mock_ctx,
        ):
            response = client.get(
                "/api/v2/users/lookup",
                params={"email": "test@example.com"},
            )
            assert response.status_code == 401
