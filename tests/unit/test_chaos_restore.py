"""
Unit Tests for Chaos Auto-Restore Lambda (Feature 1237)
=======================================================

Tests the auto-restore Lambda that is triggered by SNS when
the critical composite CloudWatch alarm fires.
"""

import json
from unittest.mock import MagicMock, patch

import pytest


@pytest.fixture(autouse=True)
def mock_env(monkeypatch):
    """Set environment variables for all tests."""
    monkeypatch.setenv("ENVIRONMENT", "preprod")
    monkeypatch.setenv("AWS_REGION", "us-east-1")


@pytest.fixture
def mock_ssm():
    with patch("src.lambdas.chaos_restore.handler._get_ssm") as mock:
        client = MagicMock()
        mock.return_value = client
        yield client


@pytest.fixture
def mock_lambda():
    with patch("src.lambdas.chaos_restore.handler._get_lambda") as mock:
        client = MagicMock()
        mock.return_value = client
        yield client


@pytest.fixture
def mock_iam():
    with patch("src.lambdas.chaos_restore.handler._get_iam") as mock:
        client = MagicMock()
        mock.return_value = client
        yield client


@pytest.fixture
def mock_events():
    with patch("src.lambdas.chaos_restore.handler._get_events") as mock:
        client = MagicMock()
        mock.return_value = client
        yield client


@pytest.fixture
def mock_cloudwatch():
    with patch("src.lambdas.chaos_restore.handler._get_cloudwatch") as mock:
        client = MagicMock()
        mock.return_value = client
        yield client


@pytest.fixture
def sns_alarm_event():
    """Sample SNS alarm event."""
    return {
        "Records": [
            {
                "Sns": {
                    "Message": json.dumps(
                        {
                            "AlarmName": "preprod-critical-composite",
                            "NewStateValue": "ALARM",
                        }
                    )
                }
            }
        ]
    }


class TestAutoRestoreLambda:
    """Tests for the auto-restore Lambda handler."""

    def test_restore_ingestion_failure(
        self, mock_ssm, mock_lambda, mock_cloudwatch, sns_alarm_event
    ):
        """Test restoring ingestion failure (concurrency)."""
        from src.lambdas.chaos_restore.handler import lambda_handler

        snapshot = {
            "FunctionName": "preprod-sentiment-ingestion",
            "MemorySize": 512,
            "Timeout": 60,
            "ReservedConcurrency": "1",
        }

        mock_ssm.get_parameters_by_path.return_value = {
            "Parameters": [
                {
                    "Name": "/chaos/preprod/snapshot/ingestion-failure",
                    "Value": json.dumps(snapshot),
                }
            ]
        }

        result = lambda_handler(sns_alarm_event, MagicMock())

        assert result["statusCode"] == 200
        assert result["body"]["restored"] == 1

        # Verify concurrency restored
        mock_lambda.put_function_concurrency.assert_called_once_with(
            FunctionName="preprod-sentiment-ingestion",
            ReservedConcurrentExecutions=1,
        )

        # Verify snapshot deleted
        mock_ssm.delete_parameter.assert_called_with(
            Name="/chaos/preprod/snapshot/ingestion-failure"
        )

    def test_restore_cold_start(
        self, mock_ssm, mock_lambda, mock_cloudwatch, sns_alarm_event
    ):
        """Test restoring cold start (memory)."""
        from src.lambdas.chaos_restore.handler import lambda_handler

        snapshot = {
            "FunctionName": "preprod-sentiment-analysis",
            "MemorySize": 2048,
            "Timeout": 120,
            "ReservedConcurrency": "NONE",
        }

        mock_ssm.get_parameters_by_path.return_value = {
            "Parameters": [
                {
                    "Name": "/chaos/preprod/snapshot/cold-start",
                    "Value": json.dumps(snapshot),
                }
            ]
        }

        result = lambda_handler(sns_alarm_event, MagicMock())

        assert result["body"]["restored"] == 1
        mock_lambda.update_function_configuration.assert_called_once_with(
            FunctionName="preprod-sentiment-analysis",
            MemorySize=2048,
        )

    def test_restore_trigger_failure(
        self, mock_ssm, mock_events, mock_cloudwatch, sns_alarm_event
    ):
        """Test restoring trigger failure (EventBridge rule)."""
        from src.lambdas.chaos_restore.handler import lambda_handler

        snapshot = {
            "FunctionName": "preprod-sentiment-ingestion",
            "MemorySize": 512,
            "Timeout": 60,
            "ReservedConcurrency": "NONE",
        }

        mock_ssm.get_parameters_by_path.return_value = {
            "Parameters": [
                {
                    "Name": "/chaos/preprod/snapshot/trigger-failure",
                    "Value": json.dumps(snapshot),
                }
            ]
        }

        result = lambda_handler(sns_alarm_event, MagicMock())

        assert result["body"]["restored"] == 1
        mock_events.enable_rule.assert_called_once_with(
            Name="preprod-sentiment-ingestion-schedule"
        )

    def test_restore_dynamodb_throttle(
        self, mock_ssm, mock_iam, mock_cloudwatch, sns_alarm_event
    ):
        """Test restoring DynamoDB throttle (IAM policy detach)."""
        from src.lambdas.chaos_restore.handler import lambda_handler

        snapshot = {
            "FunctionName": "preprod-sentiment-ingestion",
            "MemorySize": 512,
            "Timeout": 60,
            "ReservedConcurrency": "NONE",
        }

        mock_ssm.get_parameters_by_path.return_value = {
            "Parameters": [
                {
                    "Name": "/chaos/preprod/snapshot/dynamodb-throttle",
                    "Value": json.dumps(snapshot),
                }
            ]
        }

        with patch("src.lambdas.chaos_restore.handler.boto3") as mock_boto3:
            mock_sts = MagicMock()
            mock_sts.get_caller_identity.return_value = {"Account": "123456789012"}
            mock_boto3.client.return_value = mock_sts

            result = lambda_handler(sns_alarm_event, MagicMock())

        assert result["body"]["restored"] == 1
        assert mock_iam.detach_role_policy.call_count == 2

    def test_no_active_snapshots(self, mock_ssm, mock_cloudwatch, sns_alarm_event):
        """Test handler does nothing when no active snapshots exist."""
        from src.lambdas.chaos_restore.handler import lambda_handler

        mock_ssm.get_parameters_by_path.return_value = {"Parameters": []}

        result = lambda_handler(sns_alarm_event, MagicMock())

        assert result["statusCode"] == 200
        assert result["body"]["restored"] == 0
        assert result["body"]["message"] == "No active chaos"

    def test_partial_failure_leaves_kill_switch_triggered(
        self, mock_ssm, mock_lambda, mock_cloudwatch, sns_alarm_event
    ):
        """Test partial restore failure leaves kill switch as 'triggered'."""
        from src.lambdas.chaos_restore.handler import lambda_handler

        snapshot = {
            "FunctionName": "preprod-sentiment-ingestion",
            "MemorySize": 512,
            "Timeout": 60,
            "ReservedConcurrency": "1",
        }

        mock_ssm.get_parameters_by_path.return_value = {
            "Parameters": [
                {
                    "Name": "/chaos/preprod/snapshot/ingestion-failure",
                    "Value": json.dumps(snapshot),
                }
            ]
        }

        # Make the restore fail
        mock_lambda.put_function_concurrency.side_effect = Exception(
            "Service unavailable"
        )

        result = lambda_handler(sns_alarm_event, MagicMock())

        assert result["body"]["errors"] == 1

        # Kill switch should remain "triggered" (not set to "disarmed")
        # Check that the last put_parameter call was "triggered" not "disarmed"
        kill_switch_calls = [
            c for c in mock_ssm.put_parameter.call_args_list if "kill-switch" in str(c)
        ]
        # Should only have the initial "triggered" set, no "disarmed"
        assert all(c[1]["Value"] == "triggered" for c in kill_switch_calls)

    def test_concurrency_none_deletes_setting(
        self, mock_ssm, mock_lambda, mock_cloudwatch, sns_alarm_event
    ):
        """Test restoring concurrency=NONE deletes the concurrency setting."""
        from src.lambdas.chaos_restore.handler import lambda_handler

        snapshot = {
            "FunctionName": "preprod-sentiment-ingestion",
            "MemorySize": 512,
            "Timeout": 60,
            "ReservedConcurrency": "NONE",
        }

        mock_ssm.get_parameters_by_path.return_value = {
            "Parameters": [
                {
                    "Name": "/chaos/preprod/snapshot/ingestion-failure",
                    "Value": json.dumps(snapshot),
                }
            ]
        }

        lambda_handler(sns_alarm_event, MagicMock())

        mock_lambda.delete_function_concurrency.assert_called_once_with(
            FunctionName="preprod-sentiment-ingestion"
        )

    def test_emits_cloudwatch_metric(
        self, mock_ssm, mock_lambda, mock_cloudwatch, sns_alarm_event
    ):
        """Test handler emits ChaosAutoRestore metric."""
        from src.lambdas.chaos_restore.handler import lambda_handler

        snapshot = {
            "FunctionName": "preprod-sentiment-ingestion",
            "MemorySize": 512,
            "Timeout": 60,
            "ReservedConcurrency": "NONE",
        }

        mock_ssm.get_parameters_by_path.return_value = {
            "Parameters": [
                {
                    "Name": "/chaos/preprod/snapshot/ingestion-failure",
                    "Value": json.dumps(snapshot),
                }
            ]
        }

        lambda_handler(sns_alarm_event, MagicMock())

        mock_cloudwatch.put_metric_data.assert_called_once()
        metric_call = mock_cloudwatch.put_metric_data.call_args
        assert metric_call[1]["Namespace"] == "SentimentAnalyzer"
        assert metric_call[1]["MetricData"][0]["MetricName"] == "ChaosAutoRestore"
