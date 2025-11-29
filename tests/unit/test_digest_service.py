"""Unit tests for daily digest email service (Issue #127).

Tests cover:
- DigestData container
- DigestService.get_users_for_digest
- DigestService._is_digest_due
- DigestService.get_user_configurations
- DigestService.get_ticker_sentiment_data
- DigestService.generate_digest
- DigestService.build_digest_html
- process_daily_digests orchestration
"""

import uuid
from datetime import UTC, datetime, timedelta
from unittest.mock import MagicMock, patch

import pytest

from src.lambdas.notification.digest_service import (
    DigestData,
    DigestService,
    process_daily_digests,
)
from src.lambdas.shared.models.configuration import Configuration, Ticker
from src.lambdas.shared.models.notification import DigestSettings
from src.lambdas.shared.models.user import User


@pytest.fixture
def mock_table():
    """Create a mock DynamoDB table."""
    return MagicMock()


@pytest.fixture
def user_id():
    """Generate a user ID."""
    return str(uuid.uuid4())


@pytest.fixture
def config_id():
    """Generate a config ID."""
    return str(uuid.uuid4())


@pytest.fixture
def sample_user(user_id):
    """Create a sample user."""
    now = datetime.now(UTC)
    return User(
        user_id=user_id,
        email="test@example.com",
        auth_type="email",
        created_at=now - timedelta(days=30),
        last_active_at=now,
        session_expires_at=now + timedelta(days=30),
        timezone="America/New_York",
    )


@pytest.fixture
def sample_digest_settings(user_id):
    """Create sample digest settings."""
    return DigestSettings(
        user_id=user_id,
        enabled=True,
        time="09:00",
        timezone="America/New_York",
        include_all_configs=True,
    )


@pytest.fixture
def sample_configuration(user_id, config_id):
    """Create a sample configuration."""
    now = datetime.now(UTC)
    return Configuration(
        config_id=config_id,
        user_id=user_id,
        name="Tech Giants",
        tickers=[
            Ticker(
                symbol="AAPL",
                name="Apple Inc.",
                exchange="NASDAQ",
                added_at=now,
            ),
            Ticker(
                symbol="GOOGL",
                name="Alphabet Inc.",
                exchange="NASDAQ",
                added_at=now,
            ),
        ],
        timeframe_days=7,
        created_at=now,
        updated_at=now,
    )


class TestDigestData:
    """Tests for DigestData container."""

    def test_has_content_with_data(
        self, sample_user, sample_digest_settings, sample_configuration
    ):
        """DigestData.has_content returns True when ticker data exists."""
        digest = DigestData(
            user=sample_user,
            settings=sample_digest_settings,
            configs=[sample_configuration],
            ticker_data={"AAPL": {"current_sentiment": 0.5}},
        )
        assert digest.has_content is True

    def test_has_content_without_data(
        self, sample_user, sample_digest_settings, sample_configuration
    ):
        """DigestData.has_content returns False when no ticker data."""
        digest = DigestData(
            user=sample_user,
            settings=sample_digest_settings,
            configs=[sample_configuration],
            ticker_data={},
        )
        assert digest.has_content is False

    def test_all_tickers_from_configs(
        self, sample_user, sample_digest_settings, sample_configuration
    ):
        """DigestData.all_tickers returns sorted unique tickers from configs."""
        digest = DigestData(
            user=sample_user,
            settings=sample_digest_settings,
            configs=[sample_configuration],
            ticker_data={"AAPL": {}},
        )
        assert digest.all_tickers == ["AAPL", "GOOGL"]


class TestDigestServiceIsDigestDue:
    """Tests for DigestService._is_digest_due."""

    def test_digest_due_at_configured_time(self, mock_table, sample_digest_settings):
        """Digest is due when current time matches configured time in user's timezone."""
        service = DigestService(mock_table)

        # Mock current time to be 9:00 AM in user's timezone (America/New_York)
        # 9:00 AM EST = 14:00 UTC (during standard time)
        with patch("src.lambdas.notification.digest_service.datetime") as mock_dt:
            # Create a mock datetime that returns controlled time
            mock_now = datetime(
                2025, 1, 15, 14, 2, 0, tzinfo=UTC
            )  # 14:02 UTC = 9:02 AM EST
            mock_dt.now.return_value = mock_now
            mock_dt.fromisoformat = datetime.fromisoformat
            mock_dt.side_effect = lambda *args, **kw: datetime(*args, **kw)

            result = service._is_digest_due(sample_digest_settings, 14)
            assert result is True

    def test_digest_not_due_wrong_hour(self, mock_table, sample_digest_settings):
        """Digest is not due when current hour doesn't match."""
        service = DigestService(mock_table)

        with patch("src.lambdas.notification.digest_service.datetime") as mock_dt:
            mock_now = datetime(
                2025, 1, 15, 10, 0, 0, tzinfo=UTC
            )  # 10:00 UTC = 5:00 AM EST
            mock_dt.now.return_value = mock_now
            mock_dt.fromisoformat = datetime.fromisoformat
            mock_dt.side_effect = lambda *args, **kw: datetime(*args, **kw)

            result = service._is_digest_due(sample_digest_settings, 10)
            assert result is False

    def test_digest_not_due_already_sent_today(
        self, mock_table, sample_digest_settings
    ):
        """Digest is not due if already sent today."""
        service = DigestService(mock_table)

        # Set last_sent to the same day as the mocked "now" time (in user timezone)
        # 9:00 AM EST on Jan 15 2025 = 14:00 UTC
        # Set last_sent to earlier that same day
        sample_digest_settings.last_sent = datetime(2025, 1, 15, 13, 0, 0, tzinfo=UTC)

        with patch("src.lambdas.notification.digest_service.datetime") as mock_dt:
            mock_now = datetime(2025, 1, 15, 14, 2, 0, tzinfo=UTC)
            mock_dt.now.return_value = mock_now
            mock_dt.fromisoformat = datetime.fromisoformat
            mock_dt.side_effect = lambda *args, **kw: datetime(*args, **kw)

            result = service._is_digest_due(sample_digest_settings, 14)
            assert result is False


class TestDigestServiceGetUserConfigurations:
    """Tests for DigestService.get_user_configurations."""

    def test_gets_all_configs_when_include_all(
        self, mock_table, user_id, sample_digest_settings, sample_configuration
    ):
        """Returns all configurations when include_all_configs is True."""
        service = DigestService(mock_table)

        mock_table.query.return_value = {
            "Items": [sample_configuration.to_dynamodb_item()]
        }

        configs = service.get_user_configurations(user_id, sample_digest_settings)

        assert len(configs) == 1
        assert configs[0].name == "Tech Giants"
        mock_table.query.assert_called_once()

    def test_filters_by_config_ids(
        self, mock_table, user_id, sample_digest_settings, sample_configuration
    ):
        """Returns only specified configurations when include_all_configs is False."""
        service = DigestService(mock_table)
        sample_digest_settings.include_all_configs = False
        sample_digest_settings.config_ids = [sample_configuration.config_id]

        mock_table.query.return_value = {
            "Items": [sample_configuration.to_dynamodb_item()]
        }

        configs = service.get_user_configurations(user_id, sample_digest_settings)

        assert len(configs) == 1

    def test_excludes_configs_not_in_list(
        self, mock_table, user_id, sample_digest_settings, sample_configuration
    ):
        """Excludes configurations not in config_ids list."""
        service = DigestService(mock_table)
        sample_digest_settings.include_all_configs = False
        sample_digest_settings.config_ids = ["other-config-id"]  # Different ID

        mock_table.query.return_value = {
            "Items": [sample_configuration.to_dynamodb_item()]
        }

        configs = service.get_user_configurations(user_id, sample_digest_settings)

        assert len(configs) == 0


class TestDigestServiceGetTickerSentimentData:
    """Tests for DigestService.get_ticker_sentiment_data."""

    def test_returns_sentiment_data_for_tickers(self, mock_table):
        """Returns aggregated sentiment data for tickers."""
        service = DigestService(mock_table)

        # Mock query results
        mock_table.query.return_value = {
            "Items": [
                {"sentiment_score": "0.45"},
                {"sentiment_score": "0.55"},
            ]
        }

        result = service.get_ticker_sentiment_data(["AAPL"])

        assert "AAPL" in result
        assert result["AAPL"]["current_sentiment"] == 0.5  # Average of 0.45 and 0.55
        assert result["AAPL"]["sentiment_label"] == "positive"

    def test_returns_neutral_for_no_data(self, mock_table):
        """Returns neutral values when no sentiment data exists."""
        service = DigestService(mock_table)

        mock_table.query.return_value = {"Items": []}

        result = service.get_ticker_sentiment_data(["AAPL"])

        assert result["AAPL"]["current_sentiment"] == 0.0
        assert result["AAPL"]["sentiment_label"] == "neutral"
        assert result["AAPL"]["article_count"] == 0

    def test_handles_query_error(self, mock_table):
        """Handles DynamoDB query errors gracefully."""
        service = DigestService(mock_table)

        mock_table.query.side_effect = Exception("DynamoDB error")

        result = service.get_ticker_sentiment_data(["AAPL"])

        assert result["AAPL"]["current_sentiment"] == 0.0
        assert result["AAPL"]["error"] is True


class TestDigestServiceGenerateDigest:
    """Tests for DigestService.generate_digest."""

    def test_generates_digest_with_data(
        self, mock_table, sample_user, sample_digest_settings, sample_configuration
    ):
        """Generates DigestData when configurations and ticker data exist."""
        service = DigestService(mock_table)

        # Mock get_user_configurations
        mock_table.query.side_effect = [
            # First call: get configurations
            {"Items": [sample_configuration.to_dynamodb_item()]},
            # Subsequent calls: get sentiment data
            {"Items": [{"sentiment_score": "0.5"}]},
            {"Items": []},  # previous period
            {"Items": [{"sentiment_score": "0.3"}]},
            {"Items": []},  # previous period
        ]

        digest = service.generate_digest(sample_user, sample_digest_settings)

        assert digest is not None
        assert digest.has_content
        assert len(digest.configs) == 1
        assert "AAPL" in digest.ticker_data

    def test_returns_none_for_no_configs(
        self, mock_table, sample_user, sample_digest_settings
    ):
        """Returns None when user has no configurations."""
        service = DigestService(mock_table)

        mock_table.query.return_value = {"Items": []}

        digest = service.generate_digest(sample_user, sample_digest_settings)

        assert digest is None


class TestDigestServiceBuildDigestHtml:
    """Tests for DigestService.build_digest_html."""

    def test_builds_valid_html(
        self, mock_table, sample_user, sample_digest_settings, sample_configuration
    ):
        """Builds valid HTML email content."""
        service = DigestService(mock_table)

        digest = DigestData(
            user=sample_user,
            settings=sample_digest_settings,
            configs=[sample_configuration],
            ticker_data={
                "AAPL": {
                    "current_sentiment": 0.45,
                    "previous_sentiment": 0.30,
                    "sentiment_change": 0.15,
                    "sentiment_label": "positive",
                    "article_count": 10,
                    "volatility": None,
                },
                "GOOGL": {
                    "current_sentiment": -0.20,
                    "previous_sentiment": 0.10,
                    "sentiment_change": -0.30,
                    "sentiment_label": "neutral",
                    "article_count": 5,
                    "volatility": None,
                },
            },
        )

        html = service.build_digest_html(digest)

        assert "<!DOCTYPE html>" in html
        assert "Daily Sentiment Digest" in html
        assert "AAPL" in html
        assert "GOOGL" in html
        assert "POSITIVE" in html
        assert "View Full Dashboard" in html

    def test_includes_ticker_links(
        self, mock_table, sample_user, sample_digest_settings, sample_configuration
    ):
        """HTML includes links to dashboard for each ticker."""
        service = DigestService(mock_table, dashboard_url="https://test.example.com")

        digest = DigestData(
            user=sample_user,
            settings=sample_digest_settings,
            configs=[sample_configuration],
            ticker_data={
                "AAPL": {
                    "current_sentiment": 0.45,
                    "previous_sentiment": 0.30,
                    "sentiment_change": 0.15,
                    "sentiment_label": "positive",
                    "article_count": 10,
                    "volatility": None,
                },
            },
        )

        html = service.build_digest_html(digest)

        assert "https://test.example.com/dashboard?ticker=AAPL" in html


class TestProcessDailyDigests:
    """Tests for process_daily_digests orchestration function."""

    @patch("src.lambdas.notification.digest_service.DigestService")
    def test_returns_stats(self, mock_service_class, mock_table):
        """Returns processing stats dict."""
        mock_service = MagicMock()
        mock_service_class.return_value = mock_service
        mock_service.get_users_for_digest.return_value = []

        mock_email_service = MagicMock()

        stats = process_daily_digests(mock_table, mock_email_service)

        assert "processed" in stats
        assert "sent" in stats
        assert "skipped" in stats
        assert "failed" in stats

    @patch("src.lambdas.notification.digest_service.DigestService")
    def test_sends_emails_for_users_with_content(
        self,
        mock_service_class,
        mock_table,
        sample_user,
        sample_digest_settings,
        sample_configuration,
    ):
        """Sends emails for users with digest content."""
        mock_service = MagicMock()
        mock_service_class.return_value = mock_service

        # Setup mock returns
        mock_service.get_users_for_digest.return_value = [
            (sample_user, sample_digest_settings)
        ]
        mock_digest = DigestData(
            user=sample_user,
            settings=sample_digest_settings,
            configs=[sample_configuration],
            ticker_data={"AAPL": {"current_sentiment": 0.5}},
        )
        mock_service.generate_digest.return_value = mock_digest
        mock_service.build_digest_html.return_value = "<html>...</html>"

        mock_email_service = MagicMock()
        mock_email_service.send_email.return_value = True

        stats = process_daily_digests(mock_table, mock_email_service)

        assert stats["processed"] == 1
        assert stats["sent"] == 1
        mock_email_service.send_email.assert_called_once()
        mock_service.update_last_sent.assert_called_once()

    @patch("src.lambdas.notification.digest_service.DigestService")
    def test_skips_users_without_content(
        self, mock_service_class, mock_table, sample_user, sample_digest_settings
    ):
        """Skips users with no digest content."""
        mock_service = MagicMock()
        mock_service_class.return_value = mock_service

        mock_service.get_users_for_digest.return_value = [
            (sample_user, sample_digest_settings)
        ]
        mock_service.generate_digest.return_value = None  # No content

        mock_email_service = MagicMock()

        stats = process_daily_digests(mock_table, mock_email_service)

        assert stats["processed"] == 1
        assert stats["skipped"] == 1
        assert stats["sent"] == 0
        mock_email_service.send_email.assert_not_called()

    @patch("src.lambdas.notification.digest_service.DigestService")
    def test_handles_send_failure(
        self,
        mock_service_class,
        mock_table,
        sample_user,
        sample_digest_settings,
        sample_configuration,
    ):
        """Counts failed sends correctly."""
        mock_service = MagicMock()
        mock_service_class.return_value = mock_service

        mock_service.get_users_for_digest.return_value = [
            (sample_user, sample_digest_settings)
        ]
        mock_digest = DigestData(
            user=sample_user,
            settings=sample_digest_settings,
            configs=[sample_configuration],
            ticker_data={"AAPL": {"current_sentiment": 0.5}},
        )
        mock_service.generate_digest.return_value = mock_digest
        mock_service.build_digest_html.return_value = "<html>...</html>"

        mock_email_service = MagicMock()
        mock_email_service.send_email.return_value = False  # Send failed

        stats = process_daily_digests(mock_table, mock_email_service)

        assert stats["processed"] == 1
        assert stats["failed"] == 1
        assert stats["sent"] == 0


class TestDigestServiceUpdateLastSent:
    """Tests for DigestService.update_last_sent."""

    def test_updates_dynamodb(self, mock_table, user_id):
        """Updates last_sent timestamp in DynamoDB."""
        service = DigestService(mock_table)

        service.update_last_sent(user_id)

        mock_table.update_item.assert_called_once()
        call_args = mock_table.update_item.call_args
        assert call_args.kwargs["Key"]["PK"] == f"USER#{user_id}"
        assert call_args.kwargs["Key"]["SK"] == "DIGEST_SETTINGS"

    def test_handles_update_error(self, mock_table, user_id):
        """Handles update errors gracefully."""
        service = DigestService(mock_table)
        mock_table.update_item.side_effect = Exception("DynamoDB error")

        # Should not raise, just log warning
        service.update_last_sent(user_id)
