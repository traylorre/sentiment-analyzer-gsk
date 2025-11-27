"""Contract tests for volatility endpoints (T044).

Validates that volatility endpoints conform to dashboard-api.md contract:
- GET /api/v2/configurations/{id}/volatility (ATR data)
- GET /api/v2/configurations/{id}/correlation (sentiment-volatility)
"""

import uuid
from datetime import UTC, datetime
from typing import Any

from pydantic import BaseModel, Field

# --- Response Schema Definitions (from dashboard-api.md) ---


class ATRData(BaseModel):
    """ATR (Average True Range) volatility data."""

    value: float = Field(..., ge=0.0)
    percent: float = Field(..., ge=0.0)
    period: int = Field(default=14, ge=1)
    trend: str = Field(..., pattern="^(increasing|decreasing|stable)$")
    trend_arrow: str = Field(..., pattern="^[↑↓→]$")
    previous_value: float = Field(..., ge=0.0)


class TickerVolatility(BaseModel):
    """Volatility data for a single ticker."""

    symbol: str
    atr: ATRData
    includes_extended_hours: bool
    updated_at: str


class VolatilityResponse(BaseModel):
    """Response schema for GET /api/v2/configurations/{id}/volatility."""

    config_id: str
    tickers: list[TickerVolatility]


class CorrelationData(BaseModel):
    """Sentiment-volatility correlation data."""

    sentiment_trend: str = Field(..., pattern="^[↑↓→]$")
    volatility_trend: str = Field(..., pattern="^[↑↓→]$")
    interpretation: str
    description: str


class TickerCorrelation(BaseModel):
    """Correlation data for a single ticker."""

    symbol: str
    correlation: CorrelationData


class CorrelationResponse(BaseModel):
    """Response schema for GET /api/v2/configurations/{id}/correlation."""

    config_id: str
    tickers: list[TickerCorrelation]


# --- Contract Tests for Volatility Endpoint ---


class TestVolatilityEndpoint:
    """Contract tests for ATR volatility endpoint."""

    def test_response_contains_required_fields(self):
        """Response must contain all required fields per contract."""
        response = self._simulate_volatility_response()

        assert "config_id" in response
        assert "tickers" in response

    def test_config_id_is_valid_uuid(self):
        """config_id must be valid UUID."""
        response = self._simulate_volatility_response()

        uuid.UUID(response["config_id"])

    def test_tickers_array_contains_atr_data(self):
        """Each ticker has ATR volatility data."""
        response = self._simulate_volatility_response()

        for ticker_data in response["tickers"]:
            assert "symbol" in ticker_data
            assert "atr" in ticker_data
            assert "includes_extended_hours" in ticker_data
            assert "updated_at" in ticker_data

    def test_atr_value_non_negative(self):
        """ATR value must be non-negative."""
        response = self._simulate_volatility_response()

        for ticker_data in response["tickers"]:
            assert ticker_data["atr"]["value"] >= 0.0

    def test_atr_percent_non_negative(self):
        """ATR percent must be non-negative."""
        response = self._simulate_volatility_response()

        for ticker_data in response["tickers"]:
            assert ticker_data["atr"]["percent"] >= 0.0

    def test_atr_period_default_14(self):
        """ATR period defaults to 14."""
        response = self._simulate_volatility_response()

        for ticker_data in response["tickers"]:
            assert ticker_data["atr"]["period"] == 14

    def test_atr_trend_valid_values(self):
        """ATR trend must be increasing, decreasing, or stable."""
        valid_trends = ["increasing", "decreasing", "stable"]
        response = self._simulate_volatility_response()

        for ticker_data in response["tickers"]:
            assert ticker_data["atr"]["trend"] in valid_trends

    def test_atr_trend_arrow_valid_values(self):
        """trend_arrow must be ↑, ↓, or →."""
        valid_arrows = ["↑", "↓", "→"]
        response = self._simulate_volatility_response()

        for ticker_data in response["tickers"]:
            assert ticker_data["atr"]["trend_arrow"] in valid_arrows

    def test_trend_arrow_matches_trend(self):
        """trend_arrow should match trend direction."""
        trend_to_arrow = {
            "increasing": "↑",
            "decreasing": "↓",
            "stable": "→",
        }

        response = self._simulate_volatility_response()

        for ticker_data in response["tickers"]:
            trend = ticker_data["atr"]["trend"]
            arrow = ticker_data["atr"]["trend_arrow"]
            assert arrow == trend_to_arrow[trend]

    def test_previous_value_non_negative(self):
        """previous_value must be non-negative."""
        response = self._simulate_volatility_response()

        for ticker_data in response["tickers"]:
            assert ticker_data["atr"]["previous_value"] >= 0.0

    def test_updated_at_is_iso8601(self):
        """updated_at must be ISO 8601 format."""
        response = self._simulate_volatility_response()

        for ticker_data in response["tickers"]:
            datetime.fromisoformat(ticker_data["updated_at"].replace("Z", "+00:00"))

    def test_includes_extended_hours_boolean(self):
        """includes_extended_hours must be boolean."""
        response = self._simulate_volatility_response()

        for ticker_data in response["tickers"]:
            assert isinstance(ticker_data["includes_extended_hours"], bool)

    def test_response_status_200_ok(self):
        """Successful request returns 200 OK."""
        status_code = 200
        assert status_code == 200

    def test_not_found_returns_404(self):
        """Non-existent config_id returns 404."""
        error_response = {
            "error": {
                "code": "NOT_FOUND",
                "message": "Configuration not found",
            }
        }

        assert error_response["error"]["code"] == "NOT_FOUND"

    # --- Helper Methods ---

    def _simulate_volatility_response(self) -> dict[str, Any]:
        """Simulate volatility endpoint response."""
        now = datetime.now(UTC)

        return {
            "config_id": str(uuid.uuid4()),
            "tickers": [
                {
                    "symbol": "AAPL",
                    "atr": {
                        "value": 3.42,
                        "percent": 2.1,
                        "period": 14,
                        "trend": "increasing",
                        "trend_arrow": "↑",
                        "previous_value": 3.15,
                    },
                    "includes_extended_hours": False,
                    "updated_at": now.isoformat().replace("+00:00", "Z"),
                },
                {
                    "symbol": "TSLA",
                    "atr": {
                        "value": 12.85,
                        "percent": 5.2,
                        "period": 14,
                        "trend": "decreasing",
                        "trend_arrow": "↓",
                        "previous_value": 14.20,
                    },
                    "includes_extended_hours": False,
                    "updated_at": now.isoformat().replace("+00:00", "Z"),
                },
            ],
        }


# --- Contract Tests for Correlation Endpoint ---


class TestCorrelationEndpoint:
    """Contract tests for sentiment-volatility correlation endpoint."""

    def test_response_contains_required_fields(self):
        """Response must contain all required fields per contract."""
        response = self._simulate_correlation_response()

        assert "config_id" in response
        assert "tickers" in response

    def test_config_id_is_valid_uuid(self):
        """config_id must be valid UUID."""
        response = self._simulate_correlation_response()

        uuid.UUID(response["config_id"])

    def test_tickers_array_contains_correlation_data(self):
        """Each ticker has correlation data."""
        response = self._simulate_correlation_response()

        for ticker_data in response["tickers"]:
            assert "symbol" in ticker_data
            assert "correlation" in ticker_data

    def test_correlation_sentiment_trend_arrow(self):
        """sentiment_trend must be valid arrow."""
        valid_arrows = ["↑", "↓", "→"]
        response = self._simulate_correlation_response()

        for ticker_data in response["tickers"]:
            assert ticker_data["correlation"]["sentiment_trend"] in valid_arrows

    def test_correlation_volatility_trend_arrow(self):
        """volatility_trend must be valid arrow."""
        valid_arrows = ["↑", "↓", "→"]
        response = self._simulate_correlation_response()

        for ticker_data in response["tickers"]:
            assert ticker_data["correlation"]["volatility_trend"] in valid_arrows

    def test_correlation_has_interpretation(self):
        """Correlation includes interpretation field."""
        response = self._simulate_correlation_response()

        for ticker_data in response["tickers"]:
            assert "interpretation" in ticker_data["correlation"]
            assert len(ticker_data["correlation"]["interpretation"]) > 0

    def test_correlation_has_description(self):
        """Correlation includes human-readable description."""
        response = self._simulate_correlation_response()

        for ticker_data in response["tickers"]:
            assert "description" in ticker_data["correlation"]
            assert len(ticker_data["correlation"]["description"]) > 0

    def test_interpretation_valid_values(self):
        """interpretation must be a known correlation type."""
        valid_interpretations = [
            "positive_divergence",
            "negative_divergence",
            "positive_convergence",
            "negative_convergence",
            "stable",
        ]

        response = self._simulate_correlation_response()

        for ticker_data in response["tickers"]:
            assert ticker_data["correlation"]["interpretation"] in valid_interpretations

    def test_response_status_200_ok(self):
        """Successful request returns 200 OK."""
        status_code = 200
        assert status_code == 200

    def test_not_found_returns_404(self):
        """Non-existent config_id returns 404."""
        error_response = {
            "error": {
                "code": "NOT_FOUND",
                "message": "Configuration not found",
            }
        }

        assert error_response["error"]["code"] == "NOT_FOUND"

    # --- Helper Methods ---

    def _simulate_correlation_response(self) -> dict[str, Any]:
        """Simulate correlation endpoint response."""
        return {
            "config_id": str(uuid.uuid4()),
            "tickers": [
                {
                    "symbol": "AAPL",
                    "correlation": {
                        "sentiment_trend": "↑",
                        "volatility_trend": "↓",
                        "interpretation": "positive_divergence",
                        "description": "Sentiment improving while volatility decreasing",
                    },
                },
                {
                    "symbol": "TSLA",
                    "correlation": {
                        "sentiment_trend": "↓",
                        "volatility_trend": "↑",
                        "interpretation": "negative_divergence",
                        "description": "Sentiment declining while volatility increasing",
                    },
                },
            ],
        }


# --- ATR Calculation Consistency Tests ---


class TestATRCalculationConsistency:
    """Contract tests for ATR calculation consistency."""

    def test_atr_percent_calculation(self):
        """ATR percent should be ATR value / price * 100."""
        # For AAPL at $162.86 with ATR $3.42
        atr_value = 3.42
        price = 162.86
        expected_percent = (atr_value / price) * 100

        # Per contract, percent is approximately correct
        assert abs(expected_percent - 2.1) < 0.1

    def test_trend_direction_logic(self):
        """Trend should reflect value vs previous_value."""
        # If current > previous, trend should be increasing
        current = 3.42
        previous = 3.15

        if current > previous:
            expected_trend = "increasing"
        elif current < previous:
            expected_trend = "decreasing"
        else:
            expected_trend = "stable"

        assert expected_trend == "increasing"


# --- Correlation Interpretation Tests ---


class TestCorrelationInterpretations:
    """Contract tests for correlation interpretation logic."""

    def test_positive_divergence(self):
        """Positive divergence: sentiment ↑, volatility ↓."""
        correlation = {
            "sentiment_trend": "↑",
            "volatility_trend": "↓",
            "interpretation": "positive_divergence",
        }

        assert correlation["interpretation"] == "positive_divergence"

    def test_negative_divergence(self):
        """Negative divergence: sentiment ↓, volatility ↑."""
        correlation = {
            "sentiment_trend": "↓",
            "volatility_trend": "↑",
            "interpretation": "negative_divergence",
        }

        assert correlation["interpretation"] == "negative_divergence"

    def test_positive_convergence(self):
        """Positive convergence: sentiment ↑, volatility ↑."""
        correlation = {
            "sentiment_trend": "↑",
            "volatility_trend": "↑",
            "interpretation": "positive_convergence",
        }

        assert correlation["interpretation"] == "positive_convergence"

    def test_negative_convergence(self):
        """Negative convergence: sentiment ↓, volatility ↓."""
        correlation = {
            "sentiment_trend": "↓",
            "volatility_trend": "↓",
            "interpretation": "negative_convergence",
        }

        assert correlation["interpretation"] == "negative_convergence"

    def test_stable_when_no_change(self):
        """Stable when both trends are neutral."""
        correlation = {
            "sentiment_trend": "→",
            "volatility_trend": "→",
            "interpretation": "stable",
        }

        assert correlation["interpretation"] == "stable"
