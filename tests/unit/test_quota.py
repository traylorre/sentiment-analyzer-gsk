"""Unit tests for alert quota tracking."""

from datetime import UTC, datetime
from unittest.mock import MagicMock, patch

import pytest

from src.lambdas.dashboard.quota import (
    QuotaExceededError,
    QuotaStatus,
    check_quota_available,
    get_daily_quota,
    get_user_total_alerts,
    increment_email_quota,
)


class TestQuotaStatus:
    """Tests for QuotaStatus model."""

    def test_quota_status_creation(self):
        """Test QuotaStatus model creation."""
        status = QuotaStatus(
            used=5,
            limit=10,
            remaining=5,
            resets_at="2025-01-01T00:00:00+00:00",
            is_exceeded=False,
        )
        assert status.used == 5
        assert status.limit == 10
        assert status.remaining == 5
        assert status.is_exceeded is False

    def test_quota_status_exceeded(self):
        """Test QuotaStatus when quota is exceeded."""
        status = QuotaStatus(
            used=10,
            limit=10,
            remaining=0,
            resets_at="2025-01-01T00:00:00+00:00",
            is_exceeded=True,
        )
        assert status.is_exceeded is True
        assert status.remaining == 0


class TestGetDailyQuota:
    """Tests for get_daily_quota function."""

    def test_get_daily_quota_no_existing_record(self):
        """Test getting quota when no record exists."""
        mock_table = MagicMock()
        mock_table.get_item.return_value = {}

        result = get_daily_quota(mock_table, "user123")

        assert result.used == 0
        assert result.limit == 10
        assert result.remaining == 10
        assert result.is_exceeded is False

    def test_get_daily_quota_with_existing_record(self):
        """Test getting quota with existing usage."""
        mock_table = MagicMock()
        mock_table.get_item.return_value = {"Item": {"email_count": 7}}

        result = get_daily_quota(mock_table, "user123")

        assert result.used == 7
        assert result.remaining == 3
        assert result.is_exceeded is False

    def test_get_daily_quota_exceeded(self):
        """Test getting quota when exceeded."""
        mock_table = MagicMock()
        mock_table.get_item.return_value = {"Item": {"email_count": 10}}

        result = get_daily_quota(mock_table, "user123")

        assert result.used == 10
        assert result.remaining == 0
        assert result.is_exceeded is True

    def test_get_daily_quota_resets_at_tomorrow(self):
        """Test that resets_at is set to midnight UTC tomorrow."""
        mock_table = MagicMock()
        mock_table.get_item.return_value = {}

        with patch("src.lambdas.dashboard.quota.datetime") as mock_dt:
            # Mock current time to 2025-01-15 10:30:00 UTC
            mock_now = datetime(2025, 1, 15, 10, 30, 0, tzinfo=UTC)
            mock_dt.now.return_value = mock_now
            mock_dt.combine = datetime.combine
            mock_dt.min = datetime.min

            result = get_daily_quota(mock_table, "user123")

            # Should reset at 2025-01-16 00:00:00 UTC
            assert "2025-01-16T00:00:00" in result.resets_at

    def test_get_daily_quota_error_handling(self):
        """Test graceful handling of DynamoDB errors."""
        mock_table = MagicMock()
        mock_table.get_item.side_effect = Exception("DynamoDB error")

        result = get_daily_quota(mock_table, "user123")

        # Should return 0 on error
        assert result.used == 0
        assert result.remaining == 10


class TestIncrementEmailQuota:
    """Tests for increment_email_quota function."""

    def test_increment_quota_success(self):
        """Test successful quota increment."""
        mock_table = MagicMock()
        mock_table.update_item.return_value = {"Attributes": {"email_count": 1}}

        result = increment_email_quota(mock_table, "user123")

        assert result.used == 1
        mock_table.update_item.assert_called_once()

    def test_increment_quota_to_limit(self):
        """Test incrementing quota to the limit."""
        mock_table = MagicMock()
        mock_table.update_item.return_value = {"Attributes": {"email_count": 10}}

        result = increment_email_quota(mock_table, "user123")

        assert result.used == 10
        assert result.is_exceeded is True

    def test_increment_quota_exceeded_raises_error(self):
        """Test that exceeding quota raises QuotaExceededError."""
        mock_table = MagicMock()

        # Create mock client with exception class
        mock_client = MagicMock()
        mock_client.exceptions.ConditionalCheckFailedException = type(
            "ConditionalCheckFailedException", (Exception,), {}
        )
        mock_table.meta.client = mock_client
        mock_table.update_item.side_effect = (
            mock_client.exceptions.ConditionalCheckFailedException()
        )

        # Mock get_item for the error path
        mock_table.get_item.return_value = {"Item": {"email_count": 10}}

        with pytest.raises(QuotaExceededError) as exc_info:
            increment_email_quota(mock_table, "user123")

        assert exc_info.value.used == 10
        assert exc_info.value.limit == 10

    def test_increment_quota_uses_atomic_counter(self):
        """Test that increment uses DynamoDB atomic counter."""
        mock_table = MagicMock()
        mock_table.update_item.return_value = {"Attributes": {"email_count": 5}}

        increment_email_quota(mock_table, "user123")

        call_args = mock_table.update_item.call_args
        update_expr = call_args.kwargs["UpdateExpression"]
        assert "if_not_exists" in update_expr
        assert "+ :inc" in update_expr


class TestCheckQuotaAvailable:
    """Tests for check_quota_available function."""

    def test_quota_available_when_under_limit(self):
        """Test quota available when under limit."""
        mock_table = MagicMock()
        mock_table.get_item.return_value = {"Item": {"email_count": 5}}

        result = check_quota_available(mock_table, "user123")

        assert result is True

    def test_quota_not_available_when_at_limit(self):
        """Test quota not available when at limit."""
        mock_table = MagicMock()
        mock_table.get_item.return_value = {"Item": {"email_count": 10}}

        result = check_quota_available(mock_table, "user123")

        assert result is False

    def test_quota_available_with_count_param(self):
        """Test quota available with specific count."""
        mock_table = MagicMock()
        mock_table.get_item.return_value = {"Item": {"email_count": 7}}

        # 3 remaining, asking for 3
        result = check_quota_available(mock_table, "user123", count=3)
        assert result is True

        # 3 remaining, asking for 4
        result = check_quota_available(mock_table, "user123", count=4)
        assert result is False


class TestGetUserTotalAlerts:
    """Tests for get_user_total_alerts function."""

    def test_get_total_alerts_success(self):
        """Test getting total alert count."""
        mock_table = MagicMock()
        mock_table.query.return_value = {"Count": 15}

        result = get_user_total_alerts(mock_table, "user123")

        assert result == 15

    def test_get_total_alerts_no_alerts(self):
        """Test getting total when no alerts exist."""
        mock_table = MagicMock()
        mock_table.query.return_value = {"Count": 0}

        result = get_user_total_alerts(mock_table, "user123")

        assert result == 0

    def test_get_total_alerts_error_returns_zero(self):
        """Test error handling returns zero."""
        mock_table = MagicMock()
        mock_table.query.side_effect = Exception("DynamoDB error")

        result = get_user_total_alerts(mock_table, "user123")

        assert result == 0


class TestQuotaExceededError:
    """Tests for QuotaExceededError exception."""

    def test_error_creation(self):
        """Test QuotaExceededError creation."""
        error = QuotaExceededError(
            used=10, limit=10, resets_at="2025-01-01T00:00:00+00:00"
        )
        assert error.used == 10
        assert error.limit == 10
        assert "2025-01-01" in error.resets_at
        assert "10/10" in str(error)
