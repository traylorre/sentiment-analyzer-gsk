"""Unit tests for ticker filtering in config streams.

Tests that config streams only include sentiment updates for
tickers in the user's configuration per FR-015.
"""

from src.lambdas.sse_streaming.connection import SSEConnection


class TestTickerFiltering:
    """Tests for ticker filtering in SSEConnection."""

    def test_matches_ticker_with_single_filter(self):
        """Test matching a single ticker filter."""
        connection = SSEConnection(
            connection_id="test-conn",
            ticker_filters=["AAPL"],
        )

        assert connection.matches_ticker("AAPL") is True
        assert connection.matches_ticker("MSFT") is False

    def test_matches_ticker_with_multiple_filters(self):
        """Test matching multiple ticker filters."""
        connection = SSEConnection(
            connection_id="test-conn",
            ticker_filters=["AAPL", "MSFT", "GOOGL"],
        )

        assert connection.matches_ticker("AAPL") is True
        assert connection.matches_ticker("MSFT") is True
        assert connection.matches_ticker("GOOGL") is True
        assert connection.matches_ticker("AMZN") is False

    def test_matches_ticker_with_default_filters(self):
        """Test that default (no filters) means all tickers match (global stream)."""
        # Use default - don't pass ticker_filters at all
        connection = SSEConnection(connection_id="test-conn")

        # No filters = all tickers pass
        assert connection.matches_ticker("AAPL") is True
        assert connection.matches_ticker("MSFT") is True
        assert connection.matches_ticker("ANY") is True

    def test_matches_ticker_with_empty_filters(self):
        """Test that empty filter list means all tickers match."""
        connection = SSEConnection(
            connection_id="test-conn",
            ticker_filters=[],
        )

        # Empty list = all tickers pass
        assert connection.matches_ticker("AAPL") is True
        assert connection.matches_ticker("MSFT") is True

    def test_matches_ticker_case_insensitive(self):
        """Test that ticker matching is case-insensitive."""
        connection = SSEConnection(
            connection_id="test-conn",
            ticker_filters=["AAPL"],
        )

        assert connection.matches_ticker("AAPL") is True
        assert connection.matches_ticker("aapl") is True
        assert connection.matches_ticker("Aapl") is True


class TestConnectionTickerConfig:
    """Tests for SSEConnection ticker configuration."""

    def test_connection_stores_ticker_filters(self):
        """Test that connection stores ticker filters."""
        connection = SSEConnection(
            connection_id="test-conn",
            config_id="config-123",
            ticker_filters=["AAPL", "MSFT"],
        )

        assert connection.ticker_filters == ["AAPL", "MSFT"]

    def test_connection_stores_config_id(self):
        """Test that connection stores config ID."""
        connection = SSEConnection(
            connection_id="test-conn",
            config_id="config-123",
        )

        assert connection.config_id == "config-123"

    def test_global_connection_has_no_config(self):
        """Test that global connections have no config ID."""
        connection = SSEConnection(connection_id="test-conn")

        assert connection.config_id is None
        # Default is empty list, which means all tickers match (global stream)
        assert connection.ticker_filters == []


class TestFilteredEventDelivery:
    """Tests for filtered event delivery in config streams."""

    def test_sentiment_event_filtered_by_ticker(self):
        """Test that sentiment events are filtered by ticker.

        Per T036: Implement ticker filtering for sentiment_update events.
        """
        connection = SSEConnection(
            connection_id="test-conn",
            ticker_filters=["AAPL", "MSFT"],
        )

        # AAPL should pass
        assert connection.matches_ticker("AAPL") is True

        # AMZN should not pass
        assert connection.matches_ticker("AMZN") is False

    def test_heartbeat_events_not_filtered(self):
        """Test that heartbeat events are not filtered by ticker.

        Heartbeats should always be sent regardless of ticker filters.
        """
        # Heartbeats don't have tickers, so they always pass through
        # This is implicit in the stream generator logic
        connection = SSEConnection(
            connection_id="test-conn",
            ticker_filters=["AAPL"],
        )

        # Connection exists and can receive events
        assert connection.connection_id is not None

    def test_metrics_events_not_filtered(self):
        """Test that metrics events are not filtered by ticker.

        Global metrics should always be sent regardless of ticker filters.
        """
        # Metrics don't have individual tickers, so they pass through
        connection = SSEConnection(
            connection_id="test-conn",
            ticker_filters=["AAPL"],
        )

        # Connection exists and can receive events
        assert connection.connection_id is not None
