"""Unit tests for Lambda environment guard on mock token generation.

Tests for feature 1128-guard-mock-tokens:
- US1: Production Lambda rejects mock token generation
- US2: Local development continues to work
- US3: Clear error messages for debugging
"""

import os
from unittest.mock import MagicMock, patch

import pytest

from src.lambdas.dashboard.auth import _generate_tokens
from src.lambdas.shared.models.user import User


@pytest.fixture
def mock_user() -> User:
    """Create a mock User object for testing."""
    user = MagicMock(spec=User)
    user.user_id = "test-user-12345678"
    return user


class TestLambdaEnvironmentGuard:
    """Test suite for Lambda environment guard on _generate_tokens()."""

    def test_lambda_environment_raises_runtime_error(self, mock_user: User) -> None:
        """US1: When AWS_LAMBDA_FUNCTION_NAME is set, RuntimeError is raised."""
        with patch.dict(os.environ, {"AWS_LAMBDA_FUNCTION_NAME": "dashboard-lambda"}):
            with pytest.raises(RuntimeError) as exc_info:
                _generate_tokens(mock_user)

            assert "Lambda environment" in str(exc_info.value)
            assert "Cognito" in str(exc_info.value)

    def test_local_environment_generates_tokens(self, mock_user: User) -> None:
        """US2: When AWS_LAMBDA_FUNCTION_NAME is not set, mock tokens are generated."""
        # Ensure env var is not set
        env = os.environ.copy()
        env.pop("AWS_LAMBDA_FUNCTION_NAME", None)

        with patch.dict(os.environ, env, clear=True):
            body_tokens, refresh_token = _generate_tokens(mock_user)

            # Verify tokens are generated
            assert body_tokens is not None
            assert refresh_token is not None

            # Verify token format (user_id[:8] = "test-use")
            assert body_tokens["id_token"] == "mock_id_token_test-use"
            assert body_tokens["access_token"] == "mock_access_token_test-use"
            assert body_tokens["expires_in"] == 3600
            assert refresh_token == "mock_refresh_token_test-use"

    def test_empty_env_var_allows_tokens(self, mock_user: User) -> None:
        """US2 Edge Case: Empty string env var is falsy, allows mock tokens."""
        with patch.dict(os.environ, {"AWS_LAMBDA_FUNCTION_NAME": ""}):
            # Should NOT raise - empty string is falsy in Python
            body_tokens, refresh_token = _generate_tokens(mock_user)

            assert body_tokens is not None
            assert refresh_token is not None

    def test_error_message_contains_cognito_guidance(self, mock_user: User) -> None:
        """US3: Error message explains that production must use Cognito tokens."""
        with patch.dict(os.environ, {"AWS_LAMBDA_FUNCTION_NAME": "prod-lambda"}):
            with pytest.raises(RuntimeError) as exc_info:
                _generate_tokens(mock_user)

            error_message = str(exc_info.value)
            assert "Cognito" in error_message
            assert "production" in error_message

    def test_error_message_mentions_mock_disabled(self, mock_user: User) -> None:
        """US3: Error message clearly states mock tokens are disabled."""
        with patch.dict(os.environ, {"AWS_LAMBDA_FUNCTION_NAME": "any-lambda"}):
            with pytest.raises(RuntimeError) as exc_info:
                _generate_tokens(mock_user)

            error_message = str(exc_info.value)
            assert "Mock token generation is disabled" in error_message

    @patch("src.lambdas.dashboard.auth.logger")
    def test_blocked_attempt_is_logged_at_error_level(
        self, mock_logger: MagicMock, mock_user: User
    ) -> None:
        """FR-005: Blocked attempts are logged at ERROR level for security monitoring."""
        with patch.dict(os.environ, {"AWS_LAMBDA_FUNCTION_NAME": "lambda-func"}):
            with pytest.raises(RuntimeError):
                _generate_tokens(mock_user)

            # Verify logger.error was called
            mock_logger.error.assert_called_once()
            log_message = mock_logger.error.call_args[0][0]
            assert "SECURITY" in log_message
            assert "blocked" in log_message

    def test_token_format_unchanged_for_local_dev(self, mock_user: User) -> None:
        """FR-004: Token format remains unchanged for backward compatibility."""
        env = os.environ.copy()
        env.pop("AWS_LAMBDA_FUNCTION_NAME", None)

        with patch.dict(os.environ, env, clear=True):
            body_tokens, refresh_token = _generate_tokens(mock_user)

            # Verify exact format matches original implementation
            assert "id_token" in body_tokens
            assert "access_token" in body_tokens
            assert "expires_in" in body_tokens
            assert "refresh_token" not in body_tokens  # Never in body

            # Verify format pattern
            assert body_tokens["id_token"].startswith("mock_id_token_")
            assert body_tokens["access_token"].startswith("mock_access_token_")
            assert refresh_token.startswith("mock_refresh_token_")
