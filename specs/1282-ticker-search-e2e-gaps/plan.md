# Implementation Plan: Ticker Search Playwright E2E Test Gaps

**Branch**: `1282-ticker-search-e2e-gaps` | **Date**: 2026-03-29 | **Spec**: [spec.md](spec.md)
**Input**: Feature specification from `/specs/1282-ticker-search-e2e-gaps/spec.md`

## Summary

Fill coverage gaps in the ticker search Playwright E2E tests: no-results autocomplete state, keyboard navigation (Arrow Up/Down/Enter/Escape), multi-ticker chip management, and duplicate ticker prevention. All tests verify existing `ticker-input.tsx` component behavior via mock route interception.

## Technical Context

**Language/Version**: TypeScript (Playwright test files), targeting Node.js 18+
**Primary Dependencies**: `@playwright/test` (existing), `mock-api-data.ts` route interception (existing)
**Storage**: N/A (test infrastructure only)
**Testing**: Playwright Test (existing `dashboard-interactions.spec.ts`, `error-visibility-search.spec.ts`)
**Target Platform**: Desktop Chrome + Mobile Chrome Playwright projects
**Project Type**: Web application -- tests live in `frontend/tests/e2e/`
**Performance Goals**: Tests add < 30 seconds to CI run time (SC-003)
**Constraints**: Must handle 1500ms search debounce via `waitForResponse`, never `waitForTimeout` (FR-008); keyboard wrap behavior must be verified from source before testing (FR-009)
**Scale/Scope**: 4 new test scenarios added to existing E2E suite

## Constitution Check

- No new production code -- test-only feature
- No infrastructure changes
- No cost impact
- GPG-signed commits required

## Project Structure

### Documentation (this feature)

```text
specs/1282-ticker-search-e2e-gaps/
├── spec.md              # Feature specification
├── plan.md              # This file
└── tasks.md             # Task list
```

### Source Code (repository root)

```text
frontend/
├── src/components/
│   └── ticker-input.tsx            # Target component (READ ONLY -- verify behavior)
├── tests/e2e/
│   ├── dashboard-interactions.spec.ts  # Existing ticker tests
│   ├── error-visibility-search.spec.ts # Existing error state tests
│   ├── mock-api-data.ts            # Mock route interception infrastructure
│   └── ticker-search-gaps.spec.ts  # NEW -- gap coverage tests
└── playwright.config.ts
```

**Structure Decision**: New test file `ticker-search-gaps.spec.ts` rather than appending to existing test files. The existing files cover happy-path and error scenarios; these gap tests cover keyboard navigation, no-results, multi-ticker management, and duplicate prevention -- distinct concerns that benefit from isolation.

## Key Design Decisions

1. **Separate test file**: `ticker-search-gaps.spec.ts` to avoid bloating existing files and keep edge-case tests isolated.

2. **Debounce handling**: All search assertions gate on `page.waitForResponse('**/api/v2/tickers/search**')` after typing, never `waitForTimeout(1500)`. This is a hard constraint from FR-008 and the AR#1 CRITICAL finding.

3. **FR-009 gate**: T-001 reads `ticker-input.tsx` to determine actual Arrow Up/Down wrap behavior and duplicate prevention logic before writing tests. No assumptions about unverified behavior.

4. **FR-010 chart switch wait**: Multi-ticker chip click assertions wait for observable DOM changes (aria-label update or OHLC network response), never assert immediately after interaction.

5. **Mock search responses**: Use `page.route('**/api/v2/tickers/search**')` to return controlled result sets (empty, single, multiple) for deterministic testing.
