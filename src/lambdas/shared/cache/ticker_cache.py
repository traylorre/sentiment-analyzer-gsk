"""Ticker cache for US stock symbol validation and autocomplete.

Loads ~8K US stock symbols from S3 with TTL-based refresh.

Feature 1224: Replaced cold-start-only @lru_cache with TTL + S3 ETag
conditional refresh. Checks S3 ETag every TICKER_CACHE_TTL seconds
(default 5 min) and only re-downloads if the list changed.
"""

import json
import logging
import os
import threading
import time
from datetime import UTC, datetime
from typing import Literal

import boto3
from pydantic import BaseModel, Field

from src.lambdas.shared.retry import s3_retry
from src.lib.cache_utils import CacheStats, jittered_ttl, validate_non_empty

logger = logging.getLogger(__name__)

# Feature 1224: TTL-based refresh interval (default 5 minutes)
TICKER_CACHE_TTL = int(os.environ.get("TICKER_CACHE_TTL", "300"))


class TickerInfo(BaseModel):
    """Cached ticker information for autocomplete and validation."""

    symbol: str = Field(..., pattern=r"^[A-Z]{1,5}$")
    name: str
    exchange: Literal["NYSE", "NASDAQ", "AMEX"]
    sector: str | None = None
    industry: str | None = None

    # Delisting info
    is_active: bool = True
    delisted_at: datetime | None = None
    successor_symbol: str | None = None
    delisting_reason: str | None = None


class TickerCache(BaseModel):
    """Static cache of ~8K US stock symbols.

    Loaded at Lambda cold start from S3 JSON file.
    Updated weekly via scheduled job.
    """

    version: str  # ISO date of last update
    updated_at: datetime
    symbols: dict[str, TickerInfo]  # {symbol: TickerInfo}

    # Statistics
    total_active: int
    total_delisted: int
    exchanges: dict[str, int]  # {exchange: count}

    model_config = {"arbitrary_types_allowed": True}

    @classmethod
    def load_from_s3(cls, bucket: str, key: str) -> "TickerCache":
        """Load cache from S3 bucket.

        Feature 1032: Added retry logic for transient S3 failures.

        Args:
            bucket: S3 bucket name
            key: S3 object key (e.g., "ticker-cache/us-symbols.json")

        Returns:
            TickerCache instance

        Raises:
            ValueError: If S3 object cannot be loaded or parsed after retries
        """

        @s3_retry
        def _get_object_with_retry():
            s3 = boto3.client("s3")
            return s3.get_object(Bucket=bucket, Key=key)

        try:
            response = _get_object_with_retry()
            data = json.loads(response["Body"].read().decode("utf-8"))
            return cls._from_json(data)
        except Exception as e:
            logger.error(f"Failed to load ticker cache from s3://{bucket}/{key}: {e}")
            raise ValueError(f"Failed to load ticker cache: {e}") from e

    @classmethod
    def load_from_file(cls, path: str) -> "TickerCache":
        """Load cache from local file (for testing).

        Args:
            path: Path to JSON file

        Returns:
            TickerCache instance
        """
        with open(path) as f:
            data = json.load(f)
        return cls._from_json(data)

    @classmethod
    def _from_json(cls, data: dict) -> "TickerCache":
        """Parse JSON data into TickerCache."""
        symbols = {}
        for symbol, info in data.get("symbols", {}).items():
            delisted_at = None
            if info.get("delisted_at"):
                delisted_at = datetime.fromisoformat(info["delisted_at"])

            symbols[symbol] = TickerInfo(
                symbol=symbol,
                name=info.get("name", ""),
                exchange=info.get("exchange", "NYSE"),
                sector=info.get("sector"),
                industry=info.get("industry"),
                is_active=info.get("is_active", True),
                delisted_at=delisted_at,
                successor_symbol=info.get("successor_symbol"),
                delisting_reason=info.get("delisting_reason"),
            )

        # Calculate statistics
        exchanges: dict[str, int] = {}
        total_active = 0
        total_delisted = 0

        for ticker in symbols.values():
            if ticker.is_active:
                total_active += 1
                exchanges[ticker.exchange] = exchanges.get(ticker.exchange, 0) + 1
            else:
                total_delisted += 1

        return cls(
            version=data.get("version", datetime.now(UTC).strftime("%Y-%m-%d")),
            updated_at=(
                datetime.fromisoformat(data["updated_at"])
                if data.get("updated_at")
                else datetime.now(UTC)
            ),
            symbols=symbols,
            total_active=total_active,
            total_delisted=total_delisted,
            exchanges=exchanges,
        )

    def search(self, query: str, limit: int = 10) -> list[TickerInfo]:
        """Search by symbol prefix or company name.

        Args:
            query: Search query (case-insensitive)
            limit: Maximum results to return

        Returns:
            List of matching TickerInfo objects
        """
        query_upper = query.upper()
        query_lower = query.lower()
        results = []

        # First pass: exact symbol match
        if query_upper in self.symbols:
            ticker = self.symbols[query_upper]
            if ticker.is_active:
                results.append(ticker)

        # Second pass: symbol prefix match
        for symbol, ticker in self.symbols.items():
            if ticker.is_active and symbol.startswith(query_upper):
                if ticker not in results:
                    results.append(ticker)
                    if len(results) >= limit:
                        return results

        # Third pass: company name contains
        for ticker in self.symbols.values():
            if ticker.is_active and query_lower in ticker.name.lower():
                if ticker not in results:
                    results.append(ticker)
                    if len(results) >= limit:
                        return results

        return results[:limit]

    def validate(
        self, symbol: str
    ) -> tuple[Literal["valid", "delisted", "invalid"], TickerInfo | None]:
        """Validate a ticker symbol.

        Args:
            symbol: Stock symbol to validate

        Returns:
            Tuple of (status, ticker_info):
            - ("valid", TickerInfo) - Symbol exists and is active
            - ("delisted", TickerInfo) - Symbol was delisted (has successor info)
            - ("invalid", None) - Symbol not found
        """
        symbol_upper = symbol.upper()

        if symbol_upper not in self.symbols:
            return ("invalid", None)

        ticker = self.symbols[symbol_upper]

        if ticker.is_active:
            return ("valid", ticker)
        else:
            return ("delisted", ticker)

    def get_by_exchange(
        self, exchange: Literal["NYSE", "NASDAQ", "AMEX"], limit: int = 100
    ) -> list[TickerInfo]:
        """Get tickers by exchange.

        Args:
            exchange: Exchange to filter by
            limit: Maximum results

        Returns:
            List of TickerInfo for that exchange
        """
        results = []
        for ticker in self.symbols.values():
            if ticker.is_active and ticker.exchange == exchange:
                results.append(ticker)
                if len(results) >= limit:
                    break
        return results


# =============================================================================
# Feature 1224: TTL + ETag cache replacing @lru_cache
# =============================================================================
# Cache entry: (loaded_at, TickerCache, etag, effective_ttl)
_ticker_cache_entry: tuple[float, TickerCache, str, float] | None = None
_ticker_cache_lock = threading.Lock()
_ticker_stats = CacheStats(name="ticker")


def get_ticker_cache(
    bucket: str, key: str = "ticker-cache/us-symbols.json"
) -> TickerCache:
    """Get the global ticker cache instance with TTL-based refresh.

    Feature 1224: Replaced @lru_cache with TTL + S3 ETag conditional refresh.
    On TTL expiry, checks S3 ETag via head_object(). If unchanged, resets
    timer without re-downloading. If changed, downloads new list and validates
    it is non-empty before replacing the cache.

    On S3 failure, serves the stale cached list (fail-open).

    Args:
        bucket: S3 bucket name
        key: S3 object key

    Returns:
        TickerCache instance
    """
    global _ticker_cache_entry

    with _ticker_cache_lock:
        now = time.time()

        # Check if cache exists and is within TTL
        if _ticker_cache_entry is not None:
            loaded_at, cache, etag, effective_ttl = _ticker_cache_entry
            if now - loaded_at < effective_ttl:
                _ticker_stats.record_hit()
                return cache

            # TTL expired — attempt refresh outside the lock
            _ticker_stats.record_miss()
        else:
            _ticker_stats.record_miss()
            etag = ""

    # Outside lock: attempt S3 refresh
    try:
        refreshed = _refresh_from_s3(bucket, key, etag)
        if refreshed is not None:
            new_cache, new_etag = refreshed
            with _ticker_cache_lock:
                _ticker_cache_entry = (
                    time.time(),
                    new_cache,
                    new_etag,
                    jittered_ttl(TICKER_CACHE_TTL),
                )
            return new_cache

        # ETag unchanged — reset timer, keep existing cache
        with _ticker_cache_lock:
            if _ticker_cache_entry is not None:
                _, cache, old_etag, _ = _ticker_cache_entry
                _ticker_cache_entry = (
                    time.time(),
                    cache,
                    old_etag,
                    jittered_ttl(TICKER_CACHE_TTL),
                )
                return cache

    except Exception as e:
        _ticker_stats.record_refresh_failure()
        logger.warning(
            "Ticker cache refresh failed, serving stale data",
            extra={"error": str(e)},
        )
        with _ticker_cache_lock:
            if _ticker_cache_entry is not None:
                return _ticker_cache_entry[1]

    # No cached data at all — must load fresh (cold start)
    cache = TickerCache.load_from_s3(bucket, key)
    s3_etag = _get_s3_etag(bucket, key)
    with _ticker_cache_lock:
        _ticker_cache_entry = (
            time.time(),
            cache,
            s3_etag,
            jittered_ttl(TICKER_CACHE_TTL),
        )
    logger.info(
        f"Loaded ticker cache: {cache.total_active} active symbols, "
        f"version {cache.version}"
    )
    return cache


def _refresh_from_s3(
    bucket: str, key: str, current_etag: str
) -> tuple[TickerCache, str] | None:
    """Check S3 for ticker list updates using ETag conditional logic.

    Returns:
        (new_cache, new_etag) if list changed, None if unchanged.
    """
    s3 = boto3.client("s3")

    # Check ETag first (cheap HEAD request)
    head = s3.head_object(Bucket=bucket, Key=key)
    new_etag = head.get("ETag", "")

    if new_etag == current_etag and current_etag:
        logger.debug("Ticker cache ETag unchanged, skipping download")
        return None

    # ETag changed — download new list
    logger.info(
        "Ticker cache ETag changed, downloading new list",
        extra={"old_etag": current_etag[:16], "new_etag": new_etag[:16]},
    )
    response = s3.get_object(Bucket=bucket, Key=key)
    data = json.loads(response["Body"].read().decode("utf-8"))

    new_cache = TickerCache._from_json(data)

    # Validate non-empty before accepting (FR-005)
    validate_non_empty(new_cache.symbols, "ticker")

    return new_cache, new_etag


def _get_s3_etag(bucket: str, key: str) -> str:
    """Get the ETag for an S3 object (for initial load)."""
    try:
        s3 = boto3.client("s3")
        head = s3.head_object(Bucket=bucket, Key=key)
        return head.get("ETag", "")
    except Exception:
        return ""


def clear_ticker_cache() -> None:
    """Clear the global ticker cache (for testing)."""
    global _ticker_cache_entry
    with _ticker_cache_lock:
        _ticker_cache_entry = None


def get_ticker_cache_stats() -> CacheStats:
    """Get ticker cache statistics for monitoring."""
    return _ticker_stats
