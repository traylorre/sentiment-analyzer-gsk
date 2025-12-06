"""Ticker cache for US stock symbol validation and autocomplete.

Loads ~8K US stock symbols from S3 at Lambda cold start.
Provides fast symbol validation and company name search.
"""

import json
import logging
from datetime import UTC, datetime
from functools import lru_cache
from typing import Literal

import boto3
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


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

        Args:
            bucket: S3 bucket name
            key: S3 object key (e.g., "ticker-cache/us-symbols.json")

        Returns:
            TickerCache instance

        Raises:
            ValueError: If S3 object cannot be loaded or parsed
        """
        try:
            s3 = boto3.client("s3")
            response = s3.get_object(Bucket=bucket, Key=key)
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


# Global cache instance (singleton)
_cache: TickerCache | None = None


@lru_cache(maxsize=1)
def get_ticker_cache(
    bucket: str, key: str = "ticker-cache/us-symbols.json"
) -> TickerCache:
    """Get the global ticker cache instance.

    Uses LRU cache to ensure only one load per Lambda instance.

    Args:
        bucket: S3 bucket name
        key: S3 object key

    Returns:
        TickerCache instance
    """
    global _cache
    if _cache is None:
        _cache = TickerCache.load_from_s3(bucket, key)
        logger.info(
            f"Loaded ticker cache: {_cache.total_active} active symbols, "
            f"version {_cache.version}"
        )
    return _cache


def clear_ticker_cache() -> None:
    """Clear the global ticker cache (for testing)."""
    global _cache
    _cache = None
    get_ticker_cache.cache_clear()
