"""
API v2 Endpoints for POWERPLAN Mobile Dashboard
================================================

New endpoints supporting the mobile-first sentiment dashboard with:
- Multi-tag sentiment aggregation
- Time-series trend data for sparklines
- Historical data backfill

For On-Call Engineers:
    These endpoints are designed for the mobile dashboard experience.
    If mobile app shows incorrect data:
    1. Verify DynamoDB GSIs exist (by_tag, by_sentiment, by_status)
    2. Check time range is valid (not in future)
    3. Verify tag filtering is working correctly

For Developers:
    - All endpoints require API key authentication
    - Tag-based queries require the by_tag GSI
    - Trend data is aggregated in memory for small datasets
    - Backfill uses async pattern with job tracking

Security Notes:
    - All inputs validated via Pydantic
    - Query parameters sanitized before DynamoDB queries
    - No user input directly in expressions
"""

import logging
from datetime import UTC, datetime, timedelta
from typing import Any

from boto3.dynamodb.conditions import Key

from src.lambdas.shared.logging_utils import get_safe_error_info, sanitize_for_log

# Structured logging
logger = logging.getLogger(__name__)

# Constants
SENTIMENT_VALUES = ["positive", "neutral", "negative"]
MAX_TAGS = 5
MAX_TREND_POINTS = 168  # Max 7 days of hourly data


def get_sentiment_by_tags(
    table: Any,
    tags: list[str],
    start_time: str,
    end_time: str,
) -> dict[str, Any]:
    """
    Get aggregated sentiment data for multiple tags.

    Used by the mobile dashboard's Mood Ring and tag comparison views.

    Args:
        table: DynamoDB Table resource
        tags: List of topic tags to query (max 5)
        start_time: ISO8601 start timestamp
        end_time: ISO8601 end timestamp

    Returns:
        Dict with per-tag sentiment breakdown and overall aggregate:
        {
            "tags": {
                "AI": {"positive": 0.72, "neutral": 0.18, "negative": 0.10, "count": 145},
                ...
            },
            "overall": {"positive": 0.58, "neutral": 0.24, "negative": 0.18},
            "total_count": 234,
            "trend": "improving"  # or "declining", "stable"
        }

    On-Call Note:
        If all counts are 0, verify:
        1. by_tag GSI exists with tag as partition key
        2. Items have been analyzed with sentiment field
        3. Time range covers existing data
    """
    if len(tags) > MAX_TAGS:
        raise ValueError(f"Maximum {MAX_TAGS} tags allowed, got {len(tags)}")

    if not tags:
        raise ValueError("At least one tag is required")

    tag_results: dict[str, dict[str, Any]] = {}
    overall_sentiment = {"positive": 0, "neutral": 0, "negative": 0}
    total_count = 0

    for tag in tags:
        try:
            # Query by_tag GSI for this tag within time range
            response = table.query(
                IndexName="by_tag",
                KeyConditionExpression=(
                    Key("tag").eq(tag) & Key("timestamp").between(start_time, end_time)
                ),
            )

            items = response.get("Items", [])

            # Handle pagination for large result sets
            while "LastEvaluatedKey" in response:
                response = table.query(
                    IndexName="by_tag",
                    KeyConditionExpression=(
                        Key("tag").eq(tag)
                        & Key("timestamp").between(start_time, end_time)
                    ),
                    ExclusiveStartKey=response["LastEvaluatedKey"],
                )
                items.extend(response.get("Items", []))

            # Calculate sentiment distribution for this tag
            tag_sentiment = {"positive": 0, "neutral": 0, "negative": 0}
            for item in items:
                sentiment = item.get("sentiment", "").lower()
                if sentiment in tag_sentiment:
                    tag_sentiment[sentiment] += 1
                    overall_sentiment[sentiment] += 1

            tag_count = sum(tag_sentiment.values())
            total_count += tag_count

            # Convert to percentages if we have data
            if tag_count > 0:
                tag_results[tag] = {
                    "positive": round(tag_sentiment["positive"] / tag_count, 2),
                    "neutral": round(tag_sentiment["neutral"] / tag_count, 2),
                    "negative": round(tag_sentiment["negative"] / tag_count, 2),
                    "count": tag_count,
                }
            else:
                tag_results[tag] = {
                    "positive": 0.0,
                    "neutral": 0.0,
                    "negative": 0.0,
                    "count": 0,
                }

            logger.debug(
                "Queried sentiment for tag",
                extra={
                    "tag": sanitize_for_log(tag),
                    "count": tag_count,
                },
            )

        except Exception as e:
            logger.error(
                "Failed to query sentiment for tag",
                extra={
                    "tag": sanitize_for_log(tag),
                    **get_safe_error_info(e),
                },
            )
            raise

    # Calculate overall percentages
    if total_count > 0:
        overall_pct = {
            "positive": round(overall_sentiment["positive"] / total_count, 2),
            "neutral": round(overall_sentiment["neutral"] / total_count, 2),
            "negative": round(overall_sentiment["negative"] / total_count, 2),
        }
    else:
        overall_pct = {"positive": 0.0, "neutral": 0.0, "negative": 0.0}

    # Determine trend (compare to simple positive ratio)
    trend = "stable"
    if overall_pct["positive"] > 0.6:
        trend = "improving"
    elif overall_pct["negative"] > 0.4:
        trend = "declining"

    result = {
        "tags": tag_results,
        "overall": overall_pct,
        "total_count": total_count,
        "trend": trend,
        "time_range": {
            "start": start_time,
            "end": end_time,
        },
    }

    logger.info(
        "Aggregated sentiment for tags",
        extra={
            "tag_count": len(tags),
            "total_items": total_count,
            "trend": trend,
        },
    )

    return result


def get_trend_data(
    table: Any,
    tags: list[str],
    interval: str,
    range_hours: int,
) -> dict[str, list[dict[str, Any]]]:
    """
    Get time-series trend data for sparkline visualizations.

    Args:
        table: DynamoDB Table resource
        tags: List of topic tags to query (max 5)
        interval: Time interval for aggregation ("1h", "6h", "1d")
        range_hours: Number of hours to look back

    Returns:
        Dict mapping each tag to list of data points:
        {
            "AI": [
                {"timestamp": "2025-11-24T00:00:00Z", "sentiment": 0.65, "count": 12},
                {"timestamp": "2025-11-24T01:00:00Z", "sentiment": 0.70, "count": 8},
                ...
            ],
            ...
        }

    On-Call Note:
        If trend data is empty or sparse:
        1. Verify ingestion is running (check EventBridge schedule)
        2. Check time range covers data ingestion period
        3. Verify by_tag GSI exists
    """
    if len(tags) > MAX_TAGS:
        raise ValueError(f"Maximum {MAX_TAGS} tags allowed, got {len(tags)}")

    # Parse interval
    interval_hours = {"1h": 1, "6h": 6, "1d": 24}.get(interval)
    if not interval_hours:
        raise ValueError(f"Invalid interval: {interval}. Use: 1h, 6h, or 1d")

    # Limit range to prevent excessive queries
    max_range = 168  # 7 days
    if range_hours > max_range:
        range_hours = max_range
        logger.warning(
            "Range hours capped to maximum",
            extra={"requested": range_hours, "max": max_range},
        )

    now = datetime.now(UTC)
    start_time = now - timedelta(hours=range_hours)

    # Generate time buckets
    buckets: list[datetime] = []
    bucket_start = start_time.replace(minute=0, second=0, microsecond=0)
    while bucket_start < now:
        buckets.append(bucket_start)
        bucket_start += timedelta(hours=interval_hours)

    result: dict[str, list[dict[str, Any]]] = {}

    for tag in tags:
        try:
            # Query all items for this tag in the time range
            response = table.query(
                IndexName="by_tag",
                KeyConditionExpression=(
                    Key("tag").eq(tag) & Key("timestamp").gte(start_time.isoformat())
                ),
            )

            items = response.get("Items", [])

            # Handle pagination
            while "LastEvaluatedKey" in response:
                response = table.query(
                    IndexName="by_tag",
                    KeyConditionExpression=(
                        Key("tag").eq(tag)
                        & Key("timestamp").gte(start_time.isoformat())
                    ),
                    ExclusiveStartKey=response["LastEvaluatedKey"],
                )
                items.extend(response.get("Items", []))

            # Group items into time buckets
            bucket_data: dict[str, dict[str, Any]] = {}
            for bucket in buckets:
                bucket_key = bucket.isoformat()
                bucket_data[bucket_key] = {
                    "positive": 0,
                    "neutral": 0,
                    "negative": 0,
                    "total": 0,
                }

            for item in items:
                item_ts = item.get("timestamp", "")
                sentiment = item.get("sentiment", "").lower()

                if not item_ts or sentiment not in SENTIMENT_VALUES:
                    continue

                # Find the bucket this item belongs to
                try:
                    item_dt = datetime.fromisoformat(item_ts.replace("Z", "+00:00"))
                    bucket_dt = item_dt.replace(minute=0, second=0, microsecond=0)
                    # Align to interval
                    if interval_hours > 1:
                        bucket_hour = (
                            bucket_dt.hour // interval_hours
                        ) * interval_hours
                        bucket_dt = bucket_dt.replace(hour=bucket_hour)

                    bucket_key = bucket_dt.isoformat()

                    if bucket_key in bucket_data:
                        bucket_data[bucket_key][sentiment] += 1
                        bucket_data[bucket_key]["total"] += 1
                except (ValueError, KeyError):
                    continue

            # Convert to list of data points with sentiment score
            tag_trend: list[dict[str, Any]] = []
            for bucket_key in sorted(bucket_data.keys()):
                data = bucket_data[bucket_key]
                total = data["total"]

                # Calculate sentiment score: 1.0 = all positive, 0.0 = all negative
                # Formula: (positive - negative + total) / (2 * total) to normalize to 0-1
                if total > 0:
                    score = (data["positive"] - data["negative"] + total) / (2 * total)
                    score = round(max(0.0, min(1.0, score)), 2)
                else:
                    score = 0.5  # Neutral when no data

                tag_trend.append(
                    {
                        "timestamp": bucket_key,
                        "sentiment": score,
                        "count": total,
                    }
                )

            result[tag] = tag_trend

            logger.debug(
                "Generated trend data for tag",
                extra={
                    "tag": sanitize_for_log(tag),
                    "points": len(tag_trend),
                },
            )

        except Exception as e:
            logger.error(
                "Failed to get trend data for tag",
                extra={
                    "tag": sanitize_for_log(tag),
                    **get_safe_error_info(e),
                },
            )
            raise

    logger.info(
        "Generated trend data",
        extra={
            "tags": len(tags),
            "interval": interval,
            "range_hours": range_hours,
        },
    )

    return result


def get_articles_by_tags(
    table: Any,
    tags: list[str],
    limit: int = 20,
    sentiment_filter: str | None = None,
    start_time: str | None = None,
) -> list[dict[str, Any]]:
    """
    Get recent articles for specified tags with optional sentiment filtering.

    Used by the mobile dashboard's article feed.

    Args:
        table: DynamoDB Table resource
        tags: List of topic tags to query
        limit: Maximum articles to return per tag
        sentiment_filter: Optional sentiment filter (positive/neutral/negative)
        start_time: Optional start time filter

    Returns:
        List of articles sorted by timestamp descending

    On-Call Note:
        If articles list is empty:
        1. Verify by_tag GSI exists
        2. Check ingestion is working
        3. Verify sentiment filter matches existing data
    """
    if sentiment_filter and sentiment_filter.lower() not in SENTIMENT_VALUES:
        raise ValueError(
            f"Invalid sentiment filter: {sentiment_filter}. "
            f"Use: {', '.join(SENTIMENT_VALUES)}"
        )

    all_articles: list[dict[str, Any]] = []

    for tag in tags[:MAX_TAGS]:  # Limit to max tags
        try:
            # Build query
            key_condition = Key("tag").eq(tag)
            if start_time:
                key_condition = key_condition & Key("timestamp").gte(start_time)

            # Query with optional filter
            query_params: dict[str, Any] = {
                "IndexName": "by_tag",
                "KeyConditionExpression": key_condition,
                "ScanIndexForward": False,  # Newest first
                "Limit": limit,
            }

            # Add sentiment filter if specified
            if sentiment_filter:
                from boto3.dynamodb.conditions import Attr

                query_params["FilterExpression"] = Attr("sentiment").eq(
                    sentiment_filter.lower()
                )

            response = table.query(**query_params)
            items = response.get("Items", [])
            all_articles.extend(items)

        except Exception as e:
            logger.error(
                "Failed to get articles for tag",
                extra={
                    "tag": sanitize_for_log(tag),
                    **get_safe_error_info(e),
                },
            )
            raise

    # Sort all articles by timestamp descending and limit
    all_articles.sort(key=lambda x: x.get("timestamp", ""), reverse=True)
    all_articles = all_articles[:limit]

    logger.info(
        "Retrieved articles for tags",
        extra={
            "tags": len(tags),
            "articles": len(all_articles),
            "sentiment_filter": sanitize_for_log(sentiment_filter)
            if sentiment_filter
            else "none",
        },
    )

    return all_articles
