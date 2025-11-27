"""Unit tests for alert evaluator (T145-T147)."""

import uuid
from datetime import UTC, datetime, timedelta
from unittest.mock import MagicMock, patch

import pytest

from src.lambdas.notification.alert_evaluator import (
    AlertTriggerDetail,
    AlertUpdates,
    EmailQuotaResponse,
    EvaluateAlertsRequest,
    EvaluateAlertsResponse,
    SentimentUpdate,
    _check_email_quota,
    _evaluate_threshold,
    _find_alerts_by_ticker,
    _increment_global_quota,
    _increment_user_quota,
    _is_in_cooldown,
    _queue_notification,
    _update_alert_triggered,
    evaluate_alerts_for_ticker,
    get_email_quota_status,
    verify_internal_auth,
)
from src.lambdas.shared.models.alert_rule import AlertRule


@pytest.fixture
def mock_table():
    """Create a mock DynamoDB table."""
    return MagicMock()


@pytest.fixture
def user_id():
    """Generate a user ID."""
    return str(uuid.uuid4())


@pytest.fixture
def alert_id():
    """Generate an alert ID."""
    return str(uuid.uuid4())


@pytest.fixture
def config_id():
    """Generate a config ID."""
    return str(uuid.uuid4())


@pytest.fixture
def sample_alert(user_id, alert_id, config_id):
    """Create a sample alert."""
    return AlertRule(
        alert_id=alert_id,
        user_id=user_id,
        config_id=config_id,
        ticker="AAPL",
        alert_type="sentiment_threshold",
        threshold_value=-0.3,
        threshold_direction="below",
        is_enabled=True,
        trigger_count=0,
        created_at=datetime.now(UTC),
    )


@pytest.fixture
def sample_alert_item(user_id, alert_id, config_id):
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
        "created_at": datetime.now(UTC).isoformat(),
        "entity_type": "ALERT_RULE",
    }


class TestEvaluateThreshold:
    """Tests for _evaluate_threshold helper."""

    def test_above_threshold_triggered(self):
        """Triggers when value exceeds threshold (above direction)."""
        assert _evaluate_threshold(0.5, 0.3, "above") is True
        assert _evaluate_threshold(0.3, 0.3, "above") is False
        assert _evaluate_threshold(0.2, 0.3, "above") is False

    def test_below_threshold_triggered(self):
        """Triggers when value drops below threshold (below direction)."""
        assert _evaluate_threshold(-0.5, -0.3, "below") is True
        assert _evaluate_threshold(-0.3, -0.3, "below") is False
        assert _evaluate_threshold(-0.2, -0.3, "below") is False

    def test_exact_threshold_not_triggered(self):
        """Exact threshold value doesn't trigger (need to cross)."""
        assert _evaluate_threshold(0.3, 0.3, "above") is False
        assert _evaluate_threshold(-0.3, -0.3, "below") is False


class TestIsInCooldown:
    """Tests for _is_in_cooldown helper."""

    def test_no_previous_trigger(self, sample_alert):
        """Not in cooldown if never triggered."""
        assert _is_in_cooldown(sample_alert) is False

    def test_recent_trigger_in_cooldown(self, sample_alert):
        """In cooldown if triggered within cooldown period."""
        sample_alert.last_triggered_at = datetime.now(UTC) - timedelta(minutes=30)
        assert _is_in_cooldown(sample_alert) is True

    def test_old_trigger_not_in_cooldown(self, sample_alert):
        """Not in cooldown if triggered outside cooldown period."""
        sample_alert.last_triggered_at = datetime.now(UTC) - timedelta(hours=2)
        assert _is_in_cooldown(sample_alert) is False


class TestCheckEmailQuota:
    """Tests for _check_email_quota helper."""

    def test_returns_true_under_quota(self, mock_table, user_id):
        """Returns True when user is under quota."""
        mock_table.get_item.return_value = {"Item": {"count": 5}}

        result = _check_email_quota(mock_table, user_id)

        assert result is True

    def test_returns_false_at_quota(self, mock_table, user_id):
        """Returns False when user is at quota."""
        mock_table.get_item.return_value = {"Item": {"count": 10}}

        result = _check_email_quota(mock_table, user_id)

        assert result is False

    def test_returns_true_no_record(self, mock_table, user_id):
        """Returns True when no quota record exists."""
        mock_table.get_item.return_value = {}

        result = _check_email_quota(mock_table, user_id)

        assert result is True

    def test_returns_true_on_error(self, mock_table, user_id):
        """Returns True (allows) on error."""
        mock_table.get_item.side_effect = Exception("DB error")

        result = _check_email_quota(mock_table, user_id)

        assert result is True


class TestFindAlertsByTicker:
    """Tests for _find_alerts_by_ticker helper."""

    def test_finds_alerts(self, mock_table, sample_alert_item):
        """Finds alerts for ticker."""
        mock_table.scan.return_value = {"Items": [sample_alert_item]}

        alerts = _find_alerts_by_ticker(mock_table, "AAPL")

        assert len(alerts) == 1
        assert alerts[0].ticker == "AAPL"

    def test_returns_empty_when_none(self, mock_table):
        """Returns empty list when no alerts."""
        mock_table.scan.return_value = {"Items": []}

        alerts = _find_alerts_by_ticker(mock_table, "TSLA")

        assert len(alerts) == 0


class TestQueueNotification:
    """Tests for _queue_notification helper."""

    @patch("src.lambdas.notification.alert_evaluator._increment_user_quota")
    @patch("src.lambdas.notification.alert_evaluator._increment_global_quota")
    def test_queues_notification(
        self, mock_global, mock_user, mock_table, sample_alert
    ):
        """Queues notification successfully."""
        result = _queue_notification(mock_table, sample_alert, -0.42)

        assert result is not None
        mock_table.put_item.assert_called_once()
        mock_user.assert_called_once()
        mock_global.assert_called_once()

    def test_returns_none_on_error(self, mock_table, sample_alert):
        """Returns None on error."""
        mock_table.put_item.side_effect = Exception("DB error")

        result = _queue_notification(mock_table, sample_alert, -0.42)

        assert result is None


class TestUpdateAlertTriggered:
    """Tests for _update_alert_triggered helper."""

    def test_updates_alert(self, mock_table, sample_alert):
        """Updates alert trigger timestamp and count."""
        _update_alert_triggered(mock_table, sample_alert)

        mock_table.update_item.assert_called_once()
        call_kwargs = mock_table.update_item.call_args[1]
        assert "last_triggered_at" in call_kwargs["UpdateExpression"]
        assert "trigger_count" in call_kwargs["UpdateExpression"]


class TestIncrementUserQuota:
    """Tests for _increment_user_quota helper."""

    def test_increments_quota(self, mock_table, user_id):
        """Increments user quota."""
        _increment_user_quota(mock_table, user_id)

        mock_table.update_item.assert_called_once()


class TestIncrementGlobalQuota:
    """Tests for _increment_global_quota helper."""

    def test_increments_global_quota(self, mock_table):
        """Increments global quota."""
        _increment_global_quota(mock_table)

        mock_table.update_item.assert_called_once()
        call_kwargs = mock_table.update_item.call_args[1]
        assert call_kwargs["Key"]["PK"] == "EMAIL_QUOTA"


class TestEvaluateAlertsForTicker:
    """Tests for evaluate_alerts_for_ticker function."""

    @patch("src.lambdas.notification.alert_evaluator.xray_recorder")
    @patch("src.lambdas.notification.alert_evaluator._find_alerts_by_ticker")
    @patch("src.lambdas.notification.alert_evaluator._check_email_quota")
    @patch("src.lambdas.notification.alert_evaluator._queue_notification")
    @patch("src.lambdas.notification.alert_evaluator._update_alert_triggered")
    def test_evaluates_and_triggers_sentiment_alert(
        self,
        mock_update,
        mock_queue,
        mock_quota,
        mock_find,
        mock_xray,
        mock_table,
        sample_alert,
    ):
        """Evaluates sentiment alert and triggers when crossed."""
        mock_find.return_value = [sample_alert]
        mock_quota.return_value = True
        mock_queue.return_value = str(uuid.uuid4())

        result = evaluate_alerts_for_ticker(
            mock_table, "AAPL", sentiment_score=-0.5  # Below -0.3 threshold
        )

        assert isinstance(result, EvaluateAlertsResponse)
        assert result.evaluated == 1
        assert result.triggered == 1
        assert result.notifications_queued == 1

    @patch("src.lambdas.notification.alert_evaluator.xray_recorder")
    @patch("src.lambdas.notification.alert_evaluator._find_alerts_by_ticker")
    def test_skips_disabled_alerts(
        self, mock_find, mock_xray, mock_table, sample_alert
    ):
        """Skips disabled alerts."""
        sample_alert.is_enabled = False
        mock_find.return_value = [sample_alert]

        result = evaluate_alerts_for_ticker(mock_table, "AAPL", sentiment_score=-0.5)

        assert result.triggered == 0

    @patch("src.lambdas.notification.alert_evaluator.xray_recorder")
    @patch("src.lambdas.notification.alert_evaluator._find_alerts_by_ticker")
    def test_skips_alerts_in_cooldown(
        self, mock_find, mock_xray, mock_table, sample_alert
    ):
        """Skips alerts in cooldown."""
        sample_alert.last_triggered_at = datetime.now(UTC) - timedelta(minutes=30)
        mock_find.return_value = [sample_alert]

        result = evaluate_alerts_for_ticker(mock_table, "AAPL", sentiment_score=-0.5)

        assert result.triggered == 0

    @patch("src.lambdas.notification.alert_evaluator.xray_recorder")
    @patch("src.lambdas.notification.alert_evaluator._find_alerts_by_ticker")
    @patch("src.lambdas.notification.alert_evaluator._check_email_quota")
    def test_respects_email_quota(
        self, mock_quota, mock_find, mock_xray, mock_table, sample_alert
    ):
        """Doesn't queue notification when quota exceeded."""
        mock_find.return_value = [sample_alert]
        mock_quota.return_value = False  # Quota exceeded

        result = evaluate_alerts_for_ticker(mock_table, "AAPL", sentiment_score=-0.5)

        assert result.triggered == 1
        assert result.notifications_queued == 0

    @patch("src.lambdas.notification.alert_evaluator.xray_recorder")
    @patch("src.lambdas.notification.alert_evaluator._find_alerts_by_ticker")
    def test_evaluates_volatility_alert(
        self, mock_find, mock_xray, mock_table, sample_alert
    ):
        """Evaluates volatility alert."""
        sample_alert.alert_type = "volatility_threshold"
        sample_alert.threshold_value = 5.0
        sample_alert.threshold_direction = "above"
        mock_find.return_value = [sample_alert]

        result = evaluate_alerts_for_ticker(mock_table, "AAPL", volatility_atr=7.0)

        assert result.triggered == 1

    @patch("src.lambdas.notification.alert_evaluator.xray_recorder")
    @patch("src.lambdas.notification.alert_evaluator._find_alerts_by_ticker")
    def test_no_trigger_when_not_crossed(
        self, mock_find, mock_xray, mock_table, sample_alert
    ):
        """Doesn't trigger when threshold not crossed."""
        mock_find.return_value = [sample_alert]

        result = evaluate_alerts_for_ticker(
            mock_table, "AAPL", sentiment_score=0.5  # Above -0.3, not triggered
        )

        assert result.triggered == 0


class TestGetEmailQuotaStatus:
    """Tests for get_email_quota_status function."""

    @patch("src.lambdas.notification.alert_evaluator.xray_recorder")
    def test_returns_quota_status(self, mock_xray, mock_table):
        """Returns email quota status."""
        mock_table.get_item.return_value = {
            "Item": {
                "count": 47,
                "last_sent_at": "2025-11-26T15:30:00+00:00",
                "top_users": [{"user_id": "user1", "count": 8}],
            }
        }

        result = get_email_quota_status(mock_table)

        assert isinstance(result, EmailQuotaResponse)
        assert result.used_today == 47
        assert result.daily_limit == 100
        assert result.remaining == 53
        assert result.percent_used == 47.0
        assert result.alert_triggered is False  # < 50

    @patch("src.lambdas.notification.alert_evaluator.xray_recorder")
    def test_alert_triggered_at_threshold(self, mock_xray, mock_table):
        """Alert triggered when at 50% threshold."""
        mock_table.get_item.return_value = {"Item": {"count": 52}}

        result = get_email_quota_status(mock_table)

        assert result.alert_triggered is True

    @patch("src.lambdas.notification.alert_evaluator.xray_recorder")
    def test_returns_defaults_no_record(self, mock_xray, mock_table):
        """Returns defaults when no quota record."""
        mock_table.get_item.return_value = {}

        result = get_email_quota_status(mock_table)

        assert result.used_today == 0
        assert result.remaining == 100


class TestVerifyInternalAuth:
    """Tests for verify_internal_auth function."""

    @patch("src.lambdas.notification.alert_evaluator.INTERNAL_API_KEY", "secret123")
    def test_valid_auth(self):
        """Returns True for valid auth."""
        assert verify_internal_auth("secret123") is True

    @patch("src.lambdas.notification.alert_evaluator.INTERNAL_API_KEY", "secret123")
    def test_invalid_auth(self):
        """Returns False for invalid auth."""
        assert verify_internal_auth("wrong") is False

    @patch("src.lambdas.notification.alert_evaluator.INTERNAL_API_KEY", "")
    @patch.dict("os.environ", {"ENVIRONMENT": "dev"})
    def test_allows_dev_without_key(self):
        """Allows dev environment without key."""
        assert verify_internal_auth(None) is True

    @patch("src.lambdas.notification.alert_evaluator.INTERNAL_API_KEY", "")
    @patch.dict("os.environ", {"ENVIRONMENT": "prod"})
    def test_rejects_prod_without_key(self):
        """Rejects prod environment without key."""
        assert verify_internal_auth(None) is False


class TestRequestResponseSchemas:
    """Tests for Pydantic request/response schemas."""

    def test_evaluate_request_schema(self):
        """EvaluateAlertsRequest parses correctly."""
        request = EvaluateAlertsRequest(
            ticker="AAPL",
            updates=AlertUpdates(
                sentiment=SentimentUpdate(
                    score=-0.42,
                    source="tiingo",
                    timestamp="2025-11-26T10:00:00Z",
                )
            ),
        )

        assert request.ticker == "AAPL"
        assert request.updates.sentiment.score == -0.42

    def test_evaluate_response_schema(self):
        """EvaluateAlertsResponse serializes correctly."""
        response = EvaluateAlertsResponse(
            evaluated=10,
            triggered=2,
            notifications_queued=2,
            details=[
                AlertTriggerDetail(
                    alert_id="abc123",
                    user_id="user1",
                    triggered=True,
                    current_value=-0.42,
                    threshold=-0.3,
                    notification_id="notif1",
                )
            ],
        )

        assert response.evaluated == 10
        assert len(response.details) == 1

    def test_email_quota_response_schema(self):
        """EmailQuotaResponse serializes correctly."""
        response = EmailQuotaResponse(
            daily_limit=100,
            used_today=47,
            remaining=53,
            percent_used=47.0,
            reset_at="2025-11-27T00:00:00Z",
            alert_threshold=50,
            alert_triggered=False,
            alert_triggered_at=None,
            last_email_sent_at="2025-11-26T15:30:00Z",
            top_users=[{"user_id": "user1", "count": 8}],
        )

        assert response.daily_limit == 100
        assert response.remaining == 53
