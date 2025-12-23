# Quickstart: OHLC Resolution Selector (Feature 1035)

## Overview

This feature adds intraday resolution selection to the OHLC candlestick chart. Users can select 1-minute, 5-minute, 15-minute, 30-minute, 1-hour, or daily candles.

## Usage

### API Endpoint

```bash
# Daily candles (default)
curl "https://api.example.com/api/v2/tickers/AAPL/ohlc?range=1M"

# 5-minute candles for the past week
curl "https://api.example.com/api/v2/tickers/AAPL/ohlc?range=1W&resolution=5"

# 1-hour candles with custom date range
curl "https://api.example.com/api/v2/tickers/AAPL/ohlc?resolution=60&start_date=2024-01-15&end_date=2024-01-22"
```

### Response

```json
{
  "ticker": "AAPL",
  "resolution": "5",
  "candles": [
    {
      "date": "2024-01-22T14:30:00Z",
      "open": 150.25,
      "high": 151.00,
      "low": 149.50,
      "close": 150.75,
      "volume": 1234567
    }
  ],
  "time_range": "1W",
  "start_date": "2024-01-15",
  "end_date": "2024-01-22",
  "count": 288,
  "source": "finnhub"
}
```

### Resolution Values

| UI Label | API Value | Max Time Range |
|----------|-----------|----------------|
| 1 min    | "1"       | 7 days         |
| 5 min    | "5"       | 30 days        |
| 15 min   | "15"      | 90 days        |
| 30 min   | "30"      | 90 days        |
| 1 hour   | "60"      | 180 days       |
| Daily    | "D"       | 365 days       |

## Frontend Integration

### useChartData Hook

```typescript
const { data, isLoading, error } = useChartData(
  ticker,
  timeRange,
  resolution,  // NEW: "1" | "5" | "15" | "30" | "60" | "D"
  sentimentSource
);
```

### Resolution State

Resolution preference is stored in sessionStorage and persists across page navigations within the same session.

## Testing

### Unit Tests

```bash
# Backend
pytest tests/unit/lambdas/dashboard/test_ohlc.py -v

# Frontend
npm test -- --grep "resolution"
```

### E2E Tests

```bash
# Resolution selection test
pytest tests/e2e/test_ohlc_resolution.py -v
```

## Configuration

### Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `API_CACHE_TTL_OHLC_SECONDS` | Cache TTL for OHLC data | 3600 |
| `FINNHUB_API_KEY` | Finnhub API key (required) | - |

### Cache Behavior

- Daily resolution: 1 hour TTL
- Intraday resolutions: 5 minute TTL (fresher data during market hours)

## Troubleshooting

### "Intraday data unavailable"

**Cause**: Ticker doesn't have intraday data (e.g., mutual funds, ETFs)
**Solution**: System automatically falls back to daily. Message displayed to user.

### Rate Limiting

**Cause**: Exceeded Finnhub free tier (60 calls/min)
**Solution**: Reduce resolution changes, allow cache to work. Consider paid tier.

### Missing Data Points

**Cause**: Market closed, holidays, or gaps in trading
**Solution**: Chart correctly displays gaps. This is expected behavior.
