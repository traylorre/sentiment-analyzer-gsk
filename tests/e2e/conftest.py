"""E2E test configuration with synthetic data setup.

Provides fixtures for E2E tests that use synthetic deterministic data.
Ensures tests are reproducible and don't depend on external API state.
"""

import os
from collections.abc import Generator
from contextlib import contextmanager
from dataclasses import dataclass

import pytest

from tests.fixtures.mocks.mock_finnhub import MockFinnhubAdapter, create_mock_finnhub
from tests.fixtures.mocks.mock_sendgrid import MockSendGrid, create_mock_sendgrid
from tests.fixtures.mocks.mock_tiingo import MockTiingoAdapter, create_mock_tiingo
from tests.fixtures.synthetic.test_oracle import (
    TestOracle,
    TestScenario,
    create_test_oracle,
)

# Default test seed for reproducibility
DEFAULT_TEST_SEED = 42


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
