# Implementation Plan: Chaos Dashboard Report Viewer

**Feature Branch**: `1242-chaos-dashboard-reports`
**Created**: 2026-03-22
**Estimated Effort**: Medium (~600 lines added to chaos.html, ~50 lines CSS)

## Files to Modify

### Production Code

| File | Change | Lines Added | Risk |
|------|--------|-------------|------|
| `src/dashboard/chaos.html` | Add report list, detail, diff, and trend views to existing Alpine.js app | ~550 | Medium -- large HTML change to existing file, must preserve all existing functionality |

### Static Assets (Optional)

| File | Change | Lines | Risk |
|------|--------|-------|------|
| `src/dashboard/chaos.html` (CDN script tag) | Add Chart.js CDN link with SRI hash for trend charts | 3 | Low -- CDN dependency, same pattern as DaisyUI |

### No Other Files Changed

- Zero Python changes
- Zero Terraform changes
- Zero test file changes (E2E tests for report UI would be a separate ticket)

---

## Architecture

### View State Machine

The chaos.html Alpine.js app will manage view state with a `currentView` variable:

```
  ┌──────────┐    click row    ┌──────────┐
  │          │ ───────────────> │          │
  │   list   │                  │  detail  │
  │          │ <─────────────── │          │
  └──────────┘    back button   └──────────┘
       │
       │ select 2 + compare
       ▼
  ┌──────────┐
  │          │
  │   diff   │
  │          │
  └──────────┘
```

The existing experiment management (scenario library, start form, active experiments, history) remains at the top of the page. The new report section is added as a new tabbed area below.

### Data Flow

```
Alpine.js init()
  │
  ├── loadExperiments()          # existing -- fetches experiment list
  │
  └── loadReports()              # NEW -- for each completed experiment:
       │                          #   GET /chaos/experiments/{id}/report
       │                          #   cache in this.reports Map
       │
       ├── Report List View       # render from cached reports
       │    │
       │    ├── Client-side filter (scenario, verdict)
       │    └── Click row → fetchReport(id) → Detail View
       │
       ├── Report Detail View     # render single report from cache
       │    └── Collapsible sections via x-show
       │
       ├── Diff View              # compare two cached reports
       │    └── Side-by-side dependency comparison
       │
       └── Trend View             # Chart.js from cached reports
            └── Line chart + bar chart
```

### Report Enrichment Strategy

The existing `GET /chaos/experiments?limit=100` returns experiments with inline `results` (which contains baseline and post_chaos_health). The `GET /chaos/experiments/{id}/report` endpoint adds the `verdict` and `verdict_reason` fields.

**Optimization**: Fetch experiment list first, then batch-fetch reports only for completed/stopped/failed experiments using `Promise.all()`. This avoids N+1 API calls for running/pending experiments that don't have reports.

---

## Implementation Phases

### Phase 1: Report List View (US1 + FR-001, FR-002, FR-003, FR-008, FR-010)

**Goal**: Add a "Reports" section to chaos.html with a filterable list of completed experiment reports.

**Changes to `src/dashboard/chaos.html`**:

1. Add new Alpine.js state variables to `chaosApp()`:
   - `reports: {}` -- Map of experiment_id -> report data
   - `currentView: 'list'` -- current report view
   - `selectedReportId: null` -- for detail view
   - `selectedForDiff: []` -- array of max 2 experiment_ids for diff
   - `filterScenario: ''` -- scenario filter dropdown value
   - `filterVerdict: ''` -- verdict filter dropdown value
   - `loadingReports: false`

2. Add `loadReports()` method:
   - Filter experiments to completed/stopped/failed status
   - `Promise.all()` fetch reports for each
   - Cache in `this.reports` map
   - Called after `loadExperiments()` completes

3. Add computed `filteredReports` getter:
   - Applies scenario and verdict filters
   - Returns sorted array (most recent first)

4. Add report list HTML section after the existing "Experiment History" section:
   - Section header with "Chaos Reports" title
   - Filter bar: scenario dropdown + verdict dropdown + clear button
   - Report cards/table with: date, scenario badge, environment badge, verdict badge (color-coded), duration, dry_run indicator
   - Click handler on each row: `@click="viewReport(exp.experiment_id)"`
   - Checkbox for diff selection (max 2)
   - "Compare" button (enabled when exactly 2 selected)
   - Empty state when no reports

5. Add `verdictClass(verdict)` helper method returning DaisyUI badge class

### Phase 2: Report Detail View (US2 + FR-004, FR-005, FR-009)

**Goal**: Clicking a report opens a detailed view with collapsible sections.

**Changes to `src/dashboard/chaos.html`**:

1. Add `viewReport(experimentId)` method:
   - Sets `selectedReportId` and `currentView = 'detail'`
   - Fetches report if not cached

2. Add detail view HTML (shown when `currentView === 'detail'`):
   - Back button: `@click="currentView = 'list'"`
   - Header card: scenario name, verdict badge, environment, dates
   - Configuration section (collapsible): blast_radius, duration, injection_method, dry_run
   - Baseline Health section (collapsible): dependency cards with status indicators
   - Post-Chaos Health section (collapsible): recovered/new_issues/persistent_issues lists
   - Verdict section: large badge + verdict_reason text

3. Add `toggleSection(name)` method and `openSections: { config: true, baseline: true, postChaos: true, verdict: true }` state

### Phase 3: Diff View (US3 + FR-006)

**Goal**: Side-by-side comparison of two reports.

**Changes to `src/dashboard/chaos.html`**:

1. Add `compareReports()` method:
   - Validates exactly 2 selected
   - Sets `currentView = 'diff'`
   - Sorts by date (older = left, newer = right)

2. Add diff view HTML (shown when `currentView === 'diff'`):
   - Back button
   - Warning banner if different scenarios
   - Two-column layout (`md:grid-cols-2`)
   - Each column: report header + dependency status cards
   - Color-coded diff rows: regression=`bg-error/10`, improvement=`bg-success/10`
   - Metadata comparison: verdict change, duration delta

3. Add `diffStatus(depName)` helper:
   - Returns 'regression' | 'improvement' | 'unchanged' | 'unknown'

### Phase 4: Trend Charts (US4 + FR-007)

**Goal**: Line/bar charts showing recovery time and verdict trends.

**Changes to `src/dashboard/chaos.html`**:

1. Add Chart.js CDN `<script>` tag in `<head>` (with SRI hash)

2. Add "Show Trends" button to report list filter bar (visible when scenario filter is active)

3. Add `showTrends: false`, `trendLimit: 20` state variables

4. Add `renderTrendCharts()` method:
   - Filters reports by selected scenario
   - Extracts recovery time series (stopped_at - started_at per report)
   - Creates Chart.js line chart on `<canvas id="recovery-trend">`
   - Creates Chart.js stacked bar chart on `<canvas id="verdict-trend">`
   - Uses Alpine.js `$nextTick` to ensure canvas is in DOM before rendering

5. Add trend section HTML:
   - Two chart canvases in a responsive grid
   - N-selector dropdown (10/20/50)
   - "Need at least 3 runs" message when insufficient data

---

## Execution Order

```
Phase 1 (Report List)        -- ~250 lines, ~2 hours
  └── Phase 2 (Detail View)  -- ~200 lines, ~1.5 hours
       └── Phase 3 (Diff)    -- ~150 lines, ~1.5 hours
            └── Phase 4 (Trends) -- ~100 lines, ~1 hour
```

Phases are sequential because each builds on the previous view's state management.

---

## Risk Mitigations

| Risk | Mitigation |
|------|------------|
| Large change to single file (chaos.html) | Phase-by-phase implementation with verification at each phase |
| Chart.js CDN availability | Can self-host as `/static/vendor/chart.min.js` if needed (same pattern as HTMX/Alpine) |
| Report API N+1 calls | Batch with `Promise.all()`, cap at 100 experiments, show loading skeleton |
| Breaking existing experiment management UI | All new code goes in separate sections; existing Alpine.js state/methods untouched |
| Mobile responsiveness | Use DaisyUI responsive utilities throughout; test at 375px during each phase |
