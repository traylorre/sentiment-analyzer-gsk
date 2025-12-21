"""
Time-series write fanout for multi-resolution sentiment data.

Canonical References:
- [CS-001] AWS DynamoDB Best Practices: "Pre-aggregate at write time for known query patterns"
- [CS-003] Rick Houlihan re:Invent 2018: "Write amplification acceptable when reads >> writes"
- [CS-013] AWS DynamoDB TTL: "Use TTL to automatically expire items"
- [CS-014] AWS Architecture Blog: "Resolution-dependent retention policies"

This module fans out a single sentiment score into 8 resolution buckets (1m/5m/10m/1h/3h/6h/12h/24h)
using BatchWriteItem for efficiency.
"""

import logging
from datetime import datetime
from typing import Any

from botocore.exceptions import ClientError

from src.lib.timeseries.bucket import floor_to_bucket
from src.lib.timeseries.models import Resolution, SentimentScore

logger = logging.getLogger(__name__)


def generate_fanout_items(score: SentimentScore) -> list[dict[str, Any]]:
    """
    Generate DynamoDB items for all 8 resolutions from a single sentiment score.

    Canonical: [CS-001] "Pre-aggregate at write time for known query patterns"

    Args:
        score: The sentiment score to fan out

    Returns:
        List of 8 DynamoDB items (one per resolution)

    Raises:
        ValueError: If score.ticker is None or empty
    """
    if not score.ticker:
        raise ValueError("Sentiment score must have a ticker for fanout")

    items = []

    for resolution in Resolution:
        # Calculate aligned bucket timestamp
        bucket_timestamp = floor_to_bucket(score.timestamp, resolution)

        # Calculate TTL based on resolution
        ttl = int(bucket_timestamp.timestamp()) + resolution.ttl_seconds

        # Build DynamoDB item
        item: dict[str, Any] = {
            "PK": {"S": f"{score.ticker}#{resolution.value}"},
            "SK": {"S": bucket_timestamp.isoformat()},
            # OHLC values - for a single score, all are the same
            "open": {"N": str(score.value)},
            "high": {"N": str(score.value)},
            "low": {"N": str(score.value)},
            "close": {"N": str(score.value)},
            # Aggregation metadata
            "count": {"N": "1"},
            "sum": {"N": str(score.value)},
            "avg": {"N": str(score.value)},
            # TTL for automatic expiration
            "ttl": {"N": str(ttl)},
            # Partial bucket indicator (always true for initial write)
            "is_partial": {"BOOL": True},
            # Source tracking
            "sources": {"L": [{"S": score.source}] if score.source else []},
            # Label counts
            "label_counts": {"M": {score.label: {"N": "1"}} if score.label else {}},
            # Original timestamp for ordering within bucket
            "original_timestamp": {"S": score.timestamp.isoformat()},
        }

        items.append(item)

    return items


def _build_update_expression(
    score: SentimentScore, bucket_timestamp: datetime, resolution: Resolution
) -> tuple[str, dict[str, Any], dict[str, str]]:
    """
    Build UpdateItem expression for upserting into existing bucket.

    Returns:
        Tuple of (update_expression, expression_attribute_values, expression_attribute_names)
    """
    ttl = int(bucket_timestamp.timestamp()) + resolution.ttl_seconds

    update_expr = (
        "SET #open = if_not_exists(#open, :value), "
        "#close = :value, "
        "#high = if_not_exists(#high, :value), "
        "#low = if_not_exists(#low, :value), "
        "is_partial = :is_partial, "
        "original_timestamp = :orig_ts, "
        "#ttl = :ttl "
        "ADD #count :one, #sum :value"
    )

    # Conditional update for high/low
    # This requires separate updates or more complex logic
    # For now, we use a simpler approach with UpdateItem

    expr_values: dict[str, Any] = {
        ":value": {"N": str(score.value)},
        ":one": {"N": "1"},
        ":is_partial": {"BOOL": True},
        ":orig_ts": {"S": score.timestamp.isoformat()},
        ":ttl": {"N": str(ttl)},
    }

    expr_names = {
        "#open": "open",
        "#close": "close",
        "#high": "high",
        "#low": "low",
        "#count": "count",
        "#sum": "sum",
        "#ttl": "ttl",
    }

    return update_expr, expr_values, expr_names


def write_fanout(
    dynamodb: Any,
    table_name: str,
    score: SentimentScore,
) -> None:
    """
    Write a sentiment score to all 8 resolution buckets.

    Uses BatchWriteItem for efficiency when creating new items,
    falls back to UpdateItem for upserting existing buckets.

    Canonical: [CS-003] "Write amplification acceptable when reads >> writes"

    Args:
        dynamodb: boto3 DynamoDB client
        table_name: Target table name
        score: Sentiment score to write

    Raises:
        ClientError: On DynamoDB errors
    """
    items = generate_fanout_items(score)

    # Use BatchWriteItem for initial writes
    # For updates, we'd need UpdateItem with conditional expressions
    request_items = {table_name: [{"PutRequest": {"Item": item}} for item in items]}

    try:
        response = dynamodb.batch_write_item(RequestItems=request_items)

        # Handle unprocessed items (retry logic)
        unprocessed = response.get("UnprocessedItems", {})
        retry_count = 0
        max_retries = 3

        while unprocessed and retry_count < max_retries:
            logger.warning(
                "Retrying unprocessed items",
                extra={
                    "unprocessed_count": len(unprocessed.get(table_name, [])),
                    "retry": retry_count + 1,
                },
            )
            response = dynamodb.batch_write_item(RequestItems=unprocessed)
            unprocessed = response.get("UnprocessedItems", {})
            retry_count += 1

        if unprocessed:
            logger.error(
                "Failed to write all items after retries",
                extra={
                    "unprocessed_count": len(unprocessed.get(table_name, [])),
                    "ticker": score.ticker,
                },
            )

    except ClientError as e:
        logger.error(
            "BatchWriteItem failed",
            extra={
                "error_code": e.response.get("Error", {}).get("Code"),
                "error_message": e.response.get("Error", {}).get("Message"),
                "table_name": table_name,
                "ticker": score.ticker,
            },
        )
        raise


def write_fanout_with_update(
    dynamodb: Any,
    table_name: str,
    score: SentimentScore,
) -> None:
    """
    Write a sentiment score to all 8 resolution buckets using UpdateItem.

    This version properly handles updating existing buckets by:
    - Keeping original 'open' value
    - Updating 'close' to latest value
    - Updating 'high' if new value is higher
    - Updating 'low' if new value is lower
    - Incrementing count and sum

    Canonical: [CS-001] "Pre-aggregate at write time for known query patterns"

    Args:
        dynamodb: boto3 DynamoDB client
        table_name: Target table name
        score: Sentiment score to write

    Raises:
        ValueError: If score.ticker is None
        ClientError: On DynamoDB errors
    """
    if not score.ticker:
        raise ValueError("Sentiment score must have a ticker for fanout")

    for resolution in Resolution:
        bucket_timestamp = floor_to_bucket(score.timestamp, resolution)
        ttl = int(bucket_timestamp.timestamp()) + resolution.ttl_seconds

        key = {
            "PK": {"S": f"{score.ticker}#{resolution.value}"},
            "SK": {"S": bucket_timestamp.isoformat()},
        }

        # Build update expression for upsert
        # Initialize label_counts as empty map if not exists, then update nested key
        update_expr = (
            "SET "
            "#open = if_not_exists(#open, :value), "
            "#close = :value, "
            "#high = if_not_exists(#high, :value), "
            "#low = if_not_exists(#low, :value), "
            "is_partial = :is_partial, "
            "#ttl = :ttl, "
            "sources = list_append(if_not_exists(sources, :empty_list), :source_list), "
            "label_counts = if_not_exists(label_counts, :empty_map) "
            "ADD #count :one, #sum :value"
        )

        expr_values: dict[str, Any] = {
            ":value": {"N": str(score.value)},
            ":one": {"N": "1"},
            ":is_partial": {"BOOL": True},
            ":ttl": {"N": str(ttl)},
            ":empty_list": {"L": []},
            ":source_list": {"L": [{"S": score.source}] if score.source else []},
            ":empty_map": {"M": {}},
        }

        expr_names = {
            "#open": "open",
            "#close": "close",
            "#high": "high",
            "#low": "low",
            "#count": "count",
            "#sum": "sum",
            "#ttl": "ttl",
        }

        # First update: Set base fields and initialize label_counts
        try:
            dynamodb.update_item(
                TableName=table_name,
                Key=key,
                UpdateExpression=update_expr,
                ExpressionAttributeValues=expr_values,
                ExpressionAttributeNames=expr_names,
            )
        except ClientError as e:
            logger.error(
                "UpdateItem base failed",
                extra={
                    "error_code": e.response.get("Error", {}).get("Code"),
                    "ticker": score.ticker,
                    "resolution": resolution.value,
                },
            )
            raise

        # Second update: Update label count (now that label_counts exists)
        if score.label:
            try:
                dynamodb.update_item(
                    TableName=table_name,
                    Key=key,
                    UpdateExpression="ADD label_counts.#label :one",
                    ExpressionAttributeValues={":one": {"N": "1"}},
                    ExpressionAttributeNames={"#label": score.label},
                )
            except ClientError as e:
                logger.error(
                    "UpdateItem label_counts failed",
                    extra={
                        "error_code": e.response.get("Error", {}).get("Code"),
                        "ticker": score.ticker,
                        "resolution": resolution.value,
                        "label": score.label,
                    },
                )
                raise

        # Third update: Conditional update for high (if new value is higher)
        try:
            dynamodb.update_item(
                TableName=table_name,
                Key=key,
                UpdateExpression="SET #high = :value",
                ConditionExpression="#high < :value",
                ExpressionAttributeValues={":value": {"N": str(score.value)}},
                ExpressionAttributeNames={"#high": "high"},
            )
        except ClientError as e:
            if (
                e.response.get("Error", {}).get("Code")
                != "ConditionalCheckFailedException"
            ):
                raise

        # Fourth update: Conditional update for low (if new value is lower)
        try:
            dynamodb.update_item(
                TableName=table_name,
                Key=key,
                UpdateExpression="SET #low = :value",
                ConditionExpression="#low > :value",
                ExpressionAttributeValues={":value": {"N": str(score.value)}},
                ExpressionAttributeNames={"#low": "low"},
            )
        except ClientError as e:
            if (
                e.response.get("Error", {}).get("Code")
                != "ConditionalCheckFailedException"
            ):
                raise
