"""
Unit tests for chaos injection helper module.

Tests the fail-safe chaos detection system that coordinates
chaos experiments across Lambda functions.
"""

import os
from unittest.mock import MagicMock, patch

import pytest
from botocore.exceptions import ClientError

import src.lambdas.shared.chaos_injection as chaos_injection_module
from src.lambdas.shared.chaos_injection import is_chaos_active


class TestIsChaoActive:
    """Tests for is_chaos_active() function."""

    @pytest.fixture(autouse=True)
    def reset_dynamodb_client(self, monkeypatch):
        """Reset the global DynamoDB client before and after each test."""
        # Reset before test
        monkeypatch.setattr(chaos_injection_module, "_dynamodb_client", None)
        yield
        # Reset after test
        chaos_injection_module._dynamodb_client = None

    @patch.dict(
        os.environ,
        {
            "ENVIRONMENT": "preprod",
            "CHAOS_EXPERIMENTS_TABLE": "preprod-chaos-experiments",
        },
    )
    @patch("src.lambdas.shared.chaos_injection.boto3.resource")
    def test_active_experiment_found(self, mock_boto3_resource):
        """Test returns True when active experiment exists."""
        # Mock DynamoDB response with active experiment
        mock_table = MagicMock()
        mock_table.query.return_value = {
            "Items": [
                {
                    "experiment_id": "test-123",
                    "scenario_type": "ingestion_failure",
                    "status": "running",
                }
            ]
        }
        mock_dynamodb = MagicMock()
        mock_dynamodb.Table.return_value = mock_table
        mock_boto3_resource.return_value = mock_dynamodb

        result = is_chaos_active("ingestion_failure")

        assert result is True
        mock_table.query.assert_called_once()
        query_call = mock_table.query.call_args[1]
        assert query_call["IndexName"] == "by_status"
        assert query_call["ExpressionAttributeValues"][":status"] == "running"
        assert (
            query_call["ExpressionAttributeValues"][":scenario_type"]
            == "ingestion_failure"
        )

    @patch.dict(
        os.environ,
        {
            "ENVIRONMENT": "preprod",
            "CHAOS_EXPERIMENTS_TABLE": "preprod-chaos-experiments",
        },
    )
    @patch("src.lambdas.shared.chaos_injection.boto3.resource")
    def test_no_active_experiment(self, mock_boto3_resource):
        """Test returns False when no active experiments."""
        mock_table = MagicMock()
        mock_table.query.return_value = {"Items": []}
        mock_dynamodb = MagicMock()
        mock_dynamodb.Table.return_value = mock_table
        mock_boto3_resource.return_value = mock_dynamodb

        result = is_chaos_active("ingestion_failure")

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
        result = is_chaos_active("ingestion_failure")

        assert result is False

    @patch.dict(os.environ, {"ENVIRONMENT": "preprod", "CHAOS_EXPERIMENTS_TABLE": ""})
    def test_no_chaos_table_configured(self):
        """Test returns False when chaos table not configured."""
        result = is_chaos_active("ingestion_failure")

        assert result is False

    @patch.dict(
        os.environ,
        {
            "ENVIRONMENT": "preprod",
            "CHAOS_EXPERIMENTS_TABLE": "preprod-chaos-experiments",
        },
    )
    @patch("src.lambdas.shared.chaos_injection.boto3.resource")
    def test_dynamodb_client_error_returns_false(self, mock_boto3_resource):
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

        result = is_chaos_active("ingestion_failure")

        assert result is False

    @patch.dict(
        os.environ,
        {
            "ENVIRONMENT": "preprod",
            "CHAOS_EXPERIMENTS_TABLE": "preprod-chaos-experiments",
        },
    )
    @patch("src.lambdas.shared.chaos_injection.boto3.resource")
    def test_unexpected_exception_returns_false(self, mock_boto3_resource):
        """Test returns False on unexpected errors (fail-safe)."""
        mock_boto3_resource.side_effect = Exception("Unexpected error")

        result = is_chaos_active("ingestion_failure")

        assert result is False

    @patch.dict(
        os.environ,
        {"ENVIRONMENT": "dev", "CHAOS_EXPERIMENTS_TABLE": "dev-chaos-experiments"},
    )
    @patch("src.lambdas.shared.chaos_injection.boto3.resource")
    def test_dev_environment_allowed(self, mock_boto3_resource):
        """Test chaos detection works in dev environment."""
        mock_table = MagicMock()
        mock_table.query.return_value = {"Items": []}
        mock_dynamodb = MagicMock()
        mock_dynamodb.Table.return_value = mock_table
        mock_boto3_resource.return_value = mock_dynamodb

        result = is_chaos_active("dynamodb_throttle")

        assert result is False
        mock_table.query.assert_called_once()

    @patch.dict(
        os.environ,
        {"ENVIRONMENT": "test", "CHAOS_EXPERIMENTS_TABLE": "test-chaos-experiments"},
    )
    @patch("src.lambdas.shared.chaos_injection.boto3.resource")
    def test_test_environment_allowed(self, mock_boto3_resource):
        """Test chaos detection works in test environment."""
        mock_table = MagicMock()
        mock_table.query.return_value = {"Items": []}
        mock_dynamodb = MagicMock()
        mock_dynamodb.Table.return_value = mock_table
        mock_boto3_resource.return_value = mock_dynamodb

        result = is_chaos_active("lambda_cold_start")

        assert result is False
        mock_table.query.assert_called_once()

    @patch.dict(
        os.environ,
        {
            "ENVIRONMENT": "preprod",
            "CHAOS_EXPERIMENTS_TABLE": "preprod-chaos-experiments",
        },
    )
    @patch("src.lambdas.shared.chaos_injection.boto3.resource")
    def test_query_filters_by_scenario_type(self, mock_boto3_resource):
        """Test query filters by specific scenario type."""
        mock_table = MagicMock()
        mock_table.query.return_value = {"Items": []}
        mock_dynamodb = MagicMock()
        mock_dynamodb.Table.return_value = mock_table
        mock_boto3_resource.return_value = mock_dynamodb

        is_chaos_active("ingestion_failure")

        query_call = mock_table.query.call_args[1]
        assert query_call["FilterExpression"] == "scenario_type = :scenario_type"
        assert (
            query_call["ExpressionAttributeValues"][":scenario_type"]
            == "ingestion_failure"
        )

    @patch.dict(
        os.environ,
        {
            "ENVIRONMENT": "preprod",
            "CHAOS_EXPERIMENTS_TABLE": "preprod-chaos-experiments",
        },
    )
    @patch("src.lambdas.shared.chaos_injection.boto3.resource")
    def test_query_uses_by_status_gsi(self, mock_boto3_resource):
        """Test query uses by_status GSI for efficient lookups."""
        mock_table = MagicMock()
        mock_table.query.return_value = {"Items": []}
        mock_dynamodb = MagicMock()
        mock_dynamodb.Table.return_value = mock_table
        mock_boto3_resource.return_value = mock_dynamodb

        is_chaos_active("dynamodb_throttle")

        query_call = mock_table.query.call_args[1]
        assert query_call["IndexName"] == "by_status"
        assert query_call["KeyConditionExpression"] == "status = :status"
        assert query_call["ExpressionAttributeValues"][":status"] == "running"

    @patch.dict(
        os.environ,
        {
            "ENVIRONMENT": "preprod",
            "CHAOS_EXPERIMENTS_TABLE": "preprod-chaos-experiments",
        },
    )
    @patch("src.lambdas.shared.chaos_injection.boto3.resource")
    def test_query_limits_to_one_result(self, mock_boto3_resource):
        """Test query limits to 1 result for efficiency."""
        mock_table = MagicMock()
        mock_table.query.return_value = {"Items": []}
        mock_dynamodb = MagicMock()
        mock_dynamodb.Table.return_value = mock_table
        mock_boto3_resource.return_value = mock_dynamodb

        is_chaos_active("ingestion_failure")

        query_call = mock_table.query.call_args[1]
        assert query_call["Limit"] == 1

    @patch.dict(
        os.environ,
        {
            "ENVIRONMENT": "preprod",
            "CHAOS_EXPERIMENTS_TABLE": "preprod-chaos-experiments",
            "CLOUD_REGION": "us-west-2",
        },
    )
    @patch("src.lambdas.shared.chaos_injection.boto3.resource")
    def test_uses_cloud_region_env_var(self, mock_boto3_resource):
        """Test uses CLOUD_REGION environment variable."""
        mock_table = MagicMock()
        mock_table.query.return_value = {"Items": []}
        mock_dynamodb = MagicMock()
        mock_dynamodb.Table.return_value = mock_table
        mock_boto3_resource.return_value = mock_dynamodb

        is_chaos_active("ingestion_failure")

        mock_boto3_resource.assert_called_with("dynamodb", region_name="us-west-2")

    @patch.dict(
        os.environ,
        {
            "ENVIRONMENT": "preprod",
            "CHAOS_EXPERIMENTS_TABLE": "preprod-chaos-experiments",
            "AWS_REGION": "eu-west-1",
        },
    )
    @patch("src.lambdas.shared.chaos_injection.boto3.resource")
    def test_falls_back_to_aws_region(self, mock_boto3_resource):
        """Test falls back to AWS_REGION if CLOUD_REGION not set."""
        mock_table = MagicMock()
        mock_table.query.return_value = {"Items": []}
        mock_dynamodb = MagicMock()
        mock_dynamodb.Table.return_value = mock_table
        mock_boto3_resource.return_value = mock_dynamodb

        is_chaos_active("ingestion_failure")

        mock_boto3_resource.assert_called_with("dynamodb", region_name="eu-west-1")

    @patch.dict(
        os.environ,
        {
            "ENVIRONMENT": "preprod",
            "CHAOS_EXPERIMENTS_TABLE": "preprod-chaos-experiments",
        },
    )
    @patch("src.lambdas.shared.chaos_injection.boto3.resource")
    def test_caches_dynamodb_client(self, mock_boto3_resource):
        """Test caches DynamoDB client for Lambda container reuse."""
        mock_table = MagicMock()
        mock_table.query.return_value = {"Items": []}
        mock_dynamodb = MagicMock()
        mock_dynamodb.Table.return_value = mock_table
        mock_boto3_resource.return_value = mock_dynamodb

        # First call should create client
        is_chaos_active("ingestion_failure")
        assert mock_boto3_resource.call_count == 1

        # Second call should reuse cached client
        is_chaos_active("dynamodb_throttle")
        assert mock_boto3_resource.call_count == 1  # Not called again

    @patch.dict(
        os.environ,
        {
            "ENVIRONMENT": "preprod",
            "CHAOS_EXPERIMENTS_TABLE": "preprod-chaos-experiments",
        },
    )
    @patch("src.lambdas.shared.chaos_injection.boto3.resource")
    def test_multiple_items_returns_true(self, mock_boto3_resource):
        """Test returns True even if multiple active experiments (should be rare)."""
        mock_table = MagicMock()
        mock_table.query.return_value = {
            "Items": [
                {"experiment_id": "exp1", "status": "running"},
                {"experiment_id": "exp2", "status": "running"},
            ]
        }
        mock_dynamodb = MagicMock()
        mock_dynamodb.Table.return_value = mock_table
        mock_boto3_resource.return_value = mock_dynamodb

        result = is_chaos_active("ingestion_failure")

        assert result is True

    @patch.dict(
        os.environ,
        {
            "ENVIRONMENT": "staging",
            "CHAOS_EXPERIMENTS_TABLE": "staging-chaos-experiments",
        },
    )
    def test_staging_environment_returns_false(self):
        """Test returns False in staging (not in allowed list)."""
        result = is_chaos_active("ingestion_failure")

        assert result is False


# ===================================================================
# Tests for get_chaos_delay_ms() - Lines 125-204
# ===================================================================


class TestGetChaosDelayMs:
    """Tests for get_chaos_delay_ms() function.

    This function is critical for Lambda cold start simulation.
    Tests cover fail-safe behavior and delay retrieval.
    """

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
    def test_returns_delay_when_experiment_active(self, mock_boto3_resource):
        """Test returns delay_ms when active experiment found."""
        from src.lambdas.shared.chaos_injection import get_chaos_delay_ms

        mock_table = MagicMock()
        mock_table.query.return_value = {
            "Items": [
                {
                    "experiment_id": "test-123",
                    "scenario_type": "lambda_cold_start",
                    "status": "running",
                    "results": {"delay_ms": 3000},
                }
            ]
        }
        mock_dynamodb = MagicMock()
        mock_dynamodb.Table.return_value = mock_table
        mock_boto3_resource.return_value = mock_dynamodb

        result = get_chaos_delay_ms("lambda_cold_start")

        assert result == 3000

    @patch.dict(
        os.environ,
        {
            "ENVIRONMENT": "preprod",
            "CHAOS_EXPERIMENTS_TABLE": "preprod-chaos-experiments",
        },
    )
    @patch("src.lambdas.shared.chaos_injection.boto3.resource")
    def test_returns_zero_when_no_experiment(self, mock_boto3_resource):
        """Test returns 0 when no active experiment found."""
        from src.lambdas.shared.chaos_injection import get_chaos_delay_ms

        mock_table = MagicMock()
        mock_table.query.return_value = {"Items": []}
        mock_dynamodb = MagicMock()
        mock_dynamodb.Table.return_value = mock_table
        mock_boto3_resource.return_value = mock_dynamodb

        result = get_chaos_delay_ms("lambda_cold_start")

        assert result == 0

    @patch.dict(
        os.environ,
        {
            "ENVIRONMENT": "production",
            "CHAOS_EXPERIMENTS_TABLE": "prod-chaos-experiments",
        },
    )
    def test_production_environment_returns_zero(self):
        """Test returns 0 in production (safety check)."""
        from src.lambdas.shared.chaos_injection import get_chaos_delay_ms

        result = get_chaos_delay_ms("lambda_cold_start")

        assert result == 0

    @patch.dict(
        os.environ,
        {"ENVIRONMENT": "preprod", "CHAOS_EXPERIMENTS_TABLE": ""},
    )
    def test_no_chaos_table_returns_zero(self):
        """Test returns 0 when chaos table not configured."""
        from src.lambdas.shared.chaos_injection import get_chaos_delay_ms

        result = get_chaos_delay_ms("lambda_cold_start")

        assert result == 0

    @patch.dict(
        os.environ,
        {
            "ENVIRONMENT": "preprod",
            "CHAOS_EXPERIMENTS_TABLE": "preprod-chaos-experiments",
        },
    )
    @patch("src.lambdas.shared.chaos_injection.boto3.resource")
    def test_dynamodb_client_error_returns_zero(self, mock_boto3_resource):
        """Test returns 0 on DynamoDB errors (fail-safe)."""
        from src.lambdas.shared.chaos_injection import get_chaos_delay_ms

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

        result = get_chaos_delay_ms("lambda_cold_start")

        assert result == 0

    @patch.dict(
        os.environ,
        {
            "ENVIRONMENT": "preprod",
            "CHAOS_EXPERIMENTS_TABLE": "preprod-chaos-experiments",
        },
    )
    @patch("src.lambdas.shared.chaos_injection.boto3.resource")
    def test_unexpected_exception_returns_zero(self, mock_boto3_resource):
        """Test returns 0 on unexpected errors (fail-safe)."""
        from src.lambdas.shared.chaos_injection import get_chaos_delay_ms

        mock_boto3_resource.side_effect = Exception("Unexpected error")

        result = get_chaos_delay_ms("lambda_cold_start")

        assert result == 0

    @patch.dict(
        os.environ,
        {
            "ENVIRONMENT": "preprod",
            "CHAOS_EXPERIMENTS_TABLE": "preprod-chaos-experiments",
        },
    )
    @patch("src.lambdas.shared.chaos_injection.boto3.resource")
    def test_returns_zero_when_delay_not_in_results(self, mock_boto3_resource):
        """Test returns 0 when experiment has no delay_ms in results."""
        from src.lambdas.shared.chaos_injection import get_chaos_delay_ms

        mock_table = MagicMock()
        mock_table.query.return_value = {
            "Items": [
                {
                    "experiment_id": "test-123",
                    "scenario_type": "lambda_cold_start",
                    "status": "running",
                    "results": {},  # No delay_ms
                }
            ]
        }
        mock_dynamodb = MagicMock()
        mock_dynamodb.Table.return_value = mock_table
        mock_boto3_resource.return_value = mock_dynamodb

        result = get_chaos_delay_ms("lambda_cold_start")

        assert result == 0

    @patch.dict(
        os.environ,
        {
            "ENVIRONMENT": "dev",
            "CHAOS_EXPERIMENTS_TABLE": "dev-chaos-experiments",
        },
    )
    @patch("src.lambdas.shared.chaos_injection.boto3.resource")
    def test_dev_environment_allowed(self, mock_boto3_resource):
        """Test delay retrieval works in dev environment."""
        from src.lambdas.shared.chaos_injection import get_chaos_delay_ms

        mock_table = MagicMock()
        mock_table.query.return_value = {
            "Items": [
                {
                    "experiment_id": "test-dev-123",
                    "scenario_type": "lambda_cold_start",
                    "status": "running",
                    "results": {"delay_ms": 5000},
                }
            ]
        }
        mock_dynamodb = MagicMock()
        mock_dynamodb.Table.return_value = mock_table
        mock_boto3_resource.return_value = mock_dynamodb

        result = get_chaos_delay_ms("lambda_cold_start")

        assert result == 5000

    @patch.dict(
        os.environ,
        {
            "ENVIRONMENT": "test",
            "CHAOS_EXPERIMENTS_TABLE": "test-chaos-experiments",
        },
    )
    @patch("src.lambdas.shared.chaos_injection.boto3.resource")
    def test_test_environment_allowed(self, mock_boto3_resource):
        """Test delay retrieval works in test environment."""
        from src.lambdas.shared.chaos_injection import get_chaos_delay_ms

        mock_table = MagicMock()
        mock_table.query.return_value = {
            "Items": [
                {
                    "experiment_id": "test-test-123",
                    "scenario_type": "lambda_cold_start",
                    "status": "running",
                    "results": {"delay_ms": 2000},
                }
            ]
        }
        mock_dynamodb = MagicMock()
        mock_dynamodb.Table.return_value = mock_table
        mock_boto3_resource.return_value = mock_dynamodb

        result = get_chaos_delay_ms("lambda_cold_start")

        assert result == 2000

    @patch.dict(
        os.environ,
        {
            "ENVIRONMENT": "preprod",
            "CHAOS_EXPERIMENTS_TABLE": "preprod-chaos-experiments",
        },
    )
    @patch("src.lambdas.shared.chaos_injection.boto3.resource")
    def test_delay_converted_to_int(self, mock_boto3_resource):
        """Test delay_ms is converted to integer from Decimal."""
        from decimal import Decimal

        from src.lambdas.shared.chaos_injection import get_chaos_delay_ms

        mock_table = MagicMock()
        mock_table.query.return_value = {
            "Items": [
                {
                    "experiment_id": "test-123",
                    "scenario_type": "lambda_cold_start",
                    "status": "running",
                    "results": {"delay_ms": Decimal("4500")},
                }
            ]
        }
        mock_dynamodb = MagicMock()
        mock_dynamodb.Table.return_value = mock_table
        mock_boto3_resource.return_value = mock_dynamodb

        result = get_chaos_delay_ms("lambda_cold_start")

        assert result == 4500
        assert isinstance(result, int)

    @patch.dict(
        os.environ,
        {
            "ENVIRONMENT": "preprod",
            "CHAOS_EXPERIMENTS_TABLE": "preprod-chaos-experiments",
        },
    )
    @patch("src.lambdas.shared.chaos_injection.boto3.resource")
    def test_zero_delay_returns_zero(self, mock_boto3_resource):
        """Test returns 0 when delay_ms is explicitly 0."""
        from src.lambdas.shared.chaos_injection import get_chaos_delay_ms

        mock_table = MagicMock()
        mock_table.query.return_value = {
            "Items": [
                {
                    "experiment_id": "test-123",
                    "scenario_type": "lambda_cold_start",
                    "status": "running",
                    "results": {"delay_ms": 0},
                }
            ]
        }
        mock_dynamodb = MagicMock()
        mock_dynamodb.Table.return_value = mock_table
        mock_boto3_resource.return_value = mock_dynamodb

        result = get_chaos_delay_ms("lambda_cold_start")

        assert result == 0

    @patch.dict(
        os.environ,
        {
            "ENVIRONMENT": "staging",
            "CHAOS_EXPERIMENTS_TABLE": "staging-chaos-experiments",
        },
    )
    def test_staging_environment_returns_zero(self):
        """Test returns 0 in staging (not in allowed list)."""
        from src.lambdas.shared.chaos_injection import get_chaos_delay_ms

        result = get_chaos_delay_ms("lambda_cold_start")

        assert result == 0
