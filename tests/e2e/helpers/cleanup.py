# Cleanup Helpers
#
# Utilities for cleaning up test data after E2E test runs.
# Ensures test isolation and prevents data accumulation in preprod.

import os
from contextlib import suppress
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

import boto3


@dataclass
class OrphanedTestData:
    """Represents orphaned test data found during cleanup scan."""

    table_name: str
    pk: str
    sk: str
    created_at: datetime | None
    test_run_id: str


def get_dynamodb_resource():
    """Get DynamoDB resource."""
    return boto3.resource(
        "dynamodb",
        region_name=os.environ.get("AWS_REGION", "us-east-1"),
    )


def get_dynamodb_table(table_name: str | None = None):
    """Get DynamoDB table resource.

    Args:
        table_name: Table name (default: from DYNAMODB_TABLE env var)

    Returns:
        DynamoDB Table resource
    """
    dynamodb = get_dynamodb_resource()
    name = table_name or os.environ.get("DYNAMODB_TABLE", "sentiment-analyzer-preprod")
    return dynamodb.Table(name)


async def cleanup_by_prefix(
    test_run_id: str,
    table_name: str | None = None,
) -> int:
    """Delete all DynamoDB items with keys containing the test run ID prefix.

    Args:
        test_run_id: Test run ID prefix (e.g., "e2e-abc12345")
        table_name: DynamoDB table name

    Returns:
        Number of items deleted
    """
    table = get_dynamodb_table(table_name)
    deleted_count = 0

    # Scan for items with test run ID in pk or sk
    # This is expensive but necessary for test cleanup
    scan_kwargs = {
        "FilterExpression": "contains(pk, :prefix) OR contains(sk, :prefix)",
        "ExpressionAttributeValues": {":prefix": test_run_id},
        "ProjectionExpression": "pk, sk",
    }

    while True:
        response = table.scan(**scan_kwargs)

        items = response.get("Items", [])
        for item in items:
            table.delete_item(Key={"pk": item["pk"], "sk": item["sk"]})
            deleted_count += 1

        if "LastEvaluatedKey" not in response:
            break
        scan_kwargs["ExclusiveStartKey"] = response["LastEvaluatedKey"]

    return deleted_count


async def find_orphaned_test_data(
    max_age_hours: int = 24,
    table_name: str | None = None,
) -> list[OrphanedTestData]:
    """Find test data older than specified age.

    Scans for items with "e2e-" or "test-" prefixes that are older
    than max_age_hours, indicating they were not properly cleaned up.

    Args:
        max_age_hours: Age threshold in hours
        table_name: DynamoDB table name

    Returns:
        List of OrphanedTestData found
    """
    table = get_dynamodb_table(table_name)
    orphaned = []
    cutoff = datetime.now(UTC) - timedelta(hours=max_age_hours)
    cutoff_iso = cutoff.isoformat()

    # Scan for items with test prefixes
    scan_kwargs = {
        "FilterExpression": (
            "(begins_with(pk, :e2e) OR begins_with(pk, :test)) "
            "AND (attribute_not_exists(created_at) OR created_at < :cutoff)"
        ),
        "ExpressionAttributeValues": {
            ":e2e": "e2e-",
            ":test": "test-",
            ":cutoff": cutoff_iso,
        },
        "ProjectionExpression": "pk, sk, created_at",
    }

    while True:
        response = table.scan(**scan_kwargs)

        for item in response.get("Items", []):
            pk = item["pk"]
            # Extract test run ID from pk
            test_run_id = pk.split("#")[0] if "#" in pk else pk[:12]

            created_at = None
            if "created_at" in item:
                with suppress(ValueError, TypeError):
                    created_at = datetime.fromisoformat(item["created_at"])

            orphaned.append(
                OrphanedTestData(
                    table_name=table.table_name,
                    pk=pk,
                    sk=item["sk"],
                    created_at=created_at,
                    test_run_id=test_run_id,
                )
            )

        if "LastEvaluatedKey" not in response:
            break
        scan_kwargs["ExclusiveStartKey"] = response["LastEvaluatedKey"]

    return orphaned


async def cleanup_orphaned_data(
    max_age_hours: int = 24,
    table_name: str | None = None,
    dry_run: bool = True,
) -> tuple[int, list[OrphanedTestData]]:
    """Find and optionally delete orphaned test data.

    Args:
        max_age_hours: Age threshold for considering data orphaned
        table_name: DynamoDB table name
        dry_run: If True, only report without deleting

    Returns:
        Tuple of (count_deleted, list_of_orphaned_items)
    """
    orphaned = await find_orphaned_test_data(max_age_hours, table_name)

    if dry_run:
        return (0, orphaned)

    table = get_dynamodb_table(table_name)
    deleted = 0
    for item in orphaned:
        table.delete_item(Key={"pk": item.pk, "sk": item.sk})
        deleted += 1

    return (deleted, orphaned)


async def cleanup_test_user(
    user_id: str,
    table_name: str | None = None,
) -> int:
    """Delete all data associated with a test user.

    Removes user profile, configurations, alerts, and notifications.

    Args:
        user_id: User ID to clean up
        table_name: DynamoDB table name

    Returns:
        Number of items deleted
    """
    table = get_dynamodb_table(table_name)
    deleted_count = 0

    # Query all items for this user
    response = table.query(
        KeyConditionExpression="pk = :pk",
        ExpressionAttributeValues={":pk": f"USER#{user_id}"},
    )

    for item in response.get("Items", []):
        table.delete_item(Key={"pk": item["pk"], "sk": item["sk"]})
        deleted_count += 1

    # Also clean up any configs owned by this user
    # Configs have their own pk pattern but reference user_id
    scan_kwargs = {
        "FilterExpression": "user_id = :uid",
        "ExpressionAttributeValues": {":uid": user_id},
        "ProjectionExpression": "pk, sk",
    }

    response = table.scan(**scan_kwargs)
    for item in response.get("Items", []):
        table.delete_item(Key={"pk": item["pk"], "sk": item["sk"]})
        deleted_count += 1

    return deleted_count


async def cleanup_test_config(
    config_id: str,
    table_name: str | None = None,
) -> int:
    """Delete a configuration and all associated alerts.

    Args:
        config_id: Configuration ID to clean up
        table_name: DynamoDB table name

    Returns:
        Number of items deleted
    """
    table = get_dynamodb_table(table_name)
    deleted_count = 0

    # Query all items for this config (config + alerts)
    response = table.query(
        KeyConditionExpression="pk = :pk",
        ExpressionAttributeValues={":pk": f"CONFIG#{config_id}"},
    )

    for item in response.get("Items", []):
        table.delete_item(Key={"pk": item["pk"], "sk": item["sk"]})
        deleted_count += 1

    return deleted_count
