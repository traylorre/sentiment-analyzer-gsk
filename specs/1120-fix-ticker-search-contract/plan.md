# Implementation Plan: Fix Ticker Search API Contract

**Branch**: `1120-fix-ticker-search-contract` | **Date**: 2026-01-02 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `/specs/1120-fix-ticker-search-contract/spec.md`

## Summary

Fix the API contract mismatch between frontend and backend for ticker search. The backend correctly returns a wrapped response `{results: [...]}` (RESTful best practice), but the frontend expects a bare array `TickerSearchResult[]`. The fix updates the frontend API client to unwrap the `results` field from the response.

## Technical Context

**Language/Version**: TypeScript 5.x (frontend), Next.js
**Primary Dependencies**: Axios (API client)
**Storage**: N/A (no data storage changes)
**Testing**: Jest/Vitest (frontend unit tests)
**Target Platform**: Web browser (Next.js frontend)
**Project Type**: Web application (frontend change only)
**Performance Goals**: N/A (no performance impact)
**Constraints**: Must maintain backward compatibility
**Scale/Scope**: Single file change in API client layer

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Requirement | Status | Notes |
|------------|--------|-------|
| Unit tests accompany implementation | PASS | Frontend tests will be added for API client |
| No pipeline bypass | PASS | Standard PR workflow |
| GPG-signed commits | PASS | Will use -S flag |
| Feature branch workflow | PASS | On branch 1120-fix-ticker-search-contract |

**All gates PASS** - proceeding with implementation.

## Project Structure

### Documentation (this feature)

```text
specs/1120-fix-ticker-search-contract/
├── plan.md              # This file
├── research.md          # Phase 0 output
├── quickstart.md        # Phase 1 output
└── tasks.md             # Phase 2 output
```

### Source Code (repository root)

```text
frontend/
├── src/
│   ├── lib/
│   │   └── api/
│   │       └── tickers.ts    # FILE TO MODIFY - update search() method
│   └── types/
│       └── ...               # Types already defined
└── tests/
    └── ...                   # Add test for API response handling
```

**Structure Decision**: Frontend-only change. Single file modification in `frontend/src/lib/api/tickers.ts` to unwrap the `results` field from backend response.

## Complexity Tracking

No constitution violations. This is a minimal, focused fix.
