"""Tests for /users/lookup endpoint authorization (Feature 1149).

Verifies that the user lookup endpoint is properly protected
by require_role_middleware("operator") via Powertools middleware.
"""

import json
from unittest.mock import MagicMock, patch

from src.lambdas.dashboard.handler import lambda_handler
from src.lambdas.shared.middleware import AuthContext, AuthType
from tests.conftest import make_event


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


class TestUsersLookupAuth:
    """Tests for /users/lookup authorization (Feature 1149)."""

    def test_lookup_without_jwt_returns_401(self, mock_lambda_context) -> None:
        """Unauthenticated requests should return 401 Authentication required."""
        mock_ctx = mock_auth_context(user_id=None, roles=None)

        with patch(
            "src.lambdas.shared.middleware.require_role.extract_auth_context_typed",
            return_value=mock_ctx,
        ):
            response = lambda_handler(
                make_event(
                    method="GET",
                    path="/api/v2/users/lookup",
                    query_params={"email": "test@example.com"},
                ),
                mock_lambda_context,
            )
            assert response["statusCode"] == 401
            assert json.loads(response["body"])["detail"] == "Authentication required"

    def test_lookup_without_operator_role_returns_403(
        self, mock_lambda_context
    ) -> None:
        """Authenticated users without operator role should get 403."""
        mock_ctx = mock_auth_context(roles=["free"])

        with patch(
            "src.lambdas.shared.middleware.require_role.extract_auth_context_typed",
            return_value=mock_ctx,
        ):
            response = lambda_handler(
                make_event(
                    method="GET",
                    path="/api/v2/users/lookup",
                    query_params={"email": "test@example.com"},
                ),
                mock_lambda_context,
            )
            assert response["statusCode"] == 403
            assert json.loads(response["body"])["detail"] == "Access denied"

    def test_lookup_with_paid_role_returns_403(self, mock_lambda_context) -> None:
        """Paid users without operator role should still get 403."""
        mock_ctx = mock_auth_context(roles=["free", "paid"])

        with patch(
            "src.lambdas.shared.middleware.require_role.extract_auth_context_typed",
            return_value=mock_ctx,
        ):
            response = lambda_handler(
                make_event(
                    method="GET",
                    path="/api/v2/users/lookup",
                    query_params={"email": "test@example.com"},
                ),
                mock_lambda_context,
            )
            assert response["statusCode"] == 403
            assert json.loads(response["body"])["detail"] == "Access denied"

    def test_lookup_with_operator_role_succeeds(self, mock_lambda_context) -> None:
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
            patch(
                "src.lambdas.dashboard.router_v2.get_users_table",
                return_value=MagicMock(),
            ),
        ):
            # Create a mock user object
            mock_user = MagicMock()
            mock_user.user_id = "found-user-id"
            mock_user.auth_type = "oauth"
            mock_user.email = "test@example.com"
            mock_lookup.return_value = mock_user

            # Mock the mask_email function
            with patch(
                "src.lambdas.dashboard.router_v2.mask_email",
                return_value="t***@example.com",
            ):
                response = lambda_handler(
                    make_event(
                        method="GET",
                        path="/api/v2/users/lookup",
                        query_params={"email": "test@example.com"},
                    ),
                    mock_lambda_context,
                )
                assert response["statusCode"] == 200
                data = json.loads(response["body"])
                assert data["found"] is True
                assert data["user_id"] == "found-user-id"

    def test_lookup_user_not_found_returns_200_with_found_false(
        self, mock_lambda_context
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
            patch(
                "src.lambdas.dashboard.router_v2.get_users_table",
                return_value=MagicMock(),
            ),
        ):
            response = lambda_handler(
                make_event(
                    method="GET",
                    path="/api/v2/users/lookup",
                    query_params={"email": "nonexistent@example.com"},
                ),
                mock_lambda_context,
            )
            assert response["statusCode"] == 200
            data = json.loads(response["body"])
            assert data["found"] is False
            assert data["user_id"] is None

    def test_error_message_does_not_enumerate_roles(self, mock_lambda_context) -> None:
        """403 error should NOT reveal required role (security requirement)."""
        mock_ctx = mock_auth_context(roles=["free"])

        with patch(
            "src.lambdas.shared.middleware.require_role.extract_auth_context_typed",
            return_value=mock_ctx,
        ):
            response = lambda_handler(
                make_event(
                    method="GET",
                    path="/api/v2/users/lookup",
                    query_params={"email": "test@example.com"},
                ),
                mock_lambda_context,
            )
            detail = json.loads(response["body"])["detail"]
            # Must NOT contain the required role name
            assert "operator" not in detail.lower()
            assert detail == "Access denied"

    def test_anonymous_token_returns_401(self, mock_lambda_context) -> None:
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
            response = lambda_handler(
                make_event(
                    method="GET",
                    path="/api/v2/users/lookup",
                    query_params={"email": "test@example.com"},
                ),
                mock_lambda_context,
            )
            assert response["statusCode"] == 401
