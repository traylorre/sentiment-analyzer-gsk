"""News item storage with deduplication.

Provides storage operations for NewsItem entities with DynamoDB
conditional writes for deduplication per ADR-002.

Architecture:
    store_news_items() --> NewsItem.to_dynamodb_item()
                      --> put_item_if_not_exists() (conditional write)
    store_news_items_with_notification() --> store_news_items()
                                         --> NotificationPublisher.publish()
"""

import logging
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any, Literal

from botocore.exceptions import ClientError

from src.lambdas.shared.adapters.base import NewsArticle
from src.lambdas.shared.models.news_item import NewsItem
from src.lambdas.shared.utils.dedup import generate_dedup_key

if TYPE_CHECKING:
    from src.lambdas.ingestion.notification import NotificationPublisher

logger = logging.getLogger(__name__)


@dataclass
class StorageResult:
    """Result of storage operation.

    Attributes:
        items_stored: Number of new items successfully stored
        items_duplicate: Number of duplicates skipped
        items_failed: Number of items that failed to store (errors)
        errors: List of error messages
    """

    items_stored: int
    items_duplicate: int
    items_failed: int
    errors: list[str]


def store_news_items(
    table: Any,
    articles: list[NewsArticle],
    source: Literal["tiingo", "finnhub"],
) -> StorageResult:
    """Store news articles with deduplication.

    Converts NewsArticle objects to NewsItem entities and stores them
    in DynamoDB with conditional writes to prevent duplicates.

    Deduplication uses SHA256(headline|source|date)[:32] as the
    partition key per ADR-002.

    Args:
        table: DynamoDB Table resource
        articles: List of NewsArticle objects to store
        source: Data source identifier

    Returns:
        StorageResult with counts of stored, duplicated, and failed items

    Example:
        >>> result = store_news_items(table, articles, "tiingo")
        >>> logger.info(f"Stored {result.items_stored}, skipped {result.items_duplicate}")
    """
    items_stored = 0
    items_duplicate = 0
    items_failed = 0
    errors: list[str] = []

    ingested_at = datetime.now(UTC)

    for article in articles:
        try:
            # Generate deduplication key per ADR-002
            dedup_key = generate_dedup_key(
                headline=article.title,
                source=source,
                published_at=article.published_at,
            )

            # Create NewsItem entity
            news_item = NewsItem(
                dedup_key=dedup_key,
                source=source,
                headline=article.title,
                description=article.description,
                url=article.url,
                published_at=article.published_at,
                ingested_at=ingested_at,
                tickers=article.tickers,
                tags=article.tags or [],
                source_name=article.source_name,
            )

            # Store with conditional write for deduplication
            # Uses PK as condition since NewsItem uses PK/SK schema
            dynamo_item = news_item.to_dynamodb_item()
            if _put_news_item_if_not_exists(table, dynamo_item):
                items_stored += 1
                logger.debug(
                    "Stored news item",
                    extra={
                        "dedup_key": dedup_key[:8],
                        "source": source,
                        "headline": article.title[:50],
                    },
                )
            else:
                items_duplicate += 1
                logger.debug(
                    "Skipped duplicate",
                    extra={"dedup_key": dedup_key[:8], "source": source},
                )

        except ClientError as e:
            items_failed += 1
            error_msg = f"DynamoDB error: {e.response['Error']['Code']}"
            errors.append(error_msg)
            logger.error(
                "Failed to store news item",
                extra={
                    "error": error_msg,
                    "headline": article.title[:50] if article.title else "N/A",
                },
            )

        except Exception as e:
            items_failed += 1
            error_msg = f"Unexpected error: {str(e)}"
            errors.append(error_msg)
            logger.exception(
                "Unexpected error storing news item",
                extra={"headline": article.title[:50] if article.title else "N/A"},
            )

    logger.info(
        "Storage operation complete",
        extra={
            "source": source,
            "stored": items_stored,
            "duplicates": items_duplicate,
            "failed": items_failed,
        },
    )

    return StorageResult(
        items_stored=items_stored,
        items_duplicate=items_duplicate,
        items_failed=items_failed,
        errors=errors,
    )


def article_to_news_item(
    article: NewsArticle,
    source: Literal["tiingo", "finnhub"],
    ingested_at: datetime | None = None,
) -> NewsItem:
    """Convert a NewsArticle to NewsItem entity.

    Helper function for converting adapter output to storage model.

    Args:
        article: NewsArticle from adapter
        source: Data source identifier
        ingested_at: Ingestion timestamp (default: now)

    Returns:
        NewsItem entity ready for storage
    """
    if ingested_at is None:
        ingested_at = datetime.now(UTC)

    dedup_key = generate_dedup_key(
        headline=article.title,
        source=source,
        published_at=article.published_at,
    )

    return NewsItem(
        dedup_key=dedup_key,
        source=source,
        headline=article.title,
        description=article.description,
        url=article.url,
        published_at=article.published_at,
        ingested_at=ingested_at,
        tickers=article.tickers,
        tags=article.tags or [],
        source_name=article.source_name,
    )


def get_duplicate_rate(result: StorageResult) -> float:
    """Calculate duplicate rate from storage result.

    Args:
        result: StorageResult from store_news_items()

    Returns:
        Duplicate rate as float (0.0 to 1.0), or 0.0 if no items processed
    """
    total = result.items_stored + result.items_duplicate + result.items_failed
    if total == 0:
        return 0.0
    return result.items_duplicate / total


def _put_news_item_if_not_exists(table: Any, item: dict[str, Any]) -> bool:
    """Put a news item only if it doesn't already exist.

    Uses conditional write on PK (partition key) to prevent duplicates.
    This is specific to the NewsItem schema which uses PK/SK keys.

    Args:
        table: DynamoDB Table resource
        item: DynamoDB item with PK and SK keys

    Returns:
        True if item was created, False if it already existed
    """
    try:
        table.put_item(
            Item=item,
            ConditionExpression="attribute_not_exists(PK)",
        )
        return True
    except table.meta.client.exceptions.ConditionalCheckFailedException:
        # Item already exists - expected for deduplication
        return False


def store_news_items_with_notification(
    table: Any,
    articles: list[NewsArticle],
    source: Literal["tiingo", "finnhub"],
    notification_publisher: "NotificationPublisher",
    collection_timestamp: datetime,
    is_failover: bool = False,
) -> tuple[StorageResult, str | None]:
    """Store news articles and send downstream notification.

    Combines storage with notification for the FR-004 requirement:
    "Notify dependent systems within 30 seconds of new data storage"

    Args:
        table: DynamoDB Table resource
        articles: List of NewsArticle objects to store
        source: Data source identifier
        notification_publisher: Publisher for downstream notifications
        collection_timestamp: When the collection occurred
        is_failover: Whether failover source was used

    Returns:
        Tuple of (StorageResult, notification_message_id or None)

    Example:
        >>> result, msg_id = store_news_items_with_notification(
        ...     table, articles, "tiingo", publisher, datetime.now(UTC)
        ... )
    """
    # Avoid circular import
    from src.lambdas.ingestion.notification import NewDataNotification

    # Store items first
    result = store_news_items(table, articles, source)

    # Send notification if any items were stored
    notification_id = None
    if result.items_stored > 0:
        notification = NewDataNotification(
            items_stored=result.items_stored,
            source=source,
            collection_timestamp=collection_timestamp,
            is_failover=is_failover,
            items_duplicate=result.items_duplicate,
        )
        notification_id = notification_publisher.publish(notification)

        logger.info(
            "Sent downstream notification",
            extra={
                "notification_id": notification_id,
                "items_stored": result.items_stored,
                "source": source,
            },
        )

    return result, notification_id
