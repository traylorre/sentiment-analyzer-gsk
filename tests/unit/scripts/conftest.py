# Target: consolidation migration script (Feature 1397)
"""Shared moto fixtures + synthetic seeders for the consolidation script tests.

All identifiers here are SYNTHETIC (uuid4 generated per test) — NEVER the owner's
real cognito_sub / user_id / email (FR-018). The static scan in
``test_consolidate_oauth_duplicates.py`` proves no UUID-shaped literal leaked into
the script source; the synthetic ids live only in these fixtures.
"""

from __future__ import annotations

from uuid import uuid4

import boto3
import pytest
from botocore.exceptions import ClientError
from moto import mock_aws


def make_users_table():
    """Create the single-table users table with the three identity GSIs."""
    resource = boto3.resource("dynamodb", region_name="us-east-1")
    return resource.create_table(
        TableName="preprod-sentiment-users",
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


@pytest.fixture
def dynamodb_table():
    with mock_aws():
        yield make_users_table()


# --- synthetic seeders -----------------------------------------------------


def put_profile(table, user_id, created_at, cognito_sub, email, provider_sub):
    table.put_item(
        Item={
            "PK": f"USER#{user_id}",
            "SK": "PROFILE",
            "entity_type": "USER",
            "user_id": user_id,
            "created_at": created_at,
            "email": email,
            "cognito_sub": cognito_sub,
            "provider_sub": provider_sub,
            "auth_type": "google",
        }
    )


def put_owned(table, user_id, sk, **attrs):
    item = {"PK": f"USER#{user_id}", "SK": sk, "user_id": user_id}
    item.update(attrs)
    table.put_item(Item=item)


def seed_group(table, cognito_sub, created_ats, email=None, provider_sub=None):
    """Seed a duplicate group; returns the generated user_ids in seed order."""
    email = email or f"synthetic-{uuid4().hex[:8]}@example.test"
    provider_sub = provider_sub or f"google-{uuid4().hex}"
    user_ids = []
    for created_at in created_ats:
        uid = str(uuid4())
        put_profile(table, uid, created_at, cognito_sub, email, provider_sub)
        user_ids.append(uid)
    return user_ids, email, provider_sub


def count_user_profiles(table, cognito_sub=None):
    items = table.scan().get("Items", [])
    return sum(
        1
        for i in items
        if i.get("SK") == "PROFILE"
        and (cognito_sub is None or i.get("cognito_sub") == cognito_sub)
    )


# --- test doubles ----------------------------------------------------------


class SpyTable:
    """Delegates to a real moto Table but counts DynamoDB mutations."""

    def __init__(self, inner):
        self._inner = inner
        self.writes = 0

    @property
    def name(self):
        return self._inner.name

    def put_item(self, **kwargs):
        self.writes += 1
        return self._inner.put_item(**kwargs)

    def update_item(self, **kwargs):
        self.writes += 1
        return self._inner.update_item(**kwargs)

    def delete_item(self, **kwargs):
        self.writes += 1
        return self._inner.delete_item(**kwargs)

    def __getattr__(self, name):
        return getattr(self._inner, name)


class FaultTable:
    """Delegates to a real moto Table but raises a throttling error on put_item
    when the item's SK matches ``fail_on_sk`` (used to inject a mid-run failure).
    """

    def __init__(self, inner, fail_on_sk):
        self._inner = inner
        self._fail_on_sk = fail_on_sk

    @property
    def name(self):
        return self._inner.name

    def put_item(self, **kwargs):
        if kwargs.get("Item", {}).get("SK") == self._fail_on_sk:
            raise ClientError(
                {
                    "Error": {
                        "Code": "ProvisionedThroughputExceededException",
                        "Message": "throttled",
                    }
                },
                "PutItem",
            )
        return self._inner.put_item(**kwargs)

    def __getattr__(self, name):
        return getattr(self._inner, name)
