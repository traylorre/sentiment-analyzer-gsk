# Feature 1288: Chaos Admin Pages — Implementation Plan

## Technical Context

### Existing Infrastructure (Reused)
- **Chaos API**: 18 endpoints in `src/lambdas/dashboard/handler.py` — all functional
- **DynamoDB**: `{env}-chaos-experiments`, `{env}-chaos-reports` — schema stable
- **Auth**: Bearer token via `frontend/src/lib/api/client.ts` — works for all endpoints
- **Component library**: shadcn/ui (Button, Card, Dialog, Slider, Switch, Tooltip, Skeleton)
- **Icons**: Lucide React (ShieldCheck, Play, Square, Activity, AlertTriangle, etc.)
- **Toasts**: Sonner (`toast.success()`, `toast.error()`)
- **Animations**: Framer Motion (for tab transitions, expand/collapse)
- **State**: Zustand (memory-only stores), React Query (server state)

### New Dependencies
- `chart.js` ^4.4 + `react-chartjs-2` ^5 — for trend and metrics charts

### API Client Pattern
Follow existing `frontend/src/lib/api/sentiment.ts` pattern:
```typescript
// frontend/src/lib/api/chaos.ts
import { api } from './client';

export const chaosApi = {
  createExperiment: (data: CreateExperimentRequest) =>
    api.post<Experiment>('/chaos/experiments', data),
  listExperiments: (params?: ListExperimentsParams) =>
    api.get<Experiment[]>('/chaos/experiments', { params }),
  // ... all 18 endpoints
};
```

### React Query Pattern
Follow existing hook patterns:
```typescript
// Auto-refresh active experiments
const { data } = useQuery({
  queryKey: ['chaos', 'experiments'],
  queryFn: () => chaosApi.listExperiments(),
  refetchInterval: hasActiveExperiments ? 10_000 : false,
});
```

## Implementation Phases

### Phase 1: Foundation (Types + API Client + Dependencies)

1. Install `chart.js` and `react-chartjs-2`
2. Create `frontend/src/types/chaos.ts` — all TypeScript interfaces
3. Create `frontend/src/lib/api/chaos.ts` — typed API client for all 18 endpoints
4. Create `frontend/src/components/chaos/verdict-badge.tsx` — reusable badge component

### Phase 2: Experiment Management (Core Loop)

5. Create `use-chaos-experiments.ts` hook — list, create, start, stop, poll
6. Create `scenario-library.tsx` — 3 scenario cards
7. Create `experiment-config-form.tsx` — blast radius slider + duration input
8. Create `active-experiment-list.tsx` — running experiments with stop buttons
9. Create `experiment-history.tsx` — completed experiments table
10. Create `experiments-tab.tsx` — composes above components

### Phase 3: Safety Controls

11. Create `use-chaos-safety.ts` hook — health, gate, andon
12. Create `health-cards.tsx` — dependency status grid
13. Create `safety-controls-bar.tsx` — health check + gate toggle + andon cord with dialogs

### Phase 4: Reports

14. Create `use-chaos-reports.ts` hook — list, detail, compare, trends
15. Create `report-list.tsx` — filtered table with checkboxes and pagination
16. Create `report-detail.tsx` — collapsible sections (config, baseline, post-chaos, verdict)
17. Create `report-diff.tsx` — side-by-side comparison view
18. Create `reports-tab.tsx` — composes report components

### Phase 5: Charts + Metrics

19. Create `use-chaos-metrics.ts` hook — metrics with auto-refresh
20. Create `trend-chart.tsx` — stacked bar chart (verdict distribution)
21. Create `metrics-panel.tsx` — line charts (system metrics)

### Phase 6: Assembly + Polish

22. Create `chaos-page-tabs.tsx` — tab container (Experiments | Reports)
23. Update `page.tsx` at `(admin)/admin/chaos/` — replace placeholder
24. Create `chaos-store.ts` (optional) — tab state, filter persistence
25. Add data-testid attributes to all interactive elements
26. Responsive pass: verify all components at 375px

## Data Flow

```
User clicks /admin/chaos
  → Feature 1287 gate: authenticated? operator? → Allow
  → page.tsx renders ChaosPageTabs
  → ExperimentsTab:
      React Query fetches experiments (10s poll if active)
      Safety controls bar always visible
  → ReportsTab:
      React Query fetches reports (cursor pagination)
      Sub-views: detail, diff, trends (client-side navigation)
```

## State Architecture

| State | Tool | Why |
|-------|------|-----|
| Experiments list | React Query | Server state, auto-refresh |
| Reports list + detail | React Query | Server state, cache |
| Health / Gate / Andon | React Query + mutations | Server state with write operations |
| Metrics | React Query | Server state, auto-refresh |
| Active tab | Zustand or useState | Client state, session-only |
| Report filters | Zustand or useState | Client state, preserved on tab switch |
| Report cache | React Query cache | Built-in LRU, configurable staleTime |
| Diff selection | useState | Local to ReportsTab component |

## Risk Assessment

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| Chart.js bundle size bloat | Low | Medium | Tree-shake unused chart types; only import Bar and Line |
| API rate limiting on metrics | Medium | Low | Respect Retry-After header, show countdown |
| Stale experiment state | Medium | Low | 10s polling + manual refresh button |
| Component count too high | Low | Medium | Start coarser, extract when complexity warrants |
| Backend auth rejects Bearer on chaos endpoints | Low | High | Verified: handler.py uses JWT middleware |

## Dependencies

- **Upstream**: Feature 1287 (admin route group — must be merged first)
- **Downstream**: Feature 1289 (HTMX removal — waits for this to ship + 7-day soak)

## Adversarial Review #2

| # | Finding | Severity | Resolution |
|---|---------|----------|------------|
| 1 | POST /chaos/reports and DELETE not in plan phases | LOW | Backend-only operations. API client exposes them, no UI needed. |
| 2 | ExperimentsTab (Phase 2) depends on SafetyControlsBar (Phase 3) | MEDIUM | Phase 2 renders experiments tab without safety bar; Phase 3 adds it. Or implement sequentially Phase 2→3 before integration. |
| 3 | No spec drift from AR#1 | — | No action |

**Drift found:** 0 spec edits needed.
**Cross-artifact inconsistencies:** 0 remaining.
**Gate: 0 CRITICAL, 0 HIGH remaining.**
