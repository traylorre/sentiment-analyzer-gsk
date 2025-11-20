"""
Deduplication Module
====================

Generates stable, unique identifiers for articles to prevent reprocessing.

For On-Call Engineers:
    If duplicate articles appear in the dashboard:
    1. Check source_id generation - should be deterministic
    2. Same URL should always produce same source_id
    3. Hash collisions are extremely rare (SHA-256)

    If no duplicates but items are missing:
    1. Check if URL changed but content is same (expected behavior)
    2. Different URLs = different source_ids

    See SC-03 in ON_CALL_SOP.md for ingestion issues.

For Developers:
    - source_id = "newsapi#{sha256[:16]}"
    - Prefer URL for hashing, fallback to title+publishedAt
    - Hash is truncated to 16 chars for readability (still 64 bits of entropy)

Security Notes:
    - SHA-256 is cryptographically secure (no collision attacks)
    - Never use user-controlled input directly in hash without validation
    - Article content is NOT hashed (only metadata)
"""

import hashlib
import logging
from typing import Any

from src.lib.logging_utils import log_expected_warning

# Structured logging for CloudWatch
logger = logging.getLogger(__name__)

# Source prefix for NewsAPI articles
SOURCE_PREFIX = "newsapi"


def generate_source_id(article: dict[str, Any]) -> str:
    """
    Generate a unique, deterministic source_id for an article.

    Algorithm:
    1. Extract URL from article (preferred)
    2. If no URL, use title + publishedAt as fallback
    3. SHA-256 hash the content
    4. Truncate to 16 characters
    5. Prepend source prefix

    Args:
        article: NewsAPI article dict with url, title, publishedAt fields

    Returns:
        source_id in format "newsapi#{hash16}"

    Raises:
        ValueError: If article lacks required fields for hashing

    Examples:
        >>> article = {"url": "https://example.com/article/123", "title": "Test", "publishedAt": "2025-11-17T14:30:00Z"}
        >>> source_id = generate_source_id(article)
        >>> source_id
        'newsapi#a1b2c3d4e5f6g7h8'

    On-Call Note:
        Same article will always produce same source_id.
        If duplicates appear, check if articles have different URLs.
    """
    # Get content to hash
    hash_content = _get_hash_content(article)

    # Generate SHA-256 hash
    hash_bytes = hashlib.sha256(hash_content.encode("utf-8")).hexdigest()

    # Truncate to 16 characters (64 bits of entropy)
    hash_truncated = hash_bytes[:16]

    # Build source_id
    source_id = f"{SOURCE_PREFIX}#{hash_truncated}"

    logger.debug(
        "Generated source_id",
        extra={
            "source_id": source_id,
            "hash_input_length": len(hash_content),
        },
    )

    return source_id


def _get_hash_content(article: dict[str, Any]) -> str:
    """
    Extract content to hash from article.

    Priority:
    1. URL (preferred - most stable identifier)
    2. title + publishedAt (fallback if URL missing)

    Args:
        article: NewsAPI article dict

    Returns:
        String content to hash

    Raises:
        ValueError: If neither URL nor title+publishedAt available
    """
    # Prefer URL
    url = article.get("url")
    if url:
        return url

    # Fallback to title + publishedAt
    title = article.get("title")
    published_at = article.get("publishedAt")

    if title and published_at:
        log_expected_warning(
            logger,
            "Using title+publishedAt for deduplication (URL missing)",
            extra={"title": title[:50]},  # Truncate for logging
        )
        return f"{title}|{published_at}"

    # Cannot generate hash
    raise ValueError(
        "Article must have 'url' or both 'title' and 'publishedAt' for deduplication"
    )


def is_duplicate(source_id: str, existing_ids: set[str]) -> bool:
    """
    Check if a source_id already exists.

    Simple set membership check for in-memory deduplication.

    Args:
        source_id: Generated source_id to check
        existing_ids: Set of known source_ids

    Returns:
        True if duplicate, False if new

    Example:
        >>> existing = {"newsapi#abc123", "newsapi#def456"}
        >>> is_duplicate("newsapi#abc123", existing)
        True
        >>> is_duplicate("newsapi#new789", existing)
        False
    """
    return source_id in existing_ids


def extract_hash(source_id: str) -> str:
    """
    Extract the hash portion from a source_id.

    Args:
        source_id: Full source_id (e.g., "newsapi#abc123def456")

    Returns:
        Hash portion (e.g., "abc123def456")

    Raises:
        ValueError: If source_id format is invalid
    """
    if not source_id or "#" not in source_id:
        raise ValueError(f"Invalid source_id format: {source_id}")

    parts = source_id.split("#", 1)
    if len(parts) != 2:
        raise ValueError(f"Invalid source_id format: {source_id}")

    return parts[1]


def get_source_prefix(source_id: str) -> str:
    """
    Extract the source prefix from a source_id.

    Args:
        source_id: Full source_id (e.g., "newsapi#abc123def456")

    Returns:
        Source prefix (e.g., "newsapi")

    Raises:
        ValueError: If source_id format is invalid
    """
    if not source_id or "#" not in source_id:
        raise ValueError(f"Invalid source_id format: {source_id}")

    parts = source_id.split("#", 1)
    return parts[0]


def generate_correlation_id(source_id: str, request_id: str) -> str:
    """
    Generate a correlation ID for distributed tracing.

    Format: {source_id}-{request_id}

    Used to trace an item through the entire pipeline:
    Ingestion → SNS → Analysis → Dashboard

    Args:
        source_id: Article source_id
        request_id: Lambda request ID (from context.aws_request_id)

    Returns:
        Correlation ID for logging

    Example:
        >>> generate_correlation_id("newsapi#abc123", "req-456")
        'newsapi#abc123-req-456'

    On-Call Note:
        Use this ID to search CloudWatch logs across all Lambdas:
        filter @message like /newsapi#abc123-req-456/
    """
    return f"{source_id}-{request_id}"


def batch_deduplicate(
    articles: list[dict[str, Any]],
    existing_ids: set[str] | None = None,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], set[str]]:
    """
    Deduplicate a batch of articles.

    Processes a list of articles, separating new items from duplicates.
    Also deduplicates within the batch itself.

    Args:
        articles: List of NewsAPI article dicts
        existing_ids: Optional set of already-known source_ids

    Returns:
        Tuple of (new_articles, duplicate_articles, all_ids)
        - new_articles: Articles to process (with source_id added)
        - duplicate_articles: Skipped duplicates
        - all_ids: Updated set of all source_ids

    Example:
        >>> articles = [{"url": "https://a.com"}, {"url": "https://b.com"}, {"url": "https://a.com"}]
        >>> new, dups, ids = batch_deduplicate(articles)
        >>> len(new)
        2
        >>> len(dups)
        1

    On-Call Note:
        If new_articles is always empty, check:
        1. existing_ids contains all incoming URLs
        2. EventBridge schedule overlaps causing reprocessing
    """
    if existing_ids is None:
        existing_ids = set()

    new_articles = []
    duplicate_articles = []
    seen_in_batch: set[str] = set()

    for article in articles:
        try:
            source_id = generate_source_id(article)
        except ValueError as e:
            log_expected_warning(
                logger,
                "Skipping article - cannot generate source_id",
                extra={"error": str(e)},
            )
            continue

        # Check if duplicate (either in existing or in this batch)
        if source_id in existing_ids or source_id in seen_in_batch:
            duplicate_articles.append(article)
            logger.debug(
                "Duplicate article skipped",
                extra={"source_id": source_id},
            )
        else:
            # Add source_id to article
            article["source_id"] = source_id
            new_articles.append(article)
            seen_in_batch.add(source_id)

    # Combine all known IDs
    all_ids = existing_ids | seen_in_batch

    logger.info(
        "Batch deduplication complete",
        extra={
            "total_articles": len(articles),
            "new_articles": len(new_articles),
            "duplicates": len(duplicate_articles),
        },
    )

    return new_articles, duplicate_articles, all_ids
