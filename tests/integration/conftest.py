"""Integration test configuration.

Provides fixtures for integration tests that use LocalStack for AWS service emulation.
Ensures test isolation by clearing in-memory caches before each test.

LocalStack fixtures provide session-scoped boto3 clients for:
- DynamoDB, S3, SQS, SNS, Lambda, Secrets Manager

Usage:
    def test_dynamodb(dynamodb_client, test_run_id):
        table_name = f"test-table-{test_run_id}"
        dynamodb_client.create_table(TableName=table_name, ...)
"""

import os
import time
import uuid
from collections.abc import Callable

import boto3
import pytest
from botocore.config import Config

# Import cache clearing functions for test isolation
from src.lambdas.dashboard.configurations import clear_config_cache
from src.lambdas.dashboard.metrics import clear_metrics_cache
from src.lambdas.dashboard.sentiment import clear_sentiment_cache
from src.lambdas.shared.circuit_breaker import (
    clear_cache as clear_circuit_breaker_cache,
)
from src.lambdas.shared.quota_tracker import clear_quota_cache

# =============================================================================
# LocalStack Configuration
# =============================================================================

LOCALSTACK_ENDPOINT = os.getenv("LOCALSTACK_ENDPOINT", "http://localhost:4566")
AWS_REGION = os.getenv("AWS_DEFAULT_REGION", "us-east-1")

# Retry config for LocalStack startup race conditions
BOTO_CONFIG = Config(
    retries={"max_attempts": 3, "mode": "standard"},
    connect_timeout=5,
    read_timeout=10,
)


def _localstack_client(service: str):
    """Create a boto3 client configured for LocalStack."""
    return boto3.client(
        service,
        endpoint_url=LOCALSTACK_ENDPOINT,
        region_name=AWS_REGION,
        aws_access_key_id="test",
        aws_secret_access_key="test",
        config=BOTO_CONFIG,
    )


# =============================================================================
# Health Check
# =============================================================================


@pytest.fixture(scope="session")
def localstack_endpoint() -> str:
    """LocalStack endpoint URL."""
    return LOCALSTACK_ENDPOINT


@pytest.fixture(scope="session")
def boto_config() -> Config:
    """Boto3 config with retry settings for LocalStack."""
    return BOTO_CONFIG


# =============================================================================
# Service Clients (session-scoped for performance)
# =============================================================================


@pytest.fixture(scope="session")
def dynamodb_client():
    """DynamoDB client for LocalStack."""
    return _localstack_client("dynamodb")


@pytest.fixture(scope="session")
def s3_client():
    """S3 client for LocalStack."""
    return _localstack_client("s3")


@pytest.fixture(scope="session")
def sqs_client():
    """SQS client for LocalStack."""
    return _localstack_client("sqs")


@pytest.fixture(scope="session")
def sns_client():
    """SNS client for LocalStack."""
    return _localstack_client("sns")


@pytest.fixture(scope="session")
def lambda_client():
    """Lambda client for LocalStack."""
    return _localstack_client("lambda")


@pytest.fixture(scope="session")
def secretsmanager_client():
    """Secrets Manager client for LocalStack."""
    return _localstack_client("secretsmanager")


# =============================================================================
# Test Isolation
# =============================================================================


@pytest.fixture
def test_run_id() -> str:
    """Unique ID for test resource isolation.

    Used to create unique resource names that don't conflict
    across parallel test runs.
    """
    return uuid.uuid4().hex[:8]


# =============================================================================
# Assertion Helpers
# =============================================================================


@pytest.fixture
def assert_eventually() -> Callable:
    """Helper for eventually-consistent assertions.

    Usage:
        assert_eventually(lambda: s3_client.head_object(...), timeout=5)
    """

    def _assert_eventually(
        condition_fn: Callable, timeout: int = 10, interval: float = 0.5
    ):
        """Retry condition until it passes or timeout."""
        start = time.time()
        last_error = None

        while time.time() - start < timeout:
            try:
                result = condition_fn()
                if result is None or result:
                    return result
            except Exception as e:
                last_error = e
            time.sleep(interval)

        if last_error:
            raise AssertionError(f"Condition not met within {timeout}s: {last_error}")
        raise AssertionError(f"Condition not met within {timeout}s")

    return _assert_eventually


# =============================================================================
# Cache Clearing
# =============================================================================


@pytest.fixture(autouse=True)
def clear_all_caches():
    """Clear all module-level caches before each test.

    This ensures test isolation by preventing cached data from one test
    affecting another. Clears:
    - Circuit breaker state cache
    - Quota tracker cache
    - User configuration cache
    - Sentiment aggregation cache
    - Dashboard metrics cache
    """
    clear_circuit_breaker_cache()
    clear_quota_cache()
    clear_config_cache()
    clear_sentiment_cache()
    clear_metrics_cache()
    yield
    # Clear after test too (for safety)
    clear_circuit_breaker_cache()
    clear_quota_cache()
    clear_config_cache()
    clear_sentiment_cache()
    clear_metrics_cache()
