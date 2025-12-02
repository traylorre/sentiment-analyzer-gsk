"""Anonymous data merge logic for Feature 006 (T100), Feature 014 (T065-T068).

Merges anonymous user's configurations, alert rules, and preferences
into an authenticated account using tombstone pattern for idempotency.

Feature 014 Enhancements (US5 - Atomic Account Merge):
- FR-013: Merge is idempotent - retrying has no side effects
- FR-014: Tombstone pattern - original items marked, not deleted
- FR-015: Concurrent safety via conditional writes

For On-Call Engineers:
    If merges fail partially:
    1. Check items with merged_to field to see what was transferred
    2. Items use tombstone pattern - original items remain for audit
    3. Merge status tracked in USER record for auditability
    4. Retrying merge is safe - skips already-merged items

Per auth-api.md merge strategy:
1. Configurations: All anonymous configs transferred to authenticated account
2. Alert Rules: All anonymous alerts transferred
3. Preferences: Anonymous preferences preserved (can be overwritten)
"""

import logging
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from botocore.exceptions import ClientError

from src.lambdas.shared.logging_utils import get_safe_error_info, sanitize_for_log

logger = logging.getLogger(__name__)


@dataclass
class MergeResult:
    """Result of data merge operation."""

    status: str  # "completed", "no_data", "partial", "failed"
    merged_at: datetime | None = None
    configurations: int = 0
    alert_rules: int = 0
    preferences: int = 0
    message: str | None = None
    error: str | None = None


def merge_anonymous_data(
    table: Any,
    anonymous_user_id: str,
    authenticated_user_id: str,
) -> MergeResult:
    """Merge anonymous user's data into authenticated account.

    Feature 014 (T065-T068): Uses tombstone pattern for idempotency.
    - Items are marked as merged (not deleted)
    - Already-merged items are skipped
    - Safe for concurrent calls and retries

    Args:
        table: DynamoDB Table resource
        anonymous_user_id: UUID of anonymous user to merge from
        authenticated_user_id: UUID of authenticated user to merge to

    Returns:
        MergeResult with counts and status
    """
    logger.info(
        "Starting data merge",
        extra={
            "anonymous_user_prefix": sanitize_for_log(anonymous_user_id[:8]),
            "authenticated_user_prefix": sanitize_for_log(authenticated_user_id[:8]),
        },
    )

    try:
        # Check if already fully merged (FR-013: idempotent)
        user_status = _check_user_merge_status(table, anonymous_user_id)
        if user_status.get("merged_to") == authenticated_user_id:
            logger.info(
                "Merge already completed",
                extra={
                    "anonymous_user_prefix": sanitize_for_log(anonymous_user_id[:8])
                },
            )
            # Return existing merge info for idempotency
            return _get_existing_merge_result(
                table, anonymous_user_id, authenticated_user_id
            )

        # Check for conflict (merged to different user)
        if (
            user_status.get("merged_to")
            and user_status["merged_to"] != authenticated_user_id
        ):
            logger.warning(
                "Merge conflict - already merged to different user",
                extra={
                    "anonymous_user_prefix": sanitize_for_log(anonymous_user_id[:8])
                },
            )
            return MergeResult(
                status="failed",
                error="merge_conflict",
                message="Session was already merged to a different account",
            )

        # Find all items belonging to anonymous user
        items_to_merge = _query_user_items(table, anonymous_user_id)

        if not items_to_merge:
            logger.info(
                "No data to merge",
                extra={
                    "anonymous_user_prefix": sanitize_for_log(anonymous_user_id[:8])
                },
            )
            return MergeResult(
                status="no_data",
                message="No anonymous data found to merge",
            )

        # Filter out already-merged items (FR-013: skip logic)
        pending_items = [i for i in items_to_merge if not i.get("merged_to")]
        already_merged = len(items_to_merge) - len(pending_items)

        if not pending_items and already_merged > 0:
            # All items already merged
            return _get_existing_merge_result(
                table, anonymous_user_id, authenticated_user_id
            )

        # Categorize pending items
        configs = [i for i in pending_items if i.get("entity_type") == "CONFIGURATION"]
        alerts = [i for i in pending_items if i.get("entity_type") == "ALERT_RULE"]
        preferences = [i for i in pending_items if i.get("entity_type") == "PREFERENCE"]

        # Transfer items using tombstone pattern (FR-014)
        merged_configs = _transfer_items_with_tombstone(
            table, configs, anonymous_user_id, authenticated_user_id
        )
        merged_alerts = _transfer_items_with_tombstone(
            table, alerts, anonymous_user_id, authenticated_user_id
        )
        merged_prefs = _transfer_items_with_tombstone(
            table, preferences, anonymous_user_id, authenticated_user_id
        )

        total_merged = merged_configs + merged_alerts + merged_prefs
        total_pending = len(configs) + len(alerts) + len(preferences)

        # Determine status
        if total_merged == 0 and total_pending > 0:
            status = "failed"
        elif total_merged < total_pending:
            status = "partial"
        else:
            status = "completed"
            # Mark anonymous user as merged only on full completion
            _mark_user_merged(table, anonymous_user_id, authenticated_user_id)

        merged_at = datetime.now(UTC)

        logger.info(
            "Data merge completed",
            extra={
                "status": status,
                "configurations": merged_configs,
                "alert_rules": merged_alerts,
                "preferences": merged_prefs,
                "already_merged": already_merged,
            },
        )

        return MergeResult(
            status=status,
            merged_at=merged_at,
            configurations=merged_configs,
            alert_rules=merged_alerts,
            preferences=merged_prefs,
        )

    except Exception as e:
        logger.error(
            "Data merge failed",
            extra=get_safe_error_info(e),
        )
        return MergeResult(
            status="failed",
            error="merge_failed",
            message="Failed to merge data. Please contact support.",
        )


def _check_user_merge_status(table: Any, user_id: str) -> dict:
    """Check if user has already been merged.

    Returns dict with merged_to and merged_at if already merged.
    """
    try:
        response = table.get_item(
            Key={
                "PK": f"USER#{user_id}",
                "SK": "PROFILE",
            }
        )
        item = response.get("Item", {})
        return {
            "merged_to": item.get("merged_to"),
            "merged_at": item.get("merged_at"),
        }
    except Exception:
        return {}


def _get_existing_merge_result(
    table: Any,
    anonymous_user_id: str,
    authenticated_user_id: str,
) -> MergeResult:
    """Get result for already-merged data (idempotent response)."""
    # Count items that were merged
    items = _query_user_items(table, authenticated_user_id)

    configs = len(
        [
            i
            for i in items
            if i.get("merged_from") == anonymous_user_id
            and i.get("entity_type") == "CONFIGURATION"
        ]
    )
    alerts = len(
        [
            i
            for i in items
            if i.get("merged_from") == anonymous_user_id
            and i.get("entity_type") == "ALERT_RULE"
        ]
    )
    prefs = len(
        [
            i
            for i in items
            if i.get("merged_from") == anonymous_user_id
            and i.get("entity_type") == "PREFERENCE"
        ]
    )

    # Get merge timestamp
    user_status = _check_user_merge_status(table, anonymous_user_id)
    merged_at_str = user_status.get("merged_at")
    merged_at = datetime.fromisoformat(merged_at_str) if merged_at_str else None

    return MergeResult(
        status="already_merged",
        merged_at=merged_at,
        configurations=configs,
        alert_rules=alerts,
        preferences=prefs,
        message="Data was already merged",
    )


def _query_user_items(table: Any, user_id: str) -> list[dict]:
    """Query all items belonging to a user.

    Uses a GSI on user_id if available, otherwise scans with filter.
    """
    items = []

    # Query configurations (PK=USER#{user_id}, SK begins with CONFIG#)
    config_response = table.query(
        KeyConditionExpression="PK = :pk AND begins_with(SK, :sk_prefix)",
        ExpressionAttributeValues={
            ":pk": f"USER#{user_id}",
            ":sk_prefix": "CONFIG#",
        },
    )
    items.extend(config_response.get("Items", []))

    # Query alert rules (PK=USER#{user_id}, SK begins with ALERT#)
    alert_response = table.query(
        KeyConditionExpression="PK = :pk AND begins_with(SK, :sk_prefix)",
        ExpressionAttributeValues={
            ":pk": f"USER#{user_id}",
            ":sk_prefix": "ALERT#",
        },
    )
    items.extend(alert_response.get("Items", []))

    # Query preferences (PK=USER#{user_id}, SK begins with PREF#)
    pref_response = table.query(
        KeyConditionExpression="PK = :pk AND begins_with(SK, :sk_prefix)",
        ExpressionAttributeValues={
            ":pk": f"USER#{user_id}",
            ":sk_prefix": "PREF#",
        },
    )
    items.extend(pref_response.get("Items", []))

    return items


def _transfer_items_with_tombstone(
    table: Any,
    items: list[dict],
    from_user_id: str,
    to_user_id: str,
) -> int:
    """Transfer items using tombstone pattern (FR-014).

    Feature 014 (T065-T068):
    1. Creates new item in target user's namespace
    2. Marks original item as tombstone (merged_to, merged_at)
    3. Uses conditional writes for concurrent safety (FR-015)

    Returns count of successfully transferred items.
    """
    if not items:
        return 0

    transferred = 0

    for item in items:
        try:
            old_pk = item["PK"]
            old_sk = item["SK"]
            now = datetime.now(UTC)

            # Create new item with updated PK
            new_item = dict(item)
            new_item["PK"] = old_pk.replace(from_user_id, to_user_id)
            new_item["user_id"] = to_user_id
            new_item["merged_from"] = from_user_id
            new_item["merged_at"] = now.isoformat()

            # Write new item with condition (FR-015: concurrent safety)
            # Prevents duplicate if concurrent merge
            try:
                table.put_item(
                    Item=new_item,
                    ConditionExpression="attribute_not_exists(PK)",
                )
            except ClientError as e:
                if e.response["Error"]["Code"] == "ConditionalCheckFailedException":
                    # Item already exists - likely concurrent merge
                    logger.info(
                        "Item already transferred (concurrent merge)",
                        extra={"pk": sanitize_for_log(new_item["PK"][:20])},
                    )
                    # Mark original as tombstone anyway
                else:
                    raise

            # Mark original as tombstone (FR-014)
            # Uses conditional to ensure idempotency
            try:
                table.update_item(
                    Key={
                        "PK": old_pk,
                        "SK": old_sk,
                    },
                    UpdateExpression="SET merged_to = :merged_to, merged_at = :merged_at",
                    ConditionExpression="attribute_not_exists(merged_to)",
                    ExpressionAttributeValues={
                        ":merged_to": to_user_id,
                        ":merged_at": now.isoformat(),
                    },
                )
            except ClientError as e:
                if e.response["Error"]["Code"] == "ConditionalCheckFailedException":
                    # Already marked as tombstone - idempotent
                    logger.info(
                        "Item already marked as tombstone",
                        extra={"pk": sanitize_for_log(old_pk[:20])},
                    )
                else:
                    raise

            transferred += 1

        except Exception as e:
            logger.warning(
                "Failed to transfer item",
                extra={
                    "pk": sanitize_for_log(item.get("PK", "")[:20]),
                    **get_safe_error_info(e),
                },
            )

    return transferred


def _transfer_items(
    table: Any,
    items: list[dict],
    from_user_id: str,
    to_user_id: str,
) -> int:
    """Transfer items from one user to another (legacy method).

    DEPRECATED: Use _transfer_items_with_tombstone for Feature 014.
    Kept for backward compatibility.

    Creates new items with updated PK, deletes old items.
    Returns count of successfully transferred items.
    """
    if not items:
        return 0

    transferred = 0

    for item in items:
        try:
            old_pk = item["PK"]
            old_sk = item["SK"]

            # Create new item with updated PK
            new_item = dict(item)
            new_item["PK"] = old_pk.replace(from_user_id, to_user_id)
            new_item["user_id"] = to_user_id
            new_item["merged_from"] = from_user_id
            new_item["merged_at"] = datetime.now(UTC).isoformat()

            # Write new item
            table.put_item(Item=new_item)

            # Delete old item
            table.delete_item(
                Key={
                    "PK": old_pk,
                    "SK": old_sk,
                }
            )

            transferred += 1

        except Exception as e:
            logger.warning(
                "Failed to transfer item",
                extra={
                    "pk": sanitize_for_log(item.get("PK", "")[:20]),
                    **get_safe_error_info(e),
                },
            )

    return transferred


def _mark_user_merged(
    table: Any, anonymous_user_id: str, merged_to_user_id: str
) -> None:
    """Mark anonymous user as merged.

    Updates the user record to indicate it was merged and when.
    """
    try:
        table.update_item(
            Key={
                "PK": f"USER#{anonymous_user_id}",
                "SK": "PROFILE",
            },
            UpdateExpression="SET merged_to = :merged_to, merged_at = :merged_at",
            ExpressionAttributeValues={
                ":merged_to": merged_to_user_id,
                ":merged_at": datetime.now(UTC).isoformat(),
            },
        )
    except Exception as e:
        # Non-critical - log but don't fail
        logger.warning(
            "Failed to mark user as merged",
            extra=get_safe_error_info(e),
        )


def get_merge_status(
    table: Any,
    authenticated_user_id: str,
    anonymous_user_id: str,
) -> MergeResult:
    """Check if merge has already been performed.

    Args:
        table: DynamoDB Table resource
        authenticated_user_id: UUID of authenticated user
        anonymous_user_id: UUID of anonymous user

    Returns:
        MergeResult with status and counts
    """
    try:
        # Check if anonymous user was merged
        response = table.get_item(
            Key={
                "PK": f"USER#{anonymous_user_id}",
                "SK": "PROFILE",
            }
        )

        item = response.get("Item")
        if not item:
            return MergeResult(
                status="no_data",
                message="No anonymous data found to merge",
            )

        # Check if already merged
        merged_to = item.get("merged_to")
        if merged_to:
            merged_at_str = item.get("merged_at")
            merged_at = datetime.fromisoformat(merged_at_str) if merged_at_str else None

            # Count items that were merged
            items = _query_user_items(table, authenticated_user_id)
            configs = len(
                [
                    i
                    for i in items
                    if i.get("merged_from") == anonymous_user_id
                    and i.get("entity_type") == "CONFIGURATION"
                ]
            )
            alerts = len(
                [
                    i
                    for i in items
                    if i.get("merged_from") == anonymous_user_id
                    and i.get("entity_type") == "ALERT_RULE"
                ]
            )
            prefs = len(
                [
                    i
                    for i in items
                    if i.get("merged_from") == anonymous_user_id
                    and i.get("entity_type") == "PREFERENCE"
                ]
            )

            return MergeResult(
                status="completed",
                merged_at=merged_at,
                configurations=configs,
                alert_rules=alerts,
                preferences=prefs,
            )

        # Not yet merged - check if there's data to merge
        items = _query_user_items(table, anonymous_user_id)
        if not items:
            return MergeResult(
                status="no_data",
                message="No anonymous data found to merge",
            )

        return MergeResult(
            status="pending",
            message="Data available for merge",
        )

    except Exception as e:
        logger.error(
            "Failed to get merge status",
            extra=get_safe_error_info(e),
        )
        return MergeResult(
            status="failed",
            error="status_check_failed",
            message="Failed to check merge status.",
        )
