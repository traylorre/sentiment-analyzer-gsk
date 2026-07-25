# Target: Admin Dashboard (Lambda HTMX) backend auth helpers
"""Feature 1395 FR-005: WARN when >1 USER is found under one identity key.

The log must be sanitized: it carries the identity-key type, a truncated key prefix, and
the count — never the raw email or full sub.
"""

import logging
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import boto3
from moto import mock_aws

from src.lambdas.dashboard.auth import get_user_by_cognito_sub
from src.lambdas.shared.models.user import User

FULL_SUB = "very-secret-cognito-subject-should-not-be-logged-in-full"


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
            {"AttributeName": "cognito_sub", "AttributeType": "S"},
        ],
        GlobalSecondaryIndexes=[
            {
                "IndexName": "by_cognito_sub",
                "KeySchema": [{"AttributeName": "cognito_sub", "KeyType": "HASH"}],
                "Projection": {"ProjectionType": "ALL"},
            },
        ],
        BillingMode="PAY_PER_REQUEST",
    )


def _seed_user(table, *, cognito_sub, created_at):
    user = User(
        user_id=str(uuid4()),
        email=f"{uuid4()}@example.com",
        cognito_sub=cognito_sub,
        auth_type="google",
        created_at=created_at,
        last_active_at=created_at,
        session_expires_at=created_at + timedelta(days=30),
    )
    table.put_item(Item=user.to_dynamodb_item())


@mock_aws
def test_warns_on_multiple_users_without_leaking_full_sub(caplog):
    table = _create_users_table()
    now = datetime.now(UTC)
    _seed_user(table, cognito_sub=FULL_SUB, created_at=now)
    _seed_user(table, cognito_sub=FULL_SUB, created_at=now + timedelta(minutes=1))
    _seed_user(table, cognito_sub=FULL_SUB, created_at=now + timedelta(minutes=2))

    with caplog.at_level(logging.WARNING, logger="src.lambdas.dashboard.auth"):
        result = get_user_by_cognito_sub(table, FULL_SUB)

    assert result is not None

    warnings = [
        r
        for r in caplog.records
        if r.levelno == logging.WARNING and "Multiple USER records" in r.getMessage()
    ]
    assert len(warnings) == 1
    record = warnings[0]
    assert getattr(record, "count", None) == 3
    assert getattr(record, "identity_key", None) == "cognito_sub"
    # The full sub must never appear in the structured log fields.
    assert FULL_SUB not in str(getattr(record, "key_prefix", ""))


@mock_aws
def test_no_warning_for_single_user(caplog):
    table = _create_users_table()
    _seed_user(table, cognito_sub="unique-sub", created_at=datetime.now(UTC))

    with caplog.at_level(logging.WARNING, logger="src.lambdas.dashboard.auth"):
        result = get_user_by_cognito_sub(table, "unique-sub")

    assert result is not None
    assert not [r for r in caplog.records if "Multiple USER records" in r.getMessage()]
