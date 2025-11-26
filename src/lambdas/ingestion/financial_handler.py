"""
Financial News Ingestion Lambda Handler
=======================================

EventBridge-triggered Lambda that fetches financial news from Tiingo and Finnhub
for user-configured tickers and publishes to SNS for sentiment analysis.

For On-Call Engineers:
    This Lambda runs every 5 minutes via EventBridge scheduler.

    Common issues:
    - Rate limit exceeded - Check circuit breaker state and quota tracker
    - No articles fetched - Verify API keys in Secrets Manager
    - High deduplication rate - Normal for active tickers, check DynamoDB TTL

    Quick commands:
    # Check recent invocations
    aws logs tail /aws/lambda/${environment}-sentiment-ingestion --since 1h

    # Check rate limit metrics
    aws cloudwatch get-metric-statistics \
      --namespace SentimentAnalyzer \
      --metric-name APIRateLimitHit \
      --start-time $(date -d '1 hour ago' -u +%Y-%m-%dT%H:%M:%SZ) \
      --end-time $(date -u +%Y-%m-%dT%H:%M:%SZ) \
      --period 3600 --statistics Sum

    See ON_CALL_SOP.md for detailed runbooks.

For Developers:
    Handler workflow:
    1. Load active configurations from DynamoDB
    2. Aggregate unique tickers across all configurations
    3. Check circuit breaker state for each API
    4. Fetch articles from Tiingo (primary) and Finnhub (secondary)
    5. Deduplicate against DynamoDB
    6. Insert new items (status=pending)
    7. Publish to SNS for sentiment analysis
    8. Emit CloudWatch metrics

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

from src.lambdas.shared.adapters.base import (
    AdapterError,
    NewsArticle,
    RateLimitError,
)
from src.lambdas.shared.adapters.finnhub import FinnhubAdapter
from src.lambdas.shared.adapters.tiingo import TiingoAdapter
from src.lambdas.shared.circuit_breaker import CircuitBreakerState
from src.lambdas.shared.dynamodb import get_table, put_item_if_not_exists
from src.lambdas.shared.logging_utils import get_safe_error_info, sanitize_for_log
from src.lambdas.shared.quota_tracker import QuotaTracker
from src.lambdas.shared.secrets import get_api_key
from src.lib.metrics import emit_metric, emit_metrics_batch

# Structured logging
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

# SNS client configuration
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

# Circuit breaker settings
CIRCUIT_BREAKER_THRESHOLD = 5
CIRCUIT_BREAKER_TIMEOUT = 300  # 5 minutes

# Quota settings (free tier limits)
TIINGO_DAILY_LIMIT = 500
FINNHUB_DAILY_LIMIT = 1000  # 60 calls/minute ≈ 1000 safe calls/day


def lambda_handler(event: dict[str, Any], context: Any) -> dict[str, Any]:
    """
    Main Lambda handler for financial news ingestion.

    Triggered by EventBridge scheduler every 5 minutes.

    Args:
        event: EventBridge scheduled event
        context: Lambda context (contains aws_request_id)

    Returns:
        Response with status and summary
    """
    start_time = time.perf_counter()
    request_id = getattr(context, "aws_request_id", "unknown")

    logger.info(
        "Financial ingestion started",
        extra={
            "request_id": sanitize_for_log(request_id[:8]),
            "event_source": event.get("source", "unknown"),
        },
    )

    # Initialize counters
    summary = {
        "tickers_processed": 0,
        "articles_fetched": 0,
        "new_items": 0,
        "duplicates_skipped": 0,
        "tiingo_articles": 0,
        "finnhub_articles": 0,
        "errors": 0,
    }
    per_ticker_stats: dict[str, dict[str, int]] = {}
    errors: list[dict[str, Any]] = []

    try:
        # Load configuration from environment
        config = _get_config()

        # Get DynamoDB table
        table = get_table(config["dynamodb_table"])

        # Get unique tickers from all active configurations
        tickers = _get_active_tickers(table)

        if not tickers:
            logger.info("No active tickers found, skipping ingestion")
            return {
                "statusCode": 200,
                "body": {"message": "No active tickers", "summary": summary},
            }

        logger.info(
            "Found active tickers",
            extra={"ticker_count": len(tickers), "tickers": tickers[:10]},
        )

        # Initialize circuit breakers (load from DynamoDB or create default)
        tiingo_breaker = _get_or_create_circuit_breaker(table, "tiingo")
        finnhub_breaker = _get_or_create_circuit_breaker(table, "finnhub")

        # Get quota tracker (load from DynamoDB or create default)
        quota_tracker = _get_or_create_quota_tracker(table)

        # Get API keys from Secrets Manager
        tiingo_key = get_api_key(config["tiingo_secret_arn"])
        finnhub_key = get_api_key(config["finnhub_secret_arn"])

        # Initialize adapters
        tiingo_adapter = TiingoAdapter(api_key=tiingo_key) if tiingo_key else None
        finnhub_adapter = FinnhubAdapter(api_key=finnhub_key) if finnhub_key else None

        # Get SNS client
        sns_client = _get_sns_client(config["aws_region"])

        try:
            # Process each ticker
            for ticker in tickers:
                ticker_stats = {
                    "tiingo": 0,
                    "finnhub": 0,
                    "new": 0,
                    "duplicates": 0,
                }

                # Fetch from Tiingo (primary source)
                if tiingo_adapter and tiingo_breaker.can_execute():
                    if quota_tracker.can_call("tiingo"):
                        try:
                            articles = _fetch_tiingo_articles(
                                tiingo_adapter, [ticker], quota_tracker
                            )
                            ticker_stats["tiingo"] = len(articles)
                            summary["tiingo_articles"] += len(articles)

                            # Process each article
                            for article in articles:
                                result = _process_article(
                                    article=article,
                                    source="tiingo",
                                    table=table,
                                    sns_client=sns_client,
                                    sns_topic_arn=config["sns_topic_arn"],
                                    model_version=config["model_version"],
                                )
                                if result == "new":
                                    ticker_stats["new"] += 1
                                    summary["new_items"] += 1
                                else:
                                    ticker_stats["duplicates"] += 1
                                    summary["duplicates_skipped"] += 1

                            tiingo_breaker.record_success()

                        except RateLimitError as e:
                            logger.warning(
                                "Tiingo rate limited",
                                extra={
                                    "ticker": sanitize_for_log(ticker),
                                    "retry_after": e.retry_after,
                                },
                            )
                            emit_metric(
                                "APIRateLimitHit", 1, dimensions={"Source": "tiingo"}
                            )
                            tiingo_breaker.record_failure()
                            errors.append(
                                {
                                    "ticker": ticker,
                                    "source": "tiingo",
                                    "error": "RATE_LIMIT",
                                }
                            )
                            summary["errors"] += 1

                        except AdapterError as e:
                            logger.error(
                                "Tiingo adapter error",
                                extra={
                                    "ticker": sanitize_for_log(ticker),
                                    **get_safe_error_info(e),
                                },
                            )
                            tiingo_breaker.record_failure()
                            summary["errors"] += 1

                # Fetch from Finnhub (secondary source)
                if finnhub_adapter and finnhub_breaker.can_execute():
                    if quota_tracker.can_call("finnhub"):
                        try:
                            articles = _fetch_finnhub_articles(
                                finnhub_adapter, [ticker], quota_tracker
                            )
                            ticker_stats["finnhub"] = len(articles)
                            summary["finnhub_articles"] += len(articles)

                            # Process each article
                            for article in articles:
                                result = _process_article(
                                    article=article,
                                    source="finnhub",
                                    table=table,
                                    sns_client=sns_client,
                                    sns_topic_arn=config["sns_topic_arn"],
                                    model_version=config["model_version"],
                                )
                                if result == "new":
                                    ticker_stats["new"] += 1
                                    summary["new_items"] += 1
                                else:
                                    ticker_stats["duplicates"] += 1
                                    summary["duplicates_skipped"] += 1

                            finnhub_breaker.record_success()

                        except RateLimitError as e:
                            logger.warning(
                                "Finnhub rate limited",
                                extra={
                                    "ticker": sanitize_for_log(ticker),
                                    "retry_after": e.retry_after,
                                },
                            )
                            emit_metric(
                                "APIRateLimitHit", 1, dimensions={"Source": "finnhub"}
                            )
                            finnhub_breaker.record_failure()
                            errors.append(
                                {
                                    "ticker": ticker,
                                    "source": "finnhub",
                                    "error": "RATE_LIMIT",
                                }
                            )
                            summary["errors"] += 1

                        except AdapterError as e:
                            logger.error(
                                "Finnhub adapter error",
                                extra={
                                    "ticker": sanitize_for_log(ticker),
                                    **get_safe_error_info(e),
                                },
                            )
                            finnhub_breaker.record_failure()
                            summary["errors"] += 1

                summary["articles_fetched"] += (
                    ticker_stats["tiingo"] + ticker_stats["finnhub"]
                )
                summary["tickers_processed"] += 1
                per_ticker_stats[ticker] = ticker_stats

        finally:
            # Save state to DynamoDB
            _save_circuit_breaker(table, tiingo_breaker)
            _save_circuit_breaker(table, finnhub_breaker)
            _save_quota_tracker(table, quota_tracker)

            # Clean up adapters
            if tiingo_adapter:
                tiingo_adapter.close()
            if finnhub_adapter:
                finnhub_adapter.close()

        # Calculate execution time
        execution_time_ms = (time.perf_counter() - start_time) * 1000

        # Emit metrics
        _emit_summary_metrics(summary, execution_time_ms)

        logger.info(
            "Financial ingestion completed",
            extra={
                **summary,
                "execution_time_ms": round(execution_time_ms, 2),
            },
        )

        response = {
            "statusCode": 200 if summary["errors"] == 0 else 207,
            "body": {
                "summary": summary,
                "per_ticker_stats": per_ticker_stats,
                "execution_time_ms": round(execution_time_ms, 2),
            },
        }

        if errors:
            response["body"]["errors"] = errors

        return response

    except Exception as e:
        logger.error("Financial ingestion failed", extra=get_safe_error_info(e))
        emit_metric("IngestionErrors", 1)

        return {
            "statusCode": 500,
            "body": {
                "error": "Internal error",
                "code": "INTERNAL_ERROR",
            },
        }


def _get_config() -> dict[str, str]:
    """Load configuration from environment variables."""
    import os

    # Cloud-agnostic: Use CLOUD_REGION, fallback to AWS_REGION
    aws_region = os.environ.get("CLOUD_REGION") or os.environ.get("AWS_REGION")
    if not aws_region:
        raise ValueError("CLOUD_REGION or AWS_REGION environment variable must be set")

    return {
        "dynamodb_table": os.environ.get("DATABASE_TABLE")
        or os.environ.get("DYNAMODB_TABLE", ""),
        "sns_topic_arn": os.environ.get("SNS_TOPIC_ARN", ""),
        "tiingo_secret_arn": os.environ.get("TIINGO_SECRET_ARN", ""),
        "finnhub_secret_arn": os.environ.get("FINNHUB_SECRET_ARN", ""),
        "model_version": os.environ.get("MODEL_VERSION", "v1.0.0"),
        "aws_region": aws_region,
    }


def _get_active_tickers(table: Any) -> list[str]:
    """Get unique tickers from all active user configurations.

    Args:
        table: DynamoDB Table resource

    Returns:
        List of unique ticker symbols
    """
    tickers_set: set[str] = set()

    try:
        # Query all configurations (using GSI or scan)
        # For efficiency, we scan with filter on entity_type
        response = table.scan(
            FilterExpression="entity_type = :et AND is_active = :active",
            ExpressionAttributeValues={
                ":et": "CONFIGURATION",
                ":active": True,
            },
            ProjectionExpression="tickers",
        )

        for item in response.get("Items", []):
            for ticker in item.get("tickers", []):
                if isinstance(ticker, dict):
                    symbol = ticker.get("symbol", "")
                else:
                    symbol = ticker
                if symbol:
                    tickers_set.add(symbol.upper())

        # Handle pagination
        while "LastEvaluatedKey" in response:
            response = table.scan(
                FilterExpression="entity_type = :et AND is_active = :active",
                ExpressionAttributeValues={
                    ":et": "CONFIGURATION",
                    ":active": True,
                },
                ProjectionExpression="tickers",
                ExclusiveStartKey=response["LastEvaluatedKey"],
            )
            for item in response.get("Items", []):
                for ticker in item.get("tickers", []):
                    if isinstance(ticker, dict):
                        symbol = ticker.get("symbol", "")
                    else:
                        symbol = ticker
                    if symbol:
                        tickers_set.add(symbol.upper())

    except Exception as e:
        logger.error("Failed to get active tickers", extra=get_safe_error_info(e))
        return []

    return sorted(tickers_set)


def _get_or_create_circuit_breaker(table: Any, service: str) -> CircuitBreakerState:
    """Get circuit breaker from DynamoDB or create default.

    Args:
        table: DynamoDB Table resource
        service: Service name (tiingo, finnhub, sendgrid)

    Returns:
        CircuitBreakerState instance
    """
    try:
        response = table.get_item(
            Key={
                "PK": f"CIRCUIT#{service}",
                "SK": "STATE",
            }
        )
        item = response.get("Item")
        if item:
            return CircuitBreakerState.from_dynamodb_item(item)
    except Exception as e:
        logger.warning(
            "Failed to load circuit breaker",
            extra={"service": service, **get_safe_error_info(e)},
        )

    # Create default
    return CircuitBreakerState.create_default(service)


def _save_circuit_breaker(table: Any, breaker: CircuitBreakerState) -> None:
    """Save circuit breaker state to DynamoDB.

    Args:
        table: DynamoDB Table resource
        breaker: CircuitBreakerState to save
    """
    try:
        table.put_item(Item=breaker.to_dynamodb_item())
    except Exception as e:
        logger.warning(
            "Failed to save circuit breaker",
            extra={"service": breaker.service, **get_safe_error_info(e)},
        )


def _get_or_create_quota_tracker(table: Any) -> QuotaTracker:
    """Get quota tracker from DynamoDB or create default.

    Args:
        table: DynamoDB Table resource

    Returns:
        QuotaTracker instance
    """
    try:
        today = datetime.now(UTC).strftime("%Y-%m-%d")
        response = table.get_item(
            Key={
                "PK": "SYSTEM#QUOTA",
                "SK": today,
            }
        )
        item = response.get("Item")
        if item:
            return QuotaTracker.from_dynamodb_item(item)
    except Exception as e:
        logger.warning(
            "Failed to load quota tracker",
            extra=get_safe_error_info(e),
        )

    # Create default
    return QuotaTracker.create_default()


def _save_quota_tracker(table: Any, tracker: QuotaTracker) -> None:
    """Save quota tracker to DynamoDB.

    Args:
        table: DynamoDB Table resource
        tracker: QuotaTracker to save
    """
    try:
        table.put_item(Item=tracker.to_dynamodb_item())
    except Exception as e:
        logger.warning(
            "Failed to save quota tracker",
            extra=get_safe_error_info(e),
        )


def _fetch_tiingo_articles(
    adapter: TiingoAdapter,
    tickers: list[str],
    quota_tracker: QuotaTracker,
) -> list[NewsArticle]:
    """Fetch articles from Tiingo for given tickers.

    Args:
        adapter: Tiingo API adapter
        tickers: List of ticker symbols
        quota_tracker: Quota tracker for rate limiting

    Returns:
        List of NewsArticle objects
    """
    # Record API call
    quota_tracker.record_call("tiingo", count=1)

    # Fetch news for last 7 days
    end_date = datetime.now(UTC)
    start_date = end_date - timedelta(days=7)

    articles = adapter.get_news(
        tickers=tickers,
        start_date=start_date,
        end_date=end_date,
        limit=50,
    )

    return articles


def _fetch_finnhub_articles(
    adapter: FinnhubAdapter,
    tickers: list[str],
    quota_tracker: QuotaTracker,
) -> list[NewsArticle]:
    """Fetch articles from Finnhub for given tickers.

    Args:
        adapter: Finnhub API adapter
        tickers: List of ticker symbols
        quota_tracker: Quota tracker for rate limiting

    Returns:
        List of NewsArticle objects
    """
    # Record API call
    quota_tracker.record_call("finnhub", count=1)

    # Fetch news for last 7 days
    end_date = datetime.now(UTC)
    start_date = end_date - timedelta(days=7)

    articles = adapter.get_news(
        tickers=tickers,
        start_date=start_date,
        end_date=end_date,
        limit=50,
    )

    return articles


def _process_article(
    article: NewsArticle,
    source: str,
    table: Any,
    sns_client: Any,
    sns_topic_arn: str,
    model_version: str,
) -> str:
    """Process a single article: deduplicate, store, and publish to SNS.

    Args:
        article: NewsArticle object
        source: Source name (tiingo or finnhub)
        table: DynamoDB table resource
        sns_client: SNS client
        sns_topic_arn: SNS topic ARN for analysis requests
        model_version: Current model version

    Returns:
        "new" if article was inserted, "duplicate" if skipped
    """
    # Generate source_id for deduplication
    source_id = f"{source}:{article.article_id}"

    # Build DynamoDB item
    now = datetime.now(UTC)
    ttl_timestamp = int((now + timedelta(days=TTL_DAYS)).timestamp())

    item = {
        "source_id": source_id,
        "timestamp": article.published_at.isoformat(),
        "source_type": source,
        "source_url": article.url or "",
        "text_snippet": (article.description or "")[:200],
        "text_for_analysis": _get_text_for_analysis(article),
        "status": "pending",
        "matched_tickers": article.tickers,
        "ttl_timestamp": ttl_timestamp,
        "metadata": {
            "title": article.title,
            "published_at": article.published_at.isoformat(),
            "source_name": article.source_name or source,
            "tags": article.tags or [],
        },
    }

    # Try to insert (conditional write for deduplication)
    if not put_item_if_not_exists(table, item):
        return "duplicate"

    # Publish to SNS for analysis
    sns_message = {
        "source_id": source_id,
        "source_type": source,
        "text_for_analysis": item["text_for_analysis"],
        "model_version": model_version,
        "matched_tickers": article.tickers,
        "timestamp": article.published_at.isoformat(),
    }

    try:
        sns_client.publish(
            TopicArn=sns_topic_arn,
            Message=json.dumps(sns_message),
            MessageAttributes={
                "source_type": {
                    "DataType": "String",
                    "StringValue": source,
                },
            },
        )

        logger.debug(
            "Published to SNS",
            extra={"source_id": sanitize_for_log(source_id[:20])},
        )

    except Exception as e:
        logger.error(
            "Failed to publish to SNS",
            extra={
                "source_id": sanitize_for_log(source_id[:20]),
                **get_safe_error_info(e),
            },
        )
        emit_metric("SNSPublishErrors", 1)

    return "new"


def _get_text_for_analysis(article: NewsArticle) -> str:
    """Extract text for sentiment analysis from article.

    Args:
        article: NewsArticle object

    Returns:
        Text string for analysis
    """
    title = article.title or ""
    description = article.description or ""

    # Combine title and description if both available
    if title and description:
        return f"{title}. {description}"
    elif title:
        return title
    else:
        return description[:500] if description else ""


def _get_sns_client(region: str) -> Any:
    """Get an SNS client with retry configuration.

    Args:
        region: AWS region

    Returns:
        boto3 SNS client
    """
    return boto3.client(
        "sns",
        region_name=region,
        config=SNS_RETRY_CONFIG,
    )


def _emit_summary_metrics(summary: dict[str, int], execution_time_ms: float) -> None:
    """Emit all summary metrics to CloudWatch.

    Args:
        summary: Summary counters dict
        execution_time_ms: Total execution time
    """
    metrics = [
        {
            "name": "ArticlesFetched",
            "value": summary["articles_fetched"],
            "unit": "Count",
        },
        {
            "name": "NewItemsIngested",
            "value": summary["new_items"],
            "unit": "Count",
        },
        {
            "name": "DuplicatesSkipped",
            "value": summary["duplicates_skipped"],
            "unit": "Count",
        },
        {
            "name": "TiingoArticles",
            "value": summary["tiingo_articles"],
            "unit": "Count",
        },
        {
            "name": "FinnhubArticles",
            "value": summary["finnhub_articles"],
            "unit": "Count",
        },
        {
            "name": "ExecutionTimeMs",
            "value": execution_time_ms,
            "unit": "Milliseconds",
        },
    ]

    if summary["errors"] > 0:
        metrics.append(
            {"name": "IngestionErrors", "value": summary["errors"], "unit": "Count"}
        )

    emit_metrics_batch(metrics)
