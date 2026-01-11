"""Unit tests for AUTH_013-AUTH_018 error codes (Feature 1190 / A23).

These tests verify:
- All error codes are defined
- Messages don't leak role information
- Status codes are correct (400 for bad request, 401 for auth failure)
- Helper functions work correctly
"""

import pytest

from src.lambdas.shared.errors.auth_errors import (
    AUTH_ERROR_MESSAGES,
    AUTH_ERROR_STATUS,
    AuthError,
    AuthErrorCode,
    auth_error_response,
    raise_auth_error,
)


class TestAuthErrorCodeDefinitions:
    """Test that all error codes are properly defined."""

    def test_auth_013_defined(self) -> None:
        """AUTH_013: Credentials changed."""
        assert AuthErrorCode.AUTH_013 == "AUTH_013"
        assert AuthErrorCode.AUTH_013 in AUTH_ERROR_MESSAGES
        assert AuthErrorCode.AUTH_013 in AUTH_ERROR_STATUS

    def test_auth_014_defined(self) -> None:
        """AUTH_014: Session limit exceeded."""
        assert AuthErrorCode.AUTH_014 == "AUTH_014"
        assert AuthErrorCode.AUTH_014 in AUTH_ERROR_MESSAGES
        assert AuthErrorCode.AUTH_014 in AUTH_ERROR_STATUS

    def test_auth_015_defined(self) -> None:
        """AUTH_015: Unknown OAuth provider."""
        assert AuthErrorCode.AUTH_015 == "AUTH_015"
        assert AuthErrorCode.AUTH_015 in AUTH_ERROR_MESSAGES
        assert AuthErrorCode.AUTH_015 in AUTH_ERROR_STATUS

    def test_auth_016_defined(self) -> None:
        """AUTH_016: OAuth provider mismatch."""
        assert AuthErrorCode.AUTH_016 == "AUTH_016"
        assert AuthErrorCode.AUTH_016 in AUTH_ERROR_MESSAGES
        assert AuthErrorCode.AUTH_016 in AUTH_ERROR_STATUS

    def test_auth_017_defined(self) -> None:
        """AUTH_017: Password requirements not met."""
        assert AuthErrorCode.AUTH_017 == "AUTH_017"
        assert AuthErrorCode.AUTH_017 in AUTH_ERROR_MESSAGES
        assert AuthErrorCode.AUTH_017 in AUTH_ERROR_STATUS

    def test_auth_018_defined(self) -> None:
        """AUTH_018: Token audience invalid."""
        assert AuthErrorCode.AUTH_018 == "AUTH_018"
        assert AuthErrorCode.AUTH_018 in AUTH_ERROR_MESSAGES
        assert AuthErrorCode.AUTH_018 in AUTH_ERROR_STATUS


class TestAuthErrorMessages:
    """Test that error messages don't leak sensitive information."""

    @pytest.mark.parametrize(
        "code,expected_message",
        [
            (AuthErrorCode.AUTH_013, "Credentials have been changed"),
            (AuthErrorCode.AUTH_014, "Session limit exceeded"),
            (AuthErrorCode.AUTH_015, "Unknown OAuth provider"),
            (AuthErrorCode.AUTH_016, "OAuth provider mismatch"),
            (AuthErrorCode.AUTH_017, "Password requirements not met"),
            (AuthErrorCode.AUTH_018, "Token audience invalid"),
        ],
    )
    def test_message_content(self, code: AuthErrorCode, expected_message: str) -> None:
        """Verify each error code has the correct message."""
        assert AUTH_ERROR_MESSAGES[code] == expected_message

    def test_messages_dont_leak_roles(self) -> None:
        """Verify no message contains role information."""
        forbidden_terms = ["admin", "operator", "paid", "free", "tier", "role"]
        for code, message in AUTH_ERROR_MESSAGES.items():
            message_lower = message.lower()
            for term in forbidden_terms:
                assert (
                    term not in message_lower
                ), f"Message for {code} contains forbidden term '{term}': {message}"

    def test_messages_dont_leak_internals(self) -> None:
        """Verify no message contains internal details."""
        forbidden_terms = [
            "dynamodb",
            "lambda",
            "cognito",
            "jwt",
            "token",
            "database",
            "exception",
            "error:",
            "stack",
        ]
        for code, message in AUTH_ERROR_MESSAGES.items():
            message_lower = message.lower()
            for term in forbidden_terms:
                # Allow "token" in AUTH_018 message context
                if code == AuthErrorCode.AUTH_018 and term == "token":
                    continue
                assert (
                    term not in message_lower
                ), f"Message for {code} contains forbidden term '{term}': {message}"


class TestAuthErrorStatus:
    """Test HTTP status codes are correct."""

    @pytest.mark.parametrize(
        "code,expected_status",
        [
            (AuthErrorCode.AUTH_013, 401),  # Credentials changed -> unauthorized
            (AuthErrorCode.AUTH_014, 401),  # Session evicted -> unauthorized
            (AuthErrorCode.AUTH_015, 400),  # Unknown provider -> bad request
            (AuthErrorCode.AUTH_016, 400),  # Provider mismatch -> bad request
            (AuthErrorCode.AUTH_017, 400),  # Password requirements -> bad request
            (AuthErrorCode.AUTH_018, 401),  # Token audience -> unauthorized
        ],
    )
    def test_status_code(self, code: AuthErrorCode, expected_status: int) -> None:
        """Verify each error code has the correct HTTP status."""
        assert AUTH_ERROR_STATUS[code] == expected_status


class TestRaiseAuthError:
    """Test the raise_auth_error helper function."""

    def test_raises_auth_error(self) -> None:
        """Verify raise_auth_error raises AuthError."""
        with pytest.raises(AuthError) as exc_info:
            raise_auth_error(AuthErrorCode.AUTH_013)

        assert exc_info.value.code == AuthErrorCode.AUTH_013
        assert exc_info.value.message == "Credentials have been changed"
        assert exc_info.value.status_code == 401

    @pytest.mark.parametrize("code", list(AuthErrorCode))
    def test_raises_for_all_codes(self, code: AuthErrorCode) -> None:
        """Verify raise_auth_error works for all error codes."""
        with pytest.raises(AuthError) as exc_info:
            raise_auth_error(code)

        assert exc_info.value.code == code
        assert exc_info.value.message == AUTH_ERROR_MESSAGES[code]
        assert exc_info.value.status_code == AUTH_ERROR_STATUS[code]


class TestAuthErrorResponse:
    """Test the auth_error_response helper function."""

    def test_response_structure(self) -> None:
        """Verify response has correct structure."""
        response = auth_error_response(AuthErrorCode.AUTH_013)

        assert "error" in response
        assert "code" in response["error"]
        assert "message" in response["error"]

    def test_response_content(self) -> None:
        """Verify response has correct content."""
        response = auth_error_response(AuthErrorCode.AUTH_013)

        assert response["error"]["code"] == "AUTH_013"
        assert response["error"]["message"] == "Credentials have been changed"

    @pytest.mark.parametrize("code", list(AuthErrorCode))
    def test_response_for_all_codes(self, code: AuthErrorCode) -> None:
        """Verify auth_error_response works for all error codes."""
        response = auth_error_response(code)

        assert response["error"]["code"] == code.value
        assert response["error"]["message"] == AUTH_ERROR_MESSAGES[code]
