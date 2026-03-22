"""
Unit Tests for Chaos Auto-Stop Expired Experiments
===================================================

Feature 1236: Tests that expired chaos experiments are automatically
stopped to prevent runaway chaos.

Tests:
- auto_stop_expired returns True when experiment exceeded duration
- auto_stop_expired returns False when experiment still within duration
- auto_stop_expired returns False in production environment
- auto_stop_expired returns False when no chaos table configured
- auto_stop_expired handles DynamoDB errors gracefully
"""

import os
from datetime import UTC, datetime, timedelta
from unittest.mock import MagicMock, patch

import pytest
from botocore.exceptions import ClientError

import src.lambdas.shared.chaos_injection as chaos_injection_module
from src.lambdas.shared.chaos_injection import auto_stop_expired


class TestAutoStopExpired:
    """Tests for auto_stop_expired() function."""

    @pytest.fixture(autouse=True)
    def reset_dynamodb_client(self, monkeypatch):
        """Reset the global DynamoDB client before and after each test."""
        monkeypatch.setattr(chaos_injection_module, "_dynamodb_client", None)
        yield
        chaos_injection_module._dynamodb_client = None

    @patch.dict(
        os.environ,
        {
            "ENVIRONMENT": "preprod",
            "CHAOS_EXPERIMENTS_TABLE": "preprod-chaos-experiments",
        },
    )
    @patch("src.lambdas.shared.chaos_injection.boto3.resource")
    def test_auto_stops_expired_experiment(self, mock_boto3_resource):
        """Test auto-stops experiment that has exceeded its duration."""
        # Experiment started 10 minutes ago with 60 second duration
        started_at = (datetime.now(UTC) - timedelta(minutes=10)).isoformat() + "Z"

        mock_table = MagicMock()
        mock_table.query.return_value = {
            "Items": [
                {
                    "experiment_id": "exp-123",
                    "scenario_type": "ingestion_failure",
                    "status": "running",
                    "duration_seconds": 60,
                    "results": {
                        "started_at": started_at,
                        "injection_method": "dynamodb_flag",
                    },
                }
            ]
        }
        mock_dynamodb = MagicMock()
        mock_dynamodb.Table.return_value = mock_table
        mock_boto3_resource.return_value = mock_dynamodb

        result = auto_stop_expired("ingestion_failure")

        assert result is True
        mock_table.update_item.assert_called_once()
        update_call = mock_table.update_item.call_args[1]
        assert update_call["Key"]["experiment_id"] == "exp-123"
        assert update_call["ExpressionAttributeValues"][":completed"] == "completed"

    @patch.dict(
        os.environ,
        {
            "ENVIRONMENT": "preprod",
            "CHAOS_EXPERIMENTS_TABLE": "preprod-chaos-experiments",
        },
    )
    @patch("src.lambdas.shared.chaos_injection.boto3.resource")
    def test_does_not_stop_active_experiment(self, mock_boto3_resource):
        """Test does not stop experiment still within its duration."""
        # Experiment started 10 seconds ago with 300 second duration
        started_at = (datetime.now(UTC) - timedelta(seconds=10)).isoformat() + "Z"

        mock_table = MagicMock()
        mock_table.query.return_value = {
            "Items": [
                {
                    "experiment_id": "exp-456",
                    "scenario_type": "ingestion_failure",
                    "status": "running",
                    "duration_seconds": 300,
                    "results": {
                        "started_at": started_at,
                        "injection_method": "dynamodb_flag",
                    },
                }
            ]
        }
        mock_dynamodb = MagicMock()
        mock_dynamodb.Table.return_value = mock_table
        mock_boto3_resource.return_value = mock_dynamodb

        result = auto_stop_expired("ingestion_failure")

        assert result is False
        mock_table.update_item.assert_not_called()

    @patch.dict(
        os.environ,
        {
            "ENVIRONMENT": "preprod",
            "CHAOS_EXPERIMENTS_TABLE": "preprod-chaos-experiments",
        },
    )
    @patch("src.lambdas.shared.chaos_injection.boto3.resource")
    def test_returns_false_when_no_experiments(self, mock_boto3_resource):
        """Test returns False when no running experiments found."""
        mock_table = MagicMock()
        mock_table.query.return_value = {"Items": []}
        mock_dynamodb = MagicMock()
        mock_dynamodb.Table.return_value = mock_table
        mock_boto3_resource.return_value = mock_dynamodb

        result = auto_stop_expired("ingestion_failure")

        assert result is False

    @patch.dict(
        os.environ,
        {
            "ENVIRONMENT": "production",
            "CHAOS_EXPERIMENTS_TABLE": "prod-chaos-experiments",
        },
    )
    def test_production_environment_returns_false(self):
        """Test returns False in production (safety check)."""
        result = auto_stop_expired("ingestion_failure")

        assert result is False

    @patch.dict(
        os.environ,
        {"ENVIRONMENT": "preprod", "CHAOS_EXPERIMENTS_TABLE": ""},
    )
    def test_no_chaos_table_returns_false(self):
        """Test returns False when chaos table not configured."""
        result = auto_stop_expired("ingestion_failure")

        assert result is False

    @patch.dict(
        os.environ,
        {
            "ENVIRONMENT": "preprod",
            "CHAOS_EXPERIMENTS_TABLE": "preprod-chaos-experiments",
        },
    )
    @patch("src.lambdas.shared.chaos_injection.boto3.resource")
    def test_dynamodb_error_returns_false(self, mock_boto3_resource):
        """Test returns False on DynamoDB errors (fail-safe)."""
        mock_table = MagicMock()
        mock_table.query.side_effect = ClientError(
            {
                "Error": {
                    "Code": "ResourceNotFoundException",
                    "Message": "Table not found",
                }
            },
            "Query",
        )
        mock_dynamodb = MagicMock()
        mock_dynamodb.Table.return_value = mock_table
        mock_boto3_resource.return_value = mock_dynamodb

        result = auto_stop_expired("ingestion_failure")

        assert result is False

    @patch.dict(
        os.environ,
        {
            "ENVIRONMENT": "preprod",
            "CHAOS_EXPERIMENTS_TABLE": "preprod-chaos-experiments",
        },
    )
    @patch("src.lambdas.shared.chaos_injection.boto3.resource")
    def test_unexpected_error_returns_false(self, mock_boto3_resource):
        """Test returns False on unexpected errors (fail-safe)."""
        mock_boto3_resource.side_effect = Exception("Unexpected error")

        result = auto_stop_expired("ingestion_failure")

        assert result is False

    @patch.dict(
        os.environ,
        {
            "ENVIRONMENT": "preprod",
            "CHAOS_EXPERIMENTS_TABLE": "preprod-chaos-experiments",
        },
    )
    @patch("src.lambdas.shared.chaos_injection.boto3.resource")
    def test_experiment_without_started_at_skipped(self, mock_boto3_resource):
        """Test experiments without started_at are skipped."""
        mock_table = MagicMock()
        mock_table.query.return_value = {
            "Items": [
                {
                    "experiment_id": "exp-789",
                    "scenario_type": "ingestion_failure",
                    "status": "running",
                    "duration_seconds": 60,
                    "results": {},  # No started_at
                }
            ]
        }
        mock_dynamodb = MagicMock()
        mock_dynamodb.Table.return_value = mock_table
        mock_boto3_resource.return_value = mock_dynamodb

        result = auto_stop_expired("ingestion_failure")

        assert result is False
        mock_table.update_item.assert_not_called()

    @patch.dict(
        os.environ,
        {
            "ENVIRONMENT": "dev",
            "CHAOS_EXPERIMENTS_TABLE": "dev-chaos-experiments",
        },
    )
    @patch("src.lambdas.shared.chaos_injection.boto3.resource")
    def test_dev_environment_allowed(self, mock_boto3_resource):
        """Test auto-stop works in dev environment."""
        started_at = (datetime.now(UTC) - timedelta(minutes=10)).isoformat() + "Z"

        mock_table = MagicMock()
        mock_table.query.return_value = {
            "Items": [
                {
                    "experiment_id": "exp-dev-1",
                    "scenario_type": "lambda_cold_start",
                    "status": "running",
                    "duration_seconds": 60,
                    "results": {"started_at": started_at, "delay_ms": 3000},
                }
            ]
        }
        mock_dynamodb = MagicMock()
        mock_dynamodb.Table.return_value = mock_table
        mock_boto3_resource.return_value = mock_dynamodb

        result = auto_stop_expired("lambda_cold_start")

        assert result is True

    @patch.dict(
        os.environ,
        {
            "ENVIRONMENT": "preprod",
            "CHAOS_EXPERIMENTS_TABLE": "preprod-chaos-experiments",
        },
    )
    @patch("src.lambdas.shared.chaos_injection.boto3.resource")
    def test_defaults_to_300_second_duration(self, mock_boto3_resource):
        """Test defaults to 300 second duration when not specified."""
        # Started 4 minutes ago -- should NOT be stopped (default duration is 300s)
        started_at = (datetime.now(UTC) - timedelta(minutes=4)).isoformat() + "Z"

        mock_table = MagicMock()
        mock_table.query.return_value = {
            "Items": [
                {
                    "experiment_id": "exp-no-dur",
                    "scenario_type": "dynamodb_throttle",
                    "status": "running",
                    # No duration_seconds -- defaults to 300
                    "results": {"started_at": started_at},
                }
            ]
        }
        mock_dynamodb = MagicMock()
        mock_dynamodb.Table.return_value = mock_table
        mock_boto3_resource.return_value = mock_dynamodb

        result = auto_stop_expired("dynamodb_throttle")

        assert result is False
        mock_table.update_item.assert_not_called()

    @patch.dict(
        os.environ,
        {
            "ENVIRONMENT": "preprod",
            "CHAOS_EXPERIMENTS_TABLE": "preprod-chaos-experiments",
        },
    )
    @patch("src.lambdas.shared.chaos_injection.boto3.resource")
    def test_auto_stop_sets_results_metadata(self, mock_boto3_resource):
        """Test that auto-stop sets correct metadata in results."""
        started_at = (datetime.now(UTC) - timedelta(minutes=10)).isoformat() + "Z"

        mock_table = MagicMock()
        mock_table.query.return_value = {
            "Items": [
                {
                    "experiment_id": "exp-meta",
                    "scenario_type": "ingestion_failure",
                    "status": "running",
                    "duration_seconds": 60,
                    "results": {
                        "started_at": started_at,
                        "injection_method": "dynamodb_flag",
                    },
                }
            ]
        }
        mock_dynamodb = MagicMock()
        mock_dynamodb.Table.return_value = mock_table
        mock_boto3_resource.return_value = mock_dynamodb

        auto_stop_expired("ingestion_failure")

        update_call = mock_table.update_item.call_args[1]
        results = update_call["ExpressionAttributeValues"][":results"]
        assert results["auto_stopped"] is True
        assert "stopped_at" in results
        assert results["injection_method"] == "dynamodb_flag"  # Preserved original
