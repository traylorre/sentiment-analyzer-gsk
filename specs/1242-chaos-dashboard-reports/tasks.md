# Tasks: Chaos Dashboard Report Viewer

**Feature Branch**: `1242-chaos-dashboard-reports`
**Created**: 2026-03-22

## Phase 1: Report List View

### T-001: Add report-related Alpine.js state and data loading
- [ ] Add `reports: {}` (Map of experiment_id -> report JSON) to `chaosApp()` return
- [ ] Add `currentView: 'list'` (values: 'list', 'detail', 'diff')
- [ ] Add `selectedReportId: null`
- [ ] Add `selectedForDiff: []` (array of max 2 experiment_ids)
- [ ] Add `filterScenario: ''`
- [ ] Add `filterVerdict: ''`
- [ ] Add `loadingReports: false`
- [ ] Add `showTrends: false`
- [ ] Add `trendLimit: 20`
- File: `src/dashboard/chaos.html`
- Acceptance: FR-001, FR-008; Alpine.js app initializes without console errors

### T-002: Implement loadReports() method
- [ ] Add `loadReports()` async method that:
  - Filters `this.experiments` to those with status in ['completed', 'stopped', 'failed']
  - Uses `Promise.all()` to call `GET /chaos/experiments/{id}/report` for each
  - Stores successful responses in `this.reports[experiment_id]`
  - Handles individual fetch failures gracefully (store `{ error: true, status: code }`)
  - Sets `loadingReports = false` when complete
- [ ] Call `loadReports()` at the end of `loadExperiments()` (after experiments are loaded)
- File: `src/dashboard/chaos.html`
- Acceptance: FR-001, FR-008, SC-001; reports load within 3 seconds for 20 experiments

### T-003: Add verdictClass() and verdictLabel() helpers
- [ ] Add `verdictClass(verdict)` method:
  - `'CLEAN'` -> `'badge-success'`
  - `'COMPROMISED'` -> `'badge-error'`
  - `'DRY_RUN_CLEAN'` -> `'badge-info'`
  - `'RECOVERY_INCOMPLETE'` -> `'badge-warning'`
  - `'INCONCLUSIVE'` -> `'badge-ghost'`
  - default -> `'badge-ghost'`
- [ ] Add `verdictLabel(verdict)` method that returns human-readable labels:
  - `'CLEAN'` -> `'Clean'`
  - `'COMPROMISED'` -> `'Compromised'`
  - `'DRY_RUN_CLEAN'` -> `'Dry Run'`
  - `'RECOVERY_INCOMPLETE'` -> `'Recovery Incomplete'`
  - `'INCONCLUSIVE'` -> `'Inconclusive'`
- File: `src/dashboard/chaos.html`
- Acceptance: FR-002, SC-002

### T-004: Add filteredReports computed getter
- [ ] Add `get filteredReports()` that:
  - Combines `this.experiments` (for metadata) with `this.reports` (for verdicts)
  - Filters by `this.filterScenario` if non-empty
  - Filters by `this.filterVerdict` if non-empty
  - Only includes experiments that have status in ['completed', 'stopped', 'failed']
  - Sorts by `created_at` descending (most recent first)
  - Returns array of `{ experiment, report }` objects
- File: `src/dashboard/chaos.html`
- Acceptance: FR-003, SC-003

### T-005: Render report list section HTML
- [ ] Add new `<section>` after existing "Experiment History" section
- [ ] Add section header: "Chaos Reports" with report count badge
- [ ] Add filter bar with:
  - Scenario dropdown (`<select>` with DaisyUI `select select-bordered`) bound to `filterScenario`
  - Verdict dropdown bound to `filterVerdict`
  - "Clear Filters" button
  - "Show Trends" button (visible when `filterScenario` is set)
- [ ] Add report table/cards using `x-for="item in filteredReports"`:
  - Date column: `formatTime(item.experiment.created_at)`
  - Scenario column: `scenarioNames[item.experiment.scenario_type]`
  - Environment badge: `item.experiment.environment`
  - Verdict badge: `x-text="verdictLabel(item.report?.verdict)"` with `:class="verdictClass(item.report?.verdict)"`
  - Duration: `item.experiment.duration_seconds + 's'`
  - Dry Run indicator: `x-show="item.report?.dry_run"` badge
  - Click handler: `@click="viewReport(item.experiment.experiment_id)"`
  - Diff checkbox: `<input type="checkbox">` bound to `selectedForDiff` array (max 2)
- [ ] Add "Compare" button: `@click="compareReports()"` with `:disabled="selectedForDiff.length !== 2"`
- [ ] Add loading skeleton (shown when `loadingReports`)
- [ ] Add empty state (shown when `filteredReports.length === 0 && !loadingReports`)
- File: `src/dashboard/chaos.html`
- Acceptance: US1 scenarios 1-7, FR-010, EC-01, SC-009

### T-006: Implement toggleDiffSelection() method
- [ ] Add `toggleDiffSelection(experimentId)` method:
  - If already in `selectedForDiff`, remove it
  - If not in array and array length < 2, add it
  - If not in array and array length >= 2, show toast "Maximum 2 reports for comparison"
- File: `src/dashboard/chaos.html`
- Acceptance: US3 scenario 1

## Phase 2: Report Detail View

### T-007: Implement viewReport() method
- [ ] Add `viewReport(experimentId)` async method:
  - Sets `selectedReportId = experimentId`
  - Sets `currentView = 'detail'`
  - If not in `this.reports`, fetches `GET /chaos/experiments/{id}/report`
  - On fetch error, stores error state in reports cache
- File: `src/dashboard/chaos.html`
- Acceptance: FR-004, FR-009

### T-008: Add collapsible section state and toggle
- [ ] Add `openSections: { config: true, baseline: true, postChaos: true, verdict: true }` to state
- [ ] Add `toggleSection(name)` method: `this.openSections[name] = !this.openSections[name]`
- File: `src/dashboard/chaos.html`
- Acceptance: US2 scenario 5

### T-009: Render report detail view HTML
- [ ] Add detail view container: `x-show="currentView === 'detail'"` with `x-transition`
- [ ] Add back button: `@click="currentView = 'list'"` with left arrow icon
- [ ] Add header card:
  - Scenario name (large text)
  - Verdict badge (large, color-coded)
  - Environment badge
  - Dates: started_at, stopped_at
  - Status badge
- [ ] Add Configuration section (collapsible):
  - Blast radius, duration, injection method
  - Dry run indicator
  - Gate state
- [ ] Add Baseline Health section (collapsible):
  - Grid of dependency cards (`grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4`)
  - Each card: dependency name, status badge (healthy=success, degraded=error)
  - Expandable error detail for degraded dependencies
  - `all_healthy` summary indicator
  - `degraded_services` list if any
- [ ] Add Post-Chaos Health section (collapsible):
  - Recovered list (green badges)
  - New issues list (red badges with warning)
  - Persistent issues list (orange badges with explanation)
  - Warning text from `post_chaos.warning` if present
- [ ] Add Verdict section (collapsible):
  - Large verdict badge (3x size)
  - `verdict_reason` text in a DaisyUI `alert` matching verdict color
- [ ] Add error state: if `this.reports[selectedReportId]?.error`, show `alert-error` with status code
- File: `src/dashboard/chaos.html`
- Acceptance: US2 scenarios 1-8, FR-005, SC-004, EC-02, EC-03, EC-04, EC-06

### T-010: Handle running experiment report edge case
- [ ] In detail view, if experiment status is 'running', show `alert-warning` banner: "Experiment still running. Report data may be incomplete."
- [ ] Render available fields (baseline, configuration) and show "Pending" placeholders for post-chaos and verdict sections
- File: `src/dashboard/chaos.html`
- Acceptance: EC-06

## Phase 3: Diff View

### T-011: Implement compareReports() method
- [ ] Add `compareReports()` method:
  - Validates `selectedForDiff.length === 2`
  - Sorts by `created_at` (older first = left/Report A, newer = right/Report B)
  - Sets `currentView = 'diff'`
- [ ] Add `get diffReportA()` computed: returns report for `selectedForDiff[0]`
- [ ] Add `get diffReportB()` computed: returns report for `selectedForDiff[1]`
- [ ] Add `get isDiffCrossScenario()` computed: returns true if scenario types differ
- File: `src/dashboard/chaos.html`
- Acceptance: US3 scenarios 1-2

### T-012: Implement diffDependencyStatus() helper
- [ ] Add `diffDependencyStatus(depName)` method:
  - Gets dependency status from Report A baseline and Report B baseline
  - Returns object: `{ statusA, statusB, change }` where change is:
    - `'regression'` if A=healthy, B=degraded
    - `'improvement'` if A=degraded, B=healthy
    - `'unchanged'` if both same
    - `'unknown'` if either report missing dependency data
- [ ] Add `diffRowClass(change)`:
  - `'regression'` -> `'bg-error/10 border-l-4 border-error'`
  - `'improvement'` -> `'bg-success/10 border-l-4 border-success'`
  - `'unchanged'` -> `''`
  - `'unknown'` -> `'opacity-50'`
- File: `src/dashboard/chaos.html`
- Acceptance: US3 scenarios 3-5, SC-005

### T-013: Render diff view HTML
- [ ] Add diff view container: `x-show="currentView === 'diff'"` with `x-transition`
- [ ] Add back button: `@click="currentView = 'list'; selectedForDiff = []"`
- [ ] Add cross-scenario warning: `x-show="isDiffCrossScenario"` DaisyUI `alert-warning`
- [ ] Add metadata comparison row:
  - Verdict A vs Verdict B (with arrow indicator)
  - Duration A vs Duration B (show delta)
  - Blast radius A vs Blast radius B
- [ ] Add two-column grid (`grid md:grid-cols-2 gap-4`):
  - Left column: Report A header + dependency cards
  - Right column: Report B header + dependency cards
- [ ] For each dependency (union of both reports' dependencies):
  - Render row with dependency name, status A, status B
  - Apply `diffRowClass()` for color coding
- [ ] Add stacked layout for mobile: `grid-cols-1` default, `md:grid-cols-2`
- [ ] Handle missing post_chaos data: show "No post-chaos data" placeholder
- File: `src/dashboard/chaos.html`
- Acceptance: US3 scenarios 2-9, FR-006, EC-07

## Phase 4: Trend Charts

### T-014: Add Chart.js CDN dependency
- [ ] Add `<script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.7/dist/chart.umd.js" integrity="sha384-..." crossorigin="anonymous"></script>` to `<head>`
- [ ] Verify Chart.js loads without console errors
- [ ] Verify no conflict with existing Alpine.js or HTMX
- File: `src/dashboard/chaos.html`
- Acceptance: FR-007

### T-015: Implement renderTrendCharts() method
- [ ] Add `trendChartInstances: { recovery: null, verdict: null }` to state (for cleanup)
- [ ] Add `renderTrendCharts()` async method:
  - Filters reports by `filterScenario` (required for trends)
  - Sorts by date ascending
  - Limits to `trendLimit` most recent
  - If fewer than 3 data points, sets `showTrends = false` and shows toast
  - Destroys existing chart instances if any (`trendChartInstances.recovery?.destroy()`)
  - Creates recovery time line chart:
    - X axis: dates
    - Y axis: recovery time in seconds (`stopped_at - started_at`)
    - Line color: primary
  - Creates verdict distribution bar chart:
    - X axis: dates
    - Stacked bars: CLEAN (green), COMPROMISED (red), DRY_RUN_CLEAN (blue), etc.
  - Uses `$nextTick` to ensure canvas elements are in DOM
- File: `src/dashboard/chaos.html`
- Acceptance: US4 scenarios 1-3, SC-006

### T-016: Render trend section HTML
- [ ] Add trend section: `x-show="showTrends && filterScenario"` with `x-transition`
- [ ] Add trend header with scenario name and N-selector dropdown (10/20/50)
- [ ] Add two-column grid for charts:
  - `<canvas id="recovery-trend-chart" class="w-full"></canvas>`
  - `<canvas id="verdict-trend-chart" class="w-full"></canvas>`
- [ ] Add "Need at least 3 runs" message: `x-show` when data points < 3
- [ ] Add N-selector `<select>` bound to `trendLimit` with `@change="renderTrendCharts()"`
- [ ] Wire "Show Trends" button in filter bar to `showTrends = true; renderTrendCharts()`
- File: `src/dashboard/chaos.html`
- Acceptance: US4 scenarios 4-7, EC-03

## Phase 5: Verification

### T-017: Verify all existing functionality preserved
- [ ] Scenario library cards still render and are clickable
- [ ] Start experiment form still works (blast radius slider, duration input, submit)
- [ ] Active experiments section still shows with real-time polling
- [ ] Experiment history table still renders
- [ ] Toast notifications still work
- [ ] All existing Alpine.js state and methods unchanged
- File: `src/dashboard/chaos.html`
- Acceptance: SC-008 (no backend changes, existing UI preserved)

### T-018: Verify mobile responsiveness
- [ ] Report list renders without horizontal overflow at 375px width
- [ ] Report detail renders without horizontal overflow at 375px width
- [ ] Diff view switches to stacked layout at < 768px
- [ ] Trend charts render at full width on mobile
- [ ] Filter dropdowns stack vertically on mobile
- Acceptance: SC-007, EC-03

### T-019: Verify empty states and error handling
- [ ] Empty report list shows info message
- [ ] Failed report API call shows error badge in list
- [ ] Failed report API call shows error alert in detail view
- [ ] Running experiment report shows incomplete data warning
- Acceptance: EC-01, EC-04, EC-06, SC-009, SC-010
