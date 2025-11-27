"""Pytest configuration for notification tests.

Mocks AWS X-Ray SDK before handler import to prevent decorator interference.
"""

import sys
from unittest.mock import MagicMock


def pytest_configure(config):
    """Mock X-Ray SDK before any test modules are imported."""
    # Create a proper mock that returns the function unchanged when used as decorator
    mock_xray = MagicMock()

    def passthrough_decorator(name):
        def decorator(func):
            return func

        return decorator

    mock_xray.capture = passthrough_decorator
    mock_xray.patch_all = MagicMock()

    # Install mocks before handler imports
    sys.modules["aws_xray_sdk"] = MagicMock()
    sys.modules["aws_xray_sdk.core"] = MagicMock()
    sys.modules["aws_xray_sdk.core"].xray_recorder = mock_xray
    sys.modules["aws_xray_sdk.core"].patch_all = MagicMock()
