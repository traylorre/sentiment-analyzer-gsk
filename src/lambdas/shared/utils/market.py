"""Market hours utilities for cache expiration calculation."""

from datetime import datetime, time, timedelta
from zoneinfo import ZoneInfo

# NYSE trading hours in Eastern Time
ET = ZoneInfo("America/New_York")
MARKET_OPEN = time(9, 30)
MARKET_CLOSE = time(16, 0)


def get_cache_expiration(now: datetime | None = None) -> datetime:
    """Calculate when OHLC cache should expire (next market open or close).

    Cache strategy:
    - During market hours: Expire at market close (data may update)
    - After market close: Expire at next market open (data is final)
    - Weekends: Expire at Monday market open

    Args:
        now: Current datetime (defaults to now in ET). Used for testing.

    Returns:
        Datetime when cache should expire (in ET timezone).
    """
    if now is None:
        now = datetime.now(ET)
    elif now.tzinfo is None:
        # Make naive datetime timezone-aware
        now = now.replace(tzinfo=ET)

    current_time = now.time()
    weekday = now.weekday()  # Monday=0, Sunday=6

    # If it's a weekday before market close
    if weekday < 5 and current_time < MARKET_CLOSE:
        if current_time >= MARKET_OPEN:
            # During market hours - expire at close
            return now.replace(hour=16, minute=0, second=0, microsecond=0)
        else:
            # Before market open - expire at open
            return now.replace(hour=9, minute=30, second=0, microsecond=0)

    # After market close or weekend - expire at next market open
    next_open = now.replace(hour=9, minute=30, second=0, microsecond=0)

    if weekday == 4 and current_time >= MARKET_CLOSE:
        # Friday after close -> Monday
        next_open += timedelta(days=3)
    elif weekday == 5:
        # Saturday -> Monday
        next_open += timedelta(days=2)
    elif weekday == 6:
        # Sunday -> Monday
        next_open += timedelta(days=1)
    elif current_time >= MARKET_CLOSE:
        # Regular weekday after close -> next day
        next_open += timedelta(days=1)

    return next_open


def is_market_open(now: datetime | None = None) -> bool:
    """Check if the stock market is currently open.

    Args:
        now: Current datetime (defaults to now in ET).

    Returns:
        True if market is open, False otherwise.
    """
    if now is None:
        now = datetime.now(ET)
    elif now.tzinfo is None:
        now = now.replace(tzinfo=ET)

    current_time = now.time()
    weekday = now.weekday()

    # Market is closed on weekends
    if weekday >= 5:
        return False

    # Market is open during trading hours
    return MARKET_OPEN <= current_time < MARKET_CLOSE
