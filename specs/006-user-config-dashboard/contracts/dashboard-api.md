# Dashboard API Contract

**Feature**: 006-user-config-dashboard | **Version**: 2.0
**Base URL**: `https://{lambda-url}.lambda-url.{region}.on.aws` or `https://api.{domain}/v2`

## Authentication

All endpoints require either:
- **Anonymous**: `X-Anonymous-ID: {uuid}` header (localStorage user ID)
- **Authenticated**: `Authorization: Bearer {cognito_id_token}`

Rate limiting: 100 requests/minute per user ID.

---

## Configuration Endpoints

### List Configurations

```http
GET /api/v2/configurations
```

**Response** (200 OK):
```json
{
  "configurations": [
    {
      "config_id": "uuid",
      "name": "Tech Giants",
      "tickers": ["AAPL", "MSFT", "GOOGL", "NVDA", "META"],
      "timeframe_days": 30,
      "include_extended_hours": false,
      "created_at": "2025-11-26T10:00:00Z",
      "updated_at": "2025-11-26T10:00:00Z"
    }
  ],
  "max_allowed": 2
}
```

### Create Configuration

```http
POST /api/v2/configurations
Content-Type: application/json

{
  "name": "EV Sector",
  "tickers": ["TSLA", "RIVN", "LCID", "NIO", "XPEV"],
  "timeframe_days": 14,
  "include_extended_hours": false
}
```

**Response** (201 Created):
```json
{
  "config_id": "uuid",
  "name": "EV Sector",
  "tickers": [
    {"symbol": "TSLA", "name": "Tesla Inc", "exchange": "NASDAQ"},
    {"symbol": "RIVN", "name": "Rivian Automotive", "exchange": "NASDAQ"},
    ...
  ],
  "timeframe_days": 14,
  "include_extended_hours": false,
  "created_at": "2025-11-26T10:00:00Z"
}
```

**Errors**:
- `400 Bad Request`: Invalid ticker symbol or validation failure
- `409 Conflict`: Maximum configurations (2) reached

### Get Configuration

```http
GET /api/v2/configurations/{config_id}
```

**Response** (200 OK): Same as create response

### Update Configuration

```http
PATCH /api/v2/configurations/{config_id}
Content-Type: application/json

{
  "name": "Updated Name",
  "tickers": ["AAPL", "MSFT"],
  "timeframe_days": 7
}
```

**Response** (200 OK): Updated configuration object

### Delete Configuration

```http
DELETE /api/v2/configurations/{config_id}
```

**Response** (204 No Content)

---

## Sentiment Data Endpoints

### Get Sentiment by Configuration

```http
GET /api/v2/configurations/{config_id}/sentiment
```

**Query Parameters**:
- `sources`: Comma-separated list (default: `tiingo,finnhub,our_model`)

**Response** (200 OK):
```json
{
  "config_id": "uuid",
  "tickers": [
    {
      "symbol": "AAPL",
      "sentiment": {
        "tiingo": {
          "score": 0.65,
          "label": "positive",
          "confidence": 0.82,
          "updated_at": "2025-11-26T09:30:00Z"
        },
        "finnhub": {
          "score": 0.58,
          "label": "positive",
          "bullish_percent": 0.72,
          "bearish_percent": 0.28,
          "updated_at": "2025-11-26T09:35:00Z"
        },
        "our_model": {
          "score": 0.61,
          "label": "positive",
          "confidence": 0.88,
          "model_version": "v2.1.0",
          "updated_at": "2025-11-26T09:32:00Z"
        }
      }
    }
  ],
  "last_updated": "2025-11-26T09:35:00Z",
  "next_refresh_at": "2025-11-26T09:40:00Z",
  "cache_status": "fresh"
}
```

### Get Sentiment Heat Map Data

```http
GET /api/v2/configurations/{config_id}/heatmap
```

**Query Parameters**:
- `view`: `sources` (default) or `timeperiods`

**Response** (200 OK) - Sources View:
```json
{
  "view": "sources",
  "matrix": [
    {
      "ticker": "AAPL",
      "cells": [
        {"source": "tiingo", "score": 0.65, "color": "#22c55e"},
        {"source": "finnhub", "score": 0.58, "color": "#22c55e"},
        {"source": "our_model", "score": 0.61, "color": "#22c55e"}
      ]
    },
    {
      "ticker": "TSLA",
      "cells": [
        {"source": "tiingo", "score": -0.42, "color": "#ef4444"},
        {"source": "finnhub", "score": -0.35, "color": "#ef4444"},
        {"source": "our_model", "score": -0.38, "color": "#ef4444"}
      ]
    }
  ],
  "legend": {
    "positive": {"range": [0.33, 1.0], "color": "#22c55e"},
    "neutral": {"range": [-0.33, 0.33], "color": "#eab308"},
    "negative": {"range": [-1.0, -0.33], "color": "#ef4444"}
  }
}
```

**Response** (200 OK) - Time Periods View:
```json
{
  "view": "timeperiods",
  "matrix": [
    {
      "ticker": "AAPL",
      "cells": [
        {"period": "today", "score": 0.65, "color": "#22c55e"},
        {"period": "1w", "score": 0.52, "color": "#22c55e"},
        {"period": "1m", "score": 0.41, "color": "#22c55e"},
        {"period": "3m", "score": 0.38, "color": "#22c55e"}
      ]
    }
  ]
}
```

---

## Volatility Endpoints

### Get ATR Volatility

```http
GET /api/v2/configurations/{config_id}/volatility
```

**Response** (200 OK):
```json
{
  "config_id": "uuid",
  "tickers": [
    {
      "symbol": "AAPL",
      "atr": {
        "value": 3.42,
        "percent": 2.1,
        "period": 14,
        "trend": "increasing",
        "trend_arrow": "↑",
        "previous_value": 3.15
      },
      "includes_extended_hours": false,
      "updated_at": "2025-11-26T09:30:00Z"
    }
  ]
}
```

### Get Sentiment-Volatility Correlation

```http
GET /api/v2/configurations/{config_id}/correlation
```

**Response** (200 OK):
```json
{
  "config_id": "uuid",
  "tickers": [
    {
      "symbol": "AAPL",
      "correlation": {
        "sentiment_trend": "↑",
        "volatility_trend": "↓",
        "interpretation": "positive_divergence",
        "description": "Sentiment improving while volatility decreasing"
      }
    }
  ]
}
```

---

## Ticker Validation Endpoints

### Validate Ticker

```http
GET /api/v2/tickers/validate?symbol={symbol}
```

**Response** (200 OK) - Valid:
```json
{
  "symbol": "AAPL",
  "status": "valid",
  "name": "Apple Inc",
  "exchange": "NASDAQ"
}
```

**Response** (200 OK) - Delisted:
```json
{
  "symbol": "TWTR",
  "status": "delisted",
  "successor": "X",
  "message": "TWTR replaced with X (Twitter rebrand)"
}
```

**Response** (200 OK) - Invalid:
```json
{
  "symbol": "INVALID",
  "status": "invalid",
  "message": "Symbol not found"
}
```

### Search Tickers (Autocomplete)

```http
GET /api/v2/tickers/search?q={query}&limit=10
```

**Response** (200 OK):
```json
{
  "results": [
    {"symbol": "AAPL", "name": "Apple Inc", "exchange": "NASDAQ"},
    {"symbol": "AMZN", "name": "Amazon.com Inc", "exchange": "NASDAQ"},
    {"symbol": "AMD", "name": "Advanced Micro Devices", "exchange": "NASDAQ"}
  ]
}
```

---

## Refresh Endpoints

### Manual Refresh

```http
POST /api/v2/configurations/{config_id}/refresh
```

**Response** (202 Accepted):
```json
{
  "status": "refresh_queued",
  "estimated_completion": "2025-11-26T09:40:30Z"
}
```

### Get Refresh Status

```http
GET /api/v2/configurations/{config_id}/refresh/status
```

**Response** (200 OK):
```json
{
  "last_refresh": "2025-11-26T09:35:00Z",
  "next_scheduled_refresh": "2025-11-26T09:40:00Z",
  "refresh_interval_seconds": 300,
  "countdown_seconds": 180,
  "is_refreshing": false
}
```

---

## User Endpoints

### Get Current User

```http
GET /api/v2/users/me
```

**Response** (200 OK):
```json
{
  "user_id": "uuid",
  "auth_type": "google",
  "email": "user@example.com",
  "created_at": "2025-11-20T10:00:00Z",
  "configuration_count": 2,
  "alert_count": 5,
  "email_notifications_enabled": true
}
```

### Update User Preferences

```http
PATCH /api/v2/users/me
Content-Type: application/json

{
  "timezone": "America/Los_Angeles",
  "email_notifications_enabled": false
}
```

---

## Error Responses

All errors follow this format:

```json
{
  "error": {
    "code": "VALIDATION_ERROR",
    "message": "Invalid ticker symbol: INVALID",
    "details": {
      "field": "tickers[0]",
      "constraint": "must be valid US stock symbol"
    }
  }
}
```

### Error Codes

| Code | HTTP Status | Description |
|------|-------------|-------------|
| `VALIDATION_ERROR` | 400 | Request validation failed |
| `INVALID_TICKER` | 400 | Ticker symbol not found or invalid |
| `UNAUTHORIZED` | 401 | Missing or invalid auth token |
| `FORBIDDEN` | 403 | Not allowed to access resource |
| `NOT_FOUND` | 404 | Resource not found |
| `CONFLICT` | 409 | Resource conflict (e.g., max configs) |
| `RATE_LIMITED` | 429 | Too many requests |
| `SERVICE_UNAVAILABLE` | 503 | API temporarily unavailable |
| `UPSTREAM_ERROR` | 502 | Tiingo/Finnhub API error |

---

## WebSocket Events (Future Enhancement)

```javascript
// Connection
ws://api.domain/ws?token={auth_token}

// Subscribe to config updates
{ "action": "subscribe", "config_id": "uuid" }

// Sentiment update event
{
  "event": "sentiment_update",
  "config_id": "uuid",
  "ticker": "AAPL",
  "source": "finnhub",
  "score": 0.72
}

// Alert triggered event
{
  "event": "alert_triggered",
  "alert_id": "uuid",
  "ticker": "TSLA",
  "message": "Sentiment dropped below -0.5"
}
```
