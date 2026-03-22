# Implementation Plan: Heatmap Error Resilience

**Branch**: `1231-heatmap-error-resilience` | **Date**: 2026-03-21 | **Spec**: [spec.md](spec.md)
**Input**: Feature specification from `/specs/1231-heatmap-error-resilience/spec.md`

## Summary

The heatmap component (`HeatMapView`) crashes when the sentiment API returns errors or unexpected shapes because `Object.entries(ticker.sentiment)` throws on non-object values. Fix: add defensive guards in the frontend transformation layer, add an error state UI to the heatmap, and ensure the parent page component handles react-query error/loading states before passing data to the heatmap. Backend already handles partial failures correctly (per-ticker try/except); this feature adds tests to lock that behavior and documents the contract.

## Technical Context

**Language/Version**: TypeScript 5.x (frontend, Next.js), Python 3.13 (backend)
**Primary Dependencies**: React 18, TanStack Query (react-query), Framer Motion, Vitest (frontend testing), pytest (backend testing)
**Storage**: No storage changes
**Testing**: Vitest + Testing Library (frontend unit), pytest with moto (backend unit)
**Target Platform**: Next.js frontend (browser), AWS Lambda (backend, no changes)
**Project Type**: Web application (TypeScript frontend + Python backend)
**Performance Goals**: Error state renders within 500ms of API failure
**Constraints**: Must not break existing heatmap tests (heat-map-cell.test.tsx, heat-map-legend.test.tsx). Must use existing `emitErrorEvent` pattern for observability.
**Scale/Scope**: 2-3 frontend files modified, 0-1 backend files modified, 2 new test files, 1 new test file (backend)

## Constitution Check

*GATE: Must pass before implementation.*

| Gate | Status | Notes |
|------|--------|-------|
| Parameterized queries / no SQL injection | N/A | No database queries in this feature |
| Implementation accompaniment (unit tests) | PASS | Frontend: vitest tests for error states. Backend: pytest for partial failure behavior |
| Deterministic time handling in tests | N/A | No time-dependent logic |
| External dependency mocking | PASS | API responses mocked in vitest tests |
| GPG-signed commits | PASS | Standard workflow |
| Feature branch workflow | PASS | Branch `1231-heatmap-error-resilience` created |
| SAST/lint pre-push | PASS | `make validate` before push |
| Secrets management | N/A | No secrets involved |
| Least-privilege IAM | N/A | No IAM changes |

No violations. No complexity tracking needed.

## Project Structure

### Documentation (this feature)

```text
specs/1231-heatmap-error-resilience/
├── spec.md              # Feature specification
├── plan.md              # This file
├── research.md          # Research findings
├── quickstart.md        # Implementation quickstart
├── checklists/
│   └── requirements.md  # Specification quality checklist
└── tasks.md             # Task breakdown
```

### Source Code (files to modify)

```text
frontend/
├── src/
│   ├── components/
│   │   └── heatmap/
│   │       ├── heat-map-view.tsx       # MODIFY: Add defensive guards on ticker.sentiment access
│   │       └── heat-map-error.tsx      # NEW: Error state component for heatmap
│   ├── hooks/
│   │   └── use-sentiment.ts           # READ-ONLY: Understand react-query error surfacing
│   ├── lib/
│   │   └── api/
│   │       └── client.ts              # READ-ONLY: Understand error shapes (ApiClientError)
│   └── types/
│       └── sentiment.ts               # READ-ONLY: TickerSentiment type (already correct: Record<string, SentimentScore>)
└── tests/
    └── unit/
        └── components/
            └── heatmap/
                ├── heat-map-cell.test.tsx    # EXISTING: Must not break
                ├── heat-map-legend.test.tsx  # EXISTING: Must not break
                └── heat-map-view.test.tsx    # NEW: Error state tests

tests/
└── unit/
    └── test_sentiment_partial_failure.py    # NEW: Backend partial failure behavior tests
```

**Structure Decision**: Existing web application structure. Primary changes are frontend-only (defensive coding + error UI). Backend changes are test-only (locking existing partial failure behavior). No API contract changes.

## Adversarial Review Findings (2026-03-21)

### Finding 1: The crash path is real but narrow (CONFIRMED)

The crash occurs at `heat-map-view.tsx:34`: `const sentimentEntries = Object.entries(ticker.sentiment)`. If `ticker.sentiment` is `undefined`, `null`, or a non-object, this throws `TypeError: Cannot convert undefined or null to object`.

However, the `TickerSentiment` TypeScript type already declares `sentiment: Record<string, SentimentScore>`, and the backend always returns this field (even as empty `{}`). The crash can only happen if:
1. The API returns an error shape that bypasses the `SentimentData` type (e.g., `{error: {code, message}}` which has no `tickers` field)
2. Network/timeout errors cause react-query to surface `undefined` data

Both are handled by react-query's `isError`/`isLoading` states, but only if the parent component checks them BEFORE passing data to `HeatMapView`. Currently, `HeatMapView` is not integrated into any page, so the integration point is where the guard must be placed.

### Finding 2: HeatMapView is not yet mounted in any page (IMPORTANT)

The component is exported from `components/heatmap/index.ts` but no page imports or renders it. The `configs/page.tsx` shows configurations, and `page.tsx` (dashboard home) shows the price-sentiment chart. The heatmap will likely be integrated in a future feature (or already planned).

This means the defensive coding is preventative -- we are hardening the component before its first real use. This is the right time to add error handling.

### Finding 3: Backend partial failure behavior is correct but untested (MODERATE)

The `get_sentiment_by_configuration` function at lines 308-347 has a per-ticker try/except that catches query failures and appends `TickerSentimentData(symbol=symbol, sentiment={})`. This is correct behavior. However, there are no unit tests that explicitly verify this partial failure path. Adding a test locks this behavior.

### Finding 4: CompactHeatMapGrid has same vulnerability (MINOR)

The mobile `CompactHeatMapGrid` at `heat-map-grid.tsx:228-254` accesses `cell.score` at line 246. If cells array contains `undefined` entries (shouldn't happen with current code, but defensive check is cheap), this would crash. The desktop grid already has a null check at line 138 (`{cell ? ... : <HeatMapEmptyCell />}`), but the compact grid does not.
