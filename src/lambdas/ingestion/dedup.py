"""Cross-source deduplication for parallel ingestion.

Provides headline-based deduplication to identify duplicate articles
across Tiingo and Finnhub sources.

Feature 1010: Parallel Ingestion with Cross-Source Deduplication
"""

import hashlib
import logging
import re
from datetime import datetime
from typing import Any

logger = logging.getLogger(__name__)


def normalize_headline(headline: str) -> str:
    """Normalize headline for cross-source comparison.

    Transforms headline to a canonical form that matches equivalent
    articles from different sources (e.g., Tiingo vs Finnhub).

    Normalization steps:
    1. Convert to lowercase
    2. Remove all punctuation (keep alphanumeric and spaces)
    3. Collapse multiple whitespace to single space
    4. Strip leading/trailing whitespace

    Args:
        headline: Original article headline

    Returns:
        Normalized headline string

    Examples:
        >>> normalize_headline("Apple Reports Q4 Earnings Beat - Reuters")
        'apple reports q4 earnings beat reuters'

        >>> normalize_headline("Apple reports Q4 earnings beat")
        'apple reports q4 earnings beat'
    """
    if not headline:
        return ""

    # Step 1: lowercase
    text = headline.lower()

    # Step 2: remove punctuation (keep alphanumeric, spaces, and unicode letters)
    text = re.sub(r"[^\w\s]", "", text, flags=re.UNICODE)

    # Step 3: collapse multiple whitespace to single space
    text = re.sub(r"\s+", " ", text)

    # Step 4: strip leading/trailing whitespace
    return text.strip()


def generate_dedup_key(headline: str, publish_date: str | datetime) -> str:
    """Generate cross-source deduplication key.

    Creates a deterministic key from normalized headline and publish date
    that uniquely identifies an article across sources.

    Key format: SHA256(normalized_headline | YYYY-MM-DD)[:32]

    The date component ensures that:
    - Same headline on different days creates different keys
    - Same article from different sources on same day matches

    Args:
        headline: Article headline (will be normalized)
        publish_date: Publication date (ISO8601 string or datetime)

    Returns:
        32-character hexadecimal dedup key

    Examples:
        >>> key1 = generate_dedup_key("Apple Reports Q4 Earnings", "2025-12-21T10:30:00Z")
        >>> key2 = generate_dedup_key("Apple reports Q4 earnings", "2025-12-21")
        >>> key1 == key2  # Same normalized headline, same date
        True
    """
    # Normalize headline
    normalized = normalize_headline(headline)

    # Extract date portion (YYYY-MM-DD)
    if isinstance(publish_date, datetime):
        date_part = publish_date.strftime("%Y-%m-%d")
    else:
        # Handle ISO8601 string - take first 10 chars (YYYY-MM-DD)
        date_part = str(publish_date)[:10]

    # Build composite key
    composite = f"{normalized}|{date_part}"

    # Generate SHA256 hash and truncate to 32 chars (128 bits)
    return hashlib.sha256(composite.encode("utf-8")).hexdigest()[:32]


def build_source_attribution(
    source: str,
    article_id: str,
    url: str,
    crawl_timestamp: datetime,
    original_headline: str,
    source_name: str | None = None,
) -> dict[str, Any]:
    """Build per-source attribution metadata.

    Creates a metadata dictionary for tracking article provenance
    from a specific source (Tiingo or Finnhub).

    Args:
        source: Source identifier (tiingo or finnhub)
        article_id: Source-specific article identifier
        url: Original article URL
        crawl_timestamp: When the source provided this article
        original_headline: Headline before normalization
        source_name: Wire service name (e.g., "reuters", "ap")

    Returns:
        Attribution dictionary for storage in source_attribution map

    Example:
        >>> attr = build_source_attribution(
        ...     source="tiingo",
        ...     article_id="91144751",
        ...     url="https://example.com/article",
        ...     crawl_timestamp=datetime.now(),
        ...     original_headline="Apple Reports Q4 Earnings Beat - Reuters",
        ...     source_name="reuters"
        ... )
    """
    attribution = {
        "article_id": str(article_id),
        "url": url or "",
        "crawl_timestamp": (
            crawl_timestamp.isoformat()
            if isinstance(crawl_timestamp, datetime)
            else str(crawl_timestamp)
        ),
        "original_headline": original_headline,
    }

    if source_name:
        attribution["source_name"] = source_name

    return attribution


def upsert_article_with_source(
    table: Any,
    dedup_key: str,
    timestamp: str,
    source: str,
    attribution: dict[str, Any],
    item_data: dict[str, Any],
) -> str:
    """Upsert article with source attribution using conditional writes.

    If article exists: Add source to sources[] array and merge attribution
    If article doesn't exist: Create new article with single source

    Uses DynamoDB conditional expressions for atomic updates.

    Args:
        table: DynamoDB table resource
        dedup_key: Cross-source deduplication key
        timestamp: Article publication timestamp (ISO8601)
        source: Source name (tiingo or finnhub)
        attribution: Source-specific metadata from build_source_attribution()
        item_data: Additional item fields for new articles

    Returns:
        "created" if new article, "updated" if source added to existing

    Raises:
        ClientError: On DynamoDB errors (other than condition check)
    """
    from botocore.exceptions import ClientError

    source_id = f"dedup:{dedup_key}"

    logger.debug(
        "Upserting article",
        extra={
            "dedup_key": dedup_key[:8],
            "source": source,
            "source_id": source_id[:16],
        },
    )

    try:
        # Try to update existing article (add source if not present)
        table.update_item(
            Key={"source_id": source_id, "timestamp": timestamp},
            UpdateExpression=(
                "SET sources = list_append(if_not_exists(sources, :empty_list), :new_source), "
                "source_attribution.#src = :attr, "
                "updated_at = :now"
            ),
            ExpressionAttributeNames={"#src": source},
            ExpressionAttributeValues={
                ":new_source": [source],
                ":attr": attribution,
                ":empty_list": [],
                ":now": datetime.now().isoformat(),
                ":existing_source": source,
            },
            ConditionExpression=(
                "attribute_exists(source_id) AND "
                "NOT contains(sources, :existing_source)"
            ),
        )
        logger.info(
            "Updated article with new source",
            extra={"dedup_key": dedup_key[:8], "source": source},
        )
        return "updated"

    except ClientError as e:
        error_code = e.response.get("Error", {}).get("Code", "")

        if error_code == "ConditionalCheckFailedException":
            # Either article doesn't exist OR source already present
            # Try to check if article exists with this source already
            try:
                response = table.get_item(
                    Key={"source_id": source_id, "timestamp": timestamp},
                    ProjectionExpression="sources",
                )
                if "Item" in response:
                    # Article exists, source must already be present
                    logger.debug(
                        "Duplicate article skipped",
                        extra={"dedup_key": dedup_key[:8], "source": source},
                    )
                    return "duplicate"
            except ClientError:
                pass  # Proceed to create

            # Article doesn't exist - create new
            item = {
                "source_id": source_id,
                "timestamp": timestamp,
                "dedup_key": dedup_key,
                "sources": [source],
                "source_attribution": {source: attribution},
                "created_at": datetime.now().isoformat(),
                "updated_at": datetime.now().isoformat(),
                **item_data,
            }

            try:
                table.put_item(
                    Item=item,
                    ConditionExpression="attribute_not_exists(source_id)",
                )
                logger.info(
                    "Created new article",
                    extra={"dedup_key": dedup_key[:8], "source": source},
                )
                return "created"
            except ClientError as create_error:
                # Race condition - another thread created it
                if (
                    create_error.response.get("Error", {}).get("Code")
                    == "ConditionalCheckFailedException"
                ):
                    # Retry the update
                    return upsert_article_with_source(
                        table, dedup_key, timestamp, source, attribution, item_data
                    )
                raise

        # Re-raise other errors
        raise
