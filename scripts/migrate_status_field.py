#!/usr/bin/env python3
"""Migration script to convert boolean status fields to string status fields.

This script migrates DynamoDB items from boolean fields (is_active, is_enabled, enabled)
to string status field for GSI query compatibility.

Usage:
    python scripts/migrate_status_field.py --table preprod-sentiment-users --dry-run
    python scripts/migrate_status_field.py --table preprod-sentiment-users
    python scripts/migrate_status_field.py --table preprod-sentiment-users --verify
"""

import argparse
import logging
import sys
from typing import Any

import boto3
from botocore.exceptions import ClientError

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

# Status constants
ACTIVE = "active"
INACTIVE = "inactive"
ENABLED = "enabled"
DISABLED = "disabled"

# Entity type to status mapping
ENTITY_STATUS_MAP = {
    "CONFIGURATION": {
        "true_value": ACTIVE,
        "false_value": INACTIVE,
        "bool_field": "is_active",
    },
    "ALERT_RULE": {
        "true_value": ENABLED,
        "false_value": DISABLED,
        "bool_field": "is_enabled",
    },
    "DIGEST_SETTINGS": {
        "true_value": ENABLED,
        "false_value": DISABLED,
        "bool_field": "enabled",
    },
}


def get_status_from_boolean(item: dict[str, Any], entity_type: str) -> str | None:
    """Convert boolean field to status string based on entity type.

    Args:
        item: DynamoDB item
        entity_type: Entity type (CONFIGURATION, ALERT_RULE, DIGEST_SETTINGS)

    Returns:
        Status string or None if entity type not recognized
    """
    if entity_type not in ENTITY_STATUS_MAP:
        return None

    mapping = ENTITY_STATUS_MAP[entity_type]
    bool_field = mapping["bool_field"]

    # Get boolean value, default to True (active/enabled)
    bool_value = item.get(bool_field, True)

    if bool_value:
        return mapping["true_value"]
    return mapping["false_value"]


def migrate_item(
    table: Any,
    item: dict[str, Any],
    dry_run: bool = False,
) -> bool:
    """Migrate a single item to use status string field.

    Args:
        table: DynamoDB table resource
        item: Item to migrate
        dry_run: If True, don't actually update

    Returns:
        True if migration successful or not needed, False on error
    """
    pk = item.get("PK")
    sk = item.get("SK")
    entity_type = item.get("entity_type")

    if not pk or not sk:
        logger.warning(f"Item missing PK or SK: {item}")
        return False

    if entity_type not in ENTITY_STATUS_MAP:
        logger.debug(f"Skipping non-migratable entity type: {entity_type}")
        return True

    # Check if already has status field
    if "status" in item:
        logger.debug(f"Item already has status: {pk}/{sk}")
        return True

    # Calculate status from boolean
    status = get_status_from_boolean(item, entity_type)
    if not status:
        logger.warning(f"Could not determine status for {pk}/{sk}")
        return False

    if dry_run:
        logger.info(f"[DRY-RUN] Would set status={status} for {entity_type} {pk}/{sk}")
        return True

    # Update item with status field
    try:
        table.update_item(
            Key={"PK": pk, "SK": sk},
            UpdateExpression="SET #status = :status",
            ExpressionAttributeNames={"#status": "status"},
            ExpressionAttributeValues={":status": status},
        )
        logger.info(f"Set status={status} for {entity_type} {pk}/{sk}")
        return True
    except ClientError as e:
        logger.error(f"Failed to update {pk}/{sk}: {e}")
        return False


def scan_and_migrate(
    table: Any,
    entity_types: list[str],
    dry_run: bool = False,
) -> dict[str, int]:
    """Scan table and migrate items of specified entity types.

    Args:
        table: DynamoDB table resource
        entity_types: List of entity types to migrate
        dry_run: If True, don't actually update

    Returns:
        Dictionary with counts: migrated, skipped, errors
    """
    counts = {"migrated": 0, "skipped": 0, "errors": 0, "already_has_status": 0}

    # Build filter expression for entity types
    filter_parts = []
    attr_values = {}
    for i, et in enumerate(entity_types):
        filter_parts.append(f"entity_type = :et{i}")
        attr_values[f":et{i}"] = et

    filter_expression = " OR ".join(filter_parts)

    # Scan with filter
    scan_kwargs = {
        "FilterExpression": filter_expression,
        "ExpressionAttributeValues": attr_values,
    }

    last_evaluated_key = None
    while True:
        if last_evaluated_key:
            scan_kwargs["ExclusiveStartKey"] = last_evaluated_key

        response = table.scan(**scan_kwargs)

        for item in response.get("Items", []):
            if "status" in item:
                counts["already_has_status"] += 1
                continue

            if migrate_item(table, item, dry_run):
                counts["migrated"] += 1
            else:
                counts["errors"] += 1

        last_evaluated_key = response.get("LastEvaluatedKey")
        if not last_evaluated_key:
            break

    return counts


def verify_migration(table: Any, entity_types: list[str]) -> dict[str, int]:
    """Verify all items of specified entity types have status field.

    Args:
        table: DynamoDB table resource
        entity_types: List of entity types to verify

    Returns:
        Dictionary with counts: with_status, without_status, total
    """
    counts = {"with_status": 0, "without_status": 0, "total": 0}

    # Build filter expression for entity types
    filter_parts = []
    attr_values = {}
    for i, et in enumerate(entity_types):
        filter_parts.append(f"entity_type = :et{i}")
        attr_values[f":et{i}"] = et

    filter_expression = " OR ".join(filter_parts)

    # Scan with filter
    scan_kwargs = {
        "FilterExpression": filter_expression,
        "ExpressionAttributeValues": attr_values,
        "ProjectionExpression": "PK, SK, entity_type, #status",
        "ExpressionAttributeNames": {"#status": "status"},
    }

    last_evaluated_key = None
    items_without_status = []

    while True:
        if last_evaluated_key:
            scan_kwargs["ExclusiveStartKey"] = last_evaluated_key

        response = table.scan(**scan_kwargs)

        for item in response.get("Items", []):
            counts["total"] += 1
            if "status" in item:
                counts["with_status"] += 1
            else:
                counts["without_status"] += 1
                items_without_status.append(
                    f"{item.get('entity_type')}: {item.get('PK')}/{item.get('SK')}"
                )

        last_evaluated_key = response.get("LastEvaluatedKey")
        if not last_evaluated_key:
            break

    if items_without_status:
        logger.warning("Items without status field:")
        for item_desc in items_without_status[:10]:  # Show first 10
            logger.warning(f"  - {item_desc}")
        if len(items_without_status) > 10:
            logger.warning(f"  ... and {len(items_without_status) - 10} more")

    return counts


def main() -> int:
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Migrate boolean status fields to string status fields"
    )
    parser.add_argument(
        "--table",
        required=True,
        help="DynamoDB table name",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be done without making changes",
    )
    parser.add_argument(
        "--verify",
        action="store_true",
        help="Verify all items have status field",
    )
    parser.add_argument(
        "--entity-types",
        nargs="+",
        default=["CONFIGURATION", "ALERT_RULE", "DIGEST_SETTINGS"],
        help="Entity types to migrate (default: all)",
    )
    parser.add_argument(
        "--region",
        default="us-east-1",
        help="AWS region (default: us-east-1)",
    )

    args = parser.parse_args()

    # Initialize DynamoDB
    dynamodb = boto3.resource("dynamodb", region_name=args.region)
    table = dynamodb.Table(args.table)

    # Verify table exists
    try:
        table.load()
    except ClientError as e:
        logger.error(f"Failed to access table {args.table}: {e}")
        return 1

    logger.info(f"Working with table: {args.table}")
    logger.info(f"Entity types: {args.entity_types}")

    if args.verify:
        logger.info("Running verification...")
        counts = verify_migration(table, args.entity_types)
        logger.info("Verification results:")
        logger.info(f"  Total items: {counts['total']}")
        logger.info(f"  With status: {counts['with_status']}")
        logger.info(f"  Without status: {counts['without_status']}")

        if counts["without_status"] == 0:
            logger.info("SUCCESS: All items have status field")
            return 0
        else:
            logger.error(
                f"FAILED: {counts['without_status']} items missing status field"
            )
            return 1

    if args.dry_run:
        logger.info("Running in DRY-RUN mode (no changes will be made)")

    counts = scan_and_migrate(table, args.entity_types, args.dry_run)

    logger.info("Migration results:")
    logger.info(f"  Already had status: {counts['already_has_status']}")
    logger.info(f"  Migrated: {counts['migrated']}")
    logger.info(f"  Errors: {counts['errors']}")

    if counts["errors"] > 0:
        logger.error("Some items failed to migrate")
        return 1

    logger.info("Migration completed successfully")
    return 0


if __name__ == "__main__":
    sys.exit(main())
