# Implementation Checklist: Chaos Dashboard Report Viewer

**Feature**: 1242-chaos-dashboard-reports
**Date**: 2026-03-22

## Pre-Implementation

- [ ] Verify chaos.html currently loads without errors in browser
- [ ] Verify `GET /chaos/experiments?limit=50` returns data (or empty list)
- [ ] Verify `GET /chaos/experiments/{id}/report` endpoint exists and returns expected shape
- [ ] Confirm Chart.js CDN URL and SRI hash are valid

## Phase 1: Report List View

- [ ] T-001: Alpine.js state variables added
- [ ] T-002: loadReports() method implemented and called after loadExperiments()
- [ ] T-003: verdictClass() and verdictLabel() helpers working for all 5 verdict types
- [ ] T-004: filteredReports getter filters and sorts correctly
- [ ] T-005: Report list HTML renders with all columns
- [ ] T-005: Filter dropdowns work (scenario + verdict)
- [ ] T-005: Empty state shows when no reports
- [ ] T-005: Loading skeleton shows during fetch
- [ ] T-006: Diff checkbox selection toggles correctly (max 2)
- [ ] Verify: Existing experiment management UI unchanged

## Phase 2: Report Detail View

- [ ] T-007: viewReport() method fetches and caches report
- [ ] T-008: Section collapse/expand works for all 4 sections
- [ ] T-009: Header card renders scenario, verdict, environment, dates
- [ ] T-009: Configuration section shows all fields
- [ ] T-009: Baseline health cards render per dependency with correct colors
- [ ] T-009: Post-chaos health shows recovered/new/persistent lists
- [ ] T-009: Verdict section shows large badge + reason
- [ ] T-010: Running experiment shows warning banner
- [ ] Verify: Back button returns to list with filters preserved

## Phase 3: Diff View

- [ ] T-011: compareReports() validates 2 selected, sorts by date
- [ ] T-012: diffDependencyStatus() returns correct regression/improvement/unchanged
- [ ] T-013: Side-by-side layout on desktop (md:grid-cols-2)
- [ ] T-013: Stacked layout on mobile (grid-cols-1)
- [ ] T-013: Regression rows highlighted red
- [ ] T-013: Improvement rows highlighted green
- [ ] T-013: Cross-scenario warning shows for different scenario types
- [ ] T-013: Missing post_chaos data handled with placeholder

## Phase 4: Trend Charts

- [ ] T-014: Chart.js loads via CDN without console errors
- [ ] T-015: Recovery time line chart renders correctly
- [ ] T-015: Verdict distribution bar chart renders correctly
- [ ] T-015: Chart instances cleaned up before re-render
- [ ] T-016: "Need at least 3 runs" message shows when insufficient data
- [ ] T-016: N-selector (10/20/50) triggers chart update

## Phase 5: Verification

- [ ] T-017: All existing scenario cards, forms, active experiments, history table work
- [ ] T-018: All views render without horizontal overflow at 375px
- [ ] T-019: Empty state, error state, running experiment edge cases handled
- [ ] No console errors on page load
- [ ] No console errors during report list/detail/diff/trend navigation
- [ ] No unhandled promise rejections

## Post-Implementation

- [ ] Manual test: create experiment, start, stop, view report in list, open detail
- [ ] Manual test: filter by scenario, filter by verdict, clear filters
- [ ] Manual test: select 2 reports, compare diff view
- [ ] Manual test: show trends for scenario with 3+ completed experiments
- [ ] Manual test: mobile viewport (375px) for all views
