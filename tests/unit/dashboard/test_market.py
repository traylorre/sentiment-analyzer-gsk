"""Unit tests for market endpoints (T060-T063)."""

from datetime import UTC, datetime, timedelta
from unittest.mock import MagicMock, patch

from src.lambdas.dashboard.market import (
    NYSE_TZ,
    MarketStatusResponse,
    PremarketResponse,
    RefreshStatusResponse,
    RefreshTriggerResponse,
    get_market_status,
    get_premarket_estimates,
    get_refresh_status,
    trigger_refresh,
)


class TestGetRefreshStatus:
    """Tests for get_refresh_status function."""

    def test_returns_refresh_status_response(self):
        """Should return RefreshStatusResponse."""
        response = get_refresh_status(config_id="test-config")

        assert isinstance(response, RefreshStatusResponse)

    def test_sets_refresh_interval(self):
        """Should set refresh interval."""
        response = get_refresh_status(config_id="test-config")

        assert response.refresh_interval_seconds == 300

    def test_calculates_countdown(self):
        """Should calculate countdown seconds."""
        last_refresh = datetime.now(UTC) - timedelta(seconds=100)

        response = get_refresh_status(
            config_id="test-config",
            last_refresh_time=last_refresh,
        )

        # Should be ~200 seconds remaining
        assert 190 <= response.countdown_seconds <= 210

    def test_countdown_never_negative(self):
        """Should not return negative countdown."""
        last_refresh = datetime.now(UTC) - timedelta(seconds=400)

        response = get_refresh_status(
            config_id="test-config",
            last_refresh_time=last_refresh,
        )

        assert response.countdown_seconds >= 0

    def test_sets_is_refreshing_false(self):
        """Should set is_refreshing to False."""
        response = get_refresh_status(config_id="test-config")

        assert response.is_refreshing is False


class TestTriggerRefresh:
    """Tests for trigger_refresh function."""

    def test_returns_refresh_trigger_response(self):
        """Should return RefreshTriggerResponse."""
        response = trigger_refresh(config_id="test-config")

        assert isinstance(response, RefreshTriggerResponse)

    def test_sets_status_to_queued(self):
        """Should set status to refresh_queued."""
        response = trigger_refresh(config_id="test-config")

        assert response.status == "refresh_queued"

    def test_sets_estimated_completion(self):
        """Should set estimated_completion."""
        response = trigger_refresh(config_id="test-config")

        assert response.estimated_completion.endswith("Z")


class TestGetMarketStatus:
    """Tests for get_market_status function."""

    def test_returns_market_status_response(self):
        """Should return MarketStatusResponse."""
        response = get_market_status()

        assert isinstance(response, MarketStatusResponse)

    def test_sets_exchange_to_nyse(self):
        """Should set exchange to NYSE."""
        response = get_market_status()

        assert response.exchange == "NYSE"

    def test_market_open_during_trading_hours(self):
        """Should return open during trading hours."""
        # Mock time to 10:00 AM ET on a weekday
        mock_time = datetime(2025, 3, 10, 10, 0, 0, tzinfo=NYSE_TZ)
        mock_utc = mock_time.astimezone(UTC)

        with patch("src.lambdas.dashboard.market.datetime") as mock_datetime:
            mock_datetime.now.return_value = mock_utc

            response = get_market_status()

            assert response.status == "open"

    def test_market_closed_before_open(self):
        """Should return closed before market open."""
        # Mock time to 8:00 AM ET on a weekday (before 9:30)
        mock_time = datetime(2025, 3, 10, 8, 0, 0, tzinfo=NYSE_TZ)
        mock_utc = mock_time.astimezone(UTC)

        with patch("src.lambdas.dashboard.market.datetime") as mock_datetime:
            mock_datetime.now.return_value = mock_utc

            response = get_market_status()

            assert response.status == "closed"
            assert response.reason == "premarket"

    def test_market_closed_after_hours(self):
        """Should return closed after market close."""
        # Mock time to 5:00 PM ET on a weekday
        mock_time = datetime(2025, 3, 10, 17, 0, 0, tzinfo=NYSE_TZ)
        mock_utc = mock_time.astimezone(UTC)

        with patch("src.lambdas.dashboard.market.datetime") as mock_datetime:
            mock_datetime.now.return_value = mock_utc

            response = get_market_status()

            assert response.status == "closed"
            assert response.reason == "after_hours"

    def test_market_closed_on_weekend(self):
        """Should return closed on weekend."""
        # Mock time to Saturday
        mock_time = datetime(2025, 3, 8, 12, 0, 0, tzinfo=NYSE_TZ)  # Saturday
        mock_utc = mock_time.astimezone(UTC)

        with patch("src.lambdas.dashboard.market.datetime") as mock_datetime:
            mock_datetime.now.return_value = mock_utc

            response = get_market_status()

            assert response.status == "closed"
            assert response.reason == "weekend"

    def test_market_closed_on_holiday(self):
        """Should return closed on holiday."""
        # Mock time to Christmas
        mock_time = datetime(2025, 12, 25, 12, 0, 0, tzinfo=NYSE_TZ)
        mock_utc = mock_time.astimezone(UTC)

        with patch("src.lambdas.dashboard.market.datetime") as mock_datetime:
            mock_datetime.now.return_value = mock_utc

            response = get_market_status()

            assert response.status == "closed"
            assert response.is_holiday is True
            assert response.holiday_name == "Christmas Day"

    def test_sets_next_open_when_closed(self):
        """Should set next_open when market is closed."""
        # Mock time to Saturday
        mock_time = datetime(2025, 3, 8, 12, 0, 0, tzinfo=NYSE_TZ)
        mock_utc = mock_time.astimezone(UTC)

        with patch("src.lambdas.dashboard.market.datetime") as mock_datetime:
            mock_datetime.now.return_value = mock_utc

            response = get_market_status()

            assert response.next_open is not None

    def test_sets_market_hours_when_open(self):
        """Should set market_open and market_close when open."""
        # Mock time to 10:00 AM ET on a weekday
        mock_time = datetime(2025, 3, 10, 10, 0, 0, tzinfo=NYSE_TZ)
        mock_utc = mock_time.astimezone(UTC)

        with patch("src.lambdas.dashboard.market.datetime") as mock_datetime:
            mock_datetime.now.return_value = mock_utc

            response = get_market_status()

            assert response.market_open is not None
            assert response.market_close is not None


class TestGetPremarketEstimates:
    """Tests for get_premarket_estimates function."""

    def test_returns_premarket_response(self):
        """Should return PremarketResponse."""
        with patch("src.lambdas.dashboard.market.get_market_status") as mock_status:
            mock_status.return_value = MarketStatusResponse(
                status="closed",
                exchange="NYSE",
                current_time="2025-01-01T00:00:00Z",
                market_open=None,
                market_close=None,
                next_open="2025-01-02T14:30:00Z",
                reason="premarket",
            )

            response = get_premarket_estimates(
                config_id="test-config",
                tickers=["AAPL"],
            )

            assert isinstance(response, PremarketResponse)
            assert response.config_id == "test-config"

    def test_redirects_when_market_open(self):
        """Should redirect to sentiment endpoint when market is open."""
        with patch("src.lambdas.dashboard.market.get_market_status") as mock_status:
            mock_status.return_value = MarketStatusResponse(
                status="open",
                exchange="NYSE",
                current_time="2025-01-01T15:00:00Z",
                market_open="2025-01-01T14:30:00Z",
                market_close="2025-01-01T21:00:00Z",
                next_open=None,
            )

            response = get_premarket_estimates(
                config_id="test-config",
                tickers=["AAPL"],
            )

            assert response.market_status == "open"
            assert response.redirect_to is not None
            assert "sentiment" in response.redirect_to

    def test_includes_estimates_when_closed(self):
        """Should include estimates when market is closed."""
        with patch("src.lambdas.dashboard.market.get_market_status") as mock_status:
            mock_status.return_value = MarketStatusResponse(
                status="closed",
                exchange="NYSE",
                current_time="2025-01-01T00:00:00Z",
                market_open=None,
                market_close=None,
                next_open="2025-01-02T14:30:00Z",
                reason="premarket",
            )

            response = get_premarket_estimates(
                config_id="test-config",
                tickers=["AAPL", "MSFT"],
            )

            assert response.estimates is not None
            assert len(response.estimates) == 2

    def test_uses_finnhub_for_premarket_data(self):
        """Should use Finnhub for pre-market data."""
        mock_finnhub = MagicMock()
        mock_finnhub.get_quote.return_value = {
            "c": 152.0,  # Current
            "pc": 150.0,  # Previous close
        }
        mock_finnhub.get_news.return_value = []

        with patch("src.lambdas.dashboard.market.get_market_status") as mock_status:
            mock_status.return_value = MarketStatusResponse(
                status="closed",
                exchange="NYSE",
                current_time="2025-01-01T00:00:00Z",
                market_open=None,
                market_close=None,
                next_open="2025-01-02T14:30:00Z",
                reason="premarket",
            )

            get_premarket_estimates(
                config_id="test-config",
                tickers=["AAPL"],
                finnhub_adapter=mock_finnhub,
            )

            mock_finnhub.get_quote.assert_called_with("AAPL")

    def test_calculates_change_percent(self):
        """Should calculate change percent."""
        mock_finnhub = MagicMock()
        mock_finnhub.get_quote.return_value = {
            "c": 153.0,  # 2% up
            "pc": 150.0,
        }
        mock_finnhub.get_news.return_value = []

        with patch("src.lambdas.dashboard.market.get_market_status") as mock_status:
            mock_status.return_value = MarketStatusResponse(
                status="closed",
                exchange="NYSE",
                current_time="2025-01-01T00:00:00Z",
                market_open=None,
                market_close=None,
                next_open="2025-01-02T14:30:00Z",
                reason="premarket",
            )

            response = get_premarket_estimates(
                config_id="test-config",
                tickers=["AAPL"],
                finnhub_adapter=mock_finnhub,
            )

            assert response.estimates[0].change_percent == 2.0

    def test_includes_disclaimer(self):
        """Should include disclaimer for pre-market data."""
        with patch("src.lambdas.dashboard.market.get_market_status") as mock_status:
            mock_status.return_value = MarketStatusResponse(
                status="closed",
                exchange="NYSE",
                current_time="2025-01-01T00:00:00Z",
                market_open=None,
                market_close=None,
                next_open="2025-01-02T14:30:00Z",
                reason="premarket",
            )

            response = get_premarket_estimates(
                config_id="test-config",
                tickers=["AAPL"],
            )

            assert response.disclaimer is not None
            assert "predictive" in response.disclaimer.lower()

    def test_handles_finnhub_error_gracefully(self):
        """Should handle Finnhub errors gracefully."""
        mock_finnhub = MagicMock()
        mock_finnhub.get_quote.side_effect = Exception("API error")

        with patch("src.lambdas.dashboard.market.get_market_status") as mock_status:
            mock_status.return_value = MarketStatusResponse(
                status="closed",
                exchange="NYSE",
                current_time="2025-01-01T00:00:00Z",
                market_open=None,
                market_close=None,
                next_open="2025-01-02T14:30:00Z",
                reason="premarket",
            )

            # Should not raise
            response = get_premarket_estimates(
                config_id="test-config",
                tickers=["AAPL"],
                finnhub_adapter=mock_finnhub,
            )

            assert isinstance(response, PremarketResponse)
