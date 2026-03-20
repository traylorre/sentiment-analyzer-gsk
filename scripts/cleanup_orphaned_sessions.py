#!/usr/bin/env python3
"""One-time cleanup script for orphaned anonymous sessions.

Root cause: DynamoDB TTL was configured on `ttl_timestamp` (Terraform), but
anonymous session creation code wrote the TTL value to `ttl` instead. Result:
DynamoDB TTL never fired and ~110K anonymous sessions accumulated.

This script scans the users table for anonymous sessions and sets their
`ttl_timestamp` to 0 (Unix epoch), causing DynamoDB TTL to delete them
within 48 hours.

Usage:
    # Dry run (count only, no modifications)
    python scripts/cleanup_orphaned_sessions.py --dry-run

    # Execute cleanup on preprod
    python scripts/cleanup_orphaned_sessions.py --table-name preprod-sentiment-users

    # Execute cleanup on prod
    python scripts/cleanup_orphaned_sessions.py --table-name prod-sentiment-users
"""

import argparse
import logging
import sys
import time

import boto3
from boto3.dynamodb.conditions import Attr

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
logger = logging.getLogger("cleanup_orphaned_sessions")

DEFAULT_TABLE_NAME = "preprod-sentiment-users"


def scan_anonymous_sessions(table, *, dry_run: bool) -> int:
    """Scan for anonymous sessions and set ttl_timestamp to 0 for deletion.

    Args:
        table: boto3 DynamoDB Table resource.
        dry_run: If True, count items without modifying.

    Returns:
        Total number of anonymous sessions found.
    """
    total_found = 0
    total_updated = 0
    last_evaluated_key = None

    logger.info(
        "Starting scan for auth_type='anonymous' items%s",
        " (DRY RUN)" if dry_run else "",
    )

    while True:
        scan_kwargs = {
            "FilterExpression": Attr("auth_type").eq("anonymous"),
            "ProjectionExpression": "PK, SK",
        }
        if last_evaluated_key:
            scan_kwargs["ExclusiveStartKey"] = last_evaluated_key

        response = table.scan(**scan_kwargs)
        items = response.get("Items", [])
        total_found += len(items)

        if not dry_run and items:
            for item in items:
                try:
                    table.update_item(
                        Key={"PK": item["PK"], "SK": item["SK"]},
                        UpdateExpression="SET #ttl = :zero",
                        ExpressionAttributeNames={"#ttl": "ttl_timestamp"},
                        ExpressionAttributeValues={":zero": 0},
                    )
                    total_updated += 1
                except Exception:
                    logger.exception(
                        "Failed to update item PK=%s SK=%s",
                        item["PK"],
                        item["SK"],
                    )

        # Log progress every 1000 items
        prev_milestone = (total_found - len(items)) // 1000
        curr_milestone = total_found // 1000
        if curr_milestone > prev_milestone:
            if dry_run:
                logger.info("Progress: %d anonymous sessions found so far", total_found)
            else:
                logger.info(
                    "Progress: %d found, %d updated so far",
                    total_found,
                    total_updated,
                )

        last_evaluated_key = response.get("LastEvaluatedKey")
        if not last_evaluated_key:
            break

    return total_found


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Clean up orphaned anonymous sessions by setting ttl_timestamp=0 for DynamoDB TTL deletion.",
    )
    parser.add_argument(
        "--table-name",
        default=DEFAULT_TABLE_NAME,
        help=f"DynamoDB table name (default: {DEFAULT_TABLE_NAME})",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Count anonymous sessions without modifying them",
    )
    parser.add_argument(
        "--region",
        default="us-east-1",
        help="AWS region (default: us-east-1)",
    )

    args = parser.parse_args()

    dynamodb = boto3.resource("dynamodb", region_name=args.region)
    table = dynamodb.Table(args.table_name)

    logger.info("Table: %s (region: %s)", args.table_name, args.region)

    start_time = time.monotonic()
    total = scan_anonymous_sessions(table, dry_run=args.dry_run)
    elapsed = time.monotonic() - start_time

    if args.dry_run:
        logger.info(
            "DRY RUN complete: %d anonymous sessions found in %.1fs",
            total,
            elapsed,
        )
        logger.info(
            "Run without --dry-run to set ttl_timestamp=0 on these items. "
            "DynamoDB TTL will delete them within 48 hours.",
        )
    else:
        logger.info(
            "Cleanup complete: %d anonymous sessions marked for TTL deletion in %.1fs",
            total,
            elapsed,
        )
        logger.info(
            "DynamoDB will delete these items within 48 hours.",
        )

    return 0


if __name__ == "__main__":
    sys.exit(main())
