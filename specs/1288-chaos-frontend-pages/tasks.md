# Feature 1288: Chaos Admin Pages — Tasks

## Task List

### Phase 1: Foundation

#### Task 1: Install chart dependencies
- **Action**: Add `chart.js` and `react-chartjs-2` to `frontend/package.json`
- **Command**: `cd frontend && npm install chart.js react-chartjs-2`
- **Requirement mapping**: NFR-007
- **Depends on**: Nothing

#### Task 2: Create chaos TypeScript types
- **File**: `frontend/src/types/chaos.ts`
- **Action**: Create new file
- **Details**:
  - `Experiment` interface (experiment_id, scenario_type, status, blast_radius, duration_seconds, created_at, fis_status, parameters)
  - `ExperimentStatus` type: 'created' | 'pending' | 'running' | 'completed' | 'failed' | 'stopped'
  - `ScenarioType` type: 'dynamodb_throttle' | 'ingestion_failure' | 'lambda_cold_start'
  - `Verdict` type: 'CLEAN' | 'COMPROMISED' | 'DRY_RUN_CLEAN' | 'RECOVERY_INCOMPLETE' | 'INCONCLUSIVE'
  - `Report` interface (report_id, experiment_id, scenario_type, verdict, created_at, environment, duration_seconds, dry_run, verdict_reason, baseline_health, post_chaos_health, plan_report)
  - `HealthCheck` interface (all_healthy, degraded_services, dependencies)
  - `DependencyStatus` interface (status, latency_ms, error_rate)
  - `GateState` type: 'armed' | 'disarmed' | 'triggered'
  - `AndonResult` interface (kill_switch_set, experiments_found, restored, failed, errors)
  - `ComparisonResult` interface (baseline, current, direction, changes)
  - `TrendDataPoint` interface (report_id, created_at, verdict)
  - `MetricsGroup` interface (title, series[])
  - `MetricsSeries` interface (label, timestamps, values, color)
  - Request/response types for each endpoint
- **Requirement mapping**: NFR-003
- **Depends on**: Nothing

#### Task 3: Create chaos API client
- **File**: `frontend/src/lib/api/chaos.ts`
- **Action**: Create new file
- **Details**:
  - Import `api` from `./client`
  - Export `chaosApi` object with typed methods for all 18 endpoints
  - Follow exact pattern of `sentiment.ts` API module
  - All methods use Bearer token via existing `api` client
  - Handle query params for filters, pagination, metrics
- **Requirement mapping**: FR-019, FR-020, SR-001
- **Depends on**: Task 2 (types)

#### Task 4: Create VerdictBadge component
- **File**: `frontend/src/components/chaos/verdict-badge.tsx`
- **Action**: Create new file
- **Details**:
  - Props: `verdict: Verdict`, `size?: 'sm' | 'md'`
  - Color mapping per spec (CLEAN=green, COMPROMISED=red, etc.)
  - Uses Tailwind classes from spec's Verdict Color Mapping section
  - data-testid="verdict-badge"
- **Requirement mapping**: FR-005, FR-006
- **Depends on**: Task 2 (types)

### Phase 2: Experiment Management

#### Task 5: Create experiment hooks
- **File**: `frontend/src/hooks/use-chaos-experiments.ts`
- **Action**: Create new file
- **Details**:
  - `useExperiments()` — list with 10s refetch when active experiments exist
  - `useCreateExperiment()` — mutation, invalidates list on success
  - `useStartExperiment()` — mutation, invalidates list
  - `useStopExperiment()` — mutation, invalidates list
  - `useExperimentReport(id)` — query for single experiment report
  - Auto-detect active experiments via `data.some(e => e.status === 'running' || e.status === 'pending')`
  - Toast on mutation success/error via Sonner
- **Requirement mapping**: FR-004
- **Depends on**: Task 3 (API client)

#### Task 6: Create ScenarioLibrary component
- **File**: `frontend/src/components/chaos/scenario-library.tsx`
- **Action**: Create new file
- **Details**:
  - 3 scenario cards in responsive grid (3 cols desktop, 1 col mobile)
  - Each card: icon, title, description, "Select" action
  - Uses shadcn Card component
  - Scenario data hardcoded (matches backend validation)
  - data-testid="scenario-card-{type}"
- **Requirement mapping**: FR-002
- **Depends on**: Task 2 (types)

#### Task 7: Create ExperimentConfigForm component
- **File**: `frontend/src/components/chaos/experiment-config-form.tsx`
- **Action**: Create new file
- **Details**:
  - Props: `scenario: ScenarioType`, `onSubmit`, `onCancel`
  - Blast radius: shadcn Slider (10-100, step 10, default 25)
  - Duration: shadcn Input type="number" (5-300, default 60)
  - Cancel + Start Experiment buttons
  - Start button disabled while submitting
  - data-testid="experiment-form"
- **Requirement mapping**: FR-003
- **Depends on**: Task 2, Task 6

#### Task 8: Create ActiveExperimentList component
- **File**: `frontend/src/components/chaos/active-experiment-list.tsx`
- **Action**: Create new file
- **Details**:
  - Shows running/pending experiments
  - Each row: scenario name, status badge, blast radius, duration, elapsed time, Stop button
  - Stop button triggers `useStopExperiment` mutation
  - Loading state while stopping individual experiment
  - Empty state: "No active experiments"
  - data-testid="active-experiment-{id}"
- **Requirement mapping**: FR-004
- **Depends on**: Task 4 (VerdictBadge), Task 5 (hooks)

#### Task 9: Create ExperimentHistory component
- **File**: `frontend/src/components/chaos/experiment-history.tsx`
- **Action**: Create new file
- **Details**:
  - Table of completed/failed/stopped experiments
  - Columns: Time, Scenario, Status, Blast Radius, Duration, Verdict, Actions
  - Verdict column uses VerdictBadge
  - "Details" button to view experiment report
  - Responsive: table on desktop, cards on mobile
  - Empty state: "No experiments yet. Start your first chaos test above!"
  - data-testid="experiment-history"
- **Requirement mapping**: FR-005, FR-017
- **Depends on**: Task 4, Task 5

#### Task 10: Create ExperimentsTab component
- **File**: `frontend/src/components/chaos/experiments-tab.tsx`
- **Action**: Create new file
- **Details**:
  - Composes: ScenarioLibrary, ExperimentConfigForm, ActiveExperimentList, ExperimentHistory
  - State: selectedScenario (controls form visibility)
  - Placeholder slot for SafetyControlsBar (added in Phase 3)
  - Placeholder slot for MetricsPanel (added in Phase 5)
- **Requirement mapping**: FR-001
- **Depends on**: Tasks 6, 7, 8, 9

### Phase 3: Safety Controls

#### Task 11: Create safety hooks
- **File**: `frontend/src/hooks/use-chaos-safety.ts`
- **Action**: Create new file
- **Details**:
  - `useHealthCheck()` — mutation (not query — triggered by button click)
  - `useGateState()` — query with 30s refetch
  - `useSetGateState()` — mutation, invalidates gate query
  - `useAndonCord()` — mutation
  - Toast on mutation success/error
- **Requirement mapping**: FR-010, FR-011, FR-012
- **Depends on**: Task 3 (API client)

#### Task 12: Create HealthCards component
- **File**: `frontend/src/components/chaos/health-cards.tsx`
- **Action**: Create new file
- **Details**:
  - Props: `health: HealthCheck | null`, `isLoading: boolean`
  - Grid of dependency cards (2x4 responsive)
  - Each card: dependency name, status badge (healthy=green, degraded=red), latency, error rate
  - Loading state: skeleton cards
  - Null state: hidden
  - data-testid="health-card-{dependency}"
- **Requirement mapping**: FR-010
- **Depends on**: Task 2 (types)

#### Task 13: Create SafetyControlsBar component
- **File**: `frontend/src/components/chaos/safety-controls-bar.tsx`
- **Action**: Create new file
- **Details**:
  - Horizontal bar with 3 sections: Health Check, Gate Control, Emergency Stop
  - Health Check: Button + HealthCards (shown after click, 3s cooldown)
  - Gate Control: Toggle with state badge + shadcn AlertDialog confirmation
  - Andon Cord: Red button + shadcn AlertDialog with 3-step explanation
  - Gate badges: armed=warning, disarmed=neutral, triggered=error+animate-pulse
  - Andon result card: shows stats after emergency stop
  - data-testid="safety-controls"
- **Requirement mapping**: FR-010, FR-011, FR-012, SR-002, SR-003
- **Depends on**: Task 11, Task 12

#### Task 14: Integrate SafetyControlsBar into ExperimentsTab
- **File**: `frontend/src/components/chaos/experiments-tab.tsx`
- **Action**: Modify existing file
- **Details**:
  - Import SafetyControlsBar
  - Render at top of experiments tab (above scenario library)
- **Depends on**: Task 10, Task 13

### Phase 4: Reports

#### Task 15: Create report hooks
- **File**: `frontend/src/hooks/use-chaos-reports.ts`
- **Action**: Create new file
- **Details**:
  - `useReports(filters, cursor)` — query with filters
  - `useReport(id)` — single report detail query
  - `useCompareReports(currentId, baselineId)` — comparison query
  - `useTrends(scenario, limit)` — trend data query
  - All queries have appropriate staleTime (reports don't change frequently)
- **Requirement mapping**: FR-006, FR-007, FR-008, FR-009
- **Depends on**: Task 3 (API client)

#### Task 16: Create ReportList component
- **File**: `frontend/src/components/chaos/report-list.tsx`
- **Action**: Create new file
- **Details**:
  - Filter bar: scenario dropdown + verdict dropdown + Clear button
  - Table: checkbox, Time, Scenario, Environment, Verdict (badge), Duration, Dry Run, Actions
  - Checkbox column for diff selection (max 2)
  - "Compare" button enabled when exactly 2 selected
  - "Load More" button (cursor pagination)
  - Loading/error/empty states
  - Responsive: table on desktop, cards on mobile
  - data-testid="report-list", data-testid="report-row-{id}"
- **Requirement mapping**: FR-006, FR-008, FR-015, FR-016, FR-017, NFR-005
- **Depends on**: Task 4 (VerdictBadge), Task 15 (hooks)

#### Task 17: Create ReportDetail component
- **File**: `frontend/src/components/chaos/report-detail.tsx`
- **Action**: Create new file
- **Details**:
  - Collapsible sections (using state, not Radix Accordion — keep it simple)
  - Configuration section: blast radius, duration, environment, experiment ID
  - Baseline Health: dependency cards (green/red)
  - Post-Chaos Health: dependency cards with comparison indicators
  - Verdict section: large verdict badge + reason text
  - Plan report section (conditional): per-scenario summaries + assertion results
  - Dry-run banner (conditional)
  - "Back to Reports" button
  - "View Trends" button
  - data-testid="report-detail"
- **Requirement mapping**: FR-007, FR-017
- **Depends on**: Task 4, Task 12 (HealthCards reused), Task 15

#### Task 18: Create ReportDiff component
- **File**: `frontend/src/components/chaos/report-diff.tsx`
- **Action**: Create new file
- **Details**:
  - Side-by-side layout (desktop: 2 columns, mobile: stacked)
  - Verdict comparison: badges + direction arrow
  - Health comparison: dependency-by-dependency
  - Change highlights: green for improvements, red for regressions
  - Cross-scenario warning message
  - "Back to Reports" button
  - data-testid="report-diff"
- **Requirement mapping**: FR-008
- **Depends on**: Task 4, Task 15

#### Task 19: Create ReportsTab component
- **File**: `frontend/src/components/chaos/reports-tab.tsx`
- **Action**: Create new file
- **Details**:
  - Manages sub-view state: 'list' | 'detail' | 'diff' | 'trends'
  - Composes: ReportList, ReportDetail, ReportDiff, TrendChart
  - Preserves filter state when navigating between sub-views
  - data-testid="reports-tab"
- **Requirement mapping**: FR-001
- **Depends on**: Tasks 16, 17, 18

### Phase 5: Charts + Metrics

#### Task 20: Create metrics hook
- **File**: `frontend/src/hooks/use-chaos-metrics.ts`
- **Action**: Create new file
- **Details**:
  - `useMetrics()` — query with 30s refetch interval
  - Handle 403 (unavailable) by setting `metricsAvailable: false`
  - Handle 429 (rate limit) by pausing refetch, respecting Retry-After
  - Preserve last good data on error
- **Requirement mapping**: FR-013
- **Depends on**: Task 3 (API client)

#### Task 21: Create TrendChart component
- **File**: `frontend/src/components/chaos/trend-chart.tsx`
- **Action**: Create new file
- **Details**:
  - Scenario selector dropdown + N selector (10/20/50)
  - Stacked bar chart (react-chartjs-2 `<Bar>`)
  - Datasets: one per verdict type, colors from spec
  - Minimum 3 data points required — show message if fewer
  - Tooltips: date + verdict
  - Responsive: full width
  - data-testid="trend-chart"
- **Requirement mapping**: FR-009
- **Depends on**: Task 1 (chart.js), Task 15 (hooks)

#### Task 22: Create MetricsPanel component
- **File**: `frontend/src/components/chaos/metrics-panel.tsx`
- **Action**: Create new file
- **Details**:
  - Grid of line charts (react-chartjs-2 `<Line>`)
  - One chart per metrics group (from backend response)
  - Refresh button + last-fetched timestamp
  - Loading: skeleton charts (pulse animation)
  - Error: preserve last data, show error badge
  - Unavailable (403): info banner, panel hidden
  - Rate limited (429): countdown display
  - data-testid="metrics-panel"
- **Requirement mapping**: FR-013
- **Depends on**: Task 1 (chart.js), Task 20 (hooks)

#### Task 23: Integrate MetricsPanel into ExperimentsTab
- **File**: `frontend/src/components/chaos/experiments-tab.tsx`
- **Action**: Modify existing file
- **Details**:
  - Import MetricsPanel
  - Render below experiment history
- **Depends on**: Task 10, Task 22

### Phase 6: Assembly

#### Task 24: Create ChaosPageTabs component
- **File**: `frontend/src/components/chaos/chaos-page-tabs.tsx`
- **Action**: Create new file
- **Details**:
  - Two tabs: "Experiments" and "Reports"
  - Uses simple state toggle (not shadcn Tabs if not installed)
  - Default: Experiments tab
  - Preserves tab state on re-render
  - data-testid="chaos-tabs"
- **Requirement mapping**: FR-001
- **Depends on**: Task 10 (ExperimentsTab), Task 19 (ReportsTab)

#### Task 25: Update chaos page
- **File**: `frontend/src/app/(admin)/admin/chaos/page.tsx`
- **Action**: Modify existing file (replace placeholder from Feature 1287)
- **Details**:
  - Import ChaosPageTabs
  - Page title: "Chaos Dashboard"
  - Render ChaosPageTabs as main content
- **Requirement mapping**: FR-001
- **Depends on**: Task 24

#### Task 26: Final responsive + data-testid pass
- **Action**: Review all components
- **Details**:
  - Verify all interactive elements have data-testid attributes
  - Verify no horizontal scroll at 375px viewport
  - Verify keyboard accessibility on all buttons, dialogs, tabs
  - Verify toast notifications on all mutations
- **Requirement mapping**: NFR-005, NFR-006, NFR-008
- **Depends on**: Task 25

## Dependency Graph

```
Task 1 (chart.js) ────────────────────────────────┐
                                                   │
Task 2 (types) ──┬──→ Task 3 (API client) ──┬──→ Task 5 (experiment hooks) ──┐
                 │                           │                                │
                 │                           ├──→ Task 11 (safety hooks) ──┐  │
                 │                           │                             │  │
                 │                           ├──→ Task 15 (report hooks)───┤  │
                 │                           │                             │  │
                 │                           └──→ Task 20 (metrics hook)──┐│  │
                 │                                                        ││  │
                 ├──→ Task 4 (VerdictBadge) ──┬───────────────────────────┤│  │
                 │                            │                           ││  │
                 ├──→ Task 6 (ScenarioLib) ───┤                           ││  │
                 │                            │                           ││  │
                 └──→ Task 12 (HealthCards) ──┤                           ││  │
                                              │                           ││  │
Task 7 (ConfigForm) ─────────────────────────┐│                           ││  │
                                              ││                           ││  │
Task 8 (ActiveList) ──────────────────────────┤│                           ││  │
                                              ││                           ││  │
Task 9 (History) ─────────────────────────────┤│                           ││  │
                                              ││                           ││  │
Task 10 (ExperimentsTab) ←────────────────────┘│                           ││  │
         │                                     │                           ││  │
         │  Task 13 (SafetyBar) ←──────────────┤←──────────────────────────┘│  │
         │     │                               │                            │  │
         │←────┘ (Task 14: integrate)          │                            │  │
         │                                     │                            │  │
         │  Task 22 (MetricsPanel) ←───────────┤←───────────────────────────┘  │
         │     │                               │                               │
         │←────┘ (Task 23: integrate)          │                               │
         │                                     │                               │
         │  Task 16 (ReportList) ←─────────────┤                               │
         │  Task 17 (ReportDetail) ←───────────┤                               │
         │  Task 18 (ReportDiff) ←─────────────┤                               │
         │  Task 21 (TrendChart) ←─────────────┤←── Task 1 (chart.js)          │
         │                                     │                               │
         │  Task 19 (ReportsTab) ←─────────────┘                               │
         │     │                                                               │
         └──→ Task 24 (ChaosPageTabs) ←────────────────────────────────────────┘
                │
                └──→ Task 25 (Update page)
                       │
                       └──→ Task 26 (Final pass)
```

## Parallelization

- **Parallel group 1**: Tasks 1, 2 (independent)
- **Parallel group 2**: Tasks 3, 4, 6, 12 (all depend on Task 2 only)
- **Parallel group 3**: Tasks 5, 7, 8, 9, 11, 15, 20 (depend on group 2)
- **Parallel group 4**: Tasks 10, 13, 16, 17, 18, 21, 22 (compose from group 3)
- **Parallel group 5**: Tasks 14, 19, 23 (integration)
- **Sequential**: 24 → 25 → 26

## Requirement Coverage

| Requirement | Task(s) |
|-------------|---------|
| FR-001 | Tasks 10, 19, 24, 25 |
| FR-002 | Task 6 |
| FR-003 | Task 7 |
| FR-004 | Tasks 5, 8 |
| FR-005 | Tasks 4, 9 |
| FR-006 | Tasks 15, 16 |
| FR-007 | Task 17 |
| FR-008 | Tasks 16, 18 |
| FR-009 | Task 21 |
| FR-010 | Tasks 11, 12, 13 |
| FR-011 | Tasks 11, 13 |
| FR-012 | Tasks 11, 13 |
| FR-013 | Tasks 20, 22 |
| FR-014 | Tasks 5, 11 (toast in hooks) |
| FR-015 | Task 16 |
| FR-016 | Tasks 8, 9, 16, 21 |
| FR-017 | Tasks 4, 9, 16, 17 |
| FR-018 | Task 15 (React Query cache) |
| FR-019 | Task 3 |
| FR-020 | Task 3 |
| SR-001 | Task 3 |
| SR-002 | Task 13 |
| SR-003 | Task 13 |
| SR-004 | Feature 1287 (route gate) |
| NFR-001 | All (no new endpoints) |
| NFR-002 | All (no new infra) |
| NFR-003 | All (existing stack) |
| NFR-005 | Task 26 |
| NFR-006 | Task 26 |
| NFR-007 | Tasks 1, 21, 22 |
| NFR-008 | Task 26 |

All MUST requirements have ≥1 mapped task. Coverage: 100%.

## Adversarial Review #3

| # | Finding | Severity | Resolution |
|---|---------|----------|------------|
| 1 | 26 tasks risks scope creep | MEDIUM | Ship in 2 waves: MVP (Phases 1-3), then full (Phases 4-6) |
| 2 | Slider component availability | LOW | Verified: @radix-ui/react-slider installed |
| 3 | Chart.js tree-shaking requires explicit registration | MEDIUM | Implementation note added to Tasks 21/22 |
| 4 | No Vitest unit tests | LOW | Playwright covers integrated behavior; hooks are thin wrappers |

**Highest-risk task:** Task 13 (SafetyControlsBar) — critical safety operations with confirmation dialogs
**Most likely rework:** Task 3 (API client) — request/response shape mismatches ripple everywhere

**READY FOR IMPLEMENTATION** — 0 CRITICAL, 0 HIGH remaining. 26 tasks across 6 phases.
