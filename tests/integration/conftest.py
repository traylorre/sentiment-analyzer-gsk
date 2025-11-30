"""Integration test configuration.

Provides fixtures for integration tests that use moto mocks.
Ensures test isolation by clearing in-memory caches before each test.
"""

import pytest

# Import cache clearing functions for test isolation
from src.lambdas.dashboard.configurations import clear_config_cache
from src.lambdas.dashboard.metrics import clear_metrics_cache
from src.lambdas.dashboard.sentiment import clear_sentiment_cache
from src.lambdas.shared.circuit_breaker import (
    clear_cache as clear_circuit_breaker_cache,
)
from src.lambdas.shared.quota_tracker import clear_quota_cache


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
