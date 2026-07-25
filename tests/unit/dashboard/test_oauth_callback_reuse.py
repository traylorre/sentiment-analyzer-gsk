# Target: Admin Dashboard (Lambda HTMX) backend OAuth callback
"""Feature 1395: the OAuth callback reuses an existing account by stable identity.

Before this fix, a polluted `by_email` GSI made the email lookup return a false `None`,
so `handle_oauth_callback` minted a brand-new `user_id` on nearly every login. These
tests drive the real callback twice against a moto table and assert exactly one USER
record survives (reuse), and that a genuine sub-vs-email divergence still returns AUTH_023.
"""

from unittest.mock import MagicMock, patch
from uuid import uuid4

import boto3
import pytest
from moto import mock_aws

from src.lambdas.dashboard.auth import IdentityLookupError, handle_oauth_callback

EMAIL = "returning.user@gmail.com"
COGNITO_SUB = "google-cognito-sub-abc123"


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


def _count_user_records(table) -> int:
    items = table.scan().get("Items", [])
    return sum(
        1
        for i in items
        if i.get("entity_type") == "USER" and str(i.get("PK", "")).startswith("USER#")
    )


def _mock_tokens():
    tokens = MagicMock()
    tokens.id_token = "mock-id-token"
    tokens.access_token = "mock-access-token"
    tokens.expires_in = 3600
    tokens.refresh_token = "mock-refresh-token"
    return tokens


def _claims():
    return {
        "email": EMAIL,
        "sub": COGNITO_SUB,
        "email_verified": True,
        "picture": "https://example.com/a.png",
    }


def _run_callback(table):
    return handle_oauth_callback(
        table=table,
        code="auth-code",
        provider="google",
        redirect_uri="https://app.example.com/auth/callback",
        state="state-xyz",
    )


@mock_aws
def test_second_login_reuses_existing_user_no_duplicate():
    """SC-1: two sequential logins for the same Google identity -> one USER record."""
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
        patch("src.lambdas.dashboard.auth._mark_email_verified"),
        patch("src.lambdas.dashboard.auth._advance_role"),
    ):
        first = _run_callback(table)
        assert first.status == "authenticated"
        assert first.is_new_user is True
        assert _count_user_records(table) == 1

        second = _run_callback(table)
        assert second.status == "authenticated"
        assert second.is_new_user is False  # reused, not created
        assert _count_user_records(table) == 1


@mock_aws
def test_reuse_survives_magic_link_token_polluting_email_index():
    """The by_email pollution path end-to-end: a MAGIC_LINK_TOKEN under the same email
    must not cause a duplicate on the second login."""
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
        patch("src.lambdas.dashboard.auth._mark_email_verified"),
        patch("src.lambdas.dashboard.auth._advance_role"),
    ):
        first = _run_callback(table)
        assert first.is_new_user is True

        # A magic-link token stored under the SAME email pollutes the by_email GSI.
        table.put_item(
            Item={
                "PK": f"TOKEN#{uuid4()}",
                "SK": "TOKEN",
                "email": EMAIL,
                "entity_type": "MAGIC_LINK_TOKEN",
            }
        )

        second = _run_callback(table)
        assert second.status == "authenticated"
        assert second.is_new_user is False
        assert _count_user_records(table) == 1


@mock_aws
def test_sub_vs_email_divergence_returns_auth_023():
    """FR-007: when the sub resolves to a DIFFERENT user than the email account, the
    callback returns AUTH_023 rather than reusing across the boundary or minting a third
    record."""
    table = _create_users_table()

    user_a = MagicMock()
    user_a.user_id = "user-A"
    user_a.auth_type = "google"
    user_a.email = "userA@gmail.com"

    user_b = MagicMock()
    user_b.user_id = "user-B"  # provider_sub owned by a DIFFERENT user
    user_b.auth_type = "google"
    user_b.email = "userB@gmail.com"

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
        patch("src.lambdas.dashboard.auth.get_user_by_email_gsi", return_value=user_a),
        patch(
            "src.lambdas.dashboard.auth.get_user_by_provider_sub", return_value=user_b
        ),
        patch("src.lambdas.dashboard.auth.get_user_by_cognito_sub", return_value=None),
    ):
        result = _run_callback(table)

    assert result.status == "error"
    assert result.error == "AUTH_023"
    assert _count_user_records(table) == 0


class _QueryRaisesTable:
    """Wraps a moto table but makes every GSI ``query`` fail (page-1 DynamoDB error).

    Base-table operations (``put_item``, ``scan``, ``update_item``) still work so the test
    can assert that ZERO USER records were written despite the identity resolution failing.
    """

    def __init__(self, inner):
        self._inner = inner

    def query(self, **kwargs):
        raise RuntimeError("ProvisionedThroughputExceededException (simulated page-1)")

    def __getattr__(self, name):
        return getattr(self._inner, name)


@mock_aws
def test_page_one_lookup_failure_fails_closed_no_user_minted():
    """SC-6 (CWE-636 regression pin): a DynamoDB failure during identity resolution must
    surface as IdentityLookupError and mint ZERO USER records — never fall through to
    _create_authenticated_user."""
    inner = _create_users_table()
    table = _QueryRaisesTable(inner)

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
        patch("src.lambdas.dashboard.auth._mark_email_verified"),
        patch("src.lambdas.dashboard.auth._advance_role"),
    ):
        with pytest.raises(IdentityLookupError):
            _run_callback(table)

    # Fail closed: no account created on a transient lookup error.
    assert _count_user_records(inner) == 0
