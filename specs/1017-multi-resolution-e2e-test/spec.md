# Feature Specification: Multi-Resolution Dashboard E2E Test Suite

**Feature Branch**: `1017-multi-resolution-e2e-test`
**Created**: 2025-12-22
**Status**: Draft
**Parent Spec**: `specs/1009-realtime-multi-resolution/spec.md`
**Task Reference**: T063 from Phase 8

---

## Overview

Implement comprehensive E2E tests for the multi-resolution dashboard feature using Playwright against preprod. Tests validate all 5 user stories from the parent spec work together in a production-like environment, covering the complete user journey from dashboard load through resolution switching, live updates, historical scrolling, multi-ticker view, and connectivity resilience.

---

## Canonical Sources & Citations

| ID | Source | Title | Relevance |
|----|--------|-------|-----------|
| [CS-007] | MDN | Server-Sent Events | SSE patterns, auto-reconnection |
| [CS-008] | MDN | IndexedDB API | Client-side caching |
| [CS-PARENT] | Parent Spec | specs/1009-realtime-multi-resolution/spec.md | User stories, success criteria |

---

## User Scenarios & Testing

### User Story 1 - Dashboard Load and Initial Display (Priority: P1)

As a test engineer, I want to verify the dashboard loads within performance targets, so I can ensure the initial user experience meets specifications.

**Acceptance Scenarios**:

1. **Given** preprod is available, **When** dashboard is loaded, **Then** initial render completes within 500ms (SC-001)
2. **Given** dashboard is loaded, **When** sentiment data appears, **Then** skeleton placeholders are shown (FR-011), never loading spinners
3. **Given** dashboard is loaded with ticker, **When** data is available, **Then** the correct resolution (default 5m) is displayed

---

### User Story 2 - Resolution Switching Validation (Priority: P1)

As a test engineer, I want to verify resolution switching meets performance requirements, so I can ensure fluid user exploration of sentiment trends.

**Acceptance Scenarios**:

1. **Given** user is viewing 1m resolution, **When** user switches to 5m, **Then** switch completes within 100ms (SC-002)
2. **Given** user switches to any resolution, **When** data loads, **Then** all 8 resolutions are available (FR-002)
3. **Given** user switches back to previously viewed resolution, **When** data appears, **Then** it loads instantly from cache (FR-005, SC-008)

---

### User Story 3 - Live Sentiment Updates (Priority: P1)

As a test engineer, I want to verify live updates are received, so I can ensure users see real-time sentiment changes.

**Acceptance Scenarios**:

1. **Given** SSE connection is established, **When** heartbeat event arrives, **Then** dashboard acknowledges within 3 seconds (SC-003)
2. **Given** user is viewing live data, **When** partial bucket is current, **Then** progress indicator is visible (FR-004)
3. **Given** SSE connection, **When** new sentiment event arrives, **Then** chart updates without page refresh

---

### User Story 4 - Historical Data Scrolling (Priority: P2)

As a test engineer, I want to verify historical scrolling works smoothly, so I can ensure users can explore past sentiment trends.

**Acceptance Scenarios**:

1. **Given** user views current data, **When** user scrolls left, **Then** previous time range loads seamlessly (SC-005)
2. **Given** historical data is loaded, **When** same range is requested again, **Then** data loads from cache (FR-008)
3. **Given** user is viewing history, **When** new live data arrives, **Then** historical view remains stable (edge case)

---

### User Story 5 - Multi-Ticker and Connectivity (Priority: P2)

As a test engineer, I want to verify multi-ticker view and connectivity resilience, so I can ensure users can compare multiple tickers and recover from network issues.

**Acceptance Scenarios**:

1. **Given** multi-ticker view requested, **When** 10 tickers are loaded, **Then** all load within 1 second (SC-006)
2. **Given** network interruption, **When** connectivity resumes, **Then** auto-reconnection completes within 5 seconds (SC-007)
3. **Given** SSE unavailable, **When** fallback activates, **Then** polling mode indicator is visible (FR-010)

---

## Requirements

### Functional Requirements

- **FR-E2E-001**: Test suite MUST use Playwright for browser automation
- **FR-E2E-002**: Tests MUST run against preprod environment only
- **FR-E2E-003**: Tests MUST measure and assert on performance metrics (load time, switch time)
- **FR-E2E-004**: Tests MUST validate all 8 resolution levels are functional
- **FR-E2E-005**: Tests MUST verify SSE connection and event handling
- **FR-E2E-006**: Tests MUST validate skeleton UI pattern (no spinners)
- **FR-E2E-007**: Tests MUST use deterministic test data via synthetic fixtures
- **FR-E2E-008**: Tests MUST clean up test data via TTL (7 days)

### Non-Functional Requirements

- **NFR-E2E-001**: Test suite MUST complete within 10 minutes
- **NFR-E2E-002**: Tests MUST be parallelizable (no shared state between tests)
- **NFR-E2E-003**: Skip rate MUST remain below 15% (SC from parent)

---

## Success Criteria

| ID | Criterion | Target |
|----|-----------|--------|
| SC-E2E-001 | Dashboard initial load test passes | < 500ms |
| SC-E2E-002 | Resolution switch test passes | < 100ms |
| SC-E2E-003 | SSE heartbeat test passes | < 3s latency |
| SC-E2E-004 | Multi-ticker load test passes | < 1s for 10 |
| SC-E2E-005 | Auto-reconnection test passes | < 5s recovery |
| SC-E2E-006 | All 5 user stories have test coverage | 100% |

---

## Scope Boundaries

**In Scope**:
- E2E test file: `tests/e2e/test_multi_resolution_dashboard.py`
- Performance timing assertions
- SSE event validation
- Resolution switching
- Multi-ticker view
- Connectivity resilience simulation

**Out of Scope**:
- Visual regression testing (pixel comparison)
- Load testing (covered separately)
- Mobile-specific testing (responsive web only)
- Browser compatibility matrix (Chromium only for E2E)

---

## Technical Design

### Test File Structure

```python
# tests/e2e/test_multi_resolution_dashboard.py

pytestmark = [pytest.mark.e2e, pytest.mark.preprod]

class TestDashboardLoad:
    """US1: Dashboard initial load and display."""
    test_initial_load_within_500ms
    test_skeleton_ui_shown_not_spinner
    test_default_resolution_is_5m

class TestResolutionSwitching:
    """US2: Resolution switching performance."""
    test_switch_completes_within_100ms
    test_all_8_resolutions_available
    test_cached_resolution_loads_instantly

class TestLiveUpdates:
    """US3: Real-time sentiment updates via SSE."""
    test_sse_heartbeat_received
    test_partial_bucket_indicator_visible
    test_chart_updates_on_sentiment_event

class TestHistoricalScrolling:
    """US4: Historical data navigation."""
    test_scroll_left_loads_previous_range
    test_cached_range_loads_instantly
    test_live_data_appends_at_edge

class TestMultiTickerAndConnectivity:
    """US5: Multi-ticker view and resilience."""
    test_10_tickers_load_within_1_second
    test_auto_reconnection_within_5_seconds
    test_fallback_polling_mode_indicator
```

### Performance Measurement

Use Playwright's performance APIs:
- `page.evaluate("performance.now()")` for timing
- `page.on("request")` for network request tracking
- `page.wait_for_selector()` with timeout for load verification

### SSE Testing

Use `api_client.stream_sse()` from existing helpers for SSE validation.

---

## Test Data Strategy

- Use existing synthetic fixtures from `tests/e2e/conftest.py`
- Test tickers: AAPL, TSLA, MSFT, GOOGL (from synthetic config)
- All test data uses TTL-based cleanup (7 days)

---

## Dependencies

- Playwright (pytest-playwright)
- Existing E2E infrastructure in `tests/e2e/`
- Preprod environment with multi-resolution feature deployed
- SSE Lambda with streaming support

---

## Risks & Mitigations

| Risk | Mitigation |
|------|------------|
| Preprod unavailable | Skip tests with informative message |
| SSE timing flaky | Use generous timeouts with retry |
| Network conditions variable | Run in CI with stable network |
