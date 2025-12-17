"""
Integration Test: User Story 1 - Anonymous User Journey
========================================================

Tests the complete flow of an anonymous user:
1. Landing on the dashboard
2. Creating an anonymous session
3. Creating a ticker configuration
4. Viewing sentiment data
5. Viewing volatility data
6. Viewing heat map
7. Session validation and extension

IMPORTANT: This test uses moto to mock ALL AWS infrastructure.
- Purpose: Verify the complete user journey works end-to-end
- Run on: Every PR, every merge
- Cost: $0 (no real AWS resources)

For On-Call Engineers:
    If this test fails, check:
    1. DynamoDB table schema matches expected keys (PK, SK)
    2. Session TTL handling is correct
    3. Configuration validation logic
    4. API adapters are properly mocked
"""

import os
import uuid

import boto3
import pytest
from moto import mock_aws

from src.lambdas.dashboard.auth import (
    AnonymousSessionRequest,
    create_anonymous_session,
    extend_session,
    validate_session,
)
from src.lambdas.dashboard.configurations import (
    create_configuration,
    delete_configuration,
    get_configuration,
    list_configurations,
    update_configuration,
)
from src.lambdas.dashboard.market import (
    get_market_status,
    get_refresh_status,
    trigger_refresh,
)
from src.lambdas.dashboard.sentiment import (
    get_heatmap_data,
    get_sentiment_by_configuration,
)
from src.lambdas.dashboard.tickers import search_tickers, validate_ticker
from src.lambdas.dashboard.volatility import (
    get_correlation_data,
    get_volatility_by_configuration,
)
from src.lambdas.shared.models.configuration import (
    ConfigurationCreate,
    ConfigurationUpdate,
)


@pytest.fixture
def env_vars():
    """Set test environment variables."""
    os.environ["DATABASE_TABLE"] = "test-user-config"
    os.environ["ENVIRONMENT"] = "test"
    yield
    for key in ["DATABASE_TABLE", "ENVIRONMENT"]:
        os.environ.pop(key, None)


@pytest.fixture
def dynamodb_table():
    """Create mock DynamoDB table with User Story 1 schema."""
    with mock_aws():
        dynamodb = boto3.resource("dynamodb", region_name="us-east-1")

        # Create table with PK/SK design for users and configurations
        table = dynamodb.create_table(
            TableName="test-user-config",
            KeySchema=[
                {"AttributeName": "PK", "KeyType": "HASH"},
                {"AttributeName": "SK", "KeyType": "RANGE"},
            ],
            AttributeDefinitions=[
                {"AttributeName": "PK", "AttributeType": "S"},
                {"AttributeName": "SK", "AttributeType": "S"},
            ],
            BillingMode="PAY_PER_REQUEST",
        )

        yield table


class TestAnonymousUserJourney:
    """Integration tests for User Story 1: Anonymous user flow."""

    @mock_aws
    def test_complete_anonymous_journey(self, env_vars):
        """E2E: Complete anonymous user journey from landing to data view."""
        # Setup
        dynamodb = boto3.resource("dynamodb", region_name="us-east-1")
        table = dynamodb.create_table(
            TableName="test-user-config",
            KeySchema=[
                {"AttributeName": "PK", "KeyType": "HASH"},
                {"AttributeName": "SK", "KeyType": "RANGE"},
            ],
            AttributeDefinitions=[
                {"AttributeName": "PK", "AttributeType": "S"},
                {"AttributeName": "SK", "AttributeType": "S"},
            ],
            BillingMode="PAY_PER_REQUEST",
        )

        # Step 1: User lands on dashboard - create anonymous session
        session_request = AnonymousSessionRequest(timezone="America/New_York")
        session_response = create_anonymous_session(table, session_request)

        assert session_response.auth_type == "anonymous"
        assert session_response.user_id is not None
        user_id = session_response.user_id

        # Step 2: Validate the session
        validation = validate_session(table, user_id)
        assert validation.valid is True
        assert validation.user_id == user_id

        # Step 3: Search for tickers
        search_results = search_tickers("AAPL")
        assert len(search_results.results) > 0
        assert any(r.symbol == "AAPL" for r in search_results.results)

        # Step 4: Validate a ticker
        ticker_validation = validate_ticker("AAPL")
        assert ticker_validation.status == "valid"

        # Step 5: Create a configuration with tickers
        config_request = ConfigurationCreate(
            name="Tech Stocks",
            tickers=["AAPL", "MSFT", "GOOGL"],
            timeframe_days=30,
        )
        config_response = create_configuration(table, user_id, config_request)

        assert config_response.name == "Tech Stocks"
        assert len(config_response.tickers) == 3
        config_id = config_response.config_id

        # Step 6: List configurations (should show 1)
        configs = list_configurations(table, user_id)
        assert len(configs.configurations) == 1
        assert configs.max_allowed == 2

        # Step 7: Get sentiment data for configuration
        sentiment_data = get_sentiment_by_configuration(
            config_id=config_id,
            tickers=["AAPL", "MSFT", "GOOGL"],
        )

        assert sentiment_data.config_id == config_id
        assert len(sentiment_data.tickers) == 3
        assert sentiment_data.cache_status == "fresh"

        # Step 8: Get heat map data
        heatmap = get_heatmap_data(
            config_id=config_id,
            tickers=["AAPL", "MSFT", "GOOGL"],
            view="sources",
            sentiment_data=sentiment_data,
        )

        assert heatmap.view == "sources"
        assert len(heatmap.matrix) == 3
        assert heatmap.legend is not None

        # Step 9: Get volatility data
        volatility_data = get_volatility_by_configuration(
            config_id=config_id,
            tickers=["AAPL", "MSFT", "GOOGL"],
        )

        assert volatility_data.config_id == config_id
        assert len(volatility_data.tickers) == 3

        # Step 10: Get correlation data
        correlation_data = get_correlation_data(
            config_id=config_id,
            tickers=["AAPL", "MSFT", "GOOGL"],
        )

        assert correlation_data.config_id == config_id
        assert len(correlation_data.tickers) == 3

        # Step 11: Check market status
        market_status = get_market_status()
        assert market_status.exchange == "NYSE"
        assert market_status.status in ["open", "closed"]

        # Step 12: Check refresh status
        refresh_status = get_refresh_status(config_id)
        assert refresh_status.refresh_interval_seconds == 300

        # Step 13: Trigger manual refresh
        refresh_trigger = trigger_refresh(config_id)
        assert refresh_trigger.status == "refresh_queued"

        # Journey complete!

    @mock_aws
    def test_session_lifecycle(self, env_vars):
        """E2E: Session creation, validation, and extension."""
        dynamodb = boto3.resource("dynamodb", region_name="us-east-1")
        table = dynamodb.create_table(
            TableName="test-user-config",
            KeySchema=[
                {"AttributeName": "PK", "KeyType": "HASH"},
                {"AttributeName": "SK", "KeyType": "RANGE"},
            ],
            AttributeDefinitions=[
                {"AttributeName": "PK", "AttributeType": "S"},
                {"AttributeName": "SK", "AttributeType": "S"},
            ],
            BillingMode="PAY_PER_REQUEST",
        )

        # Create session
        session = create_anonymous_session(table, AnonymousSessionRequest())
        user_id = session.user_id

        # Validate - should be valid
        validation = validate_session(table, user_id)
        assert validation.valid is True

        # Extend session
        extended = extend_session(table, user_id)
        assert extended is not None

        # Validate again - still valid
        validation_after = validate_session(table, user_id)
        assert validation_after.valid is True

        # Validate with invalid ID - should fail
        invalid_validation = validate_session(table, "not-a-uuid")
        assert invalid_validation.valid is False
        assert invalid_validation.error == "invalid_user_id"

        # Validate with nonexistent ID - should fail
        fake_uuid = str(uuid.uuid4())
        missing_validation = validate_session(table, fake_uuid)
        assert missing_validation.valid is False
        assert missing_validation.error == "user_not_found"

    @mock_aws
    def test_configuration_crud_operations(self, env_vars):
        """E2E: Full CRUD operations on configurations."""
        dynamodb = boto3.resource("dynamodb", region_name="us-east-1")
        table = dynamodb.create_table(
            TableName="test-user-config",
            KeySchema=[
                {"AttributeName": "PK", "KeyType": "HASH"},
                {"AttributeName": "SK", "KeyType": "RANGE"},
            ],
            AttributeDefinitions=[
                {"AttributeName": "PK", "AttributeType": "S"},
                {"AttributeName": "SK", "AttributeType": "S"},
            ],
            BillingMode="PAY_PER_REQUEST",
        )

        # Create user
        session = create_anonymous_session(table, AnonymousSessionRequest())
        user_id = session.user_id

        # Create first configuration
        config1 = create_configuration(
            table,
            user_id,
            ConfigurationCreate(
                name="Portfolio 1",
                tickers=["AAPL", "MSFT"],
            ),
        )
        assert config1.name == "Portfolio 1"
        config1_id = config1.config_id

        # Create second configuration
        config2 = create_configuration(
            table,
            user_id,
            ConfigurationCreate(
                name="Portfolio 2",
                tickers=["GOOGL"],
            ),
        )
        assert config2.name == "Portfolio 2"

        # Try to create third - should fail (max 2)
        config3_result = create_configuration(
            table,
            user_id,
            ConfigurationCreate(
                name="Portfolio 3",
                tickers=["AMZN"],
            ),
        )
        # Should return ErrorResponse
        assert hasattr(config3_result, "error")
        assert config3_result.error.code == "CONFLICT"

        # List - should show 2
        configs = list_configurations(table, user_id)
        assert len(configs.configurations) == 2

        # Get single config
        retrieved = get_configuration(table, user_id, config1_id)
        assert retrieved is not None
        assert retrieved.name == "Portfolio 1"

        # Update config
        updated = update_configuration(
            table,
            user_id,
            config1_id,
            ConfigurationUpdate(name="Updated Portfolio"),
        )
        assert updated is not None
        assert updated.name == "Updated Portfolio"

        # Delete config (soft delete)
        deleted = delete_configuration(table, user_id, config1_id)
        assert deleted is True

        # List - should show 1 (deleted config filtered out)
        configs_after = list_configurations(table, user_id)
        assert len(configs_after.configurations) == 1

        # Get deleted config - should return None
        deleted_config = get_configuration(table, user_id, config1_id)
        assert deleted_config is None

    @mock_aws
    def test_ticker_validation_and_search(self, env_vars):
        """E2E: Ticker validation and search functionality."""
        # Validate known tickers
        aapl = validate_ticker("AAPL")
        assert aapl.status == "valid"
        assert aapl.exchange == "NASDAQ"

        msft = validate_ticker("msft")  # lowercase
        assert msft.status == "valid"
        assert msft.symbol == "MSFT"  # normalized

        # Validate unknown ticker
        unknown = validate_ticker("ZZZZZ")
        assert unknown.status == "invalid"

        # Validate invalid format
        invalid = validate_ticker("TOOLONGNAME")
        assert invalid.status == "invalid"

        # Search by symbol prefix
        results = search_tickers("AA")
        symbols = [r.symbol for r in results.results]
        assert "AAPL" in symbols

        # Search by company name
        apple_results = search_tickers("apple")
        assert any(r.symbol == "AAPL" for r in apple_results.results)

        # Empty search
        empty = search_tickers("")
        assert len(empty.results) == 0

    @mock_aws
    def test_sentiment_and_volatility_data(self, env_vars):
        """E2E: Sentiment and volatility data retrieval."""
        config_id = str(uuid.uuid4())
        tickers = ["AAPL", "MSFT"]

        # Get sentiment (without adapters - returns structure but no data)
        sentiment = get_sentiment_by_configuration(
            config_id=config_id,
            tickers=tickers,
        )

        assert sentiment.config_id == config_id
        assert len(sentiment.tickers) == 2
        assert sentiment.cache_status == "fresh"
        assert sentiment.next_refresh_at is not None

        # Get heat map - sources view
        heatmap_sources = get_heatmap_data(
            config_id=config_id,
            tickers=tickers,
            view="sources",
        )

        assert heatmap_sources.view == "sources"
        assert len(heatmap_sources.matrix) == 2
        # Each row should have cells for tiingo, finnhub, our_model
        for row in heatmap_sources.matrix:
            assert len(row.cells) == 3

        # Get heat map - timeperiods view
        heatmap_time = get_heatmap_data(
            config_id=config_id,
            tickers=tickers,
            view="timeperiods",
        )

        assert heatmap_time.view == "timeperiods"
        # Each row should have cells for today, 1w, 1m, 3m
        for row in heatmap_time.matrix:
            periods = [c.period for c in row.cells]
            assert "today" in periods
            assert "1w" in periods

        # Get volatility (without adapters - returns placeholders)
        volatility = get_volatility_by_configuration(
            config_id=config_id,
            tickers=tickers,
        )

        assert volatility.config_id == config_id
        assert len(volatility.tickers) == 2
        for ticker_vol in volatility.tickers:
            assert ticker_vol.atr.period == 14
            assert ticker_vol.atr.trend in ["increasing", "decreasing", "stable"]

        # Get correlation
        correlation = get_correlation_data(
            config_id=config_id,
            tickers=tickers,
        )

        assert correlation.config_id == config_id
        for ticker_corr in correlation.tickers:
            assert ticker_corr.correlation.interpretation in [
                "positive_divergence",
                "negative_divergence",
                "positive_convergence",
                "negative_convergence",
                "stable",
            ]

    @mock_aws
    def test_market_status_and_refresh(self, env_vars):
        """E2E: Market status and refresh controls."""
        config_id = str(uuid.uuid4())

        # Get market status
        market = get_market_status()

        assert market.exchange == "NYSE"
        assert market.status in ["open", "closed"]
        assert market.current_time is not None

        if market.status == "closed":
            # Should have reason and next_open
            assert market.reason in [
                "weekend",
                "holiday",
                "premarket",
                "after_hours",
            ]

        # Get refresh status
        refresh = get_refresh_status(config_id)

        assert refresh.refresh_interval_seconds == 300
        assert refresh.countdown_seconds >= 0
        assert refresh.is_refreshing is False

        # Trigger refresh
        trigger = trigger_refresh(config_id)

        assert trigger.status == "refresh_queued"
        assert trigger.estimated_completion is not None

    @mock_aws
    def test_user_isolation(self, env_vars):
        """E2E: Users cannot access each other's configurations."""
        dynamodb = boto3.resource("dynamodb", region_name="us-east-1")
        table = dynamodb.create_table(
            TableName="test-user-config",
            KeySchema=[
                {"AttributeName": "PK", "KeyType": "HASH"},
                {"AttributeName": "SK", "KeyType": "RANGE"},
            ],
            AttributeDefinitions=[
                {"AttributeName": "PK", "AttributeType": "S"},
                {"AttributeName": "SK", "AttributeType": "S"},
            ],
            BillingMode="PAY_PER_REQUEST",
        )

        # Create two users
        user1_session = create_anonymous_session(table, AnonymousSessionRequest())
        user2_session = create_anonymous_session(table, AnonymousSessionRequest())
        user1_id = user1_session.user_id
        user2_id = user2_session.user_id

        # User 1 creates a configuration
        user1_config = create_configuration(
            table,
            user1_id,
            ConfigurationCreate(name="User1 Portfolio", tickers=["AAPL"]),
        )
        user1_config_id = user1_config.config_id

        # User 2 tries to access User 1's config - should fail
        user2_access = get_configuration(table, user2_id, user1_config_id)
        assert user2_access is None  # Not found for user2

        # User 2 lists configs - should be empty
        user2_configs = list_configurations(table, user2_id)
        assert len(user2_configs.configurations) == 0

        # User 1 lists configs - should see their config
        user1_configs = list_configurations(table, user1_id)
        assert len(user1_configs.configurations) == 1
