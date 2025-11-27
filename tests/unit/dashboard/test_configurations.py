"""Unit tests for configuration endpoints (T049-T053)."""

import uuid
from datetime import UTC, datetime
from unittest.mock import MagicMock

from src.lambdas.dashboard.configurations import (
    ConfigurationListResponse,
    ConfigurationResponse,
    ErrorResponse,
    create_configuration,
    delete_configuration,
    get_configuration,
    list_configurations,
    update_configuration,
)
from src.lambdas.shared.models.configuration import (
    ConfigurationCreate,
    ConfigurationUpdate,
)


class TestCreateConfiguration:
    """Tests for create_configuration function."""

    def test_creates_configuration_with_valid_request(self):
        """Should create configuration with valid request."""
        mock_table = MagicMock()
        mock_table.query.return_value = {"Count": 0}
        user_id = str(uuid.uuid4())

        request = ConfigurationCreate(
            name="Tech Giants",
            tickers=["AAPL", "MSFT"],
            timeframe_days=30,
        )

        response = create_configuration(mock_table, user_id, request)

        assert isinstance(response, ConfigurationResponse)
        assert response.name == "Tech Giants"
        assert len(response.tickers) == 2
        mock_table.put_item.assert_called_once()

    def test_returns_error_for_max_configurations(self):
        """Should return error when max configurations reached."""
        mock_table = MagicMock()
        mock_table.query.return_value = {"Count": 2}
        user_id = str(uuid.uuid4())

        request = ConfigurationCreate(
            name="New Config",
            tickers=["AAPL"],
        )

        response = create_configuration(mock_table, user_id, request)

        assert isinstance(response, ErrorResponse)
        assert response.error.code == "CONFLICT"

    def test_returns_error_for_invalid_ticker(self):
        """Should return error for invalid ticker symbol."""
        mock_table = MagicMock()
        mock_table.query.return_value = {"Count": 0}
        user_id = str(uuid.uuid4())

        # Mock ticker cache that rejects invalid symbols
        mock_cache = MagicMock()
        mock_cache.validate.return_value = {"status": "invalid"}

        request = ConfigurationCreate(
            name="Invalid",
            tickers=["INVALID123"],
        )

        response = create_configuration(
            mock_table, user_id, request, ticker_cache=mock_cache
        )

        assert isinstance(response, ErrorResponse)
        assert response.error.code == "INVALID_TICKER"

    def test_creates_valid_uuid_for_config_id(self):
        """Should create valid UUID for config_id."""
        mock_table = MagicMock()
        mock_table.query.return_value = {"Count": 0}
        user_id = str(uuid.uuid4())

        request = ConfigurationCreate(name="Test", tickers=["AAPL"])

        response = create_configuration(mock_table, user_id, request)

        # Should not raise
        uuid.UUID(response.config_id)

    def test_stores_correct_dynamodb_keys(self):
        """Should store correct PK/SK in DynamoDB."""
        mock_table = MagicMock()
        mock_table.query.return_value = {"Count": 0}
        user_id = str(uuid.uuid4())

        request = ConfigurationCreate(name="Test", tickers=["AAPL"])

        create_configuration(mock_table, user_id, request)

        call_args = mock_table.put_item.call_args
        item = call_args.kwargs["Item"]

        assert item["PK"] == f"USER#{user_id}"
        assert item["SK"].startswith("CONFIG#")


class TestListConfigurations:
    """Tests for list_configurations function."""

    def test_returns_empty_list_for_no_configs(self):
        """Should return empty list when user has no configurations."""
        mock_table = MagicMock()
        mock_table.query.return_value = {"Items": []}
        user_id = str(uuid.uuid4())

        response = list_configurations(mock_table, user_id)

        assert isinstance(response, ConfigurationListResponse)
        assert len(response.configurations) == 0
        assert response.max_allowed == 2

    def test_returns_active_configurations(self):
        """Should return only active configurations."""
        mock_table = MagicMock()
        now = datetime.now(UTC)
        config_id = str(uuid.uuid4())
        user_id = str(uuid.uuid4())

        mock_table.query.return_value = {
            "Items": [
                {
                    "config_id": config_id,
                    "user_id": user_id,
                    "name": "Active Config",
                    "tickers": [
                        {
                            "symbol": "AAPL",
                            "name": "Apple",
                            "exchange": "NASDAQ",
                            "added_at": now.isoformat(),
                        }
                    ],
                    "timeframe_days": 30,
                    "include_extended_hours": False,
                    "atr_period": 14,
                    "created_at": now.isoformat(),
                    "updated_at": now.isoformat(),
                    "is_active": True,
                }
            ]
        }

        response = list_configurations(mock_table, user_id)

        assert len(response.configurations) == 1
        assert response.configurations[0].name == "Active Config"

    def test_excludes_inactive_configurations(self):
        """Should exclude inactive (deleted) configurations."""
        mock_table = MagicMock()
        now = datetime.now(UTC)
        user_id = str(uuid.uuid4())

        mock_table.query.return_value = {
            "Items": [
                {
                    "config_id": str(uuid.uuid4()),
                    "user_id": user_id,
                    "name": "Deleted Config",
                    "tickers": [],
                    "timeframe_days": 30,
                    "include_extended_hours": False,
                    "atr_period": 14,
                    "created_at": now.isoformat(),
                    "updated_at": now.isoformat(),
                    "is_active": False,
                }
            ]
        }

        response = list_configurations(mock_table, user_id)

        assert len(response.configurations) == 0


class TestGetConfiguration:
    """Tests for get_configuration function."""

    def test_returns_none_for_nonexistent(self):
        """Should return None for nonexistent configuration."""
        mock_table = MagicMock()
        mock_table.get_item.return_value = {}

        result = get_configuration(mock_table, str(uuid.uuid4()), str(uuid.uuid4()))

        assert result is None

    def test_returns_none_for_inactive(self):
        """Should return None for inactive configuration."""
        mock_table = MagicMock()
        now = datetime.now(UTC)

        mock_table.get_item.return_value = {
            "Item": {
                "config_id": str(uuid.uuid4()),
                "user_id": str(uuid.uuid4()),
                "name": "Deleted",
                "tickers": [],
                "created_at": now.isoformat(),
                "updated_at": now.isoformat(),
                "is_active": False,
            }
        }

        result = get_configuration(mock_table, str(uuid.uuid4()), str(uuid.uuid4()))

        assert result is None

    def test_returns_configuration_for_valid(self):
        """Should return configuration for valid request."""
        mock_table = MagicMock()
        now = datetime.now(UTC)
        config_id = str(uuid.uuid4())
        user_id = str(uuid.uuid4())

        mock_table.get_item.return_value = {
            "Item": {
                "config_id": config_id,
                "user_id": user_id,
                "name": "My Config",
                "tickers": [
                    {
                        "symbol": "AAPL",
                        "name": "Apple",
                        "exchange": "NASDAQ",
                        "added_at": now.isoformat(),
                    }
                ],
                "timeframe_days": 14,
                "include_extended_hours": False,
                "atr_period": 14,
                "created_at": now.isoformat(),
                "updated_at": now.isoformat(),
                "is_active": True,
            }
        }

        result = get_configuration(mock_table, user_id, config_id)

        assert result is not None
        assert result.config_id == config_id
        assert result.name == "My Config"


class TestUpdateConfiguration:
    """Tests for update_configuration function."""

    def test_returns_none_for_nonexistent(self):
        """Should return None for nonexistent configuration."""
        mock_table = MagicMock()
        mock_table.get_item.return_value = {}

        result = update_configuration(
            mock_table,
            str(uuid.uuid4()),
            str(uuid.uuid4()),
            ConfigurationUpdate(name="Updated"),
        )

        assert result is None

    def test_updates_name_field(self):
        """Should update name field."""
        mock_table = MagicMock()
        now = datetime.now(UTC)
        config_id = str(uuid.uuid4())
        user_id = str(uuid.uuid4())

        # First call for get_configuration in update
        # Second call for get_configuration to return updated
        mock_table.get_item.return_value = {
            "Item": {
                "config_id": config_id,
                "user_id": user_id,
                "name": "Original",
                "tickers": [
                    {
                        "symbol": "AAPL",
                        "name": "Apple",
                        "exchange": "NASDAQ",
                        "added_at": now.isoformat(),
                    }
                ],
                "timeframe_days": 30,
                "include_extended_hours": False,
                "atr_period": 14,
                "created_at": now.isoformat(),
                "updated_at": now.isoformat(),
                "is_active": True,
            }
        }

        update_configuration(
            mock_table,
            user_id,
            config_id,
            ConfigurationUpdate(name="Updated Name"),
        )

        mock_table.update_item.assert_called_once()
        call_args = mock_table.update_item.call_args
        assert ":name" in call_args.kwargs["ExpressionAttributeValues"]

    def test_returns_error_for_invalid_ticker(self):
        """Should return error for invalid ticker in update."""
        mock_table = MagicMock()
        now = datetime.now(UTC)
        config_id = str(uuid.uuid4())
        user_id = str(uuid.uuid4())

        mock_table.get_item.return_value = {
            "Item": {
                "config_id": config_id,
                "user_id": user_id,
                "name": "Config",
                "tickers": [],
                "timeframe_days": 30,
                "include_extended_hours": False,
                "atr_period": 14,
                "created_at": now.isoformat(),
                "updated_at": now.isoformat(),
                "is_active": True,
            }
        }

        mock_cache = MagicMock()
        mock_cache.validate.return_value = {"status": "invalid"}

        result = update_configuration(
            mock_table,
            user_id,
            config_id,
            ConfigurationUpdate(tickers=["INVALID"]),
            ticker_cache=mock_cache,
        )

        assert isinstance(result, ErrorResponse)
        assert result.error.code == "INVALID_TICKER"


class TestDeleteConfiguration:
    """Tests for delete_configuration function."""

    def test_returns_false_for_nonexistent(self):
        """Should return False for nonexistent configuration."""
        mock_table = MagicMock()
        mock_table.get_item.return_value = {}

        result = delete_configuration(mock_table, str(uuid.uuid4()), str(uuid.uuid4()))

        assert result is False

    def test_soft_deletes_configuration(self):
        """Should soft delete by setting is_active=False."""
        mock_table = MagicMock()
        now = datetime.now(UTC)
        config_id = str(uuid.uuid4())
        user_id = str(uuid.uuid4())

        mock_table.get_item.return_value = {
            "Item": {
                "config_id": config_id,
                "user_id": user_id,
                "name": "To Delete",
                "tickers": [],
                "timeframe_days": 30,
                "include_extended_hours": False,
                "atr_period": 14,
                "created_at": now.isoformat(),
                "updated_at": now.isoformat(),
                "is_active": True,
            }
        }

        result = delete_configuration(mock_table, user_id, config_id)

        assert result is True
        mock_table.update_item.assert_called_once()
        call_args = mock_table.update_item.call_args
        assert call_args.kwargs["ExpressionAttributeValues"][":inactive"] is False
