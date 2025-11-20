"""
NewsAPI Response Fixtures

Comprehensive collection of NewsAPI responses for testing edge cases.

Real NewsAPI returns various response shapes based on query success,
API errors, missing data, etc. These fixtures ensure we handle all cases.

Usage:
    from tests.fixtures.newsapi_responses import NEWSAPI_HAPPY_PATH
    responses.add(responses.GET, NEWSAPI_BASE_URL, json=NEWSAPI_HAPPY_PATH)
"""

# ============================================================================
# Happy Path Responses
# ============================================================================

NEWSAPI_HAPPY_PATH = {
    "status": "ok",
    "totalResults": 1,
    "articles": [
        {
            "source": {"id": "techcrunch", "name": "TechCrunch"},
            "author": "Test Author",
            "title": "Breaking AI News: New Model Released",
            "description": "A comprehensive article about AI developments",
            "url": "https://example.com/ai-news",
            "urlToImage": "https://example.com/image.jpg",
            "publishedAt": "2025-11-20T10:00:00Z",
            "content": "Full article content here...",
        }
    ],
}

NEWSAPI_MULTIPLE_ARTICLES = {
    "status": "ok",
    "totalResults": 3,
    "articles": [
        {
            "source": {"id": "bbc-news", "name": "BBC News"},
            "author": "John Doe",
            "title": "AI Regulation Updates",
            "description": "New regulations for AI systems",
            "url": "https://example.com/ai-regulation",
            "urlToImage": "https://example.com/reg.jpg",
            "publishedAt": "2025-11-20T09:00:00Z",
            "content": "Regulation details...",
        },
        {
            "source": {"id": "reuters", "name": "Reuters"},
            "author": "Jane Smith",
            "title": "Machine Learning Breakthrough",
            "description": "Researchers achieve new milestone",
            "url": "https://example.com/ml-breakthrough",
            "urlToImage": "https://example.com/ml.jpg",
            "publishedAt": "2025-11-20T08:00:00Z",
            "content": "Breakthrough details...",
        },
        {
            "source": {"id": "the-verge", "name": "The Verge"},
            "author": "Tech Reporter",
            "title": "AI Startup Raises $100M",
            "description": "Funding round details",
            "url": "https://example.com/funding",
            "urlToImage": "https://example.com/fund.jpg",
            "publishedAt": "2025-11-20T07:00:00Z",
            "content": "Funding details...",
        },
    ],
}

# ============================================================================
# Empty/No Results Responses
# ============================================================================

NEWSAPI_EMPTY_RESULTS = {"status": "ok", "totalResults": 0, "articles": []}

NEWSAPI_NO_ARTICLES_KEY = {
    "status": "ok",
    "totalResults": 0
    # Missing "articles" key entirely
}

# ============================================================================
# Missing/Null Field Responses
# ============================================================================

NEWSAPI_MISSING_TITLE = {
    "status": "ok",
    "totalResults": 1,
    "articles": [
        {
            "source": {"id": "source-id", "name": "Source Name"},
            "author": "Author Name",
            # "title": missing!
            "description": "Description text",
            "url": "https://example.com/article",
            "publishedAt": "2025-11-20T10:00:00Z",
            "content": "Content...",
        }
    ],
}

NEWSAPI_NULL_FIELDS = {
    "status": "ok",
    "totalResults": 1,
    "articles": [
        {
            "source": {"id": None, "name": "Source Name"},
            "author": None,
            "title": "Article Title",
            "description": None,
            "url": "https://example.com/article",
            "urlToImage": None,
            "publishedAt": "2025-11-20T10:00:00Z",
            "content": None,
        }
    ],
}

NEWSAPI_MISSING_URL = {
    "status": "ok",
    "totalResults": 1,
    "articles": [
        {
            "source": {"id": "source-id", "name": "Source Name"},
            "author": "Author Name",
            "title": "Article Title",
            "description": "Description",
            # "url": missing! (This is critical - we use URL as part of source_id)
            "publishedAt": "2025-11-20T10:00:00Z",
            "content": "Content...",
        }
    ],
}

NEWSAPI_MISSING_PUBLISHED_AT = {
    "status": "ok",
    "totalResults": 1,
    "articles": [
        {
            "source": {"id": "source-id", "name": "Source Name"},
            "author": "Author Name",
            "title": "Article Title",
            "description": "Description",
            "url": "https://example.com/article",
            # "publishedAt": missing!
            "content": "Content...",
        }
    ],
}

# ============================================================================
# API Error Responses
# ============================================================================

NEWSAPI_ERROR_RATE_LIMITED = {
    "status": "error",
    "code": "rateLimited",
    "message": "You have made too many requests recently. Developer accounts are limited to 100 requests over a 24 hour period (50 requests available). Please upgrade to a paid plan if you need more requests.",
}

NEWSAPI_ERROR_API_KEY_INVALID = {
    "status": "error",
    "code": "apiKeyInvalid",
    "message": "Your API key is invalid or incorrect. Check your key, or go to https://newsapi.org to create a free API key.",
}

NEWSAPI_ERROR_API_KEY_MISSING = {
    "status": "error",
    "code": "apiKeyMissing",
    "message": "Your API key is missing. Append this to the URL with the apiKey param, or use the x-api-key HTTP header.",
}

NEWSAPI_ERROR_PARAMETER_INVALID = {
    "status": "error",
    "code": "parameterInvalid",
    "message": "You've included a parameter in your request which is currently not supported. q is required.",
}

NEWSAPI_ERROR_PARAMETER_MISSING = {
    "status": "error",
    "code": "parametersMissing",
    "message": "Required parameters are missing. Please check the documentation.",
}

NEWSAPI_ERROR_SOURCE_DOES_NOT_EXIST = {
    "status": "error",
    "code": "sourceDoesNotExist",
    "message": "You've requested a source which does not exist.",
}

NEWSAPI_ERROR_UNEXPECTED = {
    "status": "error",
    "code": "unexpectedError",
    "message": "An unexpected error occurred. Please try again later.",
}

# ============================================================================
# Large Response (Bulk)
# ============================================================================


def generate_bulk_articles(count=100):
    """
    Generate a large NewsAPI response with many articles.

    Used to test:
    - Performance with large responses
    - Pagination handling
    - Memory usage
    - Deduplication at scale

    Args:
        count: Number of articles to generate (default 100, max supported by NewsAPI)

    Returns:
        Dict: NewsAPI response with `count` articles
    """
    articles = []
    for i in range(count):
        articles.append(
            {
                "source": {"id": f"source-{i}", "name": f"Source {i}"},
                "author": f"Author {i}",
                "title": f"AI Article {i}: Breaking News",
                "description": f"Description for article {i}",
                "url": f"https://example.com/article-{i}",
                "urlToImage": f"https://example.com/image-{i}.jpg",
                "publishedAt": f"2025-11-20T{i % 24:02d}:00:00Z",
                "content": f"Full content for article {i}...",
            }
        )

    return {"status": "ok", "totalResults": count, "articles": articles}


NEWSAPI_BULK_100_ARTICLES = generate_bulk_articles(100)

# ============================================================================
# Partial/Corrupted Data
# ============================================================================

NEWSAPI_PARTIAL_ARTICLE_DATA = {
    "status": "ok",
    "totalResults": 3,
    "articles": [
        # Complete article
        {
            "source": {"id": "source-1", "name": "Source 1"},
            "author": "Author 1",
            "title": "Complete Article",
            "description": "Full description",
            "url": "https://example.com/complete",
            "urlToImage": "https://example.com/image.jpg",
            "publishedAt": "2025-11-20T10:00:00Z",
            "content": "Full content...",
        },
        # Partial article (missing optional fields)
        {
            "source": {"id": "source-2", "name": "Source 2"},
            "author": None,
            "title": "Partial Article",
            "description": None,
            "url": "https://example.com/partial",
            "urlToImage": None,
            "publishedAt": "2025-11-20T09:00:00Z",
            "content": None,
        },
        # Minimal article (only required fields)
        {
            "source": {"id": "source-3", "name": "Source 3"},
            "title": "Minimal Article",
            "url": "https://example.com/minimal",
            "publishedAt": "2025-11-20T08:00:00Z",
        },
    ],
}

NEWSAPI_MIXED_VALID_INVALID = {
    "status": "ok",
    "totalResults": 3,
    "articles": [
        # Valid article
        {
            "source": {"id": "source-1", "name": "Source 1"},
            "author": "Author",
            "title": "Valid Article",
            "description": "Description",
            "url": "https://example.com/valid",
            "publishedAt": "2025-11-20T10:00:00Z",
            "content": "Content...",
        },
        # Invalid article (missing required URL)
        {
            "source": {"id": "source-2", "name": "Source 2"},
            "title": "Invalid Article (no URL)",
            "publishedAt": "2025-11-20T09:00:00Z",
        },
        # Valid article
        {
            "source": {"id": "source-3", "name": "Source 3"},
            "title": "Another Valid Article",
            "url": "https://example.com/valid2",
            "publishedAt": "2025-11-20T08:00:00Z",
        },
    ],
}

# ============================================================================
# Edge Cases
# ============================================================================

NEWSAPI_VERY_LONG_TITLE = {
    "status": "ok",
    "totalResults": 1,
    "articles": [
        {
            "source": {"id": "source-id", "name": "Source Name"},
            "author": "Author",
            "title": "A" * 1000,  # 1000 character title
            "description": "Description",
            "url": "https://example.com/long-title",
            "publishedAt": "2025-11-20T10:00:00Z",
            "content": "Content...",
        }
    ],
}

NEWSAPI_SPECIAL_CHARACTERS = {
    "status": "ok",
    "totalResults": 1,
    "articles": [
        {
            "source": {"id": "source-id", "name": "Source Name"},
            "author": "Authör Ñamé 中文",
            "title": "Article with émojis 🚀🔥 and spëcial çharacters",
            "description": "Description with <HTML> & \"quotes\" and 'apostrophes'",
            "url": "https://example.com/special?param=value&other=123",
            "publishedAt": "2025-11-20T10:00:00Z",
            "content": "Content with\nnewlines\tand\ttabs...",
        }
    ],
}

NEWSAPI_DUPLICATE_ARTICLES = {
    "status": "ok",
    "totalResults": 3,
    "articles": [
        {
            "source": {"id": "source-1", "name": "Source 1"},
            "title": "Duplicate Article",
            "url": "https://example.com/duplicate",
            "publishedAt": "2025-11-20T10:00:00Z",
        },
        {
            "source": {"id": "source-2", "name": "Source 2"},
            "title": "Different Article",
            "url": "https://example.com/different",
            "publishedAt": "2025-11-20T09:00:00Z",
        },
        {
            "source": {"id": "source-1", "name": "Source 1"},
            "title": "Duplicate Article",
            "url": "https://example.com/duplicate",  # Same URL as first
            "publishedAt": "2025-11-20T10:00:00Z",
        },
    ],
}

# ============================================================================
# Future Date Edge Case
# ============================================================================

NEWSAPI_FUTURE_PUBLISHED_AT = {
    "status": "ok",
    "totalResults": 1,
    "articles": [
        {
            "source": {"id": "source-id", "name": "Source Name"},
            "title": "Article from the future",
            "url": "https://example.com/future",
            "publishedAt": "2099-12-31T23:59:59Z",  # Far future date
        }
    ],
}

# ============================================================================
# HTTP Error Simulation (for responses library)
# ============================================================================


def newsapi_http_500():
    """Returns a 500 Internal Server Error response."""
    return (500, {}, "Internal Server Error")


def newsapi_http_503():
    """Returns a 503 Service Unavailable response."""
    return (503, {}, "Service Unavailable")


def newsapi_http_429():
    """Returns a 429 Too Many Requests response."""
    return (429, {}, "Too Many Requests")


# ============================================================================
# Timeout Simulation
# ============================================================================


class NewsAPITimeout:
    """
    Callable that simulates a timeout when used with responses library.

    Usage:
        responses.add_callback(
            responses.GET,
            NEWSAPI_BASE_URL,
            callback=NewsAPITimeout(),
            content_type="application/json"
        )
    """

    def __call__(self, request):
        import time

        time.sleep(61)  # Exceeds typical timeout
        return (200, {}, '{"status":"ok","articles":[]}')
