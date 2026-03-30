# Quickstart: Fix Mock OHLC/Sentiment Data Format

## Prerequisites

- Node.js 18+
- Playwright installed (`npx playwright install chromium`)
- Access to target repo (sentiment-analyzer-gsk)

## Verify mock data alignment

### 1. Compare mock fields against Pydantic models

```bash
# In the target repo, list all fields from OHLCResponse
cd ~/projects/sentiment-analyzer-gsk
grep -E '^\s+\w+:' src/lambdas/shared/models/ohlc.py

# List all fields from SentimentHistoryResponse
grep -E '^\s+\w+:' src/lambdas/shared/models/sentiment_history.py
```

Cross-reference every field in the grep output against the exported mock objects in `frontend/tests/e2e/helpers/mock-api-data.ts`. Every field must be present with the correct type.

### 2. Run Playwright tests against mocks

```bash
cd frontend
npx playwright test
```

All tests should pass. If a test fails due to missing fields or type mismatches, the mock data does not match the API contract.

### 3. Validate constraints manually

Check the mock data file for these properties:

- [ ] OHLC mock has all 11 OHLCResponse fields (ticker, candles, time_range, start_date, end_date, count, source, cache_expires_at, resolution, resolution_fallback, fallback_message)
- [ ] Sentiment mock has all 6 SentimentHistoryResponse fields (ticker, source, history, start_date, end_date, count)
- [ ] Each PriceCandle has 6 fields (date, open, high, low, close, volume)
- [ ] Each SentimentPoint has 5 fields (date, score, source, confidence, label)
- [ ] `count` field matches array length in both mocks
- [ ] Intraday candle dates use ISO 8601 datetime with Z suffix
- [ ] Daily candle dates and sentiment dates use YYYY-MM-DD
- [ ] All prices are positive, high >= low
- [ ] All sentiment scores are between -1.0 and 1.0
- [ ] At least one candle has `volume: null`
- [ ] At least one sentiment point has `confidence: null` and `label: null`
- [ ] OHLC source is "tiingo" or "finnhub"
- [ ] Sentiment source values are from: "tiingo", "finnhub", "our_model", "aggregated"
- [ ] Sentiment label values are from: "positive", "neutral", "negative", or null

### 4. Verify empty-response variants (if added)

- [ ] Empty OHLC mock has `count: 0`, `candles: []`, valid `start_date`/`end_date`
- [ ] Empty sentiment mock has `count: 0`, `history: []`, valid `start_date`/`end_date`
