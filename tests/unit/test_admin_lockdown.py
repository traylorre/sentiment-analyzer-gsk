"""Unit tests for admin dashboard lockdown (Feature 1249).

Tests environment gating, information stripping, auth on refresh/status,
and session validation enforcement.
"""

import json
import os
from unittest.mock import MagicMock, patch

import boto3
import pytest
from moto import mock_aws

# Set env before handler import
os.environ.setdefault("DYNAMODB_TABLE", "test-sentiment-items")
os.environ.setdefault("SENTIMENTS_TABLE", "test-sentiment-items")
os.environ.setdefault("USERS_TABLE", "test-sentiment-users")
os.environ.setdefault("ENVIRONMENT", "test")
os.environ.setdefault("SSE_LAMBDA_URL", "https://sse.example.com")

from tests.conftest import make_event


def _reload_handler_with_env(env_value: str):
    """Reload handler module with a specific ENVIRONMENT value."""
    import importlib

    with patch.dict(os.environ, {"ENVIRONMENT": env_value}):
        import src.lambdas.dashboard.handler as handler_module

        importlib.reload(handler_module)
        return handler_module


def _create_tables():
    """Create test DynamoDB tables for moto."""
    dynamodb = boto3.resource("dynamodb", region_name="us-east-1")
    dynamodb.create_table(
        TableName="test-sentiment-items",
        KeySchema=[
            {"AttributeName": "PK", "KeyType": "HASH"},
            {"AttributeName": "SK", "KeyType": "RANGE"},
        ],
        AttributeDefinitions=[
            {"AttributeName": "PK", "AttributeType": "S"},
            {"AttributeName": "SK", "AttributeType": "S"},
        ],
        BillingMode="PAY_PER_REQUEST",
    )
    dynamodb.create_table(
        TableName="test-sentiment-users",
        KeySchema=[
            {"AttributeName": "PK", "KeyType": "HASH"},
            {"AttributeName": "SK", "KeyType": "RANGE"},
        ],
        AttributeDefinitions=[
            {"AttributeName": "PK", "AttributeType": "S"},
            {"AttributeName": "SK", "AttributeType": "S"},
        ],
        BillingMode="PAY_PER_REQUEST",
    )


# ===================================================================
# T008.1-8: _is_dev_environment() tests
# ===================================================================


class TestIsDevEnvironment:
    """Tests for the _is_dev_environment() helper.

    Patches the module-level ENVIRONMENT constant (not os.environ) since
    _is_dev_environment() reads the constant set at import time.
    """

    _MOD = "src.lambdas.dashboard.handler.ENVIRONMENT"

    def test_local(self):
        from src.lambdas.dashboard.handler import _is_dev_environment

        with patch(self._MOD, "local"):
            assert _is_dev_environment() is True

    def test_dev(self):
        from src.lambdas.dashboard.handler import _is_dev_environment

        with patch(self._MOD, "dev"):
            assert _is_dev_environment() is True

    def test_test(self):
        from src.lambdas.dashboard.handler import _is_dev_environment

        with patch(self._MOD, "test"):
            assert _is_dev_environment() is True

    def test_preprod(self):
        from src.lambdas.dashboard.handler import _is_dev_environment

        with patch(self._MOD, "preprod"):
            assert _is_dev_environment() is False

    def test_prod(self):
        from src.lambdas.dashboard.handler import _is_dev_environment

        with patch(self._MOD, "prod"):
            assert _is_dev_environment() is False

    def test_unset(self):
        from src.lambdas.dashboard.handler import _is_dev_environment

        with patch(self._MOD, ""):
            assert _is_dev_environment() is False

    def test_unknown(self):
        from src.lambdas.dashboard.handler import _is_dev_environment

        with patch(self._MOD, "staging"):
            assert _is_dev_environment() is False

    def test_case_insensitive(self):
        from src.lambdas.dashboard.handler import _is_dev_environment

        with patch(self._MOD, "DEV"):
            assert _is_dev_environment() is True

        with patch(self._MOD, "Local"):
            assert _is_dev_environment() is True


# ===================================================================
# T008.9-14: Route gating and info stripping tests
# ===================================================================


class TestAdminRouteGating:
    """Tests for admin route lockdown in non-dev environments."""

    @pytest.fixture
    def mock_lambda_context(self):
        ctx = MagicMock()
        ctx.function_name = "test-dashboard"
        ctx.memory_limit_in_mb = 128
        ctx.invoked_function_arn = "arn:aws:lambda:us-east-1:123456789:function:test"
        ctx.aws_request_id = "test-request-id"
        return ctx

    @mock_aws
    def test_root_returns_404_in_preprod(self, mock_lambda_context):
        _create_tables()
        handler = _reload_handler_with_env("preprod")
        event = make_event(method="GET", path="/")
        response = handler.lambda_handler(event, mock_lambda_context)
        assert response["statusCode"] == 404
        data = json.loads(response["body"])
        assert data["detail"] == "Not found"

    @mock_aws
    def test_chaos_returns_404_in_preprod(self, mock_lambda_context):
        _create_tables()
        handler = _reload_handler_with_env("preprod")
        event = make_event(method="GET", path="/chaos")
        response = handler.lambda_handler(event, mock_lambda_context)
        assert response["statusCode"] == 404

    @mock_aws
    def test_health_stripped_in_preprod(self, mock_lambda_context):
        _create_tables()
        handler = _reload_handler_with_env("preprod")
        event = make_event(method="GET", path="/health")
        response = handler.lambda_handler(event, mock_lambda_context)
        assert response["statusCode"] == 200
        data = json.loads(response["body"])
        assert data["status"] == "healthy"
        assert "table" not in data
        assert "environment" not in data

    @mock_aws
    def test_health_full_in_dev(self, mock_lambda_context):
        _create_tables()
        handler = _reload_handler_with_env("dev")
        event = make_event(method="GET", path="/health")
        response = handler.lambda_handler(event, mock_lambda_context)
        assert response["statusCode"] == 200
        data = json.loads(response["body"])
        assert data["status"] == "healthy"
        assert "table" in data
        assert "environment" in data

    @mock_aws
    def test_runtime_stripped_in_preprod(self, mock_lambda_context):
        _create_tables()
        handler = _reload_handler_with_env("preprod")
        event = make_event(method="GET", path="/api/v2/runtime")
        response = handler.lambda_handler(event, mock_lambda_context)
        assert response["statusCode"] == 200
        data = json.loads(response["body"])
        assert data["sse_url"] is None
        assert data["environment"] == "production"

    @mock_aws
    def test_runtime_full_in_dev(self, mock_lambda_context):
        _create_tables()
        handler = _reload_handler_with_env("dev")
        event = make_event(method="GET", path="/api/v2/runtime")
        response = handler.lambda_handler(event, mock_lambda_context)
        assert response["statusCode"] == 200
        data = json.loads(response["body"])
        assert data["sse_url"] is not None
        assert data["environment"] == "dev"


# ===================================================================
# T008.15-16: Refresh status auth tests
# ===================================================================


class TestRefreshStatusAuth:
    """Tests for auth on /configurations/{id}/refresh/status."""

    @pytest.fixture
    def mock_lambda_context(self):
        ctx = MagicMock()
        ctx.function_name = "test-dashboard"
        ctx.memory_limit_in_mb = 128
        ctx.invoked_function_arn = "arn:aws:lambda:us-east-1:123456789:function:test"
        ctx.aws_request_id = "test-request-id"
        return ctx

    @mock_aws
    def test_refresh_status_requires_auth(self, mock_lambda_context):
        _create_tables()
        from src.lambdas.dashboard.handler import lambda_handler

        event = make_event(
            method="GET",
            path="/api/v2/configurations/fake-id/refresh/status",
        )
        response = lambda_handler(event, mock_lambda_context)
        assert response["statusCode"] == 401

    @mock_aws
    def test_refresh_status_ownership_check(self, mock_lambda_context):
        """User A's token should not access user B's config."""
        _create_tables()
        from src.lambdas.dashboard.handler import lambda_handler

        # Use a valid UUID token (anonymous session) but config doesn't belong to this user
        event = make_event(
            method="GET",
            path="/api/v2/configurations/other-user-config/refresh/status",
            headers={"Authorization": "Bearer 12345678-1234-1234-1234-123456789abc"},
        )

        # Mock session validation to pass, but config lookup to fail (not found for this user)
        with patch(
            "src.lambdas.dashboard.router_v2.auth_service.validate_session"
        ) as mock_validate:
            mock_result = MagicMock()
            mock_result.valid = True
            mock_validate.return_value = mock_result

            response = lambda_handler(event, mock_lambda_context)
            # Config not found for this user → 404
            assert response["statusCode"] == 404


# ===================================================================
# T008.17-19: Session validation tests
# ===================================================================


class TestSessionValidation:
    """Tests for session validation in _get_user_id_from_event()."""

    def test_session_validation_rejects_expired(self):
        from src.lambdas.dashboard.handler import _get_user_id_from_event

        event = make_event(
            method="GET",
            path="/api/v2/metrics",
            headers={"Authorization": "Bearer 12345678-1234-1234-1234-123456789abc"},
        )

        with patch("src.lambdas.dashboard.auth.validate_session") as mock_validate:
            mock_result = MagicMock()
            mock_result.valid = False
            mock_validate.return_value = mock_result

            with patch("src.lambdas.dashboard.handler.get_table"):
                result = _get_user_id_from_event(event, validate_session=True)
                assert result == ""

    def test_session_validation_allows_valid(self):
        from src.lambdas.dashboard.handler import _get_user_id_from_event

        event = make_event(
            method="GET",
            path="/api/v2/metrics",
            headers={"Authorization": "Bearer 12345678-1234-1234-1234-123456789abc"},
        )

        with patch("src.lambdas.dashboard.auth.validate_session") as mock_validate:
            mock_result = MagicMock()
            mock_result.valid = True
            mock_validate.return_value = mock_result

            with patch("src.lambdas.dashboard.handler.get_table"):
                result = _get_user_id_from_event(event, validate_session=True)
                assert result == "12345678-1234-1234-1234-123456789abc"

    def test_session_validation_graceful_on_error(self):
        from src.lambdas.dashboard.handler import _get_user_id_from_event

        event = make_event(
            method="GET",
            path="/api/v2/metrics",
            headers={"Authorization": "Bearer 12345678-1234-1234-1234-123456789abc"},
        )

        with patch(
            "src.lambdas.dashboard.auth.validate_session",
            side_effect=Exception("DynamoDB timeout"),
        ):
            with patch("src.lambdas.dashboard.handler.get_table"):
                result = _get_user_id_from_event(event, validate_session=True)
                # Degrades to "" rather than raising 500
                assert result == ""
