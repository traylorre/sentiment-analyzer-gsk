"""Unit tests for volatility endpoints (T058-T059)."""

from datetime import UTC, datetime
from unittest.mock import MagicMock

from src.lambdas.dashboard.volatility import (
    CorrelationResponse,
    VolatilityResponse,
    get_correlation_data,
    get_volatility_by_configuration,
)
from src.lambdas.shared.adapters.base import OHLCCandle


class TestGetVolatilityByConfiguration:
    """Tests for get_volatility_by_configuration function."""

    def test_returns_volatility_response(self):
        """Should return VolatilityResponse."""
        response = get_volatility_by_configuration(
            config_id="test-config",
            tickers=["AAPL"],
        )

        assert isinstance(response, VolatilityResponse)
        assert response.config_id == "test-config"

    def test_includes_all_tickers(self):
        """Should include all requested tickers."""
        response = get_volatility_by_configuration(
            config_id="test-config",
            tickers=["AAPL", "MSFT"],
        )

        symbols = [t.symbol for t in response.tickers]
        assert "AAPL" in symbols
        assert "MSFT" in symbols

    def test_returns_placeholder_without_adapters(self):
        """Should return placeholder without adapters."""
        response = get_volatility_by_configuration(
            config_id="test-config",
            tickers=["AAPL"],
        )

        atr = response.tickers[0].atr
        assert atr.value == 0.0
        assert atr.trend == "stable"
        assert atr.trend_arrow == "→"

    def test_uses_tiingo_adapter_first(self):
        """Should try Tiingo adapter first."""
        mock_tiingo = MagicMock()
        mock_tiingo.get_ohlc.return_value = _create_ohlc_data(20)

        get_volatility_by_configuration(
            config_id="test-config",
            tickers=["AAPL"],
            tiingo_adapter=mock_tiingo,
        )

        mock_tiingo.get_ohlc.assert_called()

    def test_falls_back_to_finnhub(self):
        """Should fall back to Finnhub if Tiingo fails."""
        mock_tiingo = MagicMock()
        mock_tiingo.get_ohlc.side_effect = Exception("Tiingo error")

        mock_finnhub = MagicMock()
        mock_finnhub.get_ohlc.return_value = _create_ohlc_data(20)

        get_volatility_by_configuration(
            config_id="test-config",
            tickers=["AAPL"],
            tiingo_adapter=mock_tiingo,
            finnhub_adapter=mock_finnhub,
        )

        mock_finnhub.get_ohlc.assert_called()

    def test_calculates_atr_with_valid_data(self):
        """Should calculate ATR with valid OHLC data."""
        mock_adapter = MagicMock()
        mock_adapter.get_ohlc.return_value = _create_ohlc_data(20)

        response = get_volatility_by_configuration(
            config_id="test-config",
            tickers=["AAPL"],
            tiingo_adapter=mock_adapter,
        )

        atr = response.tickers[0].atr
        assert atr.value > 0.0
        assert atr.period == 14

    def test_includes_extended_hours_flag(self):
        """Should include extended hours flag."""
        response = get_volatility_by_configuration(
            config_id="test-config",
            tickers=["AAPL"],
            include_extended_hours=True,
        )

        assert response.tickers[0].includes_extended_hours is True

    def test_uses_custom_atr_period(self):
        """Should use custom ATR period."""
        mock_adapter = MagicMock()
        mock_adapter.get_ohlc.return_value = _create_ohlc_data(25)

        response = get_volatility_by_configuration(
            config_id="test-config",
            tickers=["AAPL"],
            atr_period=20,
            tiingo_adapter=mock_adapter,
        )

        atr = response.tickers[0].atr
        assert atr.period == 20

    def test_handles_insufficient_data(self):
        """Should handle insufficient data gracefully."""
        mock_adapter = MagicMock()
        mock_adapter.get_ohlc.return_value = _create_ohlc_data(5)  # Less than 14

        response = get_volatility_by_configuration(
            config_id="test-config",
            tickers=["AAPL"],
            tiingo_adapter=mock_adapter,
        )

        atr = response.tickers[0].atr
        assert atr.value == 0.0  # Placeholder

    def test_sets_updated_at_timestamp(self):
        """Should set updated_at timestamp."""
        response = get_volatility_by_configuration(
            config_id="test-config",
            tickers=["AAPL"],
        )

        assert response.tickers[0].updated_at.endswith("Z")


class TestGetCorrelationData:
    """Tests for get_correlation_data function."""

    def test_returns_correlation_response(self):
        """Should return CorrelationResponse."""
        response = get_correlation_data(
            config_id="test-config",
            tickers=["AAPL"],
        )

        assert isinstance(response, CorrelationResponse)
        assert response.config_id == "test-config"

    def test_includes_all_tickers(self):
        """Should include all requested tickers."""
        response = get_correlation_data(
            config_id="test-config",
            tickers=["AAPL", "MSFT"],
        )

        symbols = [t.symbol for t in response.tickers]
        assert "AAPL" in symbols
        assert "MSFT" in symbols

    def test_defaults_to_stable_trends(self):
        """Should default to stable trends."""
        response = get_correlation_data(
            config_id="test-config",
            tickers=["AAPL"],
        )

        correlation = response.tickers[0].correlation
        assert correlation.sentiment_trend == "→"
        assert correlation.volatility_trend == "→"
        assert correlation.interpretation == "stable"

    def test_positive_divergence_interpretation(self):
        """Should interpret positive divergence."""
        response = get_correlation_data(
            config_id="test-config",
            tickers=["AAPL"],
            sentiment_trends={"AAPL": "↑"},
            volatility_trends={"AAPL": "↓"},
        )

        correlation = response.tickers[0].correlation
        assert correlation.interpretation == "positive_divergence"
        assert "improving" in correlation.description.lower()

    def test_negative_divergence_interpretation(self):
        """Should interpret negative divergence."""
        response = get_correlation_data(
            config_id="test-config",
            tickers=["AAPL"],
            sentiment_trends={"AAPL": "↓"},
            volatility_trends={"AAPL": "↑"},
        )

        correlation = response.tickers[0].correlation
        assert correlation.interpretation == "negative_divergence"
        assert "declining" in correlation.description.lower()

    def test_positive_convergence_interpretation(self):
        """Should interpret positive convergence."""
        response = get_correlation_data(
            config_id="test-config",
            tickers=["AAPL"],
            sentiment_trends={"AAPL": "↑"},
            volatility_trends={"AAPL": "↑"},
        )

        correlation = response.tickers[0].correlation
        assert correlation.interpretation == "positive_convergence"

    def test_negative_convergence_interpretation(self):
        """Should interpret negative convergence."""
        response = get_correlation_data(
            config_id="test-config",
            tickers=["AAPL"],
            sentiment_trends={"AAPL": "↓"},
            volatility_trends={"AAPL": "↓"},
        )

        correlation = response.tickers[0].correlation
        assert correlation.interpretation == "negative_convergence"

    def test_preserves_trend_arrows(self):
        """Should preserve trend arrows in response."""
        response = get_correlation_data(
            config_id="test-config",
            tickers=["AAPL"],
            sentiment_trends={"AAPL": "↑"},
            volatility_trends={"AAPL": "↓"},
        )

        correlation = response.tickers[0].correlation
        assert correlation.sentiment_trend == "↑"
        assert correlation.volatility_trend == "↓"


# Helper functions


def _create_ohlc_data(days: int) -> list[OHLCCandle]:
    """Create mock OHLC data for testing."""
    candles = []
    base_price = 150.0

    for i in range(days):
        # Create realistic OHLC data with some variation
        open_price = base_price + (i * 0.5)
        high_price = open_price + 2.0
        low_price = open_price - 1.5
        close_price = open_price + 0.5

        candles.append(
            OHLCCandle(
                date=datetime.now(UTC),
                open=open_price,
                high=high_price,
                low=low_price,
                close=close_price,
                volume=1000000,
            )
        )

    return candles
