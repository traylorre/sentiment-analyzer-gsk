"""Unit tests for configuration lookup in SSE streaming Lambda.

Tests ConfigLookupService for T033 implementation.
"""

from datetime import UTC, datetime
from unittest.mock import MagicMock, patch

import pytest
from botocore.exceptions import ClientError

from src.lambdas.sse_streaming.config import ConfigLookupService


class TestConfigLookupService:
    """Tests for ConfigLookupService class."""

    @pytest.fixture
    def mock_table(self):
        """Create mock DynamoDB table."""
        return MagicMock()

    @pytest.fixture
    def service(self, mock_table):
        """Create ConfigLookupService with mocked table.

        Note: We manually inject the mock table into the service
        to support lazy initialization without boto3 calls.
        """
        service = ConfigLookupService(table_name="test-table")
        # Manually inject mock table to bypass lazy boto3 initialization
        service._table = mock_table
        return service

    @pytest.fixture
    def sample_config_item(self):
        """Create sample DynamoDB configuration item."""
        return {
            "PK": "USER#user-123",
            "SK": "CONFIG#config-456",
            "config_id": "config-456",
            "user_id": "user-123",
            "name": "Tech Giants",
            "tickers": [
                {
                    "symbol": "AAPL",
                    "name": "Apple Inc",
                    "exchange": "NASDAQ",
                    "added_at": datetime.now(UTC).isoformat(),
                },
                {
                    "symbol": "MSFT",
                    "name": "Microsoft Corp",
                    "exchange": "NASDAQ",
                    "added_at": datetime.now(UTC).isoformat(),
                },
            ],
            "timeframe_days": 7,
            "include_extended_hours": False,
            "atr_period": 14,
            "created_at": datetime.now(UTC).isoformat(),
            "updated_at": datetime.now(UTC).isoformat(),
            "is_active": True,
        }

    def test_get_configuration_found(self, service, mock_table, sample_config_item):
        """Test get_configuration returns config when found."""
        mock_table.get_item.return_value = {"Item": sample_config_item}

        config = service.get_configuration("user-123", "config-456")

        assert config is not None
        assert config.config_id == "config-456"
        assert config.user_id == "user-123"
        assert len(config.tickers) == 2
        mock_table.get_item.assert_called_once_with(
            Key={"PK": "USER#user-123", "SK": "CONFIG#config-456"}
        )

    def test_get_configuration_not_found(self, service, mock_table):
        """Test get_configuration returns None when not found."""
        mock_table.get_item.return_value = {}

        config = service.get_configuration("user-123", "nonexistent")

        assert config is None

    def test_get_configuration_inactive(self, service, mock_table, sample_config_item):
        """Test get_configuration returns None for inactive configs."""
        sample_config_item["is_active"] = False
        mock_table.get_item.return_value = {"Item": sample_config_item}

        config = service.get_configuration("user-123", "config-456")

        assert config is None

    def test_get_configuration_wrong_user(self, service, mock_table):
        """Test get_configuration returns None for wrong user.

        The DynamoDB key includes user_id, so querying with wrong user
        won't find the item at all.
        """
        mock_table.get_item.return_value = {}  # Not found for wrong user

        config = service.get_configuration("wrong-user", "config-456")

        assert config is None
        mock_table.get_item.assert_called_once_with(
            Key={"PK": "USER#wrong-user", "SK": "CONFIG#config-456"}
        )

    def test_get_configuration_dynamodb_error(self, service, mock_table):
        """Test get_configuration handles DynamoDB errors gracefully."""
        mock_table.get_item.side_effect = ClientError(
            {"Error": {"Code": "InternalError", "Message": "Test error"}},
            "GetItem",
        )

        config = service.get_configuration("user-123", "config-456")

        assert config is None

    def test_get_ticker_filters_found(self, service, mock_table, sample_config_item):
        """Test get_ticker_filters returns ticker symbols."""
        mock_table.get_item.return_value = {"Item": sample_config_item}

        tickers = service.get_ticker_filters("user-123", "config-456")

        assert tickers is not None
        assert tickers == ["AAPL", "MSFT"]

    def test_get_ticker_filters_not_found(self, service, mock_table):
        """Test get_ticker_filters returns None when config not found."""
        mock_table.get_item.return_value = {}

        tickers = service.get_ticker_filters("user-123", "nonexistent")

        assert tickers is None

    def test_validate_user_access_has_access(
        self, service, mock_table, sample_config_item
    ):
        """Test validate_user_access returns True and tickers when valid."""
        mock_table.get_item.return_value = {"Item": sample_config_item}

        has_access, tickers = service.validate_user_access("user-123", "config-456")

        assert has_access is True
        assert tickers == ["AAPL", "MSFT"]

    def test_validate_user_access_no_access(self, service, mock_table):
        """Test validate_user_access returns False when no access."""
        mock_table.get_item.return_value = {}

        has_access, tickers = service.validate_user_access("user-123", "nonexistent")

        assert has_access is False
        assert tickers is None


class TestConfigLookupServiceInit:
    """Tests for ConfigLookupService initialization."""

    def test_default_table_name_from_env(self):
        """Test table name defaults to DATABASE_TABLE env var."""
        with patch.dict("os.environ", {"DATABASE_TABLE": "my-custom-table"}):
            with patch("src.lambdas.sse_streaming.config.boto3") as mock_boto3:
                mock_resource = MagicMock()
                mock_table = MagicMock()
                mock_table.get_item.return_value = {}
                mock_resource.Table.return_value = mock_table
                mock_boto3.resource.return_value = mock_resource

                service = ConfigLookupService()
                # Trigger lazy initialization by calling a method
                service.get_configuration("test-user", "test-config")

                mock_resource.Table.assert_called_once_with("my-custom-table")

    def test_explicit_table_name_overrides_env(self):
        """Test explicit table name overrides environment variable."""
        with patch.dict("os.environ", {"DATABASE_TABLE": "env-table"}):
            with patch("src.lambdas.sse_streaming.config.boto3") as mock_boto3:
                mock_resource = MagicMock()
                mock_table = MagicMock()
                mock_table.get_item.return_value = {}
                mock_resource.Table.return_value = mock_table
                mock_boto3.resource.return_value = mock_resource

                service = ConfigLookupService(table_name="explicit-table")
                # Trigger lazy initialization by calling a method
                service.get_configuration("test-user", "test-config")

                mock_resource.Table.assert_called_once_with("explicit-table")
