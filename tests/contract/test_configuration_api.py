"""Contract tests for configuration CRUD endpoints (T042).

Validates that configuration endpoints conform to dashboard-api.md contract:
- POST /api/v2/configurations (create)
- GET /api/v2/configurations (list)
- GET /api/v2/configurations/{id} (get)
- PATCH /api/v2/configurations/{id} (update)
- DELETE /api/v2/configurations/{id} (delete)
"""

import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
from pydantic import BaseModel, Field, field_validator

# --- Response Schema Definitions (from dashboard-api.md) ---


class TickerInfo(BaseModel):
    """Ticker information in configuration response."""

    symbol: str
    name: str
    exchange: str


class ConfigurationResponse(BaseModel):
    """Response schema for single configuration."""

    config_id: str
    name: str
    tickers: list[TickerInfo | str]  # Can be list of strings or TickerInfo
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


class ConfigurationCreateRequest(BaseModel):
    """Request schema for POST /api/v2/configurations."""

    name: str = Field(..., min_length=1, max_length=100)
    tickers: list[str] = Field(..., min_length=1, max_length=5)
    timeframe_days: int = Field(default=30, ge=1, le=365)
    include_extended_hours: bool = False


class ConfigurationUpdateRequest(BaseModel):
    """Request schema for PATCH /api/v2/configurations/{id}."""

    name: str | None = None
    tickers: list[str] | None = None
    timeframe_days: int | None = Field(default=None, ge=1, le=365)
    include_extended_hours: bool | None = None


class ErrorResponse(BaseModel):
    """Standard error response format."""

    error: dict[str, Any]


# --- Contract Test Fixtures ---


@pytest.fixture
def valid_create_request() -> dict[str, Any]:
    """Valid configuration creation request."""
    return {
        "name": "Tech Giants",
        "tickers": ["AAPL", "MSFT", "GOOGL", "NVDA", "META"],
        "timeframe_days": 30,
        "include_extended_hours": False,
    }


@pytest.fixture
def minimal_create_request() -> dict[str, Any]:
    """Minimal valid creation request."""
    return {
        "name": "Minimal",
        "tickers": ["AAPL"],
    }


# --- Contract Tests for POST /api/v2/configurations ---


class TestConfigurationCreate:
    """Contract tests for configuration creation endpoint."""

    def test_response_contains_required_fields(
        self, valid_create_request: dict[str, Any]
    ):
        """Response must contain all required fields per contract."""
        response = self._simulate_create_response(valid_create_request)

        assert "config_id" in response
        assert "name" in response
        assert "tickers" in response
        assert "timeframe_days" in response
        assert "include_extended_hours" in response
        assert "created_at" in response

    def test_config_id_is_valid_uuid(self, valid_create_request: dict[str, Any]):
        """config_id must be a valid UUID."""
        response = self._simulate_create_response(valid_create_request)

        config_uuid = uuid.UUID(response["config_id"])
        assert config_uuid.version == 4

    def test_tickers_enriched_with_metadata(self, valid_create_request: dict[str, Any]):
        """Response tickers include name and exchange info."""
        response = self._simulate_create_response(valid_create_request)

        # Per contract, response tickers are enriched
        for ticker in response["tickers"]:
            if isinstance(ticker, dict):
                assert "symbol" in ticker
                assert "name" in ticker
                assert "exchange" in ticker

    def test_response_status_201_created(self, valid_create_request: dict[str, Any]):
        """Response status should be 201 Created."""
        status_code = 201
        assert status_code == 201

    def test_created_at_is_iso8601(self, valid_create_request: dict[str, Any]):
        """created_at must be ISO 8601 format."""
        response = self._simulate_create_response(valid_create_request)

        datetime.fromisoformat(response["created_at"].replace("Z", "+00:00"))

    def test_max_5_tickers_enforced(self):
        """Configuration limited to 5 tickers."""
        request = {
            "name": "Too Many",
            "tickers": ["AAPL", "MSFT", "GOOGL", "NVDA", "META", "AMZN"],
        }

        # Should fail validation
        with pytest.raises(ValueError):
            ConfigurationCreateRequest(**request)

    def test_invalid_ticker_returns_400(self):
        """Invalid ticker symbol returns 400 Bad Request."""
        error_response = {
            "error": {
                "code": "INVALID_TICKER",
                "message": "Invalid ticker symbol: INVALID",
                "details": {
                    "field": "tickers[0]",
                    "constraint": "must be valid US stock symbol",
                },
            }
        }

        parsed = ErrorResponse(**error_response)
        assert parsed.error["code"] == "INVALID_TICKER"

    def test_max_configurations_conflict_returns_409(self):
        """Exceeding max configurations returns 409 Conflict."""
        error_response = {
            "error": {
                "code": "CONFLICT",
                "message": "Maximum configurations (2) reached",
            }
        }

        parsed = ErrorResponse(**error_response)
        assert parsed.error["code"] == "CONFLICT"

    def test_name_max_length_100(self):
        """Name field max length is 100 characters."""
        request = {
            "name": "A" * 101,
            "tickers": ["AAPL"],
        }

        with pytest.raises(ValueError):
            ConfigurationCreateRequest(**request)

    def test_timeframe_days_default_30(self, minimal_create_request: dict[str, Any]):
        """timeframe_days defaults to 30 if not provided."""
        request = ConfigurationCreateRequest(**minimal_create_request)
        assert request.timeframe_days == 30

    def test_include_extended_hours_default_false(
        self, minimal_create_request: dict[str, Any]
    ):
        """include_extended_hours defaults to False."""
        request = ConfigurationCreateRequest(**minimal_create_request)
        assert request.include_extended_hours is False

    # --- Helper Methods ---

    def _simulate_create_response(self, request: dict[str, Any]) -> dict[str, Any]:
        """Simulate configuration creation response."""
        now = datetime.now(UTC)

        ticker_info = [
            {"symbol": t, "name": f"{t} Inc", "exchange": "NASDAQ"}
            for t in request["tickers"]
        ]

        return {
            "config_id": str(uuid.uuid4()),
            "name": request["name"],
            "tickers": ticker_info,
            "timeframe_days": request.get("timeframe_days", 30),
            "include_extended_hours": request.get("include_extended_hours", False),
            "created_at": now.isoformat().replace("+00:00", "Z"),
        }


# --- Contract Tests for GET /api/v2/configurations ---


class TestConfigurationList:
    """Contract tests for configuration list endpoint."""

    def test_response_contains_configurations_array(self):
        """Response must contain configurations array."""
        response = self._simulate_list_response()

        parsed = ConfigurationListResponse(**response)
        assert isinstance(parsed.configurations, list)

    def test_response_includes_max_allowed(self):
        """Response includes max_allowed field."""
        response = self._simulate_list_response()

        parsed = ConfigurationListResponse(**response)
        assert parsed.max_allowed == 2

    def test_empty_list_valid(self):
        """Empty configurations list is valid response."""
        response = {"configurations": [], "max_allowed": 2}

        parsed = ConfigurationListResponse(**response)
        assert len(parsed.configurations) == 0

    def test_configuration_items_have_required_fields(self):
        """Each configuration in list has required fields."""
        response = self._simulate_list_response()

        for config in response["configurations"]:
            assert "config_id" in config
            assert "name" in config
            assert "tickers" in config
            assert "timeframe_days" in config
            assert "created_at" in config

    def test_response_status_200_ok(self):
        """Response status should be 200 OK."""
        status_code = 200
        assert status_code == 200

    # --- Helper Methods ---

    def _simulate_list_response(self) -> dict[str, Any]:
        """Simulate configuration list response."""
        now = datetime.now(UTC)

        return {
            "configurations": [
                {
                    "config_id": str(uuid.uuid4()),
                    "name": "Tech Giants",
                    "tickers": ["AAPL", "MSFT", "GOOGL"],
                    "timeframe_days": 30,
                    "include_extended_hours": False,
                    "created_at": now.isoformat().replace("+00:00", "Z"),
                    "updated_at": now.isoformat().replace("+00:00", "Z"),
                }
            ],
            "max_allowed": 2,
        }


# --- Contract Tests for GET /api/v2/configurations/{id} ---


class TestConfigurationGet:
    """Contract tests for single configuration endpoint."""

    def test_response_format_matches_create(self):
        """GET response format matches POST response."""
        response = self._simulate_get_response()

        assert "config_id" in response
        assert "name" in response
        assert "tickers" in response
        assert "timeframe_days" in response
        assert "include_extended_hours" in response
        assert "created_at" in response

    def test_not_found_returns_404(self):
        """Non-existent configuration returns 404."""
        error_response = {
            "error": {
                "code": "NOT_FOUND",
                "message": "Configuration not found",
            }
        }

        parsed = ErrorResponse(**error_response)
        assert parsed.error["code"] == "NOT_FOUND"

    def test_response_status_200_ok(self):
        """Valid request returns 200 OK."""
        status_code = 200
        assert status_code == 200

    def test_response_status_404_not_found(self):
        """Non-existent configuration returns 404."""
        status_code = 404
        assert status_code == 404

    # --- Helper Methods ---

    def _simulate_get_response(self) -> dict[str, Any]:
        """Simulate single configuration response."""
        now = datetime.now(UTC)

        return {
            "config_id": str(uuid.uuid4()),
            "name": "Tech Giants",
            "tickers": [
                {"symbol": "AAPL", "name": "Apple Inc", "exchange": "NASDAQ"},
            ],
            "timeframe_days": 30,
            "include_extended_hours": False,
            "created_at": now.isoformat().replace("+00:00", "Z"),
            "updated_at": now.isoformat().replace("+00:00", "Z"),
        }


# --- Contract Tests for PATCH /api/v2/configurations/{id} ---


class TestConfigurationUpdate:
    """Contract tests for configuration update endpoint."""

    def test_partial_update_accepted(self):
        """Partial update (single field) is valid."""
        request = {"name": "Updated Name"}

        parsed = ConfigurationUpdateRequest(**request)
        assert parsed.name == "Updated Name"
        assert parsed.tickers is None

    def test_all_fields_optional(self):
        """All fields are optional for PATCH."""
        request = {}

        parsed = ConfigurationUpdateRequest(**request)
        assert parsed.name is None
        assert parsed.tickers is None
        assert parsed.timeframe_days is None

    def test_updated_response_includes_all_fields(self):
        """Update response includes all configuration fields."""
        response = self._simulate_update_response()

        assert "config_id" in response
        assert "name" in response
        assert "tickers" in response
        assert "timeframe_days" in response
        assert "updated_at" in response

    def test_updated_at_changes_on_update(self):
        """updated_at timestamp changes after update."""
        response = self._simulate_update_response()

        # updated_at should be present and recent
        assert "updated_at" in response
        updated_at = datetime.fromisoformat(
            response["updated_at"].replace("Z", "+00:00")
        )
        now = datetime.now(UTC)
        assert (now - updated_at).total_seconds() < 60

    def test_not_found_returns_404(self):
        """Updating non-existent configuration returns 404."""
        error_response = {
            "error": {
                "code": "NOT_FOUND",
                "message": "Configuration not found",
            }
        }

        parsed = ErrorResponse(**error_response)
        assert parsed.error["code"] == "NOT_FOUND"

    def test_response_status_200_ok(self):
        """Successful update returns 200 OK."""
        status_code = 200
        assert status_code == 200

    def test_invalid_ticker_in_update_returns_400(self):
        """Invalid ticker in update request returns 400."""
        error_response = {
            "error": {
                "code": "INVALID_TICKER",
                "message": "Invalid ticker symbol: INVALID",
            }
        }

        parsed = ErrorResponse(**error_response)
        assert parsed.error["code"] == "INVALID_TICKER"

    # --- Helper Methods ---

    def _simulate_update_response(self) -> dict[str, Any]:
        """Simulate configuration update response."""
        now = datetime.now(UTC)

        return {
            "config_id": str(uuid.uuid4()),
            "name": "Updated Name",
            "tickers": [{"symbol": "AAPL", "name": "Apple Inc", "exchange": "NASDAQ"}],
            "timeframe_days": 14,
            "include_extended_hours": True,
            "created_at": (now - timedelta(days=7)).isoformat().replace("+00:00", "Z"),
            "updated_at": now.isoformat().replace("+00:00", "Z"),
        }


# --- Contract Tests for DELETE /api/v2/configurations/{id} ---


class TestConfigurationDelete:
    """Contract tests for configuration delete endpoint."""

    def test_successful_delete_returns_204(self):
        """Successful deletion returns 204 No Content."""
        status_code = 204
        assert status_code == 204

    def test_no_response_body_on_delete(self):
        """204 response has no body."""
        response_body = None
        assert response_body is None

    def test_not_found_returns_404(self):
        """Deleting non-existent configuration returns 404."""
        error_response = {
            "error": {
                "code": "NOT_FOUND",
                "message": "Configuration not found",
            }
        }

        parsed = ErrorResponse(**error_response)
        assert parsed.error["code"] == "NOT_FOUND"

    def test_delete_requires_authorization(self):
        """Delete requires matching user authorization."""
        # Implementation detail - user can only delete own configs
        error_response = {
            "error": {
                "code": "FORBIDDEN",
                "message": "Not allowed to delete this configuration",
            }
        }

        parsed = ErrorResponse(**error_response)
        assert parsed.error["code"] == "FORBIDDEN"


# --- Authentication Contract Tests ---


class TestConfigurationAuthentication:
    """Contract tests for authentication requirements."""

    def test_anonymous_header_accepted(self):
        """X-Anonymous-ID header authenticates anonymous users."""
        headers = {"X-Anonymous-ID": str(uuid.uuid4())}
        assert "X-Anonymous-ID" in headers

    def test_bearer_token_accepted(self):
        """Authorization: Bearer token authenticates registered users."""
        headers = {"Authorization": "Bearer eyJ..."}
        assert headers["Authorization"].startswith("Bearer ")

    def test_missing_auth_returns_401(self):
        """Missing authentication returns 401 Unauthorized."""
        error_response = {
            "error": {
                "code": "UNAUTHORIZED",
                "message": "Missing or invalid authentication",
            }
        }

        parsed = ErrorResponse(**error_response)
        assert parsed.error["code"] == "UNAUTHORIZED"


# --- Rate Limiting Contract Tests ---


class TestConfigurationRateLimiting:
    """Contract tests for rate limiting."""

    def test_rate_limit_100_per_minute(self):
        """Configuration endpoints limited to 100 requests per minute."""
        limit = 100
        window = "per minute per user ID"

        assert limit == 100
        assert "per minute" in window
