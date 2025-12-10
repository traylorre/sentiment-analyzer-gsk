"""Unit tests for market hours utilities (T025).

Tests market hours detection for ingestion scheduling.
"""

from datetime import datetime

from src.lambdas.shared.utils.market import (
    ET,
    MARKET_CLOSE,
    MARKET_OPEN,
    get_cache_expiration,
    is_market_open,
)


class TestIsMarketOpen:
    """Tests for is_market_open() function."""

    def test_returns_true_during_market_hours(self) -> None:
        """Should return True between 9:30 AM and 4:00 PM ET on weekdays."""
        # Wednesday at 10:30 AM ET
        market_time = datetime(2025, 12, 10, 10, 30, 0, tzinfo=ET)

        assert is_market_open(market_time) is True

    def test_returns_false_before_open(self) -> None:
        """Should return False before 9:30 AM ET."""
        # Wednesday at 9:00 AM ET (before open)
        before_open = datetime(2025, 12, 10, 9, 0, 0, tzinfo=ET)

        assert is_market_open(before_open) is False

    def test_returns_false_after_close(self) -> None:
        """Should return False at or after 4:00 PM ET."""
        # Wednesday at 4:00 PM ET (exactly at close)
        at_close = datetime(2025, 12, 10, 16, 0, 0, tzinfo=ET)

        assert is_market_open(at_close) is False

    def test_returns_true_at_open(self) -> None:
        """Should return True at exactly 9:30 AM ET."""
        # Wednesday at 9:30 AM ET (exactly at open)
        at_open = datetime(2025, 12, 10, 9, 30, 0, tzinfo=ET)

        assert is_market_open(at_open) is True

    def test_returns_true_just_before_close(self) -> None:
        """Should return True at 3:59 PM ET."""
        # Wednesday at 3:59 PM ET
        before_close = datetime(2025, 12, 10, 15, 59, 0, tzinfo=ET)

        assert is_market_open(before_close) is True

    def test_returns_false_on_saturday(self) -> None:
        """Should return False on Saturday."""
        # Saturday at 10:30 AM ET
        saturday = datetime(2025, 12, 13, 10, 30, 0, tzinfo=ET)

        assert is_market_open(saturday) is False

    def test_returns_false_on_sunday(self) -> None:
        """Should return False on Sunday."""
        # Sunday at 10:30 AM ET
        sunday = datetime(2025, 12, 14, 10, 30, 0, tzinfo=ET)

        assert is_market_open(sunday) is False

    def test_uses_current_time_when_none(self) -> None:
        """Should use current time when no argument provided."""
        # This test verifies the function doesn't crash with no argument
        result = is_market_open()
        assert isinstance(result, bool)

    def test_handles_naive_datetime(self) -> None:
        """Should handle naive datetime by assuming ET."""
        # Naive datetime that would be during market hours if interpreted as ET
        naive_market_time = datetime(2025, 12, 10, 10, 30, 0)

        # Should treat as ET and return True
        assert is_market_open(naive_market_time) is True

    def test_monday_market_hours(self) -> None:
        """Should return True during Monday market hours."""
        monday_mid = datetime(2025, 12, 8, 12, 0, 0, tzinfo=ET)

        assert is_market_open(monday_mid) is True

    def test_friday_market_hours(self) -> None:
        """Should return True during Friday market hours."""
        friday_mid = datetime(2025, 12, 12, 14, 0, 0, tzinfo=ET)

        assert is_market_open(friday_mid) is True


class TestGetCacheExpiration:
    """Tests for get_cache_expiration() function."""

    def test_during_market_hours_expires_at_close(self) -> None:
        """During market hours, cache should expire at market close."""
        # Wednesday at 10:30 AM ET
        market_time = datetime(2025, 12, 10, 10, 30, 0, tzinfo=ET)

        expiration = get_cache_expiration(market_time)

        assert expiration.hour == 16
        assert expiration.minute == 0
        assert expiration.day == 10

    def test_before_open_expires_at_open(self) -> None:
        """Before market open, cache should expire at open."""
        # Wednesday at 8:00 AM ET
        before_open = datetime(2025, 12, 10, 8, 0, 0, tzinfo=ET)

        expiration = get_cache_expiration(before_open)

        assert expiration.hour == 9
        assert expiration.minute == 30
        assert expiration.day == 10

    def test_after_close_expires_next_day_open(self) -> None:
        """After market close, cache should expire at next day's open."""
        # Wednesday at 5:00 PM ET
        after_close = datetime(2025, 12, 10, 17, 0, 0, tzinfo=ET)

        expiration = get_cache_expiration(after_close)

        assert expiration.hour == 9
        assert expiration.minute == 30
        assert expiration.day == 11  # Thursday

    def test_friday_after_close_expires_monday_open(self) -> None:
        """Friday after close should expire Monday at open."""
        # Friday at 5:00 PM ET
        friday_evening = datetime(2025, 12, 12, 17, 0, 0, tzinfo=ET)

        expiration = get_cache_expiration(friday_evening)

        assert expiration.hour == 9
        assert expiration.minute == 30
        assert expiration.day == 15  # Monday

    def test_saturday_expires_monday_open(self) -> None:
        """Saturday should expire Monday at open."""
        # Saturday at 10:00 AM ET
        saturday = datetime(2025, 12, 13, 10, 0, 0, tzinfo=ET)

        expiration = get_cache_expiration(saturday)

        assert expiration.hour == 9
        assert expiration.minute == 30
        assert expiration.day == 15  # Monday

    def test_sunday_expires_monday_open(self) -> None:
        """Sunday should expire Monday at open."""
        # Sunday at 2:00 PM ET
        sunday = datetime(2025, 12, 14, 14, 0, 0, tzinfo=ET)

        expiration = get_cache_expiration(sunday)

        assert expiration.hour == 9
        assert expiration.minute == 30
        assert expiration.day == 15  # Monday


class TestMarketConstants:
    """Tests for market constants."""

    def test_market_open_is_930am(self) -> None:
        """MARKET_OPEN should be 9:30 AM."""
        assert MARKET_OPEN.hour == 9
        assert MARKET_OPEN.minute == 30

    def test_market_close_is_4pm(self) -> None:
        """MARKET_CLOSE should be 4:00 PM."""
        assert MARKET_CLOSE.hour == 16
        assert MARKET_CLOSE.minute == 0

    def test_et_timezone_is_new_york(self) -> None:
        """ET should be America/New_York timezone."""
        assert str(ET) == "America/New_York"
