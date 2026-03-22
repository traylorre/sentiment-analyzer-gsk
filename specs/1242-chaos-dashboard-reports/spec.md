# Feature Specification: Chaos Dashboard Report Viewer

**Feature Branch**: `1242-chaos-dashboard-reports`
**Created**: 2026-03-22
**Status**: Draft
**Depends On**: F1237 (external actor architecture, merged), F1239 (execution plans, in progress), F1240 (chaos reports API, in progress)
**Input**: The chaos dashboard (`src/dashboard/chaos.html`) currently shows experiment lifecycle controls (create, start, stop) and a basic history table with status badges. There is no way to browse completed experiment reports, compare results across runs, or visualize trends. The backend already provides `GET /chaos/experiments/{id}/report` (see `get_experiment_report()` in `src/lambdas/dashboard/chaos.py`) which returns structured verdicts (CLEAN, COMPROMISED, DRY_RUN_CLEAN, RECOVERY_INCOMPLETE, INCONCLUSIVE), baseline health, and post-chaos health comparisons. This feature adds report viewing, diffing, and trend visualization to the existing HTMX/Alpine.js dashboard -- purely frontend work consuming existing API contracts.

## Adversarial Review Findings

### Existing Dashboard Inventory

**Current chaos.html** (505 lines):
- Alpine.js `chaosApp()` with state management for experiments
- Scenario library cards (DynamoDB Throttle, Ingestion Failure, Lambda Delay)
- Start experiment form with blast radius slider and duration input
- Active experiments section with real-time status polling (10s interval)
- Experiment history table with status, blast radius, duration columns
- `viewExperiment()` method is a TODO placeholder: `alert('Experiment details coming in Phase 2!')`
- Toast notification system

**Existing API endpoints consumed by dashboard**:
- `GET /chaos/experiments?limit=50` -- list all experiments
- `GET /chaos/experiments/{id}` -- get single experiment (with FIS status enrichment)
- `POST /chaos/experiments` -- create experiment
- `POST /chaos/experiments/{id}/start` -- start experiment
- `POST /chaos/experiments/{id}/stop` -- stop experiment
- `GET /chaos/experiments/{id}/report` -- get structured report with verdict (exists but unused by UI)

**Technology stack** (must not change):
- HTMX for server-driven interactions (self-hosted, `/static/vendor/htmx.min.js`)
- Alpine.js for client-side reactivity (self-hosted, `/static/vendor/alpine.min.js`)
- Tailwind CSS via CDN JIT compiler (`cdn.tailwindcss.com`)
- DaisyUI component library via CDN (`daisyui@4.12.14`)
- No build step, no bundler, no React/Vue/Svelte

### API Response Shapes (from `chaos.py`)

**Report response** (`get_experiment_report()`):
```json
{
  "experiment_id": "uuid",
  "scenario": "dynamodb_throttle",
  "status": "stopped",
  "dry_run": false,
  "duration_seconds": 60,
  "started_at": "2026-03-22T10:00:00Z",
  "stopped_at": "2026-03-22T10:01:00Z",
  "baseline": {
    "captured_at": "...",
    "dependencies": {
      "dynamodb": { "status": "healthy" },
      "ssm": { "status": "healthy" },
      "cloudwatch": { "status": "healthy" },
      "lambda": { "status": "healthy" }
    },
    "all_healthy": true,
    "degraded_services": []
  },
  "post_chaos": {
    "captured_at": "...",
    "recovered": [],
    "new_issues": [],
    "persistent_issues": [],
    "all_healthy": true
  },
  "verdict": "CLEAN",
  "verdict_reason": "System recovered to healthy state after chaos"
}
```

**Experiment list response** (`list_experiments()`):
```json
[
  {
    "experiment_id": "uuid",
    "created_at": "2026-03-22T10:00:00Z",
    "status": "stopped",
    "scenario_type": "dynamodb_throttle",
    "blast_radius": 25,
    "duration_seconds": 60,
    "environment": "preprod",
    "results": {
      "started_at": "...",
      "stopped_at": "...",
      "injection_method": "attach_deny_policy",
      "dry_run": false,
      "baseline": { "..." },
      "post_chaos_health": { "..." }
    }
  }
]
```

### Constraints

1. **No backend changes**: All data comes from existing API endpoints. No new Lambda routes.
2. **No build tooling**: The chaos dashboard is a single HTML file with inline Alpine.js. Adding a bundler or framework is out of scope.
3. **Chart library**: For trend visualization (US4), use a lightweight library that can be loaded via CDN without a build step. Candidates: Chart.js (CDN, 66KB gzipped), uPlot (CDN, 12KB gzipped), or inline SVG generation via Alpine.js.
4. **Mobile responsive**: DaisyUI responsive classes must be used. Tables collapse to cards on small screens.
5. **No new authentication**: Reuse existing `getApiKey()` / `X-API-Key` header pattern.

---

## User Scenarios & Testing *(mandatory)*

### User Story 1 -- Report List View with Filtering (Priority: P1)

Engineers need a dedicated view showing all completed chaos experiment reports with color-coded verdicts, so they can quickly assess system resilience at a glance without clicking into each experiment.

**Why this priority**: This is the entry point for all report viewing. Without a filterable list, engineers must manually look up experiment IDs. The existing history table shows raw experiments, not structured reports with verdicts.

**Independent Test**: Render the report list with mock data (no API needed). Verify filtering and sorting work client-side.

**Acceptance Scenarios**:

1. **Given** the chaos dashboard is open, **When** the user clicks the "Reports" tab/section, **Then** a table/card list appears showing all completed experiments with columns: Date, Scenario, Environment, Verdict (color-coded badge), Duration, Dry Run indicator
2. **Given** the report list is displayed, **When** the user selects a plan name filter (e.g., "dynamodb_throttle"), **Then** only reports for that scenario type are shown
3. **Given** the report list is displayed, **When** the user selects a verdict filter (e.g., "CLEAN"), **Then** only reports with that verdict are shown
4. **Given** the report list is displayed, **When** the user combines plan name and verdict filters, **Then** both filters are applied simultaneously (AND logic)
5. **Given** the report list has results, **When** the user clicks a report row, **Then** the report detail view (US2) opens for that experiment
6. **Given** there are no completed experiments, **When** the report list loads, **Then** an empty state is shown: "No chaos reports yet. Run an experiment to see results here."
7. **Given** reports exist, **When** verdict badges are rendered, **Then** CLEAN is green (`badge-success`), COMPROMISED is red (`badge-error`), DRY_RUN_CLEAN is blue (`badge-info`), RECOVERY_INCOMPLETE is orange (`badge-warning`), INCONCLUSIVE is gray (`badge-ghost`)

---

### User Story 2 -- Report Detail View with Expandable Scenario Sections (Priority: P1)

Engineers need to see the full details of a single chaos report: the scenario configuration, baseline health snapshot, post-chaos health comparison, verdict with reasoning, and per-dependency status.

**Why this priority**: The report detail is the core value of the feature. Engineers need to understand *why* a verdict was reached and which dependencies were affected.

**Independent Test**: Render a single report detail from mock report JSON. Verify all sections expand/collapse.

**Acceptance Scenarios**:

1. **Given** a report is selected from the list (US1), **When** the detail view loads, **Then** it calls `GET /chaos/experiments/{id}/report` and displays the structured response
2. **Given** a report detail is displayed, **Then** the following sections are visible:
   - Header: scenario name, verdict badge (color-coded), environment badge, dates
   - Configuration: blast radius, duration, injection method, dry_run flag
   - Baseline Health: per-dependency status cards (healthy=green, degraded=red)
   - Post-Chaos Health: per-dependency comparison showing recovered, new issues, persistent issues
   - Verdict: large verdict badge with `verdict_reason` text
3. **Given** the baseline health section is displayed, **When** a dependency card shows "degraded", **Then** the error message from `baseline.dependencies.{name}.error` is visible
4. **Given** the post-chaos health section is displayed, **When** there are new issues, **Then** they are highlighted red with a warning explanation
5. **Given** any section, **When** the user clicks the section header, **Then** the section collapses/expands (Alpine.js `x-show` toggle)
6. **Given** the report detail is displayed, **When** the user clicks "Back to Reports", **Then** the list view (US1) is shown with previous filter state preserved
7. **Given** a very long report (many dependencies, long error messages), **When** rendered on desktop, **Then** the layout does not break and content is scrollable
8. **Given** a very long report, **When** rendered on mobile (< 640px), **Then** the layout adapts: sections stack vertically, dependency cards become full-width

---

### User Story 3 -- Side-by-Side Diff View (Priority: P2)

Engineers need to compare two reports from the same scenario to identify regressions or improvements between runs, showing which dependencies changed status.

**Why this priority**: Diff views are only useful once there are multiple reports for the same scenario, which requires active chaos testing adoption. Important but not blocking initial usage.

**Independent Test**: Render diff view with two mock reports. Verify regression/improvement highlighting.

**Acceptance Scenarios**:

1. **Given** the report list is displayed, **When** the user selects exactly two reports (checkboxes), **Then** a "Compare" button becomes enabled
2. **Given** two reports are selected, **When** the user clicks "Compare", **Then** a side-by-side view opens with Report A (older) on the left and Report B (newer) on the right
3. **Given** the diff view is displayed, **When** a dependency that was "healthy" in Report A is "degraded" in Report B, **Then** that row is highlighted red (regression)
4. **Given** the diff view is displayed, **When** a dependency that was "degraded" in Report A is "healthy" in Report B, **Then** that row is highlighted green (improvement)
5. **Given** the diff view is displayed, **When** both reports show the same status for a dependency, **Then** that row has no highlight (unchanged)
6. **Given** the diff view is displayed, **Then** metadata comparison is shown: verdict change, duration difference, blast radius difference
7. **Given** only one report is selected, **When** the user clicks "Compare", **Then** the button remains disabled with tooltip "Select 2 reports to compare"
8. **Given** two reports from different scenarios are selected, **When** the user clicks "Compare", **Then** a warning is shown: "Comparing different scenarios. Results may not be meaningful."
9. **Given** the diff view is displayed on mobile, **Then** the layout switches to stacked (Report A above Report B) instead of side-by-side

---

### User Story 4 -- Trend Charts for Key Metrics Over Time (Priority: P3)

Engineers want to see how recovery time and verdict distribution change over the last N runs of the same plan, to track resilience improvements.

**Why this priority**: Trend analysis requires accumulated history data. It is a "nice to have" for initial release but becomes valuable as chaos testing matures.

**Independent Test**: Render charts with mock array of report summaries. Verify chart renders and axis labels are correct.

**Acceptance Scenarios**:

1. **Given** the report list is filtered to a single scenario, **When** the user clicks "Show Trends", **Then** a chart section appears below the filter bar
2. **Given** the trend chart is displayed, **Then** it shows a line chart of recovery time (stopped_at - started_at) over the last N runs (default N=20)
3. **Given** the trend chart is displayed, **Then** it shows a stacked bar chart of verdict distribution per run (green=CLEAN, red=COMPROMISED, blue=DRY_RUN_CLEAN, etc.)
4. **Given** fewer than 3 data points exist for a scenario, **When** "Show Trends" is clicked, **Then** a message is shown: "Need at least 3 runs to show trends"
5. **Given** the trend chart is displayed, **When** the user hovers over a data point, **Then** a tooltip shows the report date, verdict, and recovery time
6. **Given** the trend section, **When** the user changes N (10/20/50 dropdown), **Then** the chart updates to show the selected number of recent runs
7. **Given** the trend chart on mobile, **Then** charts render at full container width with readable axis labels

---

## Functional Requirements

### FR-001: Report List Rendering
The dashboard shall render a report list section that fetches all experiments via `GET /chaos/experiments?limit=100` and enriches each with report data via `GET /chaos/experiments/{id}/report` for completed/stopped/failed experiments. Results are cached in Alpine.js state to avoid redundant API calls.

### FR-002: Verdict Color Mapping
Verdicts shall be mapped to DaisyUI badge classes: CLEAN -> `badge-success`, COMPROMISED -> `badge-error`, DRY_RUN_CLEAN -> `badge-info`, RECOVERY_INCOMPLETE -> `badge-warning`, INCONCLUSIVE -> `badge-ghost`.

### FR-003: Client-Side Filtering
Report list shall support client-side filtering by scenario type (dropdown) and verdict (dropdown). Filters operate as AND logic. Filter state is preserved in Alpine.js reactive data.

### FR-004: Report Detail Rendering
When a report is selected, the detail view shall call `GET /chaos/experiments/{id}/report` and render all fields from the response in collapsible sections using Alpine.js `x-show` with `x-transition`.

### FR-005: Dependency Health Cards
Baseline and post-chaos health shall render as cards for each dependency (dynamodb, ssm, cloudwatch, lambda). Healthy dependencies use `bg-success/10` tint. Degraded dependencies use `bg-error/10` tint with error detail expandable.

### FR-006: Diff View Rendering
Two-report comparison shall render side-by-side on desktop (each in a `w-1/2` column) and stacked on mobile. Dependency status changes are diff-highlighted: regression=red, improvement=green, unchanged=neutral.

### FR-007: Trend Chart Library Integration
The trend chart shall use Chart.js loaded via CDN (`cdn.jsdelivr.net/npm/chart.js`) with SRI hash. Chart.js is 66KB gzipped and requires no build step. The `<canvas>` element is managed by Alpine.js lifecycle (`x-init` / `x-effect`).

### FR-008: Report Data Caching
Report data fetched from the API shall be cached in Alpine.js state (`reports` Map keyed by experiment_id). Cache is invalidated when the experiments list is refreshed (every 10 seconds for active experiments, manual refresh for history).

### FR-009: Navigation and View State
The dashboard shall support three views managed by Alpine.js state variable `currentView`: `'list'`, `'detail'`, `'diff'`. View transitions use `x-show` with `x-transition`. Browser back button is not required (SPA-like behavior within the single page).

### FR-010: Empty State Handling
When no completed experiments exist, the report list shall show a centered empty state with an explanatory message and a visual indicator (DaisyUI `alert-info`).

---

## Edge Cases

### EC-01: Empty Report List
When `GET /chaos/experiments` returns zero completed experiments, the report section shows an info alert: "No chaos reports yet. Run an experiment to see results here." with a link to scroll to the scenario library section.

### EC-02: Very Long Reports
If an experiment has many dependencies (beyond the standard 4), the dependency cards wrap to the next row using flexbox. Error messages longer than 200 characters are truncated with "..." and expandable on click.

### EC-03: Mobile Layout
On screens < 640px (Tailwind `sm:` breakpoint): tables convert to card layout, diff view switches from side-by-side to stacked, chart width adapts to container, filter dropdowns stack vertically.

### EC-04: API Errors During Report Fetch
If `GET /chaos/experiments/{id}/report` returns a non-200 status for a specific experiment, that experiment shows a `badge-ghost` "Error" badge in the list and the detail view shows a DaisyUI `alert-error` with the HTTP status code.

### EC-05: Concurrent Experiment Updates
If an experiment transitions from "running" to "stopped" while the report list is open, the 10-second auto-refresh picks up the new status. The report becomes fetchable after the status change. No manual refresh required.

### EC-06: Report for Running Experiments
If a user somehow navigates to a report for a still-running experiment, the report API may return incomplete data (no post_chaos_health, no verdict). The detail view renders what is available with a "Experiment still running" banner.

### EC-07: Diff View with Missing Fields
If one of the two compared reports has no `post_chaos` section (e.g., experiment failed before stop), that side of the diff shows "No post-chaos data" placeholder instead of dependency cards.

---

## Success Criteria

### SC-001: Report List Loads
Given 20+ completed experiments, the report list renders within 3 seconds including all report API calls (parallelized via `Promise.all`).

### SC-002: Verdict Accuracy
Every verdict badge color matches the expected DaisyUI class for its verdict string. Verified by visual inspection of all 5 verdict types.

### SC-003: Filter Functionality
Filtering by scenario and verdict correctly reduces the displayed list. Combined filters use AND logic. Clearing filters restores the full list.

### SC-004: Detail View Completeness
Every field from the report API response is rendered somewhere in the detail view. No data is silently dropped.

### SC-005: Diff Highlighting
Regression (healthy -> degraded) rows are red. Improvement (degraded -> healthy) rows are green. Unchanged rows are neutral. Verified with at least 2 test report pairs.

### SC-006: Trend Chart Renders
Chart.js canvas renders without console errors. Line chart shows at least 3 data points. Tooltip shows correct values on hover.

### SC-007: Mobile Responsive
All views (list, detail, diff, trend) render without horizontal overflow on a 375px-wide viewport (iPhone SE size).

### SC-008: No Backend Changes
Zero files changed outside of `src/dashboard/chaos.html` and any new static assets (Chart.js vendor file if self-hosted). No Python, Terraform, or test file changes.

### SC-009: Empty State UX
Empty report list shows a helpful message, not a blank page or broken table.

### SC-010: API Error Resilience
If any report API call fails (network error, 500), the UI degrades gracefully: failed reports show an error badge, other reports still render correctly. No unhandled promise rejections.

---

## Out of Scope

- **Backend API changes**: No new Lambda routes or DynamoDB schema changes.
- **Execution plan management UI**: Covered by F1239.
- **Report generation/storage**: Covered by F1240.
- **PDF/CSV export**: Potential future enhancement.
- **Real-time WebSocket updates**: Polling is sufficient for report viewing.
- **User preferences persistence**: Filter state is session-only (Alpine.js state).
- **Authentication changes**: Reuse existing API key mechanism.
