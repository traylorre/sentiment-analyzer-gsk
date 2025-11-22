"""
DynamoDB Helper Module
======================

Provides DynamoDB table operations with retry configuration for the sentiment analyzer.

For On-Call Engineers:
    - If you see `ProvisionedThroughputExceededException`, check CloudWatch alarm
      `${environment}-dynamodb-write-throttles`. Table uses on-demand billing.
    - Retry logic handles transient failures automatically (3 attempts with backoff).
    - Check SC-01 and SC-02 in ON_CALL_SOP.md for DynamoDB-related incidents.

For Developers:
    - All functions use parameterized expressions to prevent NoSQL injection.
    - Keys use composite format: PK=source_id, SK=timestamp.
    - Never construct Key expressions with string concatenation.

Security Notes:
    - All inputs are validated before use in expressions.
    - No user input is directly interpolated into queries.
"""

import logging
import os
from decimal import Decimal
from typing import Any

import boto3
from botocore.config import Config

# Structured logging for CloudWatch
logger = logging.getLogger(__name__)

# Retry configuration for transient failures
# On-Call Note: Increase max_attempts if seeing intermittent throttling
RETRY_CONFIG = Config(
    retries={
        "max_attempts": 3,
        "mode": "adaptive",  # Automatically adjusts to throttling
    },
    connect_timeout=5,
    read_timeout=10,
)


def get_dynamodb_resource(region_name: str | None = None) -> Any:
    """
    Get a DynamoDB resource with retry configuration.

    Args:
        region_name: AWS region (defaults to AWS_DEFAULT_REGION env var)

    Returns:
        boto3 DynamoDB resource

    On-Call Note:
        If this fails with credential errors, check:
        1. Lambda execution role has dynamodb:* permissions
        2. Region matches table location
    """
    region = (
        region_name
        or os.environ.get("AWS_DEFAULT_REGION")
        or os.environ.get("AWS_REGION")
    )
    if not region:
        raise ValueError(
            "AWS_DEFAULT_REGION or AWS_REGION environment variable must be set"
        )

    return boto3.resource(
        "dynamodb",
        region_name=region,
        config=RETRY_CONFIG,
    )


def get_dynamodb_client(region_name: str | None = None) -> Any:
    """
    Get a DynamoDB client with retry configuration.

    Use client for low-level operations; use resource for high-level table operations.

    Args:
        region_name: AWS region (defaults to AWS_DEFAULT_REGION env var)

    Returns:
        boto3 DynamoDB client
    """
    region = (
        region_name
        or os.environ.get("AWS_DEFAULT_REGION")
        or os.environ.get("AWS_REGION")
    )
    if not region:
        raise ValueError(
            "AWS_DEFAULT_REGION or AWS_REGION environment variable must be set"
        )

    return boto3.client(
        "dynamodb",
        region_name=region,
        config=RETRY_CONFIG,
    )


def get_table(table_name: str | None = None, region_name: str | None = None) -> Any:
    """
    Get a DynamoDB table resource.

    Args:
        table_name: Table name (defaults to DYNAMODB_TABLE env var)
        region_name: AWS region

    Returns:
        boto3 DynamoDB Table resource

    On-Call Note:
        If table not found, verify:
        1. DYNAMODB_TABLE env var is set correctly
        2. Table exists: aws dynamodb describe-table --table-name <name>
    """
    name = table_name or os.environ.get("DYNAMODB_TABLE")
    if not name:
        raise ValueError(
            "Table name required: set DYNAMODB_TABLE env var or pass table_name"
        )

    resource = get_dynamodb_resource(region_name)
    return resource.Table(name)


def build_key(source_id: str, timestamp: str) -> dict[str, str]:
    """
    Build a DynamoDB key for item operations.

    Schema: PK=source_id, SK=timestamp

    Args:
        source_id: Source identifier (e.g., "newsapi#abc123def456")
        timestamp: ISO8601 timestamp (e.g., "2025-11-17T14:30:00.000Z")

    Returns:
        Dict with source_id and timestamp keys

    Example:
        >>> build_key("newsapi#abc123", "2025-11-17T14:30:00.000Z")
        {'source_id': 'newsapi#abc123', 'timestamp': '2025-11-17T14:30:00.000Z'}

    Security Note:
        Inputs are used as-is in parameterized queries. Validation should occur
        at the schema layer (see schemas.py).
    """
    return {
        "source_id": source_id,
        "timestamp": timestamp,
    }


def parse_dynamodb_item(item: dict[str, Any]) -> dict[str, Any]:
    """
    Convert DynamoDB item to standard Python dict.

    Handles:
    - Decimal → float conversion for JSON serialization
    - Set → list conversion
    - Nested structures

    Args:
        item: DynamoDB item (from Table.get_item, scan, query)

    Returns:
        Python dict with JSON-serializable types

    On-Call Note:
        If you see Decimal serialization errors in logs, ensure all numeric
        values pass through this function before JSON encoding.
    """
    if not item:
        return {}

    result = {}
    for key, value in item.items():
        result[key] = _convert_value(value)

    return result


def _convert_value(value: Any) -> Any:
    """
    Recursively convert DynamoDB types to Python types.

    Internal helper for parse_dynamodb_item.
    """
    if isinstance(value, Decimal):
        # Convert Decimal to int if whole number, else float
        if value % 1 == 0:
            return int(value)
        return float(value)
    elif isinstance(value, set):
        return list(value)
    elif isinstance(value, dict):
        return {k: _convert_value(v) for k, v in value.items()}
    elif isinstance(value, list):
        return [_convert_value(v) for v in value]
    return value


def item_exists(table: Any, source_id: str, timestamp: str) -> bool:
    """
    Check if an item exists in the table.

    Uses projection to minimize read capacity usage.

    Args:
        table: DynamoDB Table resource
        source_id: Source identifier
        timestamp: ISO8601 timestamp

    Returns:
        True if item exists, False otherwise

    On-Call Note:
        This is used for deduplication. If duplicates appear, check:
        1. source_id generation in deduplication.py
        2. Conditional writes in ingestion handler
    """
    try:
        response = table.get_item(
            Key=build_key(source_id, timestamp),
            ProjectionExpression="source_id",  # Minimal data transfer
        )
        return "Item" in response
    except Exception as e:
        logger.error(
            "Failed to check item existence",
            extra={
                "source_id": source_id,
                "timestamp": timestamp,
                "error": str(e),
            },
        )
        raise


def put_item_if_not_exists(
    table: Any,
    item: dict[str, Any],
) -> bool:
    """
    Put an item only if it doesn't already exist.

    Uses conditional expression to prevent overwrites. This is the primary
    deduplication mechanism.

    Args:
        table: DynamoDB Table resource
        item: Item to put (must include source_id and timestamp)

    Returns:
        True if item was created, False if it already existed

    On-Call Note:
        If this returns False frequently, check ingestion is not re-processing
        the same articles. This is normal for overlapping time windows.
    """
    try:
        table.put_item(
            Item=item,
            ConditionExpression="attribute_not_exists(source_id)",
        )
        return True
    except table.meta.client.exceptions.ConditionalCheckFailedException:
        # Item already exists - this is expected for deduplication
        logger.debug(
            "Item already exists, skipping",
            extra={"source_id": item.get("source_id")},
        )
        return False
    except Exception as e:
        logger.error(
            "Failed to put item",
            extra={
                "source_id": item.get("source_id"),
                "error": str(e),
            },
        )
        raise


def update_item_status(
    table: Any,
    source_id: str,
    timestamp: str,
    status: str,
    additional_attrs: dict[str, Any] | None = None,
) -> bool:
    """
    Update an item's status and optional additional attributes.

    Used by analysis Lambda to mark items as analyzed.

    Args:
        table: DynamoDB Table resource
        source_id: Source identifier
        timestamp: ISO8601 timestamp
        status: New status value (e.g., "analyzed")
        additional_attrs: Additional attributes to update

    Returns:
        True if update succeeded

    On-Call Note:
        If updates fail with ConditionalCheckFailedException, check:
        1. Item exists with correct source_id/timestamp
        2. Analysis is not trying to re-process already-analyzed items
    """
    update_expr = "SET #status = :status"
    expr_names = {"#status": "status"}
    expr_values = {":status": status}

    if additional_attrs:
        for key, value in additional_attrs.items():
            # Use safe attribute names
            safe_key = f"#{key.replace('-', '_')}"
            update_expr += f", {safe_key} = :{key.replace('-', '_')}"
            expr_names[safe_key] = key
            expr_values[f":{key.replace('-', '_')}"] = value

    try:
        table.update_item(
            Key=build_key(source_id, timestamp),
            UpdateExpression=update_expr,
            ExpressionAttributeNames=expr_names,
            ExpressionAttributeValues=expr_values,
        )
        return True
    except Exception as e:
        logger.error(
            "Failed to update item status",
            extra={
                "source_id": source_id,
                "timestamp": timestamp,
                "status": status,
                "error": str(e),
            },
        )
        raise
