"""Unit tests for require_role_middleware (Feature 1130).

Tests cover:
- US1: Operator access to admin endpoints (P1)
- US2: Multiple role levels (P2)
- US3: Composability with Powertools middleware (P3)
- Error message security (no role enumeration)
- Startup validation of role parameters

Migration: Tests now invoke require_role_middleware as a Powertools middleware
through lambda_handler, or test the middleware factory directly.
"""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import pytest

from src.lambdas.dashboard.handler import lambda_handler
from src.lambdas.shared.auth.enums import VALID_ROLES
from src.lambdas.shared.errors.auth_errors import InvalidRoleError
from src.lambdas.shared.middleware import AuthContext, AuthType
from src.lambdas.shared.middleware.require_role import require_role_middleware
from tests.conftest import make_event

# ============================================================================
# Test Fixtures
# ============================================================================


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


# ============================================================================
# US1: Protect Admin Endpoints (P1)
# ============================================================================


class TestOperatorAccess:
    """Tests for operator role access control (US1).

    Tests use the real /api/v2/admin/sessions/revoke endpoint which
    has require_role_middleware("operator") applied.
    """

    def test_operator_can_access_protected_endpoint(self, mock_lambda_context) -> None:
        """Operators should be able to access @require_role('operator') endpoints."""
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
                "revoked_count": 0,
                "failed_count": 0,
                "failed_user_ids": [],
            }
            mock_revoke.return_value = mock_response

            response = lambda_handler(
                make_event(
                    method="POST",
                    path="/api/v2/admin/sessions/revoke",
                    body={"user_ids": [], "reason": "test"},
                ),
                mock_lambda_context,
            )
            assert response["statusCode"] == 200

    def test_non_operator_gets_403(self, mock_lambda_context) -> None:
        """Non-operators should receive 403 Access denied."""
        mock_ctx = mock_auth_context(roles=["free"])

        with patch(
            "src.lambdas.shared.middleware.require_role.extract_auth_context_typed",
            return_value=mock_ctx,
        ):
            response = lambda_handler(
                make_event(
                    method="POST",
                    path="/api/v2/admin/sessions/revoke",
                    body={"user_ids": [], "reason": "test"},
                ),
                mock_lambda_context,
            )
            assert response["statusCode"] == 403
            assert json.loads(response["body"])["detail"] == "Access denied"

    def test_unauthenticated_user_gets_401(self, mock_lambda_context) -> None:
        """Unauthenticated users should receive 401 Authentication required."""
        mock_ctx = mock_auth_context(user_id=None, roles=None)

        with patch(
            "src.lambdas.shared.middleware.require_role.extract_auth_context_typed",
            return_value=mock_ctx,
        ):
            response = lambda_handler(
                make_event(
                    method="POST",
                    path="/api/v2/admin/sessions/revoke",
                    body={"user_ids": [], "reason": "test"},
                ),
                mock_lambda_context,
            )
            assert response["statusCode"] == 401
            assert json.loads(response["body"])["detail"] == "Authentication required"

    def test_missing_roles_claim_gets_401(self, mock_lambda_context) -> None:
        """User with no roles claim should receive 401 Invalid token structure."""
        mock_ctx = mock_auth_context(user_id="test-user", roles=None)

        with patch(
            "src.lambdas.shared.middleware.require_role.extract_auth_context_typed",
            return_value=mock_ctx,
        ):
            response = lambda_handler(
                make_event(
                    method="POST",
                    path="/api/v2/admin/sessions/revoke",
                    body={"user_ids": [], "reason": "test"},
                ),
                mock_lambda_context,
            )
            assert response["statusCode"] == 401
            assert json.loads(response["body"])["detail"] == "Invalid token structure"


class TestGenericErrorMessages:
    """Tests for role enumeration prevention (FR-004)."""

    def test_error_does_not_reveal_required_role(self, mock_lambda_context) -> None:
        """403 error should NOT reveal what role is required."""
        mock_ctx = mock_auth_context(roles=["free"])

        with patch(
            "src.lambdas.shared.middleware.require_role.extract_auth_context_typed",
            return_value=mock_ctx,
        ):
            response = lambda_handler(
                make_event(
                    method="POST",
                    path="/api/v2/admin/sessions/revoke",
                    body={"user_ids": [], "reason": "test"},
                ),
                mock_lambda_context,
            )
            detail = json.loads(response["body"])["detail"]
            # Must NOT contain the required role name
            assert "operator" not in detail.lower()
            assert detail == "Access denied"

    def test_all_role_failures_use_same_message(self, mock_lambda_context) -> None:
        """All role check failures should return the same generic message.

        Tests both the admin (operator) and users lookup (operator) endpoints
        to verify consistent error messages.
        """
        mock_ctx = mock_auth_context(roles=["anonymous"])

        with patch(
            "src.lambdas.shared.middleware.require_role.extract_auth_context_typed",
            return_value=mock_ctx,
        ):
            response1 = lambda_handler(
                make_event(
                    method="POST",
                    path="/api/v2/admin/sessions/revoke",
                    body={"user_ids": [], "reason": "test"},
                ),
                mock_lambda_context,
            )
            response2 = lambda_handler(
                make_event(
                    method="GET",
                    path="/api/v2/users/lookup",
                    query_params={"email": "test@example.com"},
                ),
                mock_lambda_context,
            )

            # Both should have identical error responses
            assert response1["statusCode"] == response2["statusCode"] == 403
            detail1 = json.loads(response1["body"])["detail"]
            detail2 = json.loads(response2["body"])["detail"]
            assert detail1 == detail2
            assert detail1 == "Access denied"


class TestStartupValidation:
    """Tests for decoration-time role validation (FR-005)."""

    def test_invalid_role_raises_at_decoration_time(self) -> None:
        """Invalid role parameter should raise InvalidRoleError immediately."""
        with pytest.raises(InvalidRoleError) as exc_info:
            require_role_middleware("admn")  # Typo!

        assert exc_info.value.role == "admn"
        assert exc_info.value.valid_roles == VALID_ROLES

    def test_invalid_role_error_message_lists_valid_roles(self) -> None:
        """InvalidRoleError message should list valid roles for debugging."""
        with pytest.raises(InvalidRoleError) as exc_info:
            require_role_middleware("superuser")

        error_message = str(exc_info.value)
        assert "superuser" in error_message
        assert "Valid roles:" in error_message
        # Valid roles should be listed
        for role in ["anonymous", "free", "paid", "operator"]:
            assert role in error_message

    @pytest.mark.parametrize("valid_role", ["anonymous", "free", "paid", "operator"])
    def test_valid_roles_do_not_raise(self, valid_role: str) -> None:
        """Valid role parameters should not raise at decoration time."""
        # Should not raise - returns a middleware function
        middleware = require_role_middleware(valid_role)
        assert callable(middleware)


# ============================================================================
# US2: Support Multiple Role Levels (P2)
# ============================================================================


class TestPaidRoleRequirement:
    """Tests for paid role access control (US2).

    Tests the middleware factory directly since no production endpoint
    uses require_role_middleware("paid") yet.
    """

    def test_paid_user_passes_paid_middleware(self) -> None:
        """Paid users should pass the paid role middleware check."""
        mock_ctx = mock_auth_context(roles=["free", "paid"])
        middleware = require_role_middleware("paid")

        mock_app = MagicMock()
        mock_app.current_event.raw_event = make_event(
            method="GET",
            path="/premium/analytics",
        )

        with patch(
            "src.lambdas.shared.middleware.require_role.extract_auth_context_typed",
            return_value=mock_ctx,
        ):
            mock_next = MagicMock(return_value={"statusCode": 200, "body": "{}"})
            middleware(mock_app, mock_next)
            mock_next.assert_called_once_with(mock_app)

    def test_free_user_blocked_by_paid_middleware(self) -> None:
        """Free users should not pass the paid role middleware check."""
        mock_ctx = mock_auth_context(roles=["free"])
        middleware = require_role_middleware("paid")

        mock_app = MagicMock()
        mock_app.current_event.raw_event = make_event(
            method="GET",
            path="/premium/analytics",
        )

        with patch(
            "src.lambdas.shared.middleware.require_role.extract_auth_context_typed",
            return_value=mock_ctx,
        ):
            mock_next = MagicMock()
            result = middleware(mock_app, mock_next)
            mock_next.assert_not_called()
            assert result.status_code == 403


class TestFreeRoleRequirement:
    """Tests for free role access control (US2)."""

    def test_free_user_passes_free_middleware(self) -> None:
        """Free users should pass the free role middleware check."""
        mock_ctx = mock_auth_context(roles=["free"])
        middleware = require_role_middleware("free")

        mock_app = MagicMock()
        mock_app.current_event.raw_event = make_event(
            method="GET",
            path="/basic/feature",
        )

        with patch(
            "src.lambdas.shared.middleware.require_role.extract_auth_context_typed",
            return_value=mock_ctx,
        ):
            mock_next = MagicMock(return_value={"statusCode": 200, "body": "{}"})
            middleware(mock_app, mock_next)
            mock_next.assert_called_once_with(mock_app)


class TestRoleAccumulation:
    """Tests for role accumulation behavior (US2)."""

    def test_operator_can_pass_paid_middleware(self) -> None:
        """Operators with paid role should pass the paid middleware."""
        # Operator has accumulated roles
        mock_ctx = mock_auth_context(roles=["free", "paid", "operator"])
        middleware = require_role_middleware("paid")

        mock_app = MagicMock()
        mock_app.current_event.raw_event = make_event(
            method="GET",
            path="/premium/analytics",
        )

        with patch(
            "src.lambdas.shared.middleware.require_role.extract_auth_context_typed",
            return_value=mock_ctx,
        ):
            mock_next = MagicMock(return_value={"statusCode": 200, "body": "{}"})
            middleware(mock_app, mock_next)
            mock_next.assert_called_once_with(mock_app)

    def test_operator_can_pass_free_middleware(self) -> None:
        """Operators with free role should pass the free middleware."""
        mock_ctx = mock_auth_context(roles=["free", "operator"])
        middleware = require_role_middleware("free")

        mock_app = MagicMock()
        mock_app.current_event.raw_event = make_event(
            method="GET",
            path="/basic/feature",
        )

        with patch(
            "src.lambdas.shared.middleware.require_role.extract_auth_context_typed",
            return_value=mock_ctx,
        ):
            mock_next = MagicMock(return_value={"statusCode": 200, "body": "{}"})
            middleware(mock_app, mock_next)
            mock_next.assert_called_once_with(mock_app)


# ============================================================================
# US3: Composable with Existing Auth (P3)
# ============================================================================


class TestMiddlewareCompatibility:
    """Tests for compatibility with Powertools middleware chain (US3)."""

    def test_middleware_chains_with_next(self) -> None:
        """Middleware should call next_middleware when role check passes."""
        mock_ctx = mock_auth_context(roles=["free", "operator"])
        middleware = require_role_middleware("operator")

        mock_app = MagicMock()
        mock_app.current_event.raw_event = make_event(
            method="POST",
            path="/admin/config",
        )

        with patch(
            "src.lambdas.shared.middleware.require_role.extract_auth_context_typed",
            return_value=mock_ctx,
        ):
            expected_result = {"statusCode": 200, "body": '{"config": "value"}'}
            mock_next = MagicMock(return_value=expected_result)
            result = middleware(mock_app, mock_next)
            assert result == expected_result
            mock_next.assert_called_once_with(mock_app)

    def test_middleware_factory_returns_callable(self) -> None:
        """Middleware factory should return a callable function."""
        middleware = require_role_middleware("operator")
        assert callable(middleware)

        # The middleware function should accept (app, next_middleware)
        import inspect

        sig = inspect.signature(middleware)
        assert len(sig.parameters) == 2


class TestAsyncHandlerCompatibility:
    """Tests for handler compatibility through lambda_handler (US3)."""

    def test_middleware_works_through_lambda_handler(self, mock_lambda_context) -> None:
        """Middleware should work correctly when invoked through lambda_handler."""
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
            mock_resp = MagicMock()
            mock_resp.model_dump.return_value = {
                "revoked_count": 0,
                "failed_count": 0,
                "failed_user_ids": [],
            }
            mock_revoke.return_value = mock_resp

            response = lambda_handler(
                make_event(
                    method="POST",
                    path="/api/v2/admin/sessions/revoke",
                    body={"user_ids": [], "reason": "test"},
                ),
                mock_lambda_context,
            )
            assert response["statusCode"] == 200


# ============================================================================
# Edge Cases
# ============================================================================


class TestEdgeCases:
    """Tests for edge cases and boundary conditions."""

    def test_empty_roles_list_returns_403(self) -> None:
        """Empty roles list should result in 403 for any role requirement."""
        mock_ctx = mock_auth_context(roles=[])
        middleware = require_role_middleware("free")

        mock_app = MagicMock()
        mock_app.current_event.raw_event = make_event(
            method="GET",
            path="/endpoint",
        )

        with patch(
            "src.lambdas.shared.middleware.require_role.extract_auth_context_typed",
            return_value=mock_ctx,
        ):
            mock_next = MagicMock()
            result = middleware(mock_app, mock_next)
            mock_next.assert_not_called()
            assert result.status_code == 403

    def test_case_sensitive_role_matching(self) -> None:
        """Role matching should be case-sensitive."""
        # Roles with wrong case
        mock_ctx = mock_auth_context(roles=["OPERATOR", "Operator"])
        middleware = require_role_middleware("operator")

        mock_app = MagicMock()
        mock_app.current_event.raw_event = make_event(
            method="GET",
            path="/endpoint",
        )

        with patch(
            "src.lambdas.shared.middleware.require_role.extract_auth_context_typed",
            return_value=mock_ctx,
        ):
            mock_next = MagicMock()
            result = middleware(mock_app, mock_next)
            mock_next.assert_not_called()
            assert result.status_code == 403  # Case mismatch should fail

    def test_anonymous_role_for_public_with_tracking(self) -> None:
        """Anonymous role should work for public content with session tracking."""
        mock_ctx = mock_auth_context(roles=["anonymous"])
        middleware = require_role_middleware("anonymous")

        mock_app = MagicMock()
        mock_app.current_event.raw_event = make_event(
            method="GET",
            path="/public/content",
        )

        with patch(
            "src.lambdas.shared.middleware.require_role.extract_auth_context_typed",
            return_value=mock_ctx,
        ):
            mock_next = MagicMock(
                return_value={"statusCode": 200, "body": '{"content": "public"}'}
            )
            result = middleware(mock_app, mock_next)
            mock_next.assert_called_once_with(mock_app)
            assert result["statusCode"] == 200
