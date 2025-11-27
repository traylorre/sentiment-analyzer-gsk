"""Unit tests for rate limiting middleware (T164)."""

from unittest.mock import MagicMock

import pytest

from src.lambdas.shared.middleware.rate_limit import (
    DEFAULT_RATE_LIMITS,
    RateLimitExceeded,
    RateLimitResult,
    check_rate_limit,
    get_client_ip,
    get_rate_limit_headers,
)


class TestGetClientIp:
    """Tests for get_client_ip function."""

    def test_api_gateway_v2_http_api(self):
        """Extracts IP from API Gateway v2 HTTP API event."""
        event = {
            "requestContext": {
                "http": {
                    "sourceIp": "1.2.3.4",
                }
            }
        }
        assert get_client_ip(event) == "1.2.3.4"

    def test_api_gateway_v1_rest_api(self):
        """Extracts IP from API Gateway v1 REST API event."""
        event = {
            "requestContext": {
                "identity": {
                    "sourceIp": "5.6.7.8",
                }
            }
        }
        assert get_client_ip(event) == "5.6.7.8"

    def test_function_url(self):
        """Extracts IP from Lambda Function URL event."""
        event = {
            "requestContext": {
                "sourceIp": "9.10.11.12",
            }
        }
        assert get_client_ip(event) == "9.10.11.12"

    def test_x_forwarded_for_single(self):
        """Extracts IP from X-Forwarded-For header (single IP)."""
        event = {
            "headers": {
                "x-forwarded-for": "13.14.15.16",
            }
        }
        assert get_client_ip(event) == "13.14.15.16"

    def test_x_forwarded_for_multiple(self):
        """Extracts first IP from X-Forwarded-For header (multiple IPs)."""
        event = {
            "headers": {
                "x-forwarded-for": "17.18.19.20, 21.22.23.24, 25.26.27.28",
            }
        }
        assert get_client_ip(event) == "17.18.19.20"

    def test_x_forwarded_for_case_insensitive(self):
        """Handles case-insensitive X-Forwarded-For header."""
        event = {
            "headers": {
                "X-Forwarded-For": "29.30.31.32",
            }
        }
        assert get_client_ip(event) == "29.30.31.32"

    def test_fallback_unknown(self):
        """Returns 'unknown' when IP cannot be determined."""
        event = {"headers": {}}
        assert get_client_ip(event) == "unknown"

    def test_empty_event(self):
        """Returns 'unknown' for empty event."""
        assert get_client_ip({}) == "unknown"


class TestCheckRateLimit:
    """Tests for check_rate_limit function."""

    @pytest.fixture
    def mock_table(self):
        """Create mock DynamoDB table."""
        return MagicMock()

    def test_allows_within_limit(self, mock_table):
        """Allows requests within limit."""
        mock_table.query.return_value = {"Items": []}

        result = check_rate_limit(mock_table, "1.2.3.4", "config_create")

        assert result.allowed is True
        assert result.remaining >= 0
        mock_table.put_item.assert_called_once()

    def test_blocks_when_limit_exceeded(self, mock_table):
        """Blocks requests when limit exceeded."""
        # Return items equal to the limit
        limit = DEFAULT_RATE_LIMITS["config_create"]["limit"]
        mock_table.query.return_value = {"Items": [{"id": i} for i in range(limit)]}

        result = check_rate_limit(mock_table, "1.2.3.4", "config_create")

        assert result.allowed is False
        assert result.remaining == 0
        assert result.retry_after is not None

    def test_uses_custom_limit(self, mock_table):
        """Uses custom limit when provided."""
        mock_table.query.return_value = {"Items": [{"id": "1"}, {"id": "2"}]}

        result = check_rate_limit(mock_table, "1.2.3.4", "default", custom_limit=2)

        assert result.allowed is False

    def test_uses_custom_window(self, mock_table):
        """Uses custom window when provided."""
        mock_table.query.return_value = {"Items": []}

        result = check_rate_limit(
            mock_table, "1.2.3.4", "default", custom_window=300  # 5 minutes
        )

        assert result.allowed is True
        mock_table.query.assert_called_once()

    def test_uses_user_id_for_authenticated(self, mock_table):
        """Uses user_id for rate key when authenticated."""
        mock_table.query.return_value = {"Items": []}

        check_rate_limit(mock_table, "1.2.3.4", "config_create", user_id="user-123")

        # Verify PK uses user_id
        call_args = mock_table.query.call_args[1]
        pk_value = call_args["ExpressionAttributeValues"][":pk"]
        assert "USER#user-123" in pk_value

    def test_handles_error_gracefully(self, mock_table):
        """Returns allowed=True on error (fail open)."""
        mock_table.query.side_effect = Exception("DB error")

        result = check_rate_limit(mock_table, "1.2.3.4", "config_create")

        assert result.allowed is True

    def test_default_action_fallback(self, mock_table):
        """Uses default limits for unknown action."""
        mock_table.query.return_value = {"Items": []}

        result = check_rate_limit(mock_table, "1.2.3.4", "unknown_action")

        assert result.allowed is True
        assert result.limit == DEFAULT_RATE_LIMITS["default"]["limit"]


class TestGetRateLimitHeaders:
    """Tests for get_rate_limit_headers function."""

    def test_returns_standard_headers(self):
        """Returns standard rate limit headers."""
        result = RateLimitResult(
            allowed=True,
            limit=100,
            remaining=99,
            reset_at="2025-11-26T13:00:00Z",
        )

        headers = get_rate_limit_headers(result)

        assert headers["X-RateLimit-Limit"] == "100"
        assert headers["X-RateLimit-Remaining"] == "99"
        assert headers["X-RateLimit-Reset"] == "2025-11-26T13:00:00Z"

    def test_includes_retry_after_when_exceeded(self):
        """Includes Retry-After when rate limited."""
        result = RateLimitResult(
            allowed=False,
            limit=100,
            remaining=0,
            reset_at="2025-11-26T13:00:00Z",
            retry_after=60,
        )

        headers = get_rate_limit_headers(result)

        assert headers["Retry-After"] == "60"

    def test_no_retry_after_when_allowed(self):
        """No Retry-After when request allowed."""
        result = RateLimitResult(
            allowed=True,
            limit=100,
            remaining=99,
            reset_at="2025-11-26T13:00:00Z",
        )

        headers = get_rate_limit_headers(result)

        assert "Retry-After" not in headers


class TestRateLimitExceeded:
    """Tests for RateLimitExceeded exception."""

    def test_default_values(self):
        """Has sensible defaults."""
        exc = RateLimitExceeded()
        assert str(exc) == "Rate limit exceeded"
        assert exc.retry_after == 60

    def test_custom_values(self):
        """Accepts custom values."""
        exc = RateLimitExceeded(
            message="Too many requests",
            retry_after=120,
            limit=10,
            remaining=0,
        )
        assert str(exc) == "Too many requests"
        assert exc.retry_after == 120
        assert exc.limit == 10
        assert exc.remaining == 0


class TestRateLimitResult:
    """Tests for RateLimitResult model."""

    def test_allowed_result(self):
        """Creates allowed result."""
        result = RateLimitResult(
            allowed=True,
            limit=100,
            remaining=50,
            reset_at="2025-11-26T13:00:00Z",
        )
        assert result.allowed is True
        assert result.retry_after is None

    def test_blocked_result(self):
        """Creates blocked result."""
        result = RateLimitResult(
            allowed=False,
            limit=100,
            remaining=0,
            reset_at="2025-11-26T13:00:00Z",
            retry_after=300,
        )
        assert result.allowed is False
        assert result.retry_after == 300


class TestDefaultRateLimits:
    """Tests for default rate limit configuration."""

    def test_has_required_actions(self):
        """Has all required action configurations."""
        required_actions = [
            "config_create",
            "ticker_validate",
            "ticker_search",
            "anonymous_session",
            "auth_config_create",
            "alert_create",
            "magic_link_request",
            "default",
        ]

        for action in required_actions:
            assert action in DEFAULT_RATE_LIMITS
            assert "limit" in DEFAULT_RATE_LIMITS[action]
            assert "window_seconds" in DEFAULT_RATE_LIMITS[action]

    def test_limits_are_positive(self):
        """All limits are positive integers."""
        for action, config in DEFAULT_RATE_LIMITS.items():
            assert config["limit"] > 0, f"{action} limit should be positive"
            assert config["window_seconds"] > 0, f"{action} window should be positive"

    def test_anonymous_more_restrictive(self):
        """Anonymous limits are more restrictive than authenticated."""
        assert (
            DEFAULT_RATE_LIMITS["config_create"]["limit"]
            < DEFAULT_RATE_LIMITS["auth_config_create"]["limit"]
        )
