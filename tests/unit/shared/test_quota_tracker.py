"""Unit tests for QuotaTracker."""

from datetime import UTC, datetime

from src.lambdas.shared.quota_tracker import APIQuotaUsage, QuotaTracker


class TestAPIQuotaUsage:
    """Tests for APIQuotaUsage class."""

    def test_percent_used_calculation(self):
        """Test percentage calculation."""
        quota = APIQuotaUsage(
            service="tiingo",
            period="month",
            limit=100,
            used=25,
            remaining=75,
            reset_at=datetime.now(UTC),
        )

        assert quota.percent_used == 25.0

    def test_percent_used_zero_limit(self):
        """Test percentage with zero limit."""
        quota = APIQuotaUsage(
            service="tiingo",
            period="month",
            limit=0,
            used=0,
            remaining=0,
            reset_at=datetime.now(UTC),
        )

        assert quota.percent_used == 0

    def test_is_warning_threshold(self):
        """Test warning threshold detection."""
        quota = APIQuotaUsage(
            service="finnhub",
            period="minute",
            limit=100,
            used=50,
            remaining=50,
            reset_at=datetime.now(UTC),
            warn_threshold=0.5,
        )

        assert quota.is_warning is True

        quota.used = 49
        quota.remaining = 51
        assert quota.is_warning is False

    def test_is_critical_threshold(self):
        """Test critical threshold detection."""
        quota = APIQuotaUsage(
            service="sendgrid",
            period="day",
            limit=100,
            used=80,
            remaining=20,
            reset_at=datetime.now(UTC),
            critical_threshold=0.8,
        )

        assert quota.is_critical is True

        quota.used = 79
        quota.remaining = 21
        assert quota.is_critical is False


class TestQuotaTracker:
    """Tests for QuotaTracker class."""

    def test_create_default(self):
        """Test creating default quota tracker."""
        tracker = QuotaTracker.create_default()

        assert tracker.tiingo.limit == 500
        assert tracker.tiingo.period == "month"
        assert tracker.finnhub.limit == 60
        assert tracker.finnhub.period == "minute"
        assert tracker.sendgrid.limit == 100
        assert tracker.sendgrid.period == "day"
        assert tracker.total_api_calls_today == 0

    def test_can_call_with_remaining(self):
        """Test can_call when quota available."""
        tracker = QuotaTracker.create_default()

        assert tracker.can_call("tiingo") is True
        assert tracker.can_call("finnhub") is True
        assert tracker.can_call("sendgrid") is True

    def test_can_call_no_remaining(self):
        """Test can_call when quota exhausted."""
        tracker = QuotaTracker.create_default()
        tracker.tiingo.used = 500
        tracker.tiingo.remaining = 0

        assert tracker.can_call("tiingo") is False

    def test_can_call_at_critical(self):
        """Test can_call blocks at critical threshold."""
        tracker = QuotaTracker.create_default()
        tracker.finnhub.used = 54  # 90% of 60
        tracker.finnhub.remaining = 6

        assert tracker.can_call("finnhub") is False

    def test_record_call_updates_usage(self):
        """Test recording calls updates quota."""
        tracker = QuotaTracker.create_default()

        tracker.record_call("tiingo", 5)

        assert tracker.tiingo.used == 5
        assert tracker.tiingo.remaining == 495
        assert tracker.total_api_calls_today == 5

    def test_record_call_multiple_services(self):
        """Test recording calls to multiple services."""
        tracker = QuotaTracker.create_default()

        tracker.record_call("tiingo", 10)
        tracker.record_call("finnhub", 5)
        tracker.record_call("sendgrid", 2)

        assert tracker.tiingo.used == 10
        assert tracker.finnhub.used == 5
        assert tracker.sendgrid.used == 2
        assert tracker.total_api_calls_today == 17

    def test_record_call_doesnt_go_negative(self):
        """Test remaining doesn't go below zero."""
        tracker = QuotaTracker.create_default()
        tracker.tiingo.used = 495
        tracker.tiingo.remaining = 5

        tracker.record_call("tiingo", 10)

        assert tracker.tiingo.remaining == 0

    def test_get_reserve_allocation(self):
        """Test reserve allocation calculation."""
        tracker = QuotaTracker.create_default()

        assert tracker.get_reserve_allocation("tiingo") == 50  # 10% of 500
        assert tracker.get_reserve_allocation("finnhub") == 6  # 10% of 60
        assert tracker.get_reserve_allocation("sendgrid") == 10  # 10% of 100

    def test_pk_sk_properties(self):
        """Test DynamoDB key properties."""
        tracker = QuotaTracker.create_default()

        assert tracker.pk == "SYSTEM#QUOTA"
        assert tracker.sk == datetime.now(UTC).strftime("%Y-%m-%d")

    def test_to_dynamodb_item(self):
        """Test conversion to DynamoDB item."""
        tracker = QuotaTracker.create_default()
        tracker.record_call("tiingo", 10)

        item = tracker.to_dynamodb_item()

        assert item["PK"] == "SYSTEM#QUOTA"
        assert item["entity_type"] == "QUOTA_TRACKER"
        assert "ttl" in item
        assert item["tiingo"]["used"] == 10
        assert item["total_api_calls_today"] == 10

    def test_from_dynamodb_item(self):
        """Test creating from DynamoDB item."""
        now = datetime.now(UTC)
        item = {
            "PK": "SYSTEM#QUOTA",
            "SK": "2025-01-01",
            "tracker_id": "QUOTA_TRACKER",
            "updated_at": now.isoformat(),
            "tiingo": {
                "service": "tiingo",
                "period": "month",
                "limit": 500,
                "used": 100,
                "remaining": 400,
                "reset_at": now.isoformat(),
            },
            "finnhub": {
                "service": "finnhub",
                "period": "minute",
                "limit": 60,
                "used": 30,
                "remaining": 30,
                "reset_at": now.isoformat(),
            },
            "sendgrid": {
                "service": "sendgrid",
                "period": "day",
                "limit": 100,
                "used": 50,
                "remaining": 50,
                "reset_at": now.isoformat(),
            },
            "total_api_calls_today": 180,
            "estimated_daily_cost": "1.50",
        }

        tracker = QuotaTracker.from_dynamodb_item(item)

        assert tracker.tiingo.used == 100
        assert tracker.finnhub.used == 30
        assert tracker.sendgrid.used == 50
        assert tracker.total_api_calls_today == 180
        assert tracker.estimated_daily_cost == 1.50

    def test_roundtrip_serialization(self):
        """Test serialization roundtrip."""
        tracker = QuotaTracker.create_default()
        tracker.record_call("tiingo", 25)
        tracker.record_call("finnhub", 10)
        tracker.record_call("sendgrid", 5)

        item = tracker.to_dynamodb_item()
        restored = QuotaTracker.from_dynamodb_item(item)

        assert restored.tiingo.used == tracker.tiingo.used
        assert restored.finnhub.used == tracker.finnhub.used
        assert restored.sendgrid.used == tracker.sendgrid.used
        assert restored.total_api_calls_today == tracker.total_api_calls_today
