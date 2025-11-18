"""
Dashboard Metrics Aggregation Module
=====================================

Provides metrics calculation functions for the sentiment analyzer dashboard.

For On-Call Engineers:
    If dashboard shows incorrect metrics:
    1. Verify DynamoDB GSIs exist (by_sentiment, by_tag, by_status)
    2. Check GSI propagation delay (can take up to 1 second)
    3. Verify items have correct status field for by_status GSI

    See SC-05 in ON_CALL_SOP.md for dashboard-related incidents.

For Developers:
    - All queries use eventually consistent reads (acceptable for dashboard)
    - GSI queries are more efficient than table scans
    - Recent items limited to 20 for performance
    - Rate calculations use timestamp filtering

Security Notes:
    - Query parameters are validated before use
    - No user input directly in expressions
    - All responses sanitized before returning
"""

import logging
from datetime import datetime, timedelta, timezone
from typing import Any

from boto3.dynamodb.conditions import Key

# Structured logging
logger = logging.getLogger(__name__)

# Constants
MAX_RECENT_ITEMS = 20
SENTIMENT_VALUES = ["positive", "neutral", "negative"]


def calculate_sentiment_distribution(items: list[dict[str, Any]]) -> dict[str, int]:
    """
    Calculate sentiment distribution from a list of items.

    Args:
        items: List of DynamoDB items with 'sentiment' field

    Returns:
        Dict with counts for positive, neutral, negative

    Example:
        >>> items = [{"sentiment": "positive"}, {"sentiment": "negative"}]
        >>> calculate_sentiment_distribution(items)
        {'positive': 1, 'neutral': 0, 'negative': 1}

    On-Call Note:
        If all counts are 0, verify items have 'sentiment' field populated.
        Items with status='pending' won't have sentiment yet.
    """
    distribution = {sentiment: 0 for sentiment in SENTIMENT_VALUES}

    for item in items:
        sentiment = item.get("sentiment", "").lower()
        if sentiment in distribution:
            distribution[sentiment] += 1
        elif sentiment:
            # Log unexpected sentiment values
            logger.warning(
                "Unexpected sentiment value",
                extra={"sentiment": sentiment, "source_id": item.get("source_id")},
            )

    return distribution


def calculate_tag_distribution(items: list[dict[str, Any]]) -> dict[str, int]:
    """
    Calculate tag distribution from a list of items.

    Args:
        items: List of DynamoDB items with 'tags' field (list of strings)

    Returns:
        Dict with counts per tag, sorted by count descending

    Example:
        >>> items = [{"tags": ["tech", "ai"]}, {"tags": ["tech"]}]
        >>> calculate_tag_distribution(items)
        {'tech': 2, 'ai': 1}

    On-Call Note:
        Tags come from the watch list configured in ingestion Lambda.
        If tags are missing, check WATCH_TAGS environment variable.
    """
    tag_counts: dict[str, int] = {}

    for item in items:
        tags = item.get("tags", [])
        if isinstance(tags, list):
            for tag in tags:
                if isinstance(tag, str) and tag:
                    tag_counts[tag] = tag_counts.get(tag, 0) + 1

    # Sort by count descending
    sorted_tags = dict(sorted(tag_counts.items(), key=lambda x: x[1], reverse=True))

    return sorted_tags


def get_recent_items(
    table: Any,
    limit: int = MAX_RECENT_ITEMS,
    status: str = "analyzed",
) -> list[dict[str, Any]]:
    """
    Get recent items from DynamoDB using the by_status GSI.

    Args:
        table: DynamoDB Table resource
        limit: Maximum number of items to return
        status: Item status to filter by (default: "analyzed")

    Returns:
        List of items sorted by timestamp descending

    On-Call Note:
        If this returns empty, check:
        1. by_status GSI exists on the table
        2. Items have been analyzed (status='analyzed')
        3. Query is within last 24 hours
    """
    try:
        # Query by_status GSI with limit
        # GSI: PK=status, SK=timestamp (sorted descending)
        response = table.query(
            IndexName="by_status",
            KeyConditionExpression=Key("status").eq(status),
            ScanIndexForward=False,  # Descending order (newest first)
            Limit=limit,
        )

        items = response.get("Items", [])

        logger.info(
            "Retrieved recent items",
            extra={"count": len(items), "status": status, "limit": limit},
        )

        return items

    except Exception as e:
        logger.error(
            "Failed to get recent items",
            extra={"status": status, "limit": limit, "error": str(e)},
        )
        raise


def get_items_by_sentiment(
    table: Any,
    sentiment: str,
    hours: int = 24,
) -> list[dict[str, Any]]:
    """
    Get items by sentiment from the last N hours using by_sentiment GSI.

    Args:
        table: DynamoDB Table resource
        sentiment: Sentiment value (positive, neutral, negative)
        hours: Number of hours to look back

    Returns:
        List of items with the specified sentiment

    On-Call Note:
        If counts seem low, verify:
        1. by_sentiment GSI exists
        2. Analysis Lambda is populating sentiment field
        3. Time window covers expected data
    """
    if sentiment.lower() not in SENTIMENT_VALUES:
        raise ValueError(f"Invalid sentiment: {sentiment}")

    # Calculate time window
    now = datetime.now(timezone.utc)
    start_time = (now - timedelta(hours=hours)).isoformat()

    try:
        response = table.query(
            IndexName="by_sentiment",
            KeyConditionExpression=(
                Key("sentiment").eq(sentiment.lower())
                & Key("timestamp").gte(start_time)
            ),
        )

        items = response.get("Items", [])

        logger.debug(
            "Retrieved items by sentiment",
            extra={
                "sentiment": sentiment,
                "hours": hours,
                "count": len(items),
            },
        )

        return items

    except Exception as e:
        logger.error(
            "Failed to get items by sentiment",
            extra={"sentiment": sentiment, "hours": hours, "error": str(e)},
        )
        raise


def calculate_ingestion_rate(
    table: Any,
    hours: int = 24,
) -> dict[str, int]:
    """
    Calculate ingestion rates for different time windows.

    Args:
        table: DynamoDB Table resource
        hours: Maximum hours to look back

    Returns:
        Dict with rate_last_hour and rate_last_24h

    On-Call Note:
        If rates seem low:
        1. Check EventBridge schedule is running (every 5 min)
        2. Verify ingestion Lambda is not erroring
        3. Check NewsAPI is returning articles
    """
    now = datetime.now(timezone.utc)

    # Calculate time boundaries
    one_hour_ago = (now - timedelta(hours=1)).isoformat()
    twenty_four_hours_ago = (now - timedelta(hours=hours)).isoformat()

    try:
        # Count items in last hour (use by_status GSI to count all)
        # We query for all statuses and filter by timestamp
        response_1h = table.query(
            IndexName="by_status",
            KeyConditionExpression=(
                Key("status").eq("analyzed") & Key("timestamp").gte(one_hour_ago)
            ),
            Select="COUNT",
        )
        rate_last_hour = response_1h.get("Count", 0)

        # Also count pending items in last hour
        response_1h_pending = table.query(
            IndexName="by_status",
            KeyConditionExpression=(
                Key("status").eq("pending") & Key("timestamp").gte(one_hour_ago)
            ),
            Select="COUNT",
        )
        rate_last_hour += response_1h_pending.get("Count", 0)

        # Count items in last 24 hours
        response_24h = table.query(
            IndexName="by_status",
            KeyConditionExpression=(
                Key("status").eq("analyzed")
                & Key("timestamp").gte(twenty_four_hours_ago)
            ),
            Select="COUNT",
        )
        rate_last_24h = response_24h.get("Count", 0)

        # Also count pending items in last 24 hours
        response_24h_pending = table.query(
            IndexName="by_status",
            KeyConditionExpression=(
                Key("status").eq("pending")
                & Key("timestamp").gte(twenty_four_hours_ago)
            ),
            Select="COUNT",
        )
        rate_last_24h += response_24h_pending.get("Count", 0)

        logger.info(
            "Calculated ingestion rates",
            extra={
                "rate_last_hour": rate_last_hour,
                "rate_last_24h": rate_last_24h,
            },
        )

        return {
            "rate_last_hour": rate_last_hour,
            "rate_last_24h": rate_last_24h,
        }

    except Exception as e:
        logger.error(
            "Failed to calculate ingestion rates",
            extra={"hours": hours, "error": str(e)},
        )
        raise


def aggregate_dashboard_metrics(
    table: Any,
    hours: int = 24,
) -> dict[str, Any]:
    """
    Aggregate all dashboard metrics in a single call.

    This is the main function used by the dashboard API endpoint.

    Args:
        table: DynamoDB Table resource
        hours: Time window for metrics

    Returns:
        Dict with all dashboard metrics:
        - total: Total items
        - positive: Positive count
        - neutral: Neutral count
        - negative: Negative count
        - by_tag: Tag distribution
        - rate_last_hour: Items in last hour
        - rate_last_24h: Items in last 24 hours
        - recent_items: Recent analyzed items

    On-Call Note:
        If this fails or returns zeros:
        1. Check DynamoDB table and GSIs exist
        2. Verify Lambda has dynamodb:Query permission on GSIs
        3. Check recent items exist with status='analyzed'
    """
    try:
        # Get recent items (for display and distribution calculation)
        recent_items = get_recent_items(table, limit=MAX_RECENT_ITEMS)

        # For distribution calculations, we need more items
        # Query all analyzed items in time window
        now = datetime.now(timezone.utc)
        start_time = (now - timedelta(hours=hours)).isoformat()

        # Get all analyzed items for accurate distribution
        all_items: list[dict[str, Any]] = []
        for sentiment in SENTIMENT_VALUES:
            items = get_items_by_sentiment(table, sentiment, hours)
            all_items.extend(items)

        # Calculate distributions
        sentiment_dist = calculate_sentiment_distribution(all_items)
        tag_dist = calculate_tag_distribution(all_items)

        # Calculate ingestion rates
        rates = calculate_ingestion_rate(table, hours)

        # Calculate total
        total = sum(sentiment_dist.values())

        metrics = {
            "total": total,
            "positive": sentiment_dist["positive"],
            "neutral": sentiment_dist["neutral"],
            "negative": sentiment_dist["negative"],
            "by_tag": tag_dist,
            "rate_last_hour": rates["rate_last_hour"],
            "rate_last_24h": rates["rate_last_24h"],
            "recent_items": recent_items,
        }

        logger.info(
            "Aggregated dashboard metrics",
            extra={
                "total": total,
                "recent_count": len(recent_items),
            },
        )

        return metrics

    except Exception as e:
        logger.error(
            "Failed to aggregate dashboard metrics",
            extra={"hours": hours, "error": str(e)},
        )
        raise


def sanitize_item_for_response(item: dict[str, Any]) -> dict[str, Any]:
    """
    Sanitize a DynamoDB item for API response.

    Removes internal fields and ensures safe output.

    Args:
        item: DynamoDB item

    Returns:
        Sanitized item safe for API response

    Security Note:
        This function ensures no internal metadata leaks to clients.
        Add any fields that should be hidden to the HIDDEN_FIELDS list.
    """
    # Fields to exclude from API responses
    hidden_fields = {"ttl", "content_hash"}

    sanitized = {}
    for key, value in item.items():
        if key not in hidden_fields:
            sanitized[key] = value

    return sanitized
