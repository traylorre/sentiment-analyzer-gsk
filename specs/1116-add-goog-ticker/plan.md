# Implementation Plan: Add GOOG Ticker Support

**Branch**: `1116-add-goog-ticker` | **Date**: 2026-01-01 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `/specs/1116-add-goog-ticker/spec.md`

## Summary

Add GOOG (Alphabet Class C) ticker to the ticker search database. This is a data-only change requiring updates to `infrastructure/data/us-symbols.json` and the hardcoded fallback list in `src/lambdas/dashboard/tickers.py`. No code logic changes required - the existing ticker search and OHLC infrastructure already supports any valid ticker.

## Technical Context

**Language/Version**: N/A (data file changes only)
**Primary Dependencies**: N/A
**Storage**: JSON data file (`infrastructure/data/us-symbols.json`)
**Testing**: Existing unit tests validate ticker search; manual verification against Tiingo API
**Target Platform**: AWS Lambda (existing infrastructure)
**Project Type**: Data configuration change
**Performance Goals**: N/A (no performance impact - single ticker addition)
**Constraints**: Must match existing ticker entry format
**Scale/Scope**: Single ticker addition (GOOG)

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Requirement | Status | Notes |
|-------------|--------|-------|
| Testing & Validation (Section 7) | ✅ PASS | No new code logic; existing tests cover ticker search |
| Security (Section 3) | ✅ PASS | No secrets, no auth changes |
| Git Workflow (Section 8) | ✅ PASS | Feature branch, GPG-signed commits |
| Tech Debt (Section 9) | ✅ PASS | No workarounds or shortcuts |

**No violations.** This is a minimal data configuration change.

## Project Structure

### Documentation (this feature)

```text
specs/1116-add-goog-ticker/
├── spec.md              # Feature specification
├── plan.md              # This file
├── research.md          # Phase 0 output (minimal - no research needed)
├── checklists/
│   └── requirements.md  # Spec quality checklist
└── tasks.md             # Phase 2 output
```

### Source Code (files to modify)

```text
infrastructure/
└── data/
    └── us-symbols.json          # Add GOOG entry (FR-001)

src/lambdas/dashboard/
└── tickers.py                   # Add GOOG to COMMON_TICKERS fallback list (FR-006)
```

**Structure Decision**: Existing repository structure - no new files or directories needed.

## Implementation Approach

### Phase 1: Add GOOG to Ticker Database

1. **Add GOOG entry to `us-symbols.json`**
   - Copy format from GOOGL entry
   - Update: symbol="GOOG", name="Alphabet Inc - Class C"
   - Preserve: exchange="NASDAQ", is_active=true

2. **Add GOOG to fallback list in `tickers.py`**
   - Locate `COMMON_TICKERS` or similar hardcoded list
   - Add "GOOG" alongside "GOOGL"

### Verification

- Search API returns GOOG for query "GOOG"
- Search API returns both GOOG and GOOGL for query "GOO"
- OHLC endpoint returns valid data for GOOG ticker

## Complexity Tracking

> No violations to justify. This is a minimal, straightforward data change.

## Dependencies

- None. GOOG support already exists in:
  - Tiingo API (verified: returns valid metadata and price data)
  - OHLC endpoint logic (handles any valid ticker)
  - Frontend search component (data-driven rendering)
