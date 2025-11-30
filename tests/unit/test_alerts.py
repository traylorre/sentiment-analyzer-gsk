"""Unit tests for alert CRUD operations (T131-T136)."""

import uuid
from unittest.mock import MagicMock, patch

import pytest

from src.lambdas.dashboard.alerts import (
    AlertListResponse,
    AlertResponse,
    AlertToggleResponse,
    AlertUpdateRequest,
    ErrorResponse,
    _count_config_alerts,
    _get_daily_email_quota,
    _validate_threshold,
    create_alert,
    delete_alert,
    get_alert,
    list_alerts,
    toggle_alert,
    update_alert,
)
from src.lambdas.dashboard.quota import QuotaStatus
from src.lambdas.shared.models.alert_rule import ALERT_LIMITS, AlertRuleCreate


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
def alert_id():
    """Generate an alert ID."""
    return str(uuid.uuid4())


@pytest.fixture
def sample_alert_item(user_id, config_id, alert_id):
    """Create a sample alert DynamoDB item."""
    return {
        "PK": f"USER#{user_id}",
        "SK": f"ALERT#{alert_id}",
        "alert_id": alert_id,
        "user_id": user_id,
        "config_id": config_id,
        "ticker": "AAPL",
        "alert_type": "sentiment_threshold",
        "threshold_value": "-0.3",
        "threshold_direction": "below",
        "is_enabled": True,
        "trigger_count": 0,
        "created_at": "2025-11-25T10:00:00+00:00",
        "entity_type": "ALERT_RULE",
    }


class TestCreateAlert:
    """Tests for create_alert function."""

    @patch("src.lambdas.dashboard.alerts.xray_recorder")
    def test_creates_alert_successfully(
        self, mock_xray, mock_table, user_id, config_id
    ):
        """Creates alert with valid request."""
        mock_table.query.return_value = {"Count": 0}

        request = AlertRuleCreate(
            config_id=config_id,
            ticker="AAPL",
            alert_type="sentiment_threshold",
            threshold_value=-0.3,
            threshold_direction="below",
        )

        result = create_alert(mock_table, user_id, request, is_authenticated=True)

        assert isinstance(result, AlertResponse)
        assert result.ticker == "AAPL"
        assert result.alert_type == "sentiment_threshold"
        assert result.threshold_value == -0.3
        assert result.threshold_direction == "below"
        assert result.is_enabled is True
        mock_table.put_item.assert_called_once()

    @patch("src.lambdas.dashboard.alerts.xray_recorder")
    def test_rejects_anonymous_user(self, mock_xray, mock_table, user_id, config_id):
        """Rejects anonymous users trying to create alerts."""
        request = AlertRuleCreate(
            config_id=config_id,
            ticker="AAPL",
            alert_type="sentiment_threshold",
            threshold_value=-0.3,
            threshold_direction="below",
        )

        result = create_alert(mock_table, user_id, request, is_authenticated=False)

        assert isinstance(result, ErrorResponse)
        assert result.error.code == "ANONYMOUS_NOT_ALLOWED"
        mock_table.put_item.assert_not_called()

    @patch("src.lambdas.dashboard.alerts.xray_recorder")
    def test_rejects_max_alerts_exceeded(
        self, mock_xray, mock_table, user_id, config_id
    ):
        """Rejects when max alerts per config reached."""
        mock_table.query.return_value = {"Count": 10}

        request = AlertRuleCreate(
            config_id=config_id,
            ticker="AAPL",
            alert_type="sentiment_threshold",
            threshold_value=-0.3,
            threshold_direction="below",
        )

        result = create_alert(mock_table, user_id, request, is_authenticated=True)

        assert isinstance(result, ErrorResponse)
        assert result.error.code == "ALERT_LIMIT_EXCEEDED"
        mock_table.put_item.assert_not_called()

    @patch("src.lambdas.dashboard.alerts.xray_recorder")
    def test_rejects_invalid_sentiment_threshold(
        self, mock_xray, mock_table, user_id, config_id
    ):
        """Rejects sentiment threshold out of range."""
        mock_table.query.return_value = {"Count": 0}

        request = AlertRuleCreate(
            config_id=config_id,
            ticker="AAPL",
            alert_type="sentiment_threshold",
            threshold_value=1.5,  # Out of range (-1.0 to 1.0)
            threshold_direction="above",
        )

        result = create_alert(mock_table, user_id, request, is_authenticated=True)

        assert isinstance(result, ErrorResponse)
        assert result.error.code == "INVALID_THRESHOLD"

    @patch("src.lambdas.dashboard.alerts.xray_recorder")
    def test_rejects_invalid_volatility_threshold(
        self, mock_xray, mock_table, user_id, config_id
    ):
        """Rejects volatility threshold out of range."""
        mock_table.query.return_value = {"Count": 0}

        request = AlertRuleCreate(
            config_id=config_id,
            ticker="TSLA",
            alert_type="volatility_threshold",
            threshold_value=150.0,  # Out of range (0 to 100)
            threshold_direction="above",
        )

        result = create_alert(mock_table, user_id, request, is_authenticated=True)

        assert isinstance(result, ErrorResponse)
        assert result.error.code == "INVALID_THRESHOLD"

    @patch("src.lambdas.dashboard.alerts.xray_recorder")
    def test_uppercases_ticker(self, mock_xray, mock_table, user_id, config_id):
        """Converts ticker to uppercase."""
        mock_table.query.return_value = {"Count": 0}

        request = AlertRuleCreate(
            config_id=config_id,
            ticker="aapl",  # lowercase
            alert_type="sentiment_threshold",
            threshold_value=-0.3,
            threshold_direction="below",
        )

        result = create_alert(mock_table, user_id, request, is_authenticated=True)

        assert isinstance(result, AlertResponse)
        assert result.ticker == "AAPL"


class TestListAlerts:
    """Tests for list_alerts function."""

    @pytest.fixture
    def mock_quota(self):
        """Create a mock quota status."""
        return QuotaStatus(
            used=0,
            limit=10,
            remaining=10,
            resets_at="2025-01-01T00:00:00+00:00",
            is_exceeded=False,
        )

    @patch("src.lambdas.dashboard.alerts.get_daily_quota")
    @patch("src.lambdas.dashboard.alerts.xray_recorder")
    def test_lists_all_alerts(
        self,
        mock_xray,
        mock_get_quota,
        mock_table,
        user_id,
        sample_alert_item,
        mock_quota,
    ):
        """Lists all user alerts."""
        mock_table.query.return_value = {"Items": [sample_alert_item]}
        mock_get_quota.return_value = mock_quota

        result = list_alerts(mock_table, user_id)

        assert isinstance(result, AlertListResponse)
        assert len(result.alerts) == 1
        assert result.total == 1
        assert result.alerts[0].ticker == "AAPL"

    @patch("src.lambdas.dashboard.alerts.get_daily_quota")
    @patch("src.lambdas.dashboard.alerts.xray_recorder")
    def test_filters_by_config_id(
        self,
        mock_xray,
        mock_get_quota,
        mock_table,
        user_id,
        sample_alert_item,
        mock_quota,
    ):
        """Filters alerts by config_id."""
        config_id = sample_alert_item["config_id"]
        other_config = str(uuid.uuid4())
        mock_get_quota.return_value = mock_quota

        # Add another alert with different config
        other_alert = {**sample_alert_item}
        other_alert["config_id"] = other_config
        other_alert["ticker"] = "TSLA"

        mock_table.query.return_value = {"Items": [sample_alert_item, other_alert]}

        result = list_alerts(mock_table, user_id, config_id=config_id)

        assert len(result.alerts) == 1
        assert result.alerts[0].ticker == "AAPL"

    @patch("src.lambdas.dashboard.alerts.get_daily_quota")
    @patch("src.lambdas.dashboard.alerts.xray_recorder")
    def test_filters_by_ticker(
        self,
        mock_xray,
        mock_get_quota,
        mock_table,
        user_id,
        sample_alert_item,
        mock_quota,
    ):
        """Filters alerts by ticker."""
        other_alert = {**sample_alert_item}
        other_alert["ticker"] = "TSLA"
        mock_get_quota.return_value = mock_quota

        mock_table.query.return_value = {"Items": [sample_alert_item, other_alert]}

        result = list_alerts(mock_table, user_id, ticker="AAPL")

        assert len(result.alerts) == 1
        assert result.alerts[0].ticker == "AAPL"

    @patch("src.lambdas.dashboard.alerts.get_daily_quota")
    @patch("src.lambdas.dashboard.alerts.xray_recorder")
    def test_filters_by_enabled(
        self,
        mock_xray,
        mock_get_quota,
        mock_table,
        user_id,
        sample_alert_item,
        mock_quota,
    ):
        """Filters alerts by enabled status."""
        disabled_alert = {**sample_alert_item}
        disabled_alert["is_enabled"] = False
        mock_get_quota.return_value = mock_quota

        mock_table.query.return_value = {"Items": [sample_alert_item, disabled_alert]}

        result = list_alerts(mock_table, user_id, enabled=True)

        assert len(result.alerts) == 1
        assert result.alerts[0].is_enabled is True

    @patch("src.lambdas.dashboard.alerts.get_daily_quota")
    @patch("src.lambdas.dashboard.alerts.xray_recorder")
    def test_returns_empty_list(
        self, mock_xray, mock_get_quota, mock_table, user_id, mock_quota
    ):
        """Returns empty list when no alerts."""
        mock_table.query.return_value = {"Items": []}
        mock_get_quota.return_value = mock_quota

        result = list_alerts(mock_table, user_id)

        assert len(result.alerts) == 0
        assert result.total == 0

    @patch("src.lambdas.dashboard.alerts.get_daily_quota")
    @patch("src.lambdas.dashboard.alerts.xray_recorder")
    def test_includes_daily_email_quota(
        self,
        mock_xray,
        mock_get_quota,
        mock_table,
        user_id,
        sample_alert_item,
        mock_quota,
    ):
        """Response includes daily email quota info."""
        mock_table.query.return_value = {"Items": [sample_alert_item]}
        mock_get_quota.return_value = mock_quota

        result = list_alerts(mock_table, user_id)

        assert "used" in result.daily_email_quota
        assert "limit" in result.daily_email_quota
        assert "resets_at" in result.daily_email_quota


class TestGetAlert:
    """Tests for get_alert function."""

    @patch("src.lambdas.dashboard.alerts.xray_recorder")
    def test_gets_alert(self, mock_xray, mock_table, user_id, sample_alert_item):
        """Gets alert by ID."""
        alert_id = sample_alert_item["alert_id"]
        mock_table.get_item.return_value = {"Item": sample_alert_item}

        result = get_alert(mock_table, user_id, alert_id)

        assert isinstance(result, AlertResponse)
        assert result.alert_id == alert_id
        assert result.ticker == "AAPL"

    @patch("src.lambdas.dashboard.alerts.xray_recorder")
    def test_returns_none_for_not_found(self, mock_xray, mock_table, user_id):
        """Returns None when alert not found."""
        mock_table.get_item.return_value = {}

        result = get_alert(mock_table, user_id, str(uuid.uuid4()))

        assert result is None


class TestUpdateAlert:
    """Tests for update_alert function."""

    @patch("src.lambdas.dashboard.alerts.xray_recorder")
    def test_updates_threshold_value(
        self, mock_xray, mock_table, user_id, sample_alert_item
    ):
        """Updates alert threshold value."""
        alert_id = sample_alert_item["alert_id"]
        # get_item is called once to check existing alert
        mock_table.get_item.return_value = {"Item": sample_alert_item}

        request = AlertUpdateRequest(threshold_value=-0.5)

        # update_item now returns the updated attributes with ReturnValues='ALL_NEW'
        updated_item = {**sample_alert_item, "threshold_value": "-0.5"}
        mock_table.update_item.return_value = {"Attributes": updated_item}

        result = update_alert(mock_table, user_id, alert_id, request)

        assert isinstance(result, AlertResponse)
        mock_table.update_item.assert_called_once()

    @patch("src.lambdas.dashboard.alerts.xray_recorder")
    def test_updates_enabled_status(
        self, mock_xray, mock_table, user_id, sample_alert_item
    ):
        """Updates alert enabled status."""
        alert_id = sample_alert_item["alert_id"]
        # get_item is called once to check existing alert
        mock_table.get_item.return_value = {"Item": sample_alert_item}

        request = AlertUpdateRequest(is_enabled=False)

        # update_item now returns the updated attributes with ReturnValues='ALL_NEW'
        updated_item = {**sample_alert_item, "is_enabled": False}
        mock_table.update_item.return_value = {"Attributes": updated_item}

        result = update_alert(mock_table, user_id, alert_id, request)

        assert isinstance(result, AlertResponse)
        assert result.is_enabled is False
        mock_table.update_item.assert_called_once()

    @patch("src.lambdas.dashboard.alerts.xray_recorder")
    def test_returns_none_for_not_found(self, mock_xray, mock_table, user_id):
        """Returns None when alert not found."""
        mock_table.get_item.return_value = {}

        request = AlertUpdateRequest(threshold_value=-0.5)
        result = update_alert(mock_table, user_id, str(uuid.uuid4()), request)

        assert result is None

    @patch("src.lambdas.dashboard.alerts.xray_recorder")
    def test_rejects_invalid_threshold(
        self, mock_xray, mock_table, user_id, sample_alert_item
    ):
        """Rejects invalid threshold value on update."""
        alert_id = sample_alert_item["alert_id"]
        mock_table.get_item.return_value = {"Item": sample_alert_item}

        request = AlertUpdateRequest(threshold_value=2.0)  # Out of range

        result = update_alert(mock_table, user_id, alert_id, request)

        assert isinstance(result, ErrorResponse)
        assert result.error.code == "INVALID_THRESHOLD"

    @patch("src.lambdas.dashboard.alerts.xray_recorder")
    def test_returns_existing_when_nothing_to_update(
        self, mock_xray, mock_table, user_id, sample_alert_item
    ):
        """Returns existing alert when no fields to update."""
        alert_id = sample_alert_item["alert_id"]
        mock_table.get_item.return_value = {"Item": sample_alert_item}

        request = AlertUpdateRequest()  # Empty update

        result = update_alert(mock_table, user_id, alert_id, request)

        assert isinstance(result, AlertResponse)
        mock_table.update_item.assert_not_called()


class TestDeleteAlert:
    """Tests for delete_alert function."""

    @patch("src.lambdas.dashboard.alerts.xray_recorder")
    def test_deletes_alert(self, mock_xray, mock_table, user_id, sample_alert_item):
        """Deletes alert by ID."""
        alert_id = sample_alert_item["alert_id"]
        mock_table.get_item.return_value = {"Item": sample_alert_item}

        result = delete_alert(mock_table, user_id, alert_id)

        assert result is True
        mock_table.delete_item.assert_called_once()

    @patch("src.lambdas.dashboard.alerts.xray_recorder")
    def test_returns_false_for_not_found(self, mock_xray, mock_table, user_id):
        """Returns False when alert not found."""
        mock_table.get_item.return_value = {}

        result = delete_alert(mock_table, user_id, str(uuid.uuid4()))

        assert result is False
        mock_table.delete_item.assert_not_called()


class TestToggleAlert:
    """Tests for toggle_alert function."""

    @patch("src.lambdas.dashboard.alerts.xray_recorder")
    def test_disables_enabled_alert(
        self, mock_xray, mock_table, user_id, sample_alert_item
    ):
        """Disables an enabled alert."""
        alert_id = sample_alert_item["alert_id"]
        mock_table.get_item.return_value = {"Item": sample_alert_item}

        result = toggle_alert(mock_table, user_id, alert_id)

        assert isinstance(result, AlertToggleResponse)
        assert result.is_enabled is False
        assert "disabled" in result.message.lower()

    @patch("src.lambdas.dashboard.alerts.xray_recorder")
    def test_enables_disabled_alert(
        self, mock_xray, mock_table, user_id, sample_alert_item
    ):
        """Enables a disabled alert."""
        alert_id = sample_alert_item["alert_id"]
        disabled_item = {**sample_alert_item, "is_enabled": False}
        mock_table.get_item.return_value = {"Item": disabled_item}

        result = toggle_alert(mock_table, user_id, alert_id)

        assert isinstance(result, AlertToggleResponse)
        assert result.is_enabled is True
        assert "enabled" in result.message.lower()

    @patch("src.lambdas.dashboard.alerts.xray_recorder")
    def test_returns_none_for_not_found(self, mock_xray, mock_table, user_id):
        """Returns None when alert not found."""
        mock_table.get_item.return_value = {}

        result = toggle_alert(mock_table, user_id, str(uuid.uuid4()))

        assert result is None


class TestValidateThreshold:
    """Tests for _validate_threshold helper."""

    def test_accepts_valid_sentiment_threshold(self):
        """Accepts sentiment threshold in range."""
        assert _validate_threshold("sentiment_threshold", 0.0) is None
        assert _validate_threshold("sentiment_threshold", -1.0) is None
        assert _validate_threshold("sentiment_threshold", 1.0) is None
        assert _validate_threshold("sentiment_threshold", -0.5) is None

    def test_rejects_invalid_sentiment_threshold(self):
        """Rejects sentiment threshold out of range."""
        result = _validate_threshold("sentiment_threshold", 1.5)
        assert isinstance(result, ErrorResponse)
        assert result.error.code == "INVALID_THRESHOLD"

        result = _validate_threshold("sentiment_threshold", -1.5)
        assert isinstance(result, ErrorResponse)

    def test_accepts_valid_volatility_threshold(self):
        """Accepts volatility threshold in range."""
        assert _validate_threshold("volatility_threshold", 0.0) is None
        assert _validate_threshold("volatility_threshold", 50.0) is None
        assert _validate_threshold("volatility_threshold", 100.0) is None

    def test_rejects_invalid_volatility_threshold(self):
        """Rejects volatility threshold out of range."""
        result = _validate_threshold("volatility_threshold", -1.0)
        assert isinstance(result, ErrorResponse)
        assert result.error.code == "INVALID_THRESHOLD"

        result = _validate_threshold("volatility_threshold", 101.0)
        assert isinstance(result, ErrorResponse)


class TestCountConfigAlerts:
    """Tests for _count_config_alerts helper."""

    def test_counts_alerts(self, mock_table, user_id, config_id):
        """Counts alerts for config."""
        mock_table.query.return_value = {"Count": 5}

        count = _count_config_alerts(mock_table, user_id, config_id)

        assert count == 5

    def test_returns_zero_on_error(self, mock_table, user_id, config_id):
        """Returns 0 on query error."""
        mock_table.query.side_effect = Exception("DB error")

        count = _count_config_alerts(mock_table, user_id, config_id)

        assert count == 0


class TestGetDailyEmailQuota:
    """Tests for _get_daily_email_quota helper."""

    @patch("src.lambdas.dashboard.alerts.get_daily_quota")
    def test_returns_quota_info(self, mock_get_quota, mock_table, user_id):
        """Returns quota info dict."""
        mock_get_quota.return_value = QuotaStatus(
            used=5,
            limit=10,
            remaining=5,
            resets_at="2025-01-01T00:00:00+00:00",
            is_exceeded=False,
        )

        quota = _get_daily_email_quota(mock_table, user_id)

        assert "used" in quota
        assert "limit" in quota
        assert "resets_at" in quota
        assert quota["limit"] == ALERT_LIMITS["max_emails_per_day"]


class TestAlertResponseFormatting:
    """Tests for alert response formatting."""

    @patch("src.lambdas.dashboard.alerts.xray_recorder")
    def test_formats_timestamps_correctly(
        self, mock_xray, mock_table, user_id, sample_alert_item
    ):
        """Formats timestamps as ISO with Z suffix."""
        # Add last_triggered_at
        sample_alert_item["last_triggered_at"] = "2025-11-25T14:30:00+00:00"
        mock_table.get_item.return_value = {"Item": sample_alert_item}

        result = get_alert(mock_table, user_id, sample_alert_item["alert_id"])

        assert result.created_at.endswith("Z")
        assert result.last_triggered_at.endswith("Z")
        assert "+00:00" not in result.created_at

    @patch("src.lambdas.dashboard.alerts.xray_recorder")
    def test_handles_null_last_triggered(
        self, mock_xray, mock_table, user_id, sample_alert_item
    ):
        """Handles null last_triggered_at."""
        mock_table.get_item.return_value = {"Item": sample_alert_item}

        result = get_alert(mock_table, user_id, sample_alert_item["alert_id"])

        assert result.last_triggered_at is None
