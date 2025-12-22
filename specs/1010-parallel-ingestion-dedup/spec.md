# Feature Specification: Parallel Ingestion with Cross-Source Deduplication

**Feature Branch**: `1010-parallel-ingestion-dedup`
**Created**: 2025-12-21
**Status**: Draft
**Input**: User description: "Tiingo and Finnhub Parallel News Ingestion with Collision Detection: After upgrading Tiingo plan, integrate Tiingo news API alongside existing Finnhub adapter. This tests parallel ingestion from two sources with robust cross-source deduplication to prevent processing the same article twice when both sources carry identical or near-identical content."

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Cross-Source Duplicate Prevention (Priority: P1)

As a system operator, I want articles that appear in both Tiingo and Finnhub to be stored only once in the database, so that downstream sentiment analysis processes each unique article exactly once rather than wasting compute resources on duplicates.

**Why this priority**: This is the core value proposition - without cross-source deduplication, the system would process the same Reuters/AP article twice (once from each source), doubling sentiment analysis costs, creating conflicting dashboard entries, and potentially skewing aggregate metrics.

**Independent Test**: Ingest a known article (e.g., Apple earnings report from Reuters) that appears in both Tiingo and Finnhub. Verify exactly one database record is created with both sources tracked, and exactly one sentiment analysis message is published.

**Acceptance Scenarios**:

1. **Given** an article with headline "Apple Reports Q4 Earnings Beat" exists in both Tiingo and Finnhub feeds, **When** the ingestion process runs, **Then** exactly one database record is created with `sources: ["tiingo", "finnhub"]`
2. **Given** the same article is ingested from Tiingo first then Finnhub, **When** Finnhub returns the duplicate, **Then** the existing record is updated to add "finnhub" to sources without creating a new record
3. **Given** the same article is ingested from Finnhub first then Tiingo, **When** Tiingo returns the duplicate, **Then** the existing record is updated to add "tiingo" to sources without creating a new record

---

### User Story 2 - Parallel Source Fetching (Priority: P2)

As a system operator, I want news articles to be fetched from Tiingo and Finnhub simultaneously rather than sequentially, so that the total ingestion time is reduced and the system can process more tickers within rate limits.

**Why this priority**: Parallel fetching improves throughput, but cross-source dedup (P1) must work first. This optimization builds on the dedup foundation.

**Independent Test**: Time the ingestion of 10 tickers with parallel fetching vs baseline. Verify parallel fetch + dedup completes in under 500ms total (excluding network latency variance).

**Acceptance Scenarios**:

1. **Given** 10 tickers need news ingestion, **When** the ingestion process runs, **Then** Tiingo and Finnhub requests for all tickers are initiated concurrently
2. **Given** Tiingo returns faster than Finnhub for a ticker, **When** both complete, **Then** articles from both sources are deduped correctly regardless of arrival order
3. **Given** Tiingo rate limit is reached mid-batch, **When** Tiingo fails, **Then** Finnhub continues unaffected and Tiingo articles are skipped gracefully

---

### User Story 3 - Multi-Source Attribution Tracking (Priority: P3)

As a dashboard analyst, I want to see which news sources provided each article, so that I can assess source reliability and understand article provenance.

**Why this priority**: Attribution is valuable for analysis but not critical for core functionality. The system works without it, but it enhances data quality insights.

**Independent Test**: Query an article that was found in both sources and verify the response includes complete attribution metadata for each source.

**Acceptance Scenarios**:

1. **Given** an article was found in both Tiingo and Finnhub, **When** I query the article details, **Then** I see attribution metadata for both sources including source-specific article IDs
2. **Given** an article was found only in Tiingo, **When** I query the article details, **Then** I see only Tiingo attribution with no Finnhub entry
3. **Given** a batch of 100 articles is ingested, **When** I aggregate by source count, **Then** I can see how many were single-source vs multi-source

---

### User Story 4 - Collision Metrics & Monitoring (Priority: P4)

As a system operator, I want visibility into the cross-source collision rate, so that I can validate the deduplication system is working correctly and tune parameters if needed.

**Why this priority**: Operational visibility is important for production health but can be added after core functionality works.

**Independent Test**: After ingesting a batch of articles, query metrics to see collision statistics.

**Acceptance Scenarios**:

1. **Given** 100 articles are ingested (50 from Tiingo, 50 from Finnhub), **When** 30 are duplicates, **Then** metrics show 70 unique articles stored and 30 collisions detected
2. **Given** the collision rate exceeds 40%, **When** metrics are checked, **Then** an alert threshold is triggered for investigation
3. **Given** a daily summary is generated, **When** I view it, **Then** I see collision rate, unique count, per-source counts, and trends

---

### Edge Cases

- **Near-identical headlines**: When an article headline differs only by punctuation or trailing source attribution (e.g., "Apple Beats Estimates" vs "Apple Beats Estimates - Reuters"), the system uses normalized headline comparison (lowercase, strip punctuation, trim whitespace) to catch near-duplicates
- **Same headline, different dates**: The publish date is included in the dedup key, so the same headline appearing on different days creates distinct articles
- **Single source failure**: If one source returns an error but the other succeeds, processing continues for the successful source; the failure is logged and handled by existing circuit breaker patterns
- **Wire service attribution**: Both sources may cite the same underlying wire service (e.g., Reuters). The headline-based dedup catches this; source attribution tracks both provider IDs for provenance
- **Race conditions in parallel fetching**: When network latency causes timing variations, atomic conditional writes ensure upsert behavior is consistent regardless of which source arrives first

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: System MUST identify duplicate articles across sources using headline-based deduplication keys
- **FR-002**: System MUST normalize headlines before comparison (lowercase, strip punctuation, trim whitespace)
- **FR-003**: System MUST include publish date in deduplication key to distinguish same headline on different days
- **FR-004**: System MUST track all sources that provided an article in a `sources` array field
- **FR-005**: System MUST preserve source-specific metadata (article ID, URL, crawl timestamp) for each contributing source
- **FR-006**: System MUST fetch from Tiingo and Finnhub in parallel to reduce total ingestion time
- **FR-007**: System MUST continue processing if one source fails while the other succeeds
- **FR-008**: System MUST publish exactly one message per unique article regardless of how many sources provide it
- **FR-009**: System MUST use atomic conditional writes to prevent race conditions during parallel ingestion
- **FR-010**: System MUST record collision metrics (total articles, unique articles, collision count, per-source counts)
- **FR-011**: System MUST handle rate limits from either source independently without affecting the other
- **FR-012**: System MUST update existing articles to add new sources rather than overwriting

### Key Entities

- **Article**: A unique news item identified by normalized headline + publish date. Contains: headline, publish_date, sources (array), source_attribution (map of source to metadata), sentiment_score (after analysis), created_at, updated_at
- **Source Attribution**: Per-source metadata including: source_article_id, source_url, crawl_timestamp, original_headline (before normalization)
- **Collision Event**: A record of when deduplication matched an incoming article to an existing record. Used for metrics.
- **Ingestion Batch**: A collection of articles fetched in one ingestion run, tracking: ticker, sources_queried, articles_fetched, articles_stored, collisions_detected, duration_ms

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Zero duplicate messages published for the same article appearing in both sources
- **SC-002**: Parallel fetch + deduplication completes in under 500ms for 10 tickers (excluding network latency)
- **SC-003**: Cross-source collision rate falls within expected range of 15-25% (indicating dedup is working correctly)
- **SC-004**: System maintains independent source processing - one source failure does not block the other
- **SC-005**: Article attribution accurately tracks all contributing sources with 100% accuracy
- **SC-006**: Ingestion throughput remains stable (no regression) compared to single-source baseline
- **SC-007**: No data loss - all unique articles from both sources are captured
- **SC-008**: Alert triggered if collision rate exceeds 40% (possible dedup misconfiguration) or drops below 5% (possible dedup over-matching)

## Assumptions

1. Headlines are the most reliable indicator of article identity across sources (source-specific article IDs are not correlated)
2. Same-day articles with identical normalized headlines are duplicates; different-day articles are distinct
3. Tiingo and Finnhub rate limits are managed independently by existing quota tracking infrastructure
4. Existing circuit breaker patterns handle transient failures appropriately
5. Conditional database expressions provide sufficient atomicity for concurrent upserts
6. The expected 15-25% collision rate is based on typical financial news overlap between aggregators
