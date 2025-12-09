# Research: Market Data Ingestion

**Branch**: `072-market-data-ingestion` | **Date**: 2025-12-09 | **Phase**: 0

## 1. Existing Adapter Implementation Analysis

### BaseAdapter Pattern (`src/lambdas/shared/adapters/base.py`)

The codebase has a well-established adapter pattern for external APIs:

```python
class BaseAdapter(ABC):
    """Base class for financial API adapters."""

    @property
    @abstractmethod
    def source_name(self) -> Literal["tiingo", "finnhub"]: ...

    @abstractmethod
    def get_news(...) -> list[NewsArticle]: ...

    @abstractmethod
    def get_sentiment(ticker: str) -> SentimentData | None: ...

    @abstractmethod
    def get_ohlc(...) -> list[OHLCCandle]: ...
```

**Existing Models**:
- `NewsArticle`: Normalized news with `article_id`, `source`, `title`, `description`, `url`, `published_at`, `tickers`, `tags`, `sentiment_score`, `sentiment_label`
- `SentimentData`: Normalized sentiment with `ticker`, `source`, `fetched_at`, `sentiment_score`, `bullish_percent`, `bearish_percent`, `articles_count`, `buzz_score`
- `OHLCCandle`: Price data with `date`, `open`, `high`, `low`, `close`, `volume`

**Key Finding**: The `NewsArticle` model already exists but lacks a deduplication-friendly composite key. We need `headline + source + publication_date` per spec.

### TiingoAdapter (`src/lambdas/shared/adapters/tiingo.py`)

- **Status**: Fully implemented
- **Authentication**: Token-based (`Authorization: Token {api_key}`)
- **Rate Limits**: 500 symbol lookups/month (free tier)
- **Caching**: In-memory cache with configurable TTL (30 min news, 1 hour OHLC)
- **News Endpoint**: `/tiingo/news` with tickers param (comma-separated, max 10)
- **OHLC Endpoint**: `/tiingo/daily/{ticker}/prices`
- **Sentiment**: Returns `None` (Tiingo has no sentiment endpoint)
- **Error Handling**: 429 (rate limit), 401 (auth), 404 (not found)

### FinnhubAdapter (`src/lambdas/shared/adapters/finnhub.py`)

- **Status**: Fully implemented
- **Authentication**: Query param (`token={api_key}`)
- **Rate Limits**: 60 calls/minute (free tier)
- **Caching**: In-memory cache with configurable TTL (30 min news/sentiment, 1 hour OHLC)
- **News Endpoint**: `/company-news` (one ticker per call)
- **OHLC Endpoint**: `/stock/candle` with Unix timestamps
- **Sentiment**: `/news-sentiment` returns `bullishPercent`, `bearishPercent`, `buzz`
- **Error Handling**: 429, 401, 403

**Key Finding**: Both adapters already implement DFA-004 caching optimization. The failover logic exists in `ohlc.py` dashboard endpoint but not extracted as reusable pattern.

### Existing Failover Pattern (`src/lambdas/dashboard/ohlc.py:119-144`)

```python
# Try Tiingo first (primary source per FR-014)
source = "tiingo"
candles = []
try:
    ohlc_candles = tiingo.get_ohlc(ticker, start_date, end_date)
    ...
except Exception as e:
    logger.warning("Tiingo OHLC fetch failed, trying Finnhub", ...)

# Fallback to Finnhub if Tiingo failed or returned no data
if not candles:
    source = "finnhub"
    try:
        ohlc_candles = finnhub.get_ohlc(ticker, start_date, end_date)
```

**Key Finding**: Manual failover exists but lacks timeout control (spec requires 10-second failover). Need to extract reusable pattern with configurable timeout.

---

## 2. Tiingo API Research

**Documentation**: https://www.tiingo.com/documentation/news

### News Endpoint
- **URL**: `GET /tiingo/news`
- **Params**: `tickers` (comma-separated), `startDate`, `endDate`, `limit`, `offset`
- **Response Fields**: `id`, `title`, `url`, `description`, `publishedDate`, `tickers[]`, `tags[]`, `source`
- **Rate Limit**: 500 requests/month (free tier)

### Response Format
```json
[{
  "id": 12345,
  "title": "Apple Announces...",
  "url": "https://...",
  "description": "Full article text...",
  "publishedDate": "2025-12-09T14:30:00Z",
  "tickers": ["AAPL"],
  "tags": ["technology", "earnings"],
  "source": "bloomberg"
}]
```

### Key Observations
- No built-in sentiment score (must calculate our own)
- `id` field is unique per article
- `publishedDate` is ISO8601 format
- 10 tickers max per request

---

## 3. Finnhub API Research

**Documentation**: https://finnhub.io/docs/api/company-news

### News Endpoint
- **URL**: `GET /company-news`
- **Params**: `symbol`, `from`, `to` (YYYY-MM-DD format)
- **Response Fields**: `id`, `headline`, `summary`, `url`, `datetime` (Unix), `source`, `category`
- **Rate Limit**: 60 calls/minute

### Sentiment Endpoint
- **URL**: `GET /news-sentiment`
- **Params**: `symbol`
- **Response Fields**: `sentiment.bullishPercent`, `sentiment.bearishPercent`, `buzz.articlesInLastWeek`, `buzz.buzz`, `sectorAverageNewsScore`

### Response Format (News)
```json
[{
  "id": 67890,
  "headline": "Tesla Earnings Beat...",
  "summary": "Tesla reported...",
  "url": "https://...",
  "datetime": 1733753400,
  "source": "reuters",
  "category": "company"
}]
```

### Key Observations
- Built-in sentiment endpoint (unlike Tiingo)
- One ticker per call (unlike Tiingo's batch)
- Unix timestamps (need conversion)
- `headline` not `title` (different field name)

---

## 4. DynamoDB Deduplication Patterns

### Existing Pattern (`src/lambdas/shared/dynamodb.py`)

```python
def put_item_if_not_exists(table, item) -> bool:
    """Put an item only if it doesn't already exist."""
    try:
        table.put_item(
            Item=item,
            ConditionExpression="attribute_not_exists(source_id)",
        )
        return True
    except ConditionalCheckFailedException:
        return False  # Already exists
```

**Current Key Schema**: `PK=source_id, SK=timestamp`

### Recommended Deduplication Key

Per spec clarification, composite key is: `headline + source + publication_date`

**Implementation Options**:

1. **Hash-based composite key** (Recommended)
   ```python
   import hashlib
   composite = f"{headline}|{source}|{pub_date}"
   dedup_key = hashlib.sha256(composite.encode()).hexdigest()[:32]
   ```
   - Pros: Fixed length, URL-safe, collision-resistant
   - Cons: Not human-readable

2. **String concatenation**
   ```python
   dedup_key = f"{source}#{pub_date}#{headline[:50]}"
   ```
   - Pros: Human-readable in DynamoDB console
   - Cons: Headline truncation could cause collisions

**Decision**: Use Option 1 (hash-based) for robustness.

---

## 5. Failover Pattern Analysis

### Current State: Manual Try/Except

The existing `ohlc.py` uses simple try/except without:
- Timeout control (spec: 10 seconds)
- Circuit breaker integration
- Consecutive failure tracking (spec: alert after 3 failures in 15 min)

### Existing Circuit Breaker (`src/lambdas/shared/circuit_breaker.py`)

```python
class CircuitBreakerState:
    """Per-API circuit breaker state."""
    service: Literal["tiingo", "finnhub", "sendgrid"]
    state: Literal["closed", "open", "half_open"]
    failure_threshold: int = 5
    failure_window_seconds: int = 300
    recovery_timeout_seconds: int = 60
```

**Key Finding**: Circuit breaker exists but:
- Threshold is 5 failures (spec requires alert at 3)
- Window is 5 minutes (spec requires 15 minutes)
- No SNS/SQS integration for alerting

### Recommended Failover Pattern

```python
class SourceFailover:
    """Manages failover between primary/secondary sources."""

    def __init__(self, primary: BaseAdapter, secondary: BaseAdapter,
                 timeout: float = 10.0):
        self.primary = primary
        self.secondary = secondary
        self.timeout = timeout
        self._consecutive_failures = 0
        self._failure_timestamps: list[datetime] = []

    def fetch_with_failover(self, method: str, *args, **kwargs):
        try:
            # Primary with timeout
            result = asyncio.wait_for(
                getattr(self.primary, method)(*args, **kwargs),
                timeout=self.timeout
            )
            self._consecutive_failures = 0
            return result
        except (asyncio.TimeoutError, AdapterError):
            self._record_failure()
            # Fallback to secondary
            return getattr(self.secondary, method)(*args, **kwargs)
```

---

## 6. Unknowns Resolution

| Unknown | Resolution |
|---------|------------|
| Current adapter implementation status | Both adapters fully implemented with caching |
| Existing DynamoDB table schema | PK=source_id, SK=timestamp; need new table or GSI for news items |
| Current alerting mechanism | No existing alerting for ingestion; need SNS topic + CloudWatch alarm |
| EventBridge scheduler configuration | No existing scheduler; need to create for 5-min market hours collection |

---

## 7. Gap Analysis

### What Exists
- TiingoAdapter and FinnhubAdapter with caching
- DynamoDB helpers with conditional writes
- Circuit breaker pattern
- NewsArticle model for normalized articles

### What Needs Building

1. **Deduplication Key Generation**
   - Hash-based composite key (headline + source + pub_date)
   - New field in NewsArticle or separate storage model

2. **Failover Orchestrator**
   - Extract and enhance existing try/except pattern
   - Add timeout control (10 seconds)
   - Integrate circuit breaker

3. **Consecutive Failure Tracker**
   - Track failures per 15-minute window
   - Alert after 3 consecutive failures
   - SNS integration for operations alerts

4. **EventBridge Scheduler**
   - 5-minute cron during market hours
   - Schedule: `cron(*/5 9-16 ? * MON-FRI *)` (approximation for 9:30-4:00 ET)

5. **Collection Event Logging**
   - DynamoDB table for collection audit trail
   - Track: timestamp, source, success/failure, item_count, error_message

6. **Downstream Notification**
   - SNS topic for "new data available"
   - Message within 30 seconds of storage

---

## 8. Reuse Assessment

| Component | Reuse | Modification Needed |
|-----------|-------|---------------------|
| TiingoAdapter | Direct | None |
| FinnhubAdapter | Direct | None |
| NewsArticle model | Direct | Add dedup_key field |
| put_item_if_not_exists | Direct | Use for deduplication |
| CircuitBreakerManager | Partial | Configure for 3-failure threshold |
| Secrets helper | Direct | None |

**Estimated New Code**: ~300-400 lines
- Failover orchestrator: ~80 lines
- Ingestion handler: ~120 lines
- Collection event model: ~40 lines
- Alerting integration: ~60 lines
- Tests: ~200+ lines

---

## 9. API Budget Analysis

Per spec: $50/month budget for data sources.

| Source | Free Tier | Paid Tier | Estimate |
|--------|-----------|-----------|----------|
| Tiingo | 500 req/month | $10/mo starter | Use free tier |
| Finnhub | 60 req/min | $50/mo | Use free tier |

**Collection Frequency**: Every 5 minutes during market hours = 78 calls/day × 22 trading days = 1,716 calls/month

**Recommendation**: Free tiers sufficient with caching (30-min TTL reduces actual API calls by ~80%).

---

## 10. Next Steps (Phase 1)

1. Define `CollectionEvent` DynamoDB model
2. Define deduplication key generation utility
3. Create failover orchestrator class
4. Design SNS message schema for downstream notification
5. Write quickstart.md for local development
