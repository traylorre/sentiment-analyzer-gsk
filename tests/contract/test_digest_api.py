"""Contract tests for digest endpoints (T129 - User Story 4).

Validates daily digest endpoints per notification-api.md:
- GET /api/v2/notifications/digest - Get digest settings
- PATCH /api/v2/notifications/digest - Update digest settings
- POST /api/v2/notifications/digest/test - Trigger test digest
"""

import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
from pydantic import BaseModel

# --- Response Schema Definitions ---


class DigestSettingsResponse(BaseModel):
    """Response schema for GET /api/v2/notifications/digest."""

    enabled: bool
    time: str
    timezone: str
    include_all_configs: bool
    config_ids: list[str] | None = None
    next_scheduled: str


class UpdateDigestRequest(BaseModel):
    """Request schema for PATCH /api/v2/notifications/digest."""

    enabled: bool | None = None
    time: str | None = None
    timezone: str | None = None
    include_all_configs: bool | None = None
    config_ids: list[str] | None = None


class TriggerTestDigestResponse(BaseModel):
    """Response for POST /api/v2/notifications/digest/test."""

    status: str
    message: str


class DigestErrorResponse(BaseModel):
    """Error response schema."""

    error: str
    message: str


# --- Mock Digest API ---


# Valid IANA timezones (subset for testing)
VALID_TIMEZONES = {
    "America/New_York",
    "America/Los_Angeles",
    "America/Chicago",
    "America/Denver",
    "Europe/London",
    "Europe/Paris",
    "Asia/Tokyo",
    "UTC",
}


class MockDigestAPI:
    """Mock API for digest endpoints."""

    def __init__(self):
        self.digest_settings: dict[str, dict[str, Any]] = {}  # user_id -> settings

    def _calculate_next_scheduled(self, time: str, timezone: str) -> str:
        """Calculate next scheduled digest time (simplified)."""
        now = datetime.now(UTC)
        # Parse time
        hours, minutes = map(int, time.split(":"))

        # Calculate next occurrence (simplified - ignores timezone for mock)
        next_digest = now.replace(hour=hours, minute=minutes, second=0, microsecond=0)
        if next_digest <= now:
            next_digest += timedelta(days=1)

        # Return UTC time without timezone suffix since we add Z
        return next_digest.strftime("%Y-%m-%dT%H:%M:%S") + "Z"

    def get_digest_settings(self, user_id: str) -> tuple[int, dict[str, Any]]:
        """Get user's digest settings."""
        if user_id not in self.digest_settings:
            # Return defaults
            return 200, {
                "enabled": False,
                "time": "09:00",
                "timezone": "America/New_York",
                "include_all_configs": True,
                "config_ids": None,
                "next_scheduled": self._calculate_next_scheduled(
                    "09:00", "America/New_York"
                ),
            }
        return 200, self.digest_settings[user_id]

    def update_digest_settings(
        self,
        user_id: str,
        enabled: bool | None = None,
        time: str | None = None,
        timezone: str | None = None,
        include_all_configs: bool | None = None,
        config_ids: list[str] | None = None,
    ) -> tuple[int, dict[str, Any]]:
        """Update digest settings."""
        # Validate time format (must be HH:MM with exactly 2 digits each)
        if time is not None:
            try:
                if len(time) != 5 or time[2] != ":":
                    raise ValueError("Invalid format")
                hours, minutes = time.split(":")
                if len(hours) != 2 or len(minutes) != 2:
                    raise ValueError("Must be HH:MM format")
                if not (0 <= int(hours) <= 23 and 0 <= int(minutes) <= 59):
                    return 400, {
                        "error": "invalid_time",
                        "message": "Time must be in HH:MM format (24-hour)",
                    }
            except ValueError:
                return 400, {
                    "error": "invalid_time",
                    "message": "Time must be in HH:MM format (24-hour)",
                }

        # Validate timezone
        if timezone is not None and timezone not in VALID_TIMEZONES:
            return 400, {
                "error": "invalid_timezone",
                "message": f"Invalid timezone: {timezone}",
            }

        # Validate config_ids required if not include_all_configs
        if include_all_configs is False and not config_ids:
            return 400, {
                "error": "config_ids_required",
                "message": "config_ids required when include_all_configs is false",
            }

        # Get existing or defaults
        _, current = self.get_digest_settings(user_id)

        # Update fields
        if enabled is not None:
            current["enabled"] = enabled
        if time is not None:
            current["time"] = time
        if timezone is not None:
            current["timezone"] = timezone
        if include_all_configs is not None:
            current["include_all_configs"] = include_all_configs
        if config_ids is not None:
            current["config_ids"] = config_ids

        # Recalculate next scheduled
        current["next_scheduled"] = self._calculate_next_scheduled(
            current["time"], current["timezone"]
        )

        self.digest_settings[user_id] = current
        return 200, current

    def trigger_test_digest(self, user_id: str) -> tuple[int, dict[str, Any]]:
        """Trigger test digest email."""
        # Check if user has digest configured
        _, settings = self.get_digest_settings(user_id)

        return 202, {
            "status": "test_queued",
            "message": "Test digest email will be sent within 1 minute",
        }


@pytest.fixture
def mock_api():
    """Create fresh mock API for each test."""
    return MockDigestAPI()


@pytest.fixture
def user_id():
    """Generate a user ID for testing."""
    return str(uuid.uuid4())


# --- Contract Tests ---


class TestGetDigestSettings:
    """Tests for GET /api/v2/notifications/digest."""

    def test_gets_default_settings(self, mock_api: MockDigestAPI, user_id: str):
        """Returns default settings for new user."""
        status, response = mock_api.get_digest_settings(user_id)

        assert status == 200
        settings = DigestSettingsResponse(**response)
        assert settings.enabled is False
        assert settings.time == "09:00"
        assert settings.timezone == "America/New_York"
        assert settings.include_all_configs is True
        assert settings.next_scheduled is not None

    def test_gets_configured_settings(self, mock_api: MockDigestAPI, user_id: str):
        """Returns configured settings after update."""
        # Configure digest
        mock_api.update_digest_settings(
            user_id,
            enabled=True,
            time="08:00",
            timezone="America/Los_Angeles",
        )

        status, response = mock_api.get_digest_settings(user_id)

        assert status == 200
        settings = DigestSettingsResponse(**response)
        assert settings.enabled is True
        assert settings.time == "08:00"
        assert settings.timezone == "America/Los_Angeles"

    def test_includes_next_scheduled(self, mock_api: MockDigestAPI, user_id: str):
        """Response includes next_scheduled timestamp."""
        status, response = mock_api.get_digest_settings(user_id)

        assert status == 200
        assert "next_scheduled" in response
        # Verify it's a valid ISO timestamp
        datetime.fromisoformat(response["next_scheduled"].replace("Z", "+00:00"))


class TestUpdateDigestSettings:
    """Tests for PATCH /api/v2/notifications/digest."""

    def test_enables_digest(self, mock_api: MockDigestAPI, user_id: str):
        """Enables daily digest."""
        status, response = mock_api.update_digest_settings(user_id, enabled=True)

        assert status == 200
        assert response["enabled"] is True

    def test_updates_time(self, mock_api: MockDigestAPI, user_id: str):
        """Updates digest time."""
        status, response = mock_api.update_digest_settings(user_id, time="08:00")

        assert status == 200
        assert response["time"] == "08:00"

    def test_updates_timezone(self, mock_api: MockDigestAPI, user_id: str):
        """Updates timezone."""
        status, response = mock_api.update_digest_settings(
            user_id, timezone="America/Los_Angeles"
        )

        assert status == 200
        assert response["timezone"] == "America/Los_Angeles"

    def test_updates_include_all_configs(self, mock_api: MockDigestAPI, user_id: str):
        """Updates include_all_configs with config_ids."""
        config_ids = [str(uuid.uuid4())]
        status, response = mock_api.update_digest_settings(
            user_id, include_all_configs=False, config_ids=config_ids
        )

        assert status == 200
        assert response["include_all_configs"] is False
        assert response["config_ids"] == config_ids

    def test_rejects_invalid_time_format(self, mock_api: MockDigestAPI, user_id: str):
        """Rejects invalid time format."""
        status, response = mock_api.update_digest_settings(user_id, time="9am")

        assert status == 400
        assert response["error"] == "invalid_time"
        assert "HH:MM" in response["message"]

    def test_rejects_out_of_range_time(self, mock_api: MockDigestAPI, user_id: str):
        """Rejects out of range time."""
        status, response = mock_api.update_digest_settings(user_id, time="25:00")

        assert status == 400
        assert response["error"] == "invalid_time"

    def test_rejects_invalid_timezone(self, mock_api: MockDigestAPI, user_id: str):
        """Rejects invalid timezone."""
        status, response = mock_api.update_digest_settings(
            user_id, timezone="Invalid/Zone"
        )

        assert status == 400
        assert response["error"] == "invalid_timezone"

    def test_requires_config_ids_when_not_all_configs(
        self, mock_api: MockDigestAPI, user_id: str
    ):
        """Requires config_ids when include_all_configs is false."""
        status, response = mock_api.update_digest_settings(
            user_id, include_all_configs=False
        )

        assert status == 400
        assert response["error"] == "config_ids_required"

    def test_recalculates_next_scheduled(self, mock_api: MockDigestAPI, user_id: str):
        """Recalculates next_scheduled after time change."""
        # Get initial settings
        _, _ = mock_api.get_digest_settings(user_id)

        # Update time
        status, response = mock_api.update_digest_settings(user_id, time="23:59")

        assert status == 200
        # next_scheduled should be present in response
        assert "next_scheduled" in response


class TestTriggerTestDigest:
    """Tests for POST /api/v2/notifications/digest/test."""

    def test_queues_test_digest(self, mock_api: MockDigestAPI, user_id: str):
        """Queues test digest email."""
        status, response = mock_api.trigger_test_digest(user_id)

        assert status == 202
        test_response = TriggerTestDigestResponse(**response)
        assert test_response.status == "test_queued"
        assert "1 minute" in test_response.message

    def test_returns_202_accepted(self, mock_api: MockDigestAPI, user_id: str):
        """Returns 202 Accepted for async operation."""
        status, _ = mock_api.trigger_test_digest(user_id)

        assert status == 202  # Async operation


class TestDigestValidation:
    """Tests for digest validation rules."""

    def test_time_format_hh_mm(self, mock_api: MockDigestAPI, user_id: str):
        """Time must be in HH:MM format."""
        # Valid times
        valid_times = ["00:00", "09:00", "12:30", "23:59"]
        for t in valid_times:
            status, _ = mock_api.update_digest_settings(user_id, time=t)
            assert status == 200, f"Should accept {t}"

        # Invalid times
        invalid_times = ["9:00", "9am", "25:00", "12:60"]
        for t in invalid_times:
            status, _ = mock_api.update_digest_settings(user_id, time=t)
            assert status == 400, f"Should reject {t}"

    def test_timezone_must_be_valid_iana(self, mock_api: MockDigestAPI, user_id: str):
        """Timezone must be valid IANA timezone."""
        # Valid timezones
        valid_tzs = ["America/New_York", "UTC", "Europe/London"]
        for tz in valid_tzs:
            status, _ = mock_api.update_digest_settings(user_id, timezone=tz)
            assert status == 200, f"Should accept {tz}"

        # Invalid timezones
        invalid_tzs = ["EST", "PST", "GMT+5", "Invalid/Zone"]
        for tz in invalid_tzs:
            status, _ = mock_api.update_digest_settings(user_id, timezone=tz)
            assert status == 400, f"Should reject {tz}"
