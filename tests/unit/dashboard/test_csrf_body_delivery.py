# Target: Admin Dashboard (Lambda HTMX) backend — Feature 1396 CSRF body delivery
"""Feature 1396 (T040 / N2): the refresh (and callback) responses return the CSRF token
value in the JSON body, matching the value set in the csrf_token Set-Cookie, so the
cross-origin Amplify frontend (which cannot read the API-domain cookie) can echo it as
X-CSRF-Token. Backend double-submit validation is unchanged.
"""

from unittest.mock import MagicMock, patch

from src.lambdas.dashboard import router_v2
from src.lambdas.dashboard.auth import RefreshTokenResponse
from src.lambdas.dashboard.router_v2 import _make_csrf_set_cookie


class TestCsrfCookieHonorsToken:
    def test_provided_token_used_in_cookie(self):
        cookie = _make_csrf_set_cookie(None, token="fixed-csrf-value-123")
        assert "csrf_token=fixed-csrf-value-123" in cookie

    def test_token_none_generates_a_value(self):
        cookie = _make_csrf_set_cookie(None)
        # A real 43-char urlsafe token, not empty.
        assert "csrf_token=" in cookie
        assert "csrf_token=;" not in cookie


class TestRefreshBodyDeliversCsrf:
    def test_refresh_body_csrf_matches_set_cookie(self):
        import re

        from src.lambdas.dashboard.handler import lambda_handler
        from tests.conftest import make_event

        fake_result = RefreshTokenResponse(
            id_token="id",
            access_token="app-jwt",
            expires_in=900,
            user_id="u-1",
            auth_type="google",
        )
        event = make_event(
            method="POST",
            path="/api/v2/auth/refresh",
            cookies="refresh_token=cognito-refresh-cookie",
        )
        with (
            patch.object(router_v2, "get_users_table", return_value=MagicMock()),
            patch.object(
                router_v2.auth_service,
                "refresh_access_tokens",
                return_value=fake_result,
            ),
        ):
            response = lambda_handler(event, MagicMock())

        assert response["statusCode"] == 200
        import orjson

        body = orjson.loads(response["body"])
        assert body.get("csrf_token")  # present and non-empty

        # Set-Cookie may be in multiValueHeaders or headers.
        set_cookies = response.get("multiValueHeaders", {}).get("Set-Cookie") or []
        joined = "\n".join(set_cookies)
        m = re.search(r"csrf_token=([^;]+)", joined)
        assert m is not None
        assert m.group(1) == body["csrf_token"]
