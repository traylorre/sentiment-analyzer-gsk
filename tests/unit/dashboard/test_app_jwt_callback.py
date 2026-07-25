# Target: Admin Dashboard (Lambda HTMX) backend — Feature 1396 callback mint
"""Feature 1396 (T020): handle_oauth_callback returns a first-party app JWT as
tokens['access_token'] (not the raw Cognito access token), it passes validate_jwt with
the user's roles and sub == the created user's user_id, expires_in == 900, and the
Cognito refresh token still flows via refresh_token_for_cookie.
"""

from unittest.mock import MagicMock, patch

import boto3
import pytest
from moto import mock_aws

from src.lambdas.dashboard.auth import handle_oauth_callback
from src.lambdas.shared.middleware.auth_middleware import validate_jwt

EMAIL = "new.oauth.user@gmail.com"
COGNITO_SUB = "google-cognito-sub-xyz"
_SECRET = "unit-test-app-jwt-secret-not-prod"  # pragma: allowlist secret


@pytest.fixture(autouse=True)
def _jwt_env(monkeypatch):
    monkeypatch.setenv("JWT_SECRET", _SECRET)
    monkeypatch.delenv("JWT_ISSUER", raising=False)
    monkeypatch.delenv("JWT_AUDIENCE", raising=False)


def _create_users_table():
    resource = boto3.resource("dynamodb", region_name="us-east-1")
    return resource.create_table(
        TableName="test-users",
        KeySchema=[
            {"AttributeName": "PK", "KeyType": "HASH"},
            {"AttributeName": "SK", "KeyType": "RANGE"},
        ],
        AttributeDefinitions=[
            {"AttributeName": "PK", "AttributeType": "S"},
            {"AttributeName": "SK", "AttributeType": "S"},
            {"AttributeName": "email", "AttributeType": "S"},
            {"AttributeName": "cognito_sub", "AttributeType": "S"},
            {"AttributeName": "provider_sub", "AttributeType": "S"},
        ],
        GlobalSecondaryIndexes=[
            {
                "IndexName": "by_email",
                "KeySchema": [{"AttributeName": "email", "KeyType": "HASH"}],
                "Projection": {"ProjectionType": "ALL"},
            },
            {
                "IndexName": "by_cognito_sub",
                "KeySchema": [{"AttributeName": "cognito_sub", "KeyType": "HASH"}],
                "Projection": {"ProjectionType": "ALL"},
            },
            {
                "IndexName": "by_provider_sub",
                "KeySchema": [{"AttributeName": "provider_sub", "KeyType": "HASH"}],
                "Projection": {"ProjectionType": "ALL"},
            },
        ],
        BillingMode="PAY_PER_REQUEST",
    )


def _mock_tokens():
    tokens = MagicMock()
    tokens.id_token = "mock-id-token"
    tokens.access_token = "raw-cognito-access-token"
    tokens.expires_in = 3600
    tokens.refresh_token = "cognito-refresh-token"
    return tokens


def _claims():
    return {"email": EMAIL, "sub": COGNITO_SUB, "email_verified": True}


def _user_id_in_table(table) -> str:
    for item in table.scan().get("Items", []):
        if item.get("entity_type") == "USER":
            return item["user_id"]
    raise AssertionError("no USER record created")


@mock_aws
def test_callback_returns_app_jwt_bearer():
    table = _create_users_table()
    with (
        patch(
            "src.lambdas.dashboard.auth.validate_oauth_state",
            return_value=(True, "", None),
        ),
        patch("src.lambdas.dashboard.auth.CognitoConfig.from_env"),
        patch(
            "src.lambdas.dashboard.auth.exchange_code_for_tokens",
            return_value=_mock_tokens(),
        ),
        patch("src.lambdas.dashboard.auth.decode_id_token", return_value=_claims()),
    ):
        result = handle_oauth_callback(
            table=table,
            code="auth-code",
            provider="google",
            redirect_uri="https://app.example.com/auth/callback",
            state="state-xyz",
        )

    assert result.status == "authenticated"
    bearer = result.tokens["access_token"]

    # Not the raw Cognito access token.
    assert bearer != "raw-cognito-access-token"
    # expires_in reflects the app-JWT TTL, not Cognito's 3600.
    assert result.tokens["expires_in"] == 900
    # Cognito refresh token still flows to the httpOnly cookie.
    assert result.refresh_token_for_cookie == "cognito-refresh-token"

    claim = validate_jwt(bearer)
    assert claim is not None
    assert claim.roles == ["free"]  # new OAuth user
    assert claim.subject == _user_id_in_table(table)
