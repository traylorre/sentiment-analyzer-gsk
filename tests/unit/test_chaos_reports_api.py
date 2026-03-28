"""
Unit Tests for Chaos Reports API Endpoints (Feature 1240)
=========================================================

Tests cover:
- Auth enforcement on all 7 report endpoints (T-027)
- 404 for missing reports
- 409 for duplicate persist
- Pagination flow
- Backward compatibility of existing experiment report endpoint

Uses direct lambda_handler invocation with make_event helper
(same pattern as test_dashboard_handler.py).
"""

import json
import os
from datetime import UTC, datetime, timedelta
from unittest.mock import MagicMock, patch

import jwt
import pytest

from src.lambdas.dashboard.handler import lambda_handler
from tests.conftest import make_event

# Test JWT configuration (matches test_dashboard_handler.py pattern)
TEST_JWT_SECRET = "test-secret-key-do-not-use-in-production"
TEST_USER_ID = "12345678-1234-5678-1234-567812345678"


def _create_test_jwt(
    user_id: str = TEST_USER_ID, roles: list[str] | None = None
) -> str:
    """Create a valid JWT token for testing authenticated endpoints."""
    if roles is None:
        roles = ["free"]
    now = datetime.now(UTC)
    payload = {
        "sub": user_id,
        "exp": now + timedelta(minutes=15),
        "iat": now,
        "iss": "sentiment-analyzer",
        "aud": "sentiment-analyzer-api",
        "nbf": now,
        "roles": roles,
    }
    return jwt.encode(payload, TEST_JWT_SECRET, algorithm="HS256")


@pytest.fixture
def jwt_env():
    """Set JWT environment variables for authenticated tests."""
    with patch.dict(
        os.environ,
        {"JWT_SECRET": TEST_JWT_SECRET, "JWT_AUDIENCE": "sentiment-analyzer-api"},
    ):
        yield


@pytest.fixture
def auth_headers(jwt_env):
    """Return valid authenticated session headers."""
    token = _create_test_jwt()
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def anonymous_headers():
    """Return anonymous session headers (UUID-based, not JWT)."""
    return {"Authorization": f"Bearer {TEST_USER_ID}"}


@pytest.fixture(autouse=True)
def _mock_session_validation():
    """Mock session validation for all handler tests (Feature 1249 pattern)."""
    mock_result = MagicMock()
    mock_result.valid = True
    with patch(
        "src.lambdas.dashboard.auth.validate_session",
        return_value=mock_result,
    ):
        yield


@pytest.fixture
def mock_chaos_environment(monkeypatch):
    """Set up chaos-related environment variables."""
    monkeypatch.setenv("CHAOS_EXPERIMENTS_TABLE", "test-chaos-experiments")
    monkeypatch.setenv("CHAOS_REPORTS_TABLE", "test-chaos-reports")
    import src.lambdas.dashboard.chaos as chaos_module

    monkeypatch.setattr(chaos_module, "ENVIRONMENT", "test")
    monkeypatch.setattr(chaos_module, "CHAOS_TABLE", "test-chaos-experiments")
    monkeypatch.setattr(chaos_module, "CHAOS_REPORTS_TABLE", "test-chaos-reports")


# ===================================================================
# Auth enforcement tests (T-027)
# ===================================================================


class TestReportEndpointAuth:
    """All report endpoints must require authentication."""

    @pytest.mark.parametrize(
        "method,path",
        [
            ("POST", "/chaos/reports"),
            ("POST", "/chaos/reports/plan"),
            ("GET", "/chaos/reports"),
            ("GET", "/chaos/reports/test-id"),
            ("GET", "/chaos/reports/test-id/compare"),
            ("GET", "/chaos/reports/trends/ingestion_failure"),
            ("DELETE", "/chaos/reports/test-id"),
        ],
    )
    def test_unauthenticated_returns_401(
        self, method, path, mock_lambda_context, mock_chaos_environment
    ):
        """Unauthenticated requests return 401 on all report endpoints."""
        event = make_event(method=method, path=path)
        response = lambda_handler(event, mock_lambda_context)
        assert response["statusCode"] == 401
        body = json.loads(response["body"])
        assert "Authentication required" in body["detail"]

    @pytest.mark.parametrize(
        "method,path",
        [
            ("POST", "/chaos/reports"),
            ("POST", "/chaos/reports/plan"),
            ("GET", "/chaos/reports"),
            ("GET", "/chaos/reports/test-id"),
            ("GET", "/chaos/reports/test-id/compare"),
            ("GET", "/chaos/reports/trends/ingestion_failure"),
            ("DELETE", "/chaos/reports/test-id"),
        ],
    )
    def test_anonymous_returns_401_in_preprod(
        self,
        method,
        path,
        mock_lambda_context,
        anonymous_headers,
        monkeypatch,
    ):
        """Anonymous sessions are rejected for chaos endpoints in preprod."""
        monkeypatch.setenv("ENVIRONMENT", "preprod")
        import src.lambdas.dashboard.chaos as chaos_module

        monkeypatch.setattr(chaos_module, "ENVIRONMENT", "preprod")
        monkeypatch.setattr(
            chaos_module, "CHAOS_REPORTS_TABLE", "preprod-chaos-reports"
        )

        event = make_event(method=method, path=path, headers=anonymous_headers)
        response = lambda_handler(event, mock_lambda_context)
        assert response["statusCode"] == 401


# ===================================================================
# Report CRUD endpoint tests
# ===================================================================


class TestCreateReportEndpoint:
    def test_missing_experiment_id_returns_400(
        self, mock_lambda_context, auth_headers, mock_chaos_environment
    ):
        """Missing experiment_id in body returns 400."""
        event = make_event(
            method="POST",
            path="/chaos/reports",
            headers=auth_headers,
            body={},
        )
        response = lambda_handler(event, mock_lambda_context)
        assert response["statusCode"] == 400
        body = json.loads(response["body"])
        assert "experiment_id required" in body["detail"]

    def test_duplicate_experiment_report_returns_409(
        self, mock_lambda_context, auth_headers, mock_chaos_environment
    ):
        """Creating a report for an experiment that already has one returns 409."""
        with patch("src.lambdas.dashboard.handler.list_reports") as mock_list:
            mock_list.return_value = {
                "reports": [{"experiment_id": "exp-1", "report_type": "experiment"}],
                "next_cursor": None,
            }

            event = make_event(
                method="POST",
                path="/chaos/reports",
                headers=auth_headers,
                body={"experiment_id": "exp-1"},
            )
            response = lambda_handler(event, mock_lambda_context)
            assert response["statusCode"] == 409
            body = json.loads(response["body"])
            assert "already exists" in body["detail"]

    def test_create_report_success(
        self, mock_lambda_context, auth_headers, mock_chaos_environment
    ):
        """Successful report creation returns 201."""
        with (
            patch("src.lambdas.dashboard.handler.list_reports") as mock_list,
            patch(
                "src.lambdas.dashboard.handler.get_experiment_report"
            ) as mock_get_exp,
            patch("src.lambdas.dashboard.handler.persist_report") as mock_persist,
        ):
            mock_list.return_value = {"reports": [], "next_cursor": None}
            mock_get_exp.return_value = {
                "experiment_id": "exp-1",
                "scenario": "ingestion_failure",
                "verdict": "CLEAN",
                "verdict_reason": "All checks passed",
                "environment": "test",
                "created_at": "2026-03-27T00:00:00Z",
                "duration_seconds": 60,
            }
            mock_persist.return_value = {
                "report_id": "rpt-1",
                "experiment_id": "exp-1",
                "scenario_type": "ingestion_failure",
                "verdict": "CLEAN",
            }

            event = make_event(
                method="POST",
                path="/chaos/reports",
                headers=auth_headers,
                body={"experiment_id": "exp-1"},
            )
            response = lambda_handler(event, mock_lambda_context)
            assert response["statusCode"] == 201

    def test_nonexistent_experiment_returns_404(
        self, mock_lambda_context, auth_headers, mock_chaos_environment
    ):
        """Creating report for nonexistent experiment returns 404."""
        from src.lambdas.dashboard.chaos import ChaosError

        with (
            patch("src.lambdas.dashboard.handler.list_reports") as mock_list,
            patch(
                "src.lambdas.dashboard.handler.get_experiment_report"
            ) as mock_get_exp,
        ):
            mock_list.return_value = {"reports": [], "next_cursor": None}
            mock_get_exp.side_effect = ChaosError("Experiment not found: exp-999")

            event = make_event(
                method="POST",
                path="/chaos/reports",
                headers=auth_headers,
                body={"experiment_id": "exp-999"},
            )
            response = lambda_handler(event, mock_lambda_context)
            assert response["statusCode"] == 404


class TestCreatePlanReportEndpoint:
    def test_missing_plan_name_returns_400(
        self, mock_lambda_context, auth_headers, mock_chaos_environment
    ):
        """Missing plan_name in body returns 400."""
        event = make_event(
            method="POST",
            path="/chaos/reports/plan",
            headers=auth_headers,
            body={"experiment_ids": ["exp-1"]},
        )
        response = lambda_handler(event, mock_lambda_context)
        assert response["statusCode"] == 400
        body = json.loads(response["body"])
        assert "plan_name" in body["detail"]

    def test_missing_experiment_ids_returns_400(
        self, mock_lambda_context, auth_headers, mock_chaos_environment
    ):
        """Missing experiment_ids in body returns 400."""
        event = make_event(
            method="POST",
            path="/chaos/reports/plan",
            headers=auth_headers,
            body={"plan_name": "test-plan"},
        )
        response = lambda_handler(event, mock_lambda_context)
        assert response["statusCode"] == 400

    def test_create_plan_report_success(
        self, mock_lambda_context, auth_headers, mock_chaos_environment
    ):
        """Successful plan report creation returns 201."""
        with patch("src.lambdas.dashboard.handler.generate_plan_report") as mock_gen:
            mock_gen.return_value = {
                "report_id": "plan-rpt-1",
                "report_type": "plan",
                "plan_name": "resilience-plan",
                "verdict": "CLEAN",
            }

            event = make_event(
                method="POST",
                path="/chaos/reports/plan",
                headers=auth_headers,
                body={
                    "plan_name": "resilience-plan",
                    "experiment_ids": ["exp-1", "exp-2"],
                },
            )
            response = lambda_handler(event, mock_lambda_context)
            assert response["statusCode"] == 201


class TestGetReportEndpoint:
    def test_nonexistent_report_returns_404(
        self, mock_lambda_context, auth_headers, mock_chaos_environment
    ):
        """GET /chaos/reports/{id} returns 404 for missing report."""
        with patch("src.lambdas.dashboard.handler.get_report") as mock_get:
            mock_get.return_value = None

            event = make_event(
                method="GET",
                path="/chaos/reports/nonexistent",
                headers=auth_headers,
            )
            response = lambda_handler(event, mock_lambda_context)
            assert response["statusCode"] == 404
            body = json.loads(response["body"])
            assert "not found" in body["detail"].lower()

    def test_get_report_success(
        self, mock_lambda_context, auth_headers, mock_chaos_environment
    ):
        """GET /chaos/reports/{id} returns 200 for existing report."""
        with patch("src.lambdas.dashboard.handler.get_report") as mock_get:
            mock_get.return_value = {
                "report_id": "rpt-1",
                "scenario_type": "ingestion_failure",
                "verdict": "CLEAN",
                "created_at": "2026-03-27T00:00:00Z",
            }

            event = make_event(
                method="GET",
                path="/chaos/reports/rpt-1",
                headers=auth_headers,
            )
            response = lambda_handler(event, mock_lambda_context)
            assert response["statusCode"] == 200
            body = json.loads(response["body"])
            assert body["report_id"] == "rpt-1"


class TestDeleteReportEndpoint:
    def test_nonexistent_delete_returns_404(
        self, mock_lambda_context, auth_headers, mock_chaos_environment
    ):
        """DELETE /chaos/reports/{id} returns 404 for missing report."""
        with patch("src.lambdas.dashboard.handler.delete_report") as mock_delete:
            mock_delete.return_value = False

            event = make_event(
                method="DELETE",
                path="/chaos/reports/nonexistent",
                headers=auth_headers,
            )
            response = lambda_handler(event, mock_lambda_context)
            assert response["statusCode"] == 404

    def test_delete_report_success(
        self, mock_lambda_context, auth_headers, mock_chaos_environment
    ):
        """DELETE /chaos/reports/{id} returns 204 on success."""
        with patch("src.lambdas.dashboard.handler.delete_report") as mock_delete:
            mock_delete.return_value = True

            event = make_event(
                method="DELETE",
                path="/chaos/reports/rpt-1",
                headers=auth_headers,
            )
            response = lambda_handler(event, mock_lambda_context)
            assert response["statusCode"] == 204


class TestListReportsEndpoint:
    def test_list_with_filters(
        self, mock_lambda_context, auth_headers, mock_chaos_environment
    ):
        """GET /chaos/reports with filters passes params correctly."""
        with patch("src.lambdas.dashboard.handler.list_reports") as mock_list:
            mock_list.return_value = {"reports": [], "next_cursor": None}

            event = make_event(
                method="GET",
                path="/chaos/reports",
                headers=auth_headers,
                query_params={
                    "scenario_type": "ingestion_failure",
                    "verdict": "CLEAN",
                    "limit": "10",
                },
            )
            response = lambda_handler(event, mock_lambda_context)
            assert response["statusCode"] == 200
            mock_list.assert_called_once_with(
                scenario_type="ingestion_failure",
                verdict="CLEAN",
                report_type=None,
                from_date=None,
                to_date=None,
                limit=10,
                cursor=None,
            )

    def test_list_returns_reports(
        self, mock_lambda_context, auth_headers, mock_chaos_environment
    ):
        """GET /chaos/reports returns report list."""
        with patch("src.lambdas.dashboard.handler.list_reports") as mock_list:
            mock_list.return_value = {
                "reports": [
                    {
                        "report_id": "rpt-1",
                        "scenario_type": "ingestion_failure",
                        "verdict": "CLEAN",
                    },
                    {
                        "report_id": "rpt-2",
                        "scenario_type": "dynamodb_throttle",
                        "verdict": "COMPROMISED",
                    },
                ],
                "next_cursor": None,
            }

            event = make_event(
                method="GET",
                path="/chaos/reports",
                headers=auth_headers,
            )
            response = lambda_handler(event, mock_lambda_context)
            assert response["statusCode"] == 200
            body = json.loads(response["body"])
            assert len(body["reports"]) == 2


class TestCompareReportEndpoint:
    def test_first_baseline_returns_422(
        self, mock_lambda_context, auth_headers, mock_chaos_environment
    ):
        """Compare with no previous report returns 422."""
        with patch("src.lambdas.dashboard.handler.compare_reports") as mock_compare:
            mock_compare.return_value = {
                "is_first_baseline": True,
                "message": "First baseline -- no prior report for comparison",
            }

            event = make_event(
                method="GET",
                path="/chaos/reports/report-1/compare",
                headers=auth_headers,
            )
            response = lambda_handler(event, mock_lambda_context)
            assert response["statusCode"] == 422
            body = json.loads(response["body"])
            assert body["is_first_baseline"] is True

    def test_compare_success(
        self, mock_lambda_context, auth_headers, mock_chaos_environment
    ):
        """Successful comparison returns 200."""
        with patch("src.lambdas.dashboard.handler.compare_reports") as mock_compare:
            mock_compare.return_value = {
                "is_first_baseline": False,
                "verdict_change": {
                    "current": "CLEAN",
                    "baseline": "COMPROMISED",
                    "direction": "improved",
                },
            }

            event = make_event(
                method="GET",
                path="/chaos/reports/report-1/compare",
                headers=auth_headers,
            )
            response = lambda_handler(event, mock_lambda_context)
            assert response["statusCode"] == 200
            body = json.loads(response["body"])
            assert body["verdict_change"]["direction"] == "improved"

    def test_compare_with_baseline_id(
        self, mock_lambda_context, auth_headers, mock_chaos_environment
    ):
        """Compare with explicit baseline_id passes param correctly."""
        with patch("src.lambdas.dashboard.handler.compare_reports") as mock_compare:
            mock_compare.return_value = {
                "is_first_baseline": False,
                "verdict_change": {
                    "current": "CLEAN",
                    "baseline": "CLEAN",
                    "direction": "unchanged",
                },
            }

            event = make_event(
                method="GET",
                path="/chaos/reports/report-1/compare",
                headers=auth_headers,
                query_params={"baseline_id": "report-0"},
            )
            response = lambda_handler(event, mock_lambda_context)
            assert response["statusCode"] == 200
            mock_compare.assert_called_once_with("report-1", "report-0")

    def test_compare_chaos_error_returns_400(
        self, mock_lambda_context, auth_headers, mock_chaos_environment
    ):
        """ChaosError during comparison returns 400."""
        from src.lambdas.dashboard.chaos import ChaosError

        with patch("src.lambdas.dashboard.handler.compare_reports") as mock_compare:
            mock_compare.side_effect = ChaosError("Cannot compare different scenarios")

            event = make_event(
                method="GET",
                path="/chaos/reports/report-1/compare",
                headers=auth_headers,
            )
            response = lambda_handler(event, mock_lambda_context)
            assert response["statusCode"] == 400


class TestTrendsEndpoint:
    def test_trends_returns_data(
        self, mock_lambda_context, auth_headers, mock_chaos_environment
    ):
        """GET /chaos/reports/trends/{scenario} returns trend data."""
        with patch("src.lambdas.dashboard.handler.get_trends") as mock_trends:
            mock_trends.return_value = [
                {
                    "report_id": "rpt-1",
                    "created_at": "2026-03-25T00:00:00Z",
                    "verdict": "COMPROMISED",
                    "recovery_observed": True,
                    "recovery_time_seconds": 45,
                },
                {
                    "report_id": "rpt-2",
                    "created_at": "2026-03-27T00:00:00Z",
                    "verdict": "CLEAN",
                    "recovery_observed": True,
                    "recovery_time_seconds": 12,
                },
            ]

            event = make_event(
                method="GET",
                path="/chaos/reports/trends/ingestion_failure",
                headers=auth_headers,
            )
            response = lambda_handler(event, mock_lambda_context)
            assert response["statusCode"] == 200
            body = json.loads(response["body"])
            assert len(body) == 2


# ===================================================================
# Backward compatibility (SC-008)
# ===================================================================


class TestBackwardCompatibility:
    def test_existing_experiment_report_endpoint_unchanged(
        self, mock_lambda_context, auth_headers, mock_chaos_environment
    ):
        """GET /chaos/experiments/{id}/report still works (SC-008)."""
        with patch("src.lambdas.dashboard.handler.get_experiment_report") as mock_get:
            mock_get.return_value = {
                "experiment_id": "exp-1",
                "scenario": "ingestion_failure",
                "verdict": "CLEAN",
                "duration_seconds": 60,
            }

            event = make_event(
                method="GET",
                path="/chaos/experiments/exp-1/report",
                headers=auth_headers,
            )
            response = lambda_handler(event, mock_lambda_context)
            assert response["statusCode"] == 200
            body = json.loads(response["body"])
            assert body["experiment_id"] == "exp-1"
            assert body["verdict"] == "CLEAN"
