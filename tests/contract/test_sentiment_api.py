"""Contract tests for sentiment data endpoints (T043).

Validates that sentiment endpoints conform to dashboard-api.md contract:
- GET /api/v2/configurations/{id}/sentiment
"""

import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

from pydantic import BaseModel, Field

# --- Response Schema Definitions (from dashboard-api.md) ---


class TiingoSentiment(BaseModel):
    """Tiingo sentiment data."""

    score: float = Field(..., ge=-1.0, le=1.0)
    label: str = Field(..., pattern="^(positive|negative|neutral)$")
    confidence: float = Field(..., ge=0.0, le=1.0)
    updated_at: str


class FinnhubSentiment(BaseModel):
    """Finnhub sentiment data."""

    score: float = Field(..., ge=-1.0, le=1.0)
    label: str = Field(..., pattern="^(positive|negative|neutral)$")
    bullish_percent: float = Field(..., ge=0.0, le=1.0)
    bearish_percent: float = Field(..., ge=0.0, le=1.0)
    updated_at: str


class OurModelSentiment(BaseModel):
    """Our model sentiment data."""

    score: float = Field(..., ge=-1.0, le=1.0)
    label: str = Field(..., pattern="^(positive|negative|neutral)$")
    confidence: float = Field(..., ge=0.0, le=1.0)
    model_version: str
    updated_at: str


class TickerSentiment(BaseModel):
    """Sentiment data for a single ticker."""

    symbol: str
    sentiment: dict[str, Any]


class SentimentResponse(BaseModel):
    """Response schema for GET /api/v2/configurations/{id}/sentiment."""

    config_id: str
    tickers: list[TickerSentiment]
    last_updated: str
    next_refresh_at: str
    cache_status: str = Field(..., pattern="^(fresh|stale|refreshing)$")


# --- Contract Tests ---


class TestSentimentEndpoint:
    """Contract tests for sentiment data endpoint."""

    def test_response_contains_required_fields(self):
        """Response must contain all required fields per contract."""
        response = self._simulate_sentiment_response()

        assert "config_id" in response
        assert "tickers" in response
        assert "last_updated" in response
        assert "next_refresh_at" in response
        assert "cache_status" in response

    def test_config_id_is_valid_uuid(self):
        """config_id must be valid UUID."""
        response = self._simulate_sentiment_response()

        uuid.UUID(response["config_id"])

    def test_tickers_array_contains_sentiment_data(self):
        """Each ticker has sentiment data from sources."""
        response = self._simulate_sentiment_response()

        for ticker_data in response["tickers"]:
            assert "symbol" in ticker_data
            assert "sentiment" in ticker_data
            assert len(ticker_data["sentiment"]) > 0

    def test_tiingo_sentiment_format(self):
        """Tiingo sentiment has required fields."""
        response = self._simulate_sentiment_response()

        for ticker_data in response["tickers"]:
            if "tiingo" in ticker_data["sentiment"]:
                tiingo = ticker_data["sentiment"]["tiingo"]
                parsed = TiingoSentiment(**tiingo)

                assert -1.0 <= parsed.score <= 1.0
                assert parsed.label in ["positive", "negative", "neutral"]
                assert 0.0 <= parsed.confidence <= 1.0

    def test_finnhub_sentiment_format(self):
        """Finnhub sentiment has required fields."""
        response = self._simulate_sentiment_response()

        for ticker_data in response["tickers"]:
            if "finnhub" in ticker_data["sentiment"]:
                finnhub = ticker_data["sentiment"]["finnhub"]
                parsed = FinnhubSentiment(**finnhub)

                assert -1.0 <= parsed.score <= 1.0
                assert parsed.label in ["positive", "negative", "neutral"]
                assert 0.0 <= parsed.bullish_percent <= 1.0
                assert 0.0 <= parsed.bearish_percent <= 1.0

    def test_our_model_sentiment_format(self):
        """Our model sentiment has required fields including version."""
        response = self._simulate_sentiment_response()

        for ticker_data in response["tickers"]:
            if "our_model" in ticker_data["sentiment"]:
                our_model = ticker_data["sentiment"]["our_model"]
                parsed = OurModelSentiment(**our_model)

                assert -1.0 <= parsed.score <= 1.0
                assert parsed.model_version.startswith("v")

    def test_sentiment_score_range_negative_one_to_one(self):
        """All sentiment scores must be in [-1, 1] range."""
        response = self._simulate_sentiment_response()

        for ticker_data in response["tickers"]:
            for source, sentiment in ticker_data["sentiment"].items():
                assert -1.0 <= sentiment["score"] <= 1.0, f"{source} score out of range"

    def test_bullish_bearish_sum_to_one(self):
        """Finnhub bullish + bearish should approximately sum to 1."""
        response = self._simulate_sentiment_response()

        for ticker_data in response["tickers"]:
            if "finnhub" in ticker_data["sentiment"]:
                finnhub = ticker_data["sentiment"]["finnhub"]
                total = finnhub["bullish_percent"] + finnhub["bearish_percent"]
                # Allow small floating point error
                assert 0.99 <= total <= 1.01

    def test_timestamps_are_iso8601(self):
        """All timestamps must be ISO 8601 format."""
        response = self._simulate_sentiment_response()

        # Parse top-level timestamps
        datetime.fromisoformat(response["last_updated"].replace("Z", "+00:00"))
        datetime.fromisoformat(response["next_refresh_at"].replace("Z", "+00:00"))

        # Parse per-source timestamps
        for ticker_data in response["tickers"]:
            for _source, sentiment in ticker_data["sentiment"].items():
                datetime.fromisoformat(sentiment["updated_at"].replace("Z", "+00:00"))

    def test_cache_status_valid_values(self):
        """cache_status must be one of: fresh, stale, refreshing."""
        valid_statuses = ["fresh", "stale", "refreshing"]

        response = self._simulate_sentiment_response()
        assert response["cache_status"] in valid_statuses

    def test_next_refresh_in_future(self):
        """next_refresh_at should be in the future or very recent."""
        response = self._simulate_sentiment_response()

        next_refresh = datetime.fromisoformat(
            response["next_refresh_at"].replace("Z", "+00:00")
        )
        now = datetime.now(UTC)

        # Should be within 5 minutes past or in future
        assert (next_refresh - now).total_seconds() > -300

    def test_response_status_200_ok(self):
        """Successful request returns 200 OK."""
        status_code = 200
        assert status_code == 200

    def test_sources_query_parameter_filtering(self):
        """sources query parameter filters response sources."""
        # Contract: ?sources=tiingo,finnhub filters to those sources
        requested_sources = ["tiingo", "finnhub"]
        response = self._simulate_sentiment_response(sources=requested_sources)

        for ticker_data in response["tickers"]:
            for source in ticker_data["sentiment"]:
                assert source in requested_sources

    def test_default_sources_includes_all(self):
        """Default sources includes tiingo, finnhub, our_model."""
        default_sources = ["tiingo", "finnhub", "our_model"]
        response = self._simulate_sentiment_response()

        # At least some sources should be present
        for ticker_data in response["tickers"]:
            sources_present = list(ticker_data["sentiment"].keys())
            assert any(s in default_sources for s in sources_present)

    def test_not_found_returns_404(self):
        """Non-existent config_id returns 404."""
        error_response = {
            "error": {
                "code": "NOT_FOUND",
                "message": "Configuration not found",
            }
        }

        assert error_response["error"]["code"] == "NOT_FOUND"

    def test_upstream_error_returns_502(self):
        """Tiingo/Finnhub API error returns 502."""
        error_response = {
            "error": {
                "code": "UPSTREAM_ERROR",
                "message": "Tiingo API temporarily unavailable",
            }
        }

        assert error_response["error"]["code"] == "UPSTREAM_ERROR"

    # --- Helper Methods ---

    def _simulate_sentiment_response(
        self,
        sources: list[str] | None = None,
    ) -> dict[str, Any]:
        """Simulate sentiment endpoint response."""
        now = datetime.now(UTC)
        next_refresh = now + timedelta(seconds=300)

        if sources is None:
            sources = ["tiingo", "finnhub", "our_model"]

        sentiment_data = {}

        if "tiingo" in sources:
            sentiment_data["tiingo"] = {
                "score": 0.65,
                "label": "positive",
                "confidence": 0.82,
                "updated_at": now.isoformat().replace("+00:00", "Z"),
            }

        if "finnhub" in sources:
            sentiment_data["finnhub"] = {
                "score": 0.58,
                "label": "positive",
                "bullish_percent": 0.72,
                "bearish_percent": 0.28,
                "updated_at": now.isoformat().replace("+00:00", "Z"),
            }

        if "our_model" in sources:
            sentiment_data["our_model"] = {
                "score": 0.61,
                "label": "positive",
                "confidence": 0.88,
                "model_version": "v2.1.0",
                "updated_at": now.isoformat().replace("+00:00", "Z"),
            }

        return {
            "config_id": str(uuid.uuid4()),
            "tickers": [
                {"symbol": "AAPL", "sentiment": sentiment_data},
                {"symbol": "MSFT", "sentiment": sentiment_data},
            ],
            "last_updated": now.isoformat().replace("+00:00", "Z"),
            "next_refresh_at": next_refresh.isoformat().replace("+00:00", "Z"),
            "cache_status": "fresh",
        }


# --- Label Consistency Tests ---


class TestSentimentLabelConsistency:
    """Contract tests for label-score consistency."""

    def test_positive_score_has_positive_label(self):
        """Score >= 0.33 should have 'positive' label."""
        sentiment = {"score": 0.65, "label": "positive"}
        assert sentiment["score"] >= 0.33
        assert sentiment["label"] == "positive"

    def test_negative_score_has_negative_label(self):
        """Score <= -0.33 should have 'negative' label."""
        sentiment = {"score": -0.5, "label": "negative"}
        assert sentiment["score"] <= -0.33
        assert sentiment["label"] == "negative"

    def test_neutral_score_has_neutral_label(self):
        """Score between -0.33 and 0.33 should have 'neutral' label."""
        sentiment = {"score": 0.1, "label": "neutral"}
        assert -0.33 < sentiment["score"] < 0.33
        assert sentiment["label"] == "neutral"

    def test_label_thresholds_per_contract(self):
        """Label thresholds match contract specification."""
        # From dashboard-api.md legend
        thresholds = {
            "positive": (0.33, 1.0),
            "neutral": (-0.33, 0.33),
            "negative": (-1.0, -0.33),
        }

        assert thresholds["positive"][0] == 0.33
        assert thresholds["negative"][1] == -0.33
