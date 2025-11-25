"""
Pytest Configuration and Shared Fixtures
=========================================

Common fixtures used across all test modules.

Test Environment Separation:
    - LOCAL/DEV: Mocked AWS (moto) - runs with `pytest -m "not preprod"`
    - PREPROD/PROD: Real AWS resources - runs with `pytest -m "preprod"` or via CI

    Files with "preprod" in their name are auto-marked with the `preprod` marker.
    This ensures they are excluded from local runs automatically.

For On-Call Engineers:
    If tests fail with AWS credential errors:
    1. Ensure moto is properly mocking (check @mock_aws decorator)
    2. Verify AWS env vars are set in fixtures
    3. Check moto version (moto==4.2.0)

    If tests fail with "Unexpected ERROR/WARNING logs":
    1. The test is catching a real issue - investigate the logs
    2. If the log is expected, add marker: @pytest.mark.expect_errors("pattern")
    3. See docs/TESTING_LESSONS_LEARNED.md for details

For Developers:
    - Import fixtures by name in test files (pytest auto-discovers conftest.py)
    - All fixtures use moto mocks (no real AWS calls)
    - Add new shared fixtures here, test-specific fixtures in test files
    - Use markers to declare expected logs: @pytest.mark.expect_errors("pattern")
"""

import logging
import os
from pathlib import Path

import pytest

# =============================================================================
# Pytest Marker Registration
# =============================================================================


def pytest_configure(config):
    """Register custom markers to avoid warnings."""
    config.addinivalue_line(
        "markers",
        "preprod: marks tests that require real AWS resources (deselect with '-m \"not preprod\"')",
    )
    config.addinivalue_line(
        "markers",
        "expect_errors(pattern): marks tests that expect ERROR logs matching pattern",
    )


def pytest_collection_modifyitems(config, items):
    """
    Auto-mark tests based on their file location.

    Files with "preprod" in filename are marked as preprod tests.
    This ensures they are excluded from local runs with `-m "not preprod"`.
    """
    preprod_marker = pytest.mark.preprod

    for item in items:
        # Get the file path relative to the tests directory
        test_file = Path(item.fspath)

        # Auto-mark files with "preprod" in their name
        if "preprod" in test_file.name.lower():
            item.add_marker(preprod_marker)


# Set default test environment variables at module load time
# This allows test files to import modules that read env vars at import time
os.environ.setdefault("AWS_ACCESS_KEY_ID", "testing")
os.environ.setdefault("AWS_SECRET_ACCESS_KEY", "testing")
os.environ.setdefault("AWS_REGION", "us-east-1")
os.environ.setdefault("DYNAMODB_TABLE", "test-sentiment-items")
os.environ.setdefault("API_KEY", "test-api-key-12345")
os.environ.setdefault("SSE_POLL_INTERVAL", "1")
os.environ.setdefault("ENVIRONMENT", "test")


@pytest.fixture(autouse=True)
def reset_env_vars():
    """
    Reset environment variables before each test.

    Ensures tests don't pollute each other's environment.
    """
    # Store original env
    original_env = os.environ.copy()

    yield

    # Restore original env
    os.environ.clear()
    os.environ.update(original_env)


@pytest.fixture
def aws_credentials():
    """
    Set up mock AWS credentials for moto.

    Use this fixture when testing AWS SDK calls.
    All tests using this fixture will use moto mocks.
    """
    os.environ["AWS_ACCESS_KEY_ID"] = "testing"
    os.environ["AWS_SECRET_ACCESS_KEY"] = "testing"
    os.environ["AWS_SECURITY_TOKEN"] = "testing"
    os.environ["AWS_SESSION_TOKEN"] = "testing"
    os.environ["AWS_REGION"] = "us-east-1"

    yield

    # Cleanup handled by reset_env_vars


@pytest.fixture
def sample_article():
    """
    Sample NewsAPI article for testing.

    Matches the structure returned by NewsAPI /everything endpoint.
    """
    return {
        "source": {"id": "test-source", "name": "Test News"},
        "author": "Test Author",
        "title": "Test Article Title for Sentiment Analysis",
        "description": "This is a test article description.",
        "url": "https://example.com/article/123",
        "urlToImage": "https://example.com/image.jpg",
        "publishedAt": "2025-11-17T14:30:00Z",
        "content": "Test article content for sentiment analysis testing.",
    }


@pytest.fixture
def sample_sentiment_item():
    """
    Sample DynamoDB item representing an analyzed article.

    Matches the schema in infrastructure/terraform/modules/dynamodb/main.tf.
    """
    return {
        "source_id": "newsapi#abc123def456",
        "timestamp": "2025-11-17T14:30:00.000Z",
        "status": "analyzed",
        "sentiment": "positive",
        "score": 0.95,
        "model_version": "v1.0.0",
        "title": "Test Article",
        "snippet": "Test article content...",
        "url": "https://example.com/article/123",
        "tag": "AI",
        "ttl_timestamp": 1734444600,  # 30 days from ingestion
    }


@pytest.fixture
def sample_pending_item():
    """
    Sample DynamoDB item representing a pending (unanalyzed) article.
    """
    return {
        "source_id": "newsapi#pending123",
        "timestamp": "2025-11-17T15:00:00.000Z",
        "status": "pending",
        "title": "Pending Article",
        "snippet": "Article waiting for analysis...",
        "url": "https://example.com/article/456",
        "tag": "climate",
        "ttl_timestamp": 1734444600,
    }


# =============================================================================
# Log Validation Helpers
# =============================================================================
#
# Philosophy (see docs/TESTING_LESSONS_LEARNED.md):
# - Production code logs normally (never test-aware)
# - Tests explicitly assert on expected logs using caplog
# - Helper functions reduce boilerplate
#
# The autouse fixture approach was attempted but doesn't work because
# pytest clears caplog.record_tuples before fixture teardown runs.
# Explicit assertions are the correct pytest pattern.


def assert_error_logged(caplog, pattern: str):
    """
    Helper to assert an ERROR log was captured.

    Args:
        caplog: pytest caplog fixture
        pattern: String pattern to search for in log messages

    Raises:
        AssertionError: If no ERROR log matches the pattern

    Example:
        def test_model_failure(caplog):
            result = handler(bad_event, context)
            assert result["statusCode"] == 500
            assert_error_logged(caplog, "Model load error")
    """
    assert any(
        pattern in record.message
        for record in caplog.records
        if record.levelno >= logging.ERROR
    ), f"Expected ERROR log matching '{pattern}' not found"


def assert_warning_logged(caplog, pattern: str):
    """
    Helper to assert a WARNING log was captured.

    Args:
        caplog: pytest caplog fixture
        pattern: String pattern to search for in log messages

    Raises:
        AssertionError: If no WARNING log matches the pattern

    Example:
        def test_retry_behavior(caplog):
            result = handler(flaky_event, context)
            assert_warning_logged(caplog, "Retrying request")
    """
    assert any(
        pattern in record.message
        for record in caplog.records
        if record.levelno == logging.WARNING
    ), f"Expected WARNING log matching '{pattern}' not found"
