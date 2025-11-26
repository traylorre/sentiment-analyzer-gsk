"""Ticker validation and search endpoints for Feature 006.

Implements ticker management (T054-T055):
- GET /api/v2/tickers/validate - Validate ticker symbol
- GET /api/v2/tickers/search - Search/autocomplete tickers

For On-Call Engineers:
    Ticker validation uses S3-based ticker cache (~8K symbols).
    Cache is loaded at Lambda cold start for performance.

Security Notes:
    - Input is sanitized before search
    - Results limited to prevent data exfiltration
"""

import logging
from typing import Any

from pydantic import BaseModel, Field

from src.lambdas.shared.logging_utils import sanitize_for_log

logger = logging.getLogger(__name__)


# Response schemas


class TickerValidateResponse(BaseModel):
    """Response for GET /api/v2/tickers/validate."""

    symbol: str
    status: str = Field(..., pattern="^(valid|delisted|invalid)$")
    name: str | None = None
    exchange: str | None = None
    successor: str | None = None  # For delisted symbols
    message: str | None = None


class TickerSearchResult(BaseModel):
    """Single ticker in search results."""

    symbol: str
    name: str
    exchange: str


class TickerSearchResponse(BaseModel):
    """Response for GET /api/v2/tickers/search."""

    results: list[TickerSearchResult]


# Constants

MAX_SEARCH_RESULTS = 10


# Service functions


def validate_ticker(
    symbol: str,
    ticker_cache: Any | None = None,
) -> TickerValidateResponse:
    """Validate a ticker symbol.

    Args:
        symbol: Ticker symbol to validate
        ticker_cache: TickerCache instance for validation

    Returns:
        TickerValidateResponse with validation result
    """
    symbol = symbol.upper().strip()

    if not symbol:
        return TickerValidateResponse(
            symbol=symbol,
            status="invalid",
            message="Symbol is required",
        )

    # Basic format validation
    if len(symbol) > 5 or not symbol.isalpha():
        return TickerValidateResponse(
            symbol=symbol,
            status="invalid",
            message="Symbol not found",
        )

    if ticker_cache:
        result = ticker_cache.validate(symbol)

        if result["status"] == "valid":
            return TickerValidateResponse(
                symbol=symbol,
                status="valid",
                name=result.get("name"),
                exchange=result.get("exchange"),
            )
        elif result["status"] == "delisted":
            return TickerValidateResponse(
                symbol=symbol,
                status="delisted",
                successor=result.get("successor"),
                message=result.get("message"),
            )
        else:
            return TickerValidateResponse(
                symbol=symbol,
                status="invalid",
                message="Symbol not found",
            )

    # Without cache, accept common format (for testing)
    # In production, ticker_cache should always be provided
    if _is_common_ticker(symbol):
        return TickerValidateResponse(
            symbol=symbol,
            status="valid",
            name=f"{symbol} Inc",
            exchange="NASDAQ",
        )

    return TickerValidateResponse(
        symbol=symbol,
        status="invalid",
        message="Symbol not found",
    )


def search_tickers(
    query: str,
    limit: int = MAX_SEARCH_RESULTS,
    ticker_cache: Any | None = None,
) -> TickerSearchResponse:
    """Search for tickers by symbol or company name.

    Args:
        query: Search query
        limit: Maximum results to return
        ticker_cache: TickerCache instance for search

    Returns:
        TickerSearchResponse with matching tickers
    """
    query = query.strip()

    if len(query) < 1:
        return TickerSearchResponse(results=[])

    # Sanitize query
    query = sanitize_for_log(query)[:50]  # Limit length

    # Clamp limit
    limit = min(limit, MAX_SEARCH_RESULTS)

    if ticker_cache:
        results = ticker_cache.search(query, limit=limit)
        return TickerSearchResponse(
            results=[
                TickerSearchResult(
                    symbol=r["symbol"],
                    name=r["name"],
                    exchange=r["exchange"],
                )
                for r in results
            ]
        )

    # Without cache, return common tickers matching query (for testing)
    common_results = _search_common_tickers(query, limit)
    return TickerSearchResponse(results=common_results)


# Helper functions


def _is_common_ticker(symbol: str) -> bool:
    """Check if symbol is a common well-known ticker."""
    common_tickers = {
        "AAPL",
        "MSFT",
        "GOOGL",
        "AMZN",
        "META",
        "NVDA",
        "TSLA",
        "NFLX",
        "AMD",
        "INTC",
        "BA",
        "DIS",
        "KO",
        "PEP",
        "MCD",
        "JPM",
        "BAC",
        "WFC",
        "GS",
        "MS",
        "XOM",
        "CVX",
        "COP",
    }
    return symbol in common_tickers


def _search_common_tickers(query: str, limit: int) -> list[TickerSearchResult]:
    """Search common tickers (fallback when no cache)."""
    common_tickers = [
        ("AAPL", "Apple Inc", "NASDAQ"),
        ("AMZN", "Amazon.com Inc", "NASDAQ"),
        ("AMD", "Advanced Micro Devices", "NASDAQ"),
        ("BA", "Boeing Co", "NYSE"),
        ("BAC", "Bank of America Corp", "NYSE"),
        ("COP", "ConocoPhillips", "NYSE"),
        ("CVX", "Chevron Corp", "NYSE"),
        ("DIS", "Walt Disney Co", "NYSE"),
        ("GOOGL", "Alphabet Inc Class A", "NASDAQ"),
        ("GS", "Goldman Sachs Group", "NYSE"),
        ("INTC", "Intel Corp", "NASDAQ"),
        ("JPM", "JPMorgan Chase & Co", "NYSE"),
        ("KO", "Coca-Cola Co", "NYSE"),
        ("MCD", "McDonalds Corp", "NYSE"),
        ("META", "Meta Platforms Inc", "NASDAQ"),
        ("MS", "Morgan Stanley", "NYSE"),
        ("MSFT", "Microsoft Corp", "NASDAQ"),
        ("NFLX", "Netflix Inc", "NASDAQ"),
        ("NVDA", "NVIDIA Corp", "NASDAQ"),
        ("PEP", "PepsiCo Inc", "NASDAQ"),
        ("TSLA", "Tesla Inc", "NASDAQ"),
        ("WFC", "Wells Fargo & Co", "NYSE"),
        ("XOM", "Exxon Mobil Corp", "NYSE"),
    ]

    query_upper = query.upper()
    results = []

    for symbol, name, exchange in common_tickers:
        if query_upper in symbol or query.lower() in name.lower():
            results.append(
                TickerSearchResult(
                    symbol=symbol,
                    name=name,
                    exchange=exchange,
                )
            )
            if len(results) >= limit:
                break

    return results
