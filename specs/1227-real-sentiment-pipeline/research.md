# Research: Real Sentiment Pipeline

## R1: Ingestion Lambda Packaging Fix

**Decision**: Add `aws-lambda-powertools==3.7.0` to the ingestion Lambda pip install in `deploy.yml` line ~145.

**Rationale**: The canary Lambda (line 334) already uses this exact version. The ingestion Lambda imports `Tracer` from powertools in 6 files but the dependency was never added to the ZIP build. The version must match to avoid compatibility issues.

**Alternatives considered**:
- Replace powertools Tracer with raw `aws-xray-sdk` Tracer: Would work but diverges from the pattern used by all other Lambdas (dashboard, SSE, canary all use powertools).
- Remove X-Ray tracing from ingestion: Counterproductive — tracing is needed for observability.

## R2: Timeseries Table Query Pattern

**Decision**: Query the existing `{env}-sentiment-timeseries` table using PK=`{ticker}#24h` and SK range query between start and end dates.

**Rationale**: The table already has the correct schema (confirmed by DynamoDB scan of 678 records):
- PK: `{ticker}#24h` (e.g., `AAPL#24h`)
- SK: ISO timestamp (e.g., `2025-12-20T00:00:00+00:00`)
- Fields: `avg` (score), `count` (articles), `sources` (list), `open`, `close`, `sum`, `ttl`, `is_partial`

The `24h` resolution suffix matches the daily granularity of the history endpoint. Range queries on SK give us date-range filtering for free.

**Alternatives considered**:
- Create a new table with a different schema: Unnecessary — the existing table has exactly the right structure.
- Scan instead of query: Inefficient — query with PK+SK range is the correct DynamoDB access pattern.

## R3: Sentiment Cache Architecture

**Decision**: Follow the OHLC cache pattern: in-memory dict with jittered TTL (5 min ± 10%) → DynamoDB timeseries table (persistent, 90-day TTL). No live API tier — sentiment history reads from the table populated by background ingestion, not from Finnhub on-demand.

**Rationale**: Unlike OHLC (which can fetch live data from Tiingo for uncached tickers), sentiment history is produced by the background ingestion pipeline. There's no on-demand API to call for historical sentiment. The cache is simpler: 2 tiers instead of 3.

**Alternatives considered**:
- 3-tier with live API: Would require on-demand Finnhub calls from the dashboard Lambda, adding latency and rate limit pressure. The background pipeline is the better architecture for historical data.
- No in-memory cache: Would hit DynamoDB on every request. The 5-min TTL in-memory cache reduces read load.

## R4: Synthetic Generator Removal

**Decision**: Delete the synthetic generator code block in `ohlc.py` lines ~1020-1093 and replace with a function that queries the timeseries table. The response format (SentimentHistoryResponse with SentimentPoint entries) stays the same — only the data source changes.

**Rationale**: The response model is already defined and used by the frontend. Changing the data source without changing the response format means no frontend changes are needed.

**Alternatives considered**:
- Keep synthetic as fallback for tickers with no data: Violates FR-005 ("MUST NOT generate synthetic data"). Empty results are better than fake results.
- Move synthetic to a separate "demo mode" flag: Over-engineered for the problem. Remove it cleanly.

## R5: Observability Instrumentation

**Decision**: Add `x-cache-source` header to sentiment history response (matching OHLC pattern). Register a `CacheStats` instance named `sentiment_history` with the global `CacheMetricEmitter`. Add X-Ray subsegment annotations for DynamoDB queries.

**Rationale**: Direct copy of the pattern established in the OHLC cache audit (Feature 1224, PRs #735-#741). Same CacheStats class, same emitter, same header names. Consistency means operators use the same tools and dashboards.

**Alternatives considered**:
- Custom metrics separate from CacheStats: Would fragment observability. The existing CacheStats pattern is proven.
