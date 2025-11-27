"""Contract tests for multiple configurations (T115 - User Story 3).

Validates dual-configuration support per dashboard-api.md:
- Users can create up to 2 configurations
- Third configuration creation returns 409 Conflict
- Configuration list shows max_allowed = 2
- Each configuration has independent settings
"""

import uuid
from datetime import UTC, datetime
from typing import Any

import pytest
from pydantic import BaseModel, Field, field_validator

# --- Response Schema Definitions ---


class TickerInfo(BaseModel):
    """Ticker information in configuration response."""

    symbol: str
    name: str
    exchange: str


class ConfigurationResponse(BaseModel):
    """Response schema for single configuration."""

    config_id: str
    name: str
    tickers: list[TickerInfo | str]
    timeframe_days: int = Field(..., ge=1, le=365)
    include_extended_hours: bool
    created_at: str
    updated_at: str | None = None

    @field_validator("config_id")
    @classmethod
    def validate_uuid(cls, v: str) -> str:
        """Validate config_id is valid UUID."""
        uuid.UUID(v)
        return v


class ConfigurationListResponse(BaseModel):
    """Response schema for GET /api/v2/configurations."""

    configurations: list[dict[str, Any]]
    max_allowed: int = Field(..., ge=1)


class MultiConfigConflictResponse(BaseModel):
    """Response when max configs exceeded (409 Conflict)."""

    error: str
    message: str
    max_allowed: int
    current_count: int


# --- Mock API for Testing ---


class MockMultiConfigAPI:
    """Mock API that enforces dual-config limit."""

    def __init__(self):
        self.configs: dict[str, dict[str, Any]] = {}
        self.max_allowed = 2
        self.user_config_counts: dict[str, int] = {}

    def create_configuration(
        self,
        user_id: str,
        name: str,
        tickers: list[str],
        timeframe_days: int = 30,
        include_extended_hours: bool = False,
    ) -> tuple[int, dict[str, Any]]:
        """Create a configuration, respecting max limit."""
        current_count = self.user_config_counts.get(user_id, 0)

        if current_count >= self.max_allowed:
            return 409, {
                "error": "max_configurations_exceeded",
                "message": f"Maximum of {self.max_allowed} configurations allowed",
                "max_allowed": self.max_allowed,
                "current_count": current_count,
            }

        config_id = str(uuid.uuid4())
        now = datetime.now(UTC).isoformat()

        config = {
            "config_id": config_id,
            "user_id": user_id,
            "name": name,
            "tickers": tickers,
            "timeframe_days": timeframe_days,
            "include_extended_hours": include_extended_hours,
            "created_at": now,
            "updated_at": now,
        }

        self.configs[config_id] = config
        self.user_config_counts[user_id] = current_count + 1

        return 201, config

    def list_configurations(self, user_id: str) -> tuple[int, dict[str, Any]]:
        """List all configurations for a user."""
        user_configs = [c for c in self.configs.values() if c["user_id"] == user_id]
        return 200, {
            "configurations": user_configs,
            "max_allowed": self.max_allowed,
        }

    def delete_configuration(self, user_id: str, config_id: str) -> tuple[int, dict]:
        """Delete a configuration."""
        if config_id not in self.configs:
            return 404, {"error": "not_found", "message": "Configuration not found"}

        config = self.configs[config_id]
        if config["user_id"] != user_id:
            return 403, {"error": "forbidden", "message": "Access denied"}

        del self.configs[config_id]
        self.user_config_counts[user_id] = max(
            0, self.user_config_counts.get(user_id, 1) - 1
        )

        return 204, {}


@pytest.fixture
def mock_api():
    """Create fresh mock API for each test."""
    return MockMultiConfigAPI()


@pytest.fixture
def user_id():
    """Generate a user ID for testing."""
    return str(uuid.uuid4())


# --- Contract Tests ---


class TestMultiConfigLimit:
    """Tests for max 2 configuration limit."""

    def test_first_config_succeeds(self, mock_api: MockMultiConfigAPI, user_id: str):
        """First configuration creation succeeds."""
        status, response = mock_api.create_configuration(
            user_id=user_id,
            name="Tech Giants",
            tickers=["AAPL", "MSFT", "GOOGL"],
        )

        assert status == 201
        config = ConfigurationResponse(**response)
        assert config.name == "Tech Giants"
        assert config.timeframe_days == 30  # default

    def test_second_config_succeeds(self, mock_api: MockMultiConfigAPI, user_id: str):
        """Second configuration creation succeeds."""
        # Create first
        mock_api.create_configuration(
            user_id=user_id,
            name="Tech Giants",
            tickers=["AAPL", "MSFT", "GOOGL"],
        )

        # Create second
        status, response = mock_api.create_configuration(
            user_id=user_id,
            name="EV Sector",
            tickers=["TSLA", "RIVN", "LCID"],
            timeframe_days=14,
        )

        assert status == 201
        config = ConfigurationResponse(**response)
        assert config.name == "EV Sector"
        assert config.timeframe_days == 14

    def test_third_config_returns_409(self, mock_api: MockMultiConfigAPI, user_id: str):
        """Third configuration creation returns 409 Conflict."""
        # Create first and second
        mock_api.create_configuration(
            user_id=user_id,
            name="Tech Giants",
            tickers=["AAPL", "MSFT", "GOOGL"],
        )
        mock_api.create_configuration(
            user_id=user_id,
            name="EV Sector",
            tickers=["TSLA", "RIVN", "LCID"],
        )

        # Third should fail
        status, response = mock_api.create_configuration(
            user_id=user_id,
            name="Healthcare",
            tickers=["JNJ", "PFE", "UNH"],
        )

        assert status == 409
        conflict = MultiConfigConflictResponse(**response)
        assert conflict.error == "max_configurations_exceeded"
        assert conflict.max_allowed == 2
        assert conflict.current_count == 2

    def test_error_message_includes_limit(
        self, mock_api: MockMultiConfigAPI, user_id: str
    ):
        """Error message clearly indicates max 2 limit."""
        # Fill to max
        mock_api.create_configuration(
            user_id=user_id, name="Config 1", tickers=["AAPL"]
        )
        mock_api.create_configuration(
            user_id=user_id, name="Config 2", tickers=["MSFT"]
        )

        # Try third
        status, response = mock_api.create_configuration(
            user_id=user_id, name="Config 3", tickers=["GOOGL"]
        )

        assert status == 409
        assert "2" in response["message"]
        assert "maximum" in response["message"].lower()


class TestConfigListMaxAllowed:
    """Tests for max_allowed field in list response."""

    def test_list_shows_max_allowed(self, mock_api: MockMultiConfigAPI, user_id: str):
        """Configuration list includes max_allowed field."""
        mock_api.create_configuration(
            user_id=user_id, name="Test Config", tickers=["AAPL"]
        )

        status, response = mock_api.list_configurations(user_id)

        assert status == 200
        list_response = ConfigurationListResponse(**response)
        assert list_response.max_allowed == 2

    def test_list_empty_shows_max_allowed(
        self, mock_api: MockMultiConfigAPI, user_id: str
    ):
        """Empty configuration list still shows max_allowed."""
        status, response = mock_api.list_configurations(user_id)

        assert status == 200
        assert response["max_allowed"] == 2
        assert response["configurations"] == []

    def test_list_with_two_configs(self, mock_api: MockMultiConfigAPI, user_id: str):
        """List with 2 configs shows both."""
        mock_api.create_configuration(
            user_id=user_id,
            name="Tech Giants",
            tickers=["AAPL", "MSFT"],
        )
        mock_api.create_configuration(
            user_id=user_id,
            name="EV Sector",
            tickers=["TSLA", "RIVN"],
        )

        status, response = mock_api.list_configurations(user_id)

        assert status == 200
        assert len(response["configurations"]) == 2
        assert response["max_allowed"] == 2

        names = {c["name"] for c in response["configurations"]}
        assert names == {"Tech Giants", "EV Sector"}


class TestIndependentConfigSettings:
    """Tests for independent configuration settings."""

    def test_configs_have_independent_tickers(
        self, mock_api: MockMultiConfigAPI, user_id: str
    ):
        """Each configuration has its own ticker set."""
        mock_api.create_configuration(
            user_id=user_id,
            name="Tech Giants",
            tickers=["AAPL", "MSFT", "GOOGL", "NVDA", "META"],
        )
        mock_api.create_configuration(
            user_id=user_id,
            name="EV Sector",
            tickers=["TSLA", "RIVN", "LCID", "NIO", "XPEV"],
        )

        _, response = mock_api.list_configurations(user_id)

        configs = response["configurations"]
        tech_config = next(c for c in configs if c["name"] == "Tech Giants")
        ev_config = next(c for c in configs if c["name"] == "EV Sector")

        assert tech_config["tickers"] == ["AAPL", "MSFT", "GOOGL", "NVDA", "META"]
        assert ev_config["tickers"] == ["TSLA", "RIVN", "LCID", "NIO", "XPEV"]

    def test_configs_have_independent_timeframes(
        self, mock_api: MockMultiConfigAPI, user_id: str
    ):
        """Each configuration has its own timeframe."""
        mock_api.create_configuration(
            user_id=user_id,
            name="Long Term",
            tickers=["SPY"],
            timeframe_days=90,
        )
        mock_api.create_configuration(
            user_id=user_id,
            name="Short Term",
            tickers=["QQQ"],
            timeframe_days=7,
        )

        _, response = mock_api.list_configurations(user_id)

        configs = response["configurations"]
        long_config = next(c for c in configs if c["name"] == "Long Term")
        short_config = next(c for c in configs if c["name"] == "Short Term")

        assert long_config["timeframe_days"] == 90
        assert short_config["timeframe_days"] == 7

    def test_configs_have_independent_extended_hours(
        self, mock_api: MockMultiConfigAPI, user_id: str
    ):
        """Each configuration has its own extended hours setting."""
        mock_api.create_configuration(
            user_id=user_id,
            name="Regular Hours",
            tickers=["AAPL"],
            include_extended_hours=False,
        )
        mock_api.create_configuration(
            user_id=user_id,
            name="Extended Hours",
            tickers=["TSLA"],
            include_extended_hours=True,
        )

        _, response = mock_api.list_configurations(user_id)

        configs = response["configurations"]
        regular_config = next(c for c in configs if c["name"] == "Regular Hours")
        extended_config = next(c for c in configs if c["name"] == "Extended Hours")

        assert regular_config["include_extended_hours"] is False
        assert extended_config["include_extended_hours"] is True


class TestDeleteAndRecreate:
    """Tests for deleting config and creating new one."""

    def test_delete_allows_new_creation(
        self, mock_api: MockMultiConfigAPI, user_id: str
    ):
        """Deleting a config allows creating a new one."""
        # Create two configs
        status1, config1 = mock_api.create_configuration(
            user_id=user_id, name="Config 1", tickers=["AAPL"]
        )
        mock_api.create_configuration(
            user_id=user_id, name="Config 2", tickers=["MSFT"]
        )

        # Delete first
        delete_status, _ = mock_api.delete_configuration(user_id, config1["config_id"])
        assert delete_status == 204

        # Should now be able to create new config
        status3, config3 = mock_api.create_configuration(
            user_id=user_id, name="Config 3", tickers=["GOOGL"]
        )
        assert status3 == 201
        assert config3["name"] == "Config 3"

    def test_count_accurate_after_delete(
        self, mock_api: MockMultiConfigAPI, user_id: str
    ):
        """Config count is accurate after deletion."""
        # Create two configs
        _, config1 = mock_api.create_configuration(
            user_id=user_id, name="Config 1", tickers=["AAPL"]
        )
        mock_api.create_configuration(
            user_id=user_id, name="Config 2", tickers=["MSFT"]
        )

        # Verify two configs
        _, list_before = mock_api.list_configurations(user_id)
        assert len(list_before["configurations"]) == 2

        # Delete one
        mock_api.delete_configuration(user_id, config1["config_id"])

        # Verify one config
        _, list_after = mock_api.list_configurations(user_id)
        assert len(list_after["configurations"]) == 1


class TestUserIsolation:
    """Tests for user data isolation."""

    def test_different_users_have_separate_limits(self, mock_api: MockMultiConfigAPI):
        """Each user has their own config limit."""
        user_a = str(uuid.uuid4())
        user_b = str(uuid.uuid4())

        # User A creates 2 configs
        mock_api.create_configuration(user_id=user_a, name="A-1", tickers=["AAPL"])
        mock_api.create_configuration(user_id=user_a, name="A-2", tickers=["MSFT"])

        # User A can't create third
        status_a, _ = mock_api.create_configuration(
            user_id=user_a, name="A-3", tickers=["GOOGL"]
        )
        assert status_a == 409

        # User B can still create configs
        status_b, _ = mock_api.create_configuration(
            user_id=user_b, name="B-1", tickers=["NVDA"]
        )
        assert status_b == 201

    def test_users_only_see_own_configs(self, mock_api: MockMultiConfigAPI):
        """Users only see their own configurations."""
        user_a = str(uuid.uuid4())
        user_b = str(uuid.uuid4())

        mock_api.create_configuration(
            user_id=user_a, name="User A Config", tickers=["AAPL"]
        )
        mock_api.create_configuration(
            user_id=user_b, name="User B Config", tickers=["MSFT"]
        )

        _, list_a = mock_api.list_configurations(user_a)
        _, list_b = mock_api.list_configurations(user_b)

        assert len(list_a["configurations"]) == 1
        assert list_a["configurations"][0]["name"] == "User A Config"

        assert len(list_b["configurations"]) == 1
        assert list_b["configurations"][0]["name"] == "User B Config"
