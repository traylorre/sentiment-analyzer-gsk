"""SSE streaming test fixtures.

Provides common fixtures and test setup for SSE streaming Lambda tests.
"""

import os
import sys

import pytest

# Add SSE streaming Lambda source to Python path for imports
# This allows tests to import modules like `stream`, `handler`, etc.
SSE_STREAMING_PATH = os.path.join(
    os.path.dirname(__file__),
    "..",
    "..",
    "..",
    "src",
    "lambdas",
    "sse_streaming",
)
if SSE_STREAMING_PATH not in sys.path:
    sys.path.insert(0, SSE_STREAMING_PATH)


@pytest.fixture(autouse=True)
def sse_env_vars(monkeypatch):
    """Set SSE-specific environment variables for all tests in this directory.

    This fixture ensures consistent environment configuration for SSE streaming
    tests, avoiding issues with module-level code that reads environment
    variables at import time.
    """
    # DATABASE_TABLE is used by config.py ConfigLookupService
    monkeypatch.setenv("DATABASE_TABLE", "test-sentiment-items")

    # SSE_POLL_INTERVAL is used by polling.py PollingService
    monkeypatch.setenv("SSE_POLL_INTERVAL", "1")

    # SSE_HEARTBEAT_INTERVAL is used by stream.py SSEStreamGenerator
    monkeypatch.setenv("SSE_HEARTBEAT_INTERVAL", "5")

    # SSE_MAX_CONNECTIONS is used by connection.py ConnectionManager
    monkeypatch.setenv("SSE_MAX_CONNECTIONS", "100")

    # ENVIRONMENT is used by handler.py for debug endpoint
    monkeypatch.setenv("ENVIRONMENT", "test")

    yield


@pytest.fixture
def mock_dynamodb_table(mocker):
    """Mock DynamoDB table for SSE streaming tests.

    Returns a mock table that can be configured with scan/get_item responses.
    """
    mock_table = mocker.MagicMock()
    mock_table.scan.return_value = {"Items": []}
    mock_table.get_item.return_value = {}
    return mock_table


@pytest.fixture
def sample_config_item():
    """Sample DynamoDB configuration item for config lookup tests."""
    return {
        "PK": "USER#test-user-123",
        "SK": "CONFIG#test-config-456",
        "config_id": "test-config-456",
        "user_id": "test-user-123",
        "name": "Test Configuration",
        "is_active": True,
        "tickers": [
            {"symbol": "AAPL", "name": "Apple Inc."},
            {"symbol": "GOOGL", "name": "Alphabet Inc."},
        ],
        "created_at": "2025-01-01T00:00:00Z",
        "updated_at": "2025-01-01T00:00:00Z",
    }


@pytest.fixture
def sample_sentiment_items():
    """Sample DynamoDB sentiment items for polling tests."""
    return [
        {
            "pk": "SENTIMENT#aapl-001",
            "ticker": "AAPL",
            "sentiment": "positive",
            "score": 0.85,
            "timestamp": "2025-01-01T12:00:00Z",
        },
        {
            "pk": "SENTIMENT#googl-001",
            "ticker": "GOOGL",
            "sentiment": "neutral",
            "score": 0.50,
            "timestamp": "2025-01-01T12:05:00Z",
        },
        {
            "pk": "SENTIMENT#aapl-002",
            "ticker": "AAPL",
            "sentiment": "negative",
            "score": 0.25,
            "timestamp": "2025-01-01T12:10:00Z",
        },
    ]
