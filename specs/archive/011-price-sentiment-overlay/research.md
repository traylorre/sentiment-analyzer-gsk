# Research: Price-Sentiment Overlay Chart

**Feature**: 011-price-sentiment-overlay
**Date**: 2025-12-01
**Status**: Complete

## Research Questions

### 1. TradingView Lightweight Charts Dual-Axis Support

**Question**: Can TradingView Lightweight Charts render candlesticks and a line overlay on separate Y-axes?

**Decision**: YES - Use `createPriceScale` with separate `priceScaleId` for sentiment line

**Rationale**:
- Lightweight Charts v5.x supports multiple price scales via `priceScaleId` option
- Candlestick series uses default left price scale (`'left'`)
- Line series can use custom price scale (`'sentiment'`) positioned on right
- Both series share the same time axis, enabling crosshair synchronization

**Implementation Pattern**:
```typescript
// Create chart with two price scales
const chart = createChart(container, {
  rightPriceScale: {
    scaleMargins: { top: 0.1, bottom: 0.1 },
  },
});

// Candlestick series on left axis (default)
const candleSeries = chart.addCandlestickSeries({
  priceScaleId: 'left',
});

// Sentiment line on right axis
const sentimentSeries = chart.addLineSeries({
  priceScaleId: 'right',
  color: '#00FFFF',
  lineWidth: 2,
});

// Configure right scale for sentiment range
chart.priceScale('right').applyOptions({
  autoScale: false,
  scaleMargins: { top: 0.1, bottom: 0.1 },
});
```

**Alternatives Considered**:
- Custom overlay rendering: Rejected - requires manual coordinate calculation
- Separate synchronized charts: Rejected - worse UX, harder to maintain crosshair sync

---

### 2. Existing Adapter OHLC Implementation

**Question**: How do Tiingo/Finnhub adapters fetch OHLC data? What patterns should be followed?

**Decision**: Reuse existing `get_ohlc()` methods with extended date range support

**Rationale**:
From `src/lambdas/shared/adapters/tiingo.py` (lines 245-318):
- Method signature: `get_ohlc(ticker, start_date=None, end_date=None) -> list[OHLCCandle]`
- Default range: 30 days (can extend to 1 year)
- Built-in caching: 1-hour TTL with LRU eviction (100 entries max)
- Rate limiting: Handled via backoff/retry

**Existing OHLCCandle Model** (`src/lambdas/shared/adapters/base.py`):
```python
class OHLCCandle(BaseModel):
    date: datetime
    open: float
    high: float
    low: float
    close: float
    volume: int | None = None
```

**Pattern to Follow** (from `volatility.py`):
```python
# Primary source with fallback
candles = tiingo_adapter.get_ohlc(ticker, start_date, end_date)
if not candles:
    logger.warning("Tiingo OHLC unavailable, falling back to Finnhub")
    candles = finnhub_adapter.get_ohlc(ticker, start_date, end_date)
```

**Alternatives Considered**:
- New adapter methods: Rejected - existing methods already provide full OHLC data
- Direct API calls: Rejected - loses caching and error handling benefits

---

### 3. Market Hours Detection for Cache Expiration

**Question**: How to determine cache TTL based on market hours?

**Decision**: Use NYSE trading calendar with market close detection

**Rationale**:
- NYSE hours: 9:30 AM - 4:00 PM ET, Monday-Friday
- Cache should expire at next market open (not fixed 24h)
- Existing `market.py` has market status detection

**Implementation Pattern**:
```python
from datetime import datetime, time
from zoneinfo import ZoneInfo

ET = ZoneInfo("America/New_York")
MARKET_OPEN = time(9, 30)
MARKET_CLOSE = time(16, 0)

def get_cache_expiration() -> datetime:
    """Calculate when OHLC cache should expire (next market open)."""
    now = datetime.now(ET)

    # If before market close today, expire at close
    if now.time() < MARKET_CLOSE and now.weekday() < 5:
        return now.replace(hour=16, minute=0, second=0, microsecond=0)

    # Otherwise, expire at next market open
    next_open = now.replace(hour=9, minute=30, second=0, microsecond=0)
    if now.weekday() == 4 and now.time() >= MARKET_CLOSE:
        # Friday after close -> Monday
        next_open += timedelta(days=3)
    elif now.weekday() >= 5:
        # Weekend -> Monday
        days_until_monday = 7 - now.weekday()
        next_open += timedelta(days=days_until_monday)
    else:
        # Regular weekday after close -> next day
        next_open += timedelta(days=1)

    return next_open
```

**Alternatives Considered**:
- Fixed 24h TTL: Rejected - wastes API calls on weekends
- Real-time market status API: Rejected - unnecessary complexity for caching

---

### 4. Sentiment History by Date Range

**Question**: How to retrieve historical sentiment aligned with price data?

**Decision**: Extend sentiment endpoint with `start_date` and `end_date` params

**Rationale**:
- Current sentiment endpoint returns current/recent data only
- Need historical sentiment matching OHLC date range
- Sentiment stored in DynamoDB with timestamp, can query by date

**Current Sentiment Response** (from `sentiment.py`):
```python
class TickerSentimentData(BaseModel):
    symbol: str
    sentiment: dict[str, SourceSentiment]  # keyed by source name

class SourceSentiment(BaseModel):
    score: float  # -1.0 to 1.0
    label: str
    confidence: float | None
    updated_at: str
```

**Extended Model for History**:
```python
class SentimentHistoryPoint(BaseModel):
    date: date
    score: float
    source: str
    confidence: float | None

class SentimentHistoryResponse(BaseModel):
    ticker: str
    history: list[SentimentHistoryPoint]
    source: str  # Selected source
```

**Alignment Strategy**:
- Price data: Only trading days (Mon-Fri excluding holidays)
- Sentiment data: All days (news can happen anytime)
- Chart alignment: Match by date, show sentiment for non-trading days without candles

**Alternatives Considered**:
- Aggregate sentiment to trading days only: Rejected - loses weekend sentiment data
- Separate API calls for each day: Rejected - poor performance

---

## Summary of Key Decisions

| # | Decision | Choice | Impact |
|---|----------|--------|--------|
| 1 | Chart library | TradingView Lightweight Charts dual-axis | No new dependencies |
| 2 | OHLC data source | Existing adapters (Tiingo primary) | Minimal backend changes |
| 3 | Cache TTL | Market-hours aware (~24h max) | Efficient API usage |
| 4 | Sentiment history | Extend existing endpoint | Backward compatible |

## Unresolved Items

None - all research questions answered.

## Next Steps

1. Create `data-model.md` with complete entity definitions
2. Generate OpenAPI contract in `contracts/ohlc-api.yaml`
3. Create `quickstart.md` with implementation guide
