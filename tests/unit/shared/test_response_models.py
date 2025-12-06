"""Unit tests for response model helper functions.

Tests utility functions for secure frontend data transformation.
"""

from datetime import UTC, datetime, timedelta

from src.lambdas.shared.response_models import mask_email, seconds_until


class TestMaskEmail:
    """Tests for email masking function."""

    def test_mask_email_none(self):
        """Should return None for None input."""
        assert mask_email(None) is None

    def test_mask_email_empty(self):
        """Should return None for empty string."""
        assert mask_email("") is None

    def test_mask_email_normal(self):
        """Should mask normal email correctly."""
        result = mask_email("john@example.com")
        assert result == "j***@example.com"

    def test_mask_email_single_char_local(self):
        """Should handle single character local part."""
        result = mask_email("j@example.com")
        assert result == "*@example.com"

    def test_mask_email_invalid_format(self):
        """Should return masked string for invalid email."""
        result = mask_email("not-an-email")
        assert result == "***"


class TestSecondsUntil:
    """Tests for datetime to seconds conversion."""

    def test_seconds_until_none(self):
        """Should return None for None input."""
        assert seconds_until(None) is None

    def test_seconds_until_future(self):
        """Should return positive seconds for future datetime."""
        future = datetime.now(UTC) + timedelta(minutes=5)
        result = seconds_until(future)
        assert result is not None
        assert 290 <= result <= 310  # Approximately 5 minutes

    def test_seconds_until_past(self):
        """Should return 0 for past datetime (not negative)."""
        past = datetime.now(UTC) - timedelta(minutes=5)
        result = seconds_until(past)
        assert result == 0

    def test_seconds_until_naive_datetime(self):
        """Should handle naive datetime by assuming UTC."""
        future = datetime.now(UTC) + timedelta(seconds=60)
        result = seconds_until(future)
        assert result is not None
        # Should be approximately 60 seconds (with some tolerance for test execution)
        assert 50 <= result <= 70
