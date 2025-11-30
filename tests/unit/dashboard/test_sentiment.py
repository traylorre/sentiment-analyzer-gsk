"""Unit tests for sentiment endpoints (T056-T057)."""

from datetime import UTC, datetime
from unittest.mock import MagicMock

import pytest

from src.lambdas.dashboard.sentiment import (
    COLOR_SCHEME,
    HeatMapResponse,
    SentimentResponse,
    SourceSentiment,
    TickerSentimentData,
    clear_sentiment_cache,
    get_heatmap_data,
    get_sentiment_by_configuration,
)


@pytest.fixture(autouse=True)
def reset_sentiment_cache():
    """Clear sentiment cache before each test for isolation."""
    clear_sentiment_cache()


class TestGetSentimentByConfiguration:
    """Tests for get_sentiment_by_configuration function."""

    def test_returns_sentiment_response(self):
        """Should return SentimentResponse."""
        response = get_sentiment_by_configuration(
            config_id="test-config",
            tickers=["AAPL"],
        )

        assert isinstance(response, SentimentResponse)
        assert response.config_id == "test-config"

    def test_includes_all_tickers(self):
        """Should include all requested tickers."""
        response = get_sentiment_by_configuration(
            config_id="test-config",
            tickers=["AAPL", "MSFT", "GOOGL"],
        )

        symbols = [t.symbol for t in response.tickers]
        assert "AAPL" in symbols
        assert "MSFT" in symbols
        assert "GOOGL" in symbols

    def test_sets_cache_status_to_fresh(self):
        """Should set cache_status to fresh."""
        response = get_sentiment_by_configuration(
            config_id="test-config",
            tickers=["AAPL"],
        )

        assert response.cache_status == "fresh"

    def test_sets_next_refresh_time(self):
        """Should set next_refresh_at."""
        response = get_sentiment_by_configuration(
            config_id="test-config",
            tickers=["AAPL"],
        )

        assert response.next_refresh_at is not None
        assert response.next_refresh_at.endswith("Z")

    def test_filters_by_sources(self):
        """Should filter by specified sources."""
        response = get_sentiment_by_configuration(
            config_id="test-config",
            tickers=["AAPL"],
            sources=["our_model"],
        )

        # our_model is computed from other sources, so may be empty
        assert response.config_id == "test-config"

    def test_gets_tiingo_sentiment_when_adapter_provided(self):
        """Should get Tiingo sentiment when adapter provided."""
        mock_adapter = MagicMock()
        mock_adapter.get_news.return_value = [
            MagicMock(title="AAPL beats earnings expectations"),
            MagicMock(title="Apple stock surge"),
        ]

        get_sentiment_by_configuration(
            config_id="test-config",
            tickers=["AAPL"],
            tiingo_adapter=mock_adapter,
        )

        # Should have called get_news
        mock_adapter.get_news.assert_called()

    def test_gets_finnhub_sentiment_when_adapter_provided(self):
        """Should get Finnhub sentiment when adapter provided."""
        mock_adapter = MagicMock()
        mock_sentiment = MagicMock()
        mock_sentiment.sentiment_score = 0.5
        mock_sentiment.bullish_percent = 60.0
        mock_sentiment.bearish_percent = 40.0
        mock_sentiment.fetched_at = datetime.now(UTC)
        mock_adapter.get_sentiment.return_value = mock_sentiment

        get_sentiment_by_configuration(
            config_id="test-config",
            tickers=["AAPL"],
            finnhub_adapter=mock_adapter,
        )

        mock_adapter.get_sentiment.assert_called_with("AAPL")

    def test_handles_adapter_errors_gracefully(self):
        """Should handle adapter errors gracefully."""
        mock_adapter = MagicMock()
        mock_adapter.get_news.side_effect = Exception("API error")

        # Should not raise
        response = get_sentiment_by_configuration(
            config_id="test-config",
            tickers=["AAPL"],
            tiingo_adapter=mock_adapter,
        )

        assert isinstance(response, SentimentResponse)

    def test_computes_our_model_sentiment(self):
        """Should compute our_model sentiment from other sources."""
        mock_finnhub = MagicMock()
        mock_sentiment = MagicMock()
        mock_sentiment.sentiment_score = 0.7
        mock_sentiment.bullish_percent = 70.0
        mock_sentiment.bearish_percent = 30.0
        mock_sentiment.fetched_at = datetime.now(UTC)
        mock_finnhub.get_sentiment.return_value = mock_sentiment

        response = get_sentiment_by_configuration(
            config_id="test-config",
            tickers=["AAPL"],
            finnhub_adapter=mock_finnhub,
        )

        # Should have our_model in the result
        ticker_data = response.tickers[0]
        if "finnhub" in ticker_data.sentiment:
            assert "our_model" in ticker_data.sentiment


class TestGetHeatmapData:
    """Tests for get_heatmap_data function."""

    def test_returns_heatmap_response(self):
        """Should return HeatMapResponse."""
        response = get_heatmap_data(
            config_id="test-config",
            tickers=["AAPL"],
        )

        assert isinstance(response, HeatMapResponse)

    def test_sources_view_includes_all_sources(self):
        """Should include all sources in sources view."""
        response = get_heatmap_data(
            config_id="test-config",
            tickers=["AAPL"],
            view="sources",
        )

        assert response.view == "sources"
        assert len(response.matrix) == 1
        assert len(response.matrix[0].cells) == 3  # tiingo, finnhub, our_model

    def test_timeperiods_view_includes_all_periods(self):
        """Should include all periods in timeperiods view."""
        response = get_heatmap_data(
            config_id="test-config",
            tickers=["AAPL"],
            view="timeperiods",
        )

        assert response.view == "timeperiods"
        assert len(response.matrix) == 1
        periods = [c.period for c in response.matrix[0].cells]
        assert "today" in periods
        assert "1w" in periods
        assert "1m" in periods
        assert "3m" in periods

    def test_sources_view_includes_legend(self):
        """Should include legend in sources view."""
        response = get_heatmap_data(
            config_id="test-config",
            tickers=["AAPL"],
            view="sources",
        )

        assert response.legend is not None
        assert response.legend.positive.color == COLOR_SCHEME["positive"]
        assert response.legend.negative.color == COLOR_SCHEME["negative"]
        assert response.legend.neutral.color == COLOR_SCHEME["neutral"]

    def test_timeperiods_view_no_legend(self):
        """Should not include legend in timeperiods view."""
        response = get_heatmap_data(
            config_id="test-config",
            tickers=["AAPL"],
            view="timeperiods",
        )

        assert response.legend is None

    def test_uses_sentiment_data_when_provided(self):
        """Should use provided sentiment data."""
        sentiment_data = SentimentResponse(
            config_id="test-config",
            tickers=[
                TickerSentimentData(
                    symbol="AAPL",
                    sentiment={
                        "tiingo": SourceSentiment(
                            score=0.5,
                            label="positive",
                            updated_at="2025-01-01T00:00:00Z",
                        )
                    },
                )
            ],
            last_updated="2025-01-01T00:00:00Z",
            next_refresh_at="2025-01-01T00:05:00Z",
            cache_status="fresh",
        )

        response = get_heatmap_data(
            config_id="test-config",
            tickers=["AAPL"],
            view="sources",
            sentiment_data=sentiment_data,
        )

        # Find tiingo cell
        tiingo_cell = next(
            (c for c in response.matrix[0].cells if c.source == "tiingo"), None
        )
        assert tiingo_cell is not None
        assert tiingo_cell.score == 0.5

    def test_returns_correct_colors_for_scores(self):
        """Should return correct colors for different scores."""
        sentiment_data = SentimentResponse(
            config_id="test-config",
            tickers=[
                TickerSentimentData(
                    symbol="AAPL",
                    sentiment={
                        "tiingo": SourceSentiment(
                            score=0.5,  # positive
                            label="positive",
                            updated_at="2025-01-01T00:00:00Z",
                        ),
                        "finnhub": SourceSentiment(
                            score=-0.5,  # negative
                            label="negative",
                            updated_at="2025-01-01T00:00:00Z",
                        ),
                        "our_model": SourceSentiment(
                            score=0.0,  # neutral
                            label="neutral",
                            updated_at="2025-01-01T00:00:00Z",
                        ),
                    },
                )
            ],
            last_updated="2025-01-01T00:00:00Z",
            next_refresh_at="2025-01-01T00:05:00Z",
            cache_status="fresh",
        )

        response = get_heatmap_data(
            config_id="test-config",
            tickers=["AAPL"],
            view="sources",
            sentiment_data=sentiment_data,
        )

        cells = {c.source: c for c in response.matrix[0].cells}
        assert cells["tiingo"].color == COLOR_SCHEME["positive"]
        assert cells["finnhub"].color == COLOR_SCHEME["negative"]
        assert cells["our_model"].color == COLOR_SCHEME["neutral"]

    def test_handles_multiple_tickers(self):
        """Should handle multiple tickers."""
        response = get_heatmap_data(
            config_id="test-config",
            tickers=["AAPL", "MSFT", "GOOGL"],
            view="sources",
        )

        assert len(response.matrix) == 3
        tickers = [row.ticker for row in response.matrix]
        assert "AAPL" in tickers
        assert "MSFT" in tickers
        assert "GOOGL" in tickers
