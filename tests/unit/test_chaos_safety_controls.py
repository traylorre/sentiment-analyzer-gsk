"""
Unit Tests for Chaos Safety Controls (Features 1244, 1245, 1246)
================================================================

Tests cover:
- Pre-flight health check endpoint (1244)
- Gate arm/disarm toggle endpoints (1245)
- Andon cord emergency stop endpoint (1246)
"""

from unittest.mock import MagicMock, patch

import pytest
from botocore.exceptions import ClientError

from src.lambdas.dashboard.chaos import (
    ChaosError,
    EnvironmentNotAllowedError,
    get_gate_state,
    get_system_health,
    pull_andon_cord,
    set_gate_state,
)


@pytest.fixture
def mock_environment_preprod(monkeypatch):
    """Set ENVIRONMENT to preprod for testing."""
    monkeypatch.setenv("ENVIRONMENT", "preprod")
    monkeypatch.setenv("CHAOS_EXPERIMENTS_TABLE", "preprod-chaos-experiments")
    import src.lambdas.dashboard.chaos as chaos_module

    monkeypatch.setattr(chaos_module, "ENVIRONMENT", "preprod")
    monkeypatch.setattr(chaos_module, "CHAOS_TABLE", "preprod-chaos-experiments")


@pytest.fixture
def mock_ssm_client():
    """Mock boto3 SSM client."""
    with patch("src.lambdas.dashboard.chaos._get_ssm_client") as mock_getter:
        mock_client = MagicMock()
        mock_client.exceptions.ParameterNotFound = type(
            "ParameterNotFound", (ClientError,), {}
        )
        mock_getter.return_value = mock_client
        yield mock_client


# ===================================================================
# Feature 1244: Pre-Flight Health Check
# ===================================================================


class TestGetSystemHealth:
    """Tests for get_system_health() — Feature 1244."""

    def test_returns_baseline(self, mock_environment_preprod):
        """get_system_health returns _capture_baseline result."""
        with patch("src.lambdas.dashboard.chaos._capture_baseline") as mock_baseline:
            mock_baseline.return_value = {
                "dependencies": {"dynamodb": {"status": "healthy"}},
                "all_healthy": True,
                "degraded_services": [],
            }
            result = get_system_health()
            assert result["all_healthy"] is True
            mock_baseline.assert_called_once_with("preprod")

    def test_passes_through_degraded_info(self, mock_environment_preprod):
        """get_system_health surfaces degraded dependencies from baseline."""
        with patch("src.lambdas.dashboard.chaos._capture_baseline") as mock_baseline:
            mock_baseline.return_value = {
                "dependencies": {
                    "dynamodb": {"status": "degraded", "error": "Table not found"},
                    "lambda": {"status": "healthy"},
                },
                "all_healthy": False,
                "degraded_services": ["dynamodb"],
            }
            result = get_system_health()
            assert result["all_healthy"] is False
            assert "dynamodb" in result["degraded_services"]

    def test_blocked_in_prod(self, monkeypatch):
        """get_system_health raises EnvironmentNotAllowedError in prod."""
        import src.lambdas.dashboard.chaos as chaos_module

        monkeypatch.setattr(chaos_module, "ENVIRONMENT", "prod")
        with pytest.raises(EnvironmentNotAllowedError):
            get_system_health()

    def test_blocked_in_staging(self, monkeypatch):
        """get_system_health raises EnvironmentNotAllowedError in staging."""
        import src.lambdas.dashboard.chaos as chaos_module

        monkeypatch.setattr(chaos_module, "ENVIRONMENT", "staging")
        with pytest.raises(EnvironmentNotAllowedError):
            get_system_health()

    def test_allowed_in_dev(self, monkeypatch):
        """get_system_health works in dev environment."""
        import src.lambdas.dashboard.chaos as chaos_module

        monkeypatch.setattr(chaos_module, "ENVIRONMENT", "dev")
        with patch("src.lambdas.dashboard.chaos._capture_baseline") as mock_baseline:
            mock_baseline.return_value = {
                "dependencies": {},
                "all_healthy": True,
                "degraded_services": [],
            }
            result = get_system_health()
            assert result["all_healthy"] is True
            mock_baseline.assert_called_once_with("dev")

    def test_baseline_exception_propagates(self, mock_environment_preprod):
        """Exceptions from _capture_baseline propagate to caller."""
        with patch("src.lambdas.dashboard.chaos._capture_baseline") as mock_baseline:
            mock_baseline.side_effect = ClientError(
                {"Error": {"Code": "InternalError", "Message": "service down"}},
                "DescribeTable",
            )
            with pytest.raises(ClientError):
                get_system_health()


# ===================================================================
# Feature 1245: Gate Toggle
# ===================================================================


class TestGetGateState:
    """Tests for get_gate_state() — Feature 1245."""

    def test_returns_armed(self, mock_environment_preprod, mock_ssm_client):
        """get_gate_state returns 'armed' when SSM says armed."""
        mock_ssm_client.get_parameter.return_value = {"Parameter": {"Value": "armed"}}
        assert get_gate_state() == "armed"

    def test_returns_disarmed(self, mock_environment_preprod, mock_ssm_client):
        """get_gate_state returns 'disarmed' when SSM says disarmed."""
        mock_ssm_client.get_parameter.return_value = {
            "Parameter": {"Value": "disarmed"}
        }
        assert get_gate_state() == "disarmed"

    def test_returns_triggered(self, mock_environment_preprod, mock_ssm_client):
        """get_gate_state returns 'triggered' (doesn't raise unlike _check_gate)."""
        mock_ssm_client.get_parameter.return_value = {
            "Parameter": {"Value": "triggered"}
        }
        assert get_gate_state() == "triggered"

    def test_parameter_not_found_returns_disarmed(
        self, mock_environment_preprod, mock_ssm_client
    ):
        """Missing SSM parameter defaults to disarmed."""
        mock_ssm_client.get_parameter.side_effect = (
            mock_ssm_client.exceptions.ParameterNotFound(
                {"Error": {"Code": "ParameterNotFound", "Message": "test"}},
                "GetParameter",
            )
        )
        assert get_gate_state() == "disarmed"

    def test_ssm_error_raises_chaos_error(
        self, mock_environment_preprod, mock_ssm_client
    ):
        """SSM errors other than ParameterNotFound raise ChaosError."""
        mock_ssm_client.get_parameter.side_effect = ClientError(
            {"Error": {"Code": "InternalError", "Message": "test"}},
            "GetParameter",
        )
        with pytest.raises(ChaosError, match="Cannot read gate state"):
            get_gate_state()

    def test_reads_correct_ssm_path(self, mock_environment_preprod, mock_ssm_client):
        """get_gate_state reads /chaos/{env}/kill-switch."""
        mock_ssm_client.get_parameter.return_value = {
            "Parameter": {"Value": "disarmed"}
        }
        get_gate_state()
        mock_ssm_client.get_parameter.assert_called_once_with(
            Name="/chaos/preprod/kill-switch"
        )

    def test_blocked_in_prod(self, monkeypatch):
        """get_gate_state raises EnvironmentNotAllowedError in prod."""
        import src.lambdas.dashboard.chaos as chaos_module

        monkeypatch.setattr(chaos_module, "ENVIRONMENT", "prod")
        with pytest.raises(EnvironmentNotAllowedError):
            get_gate_state()


class TestSetGateState:
    """Tests for set_gate_state() — Feature 1245."""

    def test_arm(self, mock_environment_preprod, mock_ssm_client):
        """set_gate_state arms the gate."""
        mock_ssm_client.get_parameter.return_value = {
            "Parameter": {"Value": "disarmed"}
        }
        result = set_gate_state("armed")
        assert result == {"state": "armed", "previous": "disarmed"}

    def test_disarm(self, mock_environment_preprod, mock_ssm_client):
        """set_gate_state disarms the gate."""
        mock_ssm_client.get_parameter.return_value = {"Parameter": {"Value": "armed"}}
        result = set_gate_state("disarmed")
        assert result == {"state": "disarmed", "previous": "armed"}

    def test_arm_writes_to_ssm(self, mock_environment_preprod, mock_ssm_client):
        """set_gate_state writes new state via _set_kill_switch → SSM put_parameter."""
        mock_ssm_client.get_parameter.return_value = {
            "Parameter": {"Value": "disarmed"}
        }
        set_gate_state("armed")
        mock_ssm_client.put_parameter.assert_called_once_with(
            Name="/chaos/preprod/kill-switch",
            Value="armed",
            Type="String",
            Overwrite=True,
        )

    def test_cannot_arm_when_triggered(self, mock_environment_preprod, mock_ssm_client):
        """Cannot arm gate when it's triggered."""
        mock_ssm_client.get_parameter.return_value = {
            "Parameter": {"Value": "triggered"}
        }
        with pytest.raises(ChaosError, match="Gate is triggered"):
            set_gate_state("armed")

    def test_can_disarm_when_triggered(self, mock_environment_preprod, mock_ssm_client):
        """Can disarm gate even when triggered (reset path)."""
        mock_ssm_client.get_parameter.return_value = {
            "Parameter": {"Value": "triggered"}
        }
        result = set_gate_state("disarmed")
        assert result["state"] == "disarmed"
        assert result["previous"] == "triggered"

    def test_invalid_state_triggered(self, mock_environment_preprod, mock_ssm_client):
        """Cannot set state to 'triggered' directly — only andon cord does that."""
        with pytest.raises(ValueError, match="Invalid gate state"):
            set_gate_state("triggered")

    def test_invalid_state_random_string(
        self, mock_environment_preprod, mock_ssm_client
    ):
        """Random string raises ValueError."""
        with pytest.raises(ValueError, match="Invalid gate state"):
            set_gate_state("foobar")

    def test_no_op_arm_when_already_armed(
        self, mock_environment_preprod, mock_ssm_client
    ):
        """Arming an already-armed gate still succeeds (idempotent)."""
        mock_ssm_client.get_parameter.return_value = {"Parameter": {"Value": "armed"}}
        result = set_gate_state("armed")
        assert result == {"state": "armed", "previous": "armed"}

    def test_no_op_disarm_when_already_disarmed(
        self, mock_environment_preprod, mock_ssm_client
    ):
        """Disarming an already-disarmed gate still succeeds (idempotent)."""
        mock_ssm_client.get_parameter.return_value = {
            "Parameter": {"Value": "disarmed"}
        }
        result = set_gate_state("disarmed")
        assert result == {"state": "disarmed", "previous": "disarmed"}

    def test_blocked_in_prod(self, monkeypatch):
        """set_gate_state raises EnvironmentNotAllowedError in prod."""
        import src.lambdas.dashboard.chaos as chaos_module

        monkeypatch.setattr(chaos_module, "ENVIRONMENT", "prod")
        with pytest.raises(EnvironmentNotAllowedError):
            set_gate_state("armed")


# ===================================================================
# Feature 1246: Andon Cord
# ===================================================================


class TestPullAndonCord:
    """Tests for pull_andon_cord() — Feature 1246."""

    def test_successful_pull_no_snapshots(
        self, mock_environment_preprod, mock_ssm_client
    ):
        """Andon cord with no active snapshots just sets kill switch then disarms."""
        mock_ssm_client.get_parameters_by_path.return_value = {"Parameters": []}
        result = pull_andon_cord()
        assert result["kill_switch_set"] is True
        assert result["experiments_found"] == 0
        assert result["restored"] == 0
        assert result["failed"] == 0
        assert result["errors"] == []

    def test_successful_pull_with_snapshots(
        self, mock_environment_preprod, mock_ssm_client
    ):
        """Andon cord restores all snapshots and disarms."""
        mock_ssm_client.get_parameters_by_path.return_value = {
            "Parameters": [
                {
                    "Name": "/chaos/preprod/snapshot/ingestion-failure",
                    "Value": "{}",
                },
                {
                    "Name": "/chaos/preprod/snapshot/dynamodb-throttle",
                    "Value": "{}",
                },
            ]
        }
        with patch("src.lambdas.dashboard.chaos._restore_from_ssm") as mock_restore:
            result = pull_andon_cord()
            assert result["kill_switch_set"] is True
            assert result["experiments_found"] == 2
            assert result["restored"] == 2
            assert result["failed"] == 0
            assert mock_restore.call_count == 2

    def test_restore_receives_correct_scenario_types(
        self, mock_environment_preprod, mock_ssm_client
    ):
        """_restore_from_ssm is called with dash-to-underscore converted names."""
        mock_ssm_client.get_parameters_by_path.return_value = {
            "Parameters": [
                {
                    "Name": "/chaos/preprod/snapshot/ingestion-failure",
                    "Value": "{}",
                },
            ]
        }
        with patch("src.lambdas.dashboard.chaos._restore_from_ssm") as mock_restore:
            pull_andon_cord()
            mock_restore.assert_called_once_with("ingestion_failure")

    def test_partial_restore_failure(self, mock_environment_preprod, mock_ssm_client):
        """Andon cord continues on individual restore failures (best-effort)."""
        mock_ssm_client.get_parameters_by_path.return_value = {
            "Parameters": [
                {
                    "Name": "/chaos/preprod/snapshot/ingestion-failure",
                    "Value": "{}",
                },
                {
                    "Name": "/chaos/preprod/snapshot/dynamodb-throttle",
                    "Value": "{}",
                },
            ]
        }
        with patch("src.lambdas.dashboard.chaos._restore_from_ssm") as mock_restore:
            mock_restore.side_effect = [None, Exception("Restore failed")]
            result = pull_andon_cord()
            assert result["restored"] == 1
            assert result["failed"] == 1
            assert len(result["errors"]) == 1
            assert "dynamodb_throttle" in result["errors"][0]

    def test_kill_switch_set_first(self, mock_environment_preprod, mock_ssm_client):
        """Kill switch is set to 'triggered' BEFORE any restore attempts."""
        mock_ssm_client.get_parameters_by_path.return_value = {"Parameters": []}
        pull_andon_cord()
        # First put_parameter call should be "triggered" (from _set_kill_switch)
        calls = mock_ssm_client.put_parameter.call_args_list
        assert len(calls) >= 1
        first_call_kwargs = calls[0][1]  # keyword args
        assert first_call_kwargs["Value"] == "triggered"
        assert first_call_kwargs["Name"] == "/chaos/preprod/kill-switch"

    def test_disarms_after_clean_restore(
        self, mock_environment_preprod, mock_ssm_client
    ):
        """Andon cord disarms after all restores succeed (zero failures)."""
        mock_ssm_client.get_parameters_by_path.return_value = {"Parameters": []}
        pull_andon_cord()
        # Should call put_parameter twice: triggered → disarmed
        calls = mock_ssm_client.put_parameter.call_args_list
        assert len(calls) == 2
        assert calls[0][1]["Value"] == "triggered"
        assert calls[1][1]["Value"] == "disarmed"

    def test_stays_triggered_on_partial_failure(
        self, mock_environment_preprod, mock_ssm_client
    ):
        """Andon cord stays triggered when any restore fails."""
        mock_ssm_client.get_parameters_by_path.return_value = {
            "Parameters": [
                {
                    "Name": "/chaos/preprod/snapshot/ingestion-failure",
                    "Value": "{}",
                },
            ]
        }
        with patch("src.lambdas.dashboard.chaos._restore_from_ssm") as mock_restore:
            mock_restore.side_effect = Exception("Failed")
            result = pull_andon_cord()
            assert result["failed"] == 1
            # Only "triggered" call, NO "disarmed" call
            values = [
                c[1]["Value"] for c in mock_ssm_client.put_parameter.call_args_list
            ]
            assert values == ["triggered"]
            assert "disarmed" not in values

    def test_idempotent_double_pull(self, mock_environment_preprod, mock_ssm_client):
        """Double-pulling andon cord is safe."""
        mock_ssm_client.get_parameters_by_path.return_value = {"Parameters": []}
        result1 = pull_andon_cord()
        result2 = pull_andon_cord()
        assert result1["kill_switch_set"] is True
        assert result2["kill_switch_set"] is True

    def test_snapshot_discovery_uses_correct_path(
        self, mock_environment_preprod, mock_ssm_client
    ):
        """Snapshot discovery queries /chaos/{env}/snapshot/ path."""
        mock_ssm_client.get_parameters_by_path.return_value = {"Parameters": []}
        pull_andon_cord()
        mock_ssm_client.get_parameters_by_path.assert_called_once_with(
            Path="/chaos/preprod/snapshot/",
            Recursive=False,
        )

    def test_snapshot_discovery_failure_returns_early(
        self, mock_environment_preprod, mock_ssm_client
    ):
        """If snapshot listing fails, return early with error."""
        mock_ssm_client.get_parameters_by_path.side_effect = ClientError(
            {"Error": {"Code": "InternalError", "Message": "SSM down"}},
            "GetParametersByPath",
        )
        result = pull_andon_cord()
        assert result["kill_switch_set"] is True  # kill switch still set
        assert len(result["errors"]) == 1
        assert "Cannot list snapshots" in result["errors"][0]
        assert result["experiments_found"] == 0

    def test_result_has_timestamp(self, mock_environment_preprod, mock_ssm_client):
        """Result includes ISO timestamp."""
        mock_ssm_client.get_parameters_by_path.return_value = {"Parameters": []}
        result = pull_andon_cord()
        assert "timestamp" in result
        assert "T" in result["timestamp"]  # ISO format

    def test_blocked_in_prod(self, monkeypatch):
        """pull_andon_cord raises EnvironmentNotAllowedError in prod."""
        import src.lambdas.dashboard.chaos as chaos_module

        monkeypatch.setattr(chaos_module, "ENVIRONMENT", "prod")
        with pytest.raises(EnvironmentNotAllowedError):
            pull_andon_cord()

    def test_all_restores_fail(self, mock_environment_preprod, mock_ssm_client):
        """When all restores fail, stays triggered and reports all failures."""
        mock_ssm_client.get_parameters_by_path.return_value = {
            "Parameters": [
                {
                    "Name": "/chaos/preprod/snapshot/ingestion-failure",
                    "Value": "{}",
                },
                {
                    "Name": "/chaos/preprod/snapshot/dynamodb-throttle",
                    "Value": "{}",
                },
            ]
        }
        with patch("src.lambdas.dashboard.chaos._restore_from_ssm") as mock_restore:
            mock_restore.side_effect = Exception("Failed")
            result = pull_andon_cord()
            assert result["experiments_found"] == 2
            assert result["restored"] == 0
            assert result["failed"] == 2
            assert len(result["errors"]) == 2
            # Should NOT disarm
            values = [
                c[1]["Value"] for c in mock_ssm_client.put_parameter.call_args_list
            ]
            assert "disarmed" not in values
