"""
Unit Tests for NewsAPI Adapter
===============================

Tests NewsAPI adapter with mocked HTTP responses.

For On-Call Engineers:
    These tests verify:
    - Rate limit handling (429 responses)
    - Authentication errors (401 responses)
    - Retry logic with exponential backoff
    - Circuit breaker behavior

For Developers:
    - Uses responses library to mock HTTP requests
    - Test both success and error scenarios
    - Verify exponential backoff timing
"""


import pytest
import responses
from responses import matchers

from src.lambdas.ingestion.adapters.base import (
    AdapterError,
    AuthenticationError,
    RateLimitError,
)
from src.lambdas.ingestion.adapters.newsapi import (
    NEWSAPI_BASE_URL,
    NewsAPIAdapter,
)


@pytest.fixture
def adapter():
    """Create a NewsAPI adapter with test API key."""
    return NewsAPIAdapter(api_key="test-api-key-12345")


@pytest.fixture
def sample_response():
    """Sample successful NewsAPI response."""
    return {
        "status": "ok",
        "totalResults": 2,
        "articles": [
            {
                "source": {"id": "test-source", "name": "Test News"},
                "author": "Test Author",
                "title": "Test Article 1",
                "description": "Description 1",
                "url": "https://example.com/article/1",
                "urlToImage": "https://example.com/image1.jpg",
                "publishedAt": "2025-11-17T14:30:00Z",
                "content": "Article content 1...",
            },
            {
                "source": {"id": "test-source", "name": "Test News"},
                "author": "Another Author",
                "title": "Test Article 2",
                "description": "Description 2",
                "url": "https://example.com/article/2",
                "urlToImage": "https://example.com/image2.jpg",
                "publishedAt": "2025-11-17T15:00:00Z",
                "content": "Article content 2...",
            },
        ],
    }


class TestNewsAPIAdapterBasic:
    """Basic tests for NewsAPI adapter."""

    def test_get_source_name(self, adapter):
        """Test source name is 'newsapi'."""
        assert adapter.get_source_name() == "newsapi"

    @responses.activate
    def test_fetch_items_success(self, adapter, sample_response):
        """Test successful fetch returns articles."""
        responses.add(
            responses.GET,
            NEWSAPI_BASE_URL,
            json=sample_response,
            status=200,
        )

        articles = adapter.fetch_items("AI")

        assert len(articles) == 2
        assert articles[0]["title"] == "Test Article 1"
        assert articles[1]["title"] == "Test Article 2"

    @responses.activate
    def test_fetch_items_normalizes_articles(self, adapter, sample_response):
        """Test that articles are normalized to standard format."""
        responses.add(
            responses.GET,
            NEWSAPI_BASE_URL,
            json=sample_response,
            status=200,
        )

        articles = adapter.fetch_items("AI")

        # Check normalized fields
        article = articles[0]
        assert "url" in article
        assert "title" in article
        assert "description" in article
        assert "publishedAt" in article
        assert "author" in article
        assert "source" in article

    @responses.activate
    def test_fetch_items_with_custom_page_size(self, adapter, sample_response):
        """Test custom page size is passed to API.

        Verifies that when page_size=50 is provided, the NewsAPI request includes
        pageSize=50 in the query parameters (newsapi.py line 164).
        """
        responses.add(
            responses.GET,
            NEWSAPI_BASE_URL,
            json=sample_response,
            status=200,
        )

        adapter.fetch_items("AI", page_size=50)

        # Verify request was made with correct page size
        assert len(responses.calls) == 1
        request_params = responses.calls[0].request.params
        assert request_params["pageSize"] == "50"


class TestNewsAPIAdapterErrors:
    """Test error handling in NewsAPI adapter."""

    @responses.activate
    def test_authentication_error(self, adapter, caplog):
        """Test 401 raises AuthenticationError."""
        responses.add(
            responses.GET,
            NEWSAPI_BASE_URL,
            json={"status": "error", "message": "Invalid API key"},
            status=401,
        )

        with pytest.raises(AuthenticationError, match="Invalid NewsAPI key"):
            adapter.fetch_items("AI")

        # Verify expected error was logged
        from tests.conftest import assert_error_logged

        assert_error_logged(caplog, "NewsAPI authentication failed")

    @responses.activate
    def test_rate_limit_error(self, adapter):
        """Test 429 raises RateLimitError."""
        responses.add(
            responses.GET,
            NEWSAPI_BASE_URL,
            json={"status": "error", "message": "Rate limited"},
            status=429,
            headers={"Retry-After": "3600"},
        )

        with pytest.raises(RateLimitError) as exc_info:
            adapter.fetch_items("AI")

        assert exc_info.value.retry_after == 3600

    @responses.activate
    def test_api_error_response(self, adapter):
        """Test API error status in response body."""
        responses.add(
            responses.GET,
            NEWSAPI_BASE_URL,
            json={"status": "error", "message": "Invalid parameter"},
            status=200,  # NewsAPI returns 200 with error in body sometimes
        )

        with pytest.raises(AdapterError, match="Invalid parameter"):
            adapter.fetch_items("AI")

    @responses.activate
    def test_empty_articles(self, adapter):
        """Test handling of empty articles list."""
        responses.add(
            responses.GET,
            NEWSAPI_BASE_URL,
            json={"status": "ok", "totalResults": 0, "articles": []},
            status=200,
        )

        articles = adapter.fetch_items("AI")

        assert articles == []


class TestNewsAPIAdapterRetries:
    """Test retry logic and exponential backoff."""

    @responses.activate
    def test_retry_on_server_error(self, adapter, sample_response):
        """Test retries on 500 errors."""
        # First two requests fail, third succeeds
        responses.add(
            responses.GET,
            NEWSAPI_BASE_URL,
            json={"error": "Server error"},
            status=500,
        )
        responses.add(
            responses.GET,
            NEWSAPI_BASE_URL,
            json={"error": "Server error"},
            status=500,
        )
        responses.add(
            responses.GET,
            NEWSAPI_BASE_URL,
            json=sample_response,
            status=200,
        )

        articles = adapter.fetch_items("AI")

        assert len(articles) == 2
        assert len(responses.calls) == 3

    @responses.activate
    def test_max_retries_exceeded(self, adapter):
        """Test AdapterError after max retries."""
        # All requests fail
        for _ in range(3):
            responses.add(
                responses.GET,
                NEWSAPI_BASE_URL,
                json={"error": "Server error"},
                status=500,
            )

        with pytest.raises(AdapterError, match="server error"):
            adapter.fetch_items("AI")

        assert len(responses.calls) == 3

    @responses.activate
    def test_timeout_retry(self, adapter, sample_response):
        """Test retry on timeout."""
        import requests as req_lib

        # First request times out, second succeeds
        responses.add(
            responses.GET,
            NEWSAPI_BASE_URL,
            body=req_lib.exceptions.Timeout(),
        )
        responses.add(
            responses.GET,
            NEWSAPI_BASE_URL,
            json=sample_response,
            status=200,
        )

        articles = adapter.fetch_items("AI")

        assert len(articles) == 2


class TestNewsAPIAdapterCircuitBreaker:
    """Test circuit breaker behavior."""

    @responses.activate
    def test_circuit_breaker_opens(self, adapter, caplog):
        """Test circuit opens after consecutive failures."""
        # Add many failures
        for _ in range(10):
            responses.add(
                responses.GET,
                NEWSAPI_BASE_URL,
                json={"status": "error", "message": "Error"},
                status=500,
            )

        # First few calls should trigger retries
        for _ in range(3):
            try:
                adapter.fetch_items("AI")
            except AdapterError:
                pass

        # Circuit should now be open
        with pytest.raises(AdapterError, match="Circuit breaker open"):
            adapter.fetch_items("AI")

        # Verify expected error was logged
        from tests.conftest import assert_error_logged

        assert_error_logged(caplog, "Circuit breaker opened")

    @responses.activate
    def test_circuit_breaker_resets_on_success(self, adapter, sample_response):
        """Test circuit breaker resets after success."""
        # One failure
        responses.add(
            responses.GET,
            NEWSAPI_BASE_URL,
            json={"error": "Error"},
            status=500,
        )
        responses.add(
            responses.GET,
            NEWSAPI_BASE_URL,
            json={"error": "Error"},
            status=500,
        )
        responses.add(
            responses.GET,
            NEWSAPI_BASE_URL,
            json={"error": "Error"},
            status=500,
        )

        # Then success
        responses.add(
            responses.GET,
            NEWSAPI_BASE_URL,
            json=sample_response,
            status=200,
        )

        try:
            adapter.fetch_items("AI")
        except AdapterError:
            pass

        # Success should reset counter
        articles = adapter.fetch_items("AI")
        assert len(articles) == 2
        assert adapter._consecutive_failures == 0


class TestNewsAPIAdapterValidation:
    """Test article validation and filtering."""

    @responses.activate
    def test_filters_invalid_articles(self, adapter):
        """Test that articles without required fields are filtered."""
        response = {
            "status": "ok",
            "totalResults": 3,
            "articles": [
                {
                    "url": "https://example.com/1",
                    "title": "Valid Article",
                    "publishedAt": "2025-11-17T14:30:00Z",
                },
                {
                    # Missing URL, title, and publishedAt
                    "description": "Invalid article",
                },
                {
                    "title": "Valid without URL",
                    "publishedAt": "2025-11-17T15:00:00Z",
                },
            ],
        }

        responses.add(
            responses.GET,
            NEWSAPI_BASE_URL,
            json=response,
            status=200,
        )

        articles = adapter.fetch_items("AI")

        # Should have 2 valid articles (one filtered)
        assert len(articles) == 2

    @responses.activate
    def test_handles_missing_optional_fields(self, adapter):
        """Test articles with missing optional fields."""
        response = {
            "status": "ok",
            "totalResults": 1,
            "articles": [
                {
                    "url": "https://example.com/1",
                    "title": "Minimal Article",
                    "publishedAt": "2025-11-17T14:30:00Z",
                    # Missing: author, description, content, urlToImage
                },
            ],
        }

        responses.add(
            responses.GET,
            NEWSAPI_BASE_URL,
            json=response,
            status=200,
        )

        articles = adapter.fetch_items("AI")

        assert len(articles) == 1
        assert articles[0]["author"] is None
        assert articles[0]["description"] == ""


class TestNewsAPIAdapterHeaders:
    """Test that correct headers are sent."""

    @responses.activate
    def test_api_key_header(self, adapter, sample_response):
        """Test API key is sent in header."""
        responses.add(
            responses.GET,
            NEWSAPI_BASE_URL,
            json=sample_response,
            status=200,
            match=[matchers.header_matcher({"X-Api-Key": "test-api-key-12345"})],
        )

        adapter.fetch_items("AI")

        assert len(responses.calls) == 1
