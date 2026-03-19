# Implementation Plan: Frontend Error Visibility

**Branch**: `1226-frontend-error-visibility` | **Date**: 2026-03-19 | **Spec**: [spec.md](spec.md)
**Input**: Feature specification from `/specs/1226-frontend-error-visibility/spec.md`

## Summary

The frontend silently swallows API errors — ticker search shows "No tickers found" for both empty results and unreachable APIs, which masked a 3-day outage. This feature adds three capabilities: (1) distinct error/empty states in ticker search, (2) a request-outcome-driven health banner that appears after sustained failures, and (3) auth degradation notifications. All detection is passive (no polling) with structured console logging for test observability.

## Technical Context

**Language/Version**: TypeScript ^5 / Next.js 14.2.21 / React ^18
**Primary Dependencies**: @tanstack/react-query ^5.90.11, zustand ^5.0.8, sonner ^2.0.7
**Storage**: N/A (client-side state only, no persistence)
**Testing**: Playwright (E2E), Jest/Vitest (unit — to be confirmed from existing test setup)
**Target Platform**: Web browser (desktop + mobile responsive), deployed via AWS Amplify
**Project Type**: Web application (frontend-only changes)
**Performance Goals**: Zero additional API requests; health detection derived from existing user-triggered requests
**Constraints**: Banner must not flash on transient errors (3+ failures in 60s threshold); console events must be interceptable by Playwright
**Scale/Scope**: ~8 files modified/created, 3 user stories, 11 functional requirements

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Gate | Status | Notes |
|------|--------|-------|
| Implementation accompaniment (unit tests) | PASS | All new stores/hooks will have unit tests |
| GPG-signed commits | PASS | Standard workflow |
| No pipeline bypass | PASS | Standard PR flow |
| Security: no unauthenticated endpoints | PASS | Feature adds no endpoints; health detection is passive |
| Deterministic time handling | PASS | Sliding window uses timestamps for 60s pruning. Unit tests MUST use fake timers (jest.useFakeTimers) to avoid flaky time-dependent assertions. |
| Pre-push checklist | PASS | `make validate` + `make test-local` before push |

No constitution violations. No complexity tracking needed.

## Project Structure

### Documentation (this feature)

```text
specs/1226-frontend-error-visibility/
├── plan.md              # This file
├── research.md          # Phase 0 output
├── data-model.md        # Phase 1 output
├── quickstart.md        # Phase 1 output
└── tasks.md             # Phase 2 output (/speckit.tasks)
```

### Source Code (frontend-only)

```text
frontend/src/
├── stores/
│   └── api-health-store.ts          # NEW: tracks request outcomes, failure window, banner state
├── hooks/
│   └── use-api-health.ts            # NEW: hook that wires store to React Query global error handler
├── components/
│   ├── dashboard/
│   │   └── ticker-input.tsx          # MODIFIED: add error/empty state distinction
│   └── ui/
│       └── api-health-banner.tsx     # NEW: persistent connectivity banner component
├── lib/
│   └── api/
│       └── client.ts                 # MODIFIED: emit structured console events on error
└── app/
    └── providers.tsx                 # MODIFIED: wire global error handler + health banner

frontend/tests/
├── unit/
│   ├── stores/
│   │   └── api-health-store.test.ts  # NEW: failure window, threshold, recovery logic
│   └── components/
│       └── ticker-input-error.test.ts # NEW: error vs empty state rendering
└── e2e/
    └── error-visibility.spec.ts      # NEW: Playwright tests for banner + search errors
```

**Structure Decision**: Frontend-only changes. New files follow existing directory conventions (stores/, hooks/, components/ui/). No backend changes. No new directories created — all files placed in existing structure.
