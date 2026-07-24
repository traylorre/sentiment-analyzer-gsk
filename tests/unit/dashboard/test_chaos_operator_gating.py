"""Operator-role gating for /chaos/* routes (Feature 1391 GAP-3).

Target: Admin/operational routes on the dashboard Lambda.

Before Feature 1391 the /chaos/* routes gated only via
``_get_chaos_user_id_from_event`` (Feature 1250), which accepts ANY
non-anonymous user -- so a free signed-in user could pull the andon cord or
flip the chaos gate. GAP-3 attaches ``require_role_middleware("operator")`` to
the chaos control AND read routes, mirroring the usage on
``/api/v2/admin/sessions/revoke`` (Feature 1148).

The require_role primitive returns:
    - 401 "Authentication required" when there is no session (user_id is None)
    - 403 "Access denied" when the user lacks the operator role

Note on anonymous sessions: an anonymous (UUID) session carries
roles=["anonymous"], so the operator gate now returns 403 (was 401 via the
handler body). Either way the anonymous caller is denied -- the security
invariant "anonymous cannot touch chaos" still holds, strictly tightened.

``_is_dev_environment()`` and the chaos service-layer
``check_environment_allowed()`` are retained as additive defense-in-depth and
are exercised by the existing chaos security tests.
"""

import json
from unittest.mock import patch

from src.lambdas.dashboard.handler import lambda_handler
from src.lambdas.shared.middleware import AuthContext, AuthType
from tests.conftest import make_event

# Control route (mutating) and a read route -- both must be operator-gated.
_ANDON_PATH = "/chaos/andon-cord"
_GATE_PATH = "/chaos/gate"


def _auth_context(
    user_id: str | None = "op-user",
    auth_type: AuthType = AuthType.AUTHENTICATED,
    roles: list[str] | None = None,
) -> AuthContext:
    return AuthContext(
        user_id=user_id,
        auth_type=auth_type,
        auth_method="bearer" if user_id else None,
        roles=roles,
    )


class TestChaosControlRouteOperatorGating:
    """POST /chaos/andon-cord (control route) requires the operator role."""

    def test_no_session_returns_401(self, mock_lambda_context) -> None:
        """No session -> 401 from the operator middleware."""
        with patch(
            "src.lambdas.shared.middleware.require_role.extract_auth_context_typed",
            return_value=_auth_context(user_id=None, roles=None),
        ):
            response = lambda_handler(
                make_event(method="POST", path=_ANDON_PATH), mock_lambda_context
            )
        assert response["statusCode"] == 401
        assert json.loads(response["body"])["detail"] == "Authentication required"

    def test_signed_in_free_user_returns_403(self, mock_lambda_context) -> None:
        """A non-operator (free) signed-in user cannot pull the andon cord."""
        with patch(
            "src.lambdas.shared.middleware.require_role.extract_auth_context_typed",
            return_value=_auth_context(roles=["free"]),
        ):
            response = lambda_handler(
                make_event(method="POST", path=_ANDON_PATH), mock_lambda_context
            )
        assert response["statusCode"] == 403
        assert json.loads(response["body"])["detail"] == "Access denied"

    def test_anonymous_session_is_denied(self, mock_lambda_context) -> None:
        """Anonymous session (roles=['anonymous']) is denied by the operator gate.

        Denied is the invariant; the primitive returns 403 for a present-but-
        unprivileged session (tightened from the pre-1391 handler-body 401).
        """
        with patch(
            "src.lambdas.shared.middleware.require_role.extract_auth_context_typed",
            return_value=_auth_context(
                auth_type=AuthType.ANONYMOUS, roles=["anonymous"]
            ),
        ):
            response = lambda_handler(
                make_event(method="POST", path=_ANDON_PATH), mock_lambda_context
            )
        assert response["statusCode"] in (401, 403)
        # Never authorized: the andon cord is not pulled for anonymous callers.
        assert json.loads(response["body"])["detail"] != "kill_switch_set"

    def test_operator_reaches_handler(self, mock_lambda_context) -> None:
        """Operator passes the gate and the andon-cord action executes -> 200."""
        op_ctx = _auth_context(roles=["free", "operator"])
        with (
            patch(
                "src.lambdas.shared.middleware.require_role.extract_auth_context_typed",
                return_value=op_ctx,
            ),
            # Handler body's _get_chaos_user_id_from_event uses this copy.
            patch(
                "src.lambdas.dashboard.handler.extract_auth_context_typed",
                return_value=op_ctx,
            ),
            patch(
                "src.lambdas.dashboard.handler.pull_andon_cord",
                return_value={"kill_switch_set": True, "disabled": []},
            ) as mock_pull,
        ):
            response = lambda_handler(
                make_event(method="POST", path=_ANDON_PATH), mock_lambda_context
            )
        assert response["statusCode"] == 200
        assert json.loads(response["body"])["kill_switch_set"] is True
        mock_pull.assert_called_once()


class TestChaosReadRouteOperatorGating:
    """GET /chaos/gate (read route) is also operator-gated (leaks internals)."""

    def test_signed_in_free_user_returns_403(self, mock_lambda_context) -> None:
        """A non-operator cannot read the chaos gate state."""
        with patch(
            "src.lambdas.shared.middleware.require_role.extract_auth_context_typed",
            return_value=_auth_context(roles=["paid"]),
        ):
            response = lambda_handler(
                make_event(method="GET", path=_GATE_PATH), mock_lambda_context
            )
        assert response["statusCode"] == 403
        assert json.loads(response["body"])["detail"] == "Access denied"

    def test_no_session_returns_401(self, mock_lambda_context) -> None:
        """No session -> 401 from the operator middleware."""
        with patch(
            "src.lambdas.shared.middleware.require_role.extract_auth_context_typed",
            return_value=_auth_context(user_id=None, roles=None),
        ):
            response = lambda_handler(
                make_event(method="GET", path=_GATE_PATH), mock_lambda_context
            )
        assert response["statusCode"] == 401

    def test_operator_reads_gate_state(self, mock_lambda_context) -> None:
        """Operator passes the gate and reads state -> 200."""
        op_ctx = _auth_context(roles=["operator"])
        with (
            patch(
                "src.lambdas.shared.middleware.require_role.extract_auth_context_typed",
                return_value=op_ctx,
            ),
            patch(
                "src.lambdas.dashboard.handler.extract_auth_context_typed",
                return_value=op_ctx,
            ),
            patch(
                "src.lambdas.dashboard.handler.get_gate_state",
                return_value="disarmed",
            ),
        ):
            response = lambda_handler(
                make_event(method="GET", path=_GATE_PATH), mock_lambda_context
            )
        assert response["statusCode"] == 200
        assert json.loads(response["body"])["state"] == "disarmed"
