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
#
# IMPORTANT: Only set defaults that don't conflict with CI-provided values for preprod tests.
# For preprod tests, CI provides: DYNAMODB_TABLE, ENVIRONMENT, API_KEY, etc.
# setdefault() only sets if NOT already present, so CI values take precedence.
os.environ.setdefault("AWS_ACCESS_KEY_ID", "testing")
os.environ.setdefault("AWS_SECRET_ACCESS_KEY", "testing")
os.environ.setdefault("AWS_REGION", "us-east-1")
os.environ.setdefault("SSE_POLL_INTERVAL", "1")
os.environ.setdefault("SSE_HEARTBEAT_INTERVAL", "1")  # Fast heartbeats for tests

# Disable X-Ray SDK in tests to suppress "cannot find the current segment" errors.
# X-Ray requires a Lambda runtime context with an active segment. In tests, there's no
# X-Ray daemon running, so the SDK logs ERROR for every instrumented AWS call.
# Setting this env var makes X-Ray gracefully no-op instead of logging errors.
os.environ.setdefault("AWS_XRAY_SDK_ENABLED", "false")

# These are ONLY set if not already present (CI sets them for preprod)
# For local unit tests (not preprod), these provide sensible defaults
if "DATABASE_TABLE" not in os.environ:
    os.environ["DATABASE_TABLE"] = "test-sentiment-items"
if "API_KEY" not in os.environ:
    os.environ["API_KEY"] = "test-api-key-12345"
if "ENVIRONMENT" not in os.environ:
    os.environ["ENVIRONMENT"] = "test"


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


# =============================================================================
# Synthetic Test Data Fixture (Spec 005 - TD-004)
# =============================================================================


@pytest.fixture(scope="session")
def synthetic_data():
    """
    Generate synthetic test data for preprod E2E tests.

    This fixture creates deterministic test data in DynamoDB with known
    properties, allowing tests to verify behavior against expected values.

    The fixture is session-scoped to avoid recreating data for each test.
    Data is automatically cleaned up after the session completes.

    Note: This fixture only activates for preprod tests (requires real AWS).
    For unit tests with moto, use the sample_sentiment_item fixture instead.

    Yields:
        Dict containing:
        - items: List of 6 created items
        - generator: The SyntheticDataGenerator instance
        - positive_count: 2
        - neutral_count: 2
        - negative_count: 2
        - total_count: 6
        - tech_count: 3 (items with "tech" tag)
        - business_count: 2 (items with "business" tag)

    Example:
        def test_sentiment_returns_data(auth_headers, synthetic_data):
            response = requests.get(f"{URL}/api/v2/sentiment?tags=tech", headers=auth_headers)
            data = response.json()

            # Verify against known synthetic data
            assert data["total_count"] >= 0
            assert "tags" in data
    """
    # Only import and use for preprod tests (avoid import errors in unit tests)
    from tests.fixtures.synthetic_data import SyntheticDataGenerator

    # Get table name from environment (CI sets this for preprod)
    table_name = os.environ.get("DATABASE_TABLE")

    if not table_name or table_name == "test-sentiment-items":
        # Skip synthetic data for unit tests (mocked DynamoDB)
        pytest.skip("Synthetic data fixture only available for preprod tests")

    with SyntheticDataGenerator(table_name) as generator:
        items = generator.create_test_dataset()
        yield {
            "items": items,
            "generator": generator,
            "positive_count": 2,
            "neutral_count": 2,
            "negative_count": 2,
            "total_count": 6,
            "tech_count": 3,
            "business_count": 2,
        }
        # Cleanup happens automatically via context manager


# =============================================================================
# Feature 012: OHLC & Sentiment History Test Infrastructure
# =============================================================================
#
# Fixtures for testing OHLC and sentiment history endpoints with:
# - Failure injection for error resilience testing
# - Mock adapters with configurable behavior
# - Validators for response verification
# - Test oracle for expected value computation


@pytest.fixture
def failure_injector():
    """Default (no failure) injector."""
    from tests.fixtures.mocks.failure_injector import FailureInjector

    return FailureInjector()


@pytest.fixture
def tiingo_500_error():
    """Failure injector: Tiingo returns HTTP 500."""
    from tests.fixtures.mocks.failure_injector import create_http_500_injector

    return create_http_500_injector()


@pytest.fixture
def tiingo_502_error():
    """Failure injector: Tiingo returns HTTP 502 Bad Gateway."""
    from tests.fixtures.mocks.failure_injector import create_http_502_injector

    return create_http_502_injector()


@pytest.fixture
def tiingo_503_error():
    """Failure injector: Tiingo returns HTTP 503 Service Unavailable."""
    from tests.fixtures.mocks.failure_injector import create_http_503_injector

    return create_http_503_injector()


@pytest.fixture
def tiingo_504_error():
    """Failure injector: Tiingo returns HTTP 504 Gateway Timeout."""
    from tests.fixtures.mocks.failure_injector import create_http_504_injector

    return create_http_504_injector()


@pytest.fixture
def tiingo_429_error():
    """Failure injector: Tiingo returns HTTP 429 Rate Limited."""
    from tests.fixtures.mocks.failure_injector import create_http_429_injector

    return create_http_429_injector()


@pytest.fixture
def tiingo_timeout():
    """Failure injector: Tiingo connection timeout."""
    from tests.fixtures.mocks.failure_injector import create_timeout_injector

    return create_timeout_injector()


@pytest.fixture
def tiingo_connection_refused():
    """Failure injector: Tiingo connection refused."""
    from tests.fixtures.mocks.failure_injector import create_connection_refused_injector

    return create_connection_refused_injector()


@pytest.fixture
def tiingo_dns_failure():
    """Failure injector: Tiingo DNS resolution failure."""
    from tests.fixtures.mocks.failure_injector import create_dns_failure_injector

    return create_dns_failure_injector()


@pytest.fixture
def tiingo_invalid_json():
    """Failure injector: Tiingo returns invalid JSON."""
    from tests.fixtures.mocks.failure_injector import create_invalid_json_injector

    return create_invalid_json_injector()


@pytest.fixture
def tiingo_empty_response():
    """Failure injector: Tiingo returns empty object."""
    from tests.fixtures.mocks.failure_injector import create_empty_response_injector

    return create_empty_response_injector()


@pytest.fixture
def tiingo_empty_array():
    """Failure injector: Tiingo returns empty array."""
    from tests.fixtures.mocks.failure_injector import create_empty_array_injector

    return create_empty_array_injector()


@pytest.fixture
def mock_tiingo(failure_injector):
    """Mock Tiingo adapter with optional failure injection."""
    from tests.fixtures.mocks.mock_tiingo import MockTiingoAdapter

    return MockTiingoAdapter(seed=42, failure_injector=failure_injector)


@pytest.fixture
def mock_finnhub(failure_injector):
    """Mock Finnhub adapter with optional failure injection."""
    from tests.fixtures.mocks.mock_finnhub import MockFinnhubAdapter

    return MockFinnhubAdapter(seed=42, failure_injector=failure_injector)


@pytest.fixture
def mock_tiingo_failing(tiingo_500_error):
    """Mock Tiingo adapter that always fails with HTTP 500."""
    from tests.fixtures.mocks.mock_tiingo import MockTiingoAdapter

    return MockTiingoAdapter(seed=42, failure_injector=tiingo_500_error)


@pytest.fixture
def mock_finnhub_failing(tiingo_500_error):
    """Mock Finnhub adapter that always fails with HTTP 500."""
    from tests.fixtures.mocks.mock_finnhub import MockFinnhubAdapter

    return MockFinnhubAdapter(seed=42, failure_injector=tiingo_500_error)


@pytest.fixture
def ohlc_validator():
    """OHLC response validator."""
    from tests.fixtures.validators import OHLCValidator

    return OHLCValidator()


@pytest.fixture
def sentiment_validator():
    """Sentiment response validator."""
    from tests.fixtures.validators import SentimentValidator

    return SentimentValidator()


@pytest.fixture
def test_oracle():
    """Test oracle for computing expected responses."""
    from tests.fixtures.oracles import TestOracle

    return TestOracle(seed=42)


@pytest.fixture
def edge_case_generator():
    """Edge case generator for boundary testing."""
    from datetime import date

    from tests.fixtures.synthetic.edge_case_generator import EdgeCaseGenerator

    return EdgeCaseGenerator(base_date=date.today())


@pytest.fixture
def ohlc_test_client(mock_tiingo, mock_finnhub):
    """Test client for OHLC endpoint with mock adapters injected.

    Uses FastAPI's dependency override to inject mock adapters
    instead of real Tiingo/Finnhub adapters.
    """
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    from src.lambdas.dashboard.ohlc import (
        get_finnhub_adapter,
        get_tiingo_adapter,
        router,
    )

    app = FastAPI()
    app.include_router(router)

    # Override adapter dependencies with mocks
    app.dependency_overrides[get_tiingo_adapter] = lambda: mock_tiingo
    app.dependency_overrides[get_finnhub_adapter] = lambda: mock_finnhub

    with TestClient(app) as client:
        yield client

    # Cleanup
    app.dependency_overrides.clear()


# =============================================================================
# S3 Model Download Fixtures (087-test-coverage-completion)
# =============================================================================


@pytest.fixture
def mock_model_tar():
    """
    Create mock model tar.gz for S3 download testing.

    Creates a minimal valid tar.gz with config.json for testing
    the sentiment model S3 download path.

    Returns:
        io.BytesIO: Buffer containing tar.gz data

    Example:
        @mock_aws
        def test_download_model_from_s3_success(mock_model_tar):
            s3 = boto3.client("s3", region_name="us-east-1")
            s3.create_bucket(Bucket="sentiment-model-bucket")
            s3.put_object(
                Bucket="sentiment-model-bucket",
                Key="models/sentiment-v1.tar.gz",
                Body=mock_model_tar.read()
            )
            # Test download function
    """
    import io
    import tarfile

    tar_buffer = io.BytesIO()
    with tarfile.open(fileobj=tar_buffer, mode="w:gz") as tar:
        # Add config.json
        config_data = b'{"model_type": "distilbert", "num_labels": 3}'
        config_info = tarfile.TarInfo(name="model/config.json")
        config_info.size = len(config_data)
        tar.addfile(config_info, io.BytesIO(config_data))

        # Add mock weights file (minimal)
        weights_data = b"mock_pytorch_weights_data"
        weights_info = tarfile.TarInfo(name="model/pytorch_model.bin")
        weights_info.size = len(weights_data)
        tar.addfile(weights_info, io.BytesIO(weights_data))

    tar_buffer.seek(0)
    return tar_buffer


@pytest.fixture
def mock_s3_error_not_found():
    """
    Mock S3 NoSuchKey error for testing download failure path.

    Returns:
        botocore.exceptions.ClientError: NoSuchKey error
    """
    from botocore.exceptions import ClientError

    return ClientError(
        {
            "Error": {
                "Code": "NoSuchKey",
                "Message": "The specified key does not exist.",
            }
        },
        "GetObject",
    )


@pytest.fixture
def mock_s3_error_throttling():
    """
    Mock S3 Throttling error for testing retry behavior.

    Returns:
        botocore.exceptions.ClientError: SlowDown error
    """
    from botocore.exceptions import ClientError

    return ClientError(
        {"Error": {"Code": "SlowDown", "Message": "Please reduce your request rate."}},
        "GetObject",
    )
