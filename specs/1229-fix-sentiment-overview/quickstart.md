# Quickstart: Fix Sentiment Overview & History Endpoints

**Branch**: `1229-fix-sentiment-overview`

## What This Feature Does

Rewires two broken sentiment endpoints to read real data from the `sentiment-timeseries` DynamoDB table instead of returning empty/stub results. Also aligns sentiment resolutions with OHLC for dashboard overlay, and updates frontend to render aggregated sentiment data.

## Implementation Order

### Step 1: Modify Resolution Enum (foundation change)

**File**: `src/lib/timeseries/models.py`

Change `Resolution` enum from 8 values to 6:
- Remove: `TEN_MINUTES`, `THREE_HOURS`, `SIX_HOURS`, `TWELVE_HOURS`
- Add: `FIFTEEN_MINUTES = "15m"`, `THIRTY_MINUTES = "30m"`
- Update `duration_seconds` and `ttl_seconds` property mappings
- New TTLs: 15m→24h, 30m→3 days

**Impact**: `write_fanout()` iterates `Resolution` enum — this automatically changes fan-out from 8→6 items per score.

### Step 2: Update ALL Hardcoded Resolution References (blast radius)

**Files that must be updated when changing the enum** (found by adversarial review):

| File | What to change |
|------|---------------|
| `src/lambdas/sse_streaming/handler.py:215` | `valid_resolutions` set → use `{r.value for r in Resolution}` instead of hardcoded set |
| `src/lambdas/dashboard/router_v2.py:1551,1621` | Error messages listing valid resolutions → derive from enum |
| `src/lambdas/dashboard/timeseries.py:227-236` | `DEFAULT_LIMITS` dict → remove 10m/3h/6h/12h entries, add 15m/30m |
| `src/lib/timeseries/preload.py:24-33` | `RESOLUTION_ORDER` → rebuild from new enum values |
| `src/lib/timeseries/fanout.py:10` | Docstring: "8 resolution buckets" → "6 resolution buckets" |
| `src/dashboard/config.js:68-117` | `RESOLUTIONS` → remove 10m/3h/6h/12h, add 15m/30m |
| `src/dashboard/config.js:120` | `RESOLUTION_ORDER` → update to 6 values |
| `src/dashboard/config.js:194-205` | `UNIFIED_RESOLUTIONS` → update mappings for 1:1 OHLC alignment |
| `README.md:416` | Documentation reference to resolution list |

**Best practice**: Where possible, derive from the `Resolution` enum instead of hardcoding strings. This prevents future blast radius issues.

### Step 3: Rewrite Overview Function

**File**: `src/lambdas/dashboard/sentiment.py`

Replace `get_sentiment_by_configuration()` (lines 249-371):
- Remove `tiingo_adapter` and `finnhub_adapter` parameters
- Import and call `query_timeseries(ticker, resolution, start, end)` for each ticker
- Transform `SentimentBucketResponse` → `SourceSentiment` using:
  - `bucket.avg` → `score`
  - Score threshold (±0.33) → `label`
  - Hardcode `confidence=0.8` (matching existing pattern in ohlc.py)
  - `bucket.timestamp` → `updated_at`
- Sentiment dict key: `"aggregated"` (not per-source)
- Keep existing cache mechanism (cache real data instead of empty data)

**Reference**: `ohlc.py:1054-1104` for the exact transformation pattern.

### Step 4: Rewrite History Function

**File**: `src/lambdas/dashboard/sentiment.py`

Replace `get_ticker_sentiment_history()` (lines 608-691):
- Remove hardcoded stub data generation
- Call `query_timeseries(ticker, resolution, start_dt, end_dt)`
- Apply source filtering on `bucket.sources` if source param provided
- Transform buckets to `TickerSentimentData` time series

### Step 5: Update Router

**File**: `src/lambdas/dashboard/router_v2.py`

- Overview route (line 1159): Add `resolution` query param extraction, validate against Resolution enum, pass to rewritten function
- History route (line 1301): Add `resolution` query param, pass to rewritten function
- Fix error messages at lines 1551, 1621 to derive valid resolutions from enum

### Step 6: Clean Up Dead Code

**File**: `src/lambdas/dashboard/sentiment.py`

Remove:
- `_get_tiingo_sentiment()` helper
- `_get_finnhub_sentiment()` helper
- `_compute_our_model_sentiment()` helper

### Step 7: Update Frontend Types and Components

**Files**:
- `frontend/src/types/sentiment.ts` — Change `TickerSentiment.sentiment` from per-source (`tiingo`, `finnhub`, `ourModel`) to use `"aggregated"` key
- `frontend/src/components/heatmap/heat-map-view.tsx` — Remove hardcoded `ticker.sentiment.tiingo`, `ticker.sentiment.finnhub`, `ticker.sentiment.ourModel` access. Render from `ticker.sentiment.aggregated` instead. Note: the per-source view was always empty (dead code), so this fix makes the heatmap functional for the first time.

### Step 8: Update Tests

**Files to modify** (adversarial review found these will break):

| Test File | Change |
|-----------|--------|
| `tests/unit/dashboard/test_sentiment.py:81,98,116,130` | Remove/rewrite adapter parameter tests |
| `tests/unit/test_preload_strategy.py` | Update 11+ assertions for 6 resolutions |
| `tests/unit/test_sse_resolution_filter.py:181-184` | Remove references to removed enum values |
| `tests/unit/test_resolution_cache.py:149-153` | Update expected TTL dict |
| `tests/unit/test_timeseries_key_design.py:76` | Update hardcoded resolution list |
| `tests/unit/test_timeseries_bucket.py:39-52` | Remove alignment tests for removed resolutions |
| `tests/unit/dashboard/test_config_resolution.py:52,85,102-106` | Update expected resolution set and names |

**New tests to create**:
- `tests/unit/test_sentiment_overview.py` — Overview with real timeseries data, empty tickers, cache behavior
- `tests/unit/test_sentiment_history.py` — History with time range, source filtering, resolution param
- `tests/integration/test_sentiment_endpoints.py` — End-to-end against LocalStack

## Key Patterns to Follow

### Querying Timeseries (from ohlc.py reference)

```python
from src.lambdas.dashboard.timeseries import query_timeseries
from src.lib.timeseries.models import Resolution

ts_response = query_timeseries(
    ticker="AAPL",
    resolution=Resolution.TWENTY_FOUR_HOURS,
    start=start_dt,
    end=end_dt,
)

for bucket in ts_response.buckets:
    score = round(bucket.avg, 4)
    label = "positive" if score >= 0.33 else ("negative" if score <= -0.33 else "neutral")
```

### Score-to-Label Threshold

Existing pattern in `ohlc.py`:
- score >= 0.33 → "positive"
- score <= -0.33 → "negative"
- else → "neutral"

### Source Filtering

```python
if source_filter:
    buckets = [b for b in buckets if any(s.startswith(source_filter) for s in b.sources)]
```

### Derive Validations From Enum (prevent future blast radius)

```python
# GOOD: Derive from enum
valid_resolutions = {r.value for r in Resolution}

# BAD: Hardcoded set
valid_resolutions = {"1m", "5m", "10m", "1h", "3h", "6h", "12h", "24h"}
```

## Testing Strategy

- **Unit tests**: Mock `query_timeseries()` return value, verify transformation logic
- **Integration tests**: LocalStack DynamoDB with pre-populated timeseries buckets
- **Deterministic dates**: Use `date(2024, 1, 2)` (known Tuesday) per constitution
- **Freeze time**: Use `freezegun` for cache TTL tests
- **Resolution tests**: Verify all validation sets/error messages derive from enum
