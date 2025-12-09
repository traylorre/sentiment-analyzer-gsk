"""Deduplication utilities for market data ingestion.

Provides deterministic key generation for news article deduplication.
Key format: SHA256(headline|source|YYYY-MM-DD)[:32]
"""

import hashlib
from datetime import datetime


def generate_dedup_key(headline: str, source: str, published_at: datetime) -> str:
    """Generate a deterministic deduplication key for a news article.

    The key is a truncated SHA256 hash of the composite:
        headline|source|published_date (YYYY-MM-DD)

    This ensures:
    - Same article from same source on same day = same key (dedup works)
    - Different headlines = different key (no false positives)
    - Time-of-day variations = same key (articles republished same day)

    Args:
        headline: Article headline/title
        source: Data source identifier (e.g., "tiingo", "finnhub")
        published_at: Article publication timestamp

    Returns:
        32-character hexadecimal string (lowercase)

    Example:
        >>> generate_dedup_key("Apple Q4 Earnings", "tiingo", datetime(2025, 12, 9, 14, 30))
        'a1b2c3d4...' (32 hex chars)
    """
    # Normalize publication date to YYYY-MM-DD to handle time variations
    pub_date = published_at.strftime("%Y-%m-%d")

    # Build composite key with pipe separator
    composite = f"{headline}|{source}|{pub_date}"

    # Generate SHA256 and truncate to 32 chars (128 bits - sufficient for dedup)
    full_hash = hashlib.sha256(composite.encode("utf-8")).hexdigest()
    return full_hash[:32]


def generate_dedup_key_from_article(
    article_id: str,
    source: str,
) -> str:
    """Generate deduplication key from article ID and source.

    Alternative method when article has a unique ID from the source API.
    Useful as a faster fallback when headline is not available.

    Args:
        article_id: Unique identifier from source API
        source: Data source identifier

    Returns:
        32-character hexadecimal string (lowercase)
    """
    composite = f"{article_id}|{source}"
    return hashlib.sha256(composite.encode("utf-8")).hexdigest()[:32]
