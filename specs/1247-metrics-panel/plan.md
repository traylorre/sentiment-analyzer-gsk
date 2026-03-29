# Implementation Plan: Real-Time Metrics Panel

**Branch**: `1247-metrics-panel` | **Date**: 2026-03-27 | **Spec**: [spec.md](spec.md)
**Input**: Feature specification from `/specs/1247-metrics-panel/spec.md`

## Summary

Add a CloudWatch metrics visualization panel to the chaos dashboard: a Python backend endpoint (`/chaos/metrics`) that queries CloudWatch `GetMetricData` API, and a frontend panel with 4 Chart.js time-series charts that auto-refresh during active experiments. Backend adds ~120 lines to the dashboard Lambda. Frontend adds ~250 lines to chaos.html. Zero infrastructure changes — uses existing IAM permissions.

## Technical Context

**Language/Version**: Python 3.13 (backend endpoint), JavaScript/Alpine.js (frontend charts)
**Primary Dependencies**: boto3 CloudWatch client (existing), Chart.js 4.4.0 (existing in chaos.html from Feature 1242), Alpine.js (existing)
**Storage**: N/A (reads from CloudWatch, no persistence)
**Testing**: pytest with moto mocks for CloudWatch API calls (unit)
**Target Platform**: AWS Lambda (existing dashboard Lambda), Browser (chaos.html)
**Project Type**: Dual-layer enhancement (backend endpoint + frontend panel)
**Performance Goals**: Metrics response < 3 seconds, chart render < 2 seconds
**Constraints**: CloudWatch GetMetricData costs $0.01/metric/request; 4 metrics batched = 1 API call; ~$0.50/hour during active gameday
**Scale/Scope**: 4 metric groups, 30-minute window, 60-second period = 30 data points per metric

## Constitution Check

| Gate | Status | Notes |
|------|--------|-------|
| Amendment 1.6 (No Quick Fixes) | PASS | Full speckit workflow |
| Amendment 1.8 (Managed Policies) | N/A | No new IAM policies — uses existing `dashboard_chaos` |
| Amendment 1.12 (Mandatory Workflow) | PASS | specify -> plan -> tasks -> implement |
| Amendment 1.15 (No Fallback Config) | PASS | Environment name from `os.environ["ENVIRONMENT"]` |
| Cost Sensitivity | PASS | $0.01/request, batched to 1 call per refresh. ~$0.50/hr during gameday. Non-prod only. |
| prevent_destroy | N/A | No new stateful resources |

## Project Structure

### Source Code (in target repo: ../sentiment-analyzer-gsk/)

```text
src/lambdas/dashboard/
├── chaos.py                # MODIFY: Add get_metrics() function (~80 lines)
├── handler.py              # MODIFY: Add /chaos/metrics route (~10 lines)
└── metrics_config.py       # NEW: Metric group definitions (~40 lines)

src/dashboard/
└── chaos.html              # MODIFY: Add metrics panel UI (~250 lines)

tests/unit/
└── test_chaos_metrics.py   # NEW: Unit tests for metrics endpoint (~150 lines)
```

**Structure Decision**: Metric configuration is extracted to `metrics_config.py` rather than inlined in `chaos.py` because (1) it will grow as new metrics are added, (2) it's pure data that benefits from being readable without surrounding logic, and (3) tests can import it directly to verify configuration correctness.

## Adversarial Review (Self-Resolved)

### Cost Analysis

**Concern**: CloudWatch GetMetricData costs $0.01 per metric requested.
**Resolution**: All 4 metric groups are batched into a single `GetMetricData` API call using `MetricDataQueries` (supports up to 500 queries per call). With auto-refresh every 30 seconds, that's 120 calls/hour x $0.01 = $1.20/hour worst case. Actual cost is lower because GetMetricData charges per unique metric, and we query 6 unique metrics = $0.06 per call = $7.20/hour. However, gamedays run 1-2 hours and only in non-prod. Acceptable.

**Revised estimate**: GetMetricData pricing is $0.01 per 1,000 metrics requested (not per metric). With 6 metrics per call, 120 calls/hour = 720 metrics/hour = $0.0072/hour. Negligible.

### Permissions in Production

**Concern**: The `dashboard_chaos` IAM policy is only attached in non-prod environments.
**Resolution**: The `get_metrics()` function wraps the CloudWatch call in a try/except for `ClientError` with code `AccessDeniedException`. Returns a 403 response with `{"error": "metrics_unavailable", "message": "CloudWatch metrics are not available in this environment"}`. The frontend renders a clean "Metrics unavailable" state.

### CloudWatch Rate Limiting

**Concern**: CloudWatch `GetMetricData` has TPS limits (50 TPS default for the account).
**Resolution**: One call every 30 seconds per active dashboard session. Even with 10 concurrent operators, that's 0.33 TPS. Not a concern. The endpoint still handles 429/throttling by catching `Throttling` error code and returning HTTP 429 with `Retry-After: 5`.

### Chart.js Memory Leaks

**Concern**: Creating new Chart instances without destroying old ones leaks memory.
**Resolution**: A `destroyMetricCharts()` method is called before every `renderMetricCharts()` invocation. It iterates `metricChartInstances` (an object mapping chart IDs to Chart instances) and calls `.destroy()` on each. Also called when navigating away from experiments view.

### Dimension Mismatch

**Concern**: Lambda function names include environment prefix. Hardcoded dimensions would break across environments.
**Resolution**: The `metrics_config.py` module defines metric groups with dimension templates. The `get_metrics()` function substitutes `{environment}` at runtime from `os.environ["ENVIRONMENT"]`. Example: `FunctionName: "{environment}-sentiment-ingestion"` becomes `FunctionName: "preprod-sentiment-ingestion"`.

### Sparse Data

**Concern**: CloudWatch may return fewer data points than expected for low-traffic functions.
**Resolution**: Chart.js `spanGaps: false` setting renders discontinuities as gaps in the line rather than interpolating to zero. The frontend does NOT zero-fill missing timestamps — this would create misleading flat-line artifacts.

## Implementation Phases

### Phase 1: Backend — Metrics Configuration and Endpoint (~120 lines, ~1.5 hours)

- Create `metrics_config.py` with `METRIC_GROUPS` constant defining all 4 metric groups
- Each group specifies: namespace, metric name, dimensions (with `{environment}` template), stat, label, color hint
- Implement `get_metrics(start_time, end_time, period, environment)` in `chaos.py`
- Build `GetMetricData` request from `METRIC_GROUPS`, substituting environment into dimensions
- Parse `GetMetricData` response into structured format: `{groups: [{label, series: [{label, timestamps, values}]}]}`
- Handle errors: `AccessDeniedException` -> 403, `Throttling` -> 429 with Retry-After, general error -> 500
- Add route `GET /chaos/metrics` in `handler.py` with query param parsing

### Phase 2: Frontend — Chart.js Metrics Panel (~250 lines, ~2 hours)

- Add Alpine.js state: `metricsData`, `metricsLoading`, `metricsError`, `metricsRefreshInterval`, `metricChartInstances`
- Implement `loadMetrics()` async method — fetch from `/chaos/metrics`, handle 403/429/500
- Implement `renderMetricCharts()` — destroy existing charts, create 4 Chart.js instances with time-series config
- Implement `destroyMetricCharts()` — iterate and destroy all chart instances
- Implement `startMetricsAutoRefresh()` / `stopMetricsAutoRefresh()` — setInterval/clearInterval tied to experiment status
- Add loading skeleton (4 DaisyUI skeleton cards in 2x2 grid)
- Add error state (banner with retry button)
- Add "Metrics unavailable" state for 403 responses
- Add metrics panel HTML section below experiments, gated by `currentView === 'experiments'`
- Wire auto-refresh start/stop to experiment status changes
- Call `destroyMetricCharts()` in `navigateTo()` when leaving experiments view

### Phase 3: Tests (~150 lines, ~1 hour)

- Unit test: `get_metrics()` returns correct structure with mocked CloudWatch response
- Unit test: `get_metrics()` returns 403 on AccessDeniedException
- Unit test: `get_metrics()` returns 429 on Throttling with Retry-After header
- Unit test: `get_metrics()` handles empty MetricDataResults gracefully
- Unit test: metric configuration has correct namespaces and dimensions
- Unit test: environment substitution in dimensions works correctly

### Phase 4: Verification (~30 min)

- Verify existing chaos dashboard functionality preserved (experiment lifecycle, report viewer)
- Verify Chart.js instances are properly destroyed on view switch
- Verify auto-refresh starts/stops with experiment status
- Mobile responsiveness at 375px (charts stack to single column)
