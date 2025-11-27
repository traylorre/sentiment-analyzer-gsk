"""Integration tests for config switching (T116 - User Story 3).

Tests the complete dual-configuration workflow:
1. Create Config A (5 tech tickers, 30 days)
2. Create Config B (5 EV tickers, 14 days)
3. Verify both appear in configuration list
4. Verify data isolation between configs
5. Verify switching returns correct data
"""

import uuid
from unittest.mock import MagicMock

import pytest

from src.lambdas.dashboard.configurations import (
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


@pytest.fixture
def dynamodb_table():
    """Create mock DynamoDB table with realistic behavior."""
    table = MagicMock()

    # Storage for configurations
    storage: dict[str, dict] = {}

    def put_item(**kwargs):
        item = kwargs["Item"]
        pk = item["PK"]
        sk = item["SK"]
        key = f"{pk}#{sk}"
        storage[key] = item
        return {}

    def get_item(**kwargs):
        pk = kwargs["Key"]["PK"]
        sk = kwargs["Key"]["SK"]
        key = f"{pk}#{sk}"
        if key in storage:
            return {"Item": storage[key]}
        return {}

    def query(**kwargs):
        # Handle Key condition expressions
        key_cond = kwargs.get("KeyConditionExpression")
        filter_expr = kwargs.get("FilterExpression")

        items = []
        if key_cond is not None:
            # Check all items in storage for config items
            for stored_item in storage.values():
                if "USER#" in stored_item.get(
                    "PK", ""
                ) and "CONFIG#" in stored_item.get("SK", ""):
                    # Apply filter if present
                    if filter_expr is not None:
                        if stored_item.get("is_active", True):
                            items.append(stored_item)
                    else:
                        items.append(stored_item)

        # Remove duplicates
        seen = set()
        unique_items = []
        for item in items:
            item_key = f"{item['PK']}#{item['SK']}"
            if item_key not in seen:
                seen.add(item_key)
                unique_items.append(item)

        # For count queries
        if kwargs.get("Select") == "COUNT":
            count = sum(
                1
                for item in storage.values()
                if "is_active" in item and item.get("is_active", True)
            )
            return {"Count": count}

        return {"Items": unique_items}

    def update_item(**kwargs):
        pk = kwargs["Key"]["PK"]
        sk = kwargs["Key"]["SK"]
        key = f"{pk}#{sk}"

        if key in storage:
            item = storage[key]
            attr_values = kwargs.get("ExpressionAttributeValues", {})

            # Handle attribute updates based on expression values
            if ":inactive" in attr_values:
                item["is_active"] = attr_values[":inactive"]
            if ":updated" in attr_values:
                item["updated_at"] = attr_values[":updated"]
            if ":name" in attr_values:
                item["name"] = attr_values[":name"]
            if ":timeframe" in attr_values:
                item["timeframe_days"] = attr_values[":timeframe"]
            if ":tickers" in attr_values:
                item["tickers"] = attr_values[":tickers"]
            if ":extended" in attr_values:
                item["include_extended_hours"] = attr_values[":extended"]

            storage[key] = item

        return {}

    table.put_item.side_effect = put_item
    table.get_item.side_effect = get_item
    table.query.side_effect = query
    table.update_item.side_effect = update_item

    return table


@pytest.fixture
def user_id():
    """Generate a user ID for testing."""
    return str(uuid.uuid4())


def _make_request(
    name: str,
    tickers: list[str],
    timeframe_days: int = 30,
    include_extended_hours: bool = False,
) -> ConfigurationCreate:
    """Helper to create configuration request."""
    return ConfigurationCreate(
        name=name,
        tickers=tickers,
        timeframe_days=timeframe_days,
        include_extended_hours=include_extended_hours,
    )


class TestDualConfigWorkflow:
    """Tests for complete dual-config workflow."""

    def test_create_config_a_tech_tickers(self, dynamodb_table, user_id: str):
        """Create Config A with 5 tech tickers and 30-day timeframe."""
        request = _make_request(
            name="Tech Giants",
            tickers=["AAPL", "MSFT", "GOOGL", "NVDA", "META"],
            timeframe_days=30,
        )
        response = create_configuration(
            table=dynamodb_table,
            user_id=user_id,
            request=request,
        )

        assert isinstance(response, ConfigurationResponse)
        assert response.name == "Tech Giants"
        assert len(response.tickers) == 5
        assert response.timeframe_days == 30

    def test_create_config_b_ev_tickers(self, dynamodb_table, user_id: str):
        """Create Config B with 5 EV tickers and 14-day timeframe."""
        # Create Config A first
        request_a = _make_request(
            name="Tech Giants",
            tickers=["AAPL", "MSFT", "GOOGL", "NVDA", "META"],
            timeframe_days=30,
        )
        create_configuration(table=dynamodb_table, user_id=user_id, request=request_a)

        # Create Config B
        request_b = _make_request(
            name="EV Sector",
            tickers=["TSLA", "RIVN", "LCID", "NIO", "XPEV"],
            timeframe_days=14,
        )
        response = create_configuration(
            table=dynamodb_table, user_id=user_id, request=request_b
        )

        assert isinstance(response, ConfigurationResponse)
        assert response.name == "EV Sector"
        assert len(response.tickers) == 5
        assert response.timeframe_days == 14

    def test_both_configs_appear_in_list(self, dynamodb_table, user_id: str):
        """Both configurations appear in configuration list."""
        # Create both configs
        request_a = _make_request(
            name="Tech Giants",
            tickers=["AAPL", "MSFT", "GOOGL", "NVDA", "META"],
            timeframe_days=30,
        )
        request_b = _make_request(
            name="EV Sector",
            tickers=["TSLA", "RIVN", "LCID", "NIO", "XPEV"],
            timeframe_days=14,
        )
        create_configuration(table=dynamodb_table, user_id=user_id, request=request_a)
        create_configuration(table=dynamodb_table, user_id=user_id, request=request_b)

        # List configurations
        list_response = list_configurations(table=dynamodb_table, user_id=user_id)

        assert len(list_response.configurations) == 2
        names = {c.name for c in list_response.configurations}
        assert names == {"Tech Giants", "EV Sector"}


class TestConfigDataIsolation:
    """Tests for data isolation between configurations."""

    def test_configs_have_different_tickers(self, dynamodb_table, user_id: str):
        """Each config maintains its own ticker set."""
        request_a = _make_request(name="Tech Giants", tickers=["AAPL", "MSFT", "GOOGL"])
        request_b = _make_request(name="EV Sector", tickers=["TSLA", "RIVN", "LCID"])

        config_a = create_configuration(
            table=dynamodb_table, user_id=user_id, request=request_a
        )
        config_b = create_configuration(
            table=dynamodb_table, user_id=user_id, request=request_b
        )

        # Get each config
        retrieved_a = get_configuration(
            table=dynamodb_table, user_id=user_id, config_id=config_a.config_id
        )
        retrieved_b = get_configuration(
            table=dynamodb_table, user_id=user_id, config_id=config_b.config_id
        )

        # Verify ticker isolation
        a_symbols = {t.symbol for t in retrieved_a.tickers}
        b_symbols = {t.symbol for t in retrieved_b.tickers}

        assert a_symbols == {"AAPL", "MSFT", "GOOGL"}
        assert b_symbols == {"TSLA", "RIVN", "LCID"}
        assert a_symbols.isdisjoint(b_symbols)  # No overlap

    def test_configs_have_different_timeframes(self, dynamodb_table, user_id: str):
        """Each config maintains its own timeframe."""
        request_a = _make_request(name="Long Term", tickers=["SPY"], timeframe_days=90)
        request_b = _make_request(name="Short Term", tickers=["QQQ"], timeframe_days=7)

        config_a = create_configuration(
            table=dynamodb_table, user_id=user_id, request=request_a
        )
        config_b = create_configuration(
            table=dynamodb_table, user_id=user_id, request=request_b
        )

        # Get each config
        retrieved_a = get_configuration(
            table=dynamodb_table, user_id=user_id, config_id=config_a.config_id
        )
        retrieved_b = get_configuration(
            table=dynamodb_table, user_id=user_id, config_id=config_b.config_id
        )

        assert retrieved_a.timeframe_days == 90
        assert retrieved_b.timeframe_days == 7

    def test_update_config_a_doesnt_affect_config_b(self, dynamodb_table, user_id: str):
        """Updating Config A doesn't affect Config B."""
        request_a = _make_request(name="Config A", tickers=["AAPL"], timeframe_days=30)
        request_b = _make_request(name="Config B", tickers=["MSFT"], timeframe_days=14)

        config_a = create_configuration(
            table=dynamodb_table, user_id=user_id, request=request_a
        )
        config_b = create_configuration(
            table=dynamodb_table, user_id=user_id, request=request_b
        )

        # Update Config A
        update_req = ConfigurationUpdate(name="Updated Config A", timeframe_days=60)
        update_configuration(
            table=dynamodb_table,
            user_id=user_id,
            config_id=config_a.config_id,
            request=update_req,
        )

        # Verify Config B unchanged
        retrieved_b = get_configuration(
            table=dynamodb_table, user_id=user_id, config_id=config_b.config_id
        )

        assert retrieved_b.name == "Config B"
        assert retrieved_b.timeframe_days == 14


class TestConfigSwitching:
    """Tests for switching between configurations."""

    def test_switch_returns_correct_config_data(self, dynamodb_table, user_id: str):
        """Switching configs returns correct data for each."""
        request_a = _make_request(
            name="Tech Giants",
            tickers=["AAPL", "MSFT", "GOOGL", "NVDA", "META"],
            timeframe_days=30,
        )
        request_b = _make_request(
            name="EV Sector",
            tickers=["TSLA", "RIVN", "LCID", "NIO", "XPEV"],
            timeframe_days=14,
        )

        config_a = create_configuration(
            table=dynamodb_table, user_id=user_id, request=request_a
        )
        config_b = create_configuration(
            table=dynamodb_table, user_id=user_id, request=request_b
        )

        # "Switch" to Config A (get its data)
        data_a = get_configuration(
            table=dynamodb_table, user_id=user_id, config_id=config_a.config_id
        )
        assert data_a.name == "Tech Giants"
        assert data_a.timeframe_days == 30
        assert {t.symbol for t in data_a.tickers} == {
            "AAPL",
            "MSFT",
            "GOOGL",
            "NVDA",
            "META",
        }

        # "Switch" to Config B (get its data)
        data_b = get_configuration(
            table=dynamodb_table, user_id=user_id, config_id=config_b.config_id
        )
        assert data_b.name == "EV Sector"
        assert data_b.timeframe_days == 14
        assert {t.symbol for t in data_b.tickers} == {
            "TSLA",
            "RIVN",
            "LCID",
            "NIO",
            "XPEV",
        }

    def test_switch_back_preserves_data(self, dynamodb_table, user_id: str):
        """Switching back to previous config preserves its data."""
        request_a = _make_request(name="Config A", tickers=["AAPL"], timeframe_days=30)
        request_b = _make_request(name="Config B", tickers=["MSFT"], timeframe_days=14)

        config_a = create_configuration(
            table=dynamodb_table, user_id=user_id, request=request_a
        )
        config_b = create_configuration(
            table=dynamodb_table, user_id=user_id, request=request_b
        )

        # Get A
        data_a1 = get_configuration(
            table=dynamodb_table, user_id=user_id, config_id=config_a.config_id
        )

        # Switch to B
        get_configuration(
            table=dynamodb_table, user_id=user_id, config_id=config_b.config_id
        )

        # Switch back to A
        data_a2 = get_configuration(
            table=dynamodb_table, user_id=user_id, config_id=config_a.config_id
        )

        # Data should be identical
        assert data_a1.name == data_a2.name
        assert data_a1.timeframe_days == data_a2.timeframe_days


class TestMaxConfigLimit:
    """Tests for maximum 2 configuration limit."""

    def test_third_config_returns_error(self, dynamodb_table, user_id: str):
        """Creating third configuration returns error response."""
        request_1 = _make_request(name="Config 1", tickers=["AAPL"])
        request_2 = _make_request(name="Config 2", tickers=["MSFT"])
        request_3 = _make_request(name="Config 3", tickers=["GOOGL"])

        create_configuration(table=dynamodb_table, user_id=user_id, request=request_1)
        create_configuration(table=dynamodb_table, user_id=user_id, request=request_2)

        # Third should return error
        result = create_configuration(
            table=dynamodb_table, user_id=user_id, request=request_3
        )

        assert isinstance(result, ErrorResponse)
        assert result.error.code == "CONFLICT"

    def test_delete_allows_new_creation(self, dynamodb_table, user_id: str):
        """Deleting a config allows creating a new one."""
        request_1 = _make_request(name="Config 1", tickers=["AAPL"])
        request_2 = _make_request(name="Config 2", tickers=["MSFT"])

        config_1 = create_configuration(
            table=dynamodb_table, user_id=user_id, request=request_1
        )
        create_configuration(table=dynamodb_table, user_id=user_id, request=request_2)

        # Delete first config
        delete_configuration(
            table=dynamodb_table,
            user_id=user_id,
            config_id=config_1.config_id,
        )

        # Should now be able to create new config
        request_3 = _make_request(name="Config 3", tickers=["GOOGL"])
        config_3 = create_configuration(
            table=dynamodb_table, user_id=user_id, request=request_3
        )

        assert isinstance(config_3, ConfigurationResponse)
        assert config_3.name == "Config 3"
