# Feature Specification: Fix Sentiment Overview & History Endpoints

**Feature Branch**: `1229-fix-sentiment-overview`
**Created**: 2026-03-21
**Status**: Draft
**Input**: User description: "Fix sentiment overview and history endpoints to read real pipeline data from DynamoDB instead of returning empty/stub results"

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Sentiment Overview Shows Real Data (Priority: P1)

A user opens their dashboard and views the sentiment overview for their configured tickers. The system displays real sentiment scores and labels derived from actual news articles processed by the ingestion pipeline, not empty placeholder data.

**Why this priority**: This is the primary user-facing bug. Every user sees empty sentiment data on their dashboard because the overview endpoint returns `sentiment:{}` for all tickers. This completely breaks the core value proposition of the product.

**Independent Test**: Can be fully tested by creating a configuration with tickers that have ingested sentiment data, calling the overview endpoint, and verifying non-empty sentiment scores are returned. Delivers the core sentiment visibility that users expect.

**Acceptance Scenarios**:

1. **Given** a configuration with tickers ["AAPL", "GOOGL"] and analyzed sentiment items exist for both tickers in the pipeline, **When** the user requests the sentiment overview, **Then** the response contains sentiment data for each ticker including score, label, and confidence values.
2. **Given** a configuration with tickers ["AAPL", "TSLA"] where "TSLA" has no ingested sentiment data, **When** the user requests the sentiment overview, **Then** "AAPL" shows real sentiment data and "TSLA" shows an empty sentiment map (graceful degradation, not an error).
3. **Given** a configuration with tickers, **When** the user requests the sentiment overview, **Then** the response includes an aggregated score across recent articles (not just the latest single article) for each ticker.

---

### User Story 2 - Ticker Sentiment History Shows Real Time Series (Priority: P1)

A user drills into a specific ticker to view its sentiment history over time. The system returns actual time-series data from the pipeline showing how sentiment has changed day over day, enabling trend analysis.

**Why this priority**: Equal priority to US1 because the history endpoint is the drill-down companion. Without real history data, users cannot perform trend analysis — the second core capability of the sentiment feature.

**Independent Test**: Can be fully tested by calling the ticker history endpoint for a ticker with multiple days of ingested data and verifying the response contains real time-series entries with varying scores.

**Acceptance Scenarios**:

1. **Given** a ticker "AAPL" with analyzed sentiment items spanning 7 days, **When** the user requests 7-day history, **Then** the response contains daily aggregated sentiment entries with real scores, not synthetic/hardcoded values.
2. **Given** a ticker "AAPL" with sentiment data from both tiingo and finnhub sources, **When** the user filters history by `source=tiingo`, **Then** only tiingo-sourced sentiment entries are included in the response.
3. **Given** a ticker "AAPL" with only 3 days of data, **When** the user requests 7-day history, **Then** only the 3 available days are returned (no padding with synthetic data).

---

### User Story 3 - Sentiment Cache Serves Fresh Data Efficiently (Priority: P2)

After the first user request populates the cache, subsequent requests for the same configuration's sentiment data are served from cache within the 5-minute TTL window, reducing redundant database queries.

**Why this priority**: Performance optimization. The existing cache mechanism should continue working but now caches real data instead of empty results. Lower priority because correctness (US1, US2) must come first.

**Independent Test**: Can be tested by making two consecutive overview requests within the cache TTL and verifying the second returns a cache hit with `cache_status: "fresh"`.

**Acceptance Scenarios**:

1. **Given** an uncached sentiment request for a configuration, **When** the request completes, **Then** the result is stored in cache and subsequent requests within the TTL return the cached response.
2. **Given** a cached sentiment response older than the cache TTL, **When** a new request arrives, **Then** the system fetches fresh data from the database and updates the cache.

---

### Edge Cases

- What happens when a ticker has no timeseries data (zero buckets, pipeline hasn't analyzed articles, or no articles exist)? The overview returns an empty sentiment map for that ticker (not an error), and the history returns an empty time series.
- What happens when the timeseries table is unreachable? The system returns error code `DB_ERROR` with message "Database error", not an empty success response that masks the failure. This matches the existing error pattern in `get_ticker_sentiment_history`.
- What happens when a ticker has thousands of sentiment items? The query is bounded by `DEFAULT_LIMITS` per resolution (e.g., 7 buckets at 24h, 60 at 1m) and by the time window parameter to prevent unbounded reads.
- How does the system handle tickers that appear in `matched_tickers` vs `matched_tags`? The query uses the `sentiment-timeseries` table where ticker is part of the PK (`{ticker}#{resolution}`), not the `sentiment-items` table.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The overview endpoint MUST return real sentiment data by querying the `sentiment-timeseries` table (via `TimeseriesQueryService`) for each ticker in the configuration.
- **FR-002**: The overview endpoint MUST accept an optional `resolution` query parameter (default `24h`) and aggregate sentiment scores from the corresponding timeseries bucket to produce a per-ticker summary (score, label, confidence).
- **FR-003**: The history endpoint MUST return real time-series sentiment data from the `sentiment-timeseries` table, at the requested resolution, for the requested ticker and time window.
- **FR-004**: The history endpoint MUST support filtering by source (tiingo, finnhub) when the source parameter is provided.
- **FR-005**: Both endpoints MUST gracefully handle tickers with no sentiment data by returning empty results rather than errors.
- **FR-006**: The `sentiment-timeseries` table MUST use 6 resolutions aligned 1:1 with OHLC: 1m, 5m, 15m, 30m, 1h, 24h (replacing the current 8: 1m, 5m, 10m, 1h, 3h, 6h, 12h, 24h).
- **FR-007**: The overview endpoint MUST remove the dead external adapter parameters (tiingo_adapter, finnhub_adapter) that are never injected.
- **FR-008**: The API response structure (SentimentResponse model) MUST be preserved. The sentiment dict key changes from dead source names ("tiingo"/"finnhub") to "aggregated". Frontend types and components MUST be updated to match (the existing per-source heatmap access was always dead code returning empty data).
- **FR-009**: The frontend resolution selector and UNIFIED_RESOLUTIONS config MUST be updated to reflect the new 6-resolution set, removing options for 10m, 3h, 6h, 12h.
- **FR-010**: The existing cache mechanism MUST continue to function, now caching real data instead of empty results. Cache key MUST include resolution to prevent cross-resolution cache collisions.
- **FR-011**: Database queries MUST be bounded by time window to prevent unbounded reads. Overview queries the latest bucket at the requested resolution. History uses the user-specified days parameter (max 30).

### Key Entities

- **Sentiment Timeseries Bucket**: A pre-aggregated OHLC sentiment bucket for a specific ticker at a specific resolution. Contains open/high/low/close scores, article count, average score, label distribution, and source attribution. PK: `{ticker}#{resolution}`, SK: bucket timestamp.
- **Ticker Sentiment Summary**: An aggregated view of sentiment for a single ticker, derived from the latest timeseries bucket(s). Includes average score, overall label, and article count.
- **Configuration**: A user's saved watchlist containing a list of ticker symbols. Used to determine which tickers to query sentiment for.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: The sentiment overview endpoint returns non-empty sentiment data for tickers that have analyzed pipeline data, with a success rate of 100% (zero false empties).
- **SC-002**: The sentiment history endpoint returns real time-series data points matching the actual ingested data count for the requested time window.
- **SC-003**: The frontend dashboard displays real sentiment scores and labels. Frontend types and heatmap component updated to use aggregated data (the existing per-source access was dead code that always rendered empty).
- **SC-004**: Overview endpoint response time remains under 2 seconds for configurations with up to 20 tickers.
- **SC-005**: Existing unit and integration tests continue to pass after the change, with new tests covering the database query paths.

## Clarifications

### Session 2026-03-21

- Q: Which data source should the sentiment endpoints query — `sentiment-items` (raw articles, broken GSI) or `sentiment-timeseries` (pre-aggregated per-ticker buckets)? → A: Use `sentiment-timeseries` table via existing `TimeseriesQueryService`. The `by_tag` GSI on sentiment-items was never populated (fan-out not implemented). The timeseries table already has per-ticker data as its PK pattern.
- Q: Should sentiment resolutions align 1:1 with OHLC for dashboard overlay? → A: Yes. Replace the current 8 resolutions (1m, 5m, 10m, 1h, 3h, 6h, 12h, 24h) with 6 aligned resolutions (1m, 5m, 15m, 30m, 1h, 24h) matching OHLC exactly. Remove 10m, 3h, 6h, 12h.
- Q: What resolution should the overview endpoint use by default? → A: Accept `resolution` as an optional query parameter (default `24h`), letting the frontend choose the resolution.

## Assumptions

- The analysis pipeline fan-out writes to `sentiment-timeseries` are actively populating data for tickers in user configurations.
- The `TimeseriesQueryService` in `dashboard/timeseries.py` can be reused by the overview and history endpoints without modification.
- The `SentimentResponse`, `TickerSentimentData`, and `SourceSentiment` pydantic models can carry timeseries bucket data — only the data population logic needs to change.
- The `sentiment-timeseries` table name is resolved via the `TIMESERIES_TABLE` environment variable, already wired in Terraform.
- Existing 10m, 3h, 6h, 12h data in the timeseries table will expire naturally via TTL (no manual cleanup required).
