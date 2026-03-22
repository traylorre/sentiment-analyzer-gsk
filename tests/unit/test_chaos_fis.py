"""
Unit Tests for Chaos Module -- External Actor Architecture (Feature 1237)
=========================================================================

Tests the rewritten chaos module that uses external AWS API calls
(Lambda configuration changes, IAM policy attach/detach, SSM snapshots)
instead of embedded DynamoDB flags.

Tests cover:
- CRUD operations (unchanged)
- start_experiment() with external API calls
- stop_experiment() with SSM snapshot restoration
- Kill switch validation
- Environment gating
"""

import json
from unittest.mock import MagicMock, patch

import pytest
from botocore.exceptions import ClientError

from src.lambdas.dashboard.chaos import (
    ChaosError,
    EnvironmentNotAllowedError,
    create_experiment,
    start_experiment,
    stop_experiment,
)

# ===================================================================
# Test fixtures
# ===================================================================


@pytest.fixture
def mock_environment_preprod(monkeypatch):
    """Set ENVIRONMENT to preprod for testing."""
    monkeypatch.setenv("ENVIRONMENT", "preprod")
    monkeypatch.setenv("CHAOS_EXPERIMENTS_TABLE", "preprod-chaos-experiments")
    import src.lambdas.dashboard.chaos as chaos_module

    monkeypatch.setattr(chaos_module, "ENVIRONMENT", "preprod")
    monkeypatch.setattr(chaos_module, "CHAOS_TABLE", "preprod-chaos-experiments")


@pytest.fixture
def mock_environment_prod(monkeypatch):
    """Set ENVIRONMENT to prod (should block chaos testing)."""
    monkeypatch.setenv("ENVIRONMENT", "prod")
    monkeypatch.setenv("CHAOS_EXPERIMENTS_TABLE", "prod-chaos-experiments")
    import src.lambdas.dashboard.chaos as chaos_module

    monkeypatch.setattr(chaos_module, "ENVIRONMENT", "prod")


@pytest.fixture
def mock_dynamodb_table():
    """Mock DynamoDB table resource."""
    with patch("src.lambdas.dashboard.chaos._get_dynamodb") as mock_dynamodb_getter:
        mock_dynamodb = MagicMock()
        mock_table = MagicMock()
        mock_dynamodb.Table.return_value = mock_table
        mock_dynamodb_getter.return_value = mock_dynamodb
        yield mock_table


@pytest.fixture
def mock_lambda_client():
    """Mock boto3 Lambda client."""
    with patch("src.lambdas.dashboard.chaos._get_lambda_client") as mock_client_getter:
        mock_client = MagicMock()
        mock_client_getter.return_value = mock_client
        yield mock_client


@pytest.fixture
def mock_ssm_client():
    """Mock boto3 SSM client."""
    with patch("src.lambdas.dashboard.chaos._get_ssm_client") as mock_client_getter:
        mock_client = MagicMock()
        mock_client_getter.return_value = mock_client
        yield mock_client


@pytest.fixture
def mock_iam_client():
    """Mock boto3 IAM client."""
    with patch("src.lambdas.dashboard.chaos._get_iam_client") as mock_client_getter:
        mock_client = MagicMock()
        mock_client_getter.return_value = mock_client
        yield mock_client


@pytest.fixture
def sample_experiment():
    """Sample chaos experiment for testing."""
    return {
        "experiment_id": "12345678-1234-1234-1234-123456789012",
        "created_at": "2024-01-15T10:00:00Z",
        "status": "pending",
        "scenario_type": "ingestion_failure",
        "blast_radius": 25,
        "duration_seconds": 60,
        "parameters": {},
        "results": {},
        "environment": "preprod",
        "ttl_timestamp": 1705305600,
    }


# ===================================================================
# Tests for create_experiment() -- CRUD unchanged
# ===================================================================


class TestCreateExperiment:
    """Tests for create_experiment() function."""

    def test_create_experiment_success(
        self, mock_environment_preprod, mock_dynamodb_table
    ):
        result = create_experiment(
            scenario_type="dynamodb_throttle",
            blast_radius=25,
            duration_seconds=60,
        )

        assert "experiment_id" in result
        assert result["scenario_type"] == "dynamodb_throttle"
        assert result["blast_radius"] == 25
        assert result["duration_seconds"] == 60
        assert result["status"] == "pending"
        assert result["environment"] == "preprod"
        mock_dynamodb_table.put_item.assert_called_once()

    def test_create_experiment_environment_not_allowed(
        self, mock_environment_prod, mock_dynamodb_table
    ):
        with pytest.raises(EnvironmentNotAllowedError) as exc_info:
            create_experiment(
                scenario_type="dynamodb_throttle",
                blast_radius=25,
                duration_seconds=60,
            )

        assert "not allowed in prod" in str(exc_info.value)
        mock_dynamodb_table.put_item.assert_not_called()

    def test_create_experiment_invalid_scenario_type(
        self, mock_environment_preprod, mock_dynamodb_table
    ):
        with pytest.raises(ValueError) as exc_info:
            create_experiment(
                scenario_type="invalid_scenario",
                blast_radius=25,
                duration_seconds=60,
            )

        assert "Invalid scenario_type" in str(exc_info.value)

    def test_create_experiment_blast_radius_too_low(
        self, mock_environment_preprod, mock_dynamodb_table
    ):
        with pytest.raises(ValueError) as exc_info:
            create_experiment(
                scenario_type="dynamodb_throttle",
                blast_radius=5,
                duration_seconds=60,
            )

        assert "blast_radius must be 10-100" in str(exc_info.value)

    def test_create_experiment_blast_radius_too_high(
        self, mock_environment_preprod, mock_dynamodb_table
    ):
        with pytest.raises(ValueError):
            create_experiment(
                scenario_type="dynamodb_throttle",
                blast_radius=150,
                duration_seconds=60,
            )

    def test_create_experiment_duration_boundaries(
        self, mock_environment_preprod, mock_dynamodb_table
    ):
        # Too short
        with pytest.raises(ValueError):
            create_experiment(
                scenario_type="dynamodb_throttle", blast_radius=25, duration_seconds=3
            )

        # Too long
        with pytest.raises(ValueError):
            create_experiment(
                scenario_type="dynamodb_throttle",
                blast_radius=25,
                duration_seconds=600,
            )

    def test_create_experiment_all_valid_scenarios(
        self, mock_environment_preprod, mock_dynamodb_table
    ):
        for scenario in [
            "dynamodb_throttle",
            "ingestion_failure",
            "lambda_cold_start",
            "trigger_failure",
            "api_timeout",
        ]:
            mock_dynamodb_table.reset_mock()
            result = create_experiment(
                scenario_type=scenario, blast_radius=50, duration_seconds=60
            )
            assert result["scenario_type"] == scenario
            mock_dynamodb_table.put_item.assert_called_once()

    def test_create_experiment_dynamodb_error(
        self, mock_environment_preprod, mock_dynamodb_table
    ):
        mock_dynamodb_table.put_item.side_effect = ClientError(
            {"Error": {"Code": "InternalServerError", "Message": "Error"}},
            "PutItem",
        )

        with pytest.raises(ChaosError) as exc_info:
            create_experiment(
                scenario_type="dynamodb_throttle",
                blast_radius=25,
                duration_seconds=60,
            )

        assert "Failed to create experiment" in str(exc_info.value)


# ===================================================================
# Tests for start_experiment() -- External API calls (Feature 1237)
# ===================================================================


class TestStartExperimentExternal:
    """Tests for start_experiment() with external AWS API calls."""

    def test_start_ingestion_failure_sets_concurrency_zero(
        self,
        mock_environment_preprod,
        mock_dynamodb_table,
        mock_lambda_client,
        mock_ssm_client,
        sample_experiment,
    ):
        """Test ingestion_failure scenario sets Lambda concurrency to 0."""
        # Gate must be "armed" for real API calls (Feature 1238)
        mock_ssm_client.get_parameter.return_value = {"Parameter": {"Value": "armed"}}
        # Mock snapshot: get_function_configuration
        mock_lambda_client.get_function_configuration.return_value = {
            "FunctionName": "preprod-sentiment-ingestion",
            "FunctionArn": "arn:aws:lambda:us-east-1:123:function:preprod-sentiment-ingestion",
            "MemorySize": 512,
            "Timeout": 60,
        }
        mock_lambda_client.get_function_concurrency.return_value = {
            "ReservedConcurrentExecutions": 1
        }
        mock_lambda_client.get_function.return_value = {}

        mock_dynamodb_table.get_item.return_value = {"Item": sample_experiment}

        with patch("src.lambdas.dashboard.chaos.boto3") as mock_boto3:
            mock_ddb_client = MagicMock()
            mock_ddb_client.describe_table.return_value = {}
            mock_cw_client = MagicMock()
            mock_cw_client.describe_alarms.return_value = {}

            def client_factory(service_name, **kwargs):
                if service_name == "dynamodb":
                    return mock_ddb_client
                if service_name == "cloudwatch":
                    return mock_cw_client
                return MagicMock()

            mock_boto3.client.side_effect = client_factory

            start_experiment(sample_experiment["experiment_id"])

        # Verify concurrency set to 0
        mock_lambda_client.put_function_concurrency.assert_called_once_with(
            FunctionName="preprod-sentiment-ingestion",
            ReservedConcurrentExecutions=0,
        )

        # Verify audit log updated with concurrency_zero method (Feature 1238)
        mock_dynamodb_table.update_item.assert_called()
        update_call = mock_dynamodb_table.update_item.call_args
        results = update_call[1]["ExpressionAttributeValues"][":results"]
        assert results["injection_method"] == "concurrency_zero"
        assert results["dry_run"] is False

    def test_start_dynamodb_throttle_attaches_deny_policy(
        self,
        mock_environment_preprod,
        mock_dynamodb_table,
        mock_lambda_client,
        mock_ssm_client,
        mock_iam_client,
        sample_experiment,
    ):
        """Test dynamodb_throttle scenario attaches deny-write IAM policy."""
        sample_experiment["scenario_type"] = "dynamodb_throttle"

        # Gate must be "armed" for real API calls (Feature 1238)
        mock_ssm_client.get_parameter.return_value = {"Parameter": {"Value": "armed"}}
        mock_lambda_client.get_function_configuration.return_value = {
            "FunctionName": "preprod-sentiment-ingestion",
            "FunctionArn": "arn:aws:lambda:us-east-1:123:function:preprod-sentiment-ingestion",
            "MemorySize": 512,
            "Timeout": 60,
        }
        mock_lambda_client.get_function_concurrency.return_value = {}
        mock_lambda_client.get_function.return_value = {}

        mock_dynamodb_table.get_item.return_value = {"Item": sample_experiment}

        with (
            patch("src.lambdas.dashboard.chaos.boto3") as mock_boto3,
            patch("src.lambdas.dashboard.chaos.time") as mock_time,
        ):
            mock_sts = MagicMock()
            mock_sts.get_caller_identity.return_value = {"Account": "123456789012"}
            mock_ddb_client = MagicMock()
            mock_ddb_client.describe_table.return_value = {}
            mock_cw_client = MagicMock()
            mock_cw_client.describe_alarms.return_value = {}

            def client_factory(service_name, **kwargs):
                if service_name == "sts":
                    return mock_sts
                if service_name == "dynamodb":
                    return mock_ddb_client
                if service_name == "cloudwatch":
                    return mock_cw_client
                return MagicMock()

            mock_boto3.client.side_effect = client_factory

            start_experiment(sample_experiment["experiment_id"])

        # Verify IAM propagation delay
        mock_time.sleep.assert_called_once_with(5)

        # Verify IAM policy attached to both roles
        assert mock_iam_client.attach_role_policy.call_count == 2

        # Verify audit log (Feature 1238: method names updated)
        update_call = mock_dynamodb_table.update_item.call_args
        results = update_call[1]["ExpressionAttributeValues"][":results"]
        assert results["injection_method"] == "attach_deny_policy"
        assert results["dry_run"] is False

    def test_start_cold_start_reduces_memory(
        self,
        mock_environment_preprod,
        mock_dynamodb_table,
        mock_lambda_client,
        mock_ssm_client,
        sample_experiment,
    ):
        """Test lambda_cold_start scenario reduces memory to 128MB."""
        sample_experiment["scenario_type"] = "lambda_cold_start"

        # Gate must be "armed" for real API calls (Feature 1238)
        mock_ssm_client.get_parameter.return_value = {"Parameter": {"Value": "armed"}}
        mock_lambda_client.get_function_configuration.return_value = {
            "FunctionName": "preprod-sentiment-analysis",
            "FunctionArn": "arn:aws:lambda:us-east-1:123:function:preprod-sentiment-analysis",
            "MemorySize": 2048,
            "Timeout": 120,
        }
        mock_lambda_client.get_function_concurrency.return_value = {}
        mock_lambda_client.get_function.return_value = {}

        mock_dynamodb_table.get_item.return_value = {"Item": sample_experiment}

        with patch("src.lambdas.dashboard.chaos.boto3") as mock_boto3:
            mock_ddb_client = MagicMock()
            mock_ddb_client.describe_table.return_value = {}
            mock_cw_client = MagicMock()
            mock_cw_client.describe_alarms.return_value = {}

            def client_factory(service_name, **kwargs):
                if service_name == "dynamodb":
                    return mock_ddb_client
                if service_name == "cloudwatch":
                    return mock_cw_client
                return MagicMock()

            mock_boto3.client.side_effect = client_factory

            start_experiment(sample_experiment["experiment_id"])

        # Verify memory set to 128MB
        mock_lambda_client.update_function_configuration.assert_called_once_with(
            FunctionName="preprod-sentiment-analysis",
            MemorySize=128,
        )

    def test_start_experiment_checks_kill_switch(
        self,
        mock_environment_preprod,
        mock_dynamodb_table,
        mock_ssm_client,
        sample_experiment,
    ):
        """Test start_experiment refuses when kill switch is triggered."""
        mock_ssm_client.get_parameter.return_value = {
            "Parameter": {"Value": "triggered"}
        }
        mock_dynamodb_table.get_item.return_value = {"Item": sample_experiment}

        with pytest.raises(ChaosError) as exc_info:
            start_experiment(sample_experiment["experiment_id"])

        assert "Kill switch triggered" in str(exc_info.value)

    def test_start_experiment_snapshots_config_to_ssm(
        self,
        mock_environment_preprod,
        mock_dynamodb_table,
        mock_lambda_client,
        mock_ssm_client,
        sample_experiment,
    ):
        """Test start_experiment saves pre-chaos config to SSM before degrading."""
        # Gate must be "armed" for real API calls (Feature 1238)
        mock_ssm_client.get_parameter.return_value = {"Parameter": {"Value": "armed"}}
        mock_lambda_client.get_function_configuration.return_value = {
            "FunctionName": "preprod-sentiment-ingestion",
            "FunctionArn": "arn:aws:lambda:us-east-1:123:function:preprod-sentiment-ingestion",
            "MemorySize": 512,
            "Timeout": 60,
        }
        mock_lambda_client.get_function_concurrency.return_value = {
            "ReservedConcurrentExecutions": 1
        }
        mock_lambda_client.get_function.return_value = {}

        mock_dynamodb_table.get_item.return_value = {"Item": sample_experiment}

        with patch("src.lambdas.dashboard.chaos.boto3") as mock_boto3:
            mock_ddb_client = MagicMock()
            mock_ddb_client.describe_table.return_value = {}
            mock_cw_client = MagicMock()
            mock_cw_client.describe_alarms.return_value = {}

            def client_factory(service_name, **kwargs):
                if service_name == "dynamodb":
                    return mock_ddb_client
                if service_name == "cloudwatch":
                    return mock_cw_client
                return MagicMock()

            mock_boto3.client.side_effect = client_factory

            start_experiment(sample_experiment["experiment_id"])

        # SSM put_parameter should be called twice:
        # 1. Snapshot config
        # 2. Set kill switch to "armed"
        ssm_calls = mock_ssm_client.put_parameter.call_args_list
        assert len(ssm_calls) >= 2

        # First call: snapshot
        snapshot_call = ssm_calls[0]
        assert "/chaos/preprod/snapshot/" in snapshot_call[1]["Name"]
        snapshot_data = json.loads(snapshot_call[1]["Value"])
        assert snapshot_data["MemorySize"] == 512
        assert snapshot_data["Timeout"] == 60

    def test_start_experiment_not_found(
        self, mock_environment_preprod, mock_dynamodb_table, mock_ssm_client
    ):
        mock_ssm_client.get_parameter.return_value = {
            "Parameter": {"Value": "disarmed"}
        }
        mock_dynamodb_table.get_item.return_value = {}

        with pytest.raises(ChaosError) as exc_info:
            start_experiment("nonexistent-experiment-id")

        assert "Experiment not found" in str(exc_info.value)

    def test_start_experiment_invalid_status(
        self,
        mock_environment_preprod,
        mock_dynamodb_table,
        mock_ssm_client,
        sample_experiment,
    ):
        mock_ssm_client.get_parameter.return_value = {
            "Parameter": {"Value": "disarmed"}
        }
        sample_experiment["status"] = "running"
        mock_dynamodb_table.get_item.return_value = {"Item": sample_experiment}

        with pytest.raises(ChaosError) as exc_info:
            start_experiment(sample_experiment["experiment_id"])

        assert "must be in 'pending' status" in str(exc_info.value)

    def test_start_experiment_prod_blocked(
        self,
        mock_environment_prod,
        mock_dynamodb_table,
        sample_experiment,
    ):
        with pytest.raises(EnvironmentNotAllowedError):
            start_experiment(sample_experiment["experiment_id"])


# ===================================================================
# Tests for stop_experiment() -- SSM Snapshot Restoration
# ===================================================================


class TestStopExperimentExternal:
    """Tests for stop_experiment() with SSM snapshot restoration."""

    def test_stop_ingestion_failure_restores_concurrency(
        self,
        mock_environment_preprod,
        mock_dynamodb_table,
        mock_lambda_client,
        mock_ssm_client,
        sample_experiment,
    ):
        """Test stop_experiment restores concurrency from SSM snapshot."""
        sample_experiment["status"] = "running"
        sample_experiment["results"] = {
            "started_at": "2025-01-01T00:00:00Z",
            "injection_method": "external_api",
        }
        mock_dynamodb_table.get_item.return_value = {"Item": sample_experiment}

        # Mock SSM snapshot read
        snapshot = {
            "FunctionName": "preprod-sentiment-ingestion",
            "MemorySize": 512,
            "Timeout": 60,
            "ReservedConcurrency": "1",
        }
        mock_ssm_client.get_parameter.return_value = {
            "Parameter": {"Value": json.dumps(snapshot)}
        }

        with patch(
            "src.lambdas.dashboard.chaos.update_experiment_status"
        ) as mock_update:
            mock_update.return_value = True
            stop_experiment(sample_experiment["experiment_id"])

        # Verify concurrency restored
        mock_lambda_client.put_function_concurrency.assert_called_once_with(
            FunctionName="preprod-sentiment-ingestion",
            ReservedConcurrentExecutions=1,
        )

        # Verify snapshot deleted
        mock_ssm_client.delete_parameter.assert_called()

    def test_stop_cold_start_restores_memory(
        self,
        mock_environment_preprod,
        mock_dynamodb_table,
        mock_lambda_client,
        mock_ssm_client,
        sample_experiment,
    ):
        """Test stop_experiment restores memory from SSM snapshot."""
        sample_experiment["scenario_type"] = "lambda_cold_start"
        sample_experiment["status"] = "running"
        mock_dynamodb_table.get_item.return_value = {"Item": sample_experiment}

        snapshot = {
            "FunctionName": "preprod-sentiment-analysis",
            "MemorySize": 2048,
            "Timeout": 120,
            "ReservedConcurrency": "NONE",
        }
        mock_ssm_client.get_parameter.return_value = {
            "Parameter": {"Value": json.dumps(snapshot)}
        }

        with patch(
            "src.lambdas.dashboard.chaos.update_experiment_status"
        ) as mock_update:
            mock_update.return_value = True
            stop_experiment(sample_experiment["experiment_id"])

        mock_lambda_client.update_function_configuration.assert_called_once_with(
            FunctionName="preprod-sentiment-analysis",
            MemorySize=2048,
        )

    def test_stop_dynamodb_throttle_detaches_policy(
        self,
        mock_environment_preprod,
        mock_dynamodb_table,
        mock_ssm_client,
        mock_iam_client,
        sample_experiment,
    ):
        """Test stop_experiment detaches deny-write policy."""
        sample_experiment["scenario_type"] = "dynamodb_throttle"
        sample_experiment["status"] = "running"
        mock_dynamodb_table.get_item.return_value = {"Item": sample_experiment}

        snapshot = {
            "FunctionName": "preprod-sentiment-ingestion",
            "MemorySize": 512,
            "Timeout": 60,
            "ReservedConcurrency": "NONE",
        }
        mock_ssm_client.get_parameter.return_value = {
            "Parameter": {"Value": json.dumps(snapshot)}
        }

        with (
            patch(
                "src.lambdas.dashboard.chaos.update_experiment_status"
            ) as mock_update,
            patch("src.lambdas.dashboard.chaos.boto3") as mock_boto3,
        ):
            mock_update.return_value = True
            mock_sts = MagicMock()
            mock_sts.get_caller_identity.return_value = {"Account": "123456789012"}
            mock_boto3.client.return_value = mock_sts

            stop_experiment(sample_experiment["experiment_id"])

        # Verify policy detached from both roles
        assert mock_iam_client.detach_role_policy.call_count == 2

    def test_stop_experiment_sets_kill_switch_disarmed(
        self,
        mock_environment_preprod,
        mock_dynamodb_table,
        mock_lambda_client,
        mock_ssm_client,
        sample_experiment,
    ):
        """Test stop_experiment sets kill switch to disarmed."""
        sample_experiment["status"] = "running"
        mock_dynamodb_table.get_item.return_value = {"Item": sample_experiment}

        snapshot = {
            "FunctionName": "preprod-sentiment-ingestion",
            "MemorySize": 512,
            "Timeout": 60,
            "ReservedConcurrency": "NONE",
        }
        # First get_parameter for snapshot read, subsequent for kill switch
        mock_ssm_client.get_parameter.return_value = {
            "Parameter": {"Value": json.dumps(snapshot)}
        }

        with patch(
            "src.lambdas.dashboard.chaos.update_experiment_status"
        ) as mock_update:
            mock_update.return_value = True
            stop_experiment(sample_experiment["experiment_id"])

        # Verify kill switch set to disarmed
        ssm_put_calls = mock_ssm_client.put_parameter.call_args_list
        kill_switch_call = [c for c in ssm_put_calls if "kill-switch" in str(c)]
        assert len(kill_switch_call) >= 1
        assert kill_switch_call[0][1]["Value"] == "disarmed"

    def test_stop_experiment_invalid_status(
        self,
        mock_environment_preprod,
        mock_dynamodb_table,
        mock_ssm_client,
        sample_experiment,
    ):
        mock_ssm_client.get_parameter.return_value = {
            "Parameter": {"Value": "disarmed"}
        }
        sample_experiment["status"] = "completed"
        mock_dynamodb_table.get_item.return_value = {"Item": sample_experiment}

        with pytest.raises(ChaosError) as exc_info:
            stop_experiment(sample_experiment["experiment_id"])

        assert "must be in 'running' status" in str(exc_info.value)

    def test_stop_experiment_not_found(
        self, mock_environment_preprod, mock_dynamodb_table, mock_ssm_client
    ):
        mock_ssm_client.get_parameter.return_value = {
            "Parameter": {"Value": "disarmed"}
        }
        mock_dynamodb_table.get_item.return_value = {}

        with pytest.raises(ChaosError) as exc_info:
            stop_experiment("nonexistent-id")

        assert "Experiment not found" in str(exc_info.value)
