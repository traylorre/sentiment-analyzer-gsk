"""
Ingestion Lambda Handler
========================

EventBridge-triggered Lambda that fetches articles from NewsAPI and publishes
to SNS for sentiment analysis.

For On-Call Engineers:
    This Lambda runs every 5 minutes via EventBridge scheduler.

    Common issues:
    - SC-03: NewsAPI rate limit (429) - Check CloudWatch metric NewsAPIRateLimitHit
    - SC-07: No new items for 1 hour - Verify tags have recent news
    - SC-01: High DynamoDB write errors - Check throttling alarm

    Quick commands:
    # Check recent invocations
    aws logs tail /aws/lambda/${environment}-sentiment-ingestion --since 1h

    # Check rate limit metric
    aws cloudwatch get-metric-statistics \
      --namespace SentimentAnalyzer \
      --metric-name NewsAPIRateLimitHit \
      --start-time $(date -d '1 hour ago' -u +%Y-%m-%dT%H:%M:%SZ) \
      --end-time $(date -u +%Y-%m-%dT%H:%M:%SZ) \
      --period 3600 --statistics Sum

    See ON_CALL_SOP.md for detailed runbooks.

For Developers:
    Handler workflow:
    1. Load configuration (watch tags, secrets ARNs)
    2. Fetch NewsAPI key from Secrets Manager
    3. For each tag:
       - Fetch articles from NewsAPI
       - Deduplicate against DynamoDB
       - Insert new items (status=pending)
       - Publish to SNS for analysis
    4. Emit CloudWatch metrics

Security Notes:
    - API keys retrieved from Secrets Manager (never hardcoded)
    - Conditional writes prevent duplicate processing
    - All external calls use HTTPS
    - Input validation via Pydantic schemas
"""

import json
import logging
import time
from datetime import UTC, datetime, timedelta
from typing import Any

import boto3
from botocore.config import Config

from src.lambdas.ingestion.adapters.base import (
    AdapterError,
    AuthenticationError,
    RateLimitError,
)
from src.lambdas.ingestion.adapters.newsapi import NewsAPIAdapter
from src.lambdas.ingestion.config import ConfigurationError, get_config
from src.lambdas.shared.dynamodb import get_table, put_item_if_not_exists
from src.lambdas.shared.secrets import get_api_key
from src.lib.deduplication import generate_source_id
from src.lib.metrics import (
    emit_metric,
    emit_metrics_batch,
    log_structured,
)

# Structured logging
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

# SNS client configuration
# On-Call Note: Increase retries if seeing intermittent publish failures
SNS_RETRY_CONFIG = Config(
    retries={
        "max_attempts": 3,
        "mode": "adaptive",
    },
    connect_timeout=5,
    read_timeout=10,
)

# TTL for items (30 days)
TTL_DAYS = 30


def lambda_handler(event: dict[str, Any], context: Any) -> dict[str, Any]:
    """
    Main Lambda handler for ingestion.

    Triggered by EventBridge scheduler every 5 minutes.

    Args:
        event: EventBridge scheduled event
        context: Lambda context (contains aws_request_id)

    Returns:
        Response with status and summary

    On-Call Note:
        If this handler fails repeatedly, check:
        1. NewsAPI key in Secrets Manager
        2. DynamoDB table exists
        3. SNS topic exists and Lambda has publish permission
    """
    start_time = time.perf_counter()
    request_id = getattr(context, "aws_request_id", "unknown")

    log_structured(
        "INFO",
        "Ingestion started",
        request_id=request_id,
        event_source=event.get("source", "unknown"),
    )

    # Initialize counters
    summary = {
        "tags_processed": 0,
        "articles_fetched": 0,
        "new_items": 0,
        "duplicates_skipped": 0,
        "errors": 0,
    }
    per_tag_stats: dict[str, dict[str, int]] = {}
    errors: list[dict[str, Any]] = []

    try:
        # Load configuration
        config = get_config()

        log_structured(
            "INFO",
            "Configuration loaded",
            watch_tags=config.watch_tags,
            dynamodb_table=config.dynamodb_table,
        )

        # Get NewsAPI key from Secrets Manager
        # On-Call Note: If this fails, check secret path and Lambda IAM role
        api_key = get_api_key(config.newsapi_secret_arn)

        # Initialize adapter and resources
        adapter = NewsAPIAdapter(api_key=api_key)
        table = get_table(config.dynamodb_table)
        sns_client = _get_sns_client()

        # Process each tag
        for tag in config.watch_tags:
            tag_stats = {
                "fetched": 0,
                "new": 0,
                "duplicates": 0,
            }

            try:
                # Fetch articles for this tag
                articles = adapter.fetch_items(tag)
                tag_stats["fetched"] = len(articles)
                summary["articles_fetched"] += len(articles)

                log_structured(
                    "INFO",
                    "Fetched articles for tag",
                    tag=tag,
                    count=len(articles),
                )

                # Process each article
                for article in articles:
                    result = _process_article(
                        article=article,
                        tag=tag,
                        table=table,
                        sns_client=sns_client,
                        sns_topic_arn=config.sns_topic_arn,
                        model_version=config.model_version,
                    )

                    if result == "new":
                        tag_stats["new"] += 1
                        summary["new_items"] += 1
                    elif result == "duplicate":
                        tag_stats["duplicates"] += 1
                        summary["duplicates_skipped"] += 1

                summary["tags_processed"] += 1

            except RateLimitError as e:
                # Rate limited - log and continue with next tag
                logger.warning(
                    f"Rate limited for tag {tag}",
                    extra={
                        "tag": tag,
                        "retry_after": e.retry_after,
                    },
                )
                emit_metric("NewsAPIRateLimitHit", 1)
                errors.append(
                    {
                        "tag": tag,
                        "error": "RATE_LIMIT_EXCEEDED",
                        "retry_after": e.retry_after,
                    }
                )
                summary["errors"] += 1

            except AuthenticationError as e:
                # Auth error - this affects all tags, raise immediately
                logger.error(
                    "Authentication failed for NewsAPI",
                    extra={"tag": tag, "error": str(e)},
                )
                emit_metric("IngestionErrors", 1)
                raise

            except AdapterError as e:
                # Other adapter error - log and continue
                logger.error(
                    f"Adapter error for tag {tag}",
                    extra={"tag": tag, "error": str(e)},
                )
                emit_metric("IngestionErrors", 1)
                errors.append(
                    {
                        "tag": tag,
                        "error": "ADAPTER_ERROR",
                        "message": str(e),
                    }
                )
                summary["errors"] += 1

            except Exception as e:
                # Unexpected error - log and continue
                logger.error(
                    f"Unexpected error for tag {tag}",
                    extra={"tag": tag, "error": str(e)},
                )
                emit_metric("IngestionErrors", 1)
                errors.append(
                    {
                        "tag": tag,
                        "error": "INTERNAL_ERROR",
                        "message": str(e),
                    }
                )
                summary["errors"] += 1

            # Record tag stats
            per_tag_stats[tag] = tag_stats

        # Calculate execution time
        execution_time_ms = (time.perf_counter() - start_time) * 1000

        # Emit metrics batch
        _emit_summary_metrics(summary, execution_time_ms)

        log_structured(
            "INFO",
            "Ingestion completed",
            **summary,
            execution_time_ms=round(execution_time_ms, 2),
        )

        # Build response
        response = {
            "statusCode": 200 if summary["errors"] == 0 else 207,
            "body": {
                "summary": summary,
                "per_tag_stats": per_tag_stats,
                "execution_time_ms": round(execution_time_ms, 2),
            },
        }

        if errors:
            response["body"]["errors"] = errors

        return response

    except ConfigurationError as e:
        # Configuration error - fail fast
        logger.error(f"Configuration error: {e}")
        emit_metric("IngestionErrors", 1)

        return {
            "statusCode": 500,
            "body": {
                "error": str(e),
                "code": "CONFIGURATION_ERROR",
            },
        }

    except AuthenticationError as e:
        # Authentication error - fail fast
        logger.error(f"Authentication error: {e}")
        emit_metric("IngestionErrors", 1)

        return {
            "statusCode": 401,
            "body": {
                "error": "NewsAPI authentication failed",
                "code": "AUTHENTICATION_ERROR",
            },
        }

    except Exception as e:
        # Unexpected error - fail
        logger.error(f"Unexpected error: {e}", exc_info=True)
        emit_metric("IngestionErrors", 1)

        return {
            "statusCode": 500,
            "body": {
                "error": "Internal error",
                "code": "INTERNAL_ERROR",
            },
        }


def _process_article(
    article: dict[str, Any],
    tag: str,
    table: Any,
    sns_client: Any,
    sns_topic_arn: str,
    model_version: str,
) -> str:
    """
    Process a single article: deduplicate, store, and publish to SNS.

    Args:
        article: NewsAPI article dict
        tag: Search tag that matched this article
        table: DynamoDB table resource
        sns_client: SNS client
        sns_topic_arn: SNS topic ARN for analysis requests
        model_version: Current model version

    Returns:
        "new" if article was inserted, "duplicate" if skipped

    On-Call Note:
        If many duplicates appear, check:
        1. Deduplication logic in generate_source_id
        2. Overlapping time windows in NewsAPI fetch
    """
    try:
        # Generate source_id for deduplication
        source_id = generate_source_id(article)
    except ValueError as e:
        # Article lacks required fields - skip
        logger.warning(
            "Skipping article - cannot generate source_id",
            extra={"error": str(e)},
        )
        return "duplicate"

    # Build DynamoDB item
    # Use article's published time for consistent deduplication
    # If not available, use current time
    published_at = article.get("publishedAt")
    if published_at:
        timestamp = published_at
    else:
        timestamp = datetime.now(UTC).isoformat()

    now = datetime.now(UTC)
    ttl_timestamp = int((now + timedelta(days=TTL_DAYS)).timestamp())

    item = {
        "source_id": source_id,
        "timestamp": timestamp,
        "source_type": "newsapi",
        "source_url": article.get("url", ""),
        "text_snippet": (article.get("description") or "")[:200],
        "text_for_analysis": _get_text_for_analysis(article),
        "status": "pending",
        "matched_tags": [tag],
        "ttl_timestamp": ttl_timestamp,
        "metadata": {
            "title": article.get("title", ""),
            "author": article.get("author") or "Unknown",
            "published_at": article.get("publishedAt", ""),
            "source_name": (article.get("source") or {}).get("name", ""),
        },
    }

    # Try to insert (conditional write for deduplication)
    if not put_item_if_not_exists(table, item):
        # Duplicate - already exists
        return "duplicate"

    # Publish to SNS for analysis
    sns_message = {
        "source_id": source_id,
        "source_type": "newsapi",
        "text_for_analysis": item["text_for_analysis"],
        "model_version": model_version,
        "matched_tags": [tag],
        "timestamp": timestamp,
    }

    try:
        sns_client.publish(
            TopicArn=sns_topic_arn,
            Message=json.dumps(sns_message),
            MessageAttributes={
                "source_type": {
                    "DataType": "String",
                    "StringValue": "newsapi",
                },
            },
        )

        logger.debug(
            "Published to SNS",
            extra={"source_id": source_id},
        )

    except Exception as e:
        # Log error but don't fail - analysis can be retriggered
        # On-Call Note: If SNS publish fails, check topic exists and permissions
        logger.error(
            f"Failed to publish to SNS: {e}",
            extra={"source_id": source_id, "error": str(e)},
        )
        emit_metric("SNSPublishErrors", 1)

    return "new"


def _get_text_for_analysis(article: dict[str, Any]) -> str:
    """
    Extract text for sentiment analysis from article.

    Priority:
    1. Title + description (preferred)
    2. Title only
    3. Content (fallback)

    Args:
        article: NewsAPI article dict

    Returns:
        Text string for analysis

    On-Call Note:
        If sentiment scores seem wrong, check text extraction.
        Log text_for_analysis field to verify content.
    """
    title = article.get("title", "")
    description = article.get("description", "")
    content = article.get("content", "")

    # Combine title and description if both available
    if title and description:
        return f"{title}. {description}"
    elif title:
        return title
    elif description:
        return description
    else:
        # Fallback to content (truncated by NewsAPI anyway)
        return content[:500] if content else ""


def _get_sns_client() -> Any:
    """
    Get an SNS client with retry configuration.

    Returns:
        boto3 SNS client

    On-Call Note:
        If SNS publish fails with credential errors, check:
        1. Lambda IAM role has sns:Publish permission
        2. Topic ARN is correct
    """
    import os

    region = os.environ.get("AWS_DEFAULT_REGION", "us-east-1")

    return boto3.client(
        "sns",
        region_name=region,
        config=SNS_RETRY_CONFIG,
    )


def _emit_summary_metrics(summary: dict[str, int], execution_time_ms: float) -> None:
    """
    Emit all summary metrics to CloudWatch.

    Args:
        summary: Summary counters dict
        execution_time_ms: Total execution time

    On-Call Note:
        These metrics power CloudWatch alarms:
        - NewItemsIngested = 0 for 6 runs → "No new items" alarm
        - ArticlesFetched = 0 → "No articles" alarm
    """
    metrics = [
        {
            "name": "ArticlesFetched",
            "value": summary["articles_fetched"],
            "unit": "Count",
        },
        {"name": "NewItemsIngested", "value": summary["new_items"], "unit": "Count"},
        {
            "name": "DuplicatesSkipped",
            "value": summary["duplicates_skipped"],
            "unit": "Count",
        },
        {"name": "ExecutionTimeMs", "value": execution_time_ms, "unit": "Milliseconds"},
    ]

    # Only emit error metric if there were errors
    if summary["errors"] > 0:
        metrics.append(
            {"name": "IngestionErrors", "value": summary["errors"], "unit": "Count"}
        )

    emit_metrics_batch(metrics)
