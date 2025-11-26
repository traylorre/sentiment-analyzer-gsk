"""Contract tests for alert CRUD endpoints (T127 - User Story 4).

Validates alert endpoints per notification-api.md:
- GET /api/v2/alerts - List alerts with filtering
- POST /api/v2/alerts - Create alert with validation
- GET /api/v2/alerts/{id} - Get single alert
- PATCH /api/v2/alerts/{id} - Update alert
- DELETE /api/v2/alerts/{id} - Delete alert
- POST /api/v2/alerts/{id}/toggle - Toggle enabled status
"""

import uuid
from datetime import UTC, datetime
from typing import Any

import pytest
from pydantic import BaseModel, Field, field_validator

# --- Response Schema Definitions ---


class AlertResponse(BaseModel):
    """Response schema for a single alert rule."""

    alert_id: str
    config_id: str
    ticker: str
    alert_type: str
    threshold_value: float
    threshold_direction: str
    is_enabled: bool
    last_triggered_at: str | None = None
    trigger_count: int = 0
    created_at: str

    @field_validator("alert_id", "config_id")
    @classmethod
    def validate_uuid(cls, v: str) -> str:
        """Validate field is valid UUID."""
        uuid.UUID(v)
        return v

    @field_validator("alert_type")
    @classmethod
    def validate_alert_type(cls, v: str) -> str:
        """Validate alert type."""
        if v not in ("sentiment_threshold", "volatility_threshold"):
            raise ValueError(f"Invalid alert_type: {v}")
        return v

    @field_validator("threshold_direction")
    @classmethod
    def validate_direction(cls, v: str) -> str:
        """Validate threshold direction."""
        if v not in ("above", "below"):
            raise ValueError(f"Invalid threshold_direction: {v}")
        return v


class DailyEmailQuota(BaseModel):
    """Daily email quota info."""

    used: int = Field(..., ge=0)
    limit: int = Field(..., ge=1)
    resets_at: str


class AlertListResponse(BaseModel):
    """Response schema for GET /api/v2/alerts."""

    alerts: list[AlertResponse]
    total: int = Field(..., ge=0)
    daily_email_quota: DailyEmailQuota


class AlertToggleResponse(BaseModel):
    """Response for POST /api/v2/alerts/{id}/toggle."""

    alert_id: str
    is_enabled: bool
    message: str


class AlertErrorResponse(BaseModel):
    """Error response schema."""

    error: str
    message: str
    details: dict[str, Any] | None = None


# --- Mock Alert API ---


class MockAlertAPI:
    """Mock API that enforces alert rules per contract."""

    MAX_ALERTS_PER_CONFIG = 10
    DAILY_EMAIL_LIMIT = 10

    def __init__(self):
        self.alerts: dict[str, dict[str, Any]] = {}
        self.config_alert_counts: dict[str, int] = {}
        self.daily_email_usage: dict[str, int] = {}  # user_id -> count
        self.user_alerts: dict[str, list[str]] = {}  # user_id -> alert_ids

    def list_alerts(
        self,
        user_id: str,
        config_id: str | None = None,
        ticker: str | None = None,
        enabled: bool | None = None,
    ) -> tuple[int, dict[str, Any]]:
        """List user's alerts with optional filters."""
        user_alert_ids = self.user_alerts.get(user_id, [])
        alerts = [self.alerts[aid] for aid in user_alert_ids if aid in self.alerts]

        # Apply filters
        if config_id:
            alerts = [a for a in alerts if a["config_id"] == config_id]
        if ticker:
            alerts = [a for a in alerts if a["ticker"] == ticker]
        if enabled is not None:
            alerts = [a for a in alerts if a["is_enabled"] == enabled]

        return 200, {
            "alerts": alerts,
            "total": len(alerts),
            "daily_email_quota": {
                "used": self.daily_email_usage.get(user_id, 0),
                "limit": self.DAILY_EMAIL_LIMIT,
                "resets_at": datetime.now(UTC)
                .replace(hour=0, minute=0, second=0)
                .isoformat()
                + "Z",
            },
        }

    def create_alert(
        self,
        user_id: str,
        config_id: str,
        ticker: str,
        alert_type: str,
        threshold_value: float,
        threshold_direction: str,
        is_authenticated: bool = True,
    ) -> tuple[int, dict[str, Any]]:
        """Create a new alert rule."""
        # Check authentication
        if not is_authenticated:
            return 403, {
                "error": "ANONYMOUS_NOT_ALLOWED",
                "message": "Alerts require authentication",
            }

        # Validate alert type
        if alert_type not in ("sentiment_threshold", "volatility_threshold"):
            return 400, {
                "error": "INVALID_ALERT_TYPE",
                "message": f"Invalid alert_type: {alert_type}",
            }

        # Validate threshold direction
        if threshold_direction not in ("above", "below"):
            return 400, {
                "error": "INVALID_DIRECTION",
                "message": "threshold_direction must be 'above' or 'below'",
            }

        # Validate threshold value based on type
        if alert_type == "sentiment_threshold":
            if not -1.0 <= threshold_value <= 1.0:
                return 400, {
                    "error": "INVALID_THRESHOLD",
                    "message": "Sentiment threshold must be between -1.0 and 1.0",
                }
        else:  # volatility_threshold
            if not 0.0 <= threshold_value <= 100.0:
                return 400, {
                    "error": "INVALID_THRESHOLD",
                    "message": "Volatility threshold must be between 0 and 100%",
                }

        # Check max alerts per config
        config_count = self.config_alert_counts.get(config_id, 0)
        if config_count >= self.MAX_ALERTS_PER_CONFIG:
            return 409, {
                "error": "ALERT_LIMIT_EXCEEDED",
                "message": f"Maximum {self.MAX_ALERTS_PER_CONFIG} alerts per configuration",
            }

        # Create alert
        alert_id = str(uuid.uuid4())
        now = datetime.now(UTC).isoformat() + "Z"

        alert = {
            "alert_id": alert_id,
            "config_id": config_id,
            "ticker": ticker.upper(),
            "alert_type": alert_type,
            "threshold_value": threshold_value,
            "threshold_direction": threshold_direction,
            "is_enabled": True,
            "last_triggered_at": None,
            "trigger_count": 0,
            "created_at": now,
        }

        self.alerts[alert_id] = alert
        self.config_alert_counts[config_id] = config_count + 1
        self.user_alerts.setdefault(user_id, []).append(alert_id)

        return 201, alert

    def get_alert(self, user_id: str, alert_id: str) -> tuple[int, dict[str, Any]]:
        """Get a single alert by ID."""
        if alert_id not in self.alerts:
            return 404, {"error": "not_found", "message": "Alert not found"}

        # Check ownership
        if alert_id not in self.user_alerts.get(user_id, []):
            return 403, {"error": "forbidden", "message": "Access denied"}

        return 200, self.alerts[alert_id]

    def update_alert(
        self,
        user_id: str,
        alert_id: str,
        threshold_value: float | None = None,
        is_enabled: bool | None = None,
    ) -> tuple[int, dict[str, Any]]:
        """Update an existing alert."""
        if alert_id not in self.alerts:
            return 404, {"error": "not_found", "message": "Alert not found"}

        if alert_id not in self.user_alerts.get(user_id, []):
            return 403, {"error": "forbidden", "message": "Access denied"}

        alert = self.alerts[alert_id]

        # Validate new threshold if provided
        if threshold_value is not None:
            if alert["alert_type"] == "sentiment_threshold":
                if not -1.0 <= threshold_value <= 1.0:
                    return 400, {
                        "error": "INVALID_THRESHOLD",
                        "message": "Sentiment threshold must be between -1.0 and 1.0",
                    }
            else:
                if not 0.0 <= threshold_value <= 100.0:
                    return 400, {
                        "error": "INVALID_THRESHOLD",
                        "message": "Volatility threshold must be between 0 and 100%",
                    }
            alert["threshold_value"] = threshold_value

        if is_enabled is not None:
            alert["is_enabled"] = is_enabled

        return 200, alert

    def delete_alert(self, user_id: str, alert_id: str) -> tuple[int, dict[str, Any]]:
        """Delete an alert."""
        if alert_id not in self.alerts:
            return 404, {"error": "not_found", "message": "Alert not found"}

        if alert_id not in self.user_alerts.get(user_id, []):
            return 403, {"error": "forbidden", "message": "Access denied"}

        config_id = self.alerts[alert_id]["config_id"]
        del self.alerts[alert_id]
        self.user_alerts[user_id].remove(alert_id)
        self.config_alert_counts[config_id] = max(
            0, self.config_alert_counts.get(config_id, 1) - 1
        )

        return 204, {}

    def toggle_alert(self, user_id: str, alert_id: str) -> tuple[int, dict[str, Any]]:
        """Toggle alert enabled status."""
        if alert_id not in self.alerts:
            return 404, {"error": "not_found", "message": "Alert not found"}

        if alert_id not in self.user_alerts.get(user_id, []):
            return 403, {"error": "forbidden", "message": "Access denied"}

        alert = self.alerts[alert_id]
        alert["is_enabled"] = not alert["is_enabled"]
        status = "enabled" if alert["is_enabled"] else "disabled"

        return 200, {
            "alert_id": alert_id,
            "is_enabled": alert["is_enabled"],
            "message": f"Alert {status}",
        }


@pytest.fixture
def mock_api():
    """Create fresh mock API for each test."""
    return MockAlertAPI()


@pytest.fixture
def user_id():
    """Generate a user ID for testing."""
    return str(uuid.uuid4())


@pytest.fixture
def config_id():
    """Generate a config ID for testing."""
    return str(uuid.uuid4())


# --- Contract Tests ---


class TestCreateAlert:
    """Tests for POST /api/v2/alerts."""

    def test_creates_sentiment_alert(
        self, mock_api: MockAlertAPI, user_id: str, config_id: str
    ):
        """Create sentiment threshold alert succeeds."""
        status, response = mock_api.create_alert(
            user_id=user_id,
            config_id=config_id,
            ticker="AAPL",
            alert_type="sentiment_threshold",
            threshold_value=-0.3,
            threshold_direction="below",
        )

        assert status == 201
        alert = AlertResponse(**response)
        assert alert.ticker == "AAPL"
        assert alert.alert_type == "sentiment_threshold"
        assert alert.threshold_value == -0.3
        assert alert.threshold_direction == "below"
        assert alert.is_enabled is True

    def test_creates_volatility_alert(
        self, mock_api: MockAlertAPI, user_id: str, config_id: str
    ):
        """Create volatility threshold alert succeeds."""
        status, response = mock_api.create_alert(
            user_id=user_id,
            config_id=config_id,
            ticker="TSLA",
            alert_type="volatility_threshold",
            threshold_value=5.0,
            threshold_direction="above",
        )

        assert status == 201
        alert = AlertResponse(**response)
        assert alert.ticker == "TSLA"
        assert alert.alert_type == "volatility_threshold"
        assert alert.threshold_value == 5.0

    def test_rejects_invalid_alert_type(
        self, mock_api: MockAlertAPI, user_id: str, config_id: str
    ):
        """Invalid alert type returns 400."""
        status, response = mock_api.create_alert(
            user_id=user_id,
            config_id=config_id,
            ticker="AAPL",
            alert_type="invalid_type",
            threshold_value=0.5,
            threshold_direction="above",
        )

        assert status == 400
        assert response["error"] == "INVALID_ALERT_TYPE"

    def test_rejects_invalid_sentiment_threshold(
        self, mock_api: MockAlertAPI, user_id: str, config_id: str
    ):
        """Sentiment threshold out of range returns 400."""
        status, response = mock_api.create_alert(
            user_id=user_id,
            config_id=config_id,
            ticker="AAPL",
            alert_type="sentiment_threshold",
            threshold_value=1.5,  # > 1.0
            threshold_direction="above",
        )

        assert status == 400
        assert response["error"] == "INVALID_THRESHOLD"
        assert "-1.0" in response["message"] and "1.0" in response["message"]

    def test_rejects_invalid_volatility_threshold(
        self, mock_api: MockAlertAPI, user_id: str, config_id: str
    ):
        """Volatility threshold out of range returns 400."""
        status, response = mock_api.create_alert(
            user_id=user_id,
            config_id=config_id,
            ticker="AAPL",
            alert_type="volatility_threshold",
            threshold_value=150.0,  # > 100
            threshold_direction="above",
        )

        assert status == 400
        assert response["error"] == "INVALID_THRESHOLD"

    def test_rejects_invalid_direction(
        self, mock_api: MockAlertAPI, user_id: str, config_id: str
    ):
        """Invalid threshold direction returns 400."""
        status, response = mock_api.create_alert(
            user_id=user_id,
            config_id=config_id,
            ticker="AAPL",
            alert_type="sentiment_threshold",
            threshold_value=0.5,
            threshold_direction="sideways",
        )

        assert status == 400
        assert response["error"] == "INVALID_DIRECTION"

    def test_rejects_anonymous_user(
        self, mock_api: MockAlertAPI, user_id: str, config_id: str
    ):
        """Anonymous users cannot create alerts."""
        status, response = mock_api.create_alert(
            user_id=user_id,
            config_id=config_id,
            ticker="AAPL",
            alert_type="sentiment_threshold",
            threshold_value=-0.3,
            threshold_direction="below",
            is_authenticated=False,
        )

        assert status == 403
        assert response["error"] == "ANONYMOUS_NOT_ALLOWED"

    def test_enforces_max_alerts_per_config(
        self, mock_api: MockAlertAPI, user_id: str, config_id: str
    ):
        """Maximum 10 alerts per config enforced."""
        # Create 10 alerts
        for i in range(10):
            status, _ = mock_api.create_alert(
                user_id=user_id,
                config_id=config_id,
                ticker=f"T{i:02d}",
                alert_type="sentiment_threshold",
                threshold_value=-0.3,
                threshold_direction="below",
            )
            assert status == 201

        # 11th should fail
        status, response = mock_api.create_alert(
            user_id=user_id,
            config_id=config_id,
            ticker="EXTRA",
            alert_type="sentiment_threshold",
            threshold_value=-0.3,
            threshold_direction="below",
        )

        assert status == 409
        assert response["error"] == "ALERT_LIMIT_EXCEEDED"


class TestListAlerts:
    """Tests for GET /api/v2/alerts."""

    def test_lists_empty_alerts(self, mock_api: MockAlertAPI, user_id: str):
        """Empty list for user with no alerts."""
        status, response = mock_api.list_alerts(user_id)

        assert status == 200
        list_response = AlertListResponse(**response)
        assert list_response.alerts == []
        assert list_response.total == 0

    def test_lists_user_alerts(
        self, mock_api: MockAlertAPI, user_id: str, config_id: str
    ):
        """Lists all alerts for a user."""
        # Create two alerts
        mock_api.create_alert(
            user_id, config_id, "AAPL", "sentiment_threshold", -0.3, "below"
        )
        mock_api.create_alert(
            user_id, config_id, "TSLA", "volatility_threshold", 5.0, "above"
        )

        status, response = mock_api.list_alerts(user_id)

        assert status == 200
        assert response["total"] == 2
        tickers = {a["ticker"] for a in response["alerts"]}
        assert tickers == {"AAPL", "TSLA"}

    def test_filters_by_config_id(self, mock_api: MockAlertAPI, user_id: str):
        """Filters alerts by config_id."""
        config_a = str(uuid.uuid4())
        config_b = str(uuid.uuid4())

        mock_api.create_alert(
            user_id, config_a, "AAPL", "sentiment_threshold", -0.3, "below"
        )
        mock_api.create_alert(
            user_id, config_b, "TSLA", "sentiment_threshold", -0.5, "below"
        )

        status, response = mock_api.list_alerts(user_id, config_id=config_a)

        assert status == 200
        assert response["total"] == 1
        assert response["alerts"][0]["ticker"] == "AAPL"

    def test_filters_by_ticker(
        self, mock_api: MockAlertAPI, user_id: str, config_id: str
    ):
        """Filters alerts by ticker."""
        mock_api.create_alert(
            user_id, config_id, "AAPL", "sentiment_threshold", -0.3, "below"
        )
        mock_api.create_alert(
            user_id, config_id, "TSLA", "volatility_threshold", 5.0, "above"
        )

        status, response = mock_api.list_alerts(user_id, ticker="AAPL")

        assert status == 200
        assert response["total"] == 1
        assert response["alerts"][0]["ticker"] == "AAPL"

    def test_filters_by_enabled_status(
        self, mock_api: MockAlertAPI, user_id: str, config_id: str
    ):
        """Filters alerts by enabled status."""
        mock_api.create_alert(
            user_id, config_id, "AAPL", "sentiment_threshold", -0.3, "below"
        )
        _, alert = mock_api.create_alert(
            user_id, config_id, "TSLA", "volatility_threshold", 5.0, "above"
        )
        # Disable TSLA alert
        mock_api.update_alert(user_id, alert["alert_id"], is_enabled=False)

        status, response = mock_api.list_alerts(user_id, enabled=True)

        assert status == 200
        assert response["total"] == 1
        assert response["alerts"][0]["ticker"] == "AAPL"

    def test_includes_daily_quota(self, mock_api: MockAlertAPI, user_id: str):
        """Response includes daily email quota info."""
        status, response = mock_api.list_alerts(user_id)

        assert status == 200
        quota = response["daily_email_quota"]
        assert "used" in quota
        assert "limit" in quota
        assert quota["limit"] == 10
        assert "resets_at" in quota


class TestGetAlert:
    """Tests for GET /api/v2/alerts/{id}."""

    def test_gets_existing_alert(
        self, mock_api: MockAlertAPI, user_id: str, config_id: str
    ):
        """Returns alert for valid ID."""
        _, created = mock_api.create_alert(
            user_id, config_id, "AAPL", "sentiment_threshold", -0.3, "below"
        )

        status, response = mock_api.get_alert(user_id, created["alert_id"])

        assert status == 200
        alert = AlertResponse(**response)
        assert alert.alert_id == created["alert_id"]
        assert alert.ticker == "AAPL"

    def test_returns_404_for_nonexistent(self, mock_api: MockAlertAPI, user_id: str):
        """Returns 404 for nonexistent alert."""
        status, response = mock_api.get_alert(user_id, str(uuid.uuid4()))

        assert status == 404
        assert response["error"] == "not_found"

    def test_returns_403_for_other_user(self, mock_api: MockAlertAPI, config_id: str):
        """Returns 403 when accessing another user's alert."""
        user_a = str(uuid.uuid4())
        user_b = str(uuid.uuid4())

        _, created = mock_api.create_alert(
            user_a, config_id, "AAPL", "sentiment_threshold", -0.3, "below"
        )

        status, response = mock_api.get_alert(user_b, created["alert_id"])

        assert status == 403
        assert response["error"] == "forbidden"


class TestUpdateAlert:
    """Tests for PATCH /api/v2/alerts/{id}."""

    def test_updates_threshold_value(
        self, mock_api: MockAlertAPI, user_id: str, config_id: str
    ):
        """Updates threshold value."""
        _, created = mock_api.create_alert(
            user_id, config_id, "AAPL", "sentiment_threshold", -0.3, "below"
        )

        status, response = mock_api.update_alert(
            user_id, created["alert_id"], threshold_value=-0.5
        )

        assert status == 200
        assert response["threshold_value"] == -0.5

    def test_updates_enabled_status(
        self, mock_api: MockAlertAPI, user_id: str, config_id: str
    ):
        """Updates enabled status."""
        _, created = mock_api.create_alert(
            user_id, config_id, "AAPL", "sentiment_threshold", -0.3, "below"
        )
        assert created["is_enabled"] is True

        status, response = mock_api.update_alert(
            user_id, created["alert_id"], is_enabled=False
        )

        assert status == 200
        assert response["is_enabled"] is False

    def test_validates_new_threshold(
        self, mock_api: MockAlertAPI, user_id: str, config_id: str
    ):
        """Validates new threshold value against type limits."""
        _, created = mock_api.create_alert(
            user_id, config_id, "AAPL", "sentiment_threshold", -0.3, "below"
        )

        status, response = mock_api.update_alert(
            user_id, created["alert_id"], threshold_value=2.0  # Invalid
        )

        assert status == 400
        assert response["error"] == "INVALID_THRESHOLD"


class TestDeleteAlert:
    """Tests for DELETE /api/v2/alerts/{id}."""

    def test_deletes_existing_alert(
        self, mock_api: MockAlertAPI, user_id: str, config_id: str
    ):
        """Deletes an existing alert."""
        _, created = mock_api.create_alert(
            user_id, config_id, "AAPL", "sentiment_threshold", -0.3, "below"
        )

        status, _ = mock_api.delete_alert(user_id, created["alert_id"])

        assert status == 204

        # Verify deleted
        get_status, _ = mock_api.get_alert(user_id, created["alert_id"])
        assert get_status == 404

    def test_delete_allows_new_alert_in_config(
        self, mock_api: MockAlertAPI, user_id: str, config_id: str
    ):
        """After delete, can create new alert up to limit."""
        # Fill to max
        alert_ids = []
        for i in range(10):
            _, alert = mock_api.create_alert(
                user_id, config_id, f"T{i:02d}", "sentiment_threshold", -0.3, "below"
            )
            alert_ids.append(alert["alert_id"])

        # Delete one
        mock_api.delete_alert(user_id, alert_ids[0])

        # Should be able to create new
        status, _ = mock_api.create_alert(
            user_id, config_id, "NEW", "sentiment_threshold", -0.3, "below"
        )
        assert status == 201


class TestToggleAlert:
    """Tests for POST /api/v2/alerts/{id}/toggle."""

    def test_toggles_enabled_to_disabled(
        self, mock_api: MockAlertAPI, user_id: str, config_id: str
    ):
        """Toggle from enabled to disabled."""
        _, created = mock_api.create_alert(
            user_id, config_id, "AAPL", "sentiment_threshold", -0.3, "below"
        )
        assert created["is_enabled"] is True

        status, response = mock_api.toggle_alert(user_id, created["alert_id"])

        assert status == 200
        toggle_response = AlertToggleResponse(**response)
        assert toggle_response.is_enabled is False
        assert "disabled" in toggle_response.message.lower()

    def test_toggles_disabled_to_enabled(
        self, mock_api: MockAlertAPI, user_id: str, config_id: str
    ):
        """Toggle from disabled to enabled."""
        _, created = mock_api.create_alert(
            user_id, config_id, "AAPL", "sentiment_threshold", -0.3, "below"
        )
        # Disable first
        mock_api.toggle_alert(user_id, created["alert_id"])

        # Toggle again
        status, response = mock_api.toggle_alert(user_id, created["alert_id"])

        assert status == 200
        assert response["is_enabled"] is True
        assert "enabled" in response["message"].lower()

    def test_toggle_nonexistent_returns_404(self, mock_api: MockAlertAPI, user_id: str):
        """Toggle nonexistent alert returns 404."""
        status, response = mock_api.toggle_alert(user_id, str(uuid.uuid4()))

        assert status == 404
        assert response["error"] == "not_found"


class TestUserIsolation:
    """Tests for user data isolation."""

    def test_users_only_see_own_alerts(self, mock_api: MockAlertAPI):
        """Users can only see their own alerts."""
        user_a = str(uuid.uuid4())
        user_b = str(uuid.uuid4())
        config = str(uuid.uuid4())

        mock_api.create_alert(
            user_a, config, "AAPL", "sentiment_threshold", -0.3, "below"
        )
        mock_api.create_alert(
            user_b, config, "TSLA", "sentiment_threshold", -0.5, "below"
        )

        _, list_a = mock_api.list_alerts(user_a)
        _, list_b = mock_api.list_alerts(user_b)

        assert list_a["total"] == 1
        assert list_a["alerts"][0]["ticker"] == "AAPL"

        assert list_b["total"] == 1
        assert list_b["alerts"][0]["ticker"] == "TSLA"

    def test_users_cannot_modify_others_alerts(self, mock_api: MockAlertAPI):
        """Users cannot update/delete other users' alerts."""
        user_a = str(uuid.uuid4())
        user_b = str(uuid.uuid4())
        config = str(uuid.uuid4())

        _, alert = mock_api.create_alert(
            user_a, config, "AAPL", "sentiment_threshold", -0.3, "below"
        )
        alert_id = alert["alert_id"]

        # User B tries to update
        update_status, _ = mock_api.update_alert(user_b, alert_id, threshold_value=-0.5)
        assert update_status == 403

        # User B tries to delete
        delete_status, _ = mock_api.delete_alert(user_b, alert_id)
        assert delete_status == 403

        # User B tries to toggle
        toggle_status, _ = mock_api.toggle_alert(user_b, alert_id)
        assert toggle_status == 403
