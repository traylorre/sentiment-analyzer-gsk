"""
Unit Tests for Chaos Reports (Feature 1240)
============================================

Tests cover:
- Verdict IntEnum ordering and aggregation (T-023)
- Report persistence with ULID generation (T-024)
- Plan report aggregation with worst-case verdicts (T-025)
- Baseline comparison logic (T-026)
"""

from decimal import Decimal
from unittest.mock import MagicMock, patch

import pytest
from botocore.exceptions import ClientError

from src.lambdas.dashboard.chaos import (
    ChaosError,
    Report,
    Verdict,
    _from_dynamodb_item,
    _to_dynamodb_item,
    compare_reports,
    delete_report,
    generate_plan_report,
    get_report,
    get_trends,
    persist_report,
)

# ===================================================================
# Fixtures
# ===================================================================


@pytest.fixture
def mock_environment(monkeypatch):
    """Set up test environment variables."""
    monkeypatch.setenv("ENVIRONMENT", "preprod")
    monkeypatch.setenv("CHAOS_REPORTS_TABLE", "preprod-chaos-reports")
    import src.lambdas.dashboard.chaos as chaos_module

    monkeypatch.setattr(chaos_module, "ENVIRONMENT", "preprod")
    monkeypatch.setattr(chaos_module, "CHAOS_REPORTS_TABLE", "preprod-chaos-reports")


@pytest.fixture
def mock_reports_table():
    """Mock DynamoDB table for reports."""
    with patch("src.lambdas.dashboard.chaos._get_dynamodb") as mock_dynamodb_getter:
        mock_dynamodb = MagicMock()
        mock_table = MagicMock()
        mock_dynamodb.Table.return_value = mock_table
        mock_dynamodb_getter.return_value = mock_dynamodb
        yield mock_table


@pytest.fixture
def sample_report():
    """A valid experiment report dict."""
    return {
        "experiment_id": "12345678-1234-1234-1234-123456789012",
        "report_type": "experiment",
        "scenario_type": "ingestion_failure",
        "verdict": "CLEAN",
        "verdict_reason": "System recovered to healthy state after chaos",
        "environment": "preprod",
        "created_at": "2026-03-27T10:00:00Z",
        "started_at": "2026-03-27T09:55:00Z",
        "stopped_at": "2026-03-27T10:00:00Z",
        "duration_seconds": 120,
        "dry_run": False,
        "blast_radius": 25,
        "baseline": {"all_healthy": True, "degraded_services": []},
        "post_chaos": {"all_healthy": True, "new_issues": [], "persistent_issues": []},
        "recovery_observed": True,
        "recovery_time_seconds": 0,
    }


# ===================================================================
# T-023: Verdict IntEnum ordering and aggregation
# ===================================================================


class TestVerdict:
    def test_ordering(self):
        """Verdicts are ordered by severity."""
        assert Verdict.CLEAN < Verdict.DRY_RUN_CLEAN
        assert Verdict.DRY_RUN_CLEAN < Verdict.INCONCLUSIVE
        assert Verdict.INCONCLUSIVE < Verdict.RECOVERY_INCOMPLETE
        assert Verdict.RECOVERY_INCOMPLETE < Verdict.COMPROMISED

    def test_worst_case_aggregation_clean(self):
        """max() returns worst verdict -- all CLEAN stays CLEAN."""
        verdicts = [Verdict.CLEAN, Verdict.CLEAN]
        assert max(verdicts) == Verdict.CLEAN

    def test_worst_case_aggregation_mixed(self):
        """max() returns RECOVERY_INCOMPLETE when mixed with CLEAN."""
        verdicts = [Verdict.CLEAN, Verdict.RECOVERY_INCOMPLETE]
        assert max(verdicts) == Verdict.RECOVERY_INCOMPLETE

    def test_worst_case_aggregation_compromised(self):
        """COMPROMISED always wins."""
        verdicts = [Verdict.CLEAN, Verdict.DRY_RUN_CLEAN, Verdict.COMPROMISED]
        assert max(verdicts) == Verdict.COMPROMISED

    def test_worst_case_all_verdicts(self):
        """max() of all verdicts is COMPROMISED."""
        all_verdicts = list(Verdict)
        assert max(all_verdicts) == Verdict.COMPROMISED

    def test_verdict_by_name(self):
        """Can look up verdict by string name."""
        assert Verdict["CLEAN"] == Verdict.CLEAN
        assert Verdict["COMPROMISED"] == Verdict.COMPROMISED

    def test_verdict_name_property(self):
        """Verdict .name returns string representation."""
        assert Verdict.CLEAN.name == "CLEAN"
        assert Verdict.COMPROMISED.name == "COMPROMISED"

    def test_verdict_int_values(self):
        """Verdict values are sequential integers from 0."""
        assert Verdict.CLEAN == 0
        assert Verdict.DRY_RUN_CLEAN == 1
        assert Verdict.INCONCLUSIVE == 2
        assert Verdict.RECOVERY_INCOMPLETE == 3
        assert Verdict.COMPROMISED == 4


# ===================================================================
# T-024: Report persistence
# ===================================================================


class TestPersistReport:
    def test_persist_generates_ulid(
        self, mock_environment, mock_reports_table, sample_report
    ):
        """persist_report generates a ULID if no report_id provided."""
        mock_ulid_module = MagicMock()
        mock_ulid_module.new.return_value = "01HV1234567890ABCDEFGHJK"
        with patch.dict("sys.modules", {"ulid": mock_ulid_module}):
            result = persist_report(sample_report)
            assert result["report_id"] == "01HV1234567890ABCDEFGHJK"
            mock_ulid_module.new.assert_called_once()

    def test_persist_uses_existing_report_id(
        self, mock_environment, mock_reports_table, sample_report
    ):
        """persist_report keeps existing report_id when provided."""
        sample_report["report_id"] = "my-custom-id"
        mock_ulid = MagicMock()
        with patch.dict("sys.modules", {"ulid": mock_ulid}):
            result = persist_report(sample_report)
            assert result["report_id"] == "my-custom-id"
            mock_ulid.new.assert_not_called()

    def test_persist_calls_put_item(
        self, mock_environment, mock_reports_table, sample_report
    ):
        """persist_report writes to DynamoDB."""
        sample_report["report_id"] = "test-report-id"
        mock_ulid = MagicMock()
        with patch.dict("sys.modules", {"ulid": mock_ulid}):
            result = persist_report(sample_report)
            mock_reports_table.put_item.assert_called_once()
            assert result["report_id"] == "test-report-id"

    def test_persist_no_ttl(self, mock_environment, mock_reports_table, sample_report):
        """Persisted reports have no TTL attribute."""
        sample_report["report_id"] = "test-report-id"
        mock_ulid = MagicMock()
        with patch.dict("sys.modules", {"ulid": mock_ulid}):
            persist_report(sample_report)
            call_kwargs = mock_reports_table.put_item.call_args
            item = call_kwargs.kwargs["Item"]
            assert "ttl_timestamp" not in item

    def test_persist_survives_dynamodb_failure(
        self, mock_environment, mock_reports_table, sample_report
    ):
        """persist_report returns data even if DynamoDB write fails."""
        mock_reports_table.put_item.side_effect = ClientError(
            {"Error": {"Code": "InternalServerError", "Message": "test"}},
            "PutItem",
        )
        sample_report["report_id"] = "test-report-id"
        mock_ulid = MagicMock()
        with patch.dict("sys.modules", {"ulid": mock_ulid}):
            result = persist_report(sample_report)
            assert result["report_id"] == "test-report-id"

    def test_persist_skips_when_table_not_configured(self, monkeypatch, sample_report):
        """persist_report returns data without writing when table is empty."""
        import src.lambdas.dashboard.chaos as chaos_module

        monkeypatch.setattr(chaos_module, "CHAOS_REPORTS_TABLE", "")
        result = persist_report(sample_report)
        assert result == sample_report

    def test_persist_sets_default_fields(self, mock_environment, mock_reports_table):
        """persist_report sets defaults for created_at, environment, report_type."""
        report_data = {
            "report_id": "test-id",
            "scenario_type": "ingestion_failure",
            "verdict": "CLEAN",
        }
        mock_ulid = MagicMock()
        with patch.dict("sys.modules", {"ulid": mock_ulid}):
            result = persist_report(report_data)
            assert "created_at" in result
            assert result["environment"] == "preprod"
            assert result["report_type"] == "experiment"


class TestGetReport:
    def test_get_existing_report(self, mock_environment, mock_reports_table):
        """get_report returns report when found."""
        mock_reports_table.get_item.return_value = {
            "Item": {
                "report_id": "test-id",
                "scenario_type": "ingestion_failure",
                "verdict": "CLEAN",
                "duration_seconds": Decimal("120"),
            }
        }
        result = get_report("test-id")
        assert result is not None
        assert result["report_id"] == "test-id"
        # Verify Decimal was converted back
        assert result["duration_seconds"] == 120
        assert isinstance(result["duration_seconds"], int)

    def test_get_nonexistent_report(self, mock_environment, mock_reports_table):
        """get_report returns None when not found."""
        mock_reports_table.get_item.return_value = {}
        result = get_report("nonexistent")
        assert result is None

    def test_get_report_no_table_configured(self, monkeypatch):
        """get_report returns None when CHAOS_REPORTS_TABLE is empty."""
        import src.lambdas.dashboard.chaos as chaos_module

        monkeypatch.setattr(chaos_module, "CHAOS_REPORTS_TABLE", "")
        result = get_report("any-id")
        assert result is None

    def test_get_report_dynamodb_error(self, mock_environment, mock_reports_table):
        """get_report returns None on DynamoDB error."""
        mock_reports_table.get_item.side_effect = ClientError(
            {"Error": {"Code": "InternalServerError", "Message": "test"}},
            "GetItem",
        )
        result = get_report("test-id")
        assert result is None


class TestDeleteReport:
    def test_delete_existing_report(self, mock_environment, mock_reports_table):
        """delete_report returns True for existing report."""
        mock_reports_table.delete_item.return_value = {
            "Attributes": {"report_id": "test-id"}
        }
        assert delete_report("test-id") is True

    def test_delete_nonexistent_report(self, mock_environment, mock_reports_table):
        """delete_report returns False when report doesn't exist."""
        mock_reports_table.delete_item.return_value = {}
        assert delete_report("nonexistent") is False

    def test_delete_no_table_configured(self, monkeypatch):
        """delete_report returns False when CHAOS_REPORTS_TABLE is empty."""
        import src.lambdas.dashboard.chaos as chaos_module

        monkeypatch.setattr(chaos_module, "CHAOS_REPORTS_TABLE", "")
        assert delete_report("any-id") is False

    def test_delete_dynamodb_error(self, mock_environment, mock_reports_table):
        """delete_report returns False on DynamoDB error."""
        mock_reports_table.delete_item.side_effect = ClientError(
            {"Error": {"Code": "InternalServerError", "Message": "test"}},
            "DeleteItem",
        )
        assert delete_report("test-id") is False


# ===================================================================
# DynamoDB conversion helpers
# ===================================================================


class TestDynamoDBConversion:
    def test_to_dynamodb_removes_none(self):
        """None values are stripped from DynamoDB items."""
        data = {"a": 1, "b": None, "c": "hello"}
        result = _to_dynamodb_item(data)
        assert "b" not in result
        assert result["a"] == 1
        assert result["c"] == "hello"

    def test_to_dynamodb_converts_float(self):
        """Floats are converted to Decimal."""
        data = {"value": 3.14}
        result = _to_dynamodb_item(data)
        assert isinstance(result["value"], Decimal)
        assert result["value"] == Decimal("3.14")

    def test_to_dynamodb_handles_nested_dict(self):
        """Nested dicts are recursively converted."""
        data = {"outer": {"inner_float": 1.5, "inner_none": None}}
        result = _to_dynamodb_item(data)
        assert "inner_none" not in result["outer"]
        assert isinstance(result["outer"]["inner_float"], Decimal)

    def test_to_dynamodb_handles_list(self):
        """Lists with dicts are recursively converted."""
        data = {"items": [{"val": 1.5}, {"val": None, "name": "test"}]}
        result = _to_dynamodb_item(data)
        assert isinstance(result["items"][0]["val"], Decimal)
        assert "val" not in result["items"][1]  # None stripped
        assert result["items"][1]["name"] == "test"

    def test_from_dynamodb_converts_decimal_to_int(self):
        """Whole-number Decimals are converted to int."""
        data = {"count": Decimal("42")}
        result = _from_dynamodb_item(data)
        assert result["count"] == 42
        assert isinstance(result["count"], int)

    def test_from_dynamodb_converts_decimal_to_float(self):
        """Non-whole Decimals are converted to float."""
        data = {"ratio": Decimal("3.14")}
        result = _from_dynamodb_item(data)
        assert result["ratio"] == 3.14
        assert isinstance(result["ratio"], float)

    def test_from_dynamodb_handles_nested_dict(self):
        """Nested dicts are recursively converted."""
        data = {"outer": {"count": Decimal("10"), "name": "test"}}
        result = _from_dynamodb_item(data)
        assert result["outer"]["count"] == 10
        assert isinstance(result["outer"]["count"], int)

    def test_from_dynamodb_handles_list_with_decimals(self):
        """Lists containing Decimals are converted."""
        data = {"items": [Decimal("1"), Decimal("2.5")]}
        result = _from_dynamodb_item(data)
        assert result["items"][0] == 1
        assert isinstance(result["items"][0], int)
        assert result["items"][1] == 2.5
        assert isinstance(result["items"][1], float)

    def test_round_trip_preserves_data(self):
        """to_dynamodb -> from_dynamodb round-trip preserves values."""
        original = {"count": 42, "ratio": 3.14, "name": "test"}
        dynamo_item = _to_dynamodb_item(original)
        restored = _from_dynamodb_item(dynamo_item)
        # int stays int (no float conversion for ints)
        assert restored["count"] == 42
        assert restored["ratio"] == 3.14
        assert restored["name"] == "test"


# ===================================================================
# T-025: Plan report aggregation
# ===================================================================


class TestPlanReport:
    def test_all_clean_verdicts(self, mock_environment, mock_reports_table):
        """Plan with all CLEAN scenarios gives CLEAN overall."""
        # list_reports returns empty (no persisted reports for these experiment_ids)
        mock_reports_table.scan.return_value = {"Items": []}
        with patch("src.lambdas.dashboard.chaos.get_experiment_report") as mock_get_exp:
            mock_get_exp.side_effect = [
                {
                    "experiment_id": "exp-1",
                    "scenario_type": "ingestion_failure",
                    "verdict": "CLEAN",
                    "verdict_reason": "Clean",
                    "duration_seconds": 120,
                    "status": "stopped",
                },
                {
                    "experiment_id": "exp-2",
                    "scenario_type": "dynamodb_throttle",
                    "verdict": "CLEAN",
                    "verdict_reason": "Clean",
                    "duration_seconds": 120,
                    "status": "stopped",
                },
            ]
            mock_ulid = MagicMock()
            mock_ulid.new.return_value = "plan-report-id"
            with patch.dict("sys.modules", {"ulid": mock_ulid}):
                result = generate_plan_report(
                    "ingestion-resilience", ["exp-1", "exp-2"]
                )
                assert result["verdict"] == "CLEAN"
                assert result["report_type"] == "plan"
                assert len(result["scenario_reports"]) == 2

    def test_mixed_verdicts_worst_case(self, mock_environment, mock_reports_table):
        """Plan with mixed verdicts uses worst-case aggregation."""
        mock_reports_table.scan.return_value = {"Items": []}
        with patch("src.lambdas.dashboard.chaos.get_experiment_report") as mock_get_exp:
            mock_get_exp.side_effect = [
                {
                    "experiment_id": "exp-1",
                    "scenario_type": "ingestion_failure",
                    "verdict": "CLEAN",
                    "duration_seconds": 120,
                    "status": "stopped",
                },
                {
                    "experiment_id": "exp-2",
                    "scenario_type": "dynamodb_throttle",
                    "verdict": "RECOVERY_INCOMPLETE",
                    "duration_seconds": 120,
                    "status": "stopped",
                },
            ]
            mock_ulid = MagicMock()
            mock_ulid.new.return_value = "plan-report-id"
            with patch.dict("sys.modules", {"ulid": mock_ulid}):
                result = generate_plan_report("test-plan", ["exp-1", "exp-2"])
                assert result["verdict"] == "RECOVERY_INCOMPLETE"

    def test_no_experiments_raises(self, mock_environment, mock_reports_table):
        """Plan with no experiment IDs raises ChaosError."""
        with pytest.raises(ChaosError, match="No experiment reports found"):
            generate_plan_report("test-plan", [])

    def test_all_experiments_failed_gives_inconclusive(
        self, mock_environment, mock_reports_table
    ):
        """Plan where all experiments fail to load gives INCONCLUSIVE."""
        mock_reports_table.scan.return_value = {"Items": []}
        with patch("src.lambdas.dashboard.chaos.get_experiment_report") as mock_get_exp:
            mock_get_exp.side_effect = ChaosError("Not found")
            mock_ulid = MagicMock()
            mock_ulid.new.return_value = "plan-report-id"
            with patch.dict("sys.modules", {"ulid": mock_ulid}):
                result = generate_plan_report("test-plan", ["exp-1"])
                assert result["verdict"] == "INCONCLUSIVE"

    def test_plan_aggregates_duration(self, mock_environment, mock_reports_table):
        """Plan report sums duration from all scenarios."""
        mock_reports_table.scan.return_value = {"Items": []}
        with patch("src.lambdas.dashboard.chaos.get_experiment_report") as mock_get_exp:
            mock_get_exp.side_effect = [
                {
                    "experiment_id": "exp-1",
                    "scenario_type": "ingestion_failure",
                    "verdict": "CLEAN",
                    "duration_seconds": 60,
                    "status": "stopped",
                },
                {
                    "experiment_id": "exp-2",
                    "scenario_type": "dynamodb_throttle",
                    "verdict": "CLEAN",
                    "duration_seconds": 90,
                    "status": "stopped",
                },
            ]
            mock_ulid = MagicMock()
            mock_ulid.new.return_value = "plan-report-id"
            with patch.dict("sys.modules", {"ulid": mock_ulid}):
                result = generate_plan_report("test-plan", ["exp-1", "exp-2"])
                assert result["duration_seconds"] == 150


# ===================================================================
# T-026: Comparison logic
# ===================================================================


class TestCompareReports:
    def test_verdict_improved(self, mock_environment, mock_reports_table):
        """Detect verdict improvement between reports."""
        with patch("src.lambdas.dashboard.chaos.get_report") as mock_get:
            mock_get.side_effect = [
                {  # current
                    "report_id": "new",
                    "scenario_type": "ingestion_failure",
                    "verdict": "CLEAN",
                    "post_chaos": {"new_issues": [], "all_healthy": True},
                },
                {  # baseline
                    "report_id": "old",
                    "scenario_type": "ingestion_failure",
                    "verdict": "RECOVERY_INCOMPLETE",
                    "post_chaos": {
                        "new_issues": ["dynamodb"],
                        "all_healthy": False,
                    },
                },
            ]
            result = compare_reports("new", "old")
            assert result["verdict_change"]["direction"] == "improved"

    def test_verdict_regressed(self, mock_environment, mock_reports_table):
        """Detect verdict regression between reports."""
        with patch("src.lambdas.dashboard.chaos.get_report") as mock_get:
            mock_get.side_effect = [
                {
                    "report_id": "new",
                    "scenario_type": "ingestion_failure",
                    "verdict": "COMPROMISED",
                    "post_chaos": {
                        "new_issues": ["dynamodb"],
                        "all_healthy": False,
                    },
                },
                {
                    "report_id": "old",
                    "scenario_type": "ingestion_failure",
                    "verdict": "CLEAN",
                    "post_chaos": {"new_issues": [], "all_healthy": True},
                },
            ]
            result = compare_reports("new", "old")
            assert result["verdict_change"]["direction"] == "regressed"

    def test_verdict_unchanged(self, mock_environment, mock_reports_table):
        """Detect unchanged verdict between reports."""
        with patch("src.lambdas.dashboard.chaos.get_report") as mock_get:
            mock_get.side_effect = [
                {
                    "report_id": "new",
                    "scenario_type": "ingestion_failure",
                    "verdict": "CLEAN",
                    "post_chaos": {"new_issues": [], "all_healthy": True},
                },
                {
                    "report_id": "old",
                    "scenario_type": "ingestion_failure",
                    "verdict": "CLEAN",
                    "post_chaos": {"new_issues": [], "all_healthy": True},
                },
            ]
            result = compare_reports("new", "old")
            assert result["verdict_change"]["direction"] == "unchanged"

    def test_first_baseline(self, mock_environment, mock_reports_table):
        """First report returns is_first_baseline with no comparison."""
        with (
            patch("src.lambdas.dashboard.chaos.get_report") as mock_get,
            patch("src.lambdas.dashboard.chaos.list_reports") as mock_list,
        ):
            mock_get.return_value = {
                "report_id": "first",
                "scenario_type": "ingestion_failure",
                "verdict": "CLEAN",
            }
            mock_list.return_value = {
                "reports": [{"report_id": "first"}],
                "next_cursor": None,
            }
            result = compare_reports("first")
            assert result["is_first_baseline"] is True

    def test_auto_baseline_picks_previous(self, mock_environment, mock_reports_table):
        """When no baseline_id given, auto-selects previous report."""
        with (
            patch("src.lambdas.dashboard.chaos.get_report") as mock_get,
            patch("src.lambdas.dashboard.chaos.list_reports") as mock_list,
        ):
            mock_get.return_value = {
                "report_id": "current",
                "scenario_type": "ingestion_failure",
                "verdict": "CLEAN",
                "post_chaos": {"new_issues": [], "all_healthy": True},
            }
            mock_list.return_value = {
                "reports": [
                    {"report_id": "current"},
                    {
                        "report_id": "previous",
                        "scenario_type": "ingestion_failure",
                        "verdict": "RECOVERY_INCOMPLETE",
                        "post_chaos": {
                            "new_issues": ["dynamodb"],
                            "all_healthy": False,
                        },
                    },
                ],
                "next_cursor": None,
            }
            result = compare_reports("current")
            assert result["is_first_baseline"] is False
            assert result["verdict_change"]["direction"] == "improved"

    def test_different_scenarios_rejected(self, mock_environment, mock_reports_table):
        """Cannot compare reports from different scenario types."""
        with patch("src.lambdas.dashboard.chaos.get_report") as mock_get:
            mock_get.side_effect = [
                {
                    "report_id": "a",
                    "scenario_type": "ingestion_failure",
                    "verdict": "CLEAN",
                },
                {
                    "report_id": "b",
                    "scenario_type": "dynamodb_throttle",
                    "verdict": "CLEAN",
                },
            ]
            with pytest.raises(ChaosError, match="Cannot compare different scenarios"):
                compare_reports("a", "b")

    def test_report_not_found(self, mock_environment, mock_reports_table):
        """Raises ChaosError when report not found."""
        with patch("src.lambdas.dashboard.chaos.get_report") as mock_get:
            mock_get.return_value = None
            with pytest.raises(ChaosError, match="Report not found"):
                compare_reports("nonexistent")

    def test_baseline_not_found(self, mock_environment, mock_reports_table):
        """Raises ChaosError when baseline report not found."""
        with patch("src.lambdas.dashboard.chaos.get_report") as mock_get:
            mock_get.side_effect = [
                {
                    "report_id": "current",
                    "scenario_type": "ingestion_failure",
                    "verdict": "CLEAN",
                },
                None,  # baseline not found
            ]
            with pytest.raises(ChaosError, match="Baseline report not found"):
                compare_reports("current", "missing-baseline")

    def test_health_changes_tracked(self, mock_environment, mock_reports_table):
        """Comparison tracks per-dependency health changes."""
        with patch("src.lambdas.dashboard.chaos.get_report") as mock_get:
            mock_get.side_effect = [
                {
                    "report_id": "new",
                    "scenario_type": "ingestion_failure",
                    "verdict": "CLEAN",
                    "post_chaos": {"new_issues": [], "all_healthy": True},
                },
                {
                    "report_id": "old",
                    "scenario_type": "ingestion_failure",
                    "verdict": "RECOVERY_INCOMPLETE",
                    "post_chaos": {
                        "new_issues": ["dynamodb"],
                        "all_healthy": False,
                    },
                },
            ]
            result = compare_reports("new", "old")
            assert "health_changes" in result
            dynamo_change = next(
                c for c in result["health_changes"] if c["dependency"] == "dynamodb"
            )
            assert dynamo_change["direction"] == "improved"
            assert dynamo_change["current_healthy"] is True
            assert dynamo_change["baseline_healthy"] is False


# ===================================================================
# Trends
# ===================================================================


class TestGetTrends:
    def test_returns_chronological_order(self, mock_environment, mock_reports_table):
        """get_trends returns data in chronological order (oldest first)."""
        with patch("src.lambdas.dashboard.chaos.list_reports") as mock_list:
            mock_list.return_value = {
                "reports": [
                    {
                        "report_id": "newer",
                        "created_at": "2026-03-27T10:00:00Z",
                        "verdict": "CLEAN",
                        "recovery_observed": True,
                        "recovery_time_seconds": 5,
                    },
                    {
                        "report_id": "older",
                        "created_at": "2026-03-26T10:00:00Z",
                        "verdict": "RECOVERY_INCOMPLETE",
                        "recovery_observed": False,
                        "recovery_time_seconds": None,
                    },
                ],
                "next_cursor": None,
            }
            result = get_trends("ingestion_failure")
            assert len(result) == 2
            # Reversed to chronological: older first
            assert result[0]["report_id"] == "older"
            assert result[1]["report_id"] == "newer"

    def test_empty_trends(self, mock_environment, mock_reports_table):
        """get_trends returns empty list when no reports exist."""
        with patch("src.lambdas.dashboard.chaos.list_reports") as mock_list:
            mock_list.return_value = {
                "reports": [],
                "next_cursor": None,
            }
            result = get_trends("ingestion_failure")
            assert result == []


# ===================================================================
# Report pydantic model validation
# ===================================================================


class TestReportModel:
    def test_valid_experiment_report(self, sample_report):
        """Valid experiment report passes validation."""
        sample_report["report_id"] = "test-id"
        report = Report(**sample_report)
        assert report.report_type == "experiment"
        assert report.verdict == "CLEAN"
        assert report.experiment_id == sample_report["experiment_id"]

    def test_valid_plan_report(self):
        """Valid plan report passes validation."""
        report = Report(
            report_id="plan-id",
            report_type="plan",
            scenario_type="ingestion-resilience",
            verdict="CLEAN",
            environment="preprod",
            created_at="2026-03-27T10:00:00Z",
            plan_name="ingestion-resilience",
        )
        assert report.report_type == "plan"
        assert report.plan_name == "ingestion-resilience"

    def test_invalid_report_type(self):
        """Invalid report_type rejected by pydantic."""
        with pytest.raises(ValueError):  # pydantic ValidationError inherits ValueError
            Report(
                report_id="bad",
                report_type="invalid",
                scenario_type="test",
                verdict="CLEAN",
                environment="preprod",
                created_at="2026-03-27T10:00:00Z",
            )

    def test_optional_fields_default(self):
        """Optional fields have correct defaults."""
        report = Report(
            report_id="test-id",
            report_type="experiment",
            scenario_type="ingestion_failure",
            verdict="CLEAN",
            environment="preprod",
            created_at="2026-03-27T10:00:00Z",
        )
        assert report.experiment_id is None
        assert report.duration_seconds == 0
        assert report.dry_run is False
        assert report.blast_radius is None
        assert report.baseline == {}
        assert report.post_chaos == {}
        assert report.recovery_observed is None
        assert report.recovery_time_seconds is None
        assert report.plan_name is None
        assert report.scenario_reports == []
        assert report.assertion_results == []

    def test_model_dump(self, sample_report):
        """Report.model_dump() returns serializable dict."""
        sample_report["report_id"] = "test-id"
        report = Report(**sample_report)
        dumped = report.model_dump()
        assert isinstance(dumped, dict)
        assert dumped["report_id"] == "test-id"
        assert dumped["verdict"] == "CLEAN"
