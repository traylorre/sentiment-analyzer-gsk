# Tasks: Real-Time Metrics Panel

**Feature**: 1247-metrics-panel
**Generated**: 2026-03-27
**Spec**: [spec.md](spec.md) | **Plan**: [plan.md](plan.md)

## Phase 1: Backend — Metrics Configuration and Endpoint

### [ ] T-001: Create metrics_config.py with metric group definitions
**File**: `src/lambdas/dashboard/metrics_config.py` (NEW)
**Depends on**: None
**Requirements**: FR-002, FR-004
**Description**: Define `METRIC_GROUPS` as a list of metric group configurations. Each group has: `title` (str), `queries` (list of dicts with `namespace`, `metric_name`, `dimensions` dict with `{environment}` template placeholders, `stat` (Sum/Average/p95), `label` (str), `color` (hex string for chart hint)). The 4 groups are:
1. "Lambda Invocations & Errors" — `AWS/Lambda` namespace, `Invocations` (Sum) + `Errors` (Sum), dimension `FunctionName: "{environment}-sentiment-ingestion"`
2. "Lambda Duration P95" — `AWS/Lambda` namespace, `Duration` (p95), dimension `FunctionName: "{environment}-sentiment-ingestion"`
3. "DynamoDB Writes & Throttles" — `AWS/DynamoDB` namespace, `ConsumedWriteCapacityUnits` (Sum) + `ThrottledRequests` (Sum), dimension `TableName: "{environment}-sentiment-articles"`
4. "Items Ingested" — `SentimentAnalyzer/Ingestion` custom namespace, `NewItemsIngested` (Sum), no dimensions (custom metrics may use different dimension patterns)

### [ ] T-002: Implement get_metrics() function in chaos.py
**File**: `src/lambdas/dashboard/chaos.py`
**Depends on**: T-001
**Requirements**: FR-001, FR-003, FR-004, FR-005, FR-006
**Description**: Add `get_metrics(start_time, end_time, period, environment)` function. Import `METRIC_GROUPS` from `metrics_config`. Build `MetricDataQueries` list by iterating groups and queries, substituting `{environment}` in dimension values with the `environment` parameter. Each query gets a unique `Id` (e.g., `m0_q0`, `m0_q1`). Call `cloudwatch_client.get_metric_data(MetricDataQueries=queries, StartTime=start_time, EndTime=end_time)`. Parse response: map each `MetricDataResult` back to its group by Id prefix. Return structured dict: `{"groups": [{"title": str, "series": [{"label": str, "color": str, "timestamps": [iso8601], "values": [float]}]}]}`. Wrap CloudWatch call in try/except:
- `ClientError` with code `AccessDeniedException`: return `(403, {"error": "metrics_unavailable", "message": "CloudWatch metrics not available in this environment"})`
- `ClientError` with code `Throttling`: return `(429, {"error": "throttled", "retry_after": 5})` with `Retry-After: 5` header
- Other exceptions: return `(500, {"error": "metrics_error", "message": str(e)})`

### [ ] T-003: Add /chaos/metrics route to handler.py
**File**: `src/lambdas/dashboard/handler.py`
**Depends on**: T-002
**Requirements**: FR-001, FR-003
**Description**: Add route for `GET /chaos/metrics`. Parse query parameters: `start_time` (ISO 8601 string, default: 30 minutes ago), `end_time` (ISO 8601 string, default: now), `period` (int seconds, default: 60). Validate `period` is between 60 and 3600. Pass parsed params + `os.environ.get("ENVIRONMENT", "dev")` to `get_metrics()`. Return JSON response with appropriate status code. Follow the existing routing pattern used by `/chaos/reports` and `/chaos/experiments`.

## Phase 2: Frontend — Chart.js Metrics Panel

### [ ] T-004: Add metrics-related Alpine.js state variables
**File**: `src/dashboard/chaos.html`
**Depends on**: None
**Requirements**: FR-009, FR-010
**Description**: Add to `chaosApp()` data: `metricsData` (null), `metricsLoading` (false), `metricsError` (null — stores `{type: 'unavailable'|'throttled'|'error', message: str, retryAfter: int|null}`), `metricsRefreshTimer` (null — setInterval ID), `metricChartInstances` ({} — map of canvas ID to Chart instance), `metricsLastFetched` (null — Date for display).

### [ ] T-005: Implement loadMetrics() async method
**File**: `src/dashboard/chaos.html`
**Depends on**: T-004
**Requirements**: FR-001, FR-007
**Description**: Implement `async loadMetrics()`. Set `metricsLoading = true`, `metricsError = null`. Fetch from `${this.apiBase}/chaos/metrics` with existing `getApiKey()` auth pattern. Handle responses:
- 200: Set `metricsData` to response JSON, set `metricsLastFetched = new Date()`, call `this.$nextTick(() => this.renderMetricCharts())`
- 403: Set `metricsError = {type: 'unavailable', message: response.message}`
- 429: Set `metricsError = {type: 'throttled', message: 'Rate limited', retryAfter: response.retry_after}`
- Other: Set `metricsError = {type: 'error', message: 'Failed to load metrics'}`
Finally: set `metricsLoading = false`.

### [ ] T-006: Implement renderMetricCharts() and destroyMetricCharts()
**File**: `src/dashboard/chaos.html`
**Depends on**: T-005
**Requirements**: FR-008
**Description**: `destroyMetricCharts()`: iterate `Object.values(metricChartInstances)`, call `.destroy()` on each, reset to `{}`. `renderMetricCharts()`: call `destroyMetricCharts()` first. For each group in `metricsData.groups`, get the canvas element by ID `metrics-chart-{index}`. Create a new `Chart` instance with config:
- `type: 'line'`
- `data.labels`: timestamps from first series, formatted as HH:MM
- `data.datasets`: one per series — `{label, data: values, borderColor: color, backgroundColor: color + '20', tension: 0.1, spanGaps: false, pointRadius: 0}`
- `options.responsive: true`, `options.maintainAspectRatio: false`
- `options.scales.x`: `{type: 'category', title: {display: true, text: 'Time'}}`
- `options.scales.y`: `{beginAtZero: true, title: {display: true, text: group.title}}`
- `options.plugins.legend`: `{display: series.length > 1}`
Store instance in `metricChartInstances['metrics-chart-{index}']`.

### [ ] T-007: Implement auto-refresh start/stop methods
**File**: `src/dashboard/chaos.html`
**Depends on**: T-005
**Requirements**: FR-009, FR-010
**Description**: `startMetricsAutoRefresh()`: if `metricsRefreshTimer` is not null, return (already running). Set `metricsRefreshTimer = setInterval(() => this.loadMetrics(), 30000)`. `stopMetricsAutoRefresh()`: if `metricsRefreshTimer` is null, return. `clearInterval(metricsRefreshTimer)`, set to null. Wire into experiment status watchers: when any experiment transitions to "running", call `startMetricsAutoRefresh()`. When all experiments leave "running" status, call `stopMetricsAutoRefresh()`. Also call `stopMetricsAutoRefresh()` in `navigateTo()` when leaving 'experiments' view, and conditionally restart when returning.

### [ ] T-008: Add loading skeleton and error state HTML
**File**: `src/dashboard/chaos.html`
**Depends on**: T-004
**Requirements**: FR-007
**Description**: Add metrics panel section gated by `x-show="currentView === 'experiments'"`. Structure:
- Section header: "System Metrics" with last-fetched timestamp and manual refresh button
- Loading state (`x-show="metricsLoading && !metricsData"`): 4 DaisyUI skeleton cards in 2x2 grid (`grid grid-cols-1 md:grid-cols-2 gap-4`)
- Error state: unavailable (`x-show="metricsError?.type === 'unavailable'"`): info alert with "Metrics unavailable in this environment" message. Throttled: warning alert with retry countdown. Generic error: error alert with retry button.
- Data state (`x-show="metricsData && !metricsError"`): 2x2 grid of chart containers, each with a `<canvas>` element with ID `metrics-chart-0` through `metrics-chart-3` and fixed height (`h-48`).

### [ ] T-009: Wire metrics panel into view lifecycle
**File**: `src/dashboard/chaos.html`
**Depends on**: T-005, T-007, T-008
**Requirements**: FR-007, FR-009, FR-010
**Description**: In the existing `init()` method or `x-init`, trigger initial `loadMetrics()` when experiments view is active. Modify `navigateTo()` to call `destroyMetricCharts()` and `stopMetricsAutoRefresh()` when leaving experiments view. When returning to experiments view, call `loadMetrics()` and conditionally `startMetricsAutoRefresh()` if any experiment is running. Ensure Chart.js instances are cleaned up when the panel is hidden.

## Phase 3: Tests

### [ ] T-010: Unit test — get_metrics() returns correct structure
**File**: `tests/unit/test_chaos_metrics.py` (NEW)
**Depends on**: T-002
**Requirements**: FR-001, FR-002
**Description**: Use moto `@mock_aws` to mock CloudWatch. Seed metric data for `AWS/Lambda` namespace. Call `get_metrics()` with known time window. Assert response has `groups` array with 4 entries, each containing `title`, `series` array. Assert each series has `label`, `timestamps` (list of ISO strings), `values` (list of floats). Assert Lambda group has 2 series (Invocations + Errors).

### [ ] T-011: Unit test — get_metrics() returns 403 on AccessDeniedException
**File**: `tests/unit/test_chaos_metrics.py`
**Depends on**: T-002
**Requirements**: FR-005
**Description**: Mock CloudWatch client to raise `ClientError` with code `AccessDeniedException`. Call `get_metrics()`. Assert returns `(403, {"error": "metrics_unavailable", ...})`.

### [ ] T-012: Unit test — get_metrics() returns 429 on Throttling
**File**: `tests/unit/test_chaos_metrics.py`
**Depends on**: T-002
**Requirements**: FR-006
**Description**: Mock CloudWatch client to raise `ClientError` with code `Throttling`. Call `get_metrics()`. Assert returns `(429, {"error": "throttled", "retry_after": 5})`.

### [ ] T-013: Unit test — get_metrics() handles empty results
**File**: `tests/unit/test_chaos_metrics.py`
**Depends on**: T-002
**Requirements**: FR-002
**Description**: Mock CloudWatch to return `MetricDataResults` with empty `Values` and `Timestamps` arrays. Call `get_metrics()`. Assert response groups contain series with empty `timestamps` and `values` arrays (not None, not error).

### [ ] T-014: Unit test — metric configuration correctness
**File**: `tests/unit/test_chaos_metrics.py`
**Depends on**: T-001
**Requirements**: FR-002, FR-004
**Description**: Import `METRIC_GROUPS` from `metrics_config`. Assert 4 groups exist. Assert each group has `title`, `queries` list. Assert each query has required keys: `namespace`, `metric_name`, `dimensions`, `stat`, `label`, `color`. Assert dimension values containing `{environment}` are present for Lambda and DynamoDB groups. Assert valid stat values (Sum, Average, p95).

### [ ] T-015: Unit test — environment substitution in dimensions
**File**: `tests/unit/test_chaos_metrics.py`
**Depends on**: T-001, T-002
**Requirements**: FR-004
**Description**: Call dimension substitution logic with `environment="preprod"`. Assert `{environment}-sentiment-ingestion` becomes `preprod-sentiment-ingestion`. Assert `{environment}-sentiment-articles` becomes `preprod-sentiment-articles`. Assert dimensions without templates are unchanged.

## Phase 4: Verification

### [ ] T-016: Verify existing dashboard functionality preserved
**File**: `src/dashboard/chaos.html`
**Depends on**: T-001 through T-015
**Requirements**: FR-007
**Description**: Manually verify: experiment creation works, start/stop works, history table works, report viewer (Feature 1242) works, auto-refresh of experiments works. Default view loads without errors. Metrics panel appears below experiments without breaking layout.

### [ ] T-017: Verify Chart.js lifecycle and mobile responsiveness
**File**: `src/dashboard/chaos.html`
**Depends on**: T-006, T-008
**Requirements**: FR-008
**Description**: Switch between experiments and reports views 5+ times. Verify no console errors about Chart.js canvas reuse. Verify memory in devtools does not grow on each switch. Test at 375px width: charts stack to single column, no horizontal overflow.

## Task Summary

| Phase | Tasks | Estimated Lines |
|-------|-------|-----------------|
| 1. Backend | T-001 to T-003 | ~120 |
| 2. Frontend | T-004 to T-009 | ~250 |
| 3. Tests | T-010 to T-015 | ~150 |
| 4. Verification | T-016 to T-017 | 0 |

**Total**: 17 tasks, ~520 lines across 4 files (1 new module, 2 modified, 1 new test file)
**Critical path**: T-001 -> T-002 -> T-003 (backend must exist before frontend can fetch) -> T-005 -> T-006 -> T-009
