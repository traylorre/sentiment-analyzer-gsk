#!/usr/bin/env python3
"""Audit script: Scan users table for duplicate provider_sub entries (FR-012).

Queries the by_provider_sub GSI and reports any provider_sub values
that are linked to more than one user account.

Usage:
    python scripts/audit_duplicate_provider_subs.py
    python scripts/audit_duplicate_provider_subs.py --table preprod-sentiment-users
    python scripts/audit_duplicate_provider_subs.py --dry-run
"""

import argparse
import os
import sys
from collections import defaultdict

import boto3


def scan_provider_subs(table_name: str, dry_run: bool = False) -> dict[str, list[str]]:
    """Scan by_provider_sub GSI for duplicate entries.

    Returns:
        Dict mapping provider_sub values to lists of user_ids that share them.
        Only includes entries with 2+ users (actual duplicates).
    """
    dynamodb = boto3.resource(
        "dynamodb",
        region_name=os.environ.get("AWS_REGION", "us-east-1"),
    )
    table = dynamodb.Table(table_name)

    provider_sub_to_users: dict[str, list[str]] = defaultdict(list)
    scan_kwargs = {
        "IndexName": "by_provider_sub",
        "ProjectionExpression": "PK, provider_sub",
    }

    if dry_run:
        print(f"[DRY RUN] Would scan table: {table_name}, GSI: by_provider_sub")
        return {}

    print(f"Scanning {table_name} GSI by_provider_sub...")
    total_items = 0

    while True:
        response = table.scan(**scan_kwargs)
        items = response.get("Items", [])
        total_items += len(items)

        for item in items:
            provider_sub = item.get("provider_sub", "")
            user_pk = item.get("PK", "")
            if provider_sub and user_pk:
                # Extract user_id from PK format "USER#<uuid>"
                user_id = (
                    user_pk.replace("USER#", "")
                    if user_pk.startswith("USER#")
                    else user_pk
                )
                provider_sub_to_users[provider_sub].append(user_id)

        # Handle pagination
        last_key = response.get("LastEvaluatedKey")
        if not last_key:
            break
        scan_kwargs["ExclusiveStartKey"] = last_key

    print(f"Scanned {total_items} items.")

    # Filter to only duplicates (2+ users sharing same provider_sub)
    duplicates = {k: v for k, v in provider_sub_to_users.items() if len(v) > 1}
    return duplicates


def main() -> int:
    parser = argparse.ArgumentParser(description="Audit duplicate provider_sub entries")
    parser.add_argument(
        "--table",
        default=os.environ.get("USERS_TABLE", "preprod-sentiment-users"),
        help="DynamoDB table name (default: preprod-sentiment-users)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print what would be scanned without making API calls",
    )
    args = parser.parse_args()

    duplicates = scan_provider_subs(args.table, dry_run=args.dry_run)

    if args.dry_run:
        return 0

    if not duplicates:
        print("\nNo duplicate provider_sub entries found.")
        return 0

    print(f"\nFOUND {len(duplicates)} DUPLICATE PROVIDER_SUB ENTRIES:")
    print("=" * 60)
    for provider_sub, user_ids in sorted(duplicates.items()):
        print(f"\n  provider_sub: {provider_sub}")
        print(f"  shared by {len(user_ids)} users:")
        for uid in user_ids:
            print(f"    - {uid}")
    print("\n" + "=" * 60)
    print("ACTION REQUIRED: Review and resolve these duplicates manually.")
    print("See spec 1222-auth-security-hardening for resolution guidance.")
    return 1


if __name__ == "__main__":
    sys.exit(main())
