"""Tests for ingestion adapter base classes."""

import pytest

from src.lambdas.ingestion.adapters.base import (
    AdapterError,
    AuthenticationError,
    BaseAdapter,
    ConnectionError,
    RateLimitError,
)


class ConcreteAdapter(BaseAdapter):
    """Concrete implementation for testing."""

    def fetch_items(self, tag, **kwargs):
        return [{"url": "https://example.com", "title": f"Article about {tag}"}]

    def get_source_name(self):
        return "test"


class TestBaseAdapter:
    """Tests for BaseAdapter ABC."""

    def test_concrete_implementation(self):
        adapter = ConcreteAdapter()
        items = adapter.fetch_items("AAPL")
        assert len(items) == 1
        assert "AAPL" in items[0]["title"]

    def test_source_name(self):
        adapter = ConcreteAdapter()
        assert adapter.get_source_name() == "test"

    def test_cannot_instantiate_abstract(self):
        with pytest.raises(TypeError):
            BaseAdapter()  # type: ignore[abstract]


class TestAdapterExceptions:
    """Tests for adapter exception hierarchy."""

    def test_rate_limit_error(self):
        err = RateLimitError("Too fast", retry_after=30)
        assert err.retry_after == 30
        assert "Too fast" in str(err)

    def test_rate_limit_error_no_retry(self):
        err = RateLimitError("Slow down")
        assert err.retry_after is None

    def test_authentication_error_is_adapter_error(self):
        assert issubclass(AuthenticationError, AdapterError)

    def test_connection_error_is_adapter_error(self):
        assert issubclass(ConnectionError, AdapterError)
