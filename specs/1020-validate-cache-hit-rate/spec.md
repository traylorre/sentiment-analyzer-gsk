# Feature Specification: Validate 80% Cache Hit Rate

**Feature Branch**: `1020-validate-cache-hit-rate`
**Created**: 2025-12-22
**Updated**: 2025-12-22
**Status**: Draft
**Parent Spec**: specs/1009-realtime-multi-resolution/spec.md (T066)
**Success Criterion**: SC-008 - Cache hit rate for shared ticker data exceeds 80% during normal operation

---

## Canonical Sources & Citations

| ID | Source | Title | URL/Reference | Relevance |
|----|--------|-------|---------------|-----------|
| [CS-005] | AWS Documentation | Lambda Best Practices | https://docs.aws.amazon.com/lambda/latest/dg/best-practices.html | Global scope caching |
| [CS-006] | Yan Cui | AWS Lambda: The Complete Guide | https://theburningmonk.com/ | Warm invocation caching |
| [CS-015] | CloudWatch Logs | Logs Insights Query Syntax | https://docs.aws.amazon.com/AmazonCloudWatch/latest/logs/CWL_QuerySyntax.html | Aggregation queries |

---

## User Scenarios & Testing

### User Story 1 - Validate Cache Performance Exceeds 80% (Priority: P1)

As a system operator, I want to verify that the cache hit rate exceeds 80% during normal dashboard usage, so I can confirm the architecture delivers the promised performance without excessive DynamoDB reads.

**Why this priority**: Cache performance directly impacts cost (DynamoDB reads), latency (cache hits are instant), and user experience (resolution switching feels instant with warm cache).

**Independent Test**: Run E2E test suite that simulates normal usage patterns (resolution switching, multi-ticker views) and verify cache stats show >80% hit rate.

**Acceptance Scenarios**:

1. **Given** the dashboard is loaded with default ticker and resolution, **When** a user switches between resolutions multiple times, **Then** the cache hit rate reported in logs exceeds 80%
2. **Given** multiple users are viewing the same ticker, **When** they request the same resolution data, **Then** subsequent requests hit the cache (only first request fetches from DynamoDB)
3. **Given** the Lambda has been warm for 5 minutes with active users, **When** cache stats are queried, **Then** the hit rate exceeds 80%

---

### User Story 2 - Log Cache Metrics to CloudWatch (Priority: P1)

As a DevOps engineer, I want cache hit/miss metrics logged to CloudWatch Logs in structured JSON format, so I can query and analyze cache performance over time using CloudWatch Logs Insights.

**Why this priority**: Without observable metrics, there's no way to validate SC-008 or diagnose cache performance issues in production.

**Independent Test**: Invoke Lambda endpoints and verify CloudWatch Logs contain structured cache metric entries that can be queried.

**Acceptance Scenarios**:

1. **Given** the SSE streaming Lambda processes requests, **When** cache operations occur, **Then** structured JSON logs are emitted with event_type, hits, misses, hit_rate fields
2. **Given** CloudWatch Logs contain cache metrics, **When** a Logs Insights query is executed, **Then** aggregate hit rate can be calculated across time periods
3. **Given** cache metrics are logged periodically (every 60s or on significant changes), **When** reviewing logs, **Then** the logging does not impact Lambda performance (non-blocking)

---

### User Story 3 - Provide CloudWatch Logs Insights Queries (Priority: P2)

As a DevOps engineer, I want pre-built CloudWatch Logs Insights queries for cache analysis, so I can quickly assess cache health without writing queries from scratch.

**Why this priority**: Query templates enable rapid troubleshooting and validation without deep CloudWatch expertise.

**Independent Test**: Execute provided queries against preprod logs and verify meaningful results are returned.

**Acceptance Scenarios**:

1. **Given** the documentation includes Logs Insights queries, **When** the "Hit rate over time" query is executed, **Then** it returns time-bucketed hit rates
2. **Given** queries are documented, **When** the "Hit rate by ticker" query is executed, **Then** it shows which tickers have lowest cache efficiency
3. **Given** queries are documented, **When** the "Cache misses spike detection" query is executed, **Then** it identifies periods of poor cache performance

---

### User Story 4 - Document Cache Tuning Recommendations (Priority: P2)

As a system operator, I want documentation explaining cache behavior patterns and tuning recommendations, so I can optimize cache performance if hit rate falls below 80%.

**Why this priority**: Documentation enables self-service troubleshooting without escalation.

**Independent Test**: Review documentation and verify it covers common scenarios (cold start, TTL expiration, LRU eviction) with actionable guidance.

**Acceptance Scenarios**:

1. **Given** the documentation exists, **When** reviewing cache behavior section, **Then** it explains TTL expiration aligned with resolution duration
2. **Given** the documentation exists, **When** reviewing tuning section, **Then** it provides max_entries sizing guidance based on ticker count and resolution coverage
3. **Given** the documentation exists, **When** a cache miss spike occurs, **Then** the troubleshooting section helps identify root cause (cold starts, TTL, eviction)

---

## Functional Requirements

- **FR-001**: Add structured JSON logging for cache metrics to SSE streaming Lambda [US2]
- **FR-002**: Log cache stats periodically (every 60 seconds) when active connections exist [US2]
- **FR-003**: Log cache stats on significant events (cache clear, threshold crossings) [US2]
- **FR-004**: Include ticker context in cache metric logs for per-ticker analysis [US2]
- **FR-005**: Provide CloudWatch Logs Insights query for aggregate hit rate [US3]
- **FR-006**: Provide CloudWatch Logs Insights query for hit rate by ticker [US3]
- **FR-007**: Provide CloudWatch Logs Insights query for time-series hit rate trend [US3]
- **FR-008**: Document cache TTL behavior (resolution-aligned expiration) [US4]
- **FR-009**: Document LRU eviction behavior and max_entries sizing [US4]
- **FR-010**: Document cold start impact on cache performance [US4]
- **FR-011**: Create E2E test that validates >80% hit rate during normal usage [US1]

---

## Non-Functional Requirements

- **NFR-001**: Cache metric logging MUST NOT impact Lambda latency (non-blocking writes)
- **NFR-002**: Cache stats logging should add <1KB per minute to CloudWatch Logs volume
- **NFR-003**: E2E test must complete within 60 seconds
- **NFR-004**: Documentation must be accessible via quickstart.md reference

---

## Success Criteria

- **SC-001**: E2E test demonstrates >80% cache hit rate with normal usage patterns
- **SC-002**: CloudWatch Logs contain structured cache metrics queryable via Logs Insights
- **SC-003**: Documentation covers cache behavior, tuning, and troubleshooting
- **SC-004**: Cache logging adds no measurable latency to request processing

---

## Technical Constraints

- **TC-001**: ResolutionCache already exists in src/lib/timeseries/cache.py with CacheStats
- **TC-002**: Must use structlog for JSON logging (existing pattern in codebase)
- **TC-003**: CloudWatch Logs Insights has 10,000 result limit and query timeout
- **TC-004**: Lambda global scope caching per [CS-005], [CS-006]

---

## Out of Scope

- Custom CloudWatch metrics (PutMetricData) - use Logs Insights on structured logs instead
- Dashboard UI for cache stats - observability via CloudWatch Logs Insights only
- Modifying cache TTL or eviction policies - document existing behavior only
- Real-time alerting on cache performance - manual query validation only

---

## Dependencies

- src/lib/timeseries/cache.py - ResolutionCache with CacheStats (exists)
- src/lambdas/sse_streaming/ - SSE Lambda for logging integration
- CloudWatch Logs - Log group for SSE Lambda
- specs/1009-realtime-multi-resolution/ - Parent spec with SC-008 definition

---

## Test Design (TDD)

### Unit Tests

```python
# tests/unit/test_cache_metrics_logger.py

def test_log_cache_metrics_emits_structured_json():
    """Verify cache metrics logged in queryable JSON format."""
    # Arrange: Create cache with known hits/misses
    # Act: Call log_cache_metrics()
    # Assert: Log entry contains event_type, hits, misses, hit_rate

def test_log_cache_metrics_includes_ticker_context():
    """Verify ticker is included for per-ticker analysis."""
    # Arrange: Create cache with ticker-specific stats
    # Act: Call log_cache_metrics(ticker="AAPL")
    # Assert: Log entry contains ticker field

def test_cache_metrics_logger_non_blocking():
    """Verify logging does not impact cache operations."""
    # Arrange: Create cache with logging enabled
    # Act: Time 1000 cache operations
    # Assert: No measurable latency difference vs logging disabled
```

### E2E Tests

```python
# tests/e2e/test_cache_hit_rate.py

def test_cache_hit_rate_exceeds_80_percent():
    """SC-008: Validate >80% cache hit rate during normal usage."""
    # Arrange: Connect to preprod SSE stream
    # Act: Simulate normal usage (resolution switches, multi-ticker)
    # Assert: Final cache stats show hit_rate > 0.80

def test_cache_metrics_logged_to_cloudwatch():
    """Verify cache metrics appear in CloudWatch Logs."""
    # Arrange: Generate cache activity via SSE stream
    # Act: Query CloudWatch Logs Insights for cache metrics
    # Assert: Results contain expected metric fields
```
