# Implementation Plan: Price Chart Playwright E2E Test Gaps

**Branch**: `1281-price-chart-e2e-gaps` | **Date**: 2026-03-29 | **Spec**: [spec.md](spec.md)
**Input**: Feature specification from `/specs/1281-price-chart-e2e-gaps/spec.md`

## Summary

Fill coverage gaps in the price chart Playwright E2E tests: empty data state, resolution fallback banner, and API error state with retry. All tests verify existing component behavior via mock route interception -- no new UI logic is added.

## Technical Context

**Language/Version**: TypeScript (Playwright test files), targeting Node.js 18+
**Primary Dependencies**: `@playwright/test` (existing), `mock-api-data.ts` route interception (existing)
**Storage**: N/A (test infrastructure only)
**Testing**: Playwright Test (existing `sanity.spec.ts`, `dashboard-interactions.spec.ts`)
**Target Platform**: Desktop Chrome + Mobile Chrome Playwright projects
**Project Type**: Web application -- tests live in `frontend/tests/e2e/`
**Performance Goals**: Tests add < 30 seconds to CI run time (SC-003)
**Constraints**: No canvas-internal interactions (FR-006); must use `waitForResponse`/`waitForSelector` patterns, never `waitForTimeout`
**Scale/Scope**: 3 new test scenarios added to existing E2E suite

## Constitution Check

- No new production code -- test-only feature
- No infrastructure changes
- No cost impact
- GPG-signed commits required

## Project Structure

### Documentation (this feature)

```text
specs/1281-price-chart-e2e-gaps/
├── spec.md              # Feature specification
├── plan.md              # This file
└── tasks.md             # Task list
```

### Source Code (repository root)

```text
frontend/
├── src/components/
│   └── price-sentiment-chart.tsx   # Target component (READ ONLY -- verify code paths)
├── tests/e2e/
│   ├── sanity.spec.ts              # Existing chart tests (841 lines)
│   ├── dashboard-interactions.spec.ts  # Existing interaction tests
│   ├── mock-api-data.ts            # Mock route interception infrastructure
│   └── chart-edge-cases.spec.ts    # NEW -- gap coverage tests
└── playwright.config.ts
```

**Structure Decision**: New test file `chart-edge-cases.spec.ts` keeps gap tests isolated from the already-large `sanity.spec.ts` (841 lines). Uses existing mock infrastructure from `mock-api-data.ts`.

## Key Design Decisions

1. **Separate test file**: `chart-edge-cases.spec.ts` rather than appending to `sanity.spec.ts` -- the existing file is 841 lines and covers happy-path scenarios. Edge cases are a distinct concern.

2. **Mock-first testing**: All scenarios use `page.route()` interception to control OHLC API responses. No real API calls, no flake from network.

3. **FR-007 gate**: T-001 reads the component source first. If empty/error/fallback rendering code paths do not exist, corresponding tests are documented as TODOs with findings, not written as fiction.

4. **Selector reuse**: Tests use existing `[role="img"][aria-label*="Price and sentiment"]` selectors and aria-label data count extraction patterns (FR-005).
