"""
Dashboard Test Fixtures
=======================

Shared fixtures for dashboard unit tests.

For On-Call Engineers:
    These fixtures provide mock objects for SSE and streaming tests.
    Fresh mocks are created per test (no shared state).

For Developers:
    - Add shared dashboard-specific fixtures here
    - Test-specific fixtures belong in individual test files
"""

from unittest.mock import MagicMock, patch

import pytest


@pytest.fixture(autouse=True)
def mock_stripe_webhook_secret():
    """
    Auto-mock get_secret for Stripe webhook secret retrieval.

    This fixture ensures that tests don't require actual AWS Secrets Manager
    access. The STRIPE_WEBHOOK_SECRET_ARN env var points to a test ARN,
    and this mock returns the test secret value.

    Feature: 1191 - Mid-Session Tier Upgrade
    """
    with patch("src.lambdas.shared.secrets.get_secret") as mock_get_secret:
        mock_get_secret.return_value = {
            "webhook_secret": "whsec_test_secret_for_unit_tests"
        }
        yield mock_get_secret


@pytest.fixture
def mock_sse_generator():
    """
    Mock SSE event generator for testing streaming.

    Yields 3 events: heartbeat, metrics, and new_item.
    Use this for testing SSE streaming without actual connections.

    Example:
        async def test_sse_events(mock_sse_generator):
            gen = mock_sse_generator()
            events = [e async for e in gen]
            assert len(events) == 3
    """

    async def generator():
        yield {"event": "heartbeat", "data": "ping", "id": "1"}
        yield {"event": "metrics", "data": {"sentiment_avg": 0.65}, "id": "2"}
        yield {
            "event": "new_item",
            "data": {"id": "item-1", "sentiment": "positive"},
            "id": "3",
        }

    return generator


@pytest.fixture
def mock_connection_manager():
    """
    Mock ConnectionManager for testing connection limits.

    Returns a MagicMock with default behavior:
    - count: 0
    - max_connections: 100
    - acquire(): returns True
    - release(): no-op

    Example:
        def test_connection_limit(mock_connection_manager):
            mock_connection_manager.acquire.return_value = False
            # Test 503 response behavior
    """
    manager = MagicMock()
    manager.count = 0
    manager.max_connections = 100
    manager.acquire = MagicMock(return_value=True)
    manager.release = MagicMock()
    return manager


@pytest.fixture
def mock_dynamodb_error():
    """
    Mock DynamoDB ClientError for testing error handlers.

    Returns a botocore ClientError for ThrottlingException.
    """
    from botocore.exceptions import ClientError

    return ClientError(
        {"Error": {"Code": "ThrottlingException", "Message": "Rate exceeded"}},
        "Query",
    )


@pytest.fixture
def mock_dynamodb_table():
    """
    Mock DynamoDB table for testing without moto.

    Returns a MagicMock with common table operations.
    For full DynamoDB mocking, prefer @mock_aws from moto.
    """
    table = MagicMock()
    table.query = MagicMock(return_value={"Items": []})
    table.scan = MagicMock(return_value={"Items": []})
    table.put_item = MagicMock()
    table.get_item = MagicMock(return_value={})
    return table
