"""
Logging Utilities
=================

Shared logging utilities for the sentiment analyzer.

For On-Call Engineers:
    These utilities help manage log levels during test execution.
    When running in pytest, expected warnings are downgraded to debug
    to prevent log pollution.

For Developers:
    Use log_expected_warning() for warnings that are expected during
    normal operation but would pollute test logs (e.g., retries,
    fallback behavior, expected validation failures).

    True errors should still use logger.error() or logger.warning()
    directly as they indicate unexpected conditions.

    Note: The test detection is independent of ENVIRONMENT variable.
    Tests for any stage (local/dev/prod) will have warnings suppressed.
"""

import logging
import sys


def _is_running_in_pytest() -> bool:
    """
    Check if code is running inside pytest.

    This is independent of ENVIRONMENT variable - tests for any stage
    (local/dev/prod) should suppress expected warnings.
    """
    return "pytest" in sys.modules


def log_expected_warning(logger: logging.Logger, message: str, **kwargs) -> None:
    """
    Log warnings that are expected during normal operation.

    When running in pytest, these are logged at DEBUG level to prevent
    log pollution when testing error handling paths.

    In actual deployment (not tests), these are logged at WARNING level.

    Args:
        logger: The logger instance to use
        message: The warning message
        **kwargs: Additional arguments (e.g., extra={})

    Examples:
        - Retry attempts
        - Fallback behavior (e.g., using title instead of URL)
        - Expected validation failures in tests
        - Idempotency checks (item already processed)
    """
    if _is_running_in_pytest():
        logger.debug(message, **kwargs)
    else:
        logger.warning(message, **kwargs)


def is_running_tests() -> bool:
    """Check if running in pytest."""
    return _is_running_in_pytest()
