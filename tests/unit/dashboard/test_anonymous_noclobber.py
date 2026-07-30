"""Unit tests for Feature 1384: no-clobber guard on POST /api/v2/auth/anonymous.

Root cause the guard closes: minting a new anonymous session issues a fresh
refresh_token cookie under the SAME name/path, which silently overwrites
(clobbers) an existing OAuth (Cognito-backed) refresh cookie. On the next
reload the OAuth session can no longer be restored and the user is logged out.

The guard: when the incoming request already carries a VALID Cognito refresh
cookie, the endpoint MUST refuse to mint (and MUST NOT emit a new refresh
cookie), returning the existing session instead. With no cookie (or an
anonymous/invalid cookie) the endpoint mints a new anonymous session as before.
"""

import json
from unittest.mock import patch

import boto3
from moto import mock_aws

from src.lambdas.dashboard.auth import RefreshTokenResponse
from src.lambdas.dashboard.handler import lambda_handler
from tests.conftest import make_event


def _create_users_table():
    dynamodb = boto3.resource("dynamodb", region_name="us-east-1")
    table = dynamodb.create_table(
        TableName="test-sentiment-users",
        KeySchema=[
            {"AttributeName": "PK", "KeyType": "HASH"},
            {"AttributeName": "SK", "KeyType": "RANGE"},
        ],
        AttributeDefinitions=[
            {"AttributeName": "PK", "AttributeType": "S"},
            {"AttributeName": "SK", "AttributeType": "S"},
        ],
        BillingMode="PAY_PER_REQUEST",
    )
    table.wait_until_exists()
    return table


def _set_cookie_values(response: dict) -> list[str]:
    """Return every Set-Cookie header value emitted by the response."""
    cookies: list[str] = []
    mv = response.get("multiValueHeaders") or {}
    for key, values in mv.items():
        if key.lower() == "set-cookie":
            cookies.extend(values)
    single = response.get("headers", {}) or {}
    for key, value in single.items():
        if key.lower() == "set-cookie" and value not in cookies:
            cookies.append(value)
    return cookies


class TestNoClobberGuardWithValidCognitoCookie:
    """A valid Cognito refresh cookie must NOT be overwritten by an anon mint."""

    @mock_aws
    def test_valid_cognito_cookie_returns_existing_session_not_new_anon(
        self, mock_lambda_context
    ):
        _create_users_table()

        cognito_result = RefreshTokenResponse(
            access_token="new-access-token",
            id_token="new-id-token",
            expires_in=3600,
            user_id="oauth-user-123",
            auth_type="google",
        )

        event = make_event(
            method="POST",
            path="/api/v2/auth/anonymous",
            cookies="refresh_token=cognito-refresh-token-abc",
        )

        with patch(
            "src.lambdas.dashboard.auth.refresh_access_tokens",
            return_value=cognito_result,
        ) as mock_refresh:
            response = lambda_handler(event, mock_lambda_context)

        # Guard validated the presented cookie via the refresh path.
        mock_refresh.assert_called_once()
        assert (
            mock_refresh.call_args.kwargs["refresh_token"]
            == "cognito-refresh-token-abc"
        )

        # 200 (existing session preserved), NOT 201 (new anon minted).
        assert response["statusCode"] == 200, response["body"]

        data = json.loads(response["body"])
        # Existing OAuth session returned, not a fresh anonymous identity.
        assert data.get("auth_type") != "anonymous"
        assert data["access_token"] == "new-access-token"
        assert data["user_id"] == "oauth-user-123"
        # Refresh token must NEVER be echoed in the body.
        assert "refresh_token_for_cookie" not in data
        assert "refresh_token" not in data

    @mock_aws
    def test_valid_cognito_cookie_does_not_emit_new_refresh_cookie(
        self, mock_lambda_context
    ):
        """The core no-clobber assertion: no Set-Cookie for refresh_token."""
        _create_users_table()

        cognito_result = RefreshTokenResponse(
            access_token="new-access-token",
            id_token="new-id-token",
            expires_in=3600,
            user_id="oauth-user-123",
            auth_type="google",
        )

        event = make_event(
            method="POST",
            path="/api/v2/auth/anonymous",
            cookies="refresh_token=cognito-refresh-token-abc",
        )

        with patch(
            "src.lambdas.dashboard.auth.refresh_access_tokens",
            return_value=cognito_result,
        ):
            response = lambda_handler(event, mock_lambda_context)

        # No Set-Cookie touches refresh_token → the OAuth cookie is preserved.
        for cookie in _set_cookie_values(response):
            assert not cookie.startswith("refresh_token="), (
                f"anon mint clobbered the OAuth refresh cookie: {cookie}"
            )


class TestNoClobberGuardFallsThroughToNormalMint:
    """Without a valid Cognito cookie, minting proceeds as before."""

    @mock_aws
    def test_no_cookie_mints_new_anonymous_session(self, mock_lambda_context):
        _create_users_table()

        event = make_event(method="POST", path="/api/v2/auth/anonymous")
        response = lambda_handler(event, mock_lambda_context)

        assert response["statusCode"] == 201, response["body"]
        data = json.loads(response["body"])
        assert data["auth_type"] == "anonymous"
        assert "user_id" in data
        # A fresh anonymous session DOES set a refresh cookie.
        cookies = _set_cookie_values(response)
        assert any(c.startswith("refresh_token=") for c in cookies)

    @mock_aws
    def test_anonymous_cookie_still_mints_new_session(self, mock_lambda_context):
        """An anon.* cookie is not a Cognito session; minting proceeds."""
        _create_users_table()

        event = make_event(
            method="POST",
            path="/api/v2/auth/anonymous",
            cookies="refresh_token=anon.some-user.some-secret-value",
        )
        # Guard must not even invoke the Cognito refresh path for anon.* cookies.
        with patch("src.lambdas.dashboard.auth.refresh_access_tokens") as mock_refresh:
            response = lambda_handler(event, mock_lambda_context)
            mock_refresh.assert_not_called()

        assert response["statusCode"] == 201, response["body"]
        assert json.loads(response["body"])["auth_type"] == "anonymous"

    @mock_aws
    def test_invalid_cognito_cookie_mints_new_session(self, mock_lambda_context):
        """A present-but-rejected refresh cookie falls through to normal mint."""
        _create_users_table()

        rejected = RefreshTokenResponse(
            error="invalid_grant", message="Refresh token expired or revoked"
        )

        event = make_event(
            method="POST",
            path="/api/v2/auth/anonymous",
            cookies="refresh_token=stale-cognito-token",
        )
        with patch(
            "src.lambdas.dashboard.auth.refresh_access_tokens",
            return_value=rejected,
        ):
            response = lambda_handler(event, mock_lambda_context)

        assert response["statusCode"] == 201, response["body"]
        assert json.loads(response["body"])["auth_type"] == "anonymous"


class TestNoClobberGuardHelperUnit:
    """Direct unit coverage of the guard helper."""

    def test_returns_none_when_no_cookie(self):
        from src.lambdas.dashboard.router_v2 import _noclobber_guard_response

        event = {"headers": {}}
        assert _noclobber_guard_response(event, table=None) is None

    def test_returns_none_for_anonymous_cookie_without_calling_refresh(self):
        from src.lambdas.dashboard.router_v2 import _noclobber_guard_response

        event = {"headers": {"cookie": "refresh_token=anon.u.secret"}}
        with patch("src.lambdas.dashboard.auth.refresh_access_tokens") as mock_refresh:
            assert _noclobber_guard_response(event, table=None) is None
            mock_refresh.assert_not_called()

    def test_returns_response_for_valid_cognito_cookie(self):
        from src.lambdas.dashboard.router_v2 import _noclobber_guard_response

        event = {"headers": {"cookie": "refresh_token=cognito-tok"}}
        good = RefreshTokenResponse(
            access_token="a", id_token="i", expires_in=3600, auth_type="github"
        )
        with patch(
            "src.lambdas.dashboard.auth.refresh_access_tokens", return_value=good
        ):
            result = _noclobber_guard_response(event, table=None)
        assert result is not None
        assert result.status_code == 200
        # No refresh cookie set on the guard response.
        set_cookies = result.headers.get("Set-Cookie")
        if set_cookies:
            values = set_cookies if isinstance(set_cookies, list) else [set_cookies]
            assert not any(v.startswith("refresh_token=") for v in values)
