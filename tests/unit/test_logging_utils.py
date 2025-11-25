"""
Unit tests for logging_utils module.

Tests cover security-focused logging utilities:
- sanitize_for_log: CRLF injection prevention
- get_safe_error_info: Safe exception logging
- redact_sensitive_fields: Sensitive data redaction
- get_safe_error_message_for_user: User-safe error messages
- sanitize_path_component: Path traversal prevention
"""

from src.lambdas.shared.logging_utils import (
    get_safe_error_info,
    get_safe_error_message_for_user,
    redact_sensitive_fields,
    sanitize_for_log,
    sanitize_path_component,
)


class TestSanitizeForLog:
    """Tests for sanitize_for_log function."""

    def test_removes_newlines(self):
        """Test that newlines are replaced with spaces."""
        result = sanitize_for_log("line1\nline2\nline3")
        assert "\n" not in result
        assert result == "line1 line2 line3"

    def test_removes_carriage_returns(self):
        """Test that carriage returns are replaced with spaces."""
        result = sanitize_for_log("line1\rline2")
        assert "\r" not in result
        assert result == "line1 line2"

    def test_removes_tabs(self):
        """Test that tabs are replaced with spaces."""
        result = sanitize_for_log("col1\tcol2")
        assert "\t" not in result
        assert result == "col1 col2"

    def test_removes_control_characters(self):
        """Test that control characters are removed."""
        result = sanitize_for_log("text\x00\x1fnull")
        assert "\x00" not in result
        assert "\x1f" not in result

    def test_truncates_long_input(self):
        """Test that long input is truncated with ellipsis."""
        long_text = "a" * 300
        result = sanitize_for_log(long_text)
        assert len(result) == 203  # 200 + "..."
        assert result.endswith("...")

    def test_custom_max_length(self):
        """Test custom max length parameter."""
        text = "a" * 100
        result = sanitize_for_log(text, max_length=50)
        assert len(result) == 53  # 50 + "..."

    def test_converts_non_string_to_string(self):
        """Test that non-string values are converted."""
        result = sanitize_for_log(12345)
        assert result == "12345"

    def test_none_value(self):
        """Test handling of None value."""
        result = sanitize_for_log(None)
        assert result == "None"


class TestGetSafeErrorInfo:
    """Tests for get_safe_error_info function."""

    def test_returns_error_type(self):
        """Test that error type is returned."""
        try:
            raise ValueError("secret message")
        except Exception as e:
            result = get_safe_error_info(e)

        assert result == {"error_type": "ValueError"}

    def test_does_not_include_message(self):
        """Test that error message is not included."""
        try:
            raise KeyError("sensitive_key")
        except Exception as e:
            result = get_safe_error_info(e)

        assert "sensitive_key" not in str(result)
        assert "error_message" not in result


class TestRedactSensitiveFields:
    """Tests for redact_sensitive_fields function."""

    def test_redacts_password(self):
        """Test that password field is redacted."""
        data = {"username": "john", "password": "secret123"}
        result = redact_sensitive_fields(data)
        assert result["password"] == "***REDACTED***"
        assert result["username"] == "john"

    def test_redacts_api_key(self):
        """Test that api_key field is redacted."""
        data = {"api_key": "abc123", "data": "value"}
        result = redact_sensitive_fields(data)
        assert result["api_key"] == "***REDACTED***"

    def test_redacts_token(self):
        """Test that token field is redacted."""
        data = {"token": "jwt_token_here"}
        result = redact_sensitive_fields(data)
        assert result["token"] == "***REDACTED***"

    def test_case_insensitive(self):
        """Test case-insensitive matching of sensitive fields."""
        data = {"API_KEY": "secret", "Password": "pass123"}
        result = redact_sensitive_fields(data)
        assert result["API_KEY"] == "***REDACTED***"
        assert result["Password"] == "***REDACTED***"

    def test_nested_dictionaries(self):
        """Test redaction in nested dictionaries."""
        data = {
            "user": "john",
            "config": {
                "secret": "nested_secret",
                "setting": "value",
            },
        }
        result = redact_sensitive_fields(data)
        assert result["config"]["secret"] == "***REDACTED***"
        assert result["config"]["setting"] == "value"

    def test_preserves_non_sensitive(self):
        """Test that non-sensitive fields are preserved."""
        data = {"name": "John", "email": "john@example.com"}
        result = redact_sensitive_fields(data)
        assert result == data

    def test_does_not_modify_original(self):
        """Test that original dictionary is not modified."""
        original = {"password": "secret"}
        redact_sensitive_fields(original)
        assert original["password"] == "secret"


class TestGetSafeErrorMessageForUser:
    """Tests for get_safe_error_message_for_user function."""

    def test_value_error_message(self):
        """Test user-friendly message for ValueError."""
        try:
            raise ValueError("internal details here")
        except Exception as e:
            result = get_safe_error_message_for_user(e)

        assert result == "Invalid input provided"
        assert "internal" not in result

    def test_key_error_message(self):
        """Test user-friendly message for KeyError."""
        try:
            raise KeyError("secret_field")
        except Exception as e:
            result = get_safe_error_message_for_user(e)

        assert result == "Required field missing"

    def test_permission_error_message(self):
        """Test user-friendly message for PermissionError."""
        try:
            raise PermissionError("/etc/shadow")
        except Exception as e:
            result = get_safe_error_message_for_user(e)

        assert result == "Access denied"

    def test_file_not_found_message(self):
        """Test user-friendly message for FileNotFoundError."""
        try:
            raise FileNotFoundError("/internal/config.py")
        except Exception as e:
            result = get_safe_error_message_for_user(e)

        assert result == "Requested resource not found"

    def test_timeout_error_message(self):
        """Test user-friendly message for TimeoutError."""
        try:
            raise TimeoutError()
        except Exception as e:
            result = get_safe_error_message_for_user(e)

        assert result == "Request timed out"

    def test_unknown_error_generic_message(self):
        """Test generic message for unknown exceptions."""
        try:
            raise RuntimeError("something unexpected")
        except Exception as e:
            result = get_safe_error_message_for_user(e)

        assert result == "An error occurred processing your request"


class TestSanitizePathComponent:
    """Tests for sanitize_path_component function."""

    def test_valid_filename(self):
        """Test that valid filenames pass through."""
        assert sanitize_path_component("file.txt") == "file.txt"
        assert sanitize_path_component("image.png") == "image.png"

    def test_rejects_forward_slash(self):
        """Test rejection of forward slash."""
        assert sanitize_path_component("path/to/file") is None

    def test_rejects_backslash(self):
        """Test rejection of backslash."""
        assert sanitize_path_component("path\\to\\file") is None

    def test_rejects_parent_directory(self):
        """Test rejection of parent directory reference."""
        assert sanitize_path_component("..") is None
        assert sanitize_path_component("../etc/passwd") is None

    def test_rejects_null_byte(self):
        """Test rejection of null bytes."""
        assert sanitize_path_component("file\x00.txt") is None

    def test_rejects_control_characters(self):
        """Test rejection of control characters."""
        assert sanitize_path_component("file\x1f.txt") is None

    def test_rejects_long_filename(self):
        """Test rejection of filenames over 255 characters."""
        long_name = "a" * 256
        assert sanitize_path_component(long_name) is None

    def test_accepts_max_length_filename(self):
        """Test acceptance of filename at max length."""
        max_name = "a" * 255
        assert sanitize_path_component(max_name) == max_name
