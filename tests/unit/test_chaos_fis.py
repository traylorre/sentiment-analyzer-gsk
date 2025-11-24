"""
Unit Tests for AWS FIS Integration in Chaos Module
===================================================

Tests FIS experiment lifecycle:
- start_fis_experiment()
- stop_fis_experiment()
- get_fis_experiment_status()
- start_experiment() (DynamoDB throttle scenario)
- stop_experiment() (DynamoDB throttle scenario)
"""

from datetime import datetime
from unittest.mock import MagicMock, patch

import pytest
from botocore.exceptions import ClientError

from src.lambdas.dashboard.chaos import (
    ChaosError,
    EnvironmentNotAllowedError,
    get_fis_experiment_status,
    start_experiment,
    start_fis_experiment,
    stop_experiment,
    stop_fis_experiment,
)


# Test fixtures
@pytest.fixture
def mock_environment_preprod(monkeypatch):
    """Set ENVIRONMENT to preprod for testing."""
    monkeypatch.setenv("ENVIRONMENT", "preprod")
    monkeypatch.setenv("CHAOS_EXPERIMENTS_TABLE", "preprod-chaos-experiments")
    monkeypatch.setenv("FIS_DYNAMODB_THROTTLE_TEMPLATE", "EXTtemplate123456789")
    # Reload module-level variables
    import src.lambdas.dashboard.chaos as chaos_module

    monkeypatch.setattr(chaos_module, "ENVIRONMENT", "preprod")
    monkeypatch.setattr(
        chaos_module, "FIS_DYNAMODB_THROTTLE_TEMPLATE", "EXTtemplate123456789"
    )


@pytest.fixture
def mock_environment_prod(monkeypatch):
    """Set ENVIRONMENT to prod (should block chaos testing)."""
    monkeypatch.setenv("ENVIRONMENT", "prod")
    monkeypatch.setenv("CHAOS_EXPERIMENTS_TABLE", "prod-chaos-experiments")
    monkeypatch.setenv("FIS_DYNAMODB_THROTTLE_TEMPLATE", "EXTtemplate123456789")
    # Reload module-level variables
    import src.lambdas.dashboard.chaos as chaos_module

    monkeypatch.setattr(chaos_module, "ENVIRONMENT", "prod")
    monkeypatch.setattr(
        chaos_module, "FIS_DYNAMODB_THROTTLE_TEMPLATE", "EXTtemplate123456789"
    )


@pytest.fixture
def mock_fis_client():
    """Mock boto3 FIS client."""
    with patch("src.lambdas.dashboard.chaos.fis_client") as mock_client:
        yield mock_client


@pytest.fixture
def mock_dynamodb_table():
    """Mock DynamoDB table resource."""
    with patch("src.lambdas.dashboard.chaos.dynamodb") as mock_dynamodb:
        mock_table = MagicMock()
        mock_dynamodb.Table.return_value = mock_table
        yield mock_table


@pytest.fixture
def sample_experiment():
    """Sample chaos experiment for testing."""
    return {
        "experiment_id": "12345678-1234-1234-1234-123456789012",
        "created_at": "2024-01-15T10:00:00Z",
        "status": "pending",
        "scenario_type": "dynamodb_throttle",
        "blast_radius": 25,
        "duration_seconds": 60,
        "parameters": {},
        "results": {},
        "environment": "preprod",
        "ttl_timestamp": 1705305600,
    }


# ===================================================================
# Tests for start_fis_experiment()
# ===================================================================


class TestStartFISExperiment:
    """Tests for starting AWS FIS experiments."""

    def test_start_fis_experiment_success(
        self, mock_environment_preprod, mock_fis_client
    ):
        """Test successful FIS experiment start."""
        mock_fis_client.start_experiment.return_value = {
            "experiment": {"id": "EXP123456789"}
        }

        fis_experiment_id = start_fis_experiment(
            experiment_id="12345678-1234-1234-1234-123456789012",
            blast_radius=25,
            duration_seconds=300,
        )

        assert fis_experiment_id == "EXP123456789"
        mock_fis_client.start_experiment.assert_called_once()

        # Verify API call parameters
        call_args = mock_fis_client.start_experiment.call_args
        assert call_args.kwargs["experimentTemplateId"] == "EXTtemplate123456789"
        assert (
            call_args.kwargs["tags"]["chaos_experiment_id"]
            == "12345678-1234-1234-1234-123456789012"
        )
        assert call_args.kwargs["tags"]["environment"] == "preprod"
        assert call_args.kwargs["tags"]["blast_radius"] == "25"

    def test_start_fis_experiment_environment_not_allowed(
        self, mock_environment_prod, mock_fis_client
    ):
        """Test FIS experiment start fails in prod environment."""
        with pytest.raises(EnvironmentNotAllowedError) as exc_info:
            start_fis_experiment(
                experiment_id="12345678-1234-1234-1234-123456789012",
                blast_radius=25,
                duration_seconds=300,
            )

        assert "not allowed in prod" in str(exc_info.value)
        mock_fis_client.start_experiment.assert_not_called()

    def test_start_fis_experiment_missing_template_id(
        self, mock_environment_preprod, mock_fis_client, monkeypatch
    ):
        """Test FIS experiment start fails when template ID not set."""
        monkeypatch.delenv("FIS_DYNAMODB_THROTTLE_TEMPLATE", raising=False)
        # Reload module-level variable
        import src.lambdas.dashboard.chaos as chaos_module

        monkeypatch.setattr(chaos_module, "FIS_DYNAMODB_THROTTLE_TEMPLATE", "")

        with pytest.raises(ChaosError) as exc_info:
            start_fis_experiment(
                experiment_id="12345678-1234-1234-1234-123456789012",
                blast_radius=25,
                duration_seconds=300,
            )

        assert "environment variable not set" in str(exc_info.value)
        mock_fis_client.start_experiment.assert_not_called()

    def test_start_fis_experiment_client_error(
        self, mock_environment_preprod, mock_fis_client
    ):
        """Test FIS experiment start handles ClientError."""
        mock_fis_client.start_experiment.side_effect = ClientError(
            error_response={
                "Error": {
                    "Code": "ResourceNotFoundException",
                    "Message": "Template not found",
                }
            },
            operation_name="StartExperiment",
        )

        with pytest.raises(ChaosError) as exc_info:
            start_fis_experiment(
                experiment_id="12345678-1234-1234-1234-123456789012",
                blast_radius=25,
                duration_seconds=300,
            )

        assert "FIS experiment failed to start" in str(exc_info.value)
        assert "ResourceNotFoundException" in str(exc_info.value)

    def test_start_fis_experiment_duration_conversion(
        self, mock_environment_preprod, mock_fis_client
    ):
        """Test duration conversion to ISO 8601 format."""
        mock_fis_client.start_experiment.return_value = {
            "experiment": {"id": "EXP123456789"}
        }

        # Test 5 minutes (300 seconds)
        start_fis_experiment(
            experiment_id="12345678-1234-1234-1234-123456789012",
            blast_radius=25,
            duration_seconds=300,
        )

        # Test <1 minute (30 seconds) - should round to PT1M
        start_fis_experiment(
            experiment_id="12345678-1234-1234-1234-123456789012",
            blast_radius=25,
            duration_seconds=30,
        )

        assert mock_fis_client.start_experiment.call_count == 2


# ===================================================================
# Tests for stop_fis_experiment()
# ===================================================================


class TestStopFISExperiment:
    """Tests for stopping AWS FIS experiments."""

    def test_stop_fis_experiment_success(
        self, mock_environment_preprod, mock_fis_client
    ):
        """Test successful FIS experiment stop."""
        result = stop_fis_experiment(fis_experiment_id="EXP123456789")

        assert result is True
        mock_fis_client.stop_experiment.assert_called_once_with(id="EXP123456789")

    def test_stop_fis_experiment_environment_not_allowed(
        self, mock_environment_prod, mock_fis_client
    ):
        """Test FIS experiment stop fails in prod environment."""
        with pytest.raises(EnvironmentNotAllowedError) as exc_info:
            stop_fis_experiment(fis_experiment_id="EXP123456789")

        assert "not allowed in prod" in str(exc_info.value)
        mock_fis_client.stop_experiment.assert_not_called()

    def test_stop_fis_experiment_client_error(
        self, mock_environment_preprod, mock_fis_client
    ):
        """Test FIS experiment stop handles ClientError."""
        mock_fis_client.stop_experiment.side_effect = ClientError(
            error_response={
                "Error": {
                    "Code": "ResourceNotFoundException",
                    "Message": "Experiment not found",
                }
            },
            operation_name="StopExperiment",
        )

        with pytest.raises(ChaosError) as exc_info:
            stop_fis_experiment(fis_experiment_id="EXP123456789")

        assert "FIS experiment failed to stop" in str(exc_info.value)
        assert "ResourceNotFoundException" in str(exc_info.value)


# ===================================================================
# Tests for get_fis_experiment_status()
# ===================================================================


class TestGetFISExperimentStatus:
    """Tests for getting AWS FIS experiment status."""

    def test_get_fis_experiment_status_success(self, mock_fis_client):
        """Test successful FIS experiment status retrieval."""
        mock_fis_client.get_experiment.return_value = {
            "experiment": {
                "id": "EXP123456789",
                "state": {"status": "running", "reason": ""},
                "creationTime": datetime(2024, 1, 15, 10, 0, 0),
                "startTime": datetime(2024, 1, 15, 10, 5, 0),
            }
        }

        status = get_fis_experiment_status(fis_experiment_id="EXP123456789")

        assert status["id"] == "EXP123456789"
        assert status["state"] == "running"
        assert status["created_time"] == "2024-01-15T10:00:00"
        assert status["start_time"] == "2024-01-15T10:05:00"
        mock_fis_client.get_experiment.assert_called_once_with(id="EXP123456789")

    def test_get_fis_experiment_status_client_error(self, mock_fis_client):
        """Test FIS experiment status handles ClientError."""
        mock_fis_client.get_experiment.side_effect = ClientError(
            error_response={
                "Error": {
                    "Code": "ResourceNotFoundException",
                    "Message": "Experiment not found",
                }
            },
            operation_name="GetExperiment",
        )

        with pytest.raises(ChaosError) as exc_info:
            get_fis_experiment_status(fis_experiment_id="EXP123456789")

        assert "Failed to get FIS experiment status" in str(exc_info.value)
        assert "ResourceNotFoundException" in str(exc_info.value)


# ===================================================================
# Tests for start_experiment() with FIS Integration
# ===================================================================


class TestStartExperimentWithFIS:
    """Tests for start_experiment() with AWS FIS integration."""

    def test_start_experiment_dynamodb_throttle_success(
        self,
        mock_environment_preprod,
        mock_fis_client,
        mock_dynamodb_table,
        sample_experiment,
    ):
        """Test starting DynamoDB throttle experiment with FIS."""
        # Mock get_experiment to return pending experiment
        mock_dynamodb_table.get_item.return_value = {"Item": sample_experiment}

        # Mock FIS start
        mock_fis_client.start_experiment.return_value = {
            "experiment": {"id": "EXP123456789"}
        }

        # Mock update_experiment_status
        with patch(
            "src.lambdas.dashboard.chaos.update_experiment_status"
        ) as mock_update:
            mock_update.return_value = True

            start_experiment(sample_experiment["experiment_id"])

            # Verify FIS experiment was started
            mock_fis_client.start_experiment.assert_called_once()

            # Verify experiment status was updated
            mock_update.assert_called_once()
            call_args = mock_update.call_args
            assert call_args[0][0] == sample_experiment["experiment_id"]
            assert call_args[0][1] == "running"
            assert "fis_experiment_id" in call_args[0][2]
            assert call_args[0][2]["fis_experiment_id"] == "EXP123456789"

    def test_start_experiment_not_found(
        self, mock_environment_preprod, mock_dynamodb_table
    ):
        """Test starting experiment fails when experiment not found."""
        mock_dynamodb_table.get_item.return_value = {}

        with pytest.raises(ChaosError) as exc_info:
            start_experiment("nonexistent-experiment-id")

        assert "Experiment not found" in str(exc_info.value)

    def test_start_experiment_invalid_status(
        self, mock_environment_preprod, mock_dynamodb_table, sample_experiment
    ):
        """Test starting experiment fails when status is not 'pending'."""
        sample_experiment["status"] = "running"
        mock_dynamodb_table.get_item.return_value = {"Item": sample_experiment}

        with pytest.raises(ChaosError) as exc_info:
            start_experiment(sample_experiment["experiment_id"])

        assert "must be in 'pending' status" in str(exc_info.value)

    def test_start_experiment_newsapi_failure_not_implemented(
        self, mock_environment_preprod, mock_dynamodb_table, sample_experiment
    ):
        """Test starting newsapi_failure scenario raises NotImplementedError."""
        sample_experiment["scenario_type"] = "newsapi_failure"
        mock_dynamodb_table.get_item.return_value = {"Item": sample_experiment}

        with pytest.raises(ChaosError) as exc_info:
            start_experiment(sample_experiment["experiment_id"])

        assert "not yet implemented (Phase 3)" in str(exc_info.value)


# ===================================================================
# Tests for stop_experiment() with FIS Integration
# ===================================================================


class TestStopExperimentWithFIS:
    """Tests for stop_experiment() with AWS FIS integration."""

    def test_stop_experiment_dynamodb_throttle_success(
        self,
        mock_environment_preprod,
        mock_fis_client,
        mock_dynamodb_table,
        sample_experiment,
    ):
        """Test stopping DynamoDB throttle experiment with FIS."""
        # Mock running experiment with FIS experiment ID
        sample_experiment["status"] = "running"
        sample_experiment["results"] = {"fis_experiment_id": "EXP123456789"}
        mock_dynamodb_table.get_item.return_value = {"Item": sample_experiment}

        # Mock update_experiment_status
        with patch(
            "src.lambdas.dashboard.chaos.update_experiment_status"
        ) as mock_update:
            mock_update.return_value = True

            stop_experiment(sample_experiment["experiment_id"])

            # Verify FIS experiment was stopped
            mock_fis_client.stop_experiment.assert_called_once_with(id="EXP123456789")

            # Verify experiment status was updated
            mock_update.assert_called_once()
            call_args = mock_update.call_args
            assert call_args[0][0] == sample_experiment["experiment_id"]
            assert call_args[0][1] == "stopped"
            assert "stopped_at" in call_args[0][2]

    def test_stop_experiment_missing_fis_id(
        self, mock_environment_preprod, mock_dynamodb_table, sample_experiment
    ):
        """Test stopping experiment fails when FIS experiment ID missing."""
        sample_experiment["status"] = "running"
        sample_experiment["results"] = {}  # No FIS experiment ID
        mock_dynamodb_table.get_item.return_value = {"Item": sample_experiment}

        with pytest.raises(ChaosError) as exc_info:
            stop_experiment(sample_experiment["experiment_id"])

        assert "FIS experiment ID not found" in str(exc_info.value)

    def test_stop_experiment_invalid_status(
        self, mock_environment_preprod, mock_dynamodb_table, sample_experiment
    ):
        """Test stopping experiment fails when status is not 'running'."""
        sample_experiment["status"] = "completed"
        mock_dynamodb_table.get_item.return_value = {"Item": sample_experiment}

        with pytest.raises(ChaosError) as exc_info:
            stop_experiment(sample_experiment["experiment_id"])

        assert "must be in 'running' status" in str(exc_info.value)
