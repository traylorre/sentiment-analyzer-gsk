"""
Pytest Configuration and Shared Fixtures
=========================================

Common fixtures used across all test modules.

For On-Call Engineers:
    If tests fail with AWS credential errors:
    1. Ensure moto is properly mocking (check @mock_aws decorator)
    2. Verify AWS env vars are set in fixtures
    3. Check moto version (moto==4.2.0)

For Developers:
    - Import fixtures by name in test files (pytest auto-discovers conftest.py)
    - All fixtures use moto mocks (no real AWS calls)
    - Add new shared fixtures here, test-specific fixtures in test files
"""

import os

import pytest


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
    os.environ["AWS_DEFAULT_REGION"] = "us-east-1"

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
