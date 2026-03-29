# Feature Specification: Real-Time Metrics Panel

**Feature Branch**: `1247-metrics-panel`
**Created**: 2026-03-27
**Status**: Draft
**Input**: "Feature 1247: Embed CloudWatch metrics visualization in chaos dashboard so operators observe system behavior during chaos injection without switching to AWS Console"

## User Scenarios & Testing _(mandatory)_

### User Story 1 - Observe Lambda Health During Chaos Injection (Priority: P1)

During a chaos experiment, the operator wants to see Lambda invocation counts, error rates, and P95 duration in the chaos dashboard so they can confirm that injected faults are having the expected effect (e.g., errors spike after ingestion_failure injection) without opening the AWS Console in a separate tab.

**Why this priority**: This is the core value proposition. The operator currently must alt-tab to CloudWatch Console during gameday execution, breaking flow and adding cognitive overhead. Lambda metrics are the primary signal for all chaos scenarios (ingestion_failure, cold_start, lambda_throttle).

**Independent Test**: Can be tested by loading the chaos dashboard with an active experiment, verifying that 4 metric charts render with data from the last 30 minutes, and confirming the data matches what CloudWatch Console shows for the same time window.

**Acceptance Scenarios**:

1. **Given** the operator is viewing the experiments section, **When** the metrics panel loads, **Then** 4 charts appear in a 2x2 grid: Lambda Invocations+Errors, Lambda Duration P95, DynamoDB Writes+Throttles, Items Ingested.
2. **Given** a chaos experiment is running, **When** the experiment causes Lambda errors, **Then** the Errors line in chart 1 visibly increases within 60 seconds.
3. **Given** the metrics panel is visible, **When** data loads successfully, **Then** each chart has a title, y-axis label, time-based x-axis (last 30 minutes), and a legend for multi-series charts.
4. **Given** no experiments are running, **When** the operator views the experiments section, **Then** the metrics panel still shows recent metric history (last 30 minutes) as passive monitoring.

---

### User Story 2 - Auto-Refresh Metrics During Active Experiments (Priority: P1)

When a chaos experiment is actively running, the operator wants the metrics panel to automatically refresh every 30 seconds so the charts stay current without manual intervention. When no experiment is running, auto-refresh should stop to avoid unnecessary CloudWatch API calls.

**Why this priority**: Equally critical as chart rendering. Stale metrics during active injection defeat the purpose of real-time observation. The 30-second interval balances freshness against CloudWatch API costs ($0.01/metric/request).

**Independent Test**: Can be tested by starting an experiment and verifying that chart data updates every 30 seconds (observable via network tab or chart animation), then stopping the experiment and verifying that polling stops.

**Acceptance Scenarios**:

1. **Given** an experiment with status "running", **When** 30 seconds elapse, **Then** the metrics panel fetches fresh data and updates all 4 charts.
2. **Given** an experiment is stopped, **When** the status changes to "completed" or "restored", **Then** auto-refresh stops within one polling cycle.
3. **Given** auto-refresh is active, **When** the operator switches to a different view (e.g., reports), **Then** auto-refresh pauses. When they return to experiments view, auto-refresh resumes.
4. **Given** the operator manually triggers a refresh (refresh button), **When** clicked, **Then** data updates immediately and the auto-refresh timer resets.

---

### User Story 3 - Handle Metrics Unavailability Gracefully (Priority: P2)

When CloudWatch metrics are unavailable (API throttling, missing metrics for new functions, production environment where chaos permissions are disabled), the operator wants clear feedback instead of broken charts or silent failures.

**Why this priority**: Without graceful degradation, a CloudWatch API error during gameday would distract the operator from the actual chaos experiment. The metrics panel must be additive — its failure should never block gameday execution.

**Independent Test**: Can be tested by simulating a 403 response from the metrics endpoint and verifying the panel shows an error state, or by testing with a function that has no CloudWatch data and verifying gaps are handled.

**Acceptance Scenarios**:

1. **Given** the metrics endpoint returns 403 (production environment, no chaos permissions), **When** the panel attempts to load, **Then** a message displays "Metrics unavailable in this environment" instead of charts.
2. **Given** the metrics endpoint returns 500 or times out, **When** the panel attempts to load, **Then** an error banner displays with a retry button. Previously loaded data remains visible.
3. **Given** CloudWatch returns sparse data (gaps in time series), **When** the chart renders, **Then** gaps are shown as discontinuities in the line (not interpolated to zero).
4. **Given** a Lambda function was just deployed and has no metrics yet, **When** the panel loads, **Then** empty charts display with a "No data for this period" label.

---

### User Story 4 - View Metrics for Specific Experiments (Priority: P3)

The operator wants to align metric time windows with specific experiment start/end times so they can see the "before, during, and after" of a chaos injection in one view.

**Why this priority**: Lower priority because the default 30-minute window covers most experiment durations (2-5 minutes injection + recovery). This story adds precision for longer-running experiments or post-hoc analysis.

**Independent Test**: Can be tested by selecting a completed experiment from history and verifying that the metrics panel shifts its time window to cover that experiment's start-to-end period plus 5-minute padding on each side.

**Acceptance Scenarios**:

1. **Given** a completed experiment with known start/end times, **When** the operator clicks "View Metrics" on that experiment, **Then** the chart time window adjusts to `[start - 5min, end + 5min]`.
2. **Given** the adjusted time window, **When** charts render, **Then** vertical annotation lines mark experiment start and end times.
3. **Given** the operator is viewing experiment-aligned metrics, **When** they click "Reset to live", **Then** charts return to the default rolling 30-minute window.

---

### Edge Cases

- What happens when CloudWatch API throttles the dashboard Lambda?
  - The `/chaos/metrics` endpoint returns 429 with a `Retry-After` header. The frontend waits the specified duration before the next auto-refresh cycle. Previously fetched data remains displayed. A subtle "Rate limited, retrying in Xs" indicator shows.
- What happens when metrics are queried for a function that doesn't exist (wrong dimension)?
  - CloudWatch returns empty `MetricDataResults`. The chart shows "No data" rather than erroring. The endpoint logs a warning but does not fail.
- What happens in production where `dashboard_chaos` IAM policy is not attached?
  - The `cloudwatch:GetMetricData` call raises AccessDeniedException. The endpoint catches this and returns 403 with a structured error. The frontend shows the "Metrics unavailable" state.
- What happens when Chart.js instances accumulate from repeated view switches?
  - Each chart instance is destroyed via `chart.destroy()` before recreation. The `destroyMetricCharts()` method is called on view switch and before each refresh cycle.
- What happens when the browser tab is backgrounded during auto-refresh?
  - `setInterval` continues in backgrounded tabs (throttled by browsers to ~1/minute). This is acceptable — we don't need sub-30s precision for backgrounded tabs. The `document.hidden` API could be used to pause, but the complexity isn't justified for the low API cost.

## Requirements _(mandatory)_

### Functional Requirements

- **FR-001**: Dashboard Lambda MUST expose a `GET /chaos/metrics` endpoint that returns time-series data from CloudWatch `GetMetricData` API.
- **FR-002**: The metrics endpoint MUST query 4 metric groups: (1) Lambda Invocations + Errors, (2) Lambda Duration P95, (3) DynamoDB ConsumedWriteCapacityUnits + ThrottledRequests, (4) Custom SentimentAnalyzer/Ingestion NewItemsIngested.
- **FR-003**: The metrics endpoint MUST accept query parameters: `start_time` (ISO 8601, default: now - 30min), `end_time` (ISO 8601, default: now), `period` (seconds, default: 60).
- **FR-004**: The metrics endpoint MUST use environment-prefixed Lambda function names as dimensions (e.g., `${environment}-sentiment-ingestion`).
- **FR-005**: The metrics endpoint MUST return 403 with structured error when CloudWatch permissions are unavailable (production environment).
- **FR-006**: The metrics endpoint MUST handle CloudWatch throttling by returning 429 with `Retry-After` header.
- **FR-007**: Dashboard MUST display a metrics panel below the active experiments section when `currentView === 'experiments'`.
- **FR-008**: Dashboard MUST render 4 Chart.js time-series line charts in a responsive 2x2 grid (2 columns on desktop, 1 column on mobile < 640px).
- **FR-009**: Dashboard MUST auto-refresh metrics every 30 seconds when any experiment has status "running".
- **FR-010**: Dashboard MUST stop auto-refresh when no experiments are running or when the operator navigates away from the experiments view.

### Key Entities

- **MetricQuery**: Configuration for a single CloudWatch metric — namespace, metric name, dimensions, stat (Average, Sum, p95), label.
- **MetricGroup**: Collection of MetricQuery objects rendered in a single chart — title, queries (1-2 per chart), chart type (line).
- **MetricsResponse**: Structured response from `/chaos/metrics` — groups array, each containing label, timestamps array, and values array per query.

## Success Criteria _(mandatory)_

### Measurable Outcomes

- **SC-001**: All 4 metric charts render with real CloudWatch data within 5 seconds of panel becoming visible.
- **SC-002**: Auto-refresh updates charts every 30 seconds during active experiments (tolerance: +/- 5 seconds).
- **SC-003**: CloudWatch API cost during a 2-hour gameday is under $1.00 (4 metrics x 240 requests = 960 GetMetricData calls x $0.01 = $0.96 worst case, actual lower due to batching).
- **SC-004**: Metrics endpoint returns structured 403 in production environment without crashing the dashboard Lambda.
- **SC-005**: Chart.js memory usage does not grow unbounded — `destroy()` is called before every chart recreation.

## Assumptions

- Feature 1240 (Chaos Reports Backend) extends the dashboard Lambda handler (`src/lambdas/dashboard/handler.py`) — the metrics endpoint follows the same routing pattern.
- The dashboard Lambda already has `cloudwatch:GetMetricStatistics` and `cloudwatch:GetMetricData` in the `dashboard_chaos` IAM policy (non-prod only).
- Chart.js 4.4.0 is already loaded in `chaos.html` via CDN with SRI hash (added by Feature 1242).
- Alpine.js manages all client-side state — the metrics panel integrates into the existing `chaosApp()` data model.
- Lambda function names follow the pattern `${var.environment}-sentiment-<function>` (e.g., `dev-sentiment-ingestion`, `preprod-sentiment-analysis`).
- DynamoDB table name follows `${var.environment}-sentiment-articles` for the write capacity metric dimension.
- The custom `SentimentAnalyzer/Ingestion` namespace metrics are emitted by the ingestion Lambda and already exist in CloudWatch.

## Scope Boundaries

### In Scope
- Backend: `/chaos/metrics` endpoint querying CloudWatch GetMetricData
- Backend: Metric configuration (namespaces, dimensions, stats)
- Backend: Error handling (permissions, throttling, missing data)
- Frontend: 4 Chart.js time-series charts in 2x2 grid
- Frontend: Auto-refresh during active experiments
- Frontend: Loading skeleton and error states
- Frontend: Chart.js instance lifecycle management (destroy/recreate)
- Unit tests for the metrics endpoint

### Out of Scope
- Custom CloudWatch dashboards or alarms
- Metric alerting or threshold configuration in the UI
- Historical metric storage (CloudWatch retains natively)
- New IAM permissions (already exist in `dashboard_chaos` policy)
- New CloudWatch metric emission (metrics already exist)
- Terraform changes (no new infrastructure needed)

## Dependencies

- **Feature 1240** (Chaos Reports Backend): UPSTREAM — provides the handler routing pattern and dashboard Lambda structure that this feature extends.
- **Feature 1242** (Dashboard Report Viewer): UPSTREAM — adds Chart.js 4.4.0 CDN to chaos.html, provides Alpine.js state patterns.
- **Feature 1243** (First Gameday): DOWNSTREAM — uses the metrics panel during gameday execution for real-time observation.
