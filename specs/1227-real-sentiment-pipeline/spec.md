# Feature Specification: Real Sentiment Pipeline

**Feature Branch**: `1227-real-sentiment-pipeline`
**Created**: 2026-03-19
**Status**: Draft
**Input**: User description: "Fix broken sentiment pipeline and wire history endpoint to real data"

## Background

Investigation revealed the sentiment pipeline is NOT missing — it's broken by a single packaging bug. The ingestion Lambda crashes on every invocation with `No module named 'aws_lambda_powertools'` because the ZIP package doesn't include the dependency. The analysis Lambda works. The timeseries DynamoDB table exists with 678 real records (534 tickers, dates 2025-12-20 to 2025-12-22). The `/sentiment/history` endpoint was never wired to read from this table — it still has a synthetic placeholder from development.

**Root cause**: `aws_lambda_powertools` was imported into 5 ingestion files (for X-Ray tracing) but never added to the Lambda ZIP package build.

## User Scenarios & Testing *(mandatory)*

### User Story 1 — Restore Sentiment Data Pipeline (Priority: P1)

The sentiment data pipeline has two stages: (1) the ingestion Lambda fetches articles and publishes them to a message topic, then (2) the analysis Lambda receives those messages, runs ML inference, and writes sentiment scores to the timeseries table. The ingestion Lambda has been crashing on every invocation since ~2025-12-22 because a required dependency is missing from its deployed ZIP package (`StatusCode: 200` with `FunctionError: Unhandled`). The analysis Lambda (Docker-based) is functional but receives no messages because ingestion is dead.

After this fix, the ingestion Lambda imports successfully, fetches articles, and publishes them. The analysis Lambda processes those messages and writes sentiment scores to the timeseries table. The full pipeline resumes producing real data on the existing 5-minute cycle.

**Why this priority**: Nothing else works until data flows end-to-end. This unblocks all other user stories.

**Independent Test**: Invoke the ingestion Lambda directly — verify no `FunctionError` and articles are published. Then verify the analysis Lambda processes the messages and new timeseries records appear.

**Acceptance Scenarios**:

1. **Given** the ingestion Lambda is deployed with the fixed package, **When** it is invoked (manually or by schedule), **Then** it completes without `FunctionError` and returns a response indicating articles fetched and published to the message topic.
2. **Given** the ingestion Lambda publishes messages, **When** the analysis Lambda processes them, **Then** new sentiment records appear in the timeseries table with timestamps after the deployment date.
3. **Given** the full pipeline has been running for 1 hour (12 ingestion cycles), **When** the timeseries table is queried, **Then** records exist for today's date for at least some of the 22 active tickers.
4. **Given** the analysis Lambda needs to load an ML model at cold start, **When** it is triggered by an ingestion message, **Then** the model loads successfully from the artifact store and inference produces valid scores (-1 to +1).

---

### User Story 2 — Wire History Endpoint to Real Data (Priority: P1)

The `/sentiment/history` endpoint currently generates synthetic data using a seeded random number generator. A real timeseries table exists with the correct schema (ticker, date, score, source, count). The endpoint needs to query this table instead of generating fake data.

After this fix, customers see real sentiment scores that reflect actual news coverage and market sentiment. The synthetic data generator is completely removed.

**Why this priority**: Equal P1 — this is the customer-facing half of the fix. The ingestion Lambda produces data; this endpoint serves it.

**Independent Test**: Query `/sentiment/history` for AAPL over a date range that has real data in the timeseries table. Verify the response contains scores matching the stored records, not synthetic values. Verify X-Ray traces show a database read (not 1ms in-process computation).

**Acceptance Scenarios**:

1. **Given** a ticker with records in the timeseries table, **When** a customer queries its sentiment history, **Then** the response contains real scores from the table with correct dates, scores, and source attribution.
2. **Given** a ticker with no records for a date range, **When** the customer queries that range, **Then** the response returns an empty history array with count 0 (not synthetic filler).
3. **Given** the same query is made twice, **When** the second query executes, **Then** results are consistent (same data from the same table, not random).
4. **Given** the synthetic generator code, **When** the feature is deployed, **Then** the sha256-seeded RNG code is completely removed from the codebase.
5. **Given** data exists from December 2025 and from post-fix (March 2026+) with a 3-month gap, **When** a customer queries a 3-month range, **Then** the response contains records from both periods with the gap reflected as missing data points (no interpolation, no synthetic fill).

---

### User Story 3 — Sentiment Endpoint Observability (Priority: P2)

The sentiment endpoint has no cache headers, no cache metrics, and no meaningful X-Ray trace detail. The OHLC endpoint has all three. After this feature, the sentiment endpoint has observability parity.

**Why this priority**: P2 because the data flows without observability, but operating a pipeline blind is what caused 3 months of undetected failure. This prevents the same class of problem from recurring.

**Independent Test**: Run the trace inspection diagnostic against the sentiment endpoint. Verify `x-cache-source` headers appear, cache metrics register in the monitoring system, and X-Ray traces show database subsegments.

**Acceptance Scenarios**:

1. **Given** a sentiment query served from persistent storage, **When** the response is returned, **Then** it includes `x-cache-source: persistent-cache` header.
2. **Given** a sentiment query served from in-memory cache, **When** the response is returned, **Then** it includes `x-cache-source: in-memory` header.
3. **Given** any sentiment query, **When** the response completes, **Then** cache hit or miss metrics are emitted with the cache name "sentiment_history".
4. **Given** any sentiment query, **When** the X-Ray trace is inspected, **Then** database reads appear as subsegments (not a flat 1ms local-only trace).

---

### Edge Cases

- What if the timeseries table has records from December 2025 but nothing recent? The endpoint returns whatever exists — stale data is better than fake data. The most recent record's date in the response indicates data freshness.
- What if the ingestion Lambda's dependency fix reveals additional runtime errors? The fix should be deployed incrementally — fix the import, verify it runs, then validate data quality. Don't bundle with endpoint changes.
- What if the timeseries table schema doesn't match what the history endpoint expects? The investigation confirmed the schema: PK=`{ticker}#{resolution}`, SK=timestamp, fields include avg/sum/count/sources/open/close. The endpoint must be written to read this exact schema.
- What about the 678 existing records from December? They remain in the table and are queryable. They prove the pipeline was working and validate the data format.
- What if the ingestion Lambda now runs but produces different data than December? Acceptable — the pipeline may have been updated since December. Scores should still be in the -1 to +1 range with source attribution.
- What if the ML model artifact is missing or corrupted in the artifact store? The analysis Lambda downloads a ~250MB model at cold start. If the artifact is missing, inference silently fails and no timeseries records are written. Verify the artifact exists before declaring the pipeline healthy.
- What if the external API keys (stored in Secrets Manager) expired or were rotated during the 3-month outage? The ingestion Lambda will run but fetch zero articles. Check the Lambda response for API-level errors, not just absence of `FunctionError`.
- What about the 3-month data gap (Dec 23 - Mar 19)? The history endpoint returns whatever exists. Customers querying a 3-month range will see data from December and from post-fix, with a visible gap. No interpolation or gap-filling.
- What about DynamoDB TTL on timeseries records? The existing records had 90-day TTL and were about to expire. TTL has been disabled on the table to preserve them. Before re-enabling TTL, decide on the retention policy: 90 days may be too short for a sentiment history product. Re-enabling TTL is a deliberate future decision, not an automatic restore.
- What if the analysis Lambda cold start (model download + inference) exceeds its timeout? The Lambda is configured for 2048MB / 60s timeout. DistilBERT is ~250MB. If the first invocation after 3 months exceeds 60s, increase the timeout or pre-warm the Lambda before relying on scheduled ingestion.
- What if sentiment scores are clustered in a narrow range? Existing data shows all scores between 0.87 and 1.0 (mean 0.98). This is the real DistilBERT output on financial news — not a bug. The frontend chart will show a nearly flat positive line. This is a data quality / model calibration concern for future investigation, not a pipeline bug.
- What about source filtering when the stored format is `{provider}:{article_id}`? The `sources` field stores values like `tiingo:91120376`. Source filter parameters (`tiingo`, `finnhub`) must use prefix matching, not exact matching. The `aggregated` filter returns all records regardless of source prefix.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The ingestion Lambda's deployed package MUST include all imported dependencies. The current `ImportModuleError` MUST be resolved.
- **FR-002**: The `/sentiment/history` endpoint MUST query the existing timeseries table for real data instead of generating synthetic data.
- **FR-003**: The synthetic data generator (sha256-seeded RNG in the history endpoint) MUST be completely removed from the codebase.
- **FR-004**: The sentiment history endpoint MUST support the existing query parameters: ticker, source filter, date range (range presets or custom start/end).
- **FR-005**: The system MUST NOT generate synthetic or placeholder data for periods with no real data. Missing periods return empty results.
- **FR-006**: The sentiment endpoint MUST include `x-cache-source` response headers indicating data provenance (in-memory, persistent-cache).
- **FR-007**: The sentiment cache MUST be instrumented with hit/miss/eviction metrics, following the existing OHLC cache pattern.
- **FR-008**: The sentiment endpoint's X-Ray traces MUST show database reads as subsegments.
- **FR-009**: The ingestion pipeline MUST resume producing data on its existing 5-minute schedule after the packaging fix is deployed.

### Key Entities

- **Sentiment Timeseries Record** (existing table, existing schema): PK=`{ticker}#{resolution}`, SK=ISO timestamp. Fields: avg score, count, sources list, open/close scores, TTL, partial flag.
- **Sentiment History Response**: Time-series of score records for a ticker and date range. Includes metadata: ticker, source, date range, count, cache provenance header.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: The ingestion Lambda executes without `FunctionError` on direct invocation, verified within 1 hour of deployment.
- **SC-002**: New sentiment records appear in the timeseries table with today's date within 30 minutes of the ingestion fix being deployed.
- **SC-003**: The `/sentiment/history` endpoint returns real data (not synthetic) for tickers with timeseries records, verified by the trace inspection diagnostic showing database reads in X-Ray traces.
- **SC-004**: The synthetic RNG code is absent from the codebase, verified by searching for `hashlib.sha256.*ticker` pattern.
- **SC-005**: The sentiment endpoint includes `x-cache-source` headers on 100% of responses.
- **SC-006**: Cache metrics for "sentiment_history" appear in the monitoring system within the diagnostic test window.

## Assumptions

- The existing timeseries table schema is correct and complete for serving history responses. No schema migration is needed.
- The ingestion Lambda's only blocker is the missing dependency. No other runtime errors exist beyond the import failure. (If additional errors are discovered, they will be addressed as part of US1 validation.)
- The 5-minute EventBridge schedule is still active and will automatically trigger the Lambda once the package is fixed.
- The existing analysis Lambda (which subscribes to the SNS topic) is functional — it returned a proper validation error when invoked with an empty payload, confirming it can import and run.
- The in-memory cache tier for sentiment history will use the same jittered TTL and CacheStats pattern established by the OHLC cache audit (Feature 1224).
- Current data is Tiingo-only (zero Finnhub records). The `aggregated` source filter returns Tiingo data until multi-source ingestion is implemented. This is acceptable for launch — the data is real, just single-source.
