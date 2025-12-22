# Feature Specification: Validate Resolution Switching Performance

**Feature Branch**: `1018-validate-resolution-switching-perf`
**Created**: 2025-12-22
**Status**: Draft
**Input**: User description: "T064: Validate <100ms resolution switching (SC-002) with timing metrics. Add instrumentation to measure perceived resolution switch latency. Capture metrics in CloudWatch custom metrics or console timing API. Create performance test that switches resolutions 100+ times and validates p95 < 100ms. Document measurement methodology in docs/performance-validation.md."

---

## Canonical Sources & Citations

| ID | Source | Title | URL/Reference | Relevance |
|----|--------|-------|---------------|-----------|
| [CS-001] | Parent Spec | SC-002: Resolution Switch Latency | specs/1009-realtime-multi-resolution/spec.md | 100ms target requirement |
| [CS-002] | W3C | Performance Timeline API | https://www.w3.org/TR/performance-timeline/ | Client timing measurement |
| [CS-003] | W3C | User Timing API | https://www.w3.org/TR/user-timing/ | Custom performance marks |
| [CS-004] | AWS Docs | CloudWatch Custom Metrics | https://docs.aws.amazon.com/AmazonCloudWatch/latest/monitoring/publishingMetrics.html | Metric publishing |
| [CS-005] | MDN | Performance.measure() | https://developer.mozilla.org/en-US/docs/Web/API/Performance/measure | Precise timing |

---

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Validate Performance Target (Priority: P1)

As a system operator, I want to verify that resolution switching meets the <100ms p95 latency target (SC-002), so I can confirm the dashboard delivers the promised user experience.

**Why this priority**: The 100ms target is a core success criterion from the parent spec. If we can't validate it, we can't claim the feature works as specified.

**Independent Test**: Can be fully tested by running an automated performance test that switches resolutions 100+ times and analyzes the timing distribution.

**Acceptance Scenarios**:

1. **Given** the multi-resolution dashboard is deployed, **When** a performance test switches between all 8 resolutions 100+ times, **Then** the p95 latency is below 100ms
2. **Given** the performance test is running, **When** individual switch timings are recorded, **Then** each measurement includes start time, end time, and resolution pair (from → to)
3. **Given** performance test results exist, **When** a developer reviews the output, **Then** they see a statistical summary with min, max, mean, p50, p90, p95, and p99 latencies

---

### User Story 2 - Instrument Resolution Switching (Priority: P1)

As a developer, I want timing instrumentation added to resolution switching, so I can measure perceived latency from the user's perspective in production.

**Why this priority**: Without instrumentation, we cannot measure actual production performance or detect regressions over time.

**Independent Test**: Can be tested by triggering a resolution switch and verifying timing metrics are captured and available for analysis.

**Acceptance Scenarios**:

1. **Given** the dashboard JavaScript is loaded, **When** a user switches resolution, **Then** the client records start and end timestamps using the Performance API
2. **Given** resolution switch timing is captured, **When** metrics are reported, **Then** the measurement accurately reflects "user perceived time" (from click to visible data update)
3. **Given** multiple resolution switches occur, **When** reviewing captured metrics, **Then** each switch is uniquely identified by timestamp and resolution transition

---

### User Story 3 - Document Performance Validation (Priority: P2)

As a team member, I want a documented performance validation methodology, so I can understand how to run performance tests, interpret results, and add new performance validations.

**Why this priority**: Documentation ensures reproducibility and enables team members to run validations independently.

**Independent Test**: Can be tested by following the documented procedure and successfully running a performance validation.

**Acceptance Scenarios**:

1. **Given** the docs/performance-validation.md file exists, **When** a developer reads it, **Then** they understand how resolution switching latency is measured
2. **Given** the methodology is documented, **When** comparing results across runs, **Then** the methodology produces consistent, reproducible measurements
3. **Given** future performance targets are added, **When** updating documentation, **Then** the existing methodology pattern is easy to extend

---

### Edge Cases

- What happens when switching resolution during an active SSE update? Timing should exclude network latency from live updates.
- How does system handle rapid switching (e.g., 10 switches in 1 second)? Each switch should be measured independently.
- What if browser tab is backgrounded during test? Test should detect and exclude backgrounded periods.
- How are cache-hit vs cache-miss switches differentiated in metrics? Metrics should tag switch type.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: System MUST instrument resolution switching with start and end timestamps using the browser Performance API
- **FR-002**: System MUST calculate perceived switch latency as the time from user click to visible data render completion
- **FR-003**: System MUST support running a performance test that executes 100+ resolution switches programmatically
- **FR-004**: System MUST calculate statistical summaries (min, max, mean, p50, p90, p95, p99) from collected measurements
- **FR-005**: System MUST output performance test results in a parseable format (JSON or structured logs)
- **FR-006**: Performance test MUST assert that p95 latency is below 100ms, failing the test if exceeded
- **FR-007**: System MUST provide documentation explaining the measurement methodology and how to run performance tests
- **FR-008**: Instrumentation MUST differentiate between cache-hit switches (data already loaded) and cache-miss switches (requires fetch)

### Key Entities

- **SwitchTiming**: A single resolution switch measurement including timestamp, from_resolution, to_resolution, duration_ms, cache_hit boolean
- **PerformanceReport**: Aggregated statistics from a test run including sample_count, min_ms, max_ms, mean_ms, p50_ms, p90_ms, p95_ms, p99_ms
- **ResolutionTransition**: A pair of resolutions representing a switch (e.g., "1m → 5m")

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Performance test validates p95 resolution switch latency is below 100ms across 100+ samples
- **SC-002**: Each resolution switch captures timing data with millisecond precision
- **SC-003**: Performance test runs complete within 2 minutes for 100 switches
- **SC-004**: Documentation enables a new team member to run the validation within 5 minutes
- **SC-005**: 100% of resolution transitions between all 8 resolutions are testable

## Assumptions

- Browser Performance API is available (all modern browsers support it)
- Tests run against a deployed preprod environment with representative data
- Cache behavior matches production (warm cache for previously viewed resolutions)
- Network latency to preprod is representative of production user experience
- Playwright E2E framework is already available for performance testing

## Out of Scope

- Server-side timing metrics (this feature focuses on client-perceived latency)
- Real-time alerting on performance degradation (addressed in separate monitoring feature)
- Performance optimization implementation (this feature only validates the target is met)
- Load testing with concurrent users (this feature tests single-user resolution switching)

## Dependencies

- Multi-resolution dashboard deployed to preprod (spec 1009)
- Timeseries API endpoints returning data for all 8 resolutions
- Client-side caching implementation working correctly
