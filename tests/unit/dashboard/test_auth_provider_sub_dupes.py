# Target: Admin Dashboard (Lambda HTMX) backend auth helpers
"""Feature 1395: deterministic selection among duplicate USER records (FR-002/003/004).

`by_provider_sub` and `by_cognito_sub` are USER-only, so the `Limit=1` footgun did not
cause a false `None` there. But the live table already has up to 10 USER records sharing a
single `sub`, and `Limit=1` returned a NONDETERMINISTIC one, so the resolved `user_id`
flapped across reloads. The fix paginates and selects the earliest-`created_at` record
deterministically (with `user_id` ascending as a stable tiebreak).
"""

from datetime import UTC, datetime, timedelta
from uuid import uuid4

import boto3
from moto import mock_aws

from src.lambdas.dashboard.auth import (
    get_user_by_cognito_sub,
    get_user_by_provider_sub,
)
from src.lambdas.shared.models.user import User

SHARED_SUB = "shared-google-subject-1234567890"


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
            {"AttributeName": "provider_sub", "AttributeType": "S"},
        ],
        GlobalSecondaryIndexes=[
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


def _seed_ten_duplicates(table, *, cognito_sub=None, provider_sub=None):
    """Seed 10 USER records with created_at order deliberately MISMATCHED vs PK order.

    Returns the user_id of the EARLIEST created_at record (the expected canonical pick).
    """
    base = datetime(2026, 1, 1, tzinfo=UTC)
    # user_ids forced into a lexical order that does NOT match created_at order:
    # index 0 gets the earliest created_at but a mid-range user_id, so a naive
    # "lowest PK wins" would pick a different record.
    created_offsets = [0, 5, 2, 9, 1, 7, 3, 8, 4, 6]  # minutes after base
    # Prefix letters chosen so PK sort order != created_at order.
    prefixes = ["m", "a", "z", "b", "y", "c", "x", "d", "w", "e"]

    earliest_user_id = None
    earliest_ca = None
    for prefix, offset in zip(prefixes, created_offsets, strict=True):
        user_id = f"{prefix}-{uuid4()}"
        created_at = base + timedelta(minutes=offset)
        user = User(
            user_id=user_id,
            email=f"{prefix}@example.com",
            cognito_sub=cognito_sub,
            auth_type="google",
            created_at=created_at,
            last_active_at=created_at,
            session_expires_at=created_at + timedelta(days=30),
        )
        item = user.to_dynamodb_item()
        if provider_sub is not None:
            item["provider_sub"] = provider_sub
        table.put_item(Item=item)

        if earliest_ca is None or created_at < earliest_ca:
            earliest_ca = created_at
            earliest_user_id = user_id

    return earliest_user_id


@mock_aws
def test_provider_sub_returns_earliest_created_at_deterministically():
    table = _create_users_table()
    provider_sub = f"google:{SHARED_SUB}"
    expected = _seed_ten_duplicates(table, provider_sub=provider_sub)

    # Deterministic across repeated calls (not moto's lowest-PK).
    resolved_ids = set()
    for _ in range(5):
        result = get_user_by_provider_sub(table, "google", SHARED_SUB)
        assert result is not None
        resolved_ids.add(result.user_id)

    assert resolved_ids == {expected}


@mock_aws
def test_cognito_sub_returns_earliest_created_at_deterministically():
    table = _create_users_table()
    expected = _seed_ten_duplicates(table, cognito_sub=SHARED_SUB)

    resolved_ids = set()
    for _ in range(5):
        result = get_user_by_cognito_sub(table, SHARED_SUB)
        assert result is not None
        resolved_ids.add(result.user_id)

    assert resolved_ids == {expected}
