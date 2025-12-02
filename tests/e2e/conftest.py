"""E2E test configuration with synthetic data setup.

Provides fixtures for E2E tests against preprod environment.
Tests run ONLY in CI pipeline with real AWS resources and synthetic external API data.

Two fixture sets are available:
1. Legacy fixtures (mock_tiingo, mock_finnhub, etc.) - for local mocked tests
2. Preprod fixtures (api_client, tiingo_handler, etc.) - for preprod E2E tests

Cache Management:
    All module-level caches are cleared before each test for isolation.
    Caches affected: circuit_breaker, quota_tracker, configurations, sentiment, metrics
"""

import asyncio
import os
import uuid
from collections.abc import AsyncGenerator, Generator, Iterator
from contextlib import contextmanager
from dataclasses import dataclass

import boto3
import pytest
import pytest_asyncio

# Import cache clearing functions for test isolation
from src.lambdas.dashboard.configurations import clear_config_cache
from src.lambdas.dashboard.metrics import clear_metrics_cache
from src.lambdas.dashboard.sentiment import clear_sentiment_cache
from src.lambdas.shared.circuit_breaker import (
    clear_cache as clear_circuit_breaker_cache,
)
from src.lambdas.shared.quota_tracker import clear_quota_cache

# Legacy mock imports (for backwards compatibility with existing tests)
try:
    from tests.fixtures.mocks.mock_finnhub import (
        MockFinnhubAdapter,
        create_mock_finnhub,
    )
    from tests.fixtures.mocks.mock_sendgrid import MockSendGrid, create_mock_sendgrid
    from tests.fixtures.mocks.mock_tiingo import MockTiingoAdapter, create_mock_tiingo
    from tests.fixtures.synthetic.test_oracle import (
        TestOracle,
        TestScenario,
        create_test_oracle,
    )

    LEGACY_FIXTURES_AVAILABLE = True
except ImportError:
    # Legacy fixtures not available, skip them
    LEGACY_FIXTURES_AVAILABLE = False

# Preprod fixture imports (008-e2e-validation-suite)
from tests.e2e.fixtures.finnhub import SyntheticFinnhubHandler
from tests.e2e.fixtures.sendgrid import SyntheticSendGridHandler
from tests.e2e.fixtures.tiingo import SyntheticTiingoHandler
from tests.e2e.helpers.api_client import PreprodAPIClient
from tests.fixtures.synthetic.config_generator import (
    ConfigGenerator,
    SyntheticConfiguration,
    create_config_generator,
)

# Note: cleanup_by_prefix is available for manual cleanup if needed:
# from tests.e2e.helpers.cleanup import cleanup_by_prefix


# =============================================================================
# Cache Clearing Fixture (for test isolation)
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
    # Optionally clear after test too (for safety)
    clear_circuit_breaker_cache()
    clear_quota_cache()
    clear_config_cache()
    clear_sentiment_cache()
    clear_metrics_cache()


@dataclass
class SkipInfo:
    """Standardized skip message for E2E tests.

    Provides structured information about why a test was skipped
    and how to run it if desired.

    Format: SKIPPED: {condition}
            Reason: {reason}
            To run: {remediation}
    """

    condition: str
    reason: str
    remediation: str

    def __str__(self) -> str:
        """Format as standardized skip message."""
        return (
            f"SKIPPED: {self.condition}\n"
            f"Reason: {self.reason}\n"
            f"To run: {self.remediation}"
        )

    def skip(self) -> None:
        """Call pytest.skip with formatted message."""
        pytest.skip(str(self))


@dataclass
class FailureInjectionConfig:
    """Configuration for failure injection tests.

    Controls which failure modes are active for testing error handling
    paths in the processing layer.
    """

    tiingo_fail: bool = False
    finnhub_fail: bool = False
    sendgrid_fail: bool = False
    tiingo_timeout: bool = False
    finnhub_timeout: bool = False
    tiingo_malformed: bool = False
    finnhub_malformed: bool = False
    sendgrid_rate_limit: bool = False

    def has_any_failure(self) -> bool:
        """Check if any failure mode is enabled."""
        return any(
            [
                self.tiingo_fail,
                self.finnhub_fail,
                self.sendgrid_fail,
                self.tiingo_timeout,
                self.finnhub_timeout,
                self.tiingo_malformed,
                self.finnhub_malformed,
                self.sendgrid_rate_limit,
            ]
        )

    def describe(self) -> str:
        """Return human-readable description of active failure modes."""
        active = []
        if self.tiingo_fail:
            active.append("Tiingo API failure")
        if self.finnhub_fail:
            active.append("Finnhub API failure")
        if self.sendgrid_fail:
            active.append("SendGrid failure")
        if self.tiingo_timeout:
            active.append("Tiingo timeout")
        if self.finnhub_timeout:
            active.append("Finnhub timeout")
        if self.tiingo_malformed:
            active.append("Tiingo malformed response")
        if self.finnhub_malformed:
            active.append("Finnhub malformed response")
        if self.sendgrid_rate_limit:
            active.append("SendGrid rate limit")
        return ", ".join(active) if active else "No failures configured"


# Default test seed for reproducibility
DEFAULT_TEST_SEED = 42


# Session-scoped event loop for async fixtures
@pytest.fixture(scope="session")
def event_loop() -> Iterator[asyncio.AbstractEventLoop]:
    """Create a session-scoped event loop for async fixtures.

    This is required for session-scoped async fixtures to work properly
    with pytest-asyncio. Without this, async fixtures would fail with
    ScopeMismatch errors.
    """
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@dataclass
class E2ETestContext:
    """Context object containing all test fixtures.

    Provides access to mocks, generators, and oracle for test assertions.
    """

    seed: int
    oracle: TestOracle
    mock_tiingo: MockTiingoAdapter
    mock_finnhub: MockFinnhubAdapter
    mock_sendgrid: MockSendGrid

    def reset(self, new_seed: int | None = None) -> None:
        """Reset all fixtures with optional new seed.

        Args:
            new_seed: Optional new seed value
        """
        if new_seed is not None:
            self.seed = new_seed
            self.oracle = create_test_oracle(self.seed)
        self.mock_tiingo.reset(self.seed)
        self.mock_finnhub.reset(self.seed)
        self.mock_sendgrid.reset()

    def generate_scenario(
        self,
        ticker: str,
        days: int = 30,
        news_count: int = 15,
    ) -> TestScenario:
        """Generate a complete test scenario.

        Args:
            ticker: Stock symbol
            days: Number of days of data
            news_count: Number of news articles

        Returns:
            TestScenario with all generated data and expectations
        """
        return self.oracle.generate_test_scenario(ticker, days, news_count)


@pytest.fixture
def e2e_seed() -> int:
    """Provide the test seed, overridable via environment variable.

    Set E2E_TEST_SEED env var to use a different seed.
    """
    return int(os.environ.get("E2E_TEST_SEED", str(DEFAULT_TEST_SEED)))


@pytest.fixture
def test_oracle(e2e_seed: int) -> TestOracle:
    """Provide a test oracle for computing expected values.

    Args:
        e2e_seed: Random seed from fixture

    Returns:
        Configured TestOracle
    """
    return create_test_oracle(e2e_seed)


@pytest.fixture
def mock_tiingo(e2e_seed: int) -> MockTiingoAdapter:
    """Provide a mock Tiingo adapter with synthetic data.

    Args:
        e2e_seed: Random seed from fixture

    Returns:
        Configured MockTiingoAdapter
    """
    return create_mock_tiingo(seed=e2e_seed)


@pytest.fixture
def mock_finnhub(e2e_seed: int) -> MockFinnhubAdapter:
    """Provide a mock Finnhub adapter with synthetic data.

    Args:
        e2e_seed: Random seed from fixture

    Returns:
        Configured MockFinnhubAdapter
    """
    return create_mock_finnhub(seed=e2e_seed)


@pytest.fixture
def mock_sendgrid() -> MockSendGrid:
    """Provide a mock SendGrid for email verification.

    Returns:
        Fresh MockSendGrid instance
    """
    return create_mock_sendgrid()


@pytest.fixture
def e2e_context(
    e2e_seed: int,
    test_oracle: TestOracle,
    mock_tiingo: MockTiingoAdapter,
    mock_finnhub: MockFinnhubAdapter,
    mock_sendgrid: MockSendGrid,
) -> E2ETestContext:
    """Provide a complete E2E test context.

    Args:
        e2e_seed: Random seed
        test_oracle: Oracle for expected values
        mock_tiingo: Mock Tiingo adapter
        mock_finnhub: Mock Finnhub adapter
        mock_sendgrid: Mock SendGrid service

    Returns:
        E2ETestContext with all fixtures
    """
    return E2ETestContext(
        seed=e2e_seed,
        oracle=test_oracle,
        mock_tiingo=mock_tiingo,
        mock_finnhub=mock_finnhub,
        mock_sendgrid=mock_sendgrid,
    )


@pytest.fixture
def test_scenario(e2e_context: E2ETestContext) -> TestScenario:
    """Provide a default test scenario for AAPL.

    Args:
        e2e_context: E2E test context

    Returns:
        TestScenario for AAPL with 30 days of data
    """
    return e2e_context.generate_scenario("AAPL", days=30, news_count=15)


# Helper context managers


@contextmanager
def fail_mode_tiingo(
    mock: MockTiingoAdapter,
) -> Generator[MockTiingoAdapter, None, None]:
    """Context manager to temporarily enable Tiingo fail mode.

    Args:
        mock: MockTiingoAdapter instance

    Yields:
        Mock in fail mode
    """
    original = mock.fail_mode
    mock.fail_mode = True
    try:
        yield mock
    finally:
        mock.fail_mode = original


@contextmanager
def fail_mode_finnhub(
    mock: MockFinnhubAdapter,
) -> Generator[MockFinnhubAdapter, None, None]:
    """Context manager to temporarily enable Finnhub fail mode.

    Args:
        mock: MockFinnhubAdapter instance

    Yields:
        Mock in fail mode
    """
    original = mock.fail_mode
    mock.fail_mode = True
    try:
        yield mock
    finally:
        mock.fail_mode = original


@contextmanager
def rate_limit_sendgrid(mock: MockSendGrid) -> Generator[MockSendGrid, None, None]:
    """Context manager to simulate SendGrid rate limiting.

    Args:
        mock: MockSendGrid instance

    Yields:
        Mock in rate limit mode
    """
    original = mock.rate_limit_mode
    mock.rate_limit_mode = True
    try:
        yield mock
    finally:
        mock.rate_limit_mode = original


# Pytest markers


def pytest_configure(config):
    """Register custom markers for E2E tests."""
    config.addinivalue_line(
        "markers",
        "e2e: mark test as an end-to-end test",
    )
    config.addinivalue_line(
        "markers",
        "slow: mark test as slow running",
    )
    config.addinivalue_line(
        "markers",
        "preprod: mark test as preprod-only (requires AWS credentials)",
    )
    config.addinivalue_line(
        "markers",
        "integration_optional: mark test as requiring specific preprod resources "
        "(may skip if resource not available)",
    )


# =============================================================================
# Preprod E2E Fixtures (008-e2e-validation-suite)
# =============================================================================


@pytest.fixture(scope="session")
def test_run_id() -> str:
    """Unique identifier for this test run.

    Used for test data isolation - all test data is prefixed with this ID
    and cleaned up at the end of the session.
    """
    return f"e2e-{uuid.uuid4().hex[:8]}"


@pytest.fixture(scope="session")
def test_email_domain(test_run_id: str) -> str:
    """Unique email domain for this test run.

    Returns a domain pattern for generating test user emails:
    {user}@{test_run_id}.example.com
    """
    return f"{test_run_id}.example.com"


def generate_test_email(test_email_domain: str, username: str = "user") -> str:
    """Generate a test email address.

    Args:
        test_email_domain: Domain from fixture
        username: Local part of email

    Returns:
        Full test email address
    """
    return f"{username}@{test_email_domain}"


@pytest_asyncio.fixture
async def api_client() -> AsyncGenerator[PreprodAPIClient, None]:
    """Preprod API client for making HTTP requests.

    Function-scoped due to pytest-asyncio's asyncio_default_fixture_loop_scope=function.
    httpx.AsyncClient is lightweight, so per-test creation is acceptable.
    """
    async with PreprodAPIClient() as client:
        yield client


@pytest.fixture(scope="session")
def synthetic_seed(test_run_id: str) -> int:
    """Deterministic seed derived from test run ID.

    Ensures synthetic data is reproducible for a given test run.
    """
    # Extract hex portion and convert to int
    hex_part = test_run_id.split("-")[1]
    return int(hex_part, 16)


@pytest.fixture
def tiingo_handler(synthetic_seed: int) -> SyntheticTiingoHandler:
    """Synthetic Tiingo API handler for generating test data."""
    return SyntheticTiingoHandler(seed=synthetic_seed)


@pytest.fixture
def finnhub_handler(synthetic_seed: int) -> SyntheticFinnhubHandler:
    """Synthetic Finnhub API handler for generating test data."""
    return SyntheticFinnhubHandler(seed=synthetic_seed)


@pytest.fixture
def sendgrid_handler(synthetic_seed: int) -> SyntheticSendGridHandler:
    """Synthetic SendGrid handler for email testing."""
    return SyntheticSendGridHandler(seed=synthetic_seed)


@pytest.fixture
def config_generator(synthetic_seed: int) -> ConfigGenerator:
    """Provide config generator seeded from test run.

    Args:
        synthetic_seed: Seed derived from test run ID

    Returns:
        ConfigGenerator instance
    """
    return create_config_generator(seed=synthetic_seed)


@pytest.fixture
def synthetic_config(
    config_generator: ConfigGenerator,
    test_run_id: str,
) -> SyntheticConfiguration:
    """Provide synthetic configuration for test.

    Args:
        config_generator: ConfigGenerator fixture
        test_run_id: Unique test run identifier

    Returns:
        SyntheticConfiguration with unique name and tickers
    """
    return config_generator.generate_config(test_run_id)


@pytest.fixture
def failure_config() -> FailureInjectionConfig:
    """Provide default failure injection config (no failures).

    Tests can modify this to enable specific failure modes.
    """
    return FailureInjectionConfig()


@pytest.fixture(scope="session")
def dynamodb_table():
    """DynamoDB table resource for direct database access.

    Used for:
    - Verifying data persistence
    - Testing circuit breaker state
    - Cleanup operations
    """
    dynamodb = boto3.resource(
        "dynamodb",
        region_name=os.environ.get("AWS_REGION", "us-east-1"),
    )
    table_name = os.environ.get("DYNAMODB_TABLE", "sentiment-analyzer-preprod")
    return dynamodb.Table(table_name)


@pytest.fixture(scope="session")
def cloudwatch_logs_client():
    """CloudWatch Logs client for observability tests.

    Used for:
    - Querying Lambda function logs
    - Verifying log messages
    """
    return boto3.client(
        "logs",
        region_name=os.environ.get("AWS_REGION", "us-east-1"),
    )


@pytest.fixture(scope="session")
def cloudwatch_client():
    """CloudWatch client for metrics and alarms.

    Used for:
    - Querying custom metrics
    - Checking alarm states
    """
    return boto3.client(
        "cloudwatch",
        region_name=os.environ.get("AWS_REGION", "us-east-1"),
    )


@pytest.fixture
def synthetic_data(
    synthetic_seed: int,
    tiingo_handler: SyntheticTiingoHandler,
    finnhub_handler: SyntheticFinnhubHandler,
    sendgrid_handler: SyntheticSendGridHandler,
) -> dict:
    """Bundle of all synthetic data generators.

    Returns:
        Dict with 'tiingo', 'finnhub', 'sendgrid', and 'seed' keys
    """
    return {
        "seed": synthetic_seed,
        "tiingo": tiingo_handler,
        "finnhub": finnhub_handler,
        "sendgrid": sendgrid_handler,
    }


# TTL-based cleanup configuration (7 days)
# Test data is NOT auto-deleted. Instead, all test data items include a TTL
# attribute set to 7 days in the future. DynamoDB automatically removes
# expired items via TTL. This allows:
# - Re-using test data for debugging
# - Avoiding cleanup failures during tests
# - Automatic garbage collection after 7 days

E2E_TEST_TTL_DAYS = 7  # TTL for E2E test data (7 days)


def calculate_ttl_timestamp(days: int = E2E_TEST_TTL_DAYS) -> int:
    """Calculate TTL timestamp for test data.

    Args:
        days: Number of days until expiration (default: 7)

    Returns:
        Unix timestamp for TTL attribute
    """
    from datetime import UTC, datetime, timedelta

    return int((datetime.now(UTC) + timedelta(days=days)).timestamp())


@pytest.fixture(scope="session", autouse=True)
def cleanup_test_data(test_run_id: str) -> Generator[None, None, None]:
    """Log test run ID for reference (no auto-cleanup).

    Test data uses TTL-based expiration (7 days) instead of immediate cleanup.
    This fixture logs the test run ID for debugging and artifact inspection.

    To manually cleanup if needed:
        from tests.e2e.helpers.cleanup import cleanup_by_prefix
        await cleanup_by_prefix("e2e-XXXXXXXX")
    """
    print(f"\nE2E Test Run ID: {test_run_id}")
    print(f"Test data will auto-expire in {E2E_TEST_TTL_DAYS} days via DynamoDB TTL")

    # Setup: nothing to do
    yield

    # Teardown: No cleanup - TTL handles expiration
    # Log summary for debugging
    print(f"\nTest run {test_run_id} completed.")
    print("Data preserved for debugging. Will expire automatically via TTL.")


# =============================================================================
# Test Metrics Tracking (US5 - Skip Rate Monitoring)
# =============================================================================


@dataclass
class TestMetrics:
    """Track test execution metrics for skip rate analysis.

    Collects statistics during test run for reporting:
    - Total tests executed
    - Tests passed
    - Tests failed
    - Tests skipped (with categorization)

    Target: Skip rate below 15% (SC-003)
    """

    total: int = 0
    passed: int = 0
    failed: int = 0
    skipped: int = 0
    skip_reasons: dict = None  # Categorized skip reasons

    def __post_init__(self):
        """Initialize skip_reasons dict."""
        if self.skip_reasons is None:
            self.skip_reasons = {}

    @property
    def skip_rate(self) -> float:
        """Calculate skip rate as percentage."""
        if self.total == 0:
            return 0.0
        return (self.skipped / self.total) * 100

    @property
    def is_within_threshold(self) -> bool:
        """Check if skip rate is below 15% threshold."""
        return self.skip_rate < 15.0

    def record_skip(self, reason: str) -> None:
        """Record a skip with categorized reason."""
        self.skipped += 1
        self.total += 1
        # Categorize by common patterns
        if "not implemented" in reason.lower():
            category = "endpoint_not_implemented"
        elif "500" in reason or "api issue" in reason.lower():
            category = "api_error"
        elif "not available" in reason.lower():
            category = "resource_unavailable"
        elif "access" in reason.lower():
            category = "access_denied"
        else:
            category = "other"
        self.skip_reasons[category] = self.skip_reasons.get(category, 0) + 1

    def summary(self) -> str:
        """Generate human-readable summary."""
        lines = [
            "Test Metrics Summary:",
            f"  Total: {self.total}",
            f"  Passed: {self.passed}",
            f"  Failed: {self.failed}",
            f"  Skipped: {self.skipped} ({self.skip_rate:.1f}%)",
            f"  Skip rate threshold: {'✅ PASS' if self.is_within_threshold else '❌ FAIL'} (<15%)",
        ]
        if self.skip_reasons:
            lines.append("  Skip reasons:")
            for reason, count in sorted(self.skip_reasons.items(), key=lambda x: -x[1]):
                lines.append(f"    - {reason}: {count}")
        return "\n".join(lines)


# Global metrics instance for session-wide tracking
_test_metrics = TestMetrics()


def get_test_metrics() -> TestMetrics:
    """Get the global test metrics instance."""
    return _test_metrics


def pytest_runtest_makereport(item, call):
    """Hook to track test results for metrics."""
    if call.when == "call":
        _test_metrics.total += 1
        if call.excinfo is None:
            _test_metrics.passed += 1
        elif call.excinfo.typename == "Skipped":
            # Skipped is already counted via record_skip or here
            reason = str(call.excinfo.value) if call.excinfo.value else "unknown"
            if _test_metrics.skipped < _test_metrics.total:
                # Only record if not already recorded via SkipInfo
                _test_metrics.record_skip(reason)
        else:
            _test_metrics.failed += 1


def pytest_sessionfinish(session, exitstatus):
    """Hook to print metrics summary at end of session."""
    if _test_metrics.total > 0:
        print(f"\n{_test_metrics.summary()}")
