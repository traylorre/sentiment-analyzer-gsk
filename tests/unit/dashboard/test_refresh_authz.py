"""Authorization tests for POST /api/v2/configurations/{id}/refresh (Feature 1391 GAP-2).

Target: Customer Dashboard (Next.js/Amplify) API — dashboard Lambda REST route.

Before Feature 1391, ``trigger_refresh`` was fully unauthenticated with no
ownership check (mutating IDOR). This mirrors the hardening already applied to
its sibling ``get_refresh_status`` (Feature 1249):

    1. ``_require_user_id(event, table=table)`` -> 401 if no session
    2. ``_get_config_with_tickers(table, user_id, config_id)`` -> 404 if not
       owned (no existence oracle: same 404 whether missing or not-owned)
    3. only then ``market_service.trigger_refresh`` -> 202
"""

import json
from unittest.mock import MagicMock, patch

from src.lambdas.dashboard.handler import lambda_handler
from tests.conftest import make_event

_CONFIG_ID = "cfg-1391-refresh"
_PATH = f"/api/v2/configurations/{_CONFIG_ID}/refresh"


def _owned_config() -> MagicMock:
    """A configuration object as returned by config_service.get_configuration."""
    cfg = MagicMock()
    cfg.tickers = [MagicMock(symbol="AAPL")]
    return cfg


class TestTriggerRefreshAuthorization:
    """POST /configurations/{id}/refresh must require auth + ownership (GAP-2)."""

    def test_unauthenticated_returns_401(self, mock_lambda_context) -> None:
        """No session -> 401 (was: unauthenticated 202)."""
        with (
            patch(
                "src.lambdas.dashboard.router_v2.get_users_table",
                return_value=MagicMock(),
            ),
            patch(
                "src.lambdas.dashboard.router_v2.extract_auth_context",
                return_value={},
            ),
            patch(
                "src.lambdas.dashboard.router_v2.market_service.trigger_refresh"
            ) as mock_trigger,
        ):
            response = lambda_handler(
                make_event(method="POST", path=_PATH), mock_lambda_context
            )
        assert response["statusCode"] == 401
        # Action must never run for an unauthenticated caller.
        mock_trigger.assert_not_called()

    def test_authenticated_non_owner_returns_404(self, mock_lambda_context) -> None:
        """Authenticated user who does not own the config -> 404 (no oracle)."""
        with (
            patch(
                "src.lambdas.dashboard.router_v2.get_users_table",
                return_value=MagicMock(),
            ),
            patch(
                "src.lambdas.dashboard.router_v2.extract_auth_context",
                return_value={"user_id": "not-the-owner"},
            ),
            patch(
                "src.lambdas.dashboard.router_v2.auth_service.validate_session",
                return_value=MagicMock(valid=True),
            ),
            patch(
                "src.lambdas.dashboard.router_v2.config_service.get_configuration",
                return_value=None,
            ),
            patch(
                "src.lambdas.dashboard.router_v2.market_service.trigger_refresh"
            ) as mock_trigger,
        ):
            response = lambda_handler(
                make_event(method="POST", path=_PATH), mock_lambda_context
            )
        assert response["statusCode"] == 404
        mock_trigger.assert_not_called()

    def test_authenticated_owner_returns_202(self, mock_lambda_context) -> None:
        """Authenticated owner -> 202 and the refresh action runs."""
        trigger_result = MagicMock()
        trigger_result.model_dump.return_value = {"status": "triggered"}
        with (
            patch(
                "src.lambdas.dashboard.router_v2.get_users_table",
                return_value=MagicMock(),
            ),
            patch(
                "src.lambdas.dashboard.router_v2.extract_auth_context",
                return_value={"user_id": "the-owner"},
            ),
            patch(
                "src.lambdas.dashboard.router_v2.auth_service.validate_session",
                return_value=MagicMock(valid=True),
            ),
            patch(
                "src.lambdas.dashboard.router_v2.config_service.get_configuration",
                return_value=_owned_config(),
            ),
            patch(
                "src.lambdas.dashboard.router_v2.market_service.trigger_refresh",
                return_value=trigger_result,
            ) as mock_trigger,
        ):
            response = lambda_handler(
                make_event(method="POST", path=_PATH), mock_lambda_context
            )
        assert response["statusCode"] == 202
        assert json.loads(response["body"]) == {"status": "triggered"}
        mock_trigger.assert_called_once_with(config_id=_CONFIG_ID)
