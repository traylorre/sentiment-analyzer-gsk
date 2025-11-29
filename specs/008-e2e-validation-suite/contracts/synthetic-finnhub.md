# Synthetic Finnhub API Contract

**Feature**: 008-e2e-validation-suite
**Date**: 2025-11-28

## Overview

This contract defines the synthetic response format for mocking Finnhub API endpoints in E2E tests.

---

## News Sentiment Endpoint

### GET /api/v1/news-sentiment

Returns sentiment analysis for company news.

**Synthetic Response** (200 OK):
```json
{
  "buzz": {
    "articlesInLastWeek": 15,
    "weeklyAverage": 12.5,
    "buzz": 1.2
  },
  "companyNewsScore": 0.65,
  "sectorAverageBullishPercent": 0.55,
  "sectorAverageNewsScore": 0.48,
  "sentiment": {
    "bearishPercent": 0.28,
    "bullishPercent": 0.72
  },
  "symbol": "AAPL"
}
```

**Generation Rules**:
- `bullishPercent`: `0.5 + (seed % 50) / 100` (range: 0.5-1.0)
- `bearishPercent`: `1.0 - bullishPercent`
- `companyNewsScore`: Average of bullish/bearish
- `articlesInLastWeek`: `10 + (seed % 20)`

---

## Quote Endpoint

### GET /api/v1/quote

Returns real-time quote data.

**Synthetic Response** (200 OK):
```json
{
  "c": 151.75,
  "d": 1.25,
  "dp": 0.83,
  "h": 152.50,
  "l": 149.00,
  "o": 150.00,
  "pc": 150.50,
  "t": 1732789200
}
```

**Field Mapping**:
- `c`: Current price (close)
- `d`: Change (absolute)
- `dp`: Change percent
- `h`: High
- `l`: Low
- `o`: Open
- `pc`: Previous close
- `t`: Timestamp (Unix)

---

## Pre-Market Quote

### GET /api/v1/stock/market-status

Returns market status and pre-market data.

**Market Open Response**:
```json
{
  "exchange": "US",
  "holiday": null,
  "isOpen": true,
  "session": "regular",
  "t": 1732789200,
  "timezone": "America/New_York"
}
```

**Market Closed Response**:
```json
{
  "exchange": "US",
  "holiday": null,
  "isOpen": false,
  "session": "closed",
  "t": 1732789200,
  "timezone": "America/New_York"
}
```

**Holiday Response**:
```json
{
  "exchange": "US",
  "holiday": "Thanksgiving Day",
  "isOpen": false,
  "session": "closed",
  "t": 1732789200,
  "timezone": "America/New_York"
}
```

---

## Error Responses

**Rate Limited** (429):
```json
{
  "error": "API limit reached. Please try again later."
}
```

**Invalid Symbol** (200 with empty):
```json
{
  "buzz": null,
  "companyNewsScore": null,
  "sentiment": null,
  "symbol": "INVALID1"
}
```

---

## Handler Configuration

```python
# tests/e2e/fixtures/finnhub.py

class SyntheticFinnhubHandler:
    def __init__(self, seed: int = 12345):
        self.seed = seed
        self.market_status = "open"  # "open", "closed", "holiday"
        self.holiday_name = None

    def set_market_status(self, status: str, holiday: str = None):
        """Configure market status for testing."""
        self.market_status = status
        self.holiday_name = holiday

    def handle_sentiment(self, request: httpx.Request) -> httpx.Response:
        symbol = request.url.params.get("symbol")
        if symbol.startswith("INVALID"):
            return httpx.Response(200, json={"symbol": symbol, "sentiment": None})

        sentiment = generate_sentiment(self.seed, symbol)
        return httpx.Response(200, json=sentiment)

    def handle_market_status(self, request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={
            "exchange": "US",
            "holiday": self.holiday_name,
            "isOpen": self.market_status == "open",
            "session": self.market_status,
            "t": int(time.time()),
            "timezone": "America/New_York"
        })
```
