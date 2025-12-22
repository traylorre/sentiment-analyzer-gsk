# Implementation Plan: Multi-Resolution Dashboard E2E Test Suite

## Technical Context

- **Language**: Python 3.13
- **Test Framework**: pytest with pytest-playwright
- **Target Environment**: Preprod (real AWS resources)
- **Parent Spec**: specs/1009-realtime-multi-resolution/spec.md
- **Existing Infrastructure**: tests/e2e/conftest.py (fixtures, api_client)

## Constitution Check

| Gate | Status | Notes |
|------|--------|-------|
| No quick fixes (1.6) | PASS | Full speckit workflow |
| Canonical sources (1.5) | PASS | Cites CS-007, CS-008, parent spec |
| No workspace destruction (1.9) | PASS | Test-only changes |
| GPG signing | PASS | All commits signed |
| Linting | PASS | ruff check required |
| Tests | PASS | TDD approach |

## Phase 0: Research

### RQ-001: How do existing E2E tests use Playwright?

**Question**: What patterns do existing E2E tests use for Playwright?

**Answer**: Found in `tests/e2e/test_client_cache.py`:
- Import `from playwright.sync_api import Page`
- Use `page.goto(DASHBOARD_URL)` for navigation
- Use `page.wait_for_selector()` for element waits
- Use `page.evaluate()` for JavaScript execution
- Use `page.click()` for interactions
- Use `page.locator()` for element queries
- DASHBOARD_URL from `SSE_LAMBDA_URL` env var

### RQ-002: How to measure performance in Playwright?

**Question**: How to measure page load and interaction timing?

**Answer**: Use browser performance APIs via `page.evaluate()`:
```python
load_time = page.evaluate("performance.now()")
page.click("[data-resolution='5m']")
after_click = page.evaluate("performance.now()")
duration = after_click - load_time
```

Also track network requests via `page.on("request")` callback.

### RQ-003: How to test SSE in E2E?

**Question**: How to validate SSE events in Playwright?

**Answer**: Two approaches:
1. Use existing `api_client.stream_sse()` for direct SSE testing
2. Use Playwright to verify dashboard reacts to SSE (status indicator changes)

The dashboard has `#status-indicator` that shows connection state.

### RQ-004: What test data selectors exist in dashboard?

**Question**: What data-testid attributes exist in dashboard HTML?

**Answer**: From `src/dashboard/index.html` and `app.js`:
- `#status-indicator` - Connection status
- `#resolution-selector` - Resolution dropdown
- `[data-resolution='Xm']` - Resolution buttons
- `#timeseries-chart` - Main chart element
- Status classes: `.status-dot.streaming`, `.status-dot.polling`, `.status-dot.offline`

### RQ-005: What resolutions are supported?

**Question**: What 8 resolutions must we test?

**Answer**: From parent spec FR-002: 1m, 5m, 10m, 1h, 3h, 6h, 12h, 24h

## Phase 1: Design

### Test File Location

`tests/e2e/test_multi_resolution_dashboard.py`

### Test Classes and Methods

```python
pytestmark = [pytest.mark.e2e, pytest.mark.preprod]

class TestDashboardLoad:
    """US1: Dashboard initial load and display."""
    def test_initial_load_within_500ms(page: Page)
    def test_skeleton_ui_shown_not_spinner(page: Page)
    def test_default_resolution_is_5m(page: Page)

class TestResolutionSwitching:
    """US2: Resolution switching performance."""
    def test_switch_completes_within_100ms(page: Page)
    def test_all_8_resolutions_available(page: Page)
    def test_cached_resolution_loads_instantly(page: Page)

class TestLiveUpdates:
    """US3: Real-time sentiment updates via SSE."""
    def test_sse_connection_established(page: Page)
    def test_partial_bucket_indicator_visible(page: Page)
    def test_heartbeat_received_within_3s(page: Page)

class TestHistoricalScrolling:
    """US4: Historical data navigation."""
    def test_scroll_left_loads_previous_range(page: Page)
    def test_cached_range_loads_instantly(page: Page)
    def test_live_data_appends_at_edge(page: Page)

class TestMultiTickerConnectivity:
    """US5: Multi-ticker view and resilience."""
    def test_10_tickers_load_within_1_second(page: Page)
    def test_auto_reconnection_indicator(page: Page)
    def test_fallback_polling_mode_indicator(page: Page)
```

### Fixture Dependencies

```python
@pytest.fixture
def dashboard_page(page: Page) -> Page:
    """Navigate to dashboard and wait for load."""
    page.goto(DASHBOARD_URL)
    page.wait_for_selector("#status-indicator", timeout=10000)
    return page

@pytest.fixture
def timeseries_ready_page(dashboard_page: Page) -> Page:
    """Wait for timeseries module to initialize."""
    dashboard_page.wait_for_function(
        "typeof timeseriesManager !== 'undefined'",
        timeout=5000,
    )
    return dashboard_page
```

### Performance Measurement Helper

```python
def measure_action_time(page: Page, action_fn: callable) -> float:
    """Measure time for an action using performance.now()."""
    start = page.evaluate("performance.now()")
    action_fn()
    end = page.evaluate("performance.now()")
    return end - start
```

## Implementation Order

1. Create test file with imports and fixtures
2. Implement TestDashboardLoad (3 tests)
3. Implement TestResolutionSwitching (3 tests)
4. Implement TestLiveUpdates (3 tests)
5. Implement TestHistoricalScrolling (3 tests)
6. Implement TestMultiTickerConnectivity (3 tests)
7. Run pytest --collect-only to verify
8. Run ruff check

## Dependencies

- pytest-playwright (already in dev dependencies)
- SSE_LAMBDA_URL or DASHBOARD_URL environment variable
- Preprod environment with multi-resolution feature deployed

## Risk Mitigation

- Use `pytest.mark.skipif` if playwright not available
- Use generous timeouts (10s) for initial load
- Use smaller timeouts (100ms) for cached operations
- Skip tests gracefully if preprod unavailable
