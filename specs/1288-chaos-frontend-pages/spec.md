# Feature 1288: Chaos Admin Pages in Customer Frontend

> Supersedes: Features 1242 (chaos-dashboard-reports) and 1285 (chaos-react-dashboard)

## Summary

Migrate all chaos dashboard functionality from `src/dashboard/chaos.html` (1,634 lines of Alpine.js) into the Next.js customer frontend at `/admin/chaos`. This page is only accessible to operators (gated by Feature 1287). No new backend API endpoints are needed — the existing 18 chaos API endpoints are reused.

**Key constraint:** This is a page WITHIN the customer frontend, not a separate application. It uses the same component library (shadcn/ui), state management (Zustand + React Query), and auth system (Bearer tokens) as the rest of the app.

## User Stories

### US-001: Operator manages chaos experiments
As an operator, I want to create, start, stop, and view chaos experiments from `/admin/chaos` so that I can run chaos injection from the same app I already use.

**Acceptance criteria:**
- See 3 scenario cards (DynamoDB Throttle, Ingestion Failure, Lambda Cold Start)
- Configure blast radius (10-100%, slider) and duration (5-300s, input)
- Start experiment → see it in active list with status badges
- Stop experiment → see it move to history with verdict badge
- Active experiments auto-refresh every 10 seconds

### US-002: Operator views and filters reports
As an operator, I want to view chaos reports with filters so that I can find specific experiment results.

**Acceptance criteria:**
- Report list with columns: Time, Scenario, Environment, Verdict, Duration, Dry Run
- Filter by scenario type (dropdown) and verdict (dropdown), AND logic
- Cursor-based pagination ("Load More", 20 per page)
- Click row to view full report detail
- Verdict badges color-coded: CLEAN=green, COMPROMISED=red, DRY_RUN_CLEAN=blue, RECOVERY_INCOMPLETE=amber, INCONCLUSIVE=gray

### US-003: Operator views report details
As an operator, I want to drill into a report to see baseline health, post-chaos health, and verdict reasoning.

**Acceptance criteria:**
- Collapsible sections: Configuration, Baseline Health, Post-Chaos Health, Verdict
- Dependency cards show status (healthy/degraded) with latency and error rate
- Plan reports show per-scenario summaries and assertion results
- Dry-run banner when applicable
- Back navigation preserves filter state

### US-004: Operator compares reports
As an operator, I want to compare two reports side-by-side to detect regressions or improvements.

**Acceptance criteria:**
- Select 2 reports via checkboxes → Compare button enabled
- Side-by-side layout on desktop, stacked on mobile
- Green highlight for improvements (degraded→healthy)
- Red highlight for regressions (healthy→degraded)
- Verdict direction indicator (improved/regressed)

### US-005: Operator views trends
As an operator, I want to see verdict trends over time so I can track system resilience.

**Acceptance criteria:**
- Stacked bar chart showing verdict distribution over N runs
- Scenario selector dropdown
- N selector: 10, 20, 50
- Minimum 3 data points required (message shown if fewer)
- Tooltips on hover

### US-006: Operator uses safety controls
As an operator, I want health checks, gate controls, and an emergency stop button so I can safely manage chaos injection.

**Acceptance criteria:**
- Pre-flight health check: dependency status cards (DynamoDB, SSM, CloudWatch, Lambda)
- Gate toggle: arm/disarm with confirmation dialog
- Andon cord: emergency stop with confirmation dialog → stops all experiments + restores environment
- Gate state badges: armed=warning, disarmed=neutral, triggered=error+pulse
- 3-second cooldown after health check

### US-007: Operator views real-time metrics
As an operator, I want to see system metrics (latency, error rates, invocations, throughput) during chaos experiments.

**Acceptance criteria:**
- Line charts grouped by metric type
- Auto-refresh every 30 seconds
- Refresh button for manual refresh
- Error state preserves last good data
- Rate limit handling (retry with backoff)

## Requirements

### Functional Requirements

| ID | Requirement | Priority |
|----|-------------|----------|
| FR-001 | Chaos page at `/admin/chaos` with tabbed layout: Experiments, Reports | MUST |
| FR-002 | Scenario library: 3 clickable cards with descriptions | MUST |
| FR-003 | Experiment config form: blast radius slider + duration input | MUST |
| FR-004 | Active experiment list with auto-refresh (10s) and stop buttons | MUST |
| FR-005 | Experiment history table with verdict badges | MUST |
| FR-006 | Report list with filters (scenario, verdict) and cursor pagination | MUST |
| FR-007 | Report detail view with collapsible sections | MUST |
| FR-008 | Report comparison (select 2, side-by-side diff) | SHOULD |
| FR-009 | Verdict trend charts (stacked bar, scenario selector, N=10/20/50) | SHOULD |
| FR-010 | Health check button with dependency status cards | MUST |
| FR-011 | Gate arm/disarm toggle with confirmation dialog | MUST |
| FR-012 | Emergency stop (andon cord) with confirmation dialog | MUST |
| FR-013 | Real-time metrics panel with auto-refresh (30s) | SHOULD |
| FR-014 | Toast notifications for experiment operations (start, stop, error) | MUST |
| FR-015 | Error states: report error banner with retry, API error handling | MUST |
| FR-016 | Empty states: no experiments, no reports, insufficient trend data | MUST |
| FR-017 | Dry-run badge and banner on relevant experiments/reports | MUST |
| FR-018 | Client-side report cache (LRU, max 100 entries) | SHOULD |
| FR-019 | Bearer token auth on all API calls (via existing api client) | MUST |
| FR-020 | No X-API-Key usage (deprecated) | MUST |

### Non-Functional Requirements

| ID | Requirement | Priority |
|----|-------------|----------|
| NFR-001 | No new backend API endpoints | MUST |
| NFR-002 | No new infrastructure (DynamoDB tables, Lambda functions) | MUST |
| NFR-003 | Uses existing frontend stack: shadcn/ui, React Query, Zustand, Tailwind | MUST |
| NFR-004 | Report list loads in <3 seconds for 20 reports | SHOULD |
| NFR-005 | Responsive: no horizontal scroll at 375px viewport | MUST |
| NFR-006 | All interactive elements keyboard-accessible | MUST |
| NFR-007 | Charts: react-chartjs-2 (already bundled, no CDN) or Recharts (if already in deps) | SHOULD |
| NFR-008 | Playwright-testable: all interactive elements have data-testid attributes | MUST |

### Security Requirements

| ID | Requirement | Priority |
|----|-------------|----------|
| SR-001 | All API calls use Bearer token from existing auth system | MUST |
| SR-002 | Andon cord confirmation requires explicit user action (dialog, not toggle) | MUST |
| SR-003 | Gate arm requires confirmation dialog | MUST |
| SR-004 | No chaos API calls from non-operator context (enforced by Feature 1287 route gate) | MUST |

## API Endpoints (Existing — No Changes)

All endpoints are under the dashboard Lambda. Auth: Bearer token in Authorization header.

### Experiment Management
| Method | Path | Purpose |
|--------|------|---------|
| POST | `/chaos/experiments` | Create experiment |
| GET | `/chaos/experiments` | List experiments |
| GET | `/chaos/experiments/{id}` | Get experiment detail |
| POST | `/chaos/experiments/{id}/start` | Start experiment |
| POST | `/chaos/experiments/{id}/stop` | Stop experiment |
| GET | `/chaos/experiments/{id}/report` | Get experiment report |
| DELETE | `/chaos/experiments/{id}` | Delete experiment |

### Report Management
| Method | Path | Purpose |
|--------|------|---------|
| GET | `/chaos/reports` | List reports (filters: scenario_type, verdict, cursor, limit) |
| GET | `/chaos/reports/{id}` | Get report detail |
| GET | `/chaos/reports/{id}/compare` | Compare with baseline (query: baseline_id) |
| GET | `/chaos/reports/trends/{scenario}` | Trend data (query: limit) |

### Safety Controls
| Method | Path | Purpose |
|--------|------|---------|
| GET | `/chaos/health` | System health check |
| GET | `/chaos/gate` | Get gate state |
| PUT | `/chaos/gate` | Set gate state (body: {state}) |
| POST | `/chaos/andon-cord` | Emergency stop all |
| GET | `/chaos/metrics` | Real-time metrics (query: start_time, end_time, period) |

## Verdict Color Mapping

| Verdict | Tailwind Class | Description |
|---------|---------------|-------------|
| CLEAN | `text-success bg-success/10` | System recovered cleanly |
| COMPROMISED | `text-destructive bg-destructive/10` | System failed to recover |
| DRY_RUN_CLEAN | `text-blue-500 bg-blue-500/10` | Dry run, no fault injected |
| RECOVERY_INCOMPLETE | `text-warning bg-warning/10` | Partial recovery |
| INCONCLUSIVE | `text-muted-foreground bg-muted` | Insufficient data |

## Component Architecture

```
/admin/chaos (page.tsx)
├── ChaosPageTabs (Experiments | Reports)
│
├── ExperimentsTab
│   ├── SafetyControlsBar
│   │   ├── HealthCheckButton + HealthCards
│   │   ├── GateToggle + ConfirmDialog
│   │   └── AndonCordButton + ConfirmDialog
│   ├── ScenarioLibrary (3 cards)
│   ├── ExperimentConfigForm (blast radius + duration)
│   ├── ActiveExperimentList (auto-refresh)
│   ├── ExperimentHistory (table with verdict badges)
│   └── MetricsPanel (line charts, auto-refresh)
│
└── ReportsTab
    ├── ReportFilters (scenario + verdict dropdowns)
    ├── ReportList (table with checkboxes, pagination)
    ├── ReportDetail (collapsible sections)
    ├── ReportDiff (side-by-side comparison)
    └── TrendChart (stacked bar chart)
```

## Edge Cases

1. **Experiment still running**: Show "Running" status badge, disable report view
2. **First baseline (no prior report)**: Compare endpoint returns 422 — show "First baseline" info message
3. **Metrics unavailable in environment**: Show info banner, hide metrics panel
4. **Rate limited**: Show retry countdown, respect Retry-After header
5. **Concurrent operators**: Auto-refresh picks up other operators' experiments
6. **Network failure mid-experiment**: Toast error, experiment continues server-side, refresh picks it up
7. **Gate triggered externally**: Auto-refresh gate state updates UI
8. **Very long error messages**: Truncate at 200 chars with expandable "Show more"

## Success Criteria

| ID | Criterion |
|----|-----------|
| SC-001 | All 18 API endpoints callable from `/admin/chaos` with Bearer token auth |
| SC-002 | All 5 verdict types render with correct colors |
| SC-003 | Report list loads <3s for 20 reports |
| SC-004 | Experiment lifecycle (create→start→stop→report) works end-to-end |
| SC-005 | Safety controls (health, gate, andon) functional |
| SC-006 | Trend charts render correctly with ≥3 data points |
| SC-007 | No horizontal scroll at 375px viewport |
| SC-008 | All interactive elements have data-testid attributes |
| SC-009 | Existing customer dashboard unaffected (no regressions) |
| SC-010 | No X-API-Key usage — Bearer token only |

## New Dependencies

| Package | Purpose | Size |
|---------|---------|------|
| `chart.js` | Chart rendering engine | ~66KB gzipped |
| `react-chartjs-2` | React wrapper for Chart.js | ~5KB gzipped |

Note: `lightweight-charts` is already installed but is for OHLC financial charts (TradingView). Not suitable for stacked bar / line charts needed here.

## Out of Scope

- Backend API changes (all 18 endpoints exist)
- New DynamoDB tables or Lambda functions
- Playwright test suite (separate feature or part of overall test plan)
- Role assignment UI (manual DynamoDB for now)
- New chaos scenarios beyond the existing 3

## Files to Create

### API Client
- `frontend/src/lib/api/chaos.ts` — Typed API client for all 18 chaos endpoints

### React Query Hooks
- `frontend/src/hooks/use-chaos-experiments.ts` — Experiment CRUD + polling
- `frontend/src/hooks/use-chaos-reports.ts` — Report listing, detail, comparison, trends
- `frontend/src/hooks/use-chaos-safety.ts` — Health, gate, andon cord
- `frontend/src/hooks/use-chaos-metrics.ts` — Metrics with auto-refresh

### Page + Components
- `frontend/src/app/(admin)/admin/chaos/page.tsx` — Main page (replaces 1287 placeholder)
- `frontend/src/components/chaos/chaos-page-tabs.tsx` — Tab container
- `frontend/src/components/chaos/experiments-tab.tsx` — Experiments view
- `frontend/src/components/chaos/scenario-library.tsx` — 3 scenario cards
- `frontend/src/components/chaos/experiment-config-form.tsx` — Config inputs
- `frontend/src/components/chaos/active-experiment-list.tsx` — Running experiments
- `frontend/src/components/chaos/experiment-history.tsx` — History table
- `frontend/src/components/chaos/safety-controls-bar.tsx` — Health + gate + andon
- `frontend/src/components/chaos/metrics-panel.tsx` — Line charts
- `frontend/src/components/chaos/reports-tab.tsx` — Reports view
- `frontend/src/components/chaos/report-list.tsx` — Filtered table with pagination
- `frontend/src/components/chaos/report-detail.tsx` — Collapsible detail view
- `frontend/src/components/chaos/report-diff.tsx` — Side-by-side comparison
- `frontend/src/components/chaos/trend-chart.tsx` — Stacked bar chart
- `frontend/src/components/chaos/verdict-badge.tsx` — Reusable verdict color badge
- `frontend/src/components/chaos/health-cards.tsx` — Dependency status cards

### Types
- `frontend/src/types/chaos.ts` — TypeScript types for all chaos data models

### Store (optional)
- `frontend/src/stores/chaos-store.ts` — Zustand store for tab state, filter persistence, report cache

## Clarifications

| # | Question | Answer | Source |
|---|----------|--------|--------|
| 1 | Default tab: Experiments or Reports? | Experiments — action-oriented default | UX convention |
| 2 | Safety controls visible on Reports tab? | No — Reports tab is read-only analysis | Separation of concerns |
| 3 | Scenarios hardcoded or dynamic? | Hardcoded 3 — backend validates against fixed list | chaos.py scenario validation |
| 4 | Metrics behind feature flag? | No — backend returns 403, frontend hides gracefully | API 403 response handling |
| 5 | Cross-scenario comparison? | Allow with warning message | Existing chaos.html behavior |

All questions self-answered. No deferred questions.

## Adversarial Review #1

| # | Severity | Finding | Resolution |
|---|----------|---------|------------|
| 1 | CRITICAL | chart.js / react-chartjs-2 not installed — only lightweight-charts (OHLC) exists | Added "New Dependencies" section. chart.js + react-chartjs-2 must be installed. |
| 2 | HIGH | Backend may only accept X-API-Key, not Bearer tokens on chaos endpoints | Verified: handler.py uses JWT auth middleware. Bearer token works. |
| 3 | HIGH | API base URL routing — are chaos endpoints reachable from frontend API client? | Verified: chaos routes in same dashboard Lambda as all other API endpoints. Same base URL. |
| 4 | MEDIUM | ~20 new files may be excessive granularity | File list is target architecture. Implementation can start coarser, extract later. |
| 5 | MEDIUM | POST /chaos/reports not in user stories | Server-side auto-creation on stop. Manual endpoint exposed in API client but no UI. |
| 6 | LOW | No DELETE report UI | Rare admin action, CLI-accessible. Not worth v1 surface area. |

**Gate: 0 CRITICAL, 0 HIGH remaining.**
