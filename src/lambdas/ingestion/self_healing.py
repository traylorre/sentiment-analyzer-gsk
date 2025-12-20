"""
Self-Healing Module for Ingestion Pipeline
==========================================

Detects and republishes stale pending items that were ingested but never
analyzed (no sentiment attribute). This ensures the dashboard shows
up-to-date data even when items fail initial SNS publication.

For On-Call Engineers:
    This module runs automatically as part of each ingestion Lambda invocation.

    Self-healing will:
    - Query by_status GSI for items with status="pending"
    - Filter to items older than SELF_HEALING_THRESHOLD_HOURS (default: 1 hour)
    - Exclude items that already have a sentiment attribute
    - Republish stale items to SNS for analysis

    If you see high SelfHealingItemsRepublished metrics:
    - Check Analysis Lambda health (is it processing SNS messages?)
    - Check SNS subscription is active
    - Check for Analysis Lambda errors in CloudWatch

    Quick commands:
    # Check stale items count
    aws dynamodb query --table-name ${env}-sentiment-items \\
      --index-name by_status \\
      --key-condition-expression "status = :s" \\
      --expression-attribute-values '{":s": {"S": "pending"}}' \\
      --select COUNT

For Developers:
    Self-healing workflow:
    1. Query by_status GSI for pending items older than threshold
    2. Batch GetItem to fetch full item data (GSI is KEYS_ONLY)
    3. Filter out items that have sentiment (already analyzed)
    4. Batch publish to SNS analysis topic
    5. Log and emit metrics

    Key functions:
    - run_self_healing_check(): Main entry point, called from handler
    - query_stale_pending_items(): Query GSI for stale pending items
    - get_full_items(): Batch GetItem for KEYS_ONLY GSI results
    - republish_items_to_sns(): Batch publish items to SNS
"""

import json
import logging
import os
import time
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from typing import Any

from aws_xray_sdk.core import xray_recorder

from src.lambdas.shared.logging_utils import get_safe_error_info, sanitize_for_log
from src.lib.metrics import emit_metric

# Structured logging
logger = logging.getLogger(__name__)

# Configuration constants
SELF_HEALING_THRESHOLD_HOURS = int(os.environ.get("SELF_HEALING_THRESHOLD_HOURS", "1"))
SELF_HEALING_BATCH_SIZE = int(os.environ.get("SELF_HEALING_BATCH_SIZE", "100"))

# SNS batch limit (AWS maximum)
SNS_BATCH_SIZE = 10


@dataclass
class SelfHealingResult:
    """Result of a self-healing check.

    Attributes:
        items_found: Number of stale pending items detected
        items_republished: Number of items successfully republished to SNS
        errors: List of error messages encountered
        execution_time_ms: Time taken for self-healing check
    """

    items_found: int = 0
    items_republished: int = 0
    errors: list[str] = field(default_factory=list)
    execution_time_ms: float = 0.0


@xray_recorder.capture("query_stale_pending_items")
def query_stale_pending_items(
    table: Any,
    threshold_hours: int = SELF_HEALING_THRESHOLD_HOURS,
    limit: int = SELF_HEALING_BATCH_SIZE,
) -> list[dict[str, Any]]:
    """Query by_status GSI for pending items older than threshold.

    Uses the by_status GSI which has KEYS_ONLY projection, returning
    only source_id, status, and timestamp. Caller must use get_full_items()
    to fetch complete item data for republishing.

    Args:
        table: DynamoDB Table resource
        threshold_hours: Hours before an item is considered stale
        limit: Maximum items to return (default: 100)

    Returns:
        List of item keys (source_id, timestamp) for stale pending items
    """
    threshold = datetime.now(UTC) - timedelta(hours=threshold_hours)
    threshold_iso = threshold.isoformat()

    stale_items: list[dict[str, Any]] = []

    try:
        # Query GSI for pending items older than threshold
        response = table.query(
            IndexName="by_status",
            KeyConditionExpression="#status = :status AND #ts < :threshold",
            ExpressionAttributeNames={
                "#status": "status",
                "#ts": "timestamp",
            },
            ExpressionAttributeValues={
                ":status": "pending",
                ":threshold": threshold_iso,
            },
            Limit=limit,
        )

        stale_items.extend(response.get("Items", []))

        # Handle pagination if needed (but respect limit)
        while "LastEvaluatedKey" in response and len(stale_items) < limit:
            remaining = limit - len(stale_items)
            response = table.query(
                IndexName="by_status",
                KeyConditionExpression="#status = :status AND #ts < :threshold",
                ExpressionAttributeNames={
                    "#status": "status",
                    "#ts": "timestamp",
                },
                ExpressionAttributeValues={
                    ":status": "pending",
                    ":threshold": threshold_iso,
                },
                Limit=remaining,
                ExclusiveStartKey=response["LastEvaluatedKey"],
            )
            stale_items.extend(response.get("Items", []))

        logger.debug(
            "Queried stale pending items",
            extra={
                "items_found": len(stale_items),
                "threshold_iso": threshold_iso,
            },
        )

    except Exception as e:
        logger.error(
            "Failed to query stale pending items",
            extra=get_safe_error_info(e),
        )
        raise

    return stale_items[:limit]  # Ensure we don't exceed limit


@xray_recorder.capture("get_full_items")
def get_full_items(
    table: Any,
    item_keys: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Fetch full item data for items returned from KEYS_ONLY GSI.

    The by_status GSI only returns source_id, status, and timestamp.
    This function fetches the complete item data needed for republishing
    (text_for_analysis, matched_tickers, source_type, etc.).

    Items with a 'sentiment' attribute are filtered out (already analyzed).

    Args:
        table: DynamoDB Table resource
        item_keys: List of items with source_id from GSI query

    Returns:
        List of full items that don't have sentiment attribute
    """
    if not item_keys:
        return []

    full_items: list[dict[str, Any]] = []

    for item in item_keys:
        source_id = item.get("source_id")
        timestamp = item.get("timestamp")

        # Both keys required for composite primary key
        if not source_id or not timestamp:
            logger.warning(
                "Skipping item missing required keys",
                extra={
                    "has_source_id": bool(source_id),
                    "has_timestamp": bool(timestamp),
                },
            )
            continue

        try:
            response = table.get_item(
                Key={"source_id": source_id, "timestamp": timestamp},
                ProjectionExpression=(
                    "source_id, source_type, text_for_analysis, "
                    "matched_tickers, sentiment, metadata"
                ),
            )

            full_item = response.get("Item")
            if full_item:
                # Filter out items that already have sentiment (already analyzed)
                if "sentiment" not in full_item:
                    full_items.append(full_item)
                else:
                    logger.debug(
                        "Skipping item with sentiment",
                        extra={"source_id": sanitize_for_log(source_id[:20])},
                    )

        except Exception as e:
            logger.warning(
                "Failed to get full item",
                extra={
                    "source_id": sanitize_for_log(source_id[:20]),
                    **get_safe_error_info(e),
                },
            )
            continue

    return full_items


@xray_recorder.capture("republish_items_to_sns")
def republish_items_to_sns(
    sns_client: Any,
    sns_topic_arn: str,
    items: list[dict[str, Any]],
    model_version: str = "v1.0.0",
) -> int:
    """Batch publish stale items to SNS for reanalysis.

    Uses the same message format as normal ingestion to ensure
    compatibility with the Analysis Lambda.

    Args:
        sns_client: boto3 SNS client
        sns_topic_arn: ARN of the analysis SNS topic
        items: List of full item data to republish
        model_version: Model version for analysis

    Returns:
        Number of successfully published messages
    """
    if not items or not sns_topic_arn:
        return 0

    success_count = 0

    # Process in batches of SNS_BATCH_SIZE
    for i in range(0, len(items), SNS_BATCH_SIZE):
        batch = items[i : i + SNS_BATCH_SIZE]

        # Build batch entries
        entries = []
        for idx, item in enumerate(batch):
            message_body = {
                "source_id": item.get("source_id", ""),
                "source_type": item.get("source_type", "unknown"),
                "text_for_analysis": item.get("text_for_analysis", ""),
                "model_version": model_version,
                "matched_tickers": item.get("matched_tickers", []),
                "timestamp": item.get("timestamp", ""),
                "republished": True,  # Mark as republished for observability
            }

            entry = {
                "Id": str(i + idx),
                "Message": json.dumps(message_body),
                "MessageAttributes": {
                    "source_type": {
                        "DataType": "String",
                        "StringValue": item.get("source_type", "unknown"),
                    },
                    "republished": {
                        "DataType": "String",
                        "StringValue": "true",
                    },
                },
            }
            entries.append(entry)

        try:
            response = sns_client.publish_batch(
                TopicArn=sns_topic_arn,
                PublishBatchRequestEntries=entries,
            )

            success_count += len(response.get("Successful", []))

            for failure in response.get("Failed", []):
                logger.warning(
                    "SNS republish partial failure",
                    extra={
                        "entry_id": failure.get("Id"),
                        "code": failure.get("Code"),
                        "message": sanitize_for_log(failure.get("Message", "")[:100]),
                    },
                )

        except Exception as e:
            # TEMPORARY DEBUG: Log full exception for diagnosis
            logger.error(
                "SNS batch republish failed",
                extra={
                    "batch_size": len(batch),
                    "error_message": str(e)[:500],  # Full error for debugging
                    **get_safe_error_info(e),
                },
            )

    return success_count


def run_self_healing_check(
    table: Any,
    sns_client: Any,
    sns_topic_arn: str,
    model_version: str = "v1.0.0",
) -> SelfHealingResult:
    """Execute self-healing check and republish stale items.

    This is the main entry point called from the ingestion handler.
    It orchestrates the full self-healing workflow:
    1. Query for stale pending items
    2. Fetch full item data
    3. Republish to SNS
    4. Log and emit metrics

    The function is wrapped in try/except to prevent self-healing
    failures from affecting the main ingestion workflow.

    Args:
        table: DynamoDB Table resource
        sns_client: boto3 SNS client
        sns_topic_arn: ARN of the analysis SNS topic
        model_version: Model version for analysis

    Returns:
        SelfHealingResult with counts and any errors
    """
    start_time = time.perf_counter()
    result = SelfHealingResult()

    try:
        # Step 1: Query for stale pending items
        stale_keys = query_stale_pending_items(table)

        if not stale_keys:
            logger.info(
                "Self-healing: no stale items found",
                extra={
                    "threshold_hours": SELF_HEALING_THRESHOLD_HOURS,
                },
            )
            result.execution_time_ms = (time.perf_counter() - start_time) * 1000
            emit_metric("SelfHealingItemsFound", 0)
            emit_metric("SelfHealingItemsRepublished", 0)
            return result

        # Step 2: Fetch full item data (filter out items with sentiment)
        full_items = get_full_items(table, stale_keys)
        result.items_found = len(full_items)

        if not full_items:
            logger.info(
                "Self-healing: all stale items already have sentiment",
                extra={
                    "stale_keys_count": len(stale_keys),
                },
            )
            result.execution_time_ms = (time.perf_counter() - start_time) * 1000
            emit_metric("SelfHealingItemsFound", 0)
            emit_metric("SelfHealingItemsRepublished", 0)
            return result

        # Step 3: Republish to SNS
        published = republish_items_to_sns(
            sns_client=sns_client,
            sns_topic_arn=sns_topic_arn,
            items=full_items,
            model_version=model_version,
        )
        result.items_republished = published

        # Calculate execution time
        result.execution_time_ms = (time.perf_counter() - start_time) * 1000

        # Emit metrics
        emit_metric("SelfHealingItemsFound", result.items_found)
        emit_metric("SelfHealingItemsRepublished", result.items_republished)
        emit_metric("SelfHealingExecutionTime", result.execution_time_ms)

        # Log summary
        logger.info(
            "Self-healing completed",
            extra={
                "items_found": result.items_found,
                "items_republished": result.items_republished,
                "threshold_hours": SELF_HEALING_THRESHOLD_HOURS,
                "execution_time_ms": round(result.execution_time_ms, 2),
            },
        )

    except Exception as e:
        error_msg = f"Self-healing check failed: {e}"
        result.errors.append(error_msg)
        result.execution_time_ms = (time.perf_counter() - start_time) * 1000

        logger.error(
            "Self-healing check failed",
            extra={
                **get_safe_error_info(e),
                "execution_time_ms": round(result.execution_time_ms, 2),
            },
        )

        # Emit error metric
        emit_metric("SelfHealingErrors", 1)

    return result
