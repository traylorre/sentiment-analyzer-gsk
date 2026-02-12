# API Contract: Sentiment History Response

**Endpoint**: `GET /api/v2/tickers/{ticker}/sentiment/history`
**Version**: v2
**Date**: 2025-12-01

## Request

### Path Parameters

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| ticker | string | Yes | Stock ticker symbol (1-5 uppercase letters) |

### Query Parameters

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| source | enum | No | aggregated | Sentiment source: tiingo, finnhub, our_model, aggregated |
| range | enum | No | 1M | Time range: 1W, 1M, 3M, 6M, 1Y |
| start_date | date | No | - | Custom start date (YYYY-MM-DD) |
| end_date | date | No | today | Custom end date (YYYY-MM-DD) |

### Headers

| Header | Type | Required | Description |
|--------|------|----------|-------------|
| X-User-ID | string | Yes | User identification |

## Response

### Success Response (200 OK)

```json
{
  "ticker": "AAPL",
  "source": "aggregated",
  "history": [
    {
      "date": "2024-11-01",
      "score": 0.45,
      "source": "aggregated",
      "confidence": 0.87,
      "label": "positive"
    }
  ],
  "start_date": "2024-11-01",
  "end_date": "2024-11-30",
  "count": 30
}
```

### Response Schema

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| ticker | string | Yes | Normalized ticker symbol (uppercase) |
| source | enum | Yes | Requested sentiment source |
| history | array[SentimentPoint] | Yes | Array of sentiment points, sorted by date ascending |
| start_date | date | Yes | Date of first point |
| end_date | date | Yes | Date of last point |
| count | integer | Yes | Number of points in array |

### SentimentPoint Schema

| Field | Type | Required | Constraints | Description |
|-------|------|----------|-------------|-------------|
| date | date | Yes | YYYY-MM-DD | Calendar date |
| score | float | Yes | [-1.0, 1.0] | Sentiment score |
| source | enum | Yes | tiingo, finnhub, our_model, aggregated | Source of this score |
| confidence | float | No | [0.0, 1.0] | Confidence in score |
| label | enum | Yes | positive, neutral, negative | Sentiment label |

### Label Determination

| Score Range | Label |
|-------------|-------|
| score >= 0.33 | positive |
| score <= -0.33 | negative |
| -0.33 < score < 0.33 | neutral |

**Note**: Boundary values (exactly 0.33 and -0.33) are considered positive/negative respectively.

### Error Responses

#### 400 Bad Request

```json
{
  "detail": "Invalid ticker symbol: ABC123. Must be 1-5 letters."
}
```

Returned when:
- Ticker contains non-letter characters
- Ticker is empty or > 5 characters
- start_date is after end_date

#### 401 Unauthorized

```json
{
  "detail": "Missing user identification"
}
```

Returned when:
- X-User-ID header is missing or empty

#### 404 Not Found

```json
{
  "detail": "No sentiment data available for ZZZZ"
}
```

Returned when:
- No sentiment data available for ticker

## Business Rules

### Ticker Validation
- Ticker must be 1-5 uppercase letters (A-Z)
- Lowercase input is normalized to uppercase
- Leading/trailing whitespace is trimmed
- No digits, symbols, or special characters allowed

### Date Range Calculation
- If `start_date` and `end_date` provided: use custom range
- If only `range` provided: calculate from today
- Time range mappings:
  - 1W = 7 days (8 points including weekends)
  - 1M = 30 days (31 points including weekends)
  - 3M = 90 days
  - 6M = 180 days
  - 1Y = 365 days

### Weekend Handling
- Unlike OHLC data, sentiment is available for ALL calendar days
- Weekends and holidays are included in the response
- This is because news sentiment continues during non-trading days

### Source Filtering
- `source=aggregated` returns blended sentiment from all sources
- `source=tiingo` returns only Tiingo-derived sentiment
- `source=finnhub` returns only Finnhub-derived sentiment
- `source=our_model` returns only model-calculated sentiment

### Point Ordering
- History points sorted by date ascending (oldest first)

### Deterministic Generation
- Currently uses synthetic data based on ticker hash
- Same ticker always returns same sequence of scores
- Production will query DynamoDB for historical sentiment records

## Test Scenarios

### Happy Path
- Valid ticker with default parameters
- Valid ticker with each source filter
- Valid ticker with each TimeRange value
- Valid ticker with custom date range
- Lowercase ticker normalization

### Source Filtering
- source=tiingo returns only tiingo points
- source=finnhub returns only finnhub points
- source=our_model returns only our_model points
- source=aggregated returns aggregated points

### Error Cases
- Missing X-User-ID header
- Empty X-User-ID header
- Invalid ticker (digits, symbols, too long)
- start_date after end_date

### Edge Cases
- Single day range (start == end)
- Weekend-only range
- Score at exact threshold (0.33, -0.33)
- Score just below/above thresholds

### Label Boundary Tests
- score = 0.33 → label = "positive"
- score = 0.329999 → label = "neutral"
- score = -0.33 → label = "negative"
- score = -0.329999 → label = "neutral"
