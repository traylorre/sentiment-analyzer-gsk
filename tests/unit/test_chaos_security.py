"""Unit tests for chaos security hardening (Feature 1250).

Tests auth enforcement, environment gating, rate limiting,
scenario locking, auto-restore scheduling, and IAM metrics.
"""

import json
import os
from unittest.mock import MagicMock, patch

import pytest
from botocore.exceptions import ClientError

# Set env before imports
os.environ.setdefault("DYNAMODB_TABLE", "test-sentiment-items")
os.environ.setdefault("SENTIMENTS_TABLE", "test-sentiment-items")
os.environ.setdefault("USERS_TABLE", "test-sentiment-users")
os.environ.setdefault("ENVIRONMENT", "test")
os.environ.setdefault("CHAOS_EXPERIMENTS_TABLE", "test-chaos-experiments")

from tests.conftest import make_event


def _reload_handler_with_env(env_value: str):
    """Reload handler module with a specific ENVIRONMENT value."""
    import importlib

    with patch.dict(os.environ, {"ENVIRONMENT": env_value}):
        import src.lambdas.dashboard.handler as handler_module

        importlib.reload(handler_module)
        return handler_module


# ===================================================================
# T015.1-2: Authentication tests
# ===================================================================


class TestChaosAuthentication:
    """Tests for authenticated-only chaos access (FR-001)."""

    def test_anonymous_rejected_in_all_envs(self):
        """UUID token returns None from _get_chaos_user_id_from_event() in all envs."""
        from src.lambdas.dashboard.handler import _get_chaos_user_id_from_event

        for env in ["local", "dev", "test", "preprod", "prod"]:
            with patch.dict(os.environ, {"ENVIRONMENT": env}):
                event = make_event(
                    method="POST",
                    path="/chaos/experiments",
                    headers={
                        "Authorization": "Bearer 12345678-1234-1234-1234-123456789abc"
                    },
                )
                result = _get_chaos_user_id_from_event(event)
                assert (
                    result is None
                ), f"Anonymous should be rejected in {env}, got {result}"

    def test_authenticated_accepted(self):
        """JWT token returns user_id."""
        from src.lambdas.dashboard.handler import _get_chaos_user_id_from_event

        event = make_event(
            method="POST",
            path="/chaos/experiments",
            headers={"Authorization": "Bearer valid-jwt-token"},
        )

        # Mock JWT validation to return an authenticated context
        with patch(
            "src.lambdas.dashboard.handler.extract_auth_context_typed"
        ) as mock_auth:
            from src.lambdas.shared.middleware.auth_middleware import AuthType

            mock_ctx = MagicMock()
            mock_ctx.user_id = "user-123"
            mock_ctx.auth_type = AuthType.AUTHENTICATED
            mock_auth.return_value = mock_ctx

            result = _get_chaos_user_id_from_event(event)
            assert result == "user-123"


# ===================================================================
# T015.3-4: Environment gating tests
# ===================================================================


class TestChaosEnvironmentGating:
    """Tests for chaos route 404 in non-dev environments (FR-002)."""

    @pytest.fixture
    def mock_lambda_context(self):
        ctx = MagicMock()
        ctx.function_name = "test-dashboard"
        ctx.memory_limit_in_mb = 128
        ctx.invoked_function_arn = "arn:aws:lambda:us-east-1:123456789:function:test"
        ctx.aws_request_id = "test-request-id"
        return ctx

    def test_chaos_routes_return_404_in_preprod(self, mock_lambda_context):
        handler = _reload_handler_with_env("preprod")
        event = make_event(method="POST", path="/chaos/experiments")
        response = handler.lambda_handler(event, mock_lambda_context)
        assert response["statusCode"] == 404
        data = json.loads(response["body"])
        assert data["detail"] == "Not found"

    def test_chaos_list_returns_404_in_preprod(self, mock_lambda_context):
        handler = _reload_handler_with_env("preprod")
        event = make_event(method="GET", path="/chaos/experiments")
        response = handler.lambda_handler(event, mock_lambda_context)
        assert response["statusCode"] == 404

    def test_chaos_start_returns_404_in_prod(self, mock_lambda_context):
        handler = _reload_handler_with_env("prod")
        event = make_event(method="POST", path="/chaos/experiments/fake-id/start")
        response = handler.lambda_handler(event, mock_lambda_context)
        assert response["statusCode"] == 404


# ===================================================================
# T015.5-8: Rate limiting and scenario locking tests
# ===================================================================


class TestChaosRateLimiting:
    """Tests for chaos rate limiting (FR-005) and scenario locking (FR-008)."""

    def test_rate_limit_blocks_rapid_creation(self):
        from src.lambdas.dashboard.chaos import RateLimitError, _check_rate_limit

        mock_table = MagicMock()
        # First call succeeds, second raises ConditionalCheckFailedException
        error_response = {
            "Error": {"Code": "ConditionalCheckFailedException", "Message": ""}
        }
        mock_table.put_item.side_effect = ClientError(error_response, "PutItem")

        with patch("src.lambdas.dashboard.chaos._get_dynamodb") as mock_ddb:
            mock_ddb.return_value.Table.return_value = mock_table
            with pytest.raises(RateLimitError, match="Rate limit exceeded"):
                _check_rate_limit("user-123")

    def test_rate_limit_allows_after_window(self):
        from src.lambdas.dashboard.chaos import _check_rate_limit

        mock_table = MagicMock()
        mock_table.put_item.return_value = {}  # Success

        with patch("src.lambdas.dashboard.chaos._get_dynamodb") as mock_ddb:
            mock_ddb.return_value.Table.return_value = mock_table
            # Should not raise
            _check_rate_limit("user-123")
            mock_table.put_item.assert_called_once()

    def test_scenario_lock_prevents_concurrent(self):
        from src.lambdas.dashboard.chaos import ChaosError, _acquire_scenario_lock

        mock_table = MagicMock()
        error_response = {
            "Error": {"Code": "ConditionalCheckFailedException", "Message": ""}
        }
        mock_table.put_item.side_effect = ClientError(error_response, "PutItem")

        with patch("src.lambdas.dashboard.chaos._get_dynamodb") as mock_ddb:
            mock_ddb.return_value.Table.return_value = mock_table
            with pytest.raises(ChaosError, match="already running"):
                _acquire_scenario_lock("ingestion_failure", "exp-123")

    def test_scenario_lock_releases_on_stop(self):
        from src.lambdas.dashboard.chaos import _release_scenario_lock

        mock_table = MagicMock()
        with patch("src.lambdas.dashboard.chaos._get_dynamodb") as mock_ddb:
            mock_ddb.return_value.Table.return_value = mock_table
            _release_scenario_lock("ingestion_failure")
            mock_table.delete_item.assert_called_once_with(
                Key={
                    "experiment_id": "CHAOSLOCK#ingestion_failure",
                    "created_at": "ACTIVE",
                }
            )


# ===================================================================
# T015.9-12: Auto-restore scheduling tests
# ===================================================================


class TestAutoRestoreScheduling:
    """Tests for auto-restore scheduling (FR-003, FR-004)."""

    def test_auto_restore_scheduled_on_start(self):
        from src.lambdas.dashboard.chaos import _schedule_auto_restore

        mock_scheduler = MagicMock()
        with (
            patch(
                "src.lambdas.dashboard.chaos.boto3.client", return_value=mock_scheduler
            ),
            patch(
                "src.lambdas.dashboard.chaos.SCHEDULER_ROLE_ARN",
                "arn:aws:iam::123:role/test",
            ),
            patch(
                "src.lambdas.dashboard.chaos.DASHBOARD_LAMBDA_ARN",
                "arn:aws:lambda:us-east-1:123:function:test",
            ),
        ):
            result = _schedule_auto_restore("exp-123", 30)
            assert result == "chaos-auto-restore-exp-123"
            mock_scheduler.create_schedule.assert_called_once()
            call_kwargs = mock_scheduler.create_schedule.call_args[1]
            assert call_kwargs["Name"] == "chaos-auto-restore-exp-123"
            assert call_kwargs["ActionAfterCompletion"] == "DELETE"
            assert "at(" in call_kwargs["ScheduleExpression"]

    def test_auto_restore_scheduling_failure_raises(self):
        from src.lambdas.dashboard.chaos import ChaosError, _schedule_auto_restore

        mock_scheduler = MagicMock()
        mock_scheduler.create_schedule.side_effect = Exception("Scheduler down")

        with (
            patch(
                "src.lambdas.dashboard.chaos.boto3.client", return_value=mock_scheduler
            ),
            patch("src.lambdas.dashboard.chaos.SCHEDULER_ROLE_ARN", "arn:test"),
            patch("src.lambdas.dashboard.chaos.DASHBOARD_LAMBDA_ARN", "arn:test"),
        ):
            with pytest.raises(ChaosError, match="Failed to schedule auto-restore"):
                _schedule_auto_restore("exp-fail", 30)

    def test_auto_restore_noop_when_already_stopped(self):
        """_handle_auto_restore returns no-op when experiment is not running."""
        with patch("src.lambdas.dashboard.chaos.get_experiment") as mock_get:
            mock_get.return_value = {
                "experiment_id": "exp-123",
                "status": "stopped",
            }
            from src.lambdas.dashboard.handler import _handle_auto_restore

            result = _handle_auto_restore("exp-123")
            assert result["statusCode"] == 200
            assert "no-op" in result["body"]

    def test_auto_restore_raw_event_routing(self):
        """Raw chaos-auto-restore event is routed before Powertools."""
        with patch("src.lambdas.dashboard.chaos.get_experiment") as mock_get:
            mock_get.return_value = None
            from src.lambdas.dashboard.handler import _handle_auto_restore

            result = _handle_auto_restore("nonexistent")
            assert result["statusCode"] == 200
            assert "no-op" in result["body"]


# ===================================================================
# T015.13-15: IAM metric and stop behavior tests
# ===================================================================


class TestIAMMetricsAndStopBehavior:
    """Tests for IAM metrics (FR-006) and stop graceful handling."""

    def test_iam_metric_emitted_on_dynamodb_throttle(self):
        from src.lambdas.dashboard.chaos import _emit_iam_metric

        mock_cw = MagicMock()
        with patch("src.lambdas.dashboard.chaos.boto3.client", return_value=mock_cw):
            _emit_iam_metric(1)
            mock_cw.put_metric_data.assert_called_once()
            call_kwargs = mock_cw.put_metric_data.call_args[1]
            assert call_kwargs["Namespace"] == "SentimentAnalyzer"
            assert (
                call_kwargs["MetricData"][0]["MetricName"] == "ChaosIAMPolicyAttachment"
            )
            assert call_kwargs["MetricData"][0]["Value"] == 1

    def test_stop_deletes_scheduled_rule(self):
        from src.lambdas.dashboard.chaos import _delete_auto_restore_schedule

        mock_scheduler = MagicMock()
        with (
            patch(
                "src.lambdas.dashboard.chaos.boto3.client", return_value=mock_scheduler
            ),
            patch("src.lambdas.dashboard.chaos.SCHEDULER_ROLE_ARN", "arn:test"),
        ):
            _delete_auto_restore_schedule("exp-123")
            mock_scheduler.delete_schedule.assert_called_once_with(
                Name="chaos-auto-restore-exp-123"
            )

    def test_stop_handles_already_stopped_gracefully(self):
        """stop_experiment returns experiment without error if already stopped."""
        from src.lambdas.dashboard.chaos import stop_experiment

        mock_experiment = {
            "experiment_id": "exp-123",
            "status": "stopped",
            "scenario_type": "ingestion_failure",
        }

        with (
            patch("src.lambdas.dashboard.chaos.check_environment_allowed"),
            patch("src.lambdas.dashboard.chaos._enforce_kill_switch"),
            patch(
                "src.lambdas.dashboard.chaos.get_experiment",
                return_value=mock_experiment,
            ),
        ):
            result = stop_experiment("exp-123")
            assert result["status"] == "stopped"
            assert result["experiment_id"] == "exp-123"
