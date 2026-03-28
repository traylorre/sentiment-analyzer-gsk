"""
Integration Tests for Chaos Reports DynamoDB Operations (Feature 1240)
======================================================================

Tests cover:
- GSI queries (scenario filter, verdict filter)
- Cursor-based pagination with 25+ reports
- Date range filtering
- List ordering (newest first)
- Full CRUD round-trip

Uses moto for DynamoDB mocking (following project pattern).
"""

from datetime import UTC, datetime, timedelta

import boto3
import moto
import pytest

from src.lambdas.dashboard.chaos import (
    delete_report,
    get_report,
    list_reports,
    persist_report,
)


@pytest.fixture
def dynamodb_table(monkeypatch):
    """Create a real moto DynamoDB table for integration testing."""
    with moto.mock_aws():
        dynamodb = boto3.resource("dynamodb", region_name="us-east-1")
        table = dynamodb.create_table(
            TableName="test-chaos-reports",
            KeySchema=[{"AttributeName": "report_id", "KeyType": "HASH"}],
            AttributeDefinitions=[
                {"AttributeName": "report_id", "AttributeType": "S"},
                {"AttributeName": "scenario_type", "AttributeType": "S"},
                {"AttributeName": "verdict", "AttributeType": "S"},
                {"AttributeName": "created_at", "AttributeType": "S"},
            ],
            GlobalSecondaryIndexes=[
                {
                    "IndexName": "scenario-created-index",
                    "KeySchema": [
                        {"AttributeName": "scenario_type", "KeyType": "HASH"},
                        {"AttributeName": "created_at", "KeyType": "RANGE"},
                    ],
                    "Projection": {"ProjectionType": "ALL"},
                },
                {
                    "IndexName": "verdict-created-index",
                    "KeySchema": [
                        {"AttributeName": "verdict", "KeyType": "HASH"},
                        {"AttributeName": "created_at", "KeyType": "RANGE"},
                    ],
                    "Projection": {"ProjectionType": "ALL"},
                },
            ],
            BillingMode="PAY_PER_REQUEST",
        )
        table.meta.client.get_waiter("table_exists").wait(
            TableName="test-chaos-reports"
        )

        # Patch module-level config so chaos functions use the moto table
        import src.lambdas.dashboard.chaos as chaos_module

        monkeypatch.setattr(chaos_module, "CHAOS_REPORTS_TABLE", "test-chaos-reports")
        monkeypatch.setattr(chaos_module, "ENVIRONMENT", "test")

        # Patch the lazy-loaded _dynamodb global to use our moto resource
        monkeypatch.setattr(chaos_module, "_dynamodb", dynamodb)

        yield table


def _make_report(
    scenario_type="ingestion_failure", verdict="CLEAN", minutes_ago=0, **kwargs
):
    """Helper to create a report dict with required fields."""
    ts = (datetime.now(UTC) - timedelta(minutes=minutes_ago)).isoformat() + "Z"
    report = {
        "report_type": "experiment",
        "scenario_type": scenario_type,
        "verdict": verdict,
        "verdict_reason": f"Test {verdict}",
        "environment": "test",
        "created_at": ts,
        "duration_seconds": 120,
        "experiment_id": f"exp-{minutes_ago}",
    }
    report.update(kwargs)
    return report


class TestGSIQueries:
    """Test Global Secondary Index queries for filtering."""

    def test_filter_by_scenario_type(self, dynamodb_table):
        """scenario-created-index returns only matching scenario type."""
        persist_report(_make_report(scenario_type="ingestion_failure", report_id="r1"))
        persist_report(_make_report(scenario_type="dynamodb_throttle", report_id="r2"))
        persist_report(_make_report(scenario_type="ingestion_failure", report_id="r3"))

        result = list_reports(scenario_type="ingestion_failure")
        assert len(result["reports"]) == 2
        assert all(r["scenario_type"] == "ingestion_failure" for r in result["reports"])

    def test_filter_by_verdict(self, dynamodb_table):
        """verdict-created-index returns only matching verdict."""
        persist_report(_make_report(verdict="CLEAN", report_id="r1"))
        persist_report(_make_report(verdict="COMPROMISED", report_id="r2"))
        persist_report(_make_report(verdict="CLEAN", report_id="r3"))

        result = list_reports(verdict="CLEAN")
        assert len(result["reports"]) == 2
        assert all(r["verdict"] == "CLEAN" for r in result["reports"])

    def test_combined_filters_scan(self, dynamodb_table):
        """Combined scenario + verdict uses scan with filter."""
        persist_report(
            _make_report(
                scenario_type="ingestion_failure",
                verdict="CLEAN",
                report_id="r1",
            )
        )
        persist_report(
            _make_report(
                scenario_type="ingestion_failure",
                verdict="COMPROMISED",
                report_id="r2",
            )
        )
        persist_report(
            _make_report(
                scenario_type="dynamodb_throttle",
                verdict="CLEAN",
                report_id="r3",
            )
        )

        result = list_reports(scenario_type="ingestion_failure", verdict="CLEAN")
        assert len(result["reports"]) == 1
        assert result["reports"][0]["scenario_type"] == "ingestion_failure"
        assert result["reports"][0]["verdict"] == "CLEAN"

    def test_filter_by_report_type(self, dynamodb_table):
        """Report type filter returns only matching type."""
        persist_report(_make_report(report_type="experiment", report_id="r1"))
        persist_report(_make_report(report_type="plan", report_id="r2"))
        persist_report(_make_report(report_type="experiment", report_id="r3"))

        result = list_reports(report_type="experiment")
        assert len(result["reports"]) == 2
        assert all(r["report_type"] == "experiment" for r in result["reports"])


class TestDateRangeFiltering:
    """Test date range filters on list_reports."""

    def test_from_date_filter(self, dynamodb_table):
        """from_date excludes reports created before the cutoff."""
        persist_report(_make_report(report_id="old", minutes_ago=120))
        persist_report(_make_report(report_id="recent", minutes_ago=5))

        cutoff = (datetime.now(UTC) - timedelta(minutes=60)).isoformat() + "Z"
        result = list_reports(scenario_type="ingestion_failure", from_date=cutoff)
        assert len(result["reports"]) == 1
        assert result["reports"][0]["report_id"] == "recent"

    def test_to_date_filter(self, dynamodb_table):
        """to_date excludes reports created after the cutoff."""
        persist_report(_make_report(report_id="old", minutes_ago=120))
        persist_report(_make_report(report_id="recent", minutes_ago=5))

        cutoff = (datetime.now(UTC) - timedelta(minutes=60)).isoformat() + "Z"
        result = list_reports(scenario_type="ingestion_failure", to_date=cutoff)
        assert len(result["reports"]) == 1
        assert result["reports"][0]["report_id"] == "old"

    def test_date_range_filter(self, dynamodb_table):
        """Combined from_date + to_date narrows the window."""
        persist_report(_make_report(report_id="r1", minutes_ago=180))
        persist_report(_make_report(report_id="r2", minutes_ago=90))
        persist_report(_make_report(report_id="r3", minutes_ago=30))

        from_date = (datetime.now(UTC) - timedelta(minutes=120)).isoformat() + "Z"
        to_date = (datetime.now(UTC) - timedelta(minutes=60)).isoformat() + "Z"
        result = list_reports(
            scenario_type="ingestion_failure",
            from_date=from_date,
            to_date=to_date,
        )
        assert len(result["reports"]) == 1
        assert result["reports"][0]["report_id"] == "r2"


class TestPagination:
    """Test cursor-based pagination."""

    def test_cursor_pagination(self, dynamodb_table):
        """Pagination returns correct pages with cursor."""
        # Create 5 reports with distinct timestamps
        for i in range(5):
            persist_report(_make_report(report_id=f"r{i}", minutes_ago=i * 10))

        # First page
        page1 = list_reports(limit=2)
        assert len(page1["reports"]) == 2
        assert page1["next_cursor"] is not None

        # Second page
        page2 = list_reports(limit=2, cursor=page1["next_cursor"])
        assert len(page2["reports"]) == 2

        # Verify no duplicates across pages
        all_ids = [r["report_id"] for r in page1["reports"] + page2["reports"]]
        assert len(set(all_ids)) == 4  # 4 unique reports across 2 pages

    def test_last_page_has_no_cursor(self, dynamodb_table):
        """Last page returns None cursor."""
        persist_report(_make_report(report_id="r1"))
        persist_report(_make_report(report_id="r2"))

        result = list_reports(limit=10)
        assert len(result["reports"]) == 2
        assert result["next_cursor"] is None

    def test_limit_clamped(self, dynamodb_table):
        """Limit is clamped between 1 and 100."""
        for i in range(5):
            persist_report(_make_report(report_id=f"r{i}", minutes_ago=i))

        # Requesting limit=0 should be clamped to 1
        result = list_reports(limit=0)
        assert len(result["reports"]) <= 1


class TestOrdering:
    """Test report ordering."""

    def test_newest_first(self, dynamodb_table):
        """Reports are returned newest first."""
        persist_report(_make_report(report_id="old", minutes_ago=60))
        persist_report(_make_report(report_id="new", minutes_ago=0))
        persist_report(_make_report(report_id="mid", minutes_ago=30))

        result = list_reports()
        created_dates = [r["created_at"] for r in result["reports"]]
        assert created_dates == sorted(created_dates, reverse=True)

    def test_gsi_query_newest_first(self, dynamodb_table):
        """GSI query results are also newest first."""
        persist_report(
            _make_report(
                report_id="old",
                scenario_type="ingestion_failure",
                minutes_ago=60,
            )
        )
        persist_report(
            _make_report(
                report_id="new",
                scenario_type="ingestion_failure",
                minutes_ago=0,
            )
        )

        result = list_reports(scenario_type="ingestion_failure")
        assert result["reports"][0]["report_id"] == "new"
        assert result["reports"][1]["report_id"] == "old"


class TestCRUDIntegration:
    """Test full CRUD round-trip."""

    def test_persist_and_retrieve(self, dynamodb_table):
        """Full round-trip: persist -> get -> delete."""
        report_data = _make_report(report_id="roundtrip-1")
        persist_report(report_data)

        retrieved = get_report("roundtrip-1")
        assert retrieved is not None
        assert retrieved["report_id"] == "roundtrip-1"
        assert retrieved["scenario_type"] == "ingestion_failure"

        deleted = delete_report("roundtrip-1")
        assert deleted is True

        gone = get_report("roundtrip-1")
        assert gone is None

    def test_delete_nonexistent_returns_false(self, dynamodb_table):
        """Deleting a non-existent report returns False."""
        result = delete_report("does-not-exist")
        assert result is False

    def test_get_nonexistent_returns_none(self, dynamodb_table):
        """Getting a non-existent report returns None."""
        result = get_report("does-not-exist")
        assert result is None

    def test_persist_generates_report_id(self, dynamodb_table):
        """Persisting without report_id generates a ULID."""
        report_data = _make_report()
        # Remove report_id to test auto-generation
        report_data.pop("report_id", None)
        result = persist_report(report_data)
        assert "report_id" in result
        assert len(result["report_id"]) > 0

    def test_persist_sets_defaults(self, dynamodb_table):
        """Persisting sets default created_at and environment."""
        report_data = {
            "report_type": "experiment",
            "scenario_type": "ingestion_failure",
            "verdict": "CLEAN",
            "experiment_id": "exp-defaults",
        }
        result = persist_report(report_data)
        assert "created_at" in result
        assert result["environment"] == "test"

    def test_empty_table_returns_empty_list(self, dynamodb_table):
        """Listing with no reports returns empty list."""
        result = list_reports()
        assert result["reports"] == []
        assert result["next_cursor"] is None


class TestDecimalHandling:
    """Test that DynamoDB Decimal conversion works correctly."""

    def test_float_fields_roundtrip(self, dynamodb_table):
        """Float fields survive DynamoDB persist/retrieve cycle."""
        report_data = _make_report(report_id="decimal-test")
        persist_report(report_data)

        retrieved = get_report("decimal-test")
        assert retrieved is not None
        # duration_seconds should come back as int, not Decimal
        assert isinstance(retrieved["duration_seconds"], int)
        assert retrieved["duration_seconds"] == 120
