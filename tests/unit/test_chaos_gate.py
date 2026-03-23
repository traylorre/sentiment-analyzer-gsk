"""
Unit Tests for Chaos Gate Pattern with Dual-Mode Observability (Feature 1238)
=============================================================================

Tests the gate pattern that enables dry-run mode (disarmed gate) and baseline
health capture for chaos experiments. The gate evolves the kill switch from a
simple on/off to a three-state system: armed, disarmed, triggered.

Tests cover:
- Gate state checking (_check_gate)
- Armed gate executes real infrastructure changes
- Disarmed gate skips changes (dry-run), still records experiment
- Triggered gate blocks all operations
- SSM failure causes fail-closed behavior
- Baseline health capture (healthy and degraded dependencies)
- Post-chaos health comparison (recovery, new issues, persistent issues)
- Experiment report generation with verdicts
"""

from unittest.mock import MagicMock, patch

import pytest
from botocore.exceptions import ClientError

from src.lambdas.dashboard.chaos import (
    ChaosError,
    _capture_baseline,
    _capture_post_chaos_health,
    _check_gate,
    get_experiment_report,
    start_experiment,
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
        # Set up the ParameterNotFound exception on the mock
        mock_client.exceptions.ParameterNotFound = type(
            "ParameterNotFound", (ClientError,), {}
        )
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
# Tests for _check_gate()
# ===================================================================


class TestCheckGate:
    """Tests for the _check_gate() function."""

    def test_gate_armed_returns_armed(self, mock_ssm_client):
        """Test gate returns 'armed' when SSM parameter is 'armed'."""
        mock_ssm_client.get_parameter.return_value = {"Parameter": {"Value": "armed"}}
        result = _check_gate()
        assert result == "armed"

    def test_gate_disarmed_returns_disarmed(self, mock_ssm_client):
        """Test gate returns 'disarmed' when SSM parameter is 'disarmed'."""
        mock_ssm_client.get_parameter.return_value = {
            "Parameter": {"Value": "disarmed"}
        }
        result = _check_gate()
        assert result == "disarmed"

    def test_gate_triggered_raises_chaos_error(self, mock_ssm_client):
        """Test gate raises ChaosError when kill switch is triggered."""
        mock_ssm_client.get_parameter.return_value = {
            "Parameter": {"Value": "triggered"}
        }
        with pytest.raises(ChaosError) as exc_info:
            _check_gate()
        assert "Kill switch triggered" in str(exc_info.value)

    def test_gate_ssm_down_raises_chaos_error(self, mock_ssm_client):
        """Test gate raises ChaosError when SSM is unreachable (fail-closed)."""
        mock_ssm_client.get_parameter.side_effect = ClientError(
            {"Error": {"Code": "InternalError", "Message": "Service unavailable"}},
            "GetParameter",
        )
        with pytest.raises(ChaosError) as exc_info:
            _check_gate()
        assert "SSM unavailable" in str(exc_info.value)

    def test_gate_parameter_not_found_returns_disarmed(self, mock_ssm_client):
        """Test gate returns 'disarmed' when SSM parameter doesn't exist (first-time setup)."""
        mock_ssm_client.get_parameter.side_effect = (
            mock_ssm_client.exceptions.ParameterNotFound(
                {"Error": {"Code": "ParameterNotFound", "Message": "Not found"}},
                "GetParameter",
            )
        )
        result = _check_gate()
        assert result == "disarmed"


# ===================================================================
# Tests for gate pattern in start_experiment()
# ===================================================================


class TestGatePatternStartExperiment:
    """Tests for gate-aware start_experiment() behavior."""

    def test_gate_armed_executes_real_changes(
        self,
        mock_environment_preprod,
        mock_dynamodb_table,
        mock_lambda_client,
        mock_ssm_client,
        sample_experiment,
    ):
        """When gate is armed, real AWS API calls are made."""
        # Gate returns armed
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

        # Verify real AWS API was called
        mock_lambda_client.put_function_concurrency.assert_called_once_with(
            FunctionName="preprod-sentiment-ingestion",
            ReservedConcurrentExecutions=0,
        )

        # Verify results contain dry_run=False
        update_call = mock_dynamodb_table.update_item.call_args
        results = update_call[1]["ExpressionAttributeValues"][":results"]
        assert results["dry_run"] is False
        assert results["gate_state"] == "armed"

    def test_gate_disarmed_skips_changes(
        self,
        mock_environment_preprod,
        mock_dynamodb_table,
        mock_lambda_client,
        mock_ssm_client,
        sample_experiment,
    ):
        """When gate is disarmed, AWS API calls are skipped (dry-run) but experiment is recorded."""
        # Gate returns disarmed
        mock_ssm_client.get_parameter.return_value = {
            "Parameter": {"Value": "disarmed"}
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

        # Verify AWS API was NOT called (dry-run)
        mock_lambda_client.put_function_concurrency.assert_not_called()

        # Verify experiment was still recorded with dry_run=True
        update_call = mock_dynamodb_table.update_item.call_args
        results = update_call[1]["ExpressionAttributeValues"][":results"]
        assert results["dry_run"] is True
        assert results["gate_state"] == "disarmed"

    def test_gate_triggered_blocks(
        self,
        mock_environment_preprod,
        mock_dynamodb_table,
        mock_ssm_client,
        sample_experiment,
    ):
        """When gate is triggered, ChaosError is raised and no changes occur."""
        mock_ssm_client.get_parameter.return_value = {
            "Parameter": {"Value": "triggered"}
        }
        mock_dynamodb_table.get_item.return_value = {"Item": sample_experiment}

        with pytest.raises(ChaosError) as exc_info:
            start_experiment(sample_experiment["experiment_id"])

        assert "Kill switch triggered" in str(exc_info.value)

    def test_gate_ssm_down_blocks(
        self,
        mock_environment_preprod,
        mock_dynamodb_table,
        mock_ssm_client,
        sample_experiment,
    ):
        """When SSM is unreachable, ChaosError is raised (fail-closed)."""
        mock_ssm_client.get_parameter.side_effect = ClientError(
            {"Error": {"Code": "InternalError", "Message": "Service unavailable"}},
            "GetParameter",
        )
        mock_dynamodb_table.get_item.return_value = {"Item": sample_experiment}

        with pytest.raises(ChaosError) as exc_info:
            start_experiment(sample_experiment["experiment_id"])

        assert "SSM unavailable" in str(exc_info.value)


# ===================================================================
# Tests for _capture_baseline()
# ===================================================================


class TestCaptureBaseline:
    """Tests for the _capture_baseline() function."""

    def test_baseline_captures_healthy_deps(self, mock_ssm_client, mock_lambda_client):
        """When all dependencies are healthy, baseline reports all_healthy=True."""
        mock_ssm_client.get_parameter.return_value = {
            "Parameter": {"Value": "disarmed"}
        }
        mock_lambda_client.get_function.return_value = {}

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

            baseline = _capture_baseline("preprod")

        assert baseline["all_healthy"] is True
        assert baseline["degraded_services"] == []
        assert baseline["dependencies"]["dynamodb"]["status"] == "healthy"
        assert baseline["dependencies"]["ssm"]["status"] == "healthy"
        assert baseline["dependencies"]["cloudwatch"]["status"] == "healthy"
        assert baseline["dependencies"]["lambda"]["status"] == "healthy"

    def test_baseline_detects_degraded_dep(self, mock_ssm_client, mock_lambda_client):
        """When DynamoDB is unhealthy, baseline reports it as degraded."""
        mock_ssm_client.get_parameter.return_value = {
            "Parameter": {"Value": "disarmed"}
        }
        mock_lambda_client.get_function.return_value = {}

        with patch("src.lambdas.dashboard.chaos.boto3") as mock_boto3:
            mock_ddb_client = MagicMock()
            mock_ddb_client.describe_table.side_effect = ClientError(
                {
                    "Error": {
                        "Code": "ResourceNotFoundException",
                        "Message": "Table not found",
                    }
                },
                "DescribeTable",
            )
            mock_cw_client = MagicMock()
            mock_cw_client.describe_alarms.return_value = {}

            def client_factory(service_name, **kwargs):
                if service_name == "dynamodb":
                    return mock_ddb_client
                if service_name == "cloudwatch":
                    return mock_cw_client
                return MagicMock()

            mock_boto3.client.side_effect = client_factory

            baseline = _capture_baseline("preprod")

        assert baseline["all_healthy"] is False
        assert "dynamodb" in baseline["degraded_services"]
        assert baseline["dependencies"]["dynamodb"]["status"] == "degraded"
        assert "warning" in baseline


# ===================================================================
# Tests for _capture_post_chaos_health()
# ===================================================================


class TestCapturePostChaosHealth:
    """Tests for the _capture_post_chaos_health() function."""

    def test_post_chaos_comparison_recovery(self, mock_ssm_client, mock_lambda_client):
        """When baseline had degraded dynamodb but current is healthy, report recovery."""
        # Current health: all healthy
        mock_ssm_client.get_parameter.return_value = {
            "Parameter": {"Value": "disarmed"}
        }
        mock_lambda_client.get_function.return_value = {}

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

            baseline = {
                "degraded_services": ["dynamodb"],
                "dependencies": {
                    "dynamodb": {"status": "degraded", "error": "Table not found"},
                },
            }

            comparison = _capture_post_chaos_health("preprod", baseline)

        assert "dynamodb" in comparison["recovered"]
        assert comparison["new_issues"] == []
        assert comparison["persistent_issues"] == []


# ===================================================================
# Tests for get_experiment_report()
# ===================================================================


class TestExperimentReport:
    """Tests for the get_experiment_report() function."""

    def test_report_verdict_compromised(
        self, mock_environment_preprod, mock_dynamodb_table
    ):
        """When baseline had degraded services, verdict is COMPROMISED."""
        experiment = {
            "experiment_id": "test-123",
            "scenario_type": "ingestion_failure",
            "status": "stopped",
            "duration_seconds": 60,
            "results": {
                "started_at": "2024-01-15T10:00:00Z",
                "stopped_at": "2024-01-15T10:01:00Z",
                "dry_run": False,
                "baseline": {
                    "all_healthy": False,
                    "degraded_services": ["dynamodb"],
                },
                "post_chaos_health": {
                    "all_healthy": True,
                    "recovered": ["dynamodb"],
                    "new_issues": [],
                    "persistent_issues": [],
                },
            },
        }
        mock_dynamodb_table.get_item.return_value = {"Item": experiment}

        report = get_experiment_report("test-123")

        assert report["verdict"] == "COMPROMISED"
        assert "Pre-existing degradation" in report["verdict_reason"]

    def test_report_verdict_clean(self, mock_environment_preprod, mock_dynamodb_table):
        """When all healthy after chaos, verdict is CLEAN."""
        experiment = {
            "experiment_id": "test-456",
            "scenario_type": "ingestion_failure",
            "status": "stopped",
            "duration_seconds": 60,
            "results": {
                "started_at": "2024-01-15T10:00:00Z",
                "stopped_at": "2024-01-15T10:01:00Z",
                "dry_run": False,
                "baseline": {
                    "all_healthy": True,
                    "degraded_services": [],
                },
                "post_chaos_health": {
                    "all_healthy": True,
                    "recovered": [],
                    "new_issues": [],
                    "persistent_issues": [],
                },
            },
        }
        mock_dynamodb_table.get_item.return_value = {"Item": experiment}

        report = get_experiment_report("test-456")

        assert report["verdict"] == "CLEAN"
        assert "recovered to healthy state" in report["verdict_reason"]

    def test_report_verdict_dry_run_clean(
        self, mock_environment_preprod, mock_dynamodb_table
    ):
        """When dry_run is true, verdict is DRY_RUN_CLEAN."""
        experiment = {
            "experiment_id": "test-789",
            "scenario_type": "ingestion_failure",
            "status": "stopped",
            "duration_seconds": 60,
            "results": {
                "started_at": "2024-01-15T10:00:00Z",
                "stopped_at": "2024-01-15T10:01:00Z",
                "dry_run": True,
                "baseline": {
                    "all_healthy": True,
                    "degraded_services": [],
                },
                "post_chaos_health": {
                    "all_healthy": True,
                    "recovered": [],
                    "new_issues": [],
                    "persistent_issues": [],
                },
            },
        }
        mock_dynamodb_table.get_item.return_value = {"Item": experiment}

        report = get_experiment_report("test-789")

        assert report["verdict"] == "DRY_RUN_CLEAN"
        assert "Gate was disarmed" in report["verdict_reason"]

    def test_report_verdict_recovery_incomplete(
        self, mock_environment_preprod, mock_dynamodb_table
    ):
        """When there are new issues post-chaos, verdict is RECOVERY_INCOMPLETE."""
        experiment = {
            "experiment_id": "test-abc",
            "scenario_type": "ingestion_failure",
            "status": "stopped",
            "duration_seconds": 60,
            "results": {
                "started_at": "2024-01-15T10:00:00Z",
                "stopped_at": "2024-01-15T10:01:00Z",
                "dry_run": False,
                "baseline": {
                    "all_healthy": True,
                    "degraded_services": [],
                },
                "post_chaos_health": {
                    "all_healthy": False,
                    "recovered": [],
                    "new_issues": ["lambda"],
                    "persistent_issues": [],
                },
            },
        }
        mock_dynamodb_table.get_item.return_value = {"Item": experiment}

        report = get_experiment_report("test-abc")

        assert report["verdict"] == "RECOVERY_INCOMPLETE"
        assert "New issues after chaos" in report["verdict_reason"]

    def test_report_experiment_not_found(
        self, mock_environment_preprod, mock_dynamodb_table
    ):
        """When experiment doesn't exist, ChaosError is raised."""
        mock_dynamodb_table.get_item.return_value = {}

        with pytest.raises(ChaosError) as exc_info:
            get_experiment_report("nonexistent")

        assert "Experiment not found" in str(exc_info.value)

    def test_report_verdict_inconclusive(
        self, mock_environment_preprod, mock_dynamodb_table
    ):
        """When there's insufficient data, verdict is INCONCLUSIVE."""
        experiment = {
            "experiment_id": "test-inc",
            "scenario_type": "ingestion_failure",
            "status": "running",
            "duration_seconds": 60,
            "results": {
                "started_at": "2024-01-15T10:00:00Z",
                "dry_run": False,
                "baseline": {
                    "all_healthy": True,
                    "degraded_services": [],
                },
            },
        }
        mock_dynamodb_table.get_item.return_value = {"Item": experiment}

        report = get_experiment_report("test-inc")

        assert report["verdict"] == "INCONCLUSIVE"
        assert "Insufficient data" in report["verdict_reason"]
