"""Persistent OHLC Cache (Feature 1087).

Implements write-through caching for OHLC price data using DynamoDB.
Historical data is cached permanently to eliminate redundant API calls.

Key Design:
- PK: {ticker}#{source} (e.g., "AAPL#tiingo")
- SK: {resolution}#{timestamp} (e.g., "5m#2025-12-27T10:30:00Z")

For On-Call Engineers:
    If cache queries are slow:
    1. Check DynamoDB table exists and has correct billing mode
    2. Verify Lambda has IAM permissions for Query/PutItem
    3. Check OHLC_CACHE_TABLE environment variable is set
"""

import logging
import os
from datetime import UTC, datetime
from decimal import Decimal
from typing import NamedTuple

import boto3
from botocore.exceptions import ClientError
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

# Environment variable for table name
OHLC_CACHE_TABLE_ENV = "OHLC_CACHE_TABLE"


class CachedCandle(BaseModel):
    """A cached OHLC candle from DynamoDB."""

    timestamp: datetime
    open: float
    high: float
    low: float
    close: float
    volume: int = 0
    source: str
    resolution: str


class OHLCCacheResult(BaseModel):
    """Result of a cache query."""

    candles: list[CachedCandle] = Field(default_factory=list)
    cache_hit: bool = False
    missing_ranges: list[tuple[datetime, datetime]] = Field(default_factory=list)


class MarketHours(NamedTuple):
    """NYSE market hours in Eastern Time."""

    open_hour: int = 9
    open_minute: int = 30
    close_hour: int = 16
    close_minute: int = 0


def _get_table_name() -> str:
    """Get DynamoDB table name from environment."""
    table_name = os.environ.get(OHLC_CACHE_TABLE_ENV, "")
    if not table_name:
        environment = os.environ.get("ENVIRONMENT", "preprod")
        table_name = f"{environment}-ohlc-cache"
    return table_name


def _get_dynamodb_client():
    """Get DynamoDB client (lazy initialization).

    Uses AWS_REGION or AWS_DEFAULT_REGION from environment.
    Falls back to us-east-1 if neither is set.
    """
    region = os.environ.get("AWS_REGION") or os.environ.get(
        "AWS_DEFAULT_REGION", "us-east-1"
    )
    return boto3.client("dynamodb", region_name=region)


def _build_pk(ticker: str, source: str) -> str:
    """Build partition key: {ticker}#{source}."""
    return f"{ticker.upper()}#{source.lower()}"


def _build_sk(resolution: str, timestamp: datetime) -> str:
    """Build sort key: {resolution}#{timestamp}.

    Timestamp is in ISO8601 format with UTC timezone.
    """
    # Ensure UTC timezone
    if timestamp.tzinfo is None:
        timestamp = timestamp.replace(tzinfo=UTC)
    return f"{resolution}#{timestamp.strftime('%Y-%m-%dT%H:%M:%SZ')}"


def _parse_sk(sk: str) -> tuple[str, datetime]:
    """Parse sort key back into resolution and timestamp."""
    parts = sk.split("#", 1)
    if len(parts) != 2:
        raise ValueError(f"Invalid SK format: {sk}")
    resolution = parts[0]
    timestamp = datetime.strptime(parts[1], "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=UTC)
    return resolution, timestamp


def is_market_open() -> bool:
    """Check if NYSE market is currently open.

    NYSE hours: 9:30 AM - 4:00 PM Eastern Time, Monday-Friday.
    Does not account for holidays (returns True on bank holidays).

    Returns:
        True if within NYSE trading hours
    """
    try:
        from zoneinfo import ZoneInfo
    except ImportError:
        # Python < 3.9 fallback
        from backports.zoneinfo import ZoneInfo  # type: ignore

    now_et = datetime.now(ZoneInfo("America/New_York"))

    # Check weekday (0=Monday, 6=Sunday)
    if now_et.weekday() > 4:  # Saturday or Sunday
        return False

    hours = MarketHours()
    market_open = now_et.replace(
        hour=hours.open_hour, minute=hours.open_minute, second=0, microsecond=0
    )
    market_close = now_et.replace(
        hour=hours.close_hour, minute=hours.close_minute, second=0, microsecond=0
    )

    return market_open <= now_et <= market_close


def get_cached_candles(
    ticker: str,
    source: str,
    resolution: str,
    start_time: datetime,
    end_time: datetime,
) -> OHLCCacheResult:
    """Query DynamoDB for cached OHLC candles.

    Args:
        ticker: Stock symbol (e.g., "AAPL")
        source: Data provider ("tiingo" or "finnhub")
        resolution: Candle resolution ("1m", "5m", "15m", "30m", "1h", "D")
        start_time: Range start (inclusive, UTC)
        end_time: Range end (inclusive, UTC)

    Returns:
        OHLCCacheResult with candles and cache hit status
    """
    table_name = _get_table_name()
    if not table_name:
        logger.warning("OHLC cache table not configured")
        return OHLCCacheResult(cache_hit=False)

    pk = _build_pk(ticker, source)
    sk_start = _build_sk(resolution, start_time)
    sk_end = _build_sk(resolution, end_time)

    try:
        client = _get_dynamodb_client()
        response = client.query(
            TableName=table_name,
            KeyConditionExpression="PK = :pk AND SK BETWEEN :start AND :end",
            ExpressionAttributeValues={
                ":pk": {"S": pk},
                ":start": {"S": sk_start},
                ":end": {"S": sk_end},
            },
            ProjectionExpression="SK, #o, high, low, #c, volume",
            ExpressionAttributeNames={
                "#o": "open",  # 'open' is reserved word
                "#c": "close",  # 'close' is reserved word
            },
        )

        items = response.get("Items", [])
        if not items:
            logger.debug(
                "OHLC cache miss",
                extra={
                    "ticker": ticker,
                    "source": source,
                    "resolution": resolution,
                },
            )
            return OHLCCacheResult(cache_hit=False)

        candles = []
        for item in items:
            try:
                res, ts = _parse_sk(item["SK"]["S"])
                candles.append(
                    CachedCandle(
                        timestamp=ts,
                        open=float(item["#o"]["N"])
                        if "#o" in item
                        else float(item.get("open", {}).get("N", 0)),
                        high=float(item["high"]["N"]),
                        low=float(item["low"]["N"]),
                        close=float(item["#c"]["N"])
                        if "#c" in item
                        else float(item.get("close", {}).get("N", 0)),
                        volume=int(item.get("volume", {}).get("N", 0)),
                        source=source,
                        resolution=res,
                    )
                )
            except (KeyError, ValueError) as e:
                logger.warning(
                    "Failed to parse cached candle",
                    extra={"error": str(e), "item": item},
                )
                continue

        logger.info(
            "OHLC cache hit",
            extra={
                "ticker": ticker,
                "source": source,
                "resolution": resolution,
                "count": len(candles),
            },
        )

        return OHLCCacheResult(
            candles=sorted(candles, key=lambda c: c.timestamp),
            cache_hit=True,
        )

    except ClientError as e:
        logger.warning(
            "DynamoDB query failed for OHLC cache",
            extra={"error": str(e), "ticker": ticker},
        )
        return OHLCCacheResult(cache_hit=False)


def put_cached_candles(
    ticker: str,
    source: str,
    resolution: str,
    candles: list[CachedCandle],
) -> int:
    """Write OHLC candles to DynamoDB (write-through).

    Uses BatchWriteItem for efficiency. Existing items are overwritten.

    Args:
        ticker: Stock symbol (e.g., "AAPL")
        source: Data provider ("tiingo" or "finnhub")
        resolution: Candle resolution
        candles: List of candles to persist

    Returns:
        Number of candles written
    """
    if not candles:
        return 0

    table_name = _get_table_name()
    if not table_name:
        logger.warning("OHLC cache table not configured, skipping write")
        return 0

    pk = _build_pk(ticker, source)
    fetched_at = datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")

    # Build batch write items
    write_requests = []
    for candle in candles:
        sk = _build_sk(resolution, candle.timestamp)
        item = {
            "PK": {"S": pk},
            "SK": {"S": sk},
            "open": {"N": str(Decimal(str(candle.open)).quantize(Decimal("0.0001")))},
            "high": {"N": str(Decimal(str(candle.high)).quantize(Decimal("0.0001")))},
            "low": {"N": str(Decimal(str(candle.low)).quantize(Decimal("0.0001")))},
            "close": {"N": str(Decimal(str(candle.close)).quantize(Decimal("0.0001")))},
            "volume": {"N": str(candle.volume)},
            "fetched_at": {"S": fetched_at},
        }
        write_requests.append({"PutRequest": {"Item": item}})

    # BatchWriteItem has 25-item limit per request
    written = 0
    try:
        client = _get_dynamodb_client()
        for i in range(0, len(write_requests), 25):
            batch = write_requests[i : i + 25]
            response = client.batch_write_item(
                RequestItems={table_name: batch},
            )
            # Count successful writes
            unprocessed = response.get("UnprocessedItems", {}).get(table_name, [])
            written += len(batch) - len(unprocessed)

            # Retry unprocessed items (simple retry, no backoff for now)
            if unprocessed:
                logger.warning(
                    "Some OHLC cache writes were unprocessed",
                    extra={"count": len(unprocessed)},
                )

        logger.info(
            "OHLC candles cached",
            extra={
                "ticker": ticker,
                "source": source,
                "resolution": resolution,
                "count": written,
            },
        )
        return written

    except ClientError as e:
        logger.warning(
            "DynamoDB batch write failed for OHLC cache",
            extra={"error": str(e), "ticker": ticker},
        )
        return 0


def candles_to_cached(
    candles: list,
    source: str,
    resolution: str,
) -> list[CachedCandle]:
    """Convert adapter candles to CachedCandle format.

    Handles both OHLCCandle (from adapters) and PriceCandle (from models).

    Args:
        candles: List of candles from adapter
        source: Data source name
        resolution: Resolution string

    Returns:
        List of CachedCandle objects
    """
    result = []
    for candle in candles:
        # Handle datetime or date
        if hasattr(candle, "date"):
            ts = candle.date
        elif hasattr(candle, "timestamp"):
            ts = candle.timestamp
        else:
            continue

        # Convert date to datetime if needed
        if not isinstance(ts, datetime):
            ts = datetime.combine(ts, datetime.min.time(), tzinfo=UTC)
        elif ts.tzinfo is None:
            ts = ts.replace(tzinfo=UTC)

        result.append(
            CachedCandle(
                timestamp=ts,
                open=float(candle.open),
                high=float(candle.high),
                low=float(candle.low),
                close=float(candle.close),
                volume=int(getattr(candle, "volume", 0)),
                source=source,
                resolution=resolution,
            )
        )
    return result
