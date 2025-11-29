# Synthetic Tiingo API Contract

**Feature**: 008-e2e-validation-suite
**Date**: 2025-11-28

## Overview

This contract defines the synthetic response format for mocking Tiingo API endpoints in E2E tests. Responses match the real Tiingo API structure but contain deterministic test data.

---

## News Endpoint

### GET /tiingo/news

Returns news articles for specified tickers.

**Synthetic Response** (200 OK):
```json
[
  {
    "id": "test-12345-AAPL-0",
    "title": "Test article about AAPL #0",
    "description": "Synthetic news article for E2E testing. Generated with seed 12345.",
    "publishedDate": "2025-11-28T10:00:00Z",
    "crawlDate": "2025-11-28T10:05:00Z",
    "source": "test-source",
    "url": "https://test.example.com/articles/test-12345-AAPL-0",
    "tickers": ["AAPL"],
    "tags": ["test", "synthetic"]
  }
]
```

**Generation Rules**:
- `id`: Format `test-{seed}-{ticker}-{index}`
- `title`: Format `Test article about {ticker} #{index}`
- `publishedDate`: Test run start time + (index * 1 hour)
- `source`: Always `test-source`
- `tickers`: Single ticker from request

**Test Oracle Extension**:
```json
{
  "_synthetic": true,
  "_seed": 12345,
  "_expected_sentiment": 0.42
}
```

---

## Daily Prices Endpoint

### GET /tiingo/daily/{ticker}/prices

Returns OHLC price data for ATR calculation.

**Synthetic Response** (200 OK):
```json
[
  {
    "date": "2025-11-28T00:00:00Z",
    "open": 150.00,
    "high": 152.50,
    "low": 149.00,
    "close": 151.75,
    "volume": 1000000,
    "adjOpen": 150.00,
    "adjHigh": 152.50,
    "adjLow": 149.00,
    "adjClose": 151.75,
    "adjVolume": 1000000,
    "divCash": 0.0,
    "splitFactor": 1.0
  }
]
```

**Generation Rules**:
- Base price: `100 + (seed % 100)`
- Daily volatility: ±2% random (seeded)
- Volume: `1000000 + (seed * 1000)`
- 14 days of data for ATR-14 calculation

---

## Error Responses

**Rate Limited** (429):
```json
{
  "error": "Rate limit exceeded",
  "retryAfter": 60
}
```

**Invalid Ticker** (400):
```json
{
  "error": "Unknown ticker: INVALID1"
}
```

**Service Unavailable** (503):
```json
{
  "error": "Service temporarily unavailable"
}
```

---

## Handler Configuration

```python
# tests/e2e/fixtures/tiingo.py

class SyntheticTiingoHandler:
    def __init__(self, seed: int = 12345):
        self.seed = seed
        self.error_mode = False
        self.rate_limit_mode = False

    def set_error_mode(self, enabled: bool):
        """Configure handler to return 503 errors."""
        self.error_mode = enabled

    def set_rate_limit_mode(self, enabled: bool):
        """Configure handler to return 429 rate limits."""
        self.rate_limit_mode = enabled

    def handle_news(self, request: httpx.Request) -> httpx.Response:
        if self.error_mode:
            return httpx.Response(503, json={"error": "Service unavailable"})
        if self.rate_limit_mode:
            return httpx.Response(429, json={"error": "Rate limited"})

        ticker = extract_ticker(request.url)
        articles = generate_news_articles(self.seed, ticker)
        return httpx.Response(200, json=articles)
```
