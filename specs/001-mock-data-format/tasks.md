# Tasks: Fix Mock OHLC/Sentiment Data Format

**Feature Branch**: `001-mock-data-format`
**Spec**: [spec.md](spec.md) | **Plan**: [plan.md](plan.md) | **Data Model**: [data-model.md](data-model.md)
**Target Repo**: `~/projects/sentiment-analyzer-gsk`
**Target File**: `frontend/tests/e2e/helpers/mock-api-data.ts`

## Dependency Graph

```
Phase 0: Setup
  T-000 (verify source models) ─┐
  T-001 (verify existing mock)  ─┤
                                  ├─> Phase 1: Foundational
                                  │     T-010 (OHLCResponse skeleton)
                                  │     T-011 (SentimentHistoryResponse skeleton)
                                  │         │
                                  ├─> Phase 2: US1 (Field Completeness)
                                  │     T-020 (PriceCandle fields) ──────── depends on T-010
                                  │     T-021 (OHLCResponse metadata) ──── depends on T-010
                                  │     T-022 (SentimentPoint fields) ──── depends on T-011
                                  │     T-023 (SentimentHistoryResponse metadata) ─ depends on T-011
                                  │     T-024 (count invariant OHLC) ──── depends on T-020
                                  │     T-025 (count invariant sentiment) depends on T-022
                                  │     T-026 (date format correction) ── depends on T-020, T-022
                                  │         │
                                  ├─> Phase 3: US2 (Value Constraints)
                                  │     T-030 (numeric constraints OHLC) ── depends on T-020
                                  │     T-031 (numeric constraints sentiment) depends on T-022
                                  │     T-032 (enum values OHLC) ────────── depends on T-021
                                  │     T-033 (enum values sentiment) ───── depends on T-022
                                  │     T-034 (nullable field variants) ─── depends on T-020, T-022
                                  │     T-035 (empty array variants) ────── depends on T-024, T-025
                                  │         │
                                  └─> Phase 4: Polish
                                        T-040 (Playwright smoke test)
                                        T-041 (cross-reference Pydantic models)
```

## Parallelization Guide

```
Can run in parallel:
  T-000 || T-001           (both are read-only verification)
  T-010 || T-011           (OHLC skeleton and sentiment skeleton are independent)
  T-020 || T-022           (PriceCandle and SentimentPoint are independent)
  T-021 || T-023           (response metadata are independent)
  T-024 || T-025           (count invariants are independent)
  T-030 || T-031           (numeric constraints are independent)
  T-032 || T-033           (enum constraints are independent)

Must run sequentially:
  T-000/T-001 -> T-010/T-011 -> T-020..T-026 -> T-030..T-035 -> T-040/T-041
```

---

## Phase 0: Setup (Verification)

- [ ] **T-000** [P1] Read Pydantic source models in target repo (`src/lambdas/shared/models/ohlc.py` and `src/lambdas/shared/models/sentiment_history.py`) to confirm field names, types, nullability, and enum values match data-model.md. Record any discrepancies before proceeding.

- [ ] **T-001** [P1] Read existing `frontend/tests/e2e/helpers/mock-api-data.ts` in target repo (if it exists) to identify current mock shape, missing fields, incorrect types, and wrong date formats. If the file does not exist, note that it must be created from scratch.

---

## Phase 1: Foundational (Response Skeletons)

- [ ] **T-010** [P1] [US1] Define or update the mock `OHLCResponse` object skeleton in `frontend/tests/e2e/helpers/mock-api-data.ts` with all 11 top-level fields from FR-001: `ticker`, `candles`, `time_range`, `start_date`, `end_date`, `count`, `source`, `cache_expires_at`, `resolution`, `resolution_fallback`, `fallback_message`. Use placeholder values; detail is filled in subsequent tasks.

- [ ] **T-011** [P1] [US1] Define or update the mock `SentimentHistoryResponse` object skeleton in `frontend/tests/e2e/helpers/mock-api-data.ts` with all 6 top-level fields from FR-002: `ticker`, `source`, `history`, `start_date`, `end_date`, `count`. Use placeholder values; detail is filled in subsequent tasks.

---

## Phase 2: US1 -- Mock Data Matches Production API Shape

### PriceCandle and SentimentPoint Fields

- [ ] **T-020** [P1] [US1] Populate the `candles` array in the mock OHLC response with at least 3 `PriceCandle` entries, each containing all 6 fields from FR-003: `date`, `open`, `high`, `low`, `close`, `volume`. Use realistic stock price values. At least one entry should use intraday ISO 8601 datetime (`"2026-03-28T14:30:00Z"`) and at least one should use daily `YYYY-MM-DD` format, per FR-006.
  **File**: `frontend/tests/e2e/helpers/mock-api-data.ts`

- [ ] **T-022** [P1] [US1] Populate the `history` array in the mock sentiment response with at least 3 `SentimentPoint` entries, each containing all 5 fields from FR-004: `date`, `score`, `source`, `confidence`, `label`. Use `YYYY-MM-DD` date format per FR-006. Vary the `source` across entries to cover multiple enum values.
  **File**: `frontend/tests/e2e/helpers/mock-api-data.ts`

### Response Metadata Completion

- [ ] **T-021** [P1] [US1] Set all OHLCResponse metadata fields to realistic values: `ticker` (e.g., `"AAPL"`), `time_range` (e.g., `"1D"`), `start_date`/`end_date` in `YYYY-MM-DD` format, `source` as `"tiingo"`, `cache_expires_at` as ISO 8601 datetime with Z suffix (e.g., `"2026-03-28T15:00:00Z"`), `resolution` (e.g., `"5min"`), `resolution_fallback` as `false`, `fallback_message` as `null`.
  **File**: `frontend/tests/e2e/helpers/mock-api-data.ts`

- [ ] **T-023** [P1] [US1] Set all SentimentHistoryResponse metadata fields to realistic values: `ticker` (e.g., `"AAPL"`), `source` (e.g., `"aggregated"`), `start_date`/`end_date` in `YYYY-MM-DD` format.
  **File**: `frontend/tests/e2e/helpers/mock-api-data.ts`

### Count Invariant

- [ ] **T-024** [P1] [US1] Ensure the `count` field in the mock OHLC response equals the length of the `candles` array (FR-005). Verify this is a literal number matching the array, not a computed expression.
  **File**: `frontend/tests/e2e/helpers/mock-api-data.ts`

- [ ] **T-025** [P1] [US1] Ensure the `count` field in the mock sentiment response equals the length of the `history` array (FR-005).
  **File**: `frontend/tests/e2e/helpers/mock-api-data.ts`

### Date Format Correction

- [ ] **T-026** [P1] [US1] Audit all date strings in mock data and correct any that violate FR-006/FR-011: intraday OHLC candle dates must be ISO 8601 with `Z` suffix, daily OHLC candle dates must be `YYYY-MM-DD`, all sentiment dates must be `YYYY-MM-DD`, `cache_expires_at` must be ISO 8601 with `Z` suffix. No naive datetimes, no offset notation.
  **File**: `frontend/tests/e2e/helpers/mock-api-data.ts`

---

## Phase 3: US2 -- Mock Data Respects Value Constraints

### Numeric Constraints

- [ ] **T-030** [P2] [US2] Verify all mock PriceCandle numeric values satisfy FR-007: `open > 0`, `high > 0`, `low > 0`, `close > 0`, `high >= low`, `volume >= 0` (when not null). Fix any violations.
  **File**: `frontend/tests/e2e/helpers/mock-api-data.ts`

- [ ] **T-031** [P2] [US2] Verify all mock SentimentPoint numeric values satisfy FR-007: `score` in `[-1.0, 1.0]`, `confidence` in `[0.0, 1.0]` (when not null). Include at least one negative score and one near-boundary score (e.g., `-0.85`, `0.92`).
  **File**: `frontend/tests/e2e/helpers/mock-api-data.ts`

### Enum Values

- [ ] **T-032** [P2] [US2] Verify OHLC `source` field uses only valid enum values from FR-008: `"tiingo"` or `"finnhub"`. Primary mock should use `"tiingo"`.
  **File**: `frontend/tests/e2e/helpers/mock-api-data.ts`

- [ ] **T-033** [P2] [US2] Verify all SentimentPoint `source` and `label` fields use only valid enum values from FR-008. Sources: `"tiingo"`, `"finnhub"`, `"our_model"`, `"aggregated"`. Labels: `"positive"`, `"neutral"`, `"negative"`, or `null`. Include at least 2 distinct source values and 2 distinct label values across entries.
  **File**: `frontend/tests/e2e/helpers/mock-api-data.ts`

### Nullable and Edge Case Variants

- [ ] **T-034** [P2] [US2] Ensure at least one `PriceCandle` has `volume: null` and at least one `SentimentPoint` has both `confidence: null` and `label: null`, per FR-009. Use explicit `null`, not `undefined` or omission.
  **File**: `frontend/tests/e2e/helpers/mock-api-data.ts`

- [ ] **T-035** [P2] [US2] Add empty-array response variants per FR-012: one OHLC mock with `candles: []`, `count: 0`, and valid `start_date`/`end_date`; one sentiment mock with `history: []`, `count: 0`, and valid `start_date`/`end_date`. Export these as separate named constants (e.g., `mockEmptyOhlcResponse`, `mockEmptySentimentResponse`).
  **File**: `frontend/tests/e2e/helpers/mock-api-data.ts`

---

## Phase 4: Polish (Validation)

- [ ] **T-040** [P1] Run Playwright tests in the target repo (`cd ~/projects/sentiment-analyzer-gsk/frontend && npx playwright test`) to confirm mock data changes do not break existing E2E tests. Fix any failures caused by the updated mock shape.

- [ ] **T-041** [P1] Final cross-reference: re-read the Pydantic models (`ohlc.py`, `sentiment_history.py`) and confirm every field, type, and constraint in the mock file matches the backend contract. Check the TypeScript types in `frontend/src/types/chart.ts` for consistency.

---

## FR Traceability Matrix

| FR | Task(s) | Description |
|----|---------|-------------|
| FR-001 | T-010, T-021 | OHLCResponse field completeness |
| FR-002 | T-011, T-023 | SentimentHistoryResponse field completeness |
| FR-003 | T-020 | PriceCandle field completeness |
| FR-004 | T-022 | SentimentPoint field completeness |
| FR-005 | T-024, T-025 | Count invariant |
| FR-006 | T-020, T-022, T-026 | Date format correctness |
| FR-007 | T-030, T-031 | Numeric constraints |
| FR-008 | T-032, T-033 | Enum value validity |
| FR-009 | T-034 | Nullable field coverage |
| FR-010 | T-000, T-032, T-033 | Enum values derived from contract |
| FR-011 | T-026 | UTC Z suffix requirement |
| FR-012 | T-035 | Empty array handling |

## Notes

- All code changes target `~/projects/sentiment-analyzer-gsk`, NOT this template repo.
- T-000 and T-001 are read-only verification steps -- they produce no code changes but inform all subsequent tasks.
- Many Phase 2 and Phase 3 tasks overlap in practice (e.g., T-020 and T-030 both touch PriceCandle values). During implementation, these will likely be done together in a single editing pass per mock object, but they are listed separately for traceability to distinct FRs.
- No dedicated test-writing tasks are included because the spec scope is mock data correction, not new test creation. Existing Playwright tests serve as the validation gate (T-040).

## Adversarial Review #3

**Reviewed**: 2026-03-29

- **Highest-risk task**: T-026 — date format correction (intraday ISO datetime vs daily YYYY-MM-DD) is the most likely source of JavaScript Date parsing bugs across timezone boundaries.
- **Most likely rework**: T-034 — resolution_fallback nullability confusion from clarification Q4 may lead to incorrect null variant. Verify against Pydantic model before writing.
- **CRITICAL/HIGH remaining**: 0
- **READY FOR IMPLEMENTATION**
