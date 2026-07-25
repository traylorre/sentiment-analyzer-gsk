# Target: Admin Dashboard (Lambda HTMX) backend auth helpers
"""Feature 1395: reproduce and fix the `Limit=1 + FilterExpression` footgun on by_email.

The `by_email` GSI is polluted by NOTIFICATION and MAGIC_LINK_TOKEN records that also
carry an `email` attribute. DynamoDB applies `Limit` to the key-matched items BEFORE the
`FilterExpression` runs, so with `Limit=1` a non-USER item that sorts first returns a
single item, the `entity_type = USER` filter drops it, and the helper returns `None` even
though a USER exists — minting a duplicate user on the next OAuth login.

These tests prove the fixed helper paginates the full key match and returns the USER.
"""

from datetime import UTC, datetime, timedelta
from uuid import uuid4

import boto3
from moto import mock_aws

from src.lambdas.dashboard.auth import get_user_by_email_gsi
from src.lambdas.shared.models.user import User

EMAIL = "polluted.user@example.com"


def _make_user_item(email: str, *, created_at: datetime) -> dict:
    user = User(
        user_id=str(uuid4()),
        email=email,
        auth_type="google",
        created_at=created_at,
        last_active_at=created_at,
        session_expires_at=created_at + timedelta(days=30),
    )
    return user.to_dynamodb_item()


def _notification_item(email: str) -> dict:
    return {
        "PK": f"USER#{uuid4()}",
        "SK": f"NOTIF#{datetime.now(UTC).isoformat()}",
        "email": email,
        "entity_type": "NOTIFICATION",
        "message": "You have a new alert",
    }


def _magic_link_item(email: str) -> dict:
    return {
        "PK": f"TOKEN#{uuid4()}",
        "SK": "TOKEN",
        "email": email,
        "entity_type": "MAGIC_LINK_TOKEN",
    }


def _create_users_table():
    client = boto3.resource("dynamodb", region_name="us-east-1")
    table = client.create_table(
        TableName="test-users",
        KeySchema=[
            {"AttributeName": "PK", "KeyType": "HASH"},
            {"AttributeName": "SK", "KeyType": "RANGE"},
        ],
        AttributeDefinitions=[
            {"AttributeName": "PK", "AttributeType": "S"},
            {"AttributeName": "SK", "AttributeType": "S"},
            {"AttributeName": "email", "AttributeType": "S"},
        ],
        GlobalSecondaryIndexes=[
            {
                "IndexName": "by_email",
                "KeySchema": [{"AttributeName": "email", "KeyType": "HASH"}],
                "Projection": {"ProjectionType": "ALL"},
            },
        ],
        BillingMode="PAY_PER_REQUEST",
    )
    return table


class _LimitBeforeFilterTable:
    """Faithful emulation of DynamoDB query for a hash-only GSI.

    * The KeyConditionExpression matches every seeded item (all share the hash key).
    * `Limit` caps the number of KEY-matched items read per page, applied BEFORE the
      `FilterExpression` — this is the real footgun.
    * `entity_type = :type` is applied AFTER the limit.
    * Pagination uses ExclusiveStartKey / LastEvaluatedKey with an index cursor, and
      LastEvaluatedKey is present whenever more key-matched items remain — even if the
      page filtered to empty (exactly the condition the old code misread as "no user").
    """

    def __init__(self, ordered_items: list[dict]):
        self._items = ordered_items

    def query(self, **kwargs):
        values = kwargs["ExpressionAttributeValues"]
        wanted_type = values[":type"]
        limit = kwargs.get("Limit")
        start = kwargs.get("ExclusiveStartKey")
        idx = start["_i"] if start else 0
        remaining = self._items[idx:]
        read = remaining if limit is None else remaining[:limit]
        next_idx = idx + len(read)
        result = {
            "Items": [i for i in read if i.get("entity_type") == wanted_type],
        }
        if next_idx < len(self._items):
            result["LastEvaluatedKey"] = {"_i": next_idx}
        return result


@mock_aws
def test_returns_user_when_notification_and_magic_link_share_email():
    """SC-2: USER is found even when NOTIFICATION and MAGIC_LINK_TOKEN share the email."""
    table = _create_users_table()
    user_item = _make_user_item(EMAIL, created_at=datetime.now(UTC))
    table.put_item(Item=user_item)
    table.put_item(Item=_notification_item(EMAIL))
    table.put_item(Item=_magic_link_item(EMAIL))

    result = get_user_by_email_gsi(table, EMAIL)

    assert result is not None
    assert result.user_id == user_item["user_id"]
    assert result.entity_type == "USER"


def test_old_limit1_path_returns_none_but_fixed_helper_finds_user():
    """The footgun proof: a non-USER item sorting first defeats `Limit=1`.

    With the emulated Limit-before-filter table, a raw `Limit=1` query returns the
    NOTIFICATION item, which the `entity_type = USER` filter drops -> Items == [] with a
    LastEvaluatedKey set. That is exactly what the pre-fix helper misread as "no user".
    The fixed helper paginates the full key match and returns the USER.
    """
    now = datetime.now(UTC)
    user_item = _make_user_item(EMAIL, created_at=now)
    # Non-USER items ordered FIRST so Limit=1 reads one of them.
    ordered = [
        _notification_item(EMAIL),
        _magic_link_item(EMAIL),
        user_item,
    ]
    table = _LimitBeforeFilterTable(ordered)

    # Demonstrate the old-code condition: Limit=1 -> filtered-empty page + a cursor.
    old_page = table.query(
        IndexName="by_email",
        KeyConditionExpression="email = :email",
        FilterExpression="entity_type = :type",
        ExpressionAttributeValues={":email": EMAIL, ":type": "USER"},
        Limit=1,
    )
    assert old_page["Items"] == []
    assert "LastEvaluatedKey" in old_page  # old code ignored this -> false None

    # The fixed helper (no Limit, full pagination) returns the USER.
    result = get_user_by_email_gsi(table, EMAIL)
    assert result is not None
    assert result.user_id == user_item["user_id"]
