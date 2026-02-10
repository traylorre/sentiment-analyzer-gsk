"""Lazy-init singleton dependency getters (FR-013, R6).

Replaces FastAPI's Depends() injection with module-level singletons.
Each getter initializes its resource on first call and caches it for
the Lambda container lifetime. Thread-safe for SSE Lambda.

Usage:
    from src.lambdas.shared.dependencies import get_users_table

    # In handler (replaces Depends(get_users_table)):
    table = get_users_table()
"""

import logging
import os
import threading

logger = logging.getLogger(__name__)

# Thread lock for SSE Lambda concurrent initialization
_init_lock = threading.Lock()

# Singleton instances
_users_table = None
_tiingo_adapter = None
_finnhub_adapter = None
_ticker_cache = None


def get_users_table():
    """Get DynamoDB users table resource (lazy singleton).

    Returns:
        boto3 DynamoDB Table resource for USERS_TABLE.

    Raises:
        KeyError: If USERS_TABLE environment variable is not set.
    """
    global _users_table
    if _users_table is None:
        from src.lambdas.shared.dynamodb import get_table

        _users_table = get_table(os.environ["USERS_TABLE"])
    return _users_table


def get_tiingo_adapter():
    """Get TiingoAdapter with API credentials (lazy singleton).

    Fetches API key from Secrets Manager (TIINGO_SECRET_ARN) or
    environment variable (TIINGO_API_KEY) for local dev.

    Returns:
        TiingoAdapter instance.

    Raises:
        RuntimeError: If no API key is available from any source.
    """
    global _tiingo_adapter
    if _tiingo_adapter is None:
        from src.lambdas.shared.adapters.tiingo import TiingoAdapter
        from src.lambdas.shared.logging_utils import get_safe_error_info

        api_key = os.environ.get("TIINGO_API_KEY")
        if not api_key:
            secret_arn = os.environ.get("TIINGO_SECRET_ARN")
            if secret_arn:
                try:
                    from src.lambdas.shared.secrets import get_api_key

                    api_key = get_api_key(secret_arn)
                except Exception as e:
                    logger.warning(
                        "Failed to retrieve Tiingo API key from Secrets Manager",
                        extra=get_safe_error_info(e),
                    )
        if not api_key:
            logger.warning("Tiingo API key not configured, data source unavailable")
            raise RuntimeError("Tiingo data source unavailable")
        _tiingo_adapter = TiingoAdapter(api_key=api_key)
    return _tiingo_adapter


def get_finnhub_adapter():
    """Get FinnhubAdapter with API credentials (lazy singleton).

    Fetches API key from Secrets Manager (FINNHUB_SECRET_ARN) or
    environment variable (FINNHUB_API_KEY) for local dev.

    Returns:
        FinnhubAdapter instance.

    Raises:
        RuntimeError: If no API key is available from any source.
    """
    global _finnhub_adapter
    if _finnhub_adapter is None:
        from src.lambdas.shared.adapters.finnhub import FinnhubAdapter
        from src.lambdas.shared.logging_utils import get_safe_error_info

        api_key = os.environ.get("FINNHUB_API_KEY")
        if not api_key:
            secret_arn = os.environ.get("FINNHUB_SECRET_ARN")
            if secret_arn:
                try:
                    from src.lambdas.shared.secrets import get_api_key

                    api_key = get_api_key(secret_arn)
                except Exception as e:
                    logger.warning(
                        "Failed to retrieve Finnhub API key from Secrets Manager",
                        extra=get_safe_error_info(e),
                    )
        if not api_key:
            logger.warning("Finnhub API key not configured, data source unavailable")
            raise RuntimeError("Finnhub data source unavailable")
        _finnhub_adapter = FinnhubAdapter(api_key=api_key)
    return _finnhub_adapter


def get_ticker_cache_dependency():
    """Get ticker cache instance (lazy singleton, optional).

    Returns None if TICKER_CACHE_BUCKET is not configured, allowing
    graceful degradation where service functions fall back to external
    API validation.

    Returns:
        TickerCache instance or None if not configured.
    """
    global _ticker_cache
    bucket = os.environ.get("TICKER_CACHE_BUCKET", "")
    if not bucket:
        logger.debug("TICKER_CACHE_BUCKET not configured, ticker cache disabled")
        return None
    if _ticker_cache is None:
        from src.lambdas.shared.cache.ticker_cache import get_ticker_cache

        try:
            _ticker_cache = get_ticker_cache(bucket)
        except Exception as e:
            logger.warning(f"Failed to load ticker cache: {e}")
            return None
    return _ticker_cache


def get_no_cache_headers() -> dict[str, str]:
    """Get cache-busting headers for auth responses (Feature 1157).

    Returns a dict of headers that prevent browser and proxy caching
    of sensitive auth data. Applied to all auth endpoint responses.

    Returns:
        Dict with Cache-Control, Pragma, and Expires headers.
    """
    return {
        "Cache-Control": "no-store, no-cache, must-revalidate",
        "Pragma": "no-cache",
        "Expires": "0",
    }


def reset_singletons():
    """Reset all singleton instances (for testing only).

    Allows tests to reinitialize dependencies between test runs
    without reloading modules.
    """
    global _users_table, _tiingo_adapter, _finnhub_adapter, _ticker_cache
    with _init_lock:
        _users_table = None
        _tiingo_adapter = None
        _finnhub_adapter = None
        _ticker_cache = None
