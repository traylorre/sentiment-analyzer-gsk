"""
Secure logging utilities to prevent log injection and sensitive data exposure.

This module provides functions to sanitize data before logging, preventing:
- Log injection attacks (CWE-117, CWE-93)
- Sensitive data exposure in logs
- Stack trace leakage to external users

Security References:
- OWASP Logging Cheat Sheet: https://cheatsheetseries.owasp.org/cheatsheets/Logging_Cheat_Sheet.html
- CodeQL Log Injection: https://codeql.github.com/codeql-query-help/python/py-log-injection/

CodeQL Taint Barrier Requirements:
    CodeQL's static analysis doesn't automatically recognize custom sanitizer functions
    as taint barriers. To satisfy CodeQL's py/log-injection and py/clear-text-logging
    queries, use one of these patterns:

    1. Inline sanitization (preferred for CodeQL compliance):
       safe_value = user_input.replace("\\r\\n", "").replace("\\n", "").replace("\\r", "")
       logger.info("Message", extra={"field": safe_value})

    2. Break taint flow with intermediate variable (for sensitive data):
       safe_identifier = _sanitize_function(secret_id)
       logger.info("Message", extra={"id": safe_identifier})

    The helper functions in this module are still useful for additional sanitization
    beyond what CodeQL requires (control character removal, length limiting).
"""

import re
from typing import Any

# Maximum length for logged user input to prevent log flooding
MAX_LOG_INPUT_LENGTH = 200

# Sensitive field names that should never be logged
SENSITIVE_FIELDS = {
    "password",
    "secret",
    "token",
    "api_key",
    "apikey",
    "authorization",
    "auth",
    "key",
    "private",
    "credential",
    "credentials",
}


def sanitize_for_log(value: Any, max_length: int = MAX_LOG_INPUT_LENGTH) -> str:
    """
    Sanitize a value for safe logging by removing CRLF and limiting length.

    Prevents log injection attacks by removing carriage return, line feed, and
    other control characters that could be used to inject false log entries.

    Args:
        value: Value to sanitize (will be converted to string)
        max_length: Maximum length of output (default: 200)

    Returns:
        Sanitized string safe for logging

    Security:
        - Removes \\r, \\n, \\t to prevent CRLF injection
        - Limits length to prevent log flooding
        - Replaces control characters with spaces

    CodeQL Note:
        CodeQL's py/log-injection query does NOT recognize this function as a
        taint barrier because it performs inter-procedural analysis but doesn't
        automatically trust custom sanitizer functions. For CodeQL compliance,
        use inline sanitization at the call site instead:

            # CodeQL-recognized pattern:
            safe_value = value.replace("\\r\\n", "").replace("\\n", "").replace("\\r", "")[:200]
            logger.info("Message", extra={"field": safe_value})

        This function is still useful for:
        - Additional sanitization beyond CRLF (control characters, length)
        - Non-CodeQL contexts where the helper improves readability
        - Consistent sanitization across the codebase

    Example:
        >>> sanitize_for_log("error\\n[FAKE] Admin logged in")
        'error [FAKE] Admin logged in'
    """
    # Convert to string
    text = str(value)

    # Remove CRLF characters to prevent log injection
    text = text.replace("\r", " ").replace("\n", " ").replace("\t", " ")

    # Remove other control characters
    text = re.sub(r"[\x00-\x1f\x7f-\x9f]", " ", text)

    # Limit length to prevent log flooding
    if len(text) > max_length:
        text = text[:max_length] + "..."

    return text


def get_safe_error_info(exception: Exception) -> dict[str, str]:
    """
    Extract safe information from an exception for logging.

    Returns only the exception type, NOT the message, to prevent:
    - Logging user-controlled data that could inject log entries
    - Exposing sensitive information from error messages
    - Stack trace exposure

    Args:
        exception: Exception to extract info from

    Returns:
        Dict with safe error information (type only)

    Security:
        - Does NOT include exception message (may contain user input)
        - Does NOT include stack trace (exposes internal structure)
        - Only includes exception class name

    Example:
        >>> try:
        ...     raise ValueError("user input here")
        ... except Exception as e:
        ...     get_safe_error_info(e)
        {'error_type': 'ValueError'}
    """
    return {"error_type": type(exception).__name__}


def redact_sensitive_fields(data: dict[str, Any]) -> dict[str, Any]:
    """
    Redact sensitive fields from a dictionary before logging.

    Args:
        data: Dictionary that may contain sensitive fields

    Returns:
        New dictionary with sensitive fields replaced with '***REDACTED***'

    Security:
        - Prevents accidental logging of secrets, passwords, tokens
        - Uses case-insensitive matching for field names
        - Creates a copy, doesn't modify original

    Example:
        >>> redact_sensitive_fields({"user": "john", "api_key": "secret123"})  # pragma: allowlist secret
        {'user': 'john', 'api_key': '***REDACTED***'}
    """
    result = {}
    for key, value in data.items():
        # Check if field name matches sensitive patterns (case-insensitive)
        if any(sensitive in key.lower() for sensitive in SENSITIVE_FIELDS):
            result[key] = "***REDACTED***"
        elif isinstance(value, dict):
            # Recursively redact nested dictionaries
            result[key] = redact_sensitive_fields(value)
        else:
            result[key] = value
    return result


def get_safe_error_message_for_user(exception: Exception) -> str:
    """
    Get a safe, generic error message to return to users.

    NEVER expose internal exception details to users, as this can reveal:
    - Stack traces with file paths and code structure
    - Library versions and dependencies
    - Internal business logic
    - Potential attack surface

    Args:
        exception: Exception that occurred

    Returns:
        Generic error message safe to show users

    Security:
        - Returns generic message, no exception details
        - Prevents information disclosure
        - Internal details should be logged separately

    Example:
        >>> try:
        ...     raise ValueError("/internal/path/to/file.py not found")
        ... except Exception as e:
        ...     get_safe_error_message_for_user(e)
        'An error occurred processing your request'
    """
    # Map common exception types to user-friendly messages
    error_messages = {
        "ValueError": "Invalid input provided",
        "KeyError": "Required field missing",
        "PermissionError": "Access denied",
        "FileNotFoundError": "Requested resource not found",
        "TimeoutError": "Request timed out",
    }

    exception_type = type(exception).__name__
    return error_messages.get(
        exception_type, "An error occurred processing your request"
    )


def sanitize_path_component(filename: str) -> str | None:
    """
    Validate and sanitize a filename/path component for safe file access.

    Prevents path traversal attacks by rejecting filenames with:
    - Directory separators (/ or \\)
    - Parent directory references (..)
    - Null bytes
    - Control characters

    Args:
        filename: Filename to validate

    Returns:
        Sanitized filename if safe, None if rejected

    Security:
        - Prevents path traversal (../../../etc/passwd)
        - Rejects directory separators
        - Validates against null byte injection

    Example:
        >>> sanitize_path_component("safe.txt")
        'safe.txt'
        >>> sanitize_path_component("../etc/passwd")
        None
    """
    # Reject if contains path separators
    if "/" in filename or "\\" in filename:
        return None

    # Reject if contains parent directory reference
    if ".." in filename:
        return None

    # Reject if contains null bytes
    if "\x00" in filename:
        return None

    # Reject if contains control characters
    if re.search(r"[\x00-\x1f\x7f-\x9f]", filename):
        return None

    # Limit length
    if len(filename) > 255:
        return None

    return filename
