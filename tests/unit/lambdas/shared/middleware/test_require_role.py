"""Unit tests for @require_role decorator (Feature 1130).

Tests cover:
- US1: Operator access to admin endpoints (P1)
- US2: Multiple role levels (P2)
- US3: Composability with FastAPI Depends (P3)
- Error message security (no role enumeration)
- Startup validation of role parameters
"""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock, patch

import pytest
from fastapi import Depends, FastAPI, Request
from fastapi.testclient import TestClient

from src.lambdas.shared.auth.constants import VALID_ROLES
from src.lambdas.shared.errors.auth_errors import InvalidRoleError
from src.lambdas.shared.middleware import AuthContext, AuthType
from src.lambdas.shared.middleware.require_role import require_role

# ============================================================================
# Test Fixtures
# ============================================================================


@pytest.fixture
def app() -> FastAPI:
    """Create a FastAPI app for testing."""
    return FastAPI()


@pytest.fixture
def client(app: FastAPI) -> TestClient:
    """Create a test client for the app."""
    return TestClient(app, raise_server_exceptions=False)


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
    """Tests for operator role access control (US1)."""

    def test_operator_can_access_protected_endpoint(
        self, app: FastAPI, client: TestClient
    ) -> None:
        """Operators should be able to access @require_role('operator') endpoints."""

        @app.post("/admin/sessions/revoke")
        @require_role("operator")
        async def revoke_sessions(request: Request) -> dict[str, str]:
            return {"status": "revoked"}

        mock_ctx = mock_auth_context(roles=["free", "operator"])

        with patch(
            "src.lambdas.shared.middleware.require_role.extract_auth_context_typed",
            return_value=mock_ctx,
        ):
            response = client.post("/admin/sessions/revoke")
            assert response.status_code == 200
            assert response.json() == {"status": "revoked"}

    def test_non_operator_gets_403(self, app: FastAPI, client: TestClient) -> None:
        """Non-operators should receive 403 Access denied."""

        @app.post("/admin/sessions/revoke")
        @require_role("operator")
        async def revoke_sessions(request: Request) -> dict[str, str]:
            return {"status": "revoked"}

        mock_ctx = mock_auth_context(roles=["free"])

        with patch(
            "src.lambdas.shared.middleware.require_role.extract_auth_context_typed",
            return_value=mock_ctx,
        ):
            response = client.post("/admin/sessions/revoke")
            assert response.status_code == 403
            assert response.json()["detail"] == "Access denied"

    def test_unauthenticated_user_gets_401(
        self, app: FastAPI, client: TestClient
    ) -> None:
        """Unauthenticated users should receive 401 Authentication required."""

        @app.post("/admin/sessions/revoke")
        @require_role("operator")
        async def revoke_sessions(request: Request) -> dict[str, str]:
            return {"status": "revoked"}

        mock_ctx = mock_auth_context(user_id=None, roles=None)

        with patch(
            "src.lambdas.shared.middleware.require_role.extract_auth_context_typed",
            return_value=mock_ctx,
        ):
            response = client.post("/admin/sessions/revoke")
            assert response.status_code == 401
            assert response.json()["detail"] == "Authentication required"

    def test_missing_roles_claim_gets_401(
        self, app: FastAPI, client: TestClient
    ) -> None:
        """User with no roles claim should receive 401 Invalid token structure."""

        @app.post("/admin/sessions/revoke")
        @require_role("operator")
        async def revoke_sessions(request: Request) -> dict[str, str]:
            return {"status": "revoked"}

        mock_ctx = mock_auth_context(user_id="test-user", roles=None)

        with patch(
            "src.lambdas.shared.middleware.require_role.extract_auth_context_typed",
            return_value=mock_ctx,
        ):
            response = client.post("/admin/sessions/revoke")
            assert response.status_code == 401
            assert response.json()["detail"] == "Invalid token structure"


class TestGenericErrorMessages:
    """Tests for role enumeration prevention (FR-004)."""

    def test_error_does_not_reveal_required_role(
        self, app: FastAPI, client: TestClient
    ) -> None:
        """403 error should NOT reveal what role is required."""

        @app.post("/admin/endpoint")
        @require_role("operator")
        async def admin_endpoint(request: Request) -> dict[str, str]:
            return {"status": "ok"}

        mock_ctx = mock_auth_context(roles=["free"])

        with patch(
            "src.lambdas.shared.middleware.require_role.extract_auth_context_typed",
            return_value=mock_ctx,
        ):
            response = client.post("/admin/endpoint")
            detail = response.json()["detail"]
            # Must NOT contain the required role name
            assert "operator" not in detail.lower()
            assert detail == "Access denied"

    def test_all_role_failures_use_same_message(
        self, app: FastAPI, client: TestClient
    ) -> None:
        """All role check failures should return the same generic message."""

        @app.post("/endpoint-operator")
        @require_role("operator")
        async def operator_endpoint(request: Request) -> dict[str, str]:
            return {"status": "ok"}

        @app.post("/endpoint-paid")
        @require_role("paid")
        async def paid_endpoint(request: Request) -> dict[str, str]:
            return {"status": "ok"}

        mock_ctx = mock_auth_context(roles=["anonymous"])

        with patch(
            "src.lambdas.shared.middleware.require_role.extract_auth_context_typed",
            return_value=mock_ctx,
        ):
            response1 = client.post("/endpoint-operator")
            response2 = client.post("/endpoint-paid")

            # Both should have identical error responses
            assert response1.status_code == response2.status_code == 403
            assert response1.json()["detail"] == response2.json()["detail"]
            assert response1.json()["detail"] == "Access denied"


class TestStartupValidation:
    """Tests for decoration-time role validation (FR-005)."""

    def test_invalid_role_raises_at_decoration_time(self) -> None:
        """Invalid role parameter should raise InvalidRoleError immediately."""
        with pytest.raises(InvalidRoleError) as exc_info:

            @require_role("admn")  # Typo!
            async def endpoint(request: Request) -> dict[str, str]:
                return {"status": "ok"}

        assert exc_info.value.role == "admn"
        assert exc_info.value.valid_roles == VALID_ROLES

    def test_invalid_role_error_message_lists_valid_roles(self) -> None:
        """InvalidRoleError message should list valid roles for debugging."""
        with pytest.raises(InvalidRoleError) as exc_info:

            @require_role("superuser")
            async def endpoint(request: Request) -> dict[str, str]:
                return {"status": "ok"}

        error_message = str(exc_info.value)
        assert "superuser" in error_message
        assert "Valid roles:" in error_message
        # Valid roles should be listed
        for role in ["anonymous", "free", "paid", "operator"]:
            assert role in error_message

    @pytest.mark.parametrize("valid_role", ["anonymous", "free", "paid", "operator"])
    def test_valid_roles_do_not_raise(self, valid_role: str) -> None:
        """Valid role parameters should not raise at decoration time."""

        # Should not raise
        @require_role(valid_role)
        async def endpoint(request: Request) -> dict[str, str]:
            return {"status": "ok"}


# ============================================================================
# US2: Support Multiple Role Levels (P2)
# ============================================================================


class TestPaidRoleRequirement:
    """Tests for paid role access control (US2)."""

    def test_paid_user_can_access_paid_endpoint(
        self, app: FastAPI, client: TestClient
    ) -> None:
        """Paid users should access @require_role('paid') endpoints."""

        @app.get("/premium/analytics")
        @require_role("paid")
        async def premium_analytics(request: Request) -> dict[str, str]:
            return {"data": "premium"}

        mock_ctx = mock_auth_context(roles=["free", "paid"])

        with patch(
            "src.lambdas.shared.middleware.require_role.extract_auth_context_typed",
            return_value=mock_ctx,
        ):
            response = client.get("/premium/analytics")
            assert response.status_code == 200

    def test_free_user_cannot_access_paid_endpoint(
        self, app: FastAPI, client: TestClient
    ) -> None:
        """Free users should not access @require_role('paid') endpoints."""

        @app.get("/premium/analytics")
        @require_role("paid")
        async def premium_analytics(request: Request) -> dict[str, str]:
            return {"data": "premium"}

        mock_ctx = mock_auth_context(roles=["free"])

        with patch(
            "src.lambdas.shared.middleware.require_role.extract_auth_context_typed",
            return_value=mock_ctx,
        ):
            response = client.get("/premium/analytics")
            assert response.status_code == 403


class TestFreeRoleRequirement:
    """Tests for free role access control (US2)."""

    def test_free_user_can_access_free_endpoint(
        self, app: FastAPI, client: TestClient
    ) -> None:
        """Free users should access @require_role('free') endpoints."""

        @app.get("/basic/feature")
        @require_role("free")
        async def basic_feature(request: Request) -> dict[str, str]:
            return {"data": "basic"}

        mock_ctx = mock_auth_context(roles=["free"])

        with patch(
            "src.lambdas.shared.middleware.require_role.extract_auth_context_typed",
            return_value=mock_ctx,
        ):
            response = client.get("/basic/feature")
            assert response.status_code == 200


class TestRoleAccumulation:
    """Tests for role accumulation behavior (US2)."""

    def test_operator_can_access_paid_endpoint(
        self, app: FastAPI, client: TestClient
    ) -> None:
        """Operators with paid role should access @require_role('paid') endpoints."""

        @app.get("/premium/analytics")
        @require_role("paid")
        async def premium_analytics(request: Request) -> dict[str, str]:
            return {"data": "premium"}

        # Operator has accumulated roles
        mock_ctx = mock_auth_context(roles=["free", "paid", "operator"])

        with patch(
            "src.lambdas.shared.middleware.require_role.extract_auth_context_typed",
            return_value=mock_ctx,
        ):
            response = client.get("/premium/analytics")
            assert response.status_code == 200

    def test_operator_can_access_free_endpoint(
        self, app: FastAPI, client: TestClient
    ) -> None:
        """Operators with free role should access @require_role('free') endpoints."""

        @app.get("/basic/feature")
        @require_role("free")
        async def basic_feature(request: Request) -> dict[str, str]:
            return {"data": "basic"}

        mock_ctx = mock_auth_context(roles=["free", "operator"])

        with patch(
            "src.lambdas.shared.middleware.require_role.extract_auth_context_typed",
            return_value=mock_ctx,
        ):
            response = client.get("/basic/feature")
            assert response.status_code == 200


# ============================================================================
# US3: Composable with Existing Auth (P3)
# ============================================================================


class TestDependencyInjectionCompatibility:
    """Tests for compatibility with FastAPI Depends() (US3)."""

    def test_decorator_works_with_depends(
        self, app: FastAPI, client: TestClient
    ) -> None:
        """Decorator should work alongside Depends() injected parameters."""

        def get_config() -> dict[str, str]:
            return {"setting": "value"}

        @app.post("/admin/config")
        @require_role("operator")
        async def update_config(
            request: Request,
            config: dict[str, str] = Depends(get_config),  # noqa: B008
        ) -> dict[str, Any]:
            return {"config": config}

        mock_ctx = mock_auth_context(roles=["free", "operator"])

        with patch(
            "src.lambdas.shared.middleware.require_role.extract_auth_context_typed",
            return_value=mock_ctx,
        ):
            response = client.post("/admin/config")
            assert response.status_code == 200
            assert response.json()["config"] == {"setting": "value"}

    def test_decorator_preserves_function_signature(self) -> None:
        """Decorator should preserve the wrapped function's metadata."""

        @require_role("operator")
        async def my_endpoint(request: Request) -> dict[str, str]:
            """My endpoint docstring."""
            return {"status": "ok"}

        assert my_endpoint.__name__ == "my_endpoint"
        assert my_endpoint.__doc__ == "My endpoint docstring."


class TestAsyncHandlerCompatibility:
    """Tests for async handler compatibility (US3)."""

    def test_decorator_works_with_async_handlers(
        self, app: FastAPI, client: TestClient
    ) -> None:
        """Decorator should work with async def handlers."""

        @app.get("/async/endpoint")
        @require_role("free")
        async def async_endpoint(request: Request) -> dict[str, str]:
            return {"async": "true"}

        mock_ctx = mock_auth_context(roles=["free"])

        with patch(
            "src.lambdas.shared.middleware.require_role.extract_auth_context_typed",
            return_value=mock_ctx,
        ):
            response = client.get("/async/endpoint")
            assert response.status_code == 200
            assert response.json() == {"async": "true"}

    def test_decorator_with_multiple_dependencies(
        self, app: FastAPI, client: TestClient
    ) -> None:
        """Decorator should work with multiple Depends() parameters."""

        def get_db() -> MagicMock:
            return MagicMock(name="db")

        def get_cache() -> MagicMock:
            return MagicMock(name="cache")

        @app.post("/admin/operation")
        @require_role("operator")
        async def admin_operation(
            request: Request,
            db: MagicMock = Depends(get_db),  # noqa: B008
            cache: MagicMock = Depends(get_cache),  # noqa: B008
        ) -> dict[str, str]:
            return {"db": str(db), "cache": str(cache)}

        mock_ctx = mock_auth_context(roles=["free", "operator"])

        with patch(
            "src.lambdas.shared.middleware.require_role.extract_auth_context_typed",
            return_value=mock_ctx,
        ):
            response = client.post("/admin/operation")
            assert response.status_code == 200


# ============================================================================
# Edge Cases
# ============================================================================


class TestEdgeCases:
    """Tests for edge cases and boundary conditions."""

    def test_empty_roles_list_returns_403(
        self, app: FastAPI, client: TestClient
    ) -> None:
        """Empty roles list should result in 403 for any role requirement."""

        @app.get("/endpoint")
        @require_role("free")
        async def endpoint(request: Request) -> dict[str, str]:
            return {"status": "ok"}

        mock_ctx = mock_auth_context(roles=[])

        with patch(
            "src.lambdas.shared.middleware.require_role.extract_auth_context_typed",
            return_value=mock_ctx,
        ):
            response = client.get("/endpoint")
            assert response.status_code == 403

    def test_case_sensitive_role_matching(
        self, app: FastAPI, client: TestClient
    ) -> None:
        """Role matching should be case-sensitive."""

        @app.get("/endpoint")
        @require_role("operator")
        async def endpoint(request: Request) -> dict[str, str]:
            return {"status": "ok"}

        # Roles with wrong case
        mock_ctx = mock_auth_context(roles=["OPERATOR", "Operator"])

        with patch(
            "src.lambdas.shared.middleware.require_role.extract_auth_context_typed",
            return_value=mock_ctx,
        ):
            response = client.get("/endpoint")
            assert response.status_code == 403  # Case mismatch should fail

    def test_anonymous_role_for_public_with_tracking(
        self, app: FastAPI, client: TestClient
    ) -> None:
        """Anonymous role should work for public content with session tracking."""

        @app.get("/public/content")
        @require_role("anonymous")
        async def public_content(request: Request) -> dict[str, str]:
            return {"content": "public"}

        mock_ctx = mock_auth_context(roles=["anonymous"])

        with patch(
            "src.lambdas.shared.middleware.require_role.extract_auth_context_typed",
            return_value=mock_ctx,
        ):
            response = client.get("/public/content")
            assert response.status_code == 200
