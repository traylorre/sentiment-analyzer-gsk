"""Tests for /admin/sessions/revoke endpoint authorization (Feature 1148).

Verifies that the bulk session revocation endpoint is properly protected
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


class TestAdminSessionsRevokeAuth:
    """Tests for /admin/sessions/revoke authorization (Feature 1148)."""

    def test_revoke_without_jwt_returns_401(self, mock_lambda_context) -> None:
        """Unauthenticated requests should return 401 Authentication required."""
        mock_ctx = mock_auth_context(user_id=None, roles=None)

        with patch(
            "src.lambdas.shared.middleware.require_role.extract_auth_context_typed",
            return_value=mock_ctx,
        ):
            response = lambda_handler(
                make_event(
                    method="POST",
                    path="/api/v2/admin/sessions/revoke",
                    body={"user_ids": ["user-1"], "reason": "test"},
                ),
                mock_lambda_context,
            )
            assert response["statusCode"] == 401
            assert json.loads(response["body"])["detail"] == "Authentication required"

    def test_revoke_without_operator_role_returns_403(
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
                    method="POST",
                    path="/api/v2/admin/sessions/revoke",
                    body={"user_ids": ["user-1"], "reason": "test"},
                ),
                mock_lambda_context,
            )
            assert response["statusCode"] == 403
            assert json.loads(response["body"])["detail"] == "Access denied"

    def test_revoke_with_paid_role_returns_403(self, mock_lambda_context) -> None:
        """Paid users without operator role should still get 403."""
        mock_ctx = mock_auth_context(roles=["free", "paid"])

        with patch(
            "src.lambdas.shared.middleware.require_role.extract_auth_context_typed",
            return_value=mock_ctx,
        ):
            response = lambda_handler(
                make_event(
                    method="POST",
                    path="/api/v2/admin/sessions/revoke",
                    body={"user_ids": ["user-1"], "reason": "test"},
                ),
                mock_lambda_context,
            )
            assert response["statusCode"] == 403
            assert json.loads(response["body"])["detail"] == "Access denied"

    def test_revoke_with_operator_role_succeeds(self, mock_lambda_context) -> None:
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
            patch(
                "src.lambdas.dashboard.router_v2.get_users_table",
                return_value=MagicMock(),
            ),
        ):
            # Create a mock response
            mock_response = MagicMock()
            mock_response.model_dump.return_value = {
                "revoked_count": 1,
                "failed_count": 0,
                "failed_user_ids": [],
            }
            mock_revoke.return_value = mock_response

            response = lambda_handler(
                make_event(
                    method="POST",
                    path="/api/v2/admin/sessions/revoke",
                    body={"user_ids": ["user-1"], "reason": "security incident"},
                ),
                mock_lambda_context,
            )
            assert response["statusCode"] == 200
            assert json.loads(response["body"])["revoked_count"] == 1

    def test_error_message_does_not_enumerate_roles(self, mock_lambda_context) -> None:
        """403 error should NOT reveal required role (security requirement)."""
        mock_ctx = mock_auth_context(roles=["free"])

        with patch(
            "src.lambdas.shared.middleware.require_role.extract_auth_context_typed",
            return_value=mock_ctx,
        ):
            response = lambda_handler(
                make_event(
                    method="POST",
                    path="/api/v2/admin/sessions/revoke",
                    body={"user_ids": ["user-1"], "reason": "test"},
                ),
                mock_lambda_context,
            )
            detail = json.loads(response["body"])["detail"]
            # Must NOT contain the required role name
            assert "operator" not in detail.lower()
            assert detail == "Access denied"

    def test_expired_token_returns_401(self, mock_lambda_context) -> None:
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
            response = lambda_handler(
                make_event(
                    method="POST",
                    path="/api/v2/admin/sessions/revoke",
                    body={"user_ids": ["user-1"], "reason": "test"},
                ),
                mock_lambda_context,
            )
            assert response["statusCode"] == 401


class TestAdminSessionsRevokeIntegration:
    """Integration tests for bulk revocation with proper authorization."""

    def test_bulk_revocation_with_multiple_users(self, mock_lambda_context) -> None:
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
            patch(
                "src.lambdas.dashboard.router_v2.get_users_table",
                return_value=MagicMock(),
            ),
        ):
            mock_response = MagicMock()
            mock_response.model_dump.return_value = {
                "revoked_count": 3,
                "failed_count": 1,
                "failed_user_ids": ["user-4"],
            }
            mock_revoke.return_value = mock_response

            response = lambda_handler(
                make_event(
                    method="POST",
                    path="/api/v2/admin/sessions/revoke",
                    body={
                        "user_ids": ["user-1", "user-2", "user-3", "user-4"],
                        "reason": "security incident response",
                    },
                ),
                mock_lambda_context,
            )
            assert response["statusCode"] == 200
            data = json.loads(response["body"])
            assert data["revoked_count"] == 3
            assert data["failed_count"] == 1
            assert data["failed_user_ids"] == ["user-4"]

    def test_revocation_reason_passed_to_service(self, mock_lambda_context) -> None:
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
            patch(
                "src.lambdas.dashboard.router_v2.get_users_table",
                return_value=MagicMock(),
            ),
        ):
            mock_response = MagicMock()
            mock_response.model_dump.return_value = {
                "revoked_count": 1,
                "failed_count": 0,
                "failed_user_ids": [],
            }
            mock_revoke.return_value = mock_response

            response = lambda_handler(
                make_event(
                    method="POST",
                    path="/api/v2/admin/sessions/revoke",
                    body={
                        "user_ids": ["user-1"],
                        "reason": "Compromised credentials detected",
                    },
                ),
                mock_lambda_context,
            )
            assert response["statusCode"] == 200

            # Verify the reason was passed correctly
            mock_revoke.assert_called_once()
            call_kwargs = mock_revoke.call_args.kwargs
            assert call_kwargs["reason"] == "Compromised credentials detected"
            assert call_kwargs["user_ids"] == ["user-1"]
