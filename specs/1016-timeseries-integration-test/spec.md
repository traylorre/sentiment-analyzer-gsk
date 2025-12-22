# Feature Specification: Timeseries Integration Test Suite

**Feature Branch**: `1016-timeseries-integration-test`
**Created**: 2025-12-22
**Updated**: 2025-12-22
**Status**: Draft
**Input**: User description: "T062: Implement tests/integration/test_timeseries_pipeline.py with LocalStack per [CS-001]. Full integration test for timeseries pipeline: ingest -> fanout -> query -> SSE stream. Uses LocalStack DynamoDB for realistic testing."

---

## Canonical Sources & Citations

This specification's design decisions are grounded in authoritative sources from the parent feature (1009-realtime-multi-resolution).

### Primary References

| ID | Source | Title | Relevance |
|----|--------|-------|-----------|
| [CS-001] | AWS Documentation | Best Practices for Designing with DynamoDB | Write fanout, key design, TTL |
| [CS-002] | AWS Blog | Choosing the Right DynamoDB Partition Key | Composite key pattern |
| [CS-003] | Rick Houlihan (AWS) | Advanced Design Patterns for DynamoDB | Time-series patterns |
| [CS-009] | Prometheus Docs | Time-Series Alignment | Bucket alignment |

---

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Validate Write Fanout Creates All Resolution Items (Priority: P1)

As a developer running integration tests, I want to verify that a single sentiment score ingestion correctly produces 8 DynamoDB items (one per resolution level), so I can trust that the write fanout pattern works correctly before deploying to production.

**Why this priority**: The write fanout is the foundation of the multi-resolution architecture. If fanout fails, no resolution switching or historical queries will work. This is the most critical integration point.

**Independent Test**: Can be fully tested by ingesting one sentiment score and scanning the timeseries table to count items. Delivers confidence that the core data pipeline works.

**Acceptance Scenarios**:

1. **Given** an empty timeseries table in LocalStack, **When** a single sentiment score is ingested with timestamp 10:35:47Z, **Then** exactly 8 items exist in the table (one for each resolution: 1m, 5m, 10m, 1h, 3h, 6h, 12h, 24h)
2. **Given** a sentiment score for ticker AAPL, **When** fanout completes, **Then** each item has the correct partition key format `{ticker}#{resolution}` (e.g., AAPL#1m, AAPL#5m)
3. **Given** a sentiment score at 10:37:47Z, **When** fanout completes, **Then** each resolution's bucket timestamp is correctly aligned (1m: 10:37:00, 5m: 10:35:00, 1h: 10:00:00, etc.)

---

### User Story 2 - Validate Query Returns Buckets in Time Order (Priority: P1)

As a developer running integration tests, I want to verify that querying a time range returns buckets in ascending timestamp order, so I can trust that the dashboard will display data correctly.

**Why this priority**: Correct query ordering is essential for time-series visualization. Incorrect ordering would render the dashboard unusable.

**Independent Test**: Can be fully tested by inserting multiple buckets and querying with a time range, verifying order. Delivers confidence that data retrieval works correctly.

**Acceptance Scenarios**:

1. **Given** 5 buckets exist for AAPL#5m at timestamps 10:30, 10:35, 10:40, 10:45, 10:50, **When** querying with start=10:25 and end=10:55, **Then** all 5 buckets are returned in ascending order (10:30 < 10:35 < 10:40 < 10:45 < 10:50)
2. **Given** buckets are inserted out of order (10:40, 10:30, 10:50, 10:35, 10:45), **When** querying the range, **Then** results are still returned in ascending timestamp order
3. **Given** a time range that spans no buckets, **When** querying, **Then** an empty list is returned (not an error)

---

### User Story 3 - Validate Partial Bucket Flagging (Priority: P2)

As a developer running integration tests, I want to verify that the current in-progress bucket is correctly flagged as partial with a progress percentage, so I can trust that the dashboard will display real-time progress indicators.

**Why this priority**: Partial bucket flagging enables the "live breathing data" experience. Important but secondary to core data flow.

**Independent Test**: Can be fully tested by inserting a bucket at the current time and verifying its partial flag and progress calculation. Delivers confidence that real-time indicators work.

**Acceptance Scenarios**:

1. **Given** current time is mid-bucket (e.g., 10:37:30 for a 5m bucket starting 10:35:00), **When** querying includes the current bucket, **Then** the response marks the current bucket as `is_partial=True`
2. **Given** a partial bucket at 50% progress (2.5 minutes into a 5-minute bucket), **When** querying, **Then** `progress_pct` is approximately 50%
3. **Given** a bucket that is fully complete (current time past bucket end), **When** querying, **Then** the bucket has `is_partial=False` and `progress_pct=100%`

---

### User Story 4 - Validate OHLC Aggregation Accuracy (Priority: P2)

As a developer running integration tests, I want to verify that multiple sentiment scores within a bucket are correctly aggregated into OHLC (Open/High/Low/Close) values, so I can trust that aggregated data represents actual sentiment trends.

**Why this priority**: OHLC aggregation is the primary data summarization technique. Incorrect aggregation would produce misleading charts.

**Independent Test**: Can be fully tested by writing multiple scores to a single bucket and verifying OHLC values. Delivers confidence in data aggregation accuracy.

**Acceptance Scenarios**:

1. **Given** 4 sentiment scores [0.6, 0.9, 0.3, 0.7] in timestamp order for the same bucket, **When** the bucket is queried, **Then** OHLC values are: open=0.6, high=0.9, low=0.3, close=0.7
2. **Given** scores with labels [positive, neutral, positive, negative], **When** the bucket is queried, **Then** `label_counts` is {positive: 2, neutral: 1, negative: 1}
3. **Given** scores [0.6, 0.8], **When** the bucket is queried, **Then** `avg` is 0.7 and `count` is 2

---

### Edge Cases

- What happens when the table does not exist? (Test setup should create it, test should fail gracefully with clear error if missing)
- What happens when querying with start > end? (Should return empty list or raise validation error)
- What happens when a sentiment score has edge timestamp values? (Midnight boundary, leap seconds should align correctly)
- What happens when two scores have identical timestamps? (Both should be included in aggregation, order by ingestion time)
- What happens when the table has TTL-expired items? (LocalStack should handle TTL correctly, tests should not rely on expired data)

---

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: Test suite MUST use LocalStack for DynamoDB to provide realistic AWS behavior without cloud costs
- **FR-002**: Test suite MUST create and tear down the timeseries table for each test class to ensure isolation
- **FR-003**: Test suite MUST verify write fanout produces exactly 8 items (one per resolution) for each ingested score
- **FR-004**: Test suite MUST verify partition key format follows `{ticker}#{resolution}` pattern per [CS-002]
- **FR-005**: Test suite MUST verify sort key contains ISO8601 bucket timestamp aligned to resolution boundaries
- **FR-006**: Test suite MUST verify query results are returned in ascending timestamp order
- **FR-007**: Test suite MUST verify partial bucket detection with progress percentage calculation
- **FR-008**: Test suite MUST verify OHLC aggregation produces correct open, high, low, close values
- **FR-009**: Test suite MUST verify TTL values are set correctly per resolution (6h for 1m, 12h for 5m, etc.)
- **FR-010**: Test suite MUST run as part of the standard integration test suite (`pytest tests/integration/`)

### Key Entities

- **Timeseries Table**: DynamoDB table with composite key (PK: ticker#resolution, SK: bucket timestamp) storing aggregated sentiment buckets
- **Sentiment Score**: Input data representing a single sentiment analysis result with ticker, value, label, and timestamp
- **Sentiment Bucket**: Aggregated time-bounded sentiment data containing OHLC values, label counts, and article count
- **Partial Bucket**: An incomplete bucket representing current in-progress time period with progress percentage

---

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: All 4 user story test scenarios pass consistently (100% pass rate across 10 consecutive runs)
- **SC-002**: Integration test suite completes in under 60 seconds on standard CI hardware
- **SC-003**: No flaky tests - each test produces identical results when run 10 times in sequence
- **SC-004**: Test coverage for timeseries pipeline code exceeds 80%
- **SC-005**: Tests detect regressions - intentionally breaking fanout logic causes at least one test to fail
- **SC-006**: Tests run successfully in both local development and CI environments

---

## Assumptions

- LocalStack is available and properly configured in the test environment
- The timeseries library (`src/lib/timeseries/`) is already implemented from earlier phases
- The write fanout function (`src/lambdas/ingestion/timeseries_fanout.py`) exists and can be imported
- Standard pytest fixtures for LocalStack DynamoDB are available in `tests/conftest.py`
- Tests will use `freezegun` for time mocking to ensure deterministic partial bucket calculations
- Test data will use synthetic but realistic ticker symbols (AAPL, TSLA, MSFT) and sentiment values (0.0-1.0 range)

---

## Scope Boundaries

**In Scope**:
- Integration tests for write fanout to all 8 resolutions
- Integration tests for query with time range and ordering
- Integration tests for partial bucket flagging and progress
- Integration tests for OHLC aggregation accuracy
- LocalStack-based realistic DynamoDB behavior
- Test isolation with table setup/teardown

**Out of Scope**:
- SSE streaming integration tests (covered in separate E2E test feature)
- Performance/load testing (covered in performance validation feature)
- Client-side caching tests (covered in E2E dashboard tests)
- Multi-user concurrent access tests (covered in E2E tests)
- Production AWS testing (this is LocalStack only)
