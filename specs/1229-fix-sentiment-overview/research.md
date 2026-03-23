# Research: Fix Sentiment Overview & History Endpoints

**Date**: 2026-03-21
**Branch**: `1229-fix-sentiment-overview`

## Research Question 1: Data Source for Per-Ticker Sentiment Queries

**Decision**: Use `sentiment-timeseries` table via existing `TimeseriesQueryService`

**Rationale**:
- The `sentiment-items` table has no usable GSI for per-ticker queries. The `by_tag` GSI (PK: `tag`, SK: `timestamp`) is empty because the fan-out writes were never implemented — ingestion stores `tags` as a list attribute, not individual `tag` items.
- The `sentiment-timeseries` table already has per-ticker data as its PK pattern: `{ticker}#{resolution}`. It's populated by the analysis pipeline fan-out.
- An existing `TimeseriesQueryService` in `dashboard/timeseries.py` handles querying with caching, pagination, and partial bucket detection.
- A working reference implementation exists in `ohlc.py:1024-1150` that queries timeseries and transforms to sentiment response models.

**Alternatives considered**:
- Scan `sentiment-items` with FilterExpression on `matched_tickers` — too slow/expensive, violates DynamoDB best practices
- Implement tag fan-out in ingestion to populate `by_tag` GSI — larger scope, separate feature, still indexes by content tags not ticker symbols
- Add new `by_ticker` GSI to `sentiment-items` — requires Terraform change, backfill, and fan-out writes; unnecessary when timeseries already works

## Research Question 2: Resolution Alignment

**Decision**: Replace 8 sentiment resolutions with 6 OHLC-aligned resolutions

**Rationale**:
- Sentiment and OHLC data must overlay on the same dashboard chart at the same bucket size
- Current sentiment resolutions (1m, 5m, 10m, 1h, 3h, 6h, 12h, 24h) misalign with OHLC (1m, 5m, 15m, 30m, 1h, D) at 15m and 30m
- Removing 10m, 3h, 6h, 12h and adding 15m, 30m produces exact 1:1 alignment
- Fan-out writes iterate `Resolution` enum, so changing the enum automatically changes fan-out (no code change in `fanout.py`)
- Existing 10m/3h/6h/12h data expires naturally via TTL (no manual cleanup)

**New resolution set with TTLs**:

| Resolution | Duration (s) | TTL | OHLC Match |
|------------|-------------|-----|------------|
| 1m | 60 | 6 hours | 1 |
| 5m | 300 | 12 hours | 5 |
| 15m | 900 | 24 hours | 15 |
| 30m | 1800 | 3 days | 30 |
| 1h | 3600 | 7 days | 60 |
| 24h | 86400 | 90 days | D |

**TTL rationale**: 15m inherits 10m's 24h TTL (similar granularity). 30m gets 3 days (between 24h and 7d, proportional to resolution). Other TTLs unchanged.

**Alternatives considered**:
- Keep all 8 + add 15m/30m (10 total) — user rejected: unnecessary write amplification for unused resolutions
- Replace 10m with 15m only — doesn't fix 30m misalignment
- Frontend interpolation — introduces approximation artifacts on charts

## Research Question 3: Overview Resolution Strategy

**Decision**: Accept `resolution` as optional query parameter (default `24h`)

**Rationale**:
- Gives frontend control over what resolution the overview displays
- When dashboard is showing 5m OHLC candles, sentiment overview can match at 5m
- Default 24h provides daily summary for users who don't specify
- Same parameter pattern as the history endpoint for consistency

## Research Question 4: Model Compatibility

**Decision**: Existing `SentimentResponse` model can carry timeseries data with minimal mapping

**Mapping from `SentimentBucketResponse` → `SourceSentiment`**:

| SentimentBucketResponse field | Maps to SourceSentiment field |
|-------------------------------|-------------------------------|
| `avg` | `score` |
| label from score threshold (±0.33) | `label` |
| `count` / total count ratio | `confidence` (article density proxy) |
| `timestamp` | `updated_at` |

**Key insight**: `TickerSentimentData.sentiment` is `dict[str, SourceSentiment]`. The existing key convention uses source names ("tiingo", "finnhub", "our_model"). For timeseries data, the key will be "aggregated" (combining all sources in the bucket) or individual source names filtered from `bucket.sources`.

## Research Question 5: Source Filtering on Timeseries

**Decision**: Application-level filtering using `bucket.sources` attribute

**Rationale**:
- Each timeseries bucket stores a `sources` list (e.g., `["tiingo:91120376", "finnhub:xyz"]`) tracking which sources contributed
- The `by_tag` GSI on sentiment-items is broken, so querying raw articles by source isn't viable
- Source prefix matching (`source.startswith("tiingo")`) on bucket data is sufficient
- If a bucket has mixed sources, filtering shows buckets where the requested source contributed — this is acceptable for the history view

## Research Question 6: Existing Code to Reuse vs Rewrite

**Reuse** (no changes needed):
- `TimeseriesQueryService` — query engine with caching, pagination
- `query_timeseries()` convenience function — global singleton pattern
- `floor_to_bucket()` — timestamp alignment
- `ResolutionCache` — per-resolution TTL cache
- `SentimentBucketResponse` / `TimeseriesResponse` — query result models

**Rewrite**:
- `get_sentiment_by_configuration()` in `sentiment.py:249-371` — replace adapter calls with timeseries queries
- `get_ticker_sentiment_history()` in `sentiment.py:608-691` — replace stub data with timeseries queries
- `Resolution` enum in `models.py` — 8 values → 6 values + updated TTL/duration mappings

**Modify**:
- `router_v2.py:1144-1163` — add `resolution` query param to overview route
- `router_v2.py:1278-1311` — add `resolution` query param to history route, pass table reference

**Remove**:
- `tiingo_adapter` and `finnhub_adapter` parameters from `get_sentiment_by_configuration()`
- `_get_tiingo_sentiment()` and `_get_finnhub_sentiment()` helper functions (dead code)
- `_compute_our_model_sentiment()` helper (computed from dead adapter data)
