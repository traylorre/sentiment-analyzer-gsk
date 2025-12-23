# Implementation Plan: Skeleton Loading UI

**Branch**: `1021-skeleton-loading-ui` | **Date**: 2025-12-22 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `/specs/1021-skeleton-loading-ui/spec.md`

## Summary

Add skeleton loading UI components to the sentiment dashboard, replacing all loading spinners with skeleton placeholders that show during initial page load, resolution switches, and data refreshes. Implements parent spec FR-011 (never show loading spinners) and SC-009 (zero loading spinners visible).

## Technical Context

**Language/Version**: JavaScript ES6+ (vanilla JS, no framework)
**Primary Dependencies**: None (pure CSS animations, vanilla JS state management)
**Storage**: N/A (client-side only, no persistence)
**Testing**: Playwright E2E for visual verification, Jest unit tests for state logic
**Target Platform**: Modern browsers (Chrome, Firefox, Safari, Edge)
**Project Type**: Frontend dashboard (src/dashboard/)
**Performance Goals**: Skeleton appears within 100ms, transition to content under 300ms
**Constraints**: Must work without framework dependencies, CSS-only shimmer animation
**Scale/Scope**: 3 skeleton components (chart, ticker list, resolution selector)

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Section | Gate | Status | Notes |
|---------|------|--------|-------|
| Section 5 | IaC (Terraform) | N/A | Frontend-only, no infra changes |
| Section 6 | Observability | N/A | Client-side, no CloudWatch |
| Section 7 | Testing | PASS | Playwright E2E + Jest unit tests |
| Amendment 1.5 | Deterministic time | PASS | No time-sensitive logic |

**Result**: 4/4 PASS (2 N/A, 2 PASS) - Ready for Phase 0

## Project Structure

### Documentation (this feature)

```text
specs/1021-skeleton-loading-ui/
├── spec.md              # Feature specification
├── plan.md              # This file
├── research.md          # Phase 0 output
├── quickstart.md        # Phase 1 output
└── tasks.md             # Phase 2 output (/speckit.tasks)
```

### Source Code (repository root)

```text
src/dashboard/
├── app.js               # Main application logic (add skeleton state management)
├── styles.css           # Styles (add skeleton CSS classes and shimmer animation)
├── config.js            # Configuration (skeleton timing constants)
└── index.html           # Entry point (skeleton HTML structure)

tests/
├── e2e/
│   └── test_skeleton_loading.py  # Playwright E2E tests
└── unit/
    └── dashboard/
        └── test_skeleton_state.js  # Jest unit tests for skeleton state
```

**Structure Decision**: Single frontend project under src/dashboard/. Tests split between E2E (Python/Playwright for visual verification) and unit (Jest for state logic).

## Complexity Tracking

No violations. Simple CSS + JS implementation with no new dependencies.
