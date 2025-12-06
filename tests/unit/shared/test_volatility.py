"""Unit tests for ATR volatility calculator."""

from datetime import UTC, datetime, timedelta

import pytest

from src.lambdas.shared.adapters.base import OHLCCandle
from src.lambdas.shared.volatility import (
    ATRResult,
    calculate_atr,
    calculate_atr_result,
    calculate_true_range,
    classify_volatility,
)


def make_candle(
    high: float,
    low: float,
    close: float,
    open_: float = 0,
    days_ago: int = 0,
) -> OHLCCandle:
    """Helper to create test candles."""
    return OHLCCandle(
        date=datetime.now(UTC) - timedelta(days=days_ago),
        open=open_ or low,
        high=high,
        low=low,
        close=close,
        volume=1000000,
    )


class TestCalculateTrueRange:
    """Tests for calculate_true_range function."""

    def test_first_candle_no_previous(self):
        """Test TR for first candle (no previous close)."""
        tr = calculate_true_range(high=155.0, low=145.0, previous_close=None)
        assert tr == 10.0  # high - low

    def test_high_low_range_largest(self):
        """Test when high-low is largest range."""
        tr = calculate_true_range(high=155.0, low=145.0, previous_close=150.0)
        assert tr == 10.0  # high - low

    def test_gap_up_largest(self):
        """Test when gap up creates largest range."""
        # Previous close at 140, current high at 155
        tr = calculate_true_range(high=155.0, low=150.0, previous_close=140.0)
        assert tr == 15.0  # abs(155 - 140)

    def test_gap_down_largest(self):
        """Test when gap down creates largest range."""
        # Previous close at 160, current low at 145
        tr = calculate_true_range(high=150.0, low=145.0, previous_close=160.0)
        assert tr == 15.0  # abs(145 - 160)


class TestCalculateATR:
    """Tests for calculate_atr function."""

    def test_insufficient_candles(self):
        """Test ATR returns None with insufficient data."""
        candles = [make_candle(155, 145, 150) for _ in range(5)]
        result = calculate_atr(candles, period=14)
        assert result is None

    def test_basic_atr_calculation(self):
        """Test basic ATR calculation."""
        # Create 14 candles with consistent $10 range
        candles = []
        close = 100.0
        for i in range(14):
            candles.append(
                make_candle(
                    high=close + 5,
                    low=close - 5,
                    close=close,
                    days_ago=14 - i,
                )
            )

        result = calculate_atr(candles, period=14)
        assert result is not None
        assert result == pytest.approx(10.0, rel=0.01)  # $10 range

    def test_atr_with_gaps(self):
        """Test ATR with price gaps."""
        candles = []
        prices = [
            (100, 105, 95, 100),  # First candle
            (110, 115, 108, 112),  # Gap up
            (108, 113, 107, 110),  # Normal
            (105, 110, 104, 107),  # Gap down
        ]
        for i, (open_, high, low, close) in enumerate(prices):
            candles.append(
                make_candle(
                    high=high, low=low, close=close, open_=open_, days_ago=4 - i
                )
            )

        result = calculate_atr(candles, period=4)
        assert result is not None
        # TR values: 10 (first), 15 (gap up), 6 (normal), 6 (normal)
        # ATR = (10 + 15 + 6 + 6) / 4 = 9.25
        assert result == pytest.approx(9.25, rel=0.01)

    def test_atr_uses_last_n_periods(self):
        """Test ATR uses only last N periods."""
        # Create 20 candles, first 6 with $20 range, last 14 with $10 range
        candles = []
        close = 100.0

        # First 6 candles with $20 range
        for i in range(6):
            candles.append(
                make_candle(
                    high=close + 10,
                    low=close - 10,
                    close=close,
                    days_ago=20 - i,
                )
            )

        # Last 14 candles with $10 range
        for i in range(14):
            candles.append(
                make_candle(
                    high=close + 5,
                    low=close - 5,
                    close=close,
                    days_ago=14 - i,
                )
            )

        result = calculate_atr(candles, period=14)
        assert result is not None
        # Should be ~$10 (only last 14 used)
        assert result == pytest.approx(10.0, rel=0.01)


class TestCalculateATRResult:
    """Tests for calculate_atr_result function."""

    def test_insufficient_candles_returns_none(self):
        """Test returns None with insufficient candles."""
        candles = [make_candle(155, 145, 150) for _ in range(5)]
        result = calculate_atr_result("AAPL", candles, period=14)
        assert result is None

    def test_basic_atr_result(self):
        """Test basic ATR result calculation."""
        candles = []
        close = 150.0
        for i in range(14):
            candles.append(
                make_candle(
                    high=close + 3,  # $6 range = 4% ATR
                    low=close - 3,
                    close=close,
                    days_ago=14 - i,
                )
            )

        result = calculate_atr_result("AAPL", candles, period=14)

        assert result is not None
        assert isinstance(result, ATRResult)
        assert result.ticker == "AAPL"
        assert result.atr == pytest.approx(6.0, rel=0.01)
        assert result.atr_percent == pytest.approx(0.04, rel=0.01)  # 6/150
        assert result.period == 14
        assert result.candle_count == 14

    def test_high_volatility_classification(self):
        """Test high volatility classification."""
        candles = []
        close = 100.0
        for i in range(14):
            candles.append(
                make_candle(
                    high=close + 3,  # $6 range = 6% ATR (high)
                    low=close - 3,
                    close=close,
                    days_ago=14 - i,
                )
            )

        result = calculate_atr_result(
            "AAPL", candles, period=14, high_volatility_threshold=0.03
        )

        assert result is not None
        assert result.volatility_level == "high"

    def test_low_volatility_classification(self):
        """Test low volatility classification."""
        candles = []
        close = 100.0
        for i in range(14):
            candles.append(
                make_candle(
                    high=close + 0.4,  # $0.8 range = 0.8% ATR (low)
                    low=close - 0.4,
                    close=close,
                    days_ago=14 - i,
                )
            )

        result = calculate_atr_result(
            "AAPL", candles, period=14, low_volatility_threshold=0.01
        )

        assert result is not None
        assert result.volatility_level == "low"

    def test_medium_volatility_classification(self):
        """Test medium volatility classification."""
        candles = []
        close = 100.0
        for i in range(14):
            candles.append(
                make_candle(
                    high=close + 1,  # $2 range = 2% ATR (medium)
                    low=close - 1,
                    close=close,
                    days_ago=14 - i,
                )
            )

        result = calculate_atr_result(
            "AAPL",
            candles,
            period=14,
            high_volatility_threshold=0.03,
            low_volatility_threshold=0.01,
        )

        assert result is not None
        assert result.volatility_level == "medium"

    def test_trend_increasing(self):
        """Test increasing volatility trend detection."""
        candles = []
        close = 100.0

        # First 14 candles with $5 range
        for i in range(14):
            candles.append(
                make_candle(
                    high=close + 2.5,
                    low=close - 2.5,
                    close=close,
                    days_ago=28 - i,
                )
            )

        # Next 14 candles with $10 range (doubled)
        for i in range(14):
            candles.append(
                make_candle(
                    high=close + 5,
                    low=close - 5,
                    close=close,
                    days_ago=14 - i,
                )
            )

        result = calculate_atr_result("AAPL", candles, period=14)

        assert result is not None
        assert result.trend == "increasing"
        assert result.trend_arrow == "↑"

    def test_trend_decreasing(self):
        """Test decreasing volatility trend detection."""
        candles = []
        close = 100.0

        # First 14 candles with $10 range
        for i in range(14):
            candles.append(
                make_candle(
                    high=close + 5,
                    low=close - 5,
                    close=close,
                    days_ago=28 - i,
                )
            )

        # Next 14 candles with $5 range (halved)
        for i in range(14):
            candles.append(
                make_candle(
                    high=close + 2.5,
                    low=close - 2.5,
                    close=close,
                    days_ago=14 - i,
                )
            )

        result = calculate_atr_result("AAPL", candles, period=14)

        assert result is not None
        assert result.trend == "decreasing"
        assert result.trend_arrow == "↓"

    def test_trend_stable(self):
        """Test stable volatility trend detection."""
        candles = []
        close = 100.0

        # All 28 candles with same $5 range
        for i in range(28):
            candles.append(
                make_candle(
                    high=close + 2.5,
                    low=close - 2.5,
                    close=close,
                    days_ago=28 - i,
                )
            )

        result = calculate_atr_result("AAPL", candles, period=14)

        assert result is not None
        assert result.trend == "stable"
        assert result.trend_arrow == "→"

    def test_invalid_close_price(self):
        """Test handling of invalid closing price."""
        candles = []
        for i in range(14):
            candles.append(
                make_candle(
                    high=100,
                    low=90,
                    close=0,  # Invalid
                    days_ago=14 - i,
                )
            )

        result = calculate_atr_result("AAPL", candles, period=14)
        assert result is None


class TestClassifyVolatility:
    """Tests for classify_volatility function."""

    def test_high_volatility(self):
        """Test high volatility classification."""
        assert classify_volatility(0.05) == "high"
        assert classify_volatility(0.03) == "high"

    def test_low_volatility(self):
        """Test low volatility classification."""
        assert classify_volatility(0.005) == "low"
        assert classify_volatility(0.01) == "low"

    def test_medium_volatility(self):
        """Test medium volatility classification."""
        assert classify_volatility(0.02) == "medium"
        assert classify_volatility(0.015) == "medium"

    def test_custom_thresholds(self):
        """Test with custom thresholds."""
        # With custom thresholds, 2% is now high
        assert (
            classify_volatility(0.02, high_threshold=0.02, low_threshold=0.01) == "high"
        )
        # With custom thresholds, 0.5% is now low
        assert (
            classify_volatility(0.005, high_threshold=0.03, low_threshold=0.005)
            == "low"
        )


class TestATRResultDataclass:
    """Tests for ATRResult dataclass."""

    def test_atr_result_creation(self):
        """Test creating ATR result."""
        result = ATRResult(
            ticker="AAPL",
            atr=5.5,
            atr_percent=0.025,
            period=14,
            calculated_at=datetime.now(UTC),
            candle_count=30,
            trend="stable",
            trend_arrow="→",
            volatility_level="medium",
        )

        assert result.ticker == "AAPL"
        assert result.atr == 5.5
        assert result.atr_percent == 0.025
        assert result.period == 14
        assert result.candle_count == 30
        assert result.trend == "stable"
        assert result.trend_arrow == "→"
        assert result.volatility_level == "medium"
