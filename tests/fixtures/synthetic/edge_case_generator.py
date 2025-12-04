"""Edge case generator for boundary testing.

Generates specific edge case test data for boundary testing:
- Date boundaries: single day, adjacent days, far past, far future
- Ticker boundaries: 1 char, 5 chars, 6 chars, invalid chars
- Price boundaries: doji, penny stock, large cap, zero, negative
- Score boundaries: exactly -1, 0, 1, threshold boundaries (±0.33)
"""

from datetime import date, timedelta
from typing import Any


class EdgeCaseGenerator:
    """Generates edge case test data for boundary testing."""

    # Label thresholds (same as sentiment endpoint)
    POSITIVE_THRESHOLD = 0.33
    NEGATIVE_THRESHOLD = -0.33

    def __init__(self, base_date: date | None = None):
        """Initialize edge case generator.

        Args:
            base_date: Base date for date-related edge cases (defaults to today)
        """
        self.base_date = base_date or date.today()

    # =========================================================================
    # OHLC Price Edge Cases
    # =========================================================================

    def ohlc_doji(self, price: float = 100.0, volume: int = 1000000) -> dict[str, Any]:
        """Generate doji candle (O=H=L=C).

        A doji represents a trading day where price opened and closed
        at essentially the same level - indicates market indecision.

        Args:
            price: Price for all OHLC values
            volume: Trading volume

        Returns:
            Candle dict with O=H=L=C
        """
        return {
            "date": self.base_date.isoformat(),
            "open": price,
            "high": price,
            "low": price,
            "close": price,
            "volume": volume,
        }

    def ohlc_penny_stock(self, base_price: float = 0.0001) -> dict[str, Any]:
        """Generate penny stock candle with very low prices.

        Tests handling of sub-penny stocks (prices below $0.01).

        Args:
            base_price: Base price (default: $0.0001)

        Returns:
            Candle dict with penny stock prices
        """
        return {
            "date": self.base_date.isoformat(),
            "open": base_price,
            "high": base_price * 1.1,
            "low": base_price * 0.9,
            "close": base_price * 1.05,
            "volume": 100000000,  # Penny stocks often have high volume
        }

    def ohlc_large_cap(self, base_price: float = 600000.0) -> dict[str, Any]:
        """Generate large cap candle with very high prices.

        Tests handling of expensive stocks like BRK.A (~$600k/share).

        Args:
            base_price: Base price (default: $600,000)

        Returns:
            Candle dict with large cap prices
        """
        return {
            "date": self.base_date.isoformat(),
            "open": base_price,
            "high": base_price * 1.02,
            "low": base_price * 0.98,
            "close": base_price * 1.01,
            "volume": 1000,  # Large cap stocks often have lower volume
        }

    def ohlc_invalid_high_low(self) -> dict[str, Any]:
        """Generate candle where high < low (invalid).

        Returns:
            Invalid candle dict for testing validation
        """
        return {
            "date": self.base_date.isoformat(),
            "open": 100.0,
            "high": 95.0,  # Invalid: high < low
            "low": 105.0,
            "close": 98.0,
            "volume": 1000000,
        }

    def ohlc_close_outside_range(self) -> dict[str, Any]:
        """Generate candle where close is outside high-low range (invalid).

        Returns:
            Invalid candle dict for testing validation
        """
        return {
            "date": self.base_date.isoformat(),
            "open": 100.0,
            "high": 105.0,
            "low": 95.0,
            "close": 110.0,  # Invalid: close > high
            "volume": 1000000,
        }

    def ohlc_open_outside_range(self) -> dict[str, Any]:
        """Generate candle where open is outside high-low range (invalid).

        Returns:
            Invalid candle dict for testing validation
        """
        return {
            "date": self.base_date.isoformat(),
            "open": 90.0,  # Invalid: open < low
            "high": 105.0,
            "low": 95.0,
            "close": 100.0,
            "volume": 1000000,
        }

    def ohlc_zero_price(self) -> dict[str, Any]:
        """Generate candle with zero price (invalid).

        Returns:
            Invalid candle dict for testing validation
        """
        return {
            "date": self.base_date.isoformat(),
            "open": 0.0,
            "high": 0.0,
            "low": 0.0,
            "close": 0.0,
            "volume": 0,
        }

    def ohlc_negative_price(self) -> dict[str, Any]:
        """Generate candle with negative prices (invalid).

        Returns:
            Invalid candle dict for testing validation
        """
        return {
            "date": self.base_date.isoformat(),
            "open": -100.0,
            "high": -95.0,
            "low": -110.0,
            "close": -98.0,
            "volume": 1000000,
        }

    def ohlc_zero_volume(self) -> dict[str, Any]:
        """Generate candle with zero volume (valid - low liquidity).

        Returns:
            Valid candle dict with zero volume
        """
        return {
            "date": self.base_date.isoformat(),
            "open": 100.0,
            "high": 105.0,
            "low": 95.0,
            "close": 102.0,
            "volume": 0,
        }

    def ohlc_negative_volume(self) -> dict[str, Any]:
        """Generate candle with negative volume (invalid).

        Returns:
            Invalid candle dict for testing validation
        """
        return {
            "date": self.base_date.isoformat(),
            "open": 100.0,
            "high": 105.0,
            "low": 95.0,
            "close": 102.0,
            "volume": -1000000,
        }

    # =========================================================================
    # Sentiment Score Edge Cases
    # =========================================================================

    def sentiment_at_threshold(
        self, threshold: str, source: str = "aggregated"
    ) -> dict[str, Any]:
        """Generate sentiment point at exact threshold.

        Args:
            threshold: Which threshold ("positive", "negative", "zero")
            source: Sentiment source

        Returns:
            Sentiment point dict at exact threshold
        """
        scores = {
            "positive": self.POSITIVE_THRESHOLD,  # 0.33
            "negative": self.NEGATIVE_THRESHOLD,  # -0.33
            "zero": 0.0,
        }
        labels = {
            "positive": "positive",
            "negative": "negative",
            "zero": "neutral",
        }

        score = scores.get(threshold, 0.0)
        label = labels.get(threshold, "neutral")

        return {
            "date": self.base_date.isoformat(),
            "score": score,
            "source": source,
            "confidence": 0.95,
            "label": label,
        }

    def sentiment_near_threshold(
        self, threshold: str, delta: float = 0.001, source: str = "aggregated"
    ) -> dict[str, Any]:
        """Generate sentiment point just below/above threshold.

        Args:
            threshold: Which threshold ("positive_below", "positive_above",
                       "negative_below", "negative_above")
            delta: Distance from threshold
            source: Sentiment source

        Returns:
            Sentiment point dict near threshold
        """
        score_map = {
            "positive_below": self.POSITIVE_THRESHOLD - delta,  # 0.329 -> neutral
            "positive_above": self.POSITIVE_THRESHOLD + delta,  # 0.331 -> positive
            "negative_above": self.NEGATIVE_THRESHOLD + delta,  # -0.329 -> neutral
            "negative_below": self.NEGATIVE_THRESHOLD - delta,  # -0.331 -> negative
        }
        label_map = {
            "positive_below": "neutral",
            "positive_above": "positive",
            "negative_above": "neutral",
            "negative_below": "negative",
        }

        score = score_map.get(threshold, 0.0)
        label = label_map.get(threshold, "neutral")

        return {
            "date": self.base_date.isoformat(),
            "score": round(score, 6),
            "source": source,
            "confidence": 0.95,
            "label": label,
        }

    def sentiment_extreme(
        self, extreme: str, source: str = "aggregated"
    ) -> dict[str, Any]:
        """Generate sentiment at extreme values (-1 or +1).

        Args:
            extreme: Which extreme ("max" for +1.0, "min" for -1.0)
            source: Sentiment source

        Returns:
            Sentiment point dict at extreme
        """
        score = 1.0 if extreme == "max" else -1.0
        label = "positive" if extreme == "max" else "negative"

        return {
            "date": self.base_date.isoformat(),
            "score": score,
            "source": source,
            "confidence": 1.0,
            "label": label,
        }

    def sentiment_out_of_bounds(
        self, direction: str, source: str = "aggregated"
    ) -> dict[str, Any]:
        """Generate sentiment outside valid bounds (invalid).

        Args:
            direction: "above" for > 1.0, "below" for < -1.0
            source: Sentiment source

        Returns:
            Invalid sentiment point dict for testing validation
        """
        score = 1.5 if direction == "above" else -1.5

        return {
            "date": self.base_date.isoformat(),
            "score": score,
            "source": source,
            "confidence": 0.95,
            "label": "positive" if score > 0 else "negative",
        }

    def confidence_boundary(
        self, boundary: str, source: str = "aggregated"
    ) -> dict[str, Any]:
        """Generate sentiment with confidence at boundary values.

        Args:
            boundary: "min" for 0.0, "max" for 1.0, "below" for -0.1, "above" for 1.1
            source: Sentiment source

        Returns:
            Sentiment point dict with boundary confidence
        """
        confidence_map = {
            "min": 0.0,
            "max": 1.0,
            "below": -0.1,  # Invalid
            "above": 1.1,  # Invalid
        }

        confidence = confidence_map.get(boundary, 0.5)

        return {
            "date": self.base_date.isoformat(),
            "score": 0.5,
            "source": source,
            "confidence": confidence,
            "label": "positive",
        }

    # =========================================================================
    # Date Edge Cases
    # =========================================================================

    def date_single_day(self) -> tuple[date, date]:
        """Generate single day range (start == end).

        Returns:
            Tuple of (start_date, end_date) where both are the same
        """
        return (self.base_date, self.base_date)

    def date_adjacent_days(self) -> tuple[date, date]:
        """Generate adjacent days range (end = start + 1).

        Returns:
            Tuple of (start_date, end_date) for adjacent days
        """
        return (self.base_date - timedelta(days=1), self.base_date)

    def date_inverted(self) -> tuple[date, date]:
        """Generate inverted date range (start > end - invalid).

        Returns:
            Tuple of (start_date, end_date) where start > end
        """
        return (self.base_date, self.base_date - timedelta(days=7))

    def date_far_past(self, years_back: int = 50) -> tuple[date, date]:
        """Generate date range far in the past.

        Args:
            years_back: How many years back to go

        Returns:
            Tuple of (start_date, end_date) in far past
        """
        far_past = self.base_date - timedelta(days=years_back * 365)
        return (far_past, far_past + timedelta(days=30))

    def date_future(self, days_ahead: int = 30) -> tuple[date, date]:
        """Generate date range in the future (invalid for historical data).

        Args:
            days_ahead: How many days in the future

        Returns:
            Tuple of (start_date, end_date) in future
        """
        future_start = self.base_date + timedelta(days=days_ahead)
        return (future_start, future_start + timedelta(days=7))

    # =========================================================================
    # Ticker Edge Cases
    # =========================================================================

    def ticker_valid_1_char(self) -> str:
        """Generate valid 1-character ticker (minimum length)."""
        return "A"

    def ticker_valid_5_chars(self) -> str:
        """Generate valid 5-character ticker (maximum length)."""
        return "GOOGL"

    def ticker_invalid_6_chars(self) -> str:
        """Generate invalid 6-character ticker (too long)."""
        return "GOOGLE"

    def ticker_invalid_empty(self) -> str:
        """Generate empty ticker (invalid)."""
        return ""

    def ticker_invalid_with_digits(self) -> str:
        """Generate ticker with digits (invalid)."""
        return "ABC123"

    def ticker_invalid_with_symbols(self, symbol: str = "-") -> str:
        """Generate ticker with symbol (invalid).

        Args:
            symbol: Symbol to include (-, ., _, etc.)

        Returns:
            Invalid ticker with symbol
        """
        return f"AB{symbol}C"

    def ticker_with_whitespace(self) -> str:
        """Generate ticker with surrounding whitespace (should be trimmed)."""
        return "  AAPL  "

    def ticker_mixed_case(self) -> str:
        """Generate ticker with mixed case (should be normalized to uppercase)."""
        return "AaPl"

    def ticker_unicode(self) -> str:
        """Generate ticker with unicode characters (invalid)."""
        return "AA\u03a9L"  # Greek letter Omega

    def ticker_unknown(self) -> str:
        """Generate ticker that doesn't exist (for 404 testing)."""
        return "ZZZZZ"
