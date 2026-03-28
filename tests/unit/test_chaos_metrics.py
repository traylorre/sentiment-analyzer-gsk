"""
Unit Tests for Chaos Metrics Panel (Feature 1247)
==================================================

Tests cover:
- Metric configuration correctness (T-014)
- Environment substitution (T-015)
- get_metrics() response structure (T-010)
- AccessDeniedException handling (T-011)
- Throttling handling (T-012)
- Empty results handling (T-013)
"""

from datetime import UTC, datetime, timedelta
from unittest.mock import MagicMock, patch

import pytest
from botocore.exceptions import ClientError


@pytest.fixture
def mock_environment(monkeypatch):
    """Set up test environment."""
    monkeypatch.setenv("ENVIRONMENT", "preprod")
    import src.lambdas.dashboard.chaos as chaos_module

    monkeypatch.setattr(chaos_module, "ENVIRONMENT", "preprod")


# ===================================================================
# T-014: Metric configuration correctness
# ===================================================================


class TestMetricConfig:
    def test_four_groups_exist(self):
        """METRIC_GROUPS has exactly 4 groups."""
        from src.lambdas.dashboard.metrics_config import METRIC_GROUPS

        assert len(METRIC_GROUPS) == 4

    def test_each_group_has_required_fields(self):
        """Each group has title and queries."""
        from src.lambdas.dashboard.metrics_config import METRIC_GROUPS

        for group in METRIC_GROUPS:
            assert "title" in group
            assert "queries" in group
            assert len(group["queries"]) > 0

    def test_each_query_has_required_fields(self):
        """Each query has namespace, metric_name, dimensions, stat, label, color."""
        from src.lambdas.dashboard.metrics_config import METRIC_GROUPS

        required = {"namespace", "metric_name", "dimensions", "stat", "label", "color"}
        for group in METRIC_GROUPS:
            for query in group["queries"]:
                assert required.issubset(query.keys()), f"Missing keys in {query}"

    def test_valid_stat_values(self):
        """All stat values are valid CloudWatch statistics."""
        from src.lambdas.dashboard.metrics_config import METRIC_GROUPS

        valid_stats = {
            "Sum",
            "Average",
            "Minimum",
            "Maximum",
            "SampleCount",
            "p95",
            "p99",
        }
        for group in METRIC_GROUPS:
            for query in group["queries"]:
                assert query["stat"] in valid_stats, f"Invalid stat: {query['stat']}"

    def test_environment_templates_present(self):
        """Lambda and DynamoDB groups use {environment} template."""
        from src.lambdas.dashboard.metrics_config import METRIC_GROUPS

        has_template = False
        for group in METRIC_GROUPS:
            for query in group["queries"]:
                for dim_value in query["dimensions"].values():
                    if "{environment}" in dim_value:
                        has_template = True
        assert has_template, "No {environment} templates found in dimensions"


# ===================================================================
# T-015: Environment substitution
# ===================================================================


class TestEnvironmentSubstitution:
    def test_substitution(self, mock_environment):
        """Environment template is replaced correctly."""
        from src.lambdas.dashboard.metrics_config import METRIC_GROUPS

        group = METRIC_GROUPS[0]  # Lambda group
        query = group["queries"][0]
        dim_value = query["dimensions"]["FunctionName"]
        result = dim_value.replace("{environment}", "preprod")
        assert result == "preprod-sentiment-ingestion"
        assert "{environment}" not in result

    def test_no_template_unchanged(self):
        """Dimensions without templates are left unchanged."""
        from src.lambdas.dashboard.metrics_config import METRIC_GROUPS

        # Items Ingested group has empty dimensions
        items_group = METRIC_GROUPS[3]
        assert items_group["queries"][0]["dimensions"] == {}


# ===================================================================
# T-010: get_metrics() response structure
# ===================================================================


class TestGetMetrics:
    def test_returns_correct_structure(self, mock_environment):
        """get_metrics returns 200 with correct group/series structure."""
        from src.lambdas.dashboard.chaos import get_metrics

        mock_cw = MagicMock()
        mock_cw.get_metric_data.return_value = {
            "MetricDataResults": [
                {
                    "Id": "m0q0",
                    "Timestamps": [datetime(2026, 3, 27, 10, 0, tzinfo=UTC)],
                    "Values": [42.0],
                },
                {
                    "Id": "m0q1",
                    "Timestamps": [datetime(2026, 3, 27, 10, 0, tzinfo=UTC)],
                    "Values": [1.0],
                },
                {
                    "Id": "m1q0",
                    "Timestamps": [datetime(2026, 3, 27, 10, 0, tzinfo=UTC)],
                    "Values": [150.0],
                },
                {
                    "Id": "m2q0",
                    "Timestamps": [datetime(2026, 3, 27, 10, 0, tzinfo=UTC)],
                    "Values": [5.0],
                },
                {
                    "Id": "m2q1",
                    "Timestamps": [],
                    "Values": [],
                },
                {
                    "Id": "m3q0",
                    "Timestamps": [datetime(2026, 3, 27, 10, 0, tzinfo=UTC)],
                    "Values": [10.0],
                },
            ],
        }

        with patch("src.lambdas.dashboard.chaos.boto3") as mock_boto:
            mock_boto.client.return_value = mock_cw

            now = datetime.now(UTC)
            status, data = get_metrics(now - timedelta(minutes=30), now)

            assert status == 200
            assert "groups" in data
            assert len(data["groups"]) == 4

            # First group should have 2 series
            assert len(data["groups"][0]["series"]) == 2
            assert data["groups"][0]["series"][0]["label"] == "Invocations"
            assert data["groups"][0]["series"][0]["values"] == [42.0]

    def test_empty_results(self, mock_environment):
        """get_metrics handles empty CloudWatch results gracefully."""
        from src.lambdas.dashboard.chaos import get_metrics

        mock_cw = MagicMock()
        mock_cw.get_metric_data.return_value = {"MetricDataResults": []}

        with patch("src.lambdas.dashboard.chaos.boto3") as mock_boto:
            mock_boto.client.return_value = mock_cw

            now = datetime.now(UTC)
            status, data = get_metrics(now - timedelta(minutes=30), now)

            assert status == 200
            assert len(data["groups"]) == 4
            # All series should have empty arrays, not None
            for group in data["groups"]:
                for series in group["series"]:
                    assert series["timestamps"] == []
                    assert series["values"] == []


# ===================================================================
# T-011: AccessDeniedException
# ===================================================================


class TestMetricsAccessDenied:
    def test_returns_403(self, mock_environment):
        """AccessDeniedException returns 403 with error structure."""
        from src.lambdas.dashboard.chaos import get_metrics

        mock_cw = MagicMock()
        mock_cw.get_metric_data.side_effect = ClientError(
            {"Error": {"Code": "AccessDeniedException", "Message": "Not authorized"}},
            "GetMetricData",
        )

        with patch("src.lambdas.dashboard.chaos.boto3") as mock_boto:
            mock_boto.client.return_value = mock_cw

            now = datetime.now(UTC)
            status, data = get_metrics(now - timedelta(minutes=30), now)

            assert status == 403
            assert data["error"] == "metrics_unavailable"


# ===================================================================
# T-012: Throttling
# ===================================================================


class TestMetricsThrottling:
    def test_returns_429(self, mock_environment):
        """Throttling returns 429 with retry_after."""
        from src.lambdas.dashboard.chaos import get_metrics

        mock_cw = MagicMock()
        mock_cw.get_metric_data.side_effect = ClientError(
            {"Error": {"Code": "Throttling", "Message": "Rate exceeded"}},
            "GetMetricData",
        )

        with patch("src.lambdas.dashboard.chaos.boto3") as mock_boto:
            mock_boto.client.return_value = mock_cw

            now = datetime.now(UTC)
            status, data = get_metrics(now - timedelta(minutes=30), now)

            assert status == 429
            assert data["error"] == "throttled"
            assert data["retry_after"] == 5
