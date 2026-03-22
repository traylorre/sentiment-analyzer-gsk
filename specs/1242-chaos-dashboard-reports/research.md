# Research: Chaos Dashboard Report Viewer

**Feature**: 1242-chaos-dashboard-reports
**Date**: 2026-03-22

## Existing Codebase Analysis

### Current Dashboard Architecture

The chaos dashboard (`src/dashboard/chaos.html`) is a single 505-line HTML file with:
- **HTMX** (14KB, self-hosted at `/static/vendor/htmx.min.js`) -- used for server-driven interactions
- **Alpine.js** (44KB, self-hosted at `/static/vendor/alpine.min.js`) -- used for all client-side reactivity
- **Tailwind CSS** via CDN JIT compiler (`cdn.tailwindcss.com`) -- note: no SRI (JIT generates CSS dynamically)
- **DaisyUI** 4.12.14 via CDN with SRI hash

The entire app is a single Alpine.js component (`chaosApp()`) containing:
- 8 state variables
- 2 computed getters (`activeExperiments`, `historyExperiments`)
- 1 constants object (`scenarioNames`)
- 7 methods (init, showToast, selectScenario, startExperiment, stopExperiment, loadExperiments, viewExperiment, formatTime, getApiKey)

The `viewExperiment()` method is currently a placeholder: `alert('Experiment details coming in Phase 2!')`. This is the natural hook for the report detail view.

### Backend Report API

`get_experiment_report()` in `src/lambdas/dashboard/chaos.py` (lines 1005-1062) already provides:
- Experiment metadata (scenario, status, dry_run, duration)
- Baseline health with per-dependency status
- Post-chaos health comparison (recovered, new_issues, persistent_issues)
- Verdict determination with 5 possible values and reasons

The report is computed on-the-fly from experiment data -- there is no separate report table. This means:
1. Reports are always up-to-date with experiment state
2. No report creation/storage needed
3. Caching on the frontend is important to avoid recomputing per render

### Existing E2E Tests

`frontend/tests/e2e/chaos.spec.ts` tests the full experiment lifecycle including reports:
- Creates experiments for all 5 scenario types
- Starts and stops experiments
- Fetches reports via `GET /chaos/experiments/{id}/report`
- Validates verdict = 'DRY_RUN_CLEAN' for gate-disarmed experiments
- Tests authentication requirements
- Tests safety guard validations

These tests confirm the API contract is stable and the report endpoint works.

## Chart Library Decision

### Requirements
- No build step (CDN or self-hosted UMD/IIFE bundle)
- Works with Alpine.js (imperative `new Chart(canvas, config)` API)
- Supports line charts and stacked bar charts
- Responsive by default
- Reasonable bundle size

### Options Evaluated

| Library | Size (gzipped) | CDN | Alpine.js compat | Charts needed |
|---------|-----------------|-----|-------------------|---------------|
| Chart.js 4.x | 66KB | Yes (jsdelivr, SRI) | Yes (canvas API) | Line, Bar (stacked) |
| uPlot | 12KB | Yes (unpkg) | Yes (canvas API) | Line only, no stacked bar |
| Frappe Charts | 18KB | Yes (unpkg) | Yes (SVG DOM API) | Line, Bar (no stacked) |
| Inline SVG | 0KB | N/A | Yes | Manual implementation |

### Decision: Chart.js 4.x

**Rationale**:
1. Supports both line and stacked bar charts out of the box
2. Well-maintained, widely used, stable CDN availability
3. Canvas-based -- works with Alpine.js lifecycle hooks (`$nextTick`)
4. Responsive by default (`responsive: true` option)
5. Tooltip support built-in
6. 66KB gzipped is acceptable for a dashboard page (not a latency-critical path)

**Alternative considered**: Inline SVG generation would be zero-dependency but requires significant implementation effort for axis labels, tooltips, and responsiveness. Not worth the trade-off for a P3 feature.

## DaisyUI Component Mapping

### Verdict Badges
- CLEAN: `badge badge-success badge-lg` (green)
- COMPROMISED: `badge badge-error badge-lg` (red)
- DRY_RUN_CLEAN: `badge badge-info badge-lg` (blue)
- RECOVERY_INCOMPLETE: `badge badge-warning badge-lg` (orange)
- INCONCLUSIVE: `badge badge-ghost badge-lg` (gray)

### Health Status Cards
- Healthy: `card bg-success/10 border border-success/20`
- Degraded: `card bg-error/10 border border-error/20`

### Diff Highlighting
- Regression: `bg-error/10 border-l-4 border-error`
- Improvement: `bg-success/10 border-l-4 border-success`
- Unchanged: no additional classes

### Collapsible Sections
Using DaisyUI `collapse` component or Alpine.js `x-show` with `x-transition`:
```html
<div @click="toggleSection('baseline')" class="cursor-pointer flex justify-between items-center">
  <h3>Baseline Health</h3>
  <svg :class="openSections.baseline ? 'rotate-180' : ''" class="transition-transform">...</svg>
</div>
<div x-show="openSections.baseline" x-transition>
  <!-- content -->
</div>
```

Alpine.js `x-show` with `x-transition` is preferred over DaisyUI `collapse` because:
- More control over animation
- Consistent with existing dashboard patterns
- No checkbox hack needed

## Prior Art

### Related Features
- **F1237** (chaos external refactor): Refactored chaos.py to external actor architecture. The report API exists because of this work.
- **F1239** (execution plans): Adds plan management (create/edit/delete plans). Report viewer consumes plan execution results.
- **F1240** (chaos reports): Backend report generation and storage. This feature (1242) is the UI complement.

### Chaos Dashboard UI Patterns (External)
- **Gremlin**: Card-based report list with verdict badges, expandable detail, trend sparklines
- **Chaos Mesh**: Table-based experiment list with status filters, modal detail view
- **Litmus (CNCF)**: Dashboard with metric cards, timeline view, comparison table

The most relevant pattern for this project is Gremlin's approach: simple verdict badges in a list with click-to-expand detail. The diff view and trends are additions not commonly found in chaos dashboards (differentiator for engineering velocity).
