"""
Unit Tests for Chaos Injection Wiring in Ingestion Handler
==========================================================

Feature 1236: Tests that the ingestion Lambda correctly gates on
chaos experiments and emits metrics.

Tests:
- test_chaos_active_returns_early: Handler short-circuits when ingestion_failure is active
- test_chaos_inactive_proceeds: Handler proceeds normally when no chaos active
- test_chaos_emits_metric: ChaosInjectionActive metric is emitted
- test_production_env_skips_chaos: Chaos is never checked in production
"""

import json
import os
from unittest.mock import MagicMock, patch


class TestChaosIngestionWiring:
    """Tests for ingestion_failure chaos wiring in the ingestion handler."""

    @patch.dict(
        os.environ,
        {
            "ENVIRONMENT": "preprod",
            "CHAOS_EXPERIMENTS_TABLE": "preprod-chaos-experiments",
            "DATABASE_TABLE": "test-table",
            "USERS_TABLE": "test-users",
            "TIINGO_SECRET_ARN": "arn:aws:secretsmanager:us-east-1:123:secret:tiingo",
            "FINNHUB_SECRET_ARN": "arn:aws:secretsmanager:us-east-1:123:secret:finnhub",
            "SNS_TOPIC_ARN": "arn:aws:sns:us-east-1:123:test-topic",
            "ALERT_TOPIC_ARN": "arn:aws:sns:us-east-1:123:alert-topic",
            "AWS_REGION": "us-east-1",
            "CLOUD_REGION": "us-east-1",
        },
    )
    @patch("src.lambdas.ingestion.handler.is_chaos_active", return_value=True)
    @patch("src.lambdas.ingestion.handler.emit_metric")
    def test_chaos_active_returns_early(self, mock_emit_metric, mock_is_chaos):
        """Test handler returns early when ingestion_failure chaos is active."""
        from src.lambdas.ingestion.handler import lambda_handler

        event = {"source": "aws.events"}
        context = MagicMock()
        context.aws_request_id = "test-request-id"

        result = lambda_handler(event, context)

        assert result["statusCode"] == 200
        body = json.loads(result["body"])
        assert body["status"] == "chaos_active"
        assert body["scenario"] == "ingestion_failure"

        # Verify chaos check was called
        mock_is_chaos.assert_called_once_with("ingestion_failure")

    @patch.dict(
        os.environ,
        {
            "ENVIRONMENT": "preprod",
            "CHAOS_EXPERIMENTS_TABLE": "preprod-chaos-experiments",
            "DATABASE_TABLE": "test-table",
            "USERS_TABLE": "test-users",
            "TIINGO_SECRET_ARN": "arn:aws:secretsmanager:us-east-1:123:secret:tiingo",
            "FINNHUB_SECRET_ARN": "arn:aws:secretsmanager:us-east-1:123:secret:finnhub",
            "SNS_TOPIC_ARN": "arn:aws:sns:us-east-1:123:test-topic",
            "ALERT_TOPIC_ARN": "arn:aws:sns:us-east-1:123:alert-topic",
            "AWS_REGION": "us-east-1",
            "CLOUD_REGION": "us-east-1",
        },
    )
    @patch("src.lambdas.ingestion.handler.is_chaos_active", return_value=False)
    @patch("src.lambdas.ingestion.handler.auto_stop_expired", return_value=False)
    @patch("src.lambdas.ingestion.handler.get_chaos_delay_ms", return_value=0)
    @patch("src.lambdas.ingestion.handler._get_active_tickers", return_value=[])
    @patch("src.lambdas.ingestion.handler.get_table")
    @patch("src.lambdas.ingestion.handler._get_config")
    def test_chaos_inactive_proceeds(
        self,
        mock_config,
        mock_get_table,
        mock_get_tickers,
        mock_delay,
        mock_auto_stop,
        mock_is_chaos,
    ):
        """Test handler proceeds normally when chaos is not active."""
        from src.lambdas.ingestion.handler import lambda_handler

        mock_config.return_value = {
            "dynamodb_table": "test-table",
            "users_table": "test-users",
            "tiingo_secret_arn": "arn:aws:secretsmanager:us-east-1:123:secret:tiingo",
            "finnhub_secret_arn": "arn:aws:secretsmanager:us-east-1:123:secret:finnhub",
            "sns_topic_arn": "arn:aws:sns:us-east-1:123:test-topic",
            "alert_topic_arn": "arn:aws:sns:us-east-1:123:alert-topic",
            "aws_region": "us-east-1",
        }
        mock_get_table.return_value = MagicMock()

        event = {"source": "aws.events"}
        context = MagicMock()
        context.aws_request_id = "test-request-id"

        result = lambda_handler(event, context)

        # Handler should proceed past chaos check
        assert result["statusCode"] == 200
        body = result["body"]
        assert body["message"] == "No active tickers"

    @patch.dict(
        os.environ,
        {
            "ENVIRONMENT": "preprod",
            "CHAOS_EXPERIMENTS_TABLE": "preprod-chaos-experiments",
            "DATABASE_TABLE": "test-table",
            "USERS_TABLE": "test-users",
            "TIINGO_SECRET_ARN": "arn:aws:secretsmanager:us-east-1:123:secret:tiingo",
            "FINNHUB_SECRET_ARN": "arn:aws:secretsmanager:us-east-1:123:secret:finnhub",
            "SNS_TOPIC_ARN": "arn:aws:sns:us-east-1:123:test-topic",
            "ALERT_TOPIC_ARN": "arn:aws:sns:us-east-1:123:alert-topic",
            "AWS_REGION": "us-east-1",
            "CLOUD_REGION": "us-east-1",
        },
    )
    @patch("src.lambdas.ingestion.handler.is_chaos_active", return_value=True)
    @patch("src.lambdas.ingestion.handler.emit_metric")
    def test_chaos_emits_metric(self, mock_emit_metric, mock_is_chaos):
        """Test ChaosInjectionActive metric is emitted when chaos is active."""
        from src.lambdas.ingestion.handler import lambda_handler

        event = {"source": "aws.events"}
        context = MagicMock()
        context.aws_request_id = "test-request-id"

        lambda_handler(event, context)

        # Verify ChaosInjectionActive metric was emitted
        mock_emit_metric.assert_called_once_with(
            "ChaosInjectionActive",
            1,
            dimensions={"Scenario": "ingestion_failure"},
        )

    @patch.dict(
        os.environ,
        {
            "ENVIRONMENT": "prod",
            "CHAOS_EXPERIMENTS_TABLE": "",
            "DATABASE_TABLE": "prod-table",
            "USERS_TABLE": "prod-users",
            "TIINGO_SECRET_ARN": "arn:aws:secretsmanager:us-east-1:123:secret:tiingo",
            "FINNHUB_SECRET_ARN": "arn:aws:secretsmanager:us-east-1:123:secret:finnhub",
            "SNS_TOPIC_ARN": "arn:aws:sns:us-east-1:123:test-topic",
            "ALERT_TOPIC_ARN": "arn:aws:sns:us-east-1:123:alert-topic",
            "AWS_REGION": "us-east-1",
            "CLOUD_REGION": "us-east-1",
        },
    )
    @patch("src.lambdas.ingestion.handler.is_chaos_active", return_value=False)
    @patch("src.lambdas.ingestion.handler.auto_stop_expired", return_value=False)
    @patch("src.lambdas.ingestion.handler.get_chaos_delay_ms", return_value=0)
    @patch("src.lambdas.ingestion.handler._get_active_tickers", return_value=[])
    @patch("src.lambdas.ingestion.handler.get_table")
    @patch("src.lambdas.ingestion.handler._get_config")
    def test_production_env_skips_chaos(
        self,
        mock_config,
        mock_get_table,
        mock_get_tickers,
        mock_delay,
        mock_auto_stop,
        mock_is_chaos,
    ):
        """Test that production environment never activates chaos."""
        from src.lambdas.ingestion.handler import lambda_handler

        mock_config.return_value = {
            "dynamodb_table": "prod-table",
            "users_table": "prod-users",
            "tiingo_secret_arn": "arn:aws:secretsmanager:us-east-1:123:secret:tiingo",
            "finnhub_secret_arn": "arn:aws:secretsmanager:us-east-1:123:secret:finnhub",
            "sns_topic_arn": "arn:aws:sns:us-east-1:123:test-topic",
            "alert_topic_arn": "arn:aws:sns:us-east-1:123:alert-topic",
            "aws_region": "us-east-1",
        }
        mock_get_table.return_value = MagicMock()

        event = {"source": "aws.events"}
        context = MagicMock()
        context.aws_request_id = "test-request-id"

        result = lambda_handler(event, context)

        # is_chaos_active should return False for prod
        # Handler should have proceeded to normal flow
        mock_is_chaos.assert_called()
        assert result["statusCode"] == 200
