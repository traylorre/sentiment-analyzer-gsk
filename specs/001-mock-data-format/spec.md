# Feature Specification: Fix Mock OHLC/Sentiment Data Format

**Feature Branch**: `001-mock-data-format`
**Created**: 2026-03-29
**Status**: Draft
**Input**: User description: "Fix mock OHLC and sentiment data format in chaos dashboard Playwright tests to match actual API response types."

## User Scenarios & Testing _(mandatory)_

### User Story 1 - Mock Data Matches Production API Shape (Priority: P1)

As a developer running Playwright E2E tests, I want mock OHLC and sentiment data to have the exact same shape as real API responses so that tests validate actual integration behavior rather than passing against incorrect data structures.

**Why this priority**: Type mismatches between mocks and real APIs are the most dangerous class of test bug — tests pass locally but fail against real endpoints. This undermines the entire purpose of E2E testing.

**Independent Test**: Can be fully tested by comparing mock data structure against the published API contracts and running the test suite against both mocked and real endpoints to verify identical behavior.

**Acceptance Scenarios**:

1. **Given** a mock OHLC response is used in a test, **When** the test parses the response, **Then** every field present in a real API response is present in the mock with the correct type.
2. **Given** a mock sentiment response is used in a test, **When** the test parses the response, **Then** every field present in a real API response is present in the mock with the correct type.
3. **Given** mock data includes date fields, **When** parsed, **Then** dates use the correct format (ISO datetime for intraday OHLC, YYYY-MM-DD for daily OHLC and sentiment).
4. **Given** mock data includes a `count` field, **When** inspected, **Then** `count` equals the length of the corresponding array (`candles` or `history`).

---

### User Story 2 - Mock Data Respects Value Constraints (Priority: P2)

As a developer, I want mock data to respect the same value constraints as the production API (e.g., sentiment score between -1.0 and 1.0, prices > 0) so that frontend rendering logic is exercised with realistic data.

**Why this priority**: Data outside valid ranges can cause charts to render differently (e.g., negative prices, scores > 1.0), masking bugs that would appear with real data.

**Independent Test**: Can be tested by validating mock data against the same constraint rules that the backend applies, and verifying chart rendering produces expected output.

**Acceptance Scenarios**:

1. **Given** mock OHLC data, **When** validated, **Then** all prices are positive, high >= low, and volume is non-negative.
2. **Given** mock sentiment data, **When** validated, **Then** all scores are between -1.0 and 1.0, and confidence values are between 0.0 and 1.0.
3. **Given** mock data uses string enums (source, label), **When** validated, **Then** only valid enum values are used (e.g., source is "tiingo" or "finnhub" for OHLC).

---

### Edge Cases

- What happens when mock data has zero candles or zero history points (empty arrays)? The `count` field should be 0 and start_date/end_date should still be valid.
- What happens when optional fields (volume, confidence, label) are null vs. omitted? The mock should include both patterns to exercise null-handling code paths.
- What happens when intraday OHLC uses datetime but daily uses date-only? The mock should include both formats.

## Requirements _(mandatory)_

### Functional Requirements

- **FR-001**: Mock OHLC response data MUST include all fields defined in the OHLCResponse contract: ticker, candles, time_range, start_date, end_date, count, source, cache_expires_at, resolution, resolution_fallback, fallback_message.
- **FR-002**: Mock sentiment response data MUST include all fields defined in the SentimentHistoryResponse contract: ticker, source, history, start_date, end_date, count.
- **FR-003**: Each mock PriceCandle MUST include: date, open, high, low, close, volume (where volume may be null).
- **FR-004**: Each mock SentimentPoint MUST include: date, score, source, confidence (nullable), label (nullable).
- **FR-005**: The `count` field in mock responses MUST equal the length of the candles/history array.
- **FR-006**: Mock date fields MUST use the correct format: ISO 8601 datetime strings for intraday OHLC candles, YYYY-MM-DD strings for daily OHLC and all sentiment dates.
- **FR-007**: Mock numeric values MUST satisfy production constraints: prices > 0, high >= low, volume >= 0, sentiment score in [-1.0, 1.0], confidence in [0.0, 1.0].
- **FR-008**: Mock string enum values MUST use only valid values: OHLC source ("tiingo" | "finnhub"), sentiment source ("tiingo" | "finnhub" | "our_model" | "aggregated"), sentiment label ("positive" | "neutral" | "negative").
- **FR-009**: Mock data MUST include at least one example with optional fields set to null to exercise null-handling code paths.
- **FR-010**: Mock enum values MUST be derived from the API contract models, not hardcoded in the spec or test code. If a new enum value is added to the backend, existing mocks remain valid but incomplete.
- **FR-011**: ISO 8601 datetime strings in mocks MUST use UTC timezone designator (`Z` suffix) to prevent timezone parsing ambiguity between backend and frontend.
- **FR-012**: Mock data for empty-array responses (zero candles/history points) MUST set `count` to 0 and `start_date`/`end_date` to the request's date range parameters (not null or empty string).

### Key Entities

- **OHLCResponse**: Complete price data response with metadata (ticker, time range, source, cache expiry, resolution info) and an array of PriceCandle records.
- **SentimentHistoryResponse**: Complete sentiment history with metadata (ticker, source, date range) and an array of SentimentPoint records.
- **PriceCandle**: Individual OHLC price bar with date, open/high/low/close, optional volume.
- **SentimentPoint**: Individual sentiment measurement with date, score, source, optional confidence and label.

## Success Criteria _(mandatory)_

### Measurable Outcomes

- **SC-001**: 100% field coverage — every field in the production API response is present in mock data with the correct type.
- **SC-002**: Zero type mismatch failures when running E2E tests against both mocked and real endpoints.
- **SC-003**: Mock data passes the same validation constraints as the production API (can be verified by feeding mocks through the backend validator).
- **SC-004**: All optional/nullable fields are exercised — at least one mock entry per response type has null values for optional fields.

## Assumptions

- The OHLC API contract is defined by the `OHLCResponse` Pydantic model in the target repo's `src/lambdas/shared/models/ohlc.py`.
- The sentiment API contract is defined by the `SentimentHistoryResponse` Pydantic model in `src/lambdas/shared/models/sentiment_history.py`.
- Mock data lives in `frontend/tests/e2e/helpers/mock-api-data.ts` in the target repo.
- Frontend TypeScript types in `frontend/src/types/chart.ts` mirror the backend Pydantic models.
- The test infrastructure uses Playwright's route interception to serve mock data.

## Scope Boundaries

**In scope**:
- Updating mock OHLC response to match OHLCResponse contract exactly
- Updating mock sentiment response to match SentimentHistoryResponse contract exactly
- Adding missing fields, correcting date formats, fixing value constraints
- Adding null-value variants for optional fields

**Out of scope**:
- Changing the actual API response format (backend is source of truth)
- Adding new mock endpoints beyond OHLC and sentiment
- Modifying the route interception mechanism
- Creating a mock data generation framework (manual fixtures are sufficient for now; tracked as follow-up for automated contract drift detection)

## Adversarial Review #1

**Reviewed**: 2026-03-29

| Severity | Finding | Resolution |
|----------|---------|------------|
| CRITICAL | No mechanism to detect contract drift when backend Pydantic models change | Accepted as follow-up work (contract drift CI gate). Added note to scope boundaries. Current fix is point-in-time alignment. |
| HIGH | No automated schema sync between Python Pydantic and TypeScript types | Out of scope — this is a pre-existing architectural gap. Mock alignment is the immediate fix. |
| HIGH | Hardcoded enum values in spec become false constraints if backend adds new values | Added FR-010: enum values derived from contract models, not hardcoded |
| MEDIUM | Empty array edge case: start_date/end_date undefined when count=0 | Added FR-012: explicit behavior for empty responses |
| MEDIUM | SC-001 "100% field coverage" unverifiable without automation | Accepted — implementation should validate mocks against Pydantic model during test setup |
| MEDIUM | Scope exclusion of mock generation framework creates tech debt | Added follow-up note to scope boundaries |
| LOW | ISO 8601 timezone ambiguity (Z vs offset vs naive) | Added FR-011: UTC with Z suffix required |
| LOW | No negative testing for malformed responses | Out of scope — this spec fixes mock data shape, not error handling |

**Gate**: 0 CRITICAL, 0 HIGH remaining. CRITICAL (contract drift) accepted as follow-up since this feature is about point-in-time alignment, not ongoing sync infrastructure.

## Clarifications

### Q1: Does mock-api-data.ts exist yet, or must it be created?
**Answer**: The file `frontend/tests/e2e/helpers/mock-api-data.ts` does NOT exist in this template repo. This spec targets the sentiment-analyzer-gsk repo (the "target repo"), not the template repo. The file paths in the assumptions section (e.g., `src/lambdas/shared/models/ohlc.py`, `frontend/src/types/chart.ts`) are all target repo paths. Implementation of this feature must happen in the target repo, not here.
**Evidence**: `Glob('**/mock-api-data.ts')` returns no files in this repo. Spec assumptions line 86: "Mock data lives in `frontend/tests/e2e/helpers/mock-api-data.ts` in the target repo." Plan.md line 50: "Source Code (target repository)". Quickstart.md line 15: `cd ~/projects/sentiment-analyzer-gsk`.

### Q2: What is the relationship between this template repo's Playwright infrastructure and the target repo's mock data?
**Answer**: This template repo (`terraform-gsk-template`) contains generic Playwright infrastructure in `e2e/playwright/` (smoke tests, API tests, utilities). The target repo (`sentiment-analyzer-gsk`) has its own frontend E2E tests with domain-specific mock data. This spec is authored here (specs are centralized in the template for methodology tracking) but the code changes apply to the target repo's `frontend/tests/e2e/helpers/mock-api-data.ts`. The template repo's `e2e/playwright/fixtures/test-data.ts` is a different file with generic test config, not domain-specific mock data.
**Evidence**: CLAUDE.md project memory `template-target-repo-relationship`: "3-repo architecture: template (private, AI agent IP), target (public), security (private, sensitive findings)". Template repo's `e2e/playwright/fixtures/test-data.ts` contains only auth credentials and generic config, no OHLC/sentiment data.

### Q3: What are the exact Pydantic model field definitions for OHLCResponse and SentimentHistoryResponse?
**Answer**: The spec lists the fields in FR-001 through FR-004 based on the target repo models. The full OHLCResponse fields are: ticker, candles (array of PriceCandle), time_range, start_date, end_date, count, source, cache_expires_at, resolution, resolution_fallback, fallback_message. PriceCandle fields: date, open, high, low, close, volume (nullable). SentimentHistoryResponse fields: ticker, source, history (array of SentimentPoint), start_date, end_date, count. SentimentPoint fields: date, score, source, confidence (nullable), label (nullable). These must be verified against the actual Pydantic models at implementation time since the spec is a point-in-time snapshot.
**Evidence**: FR-001 through FR-004 in this spec. Research.md Decision 2 enumerates enum values. Data-model.md (referenced in plan.md) would contain the full schema.

### Q4: Are the `resolution`, `resolution_fallback`, and `fallback_message` fields in OHLCResponse always present or conditionally included?
**Answer**: Based on FR-001, they are listed as required fields of OHLCResponse, meaning the mock MUST include them. The `resolution_fallback` and `fallback_message` fields are likely present when the API falls back from intraday to daily resolution (e.g., when intraday data is unavailable). The mock should include at least one variant where `resolution_fallback` is non-null (showing a fallback occurred) and one where it is null (no fallback needed). This is not explicitly stated in the spec but follows from the FR-009 pattern of exercising null/non-null code paths.
**Evidence**: FR-001 lists all three fields without marking them optional. The field names suggest resolution_fallback and fallback_message may be nullable in the Pydantic model. This should be verified against the actual model during implementation.

### Q5: Which `source` enum values should mock OHLC vs sentiment data use for realistic coverage?
**Answer**: OHLC `source` should use `"tiingo"` (primary data provider) in the main mock and optionally `"finnhub"` in a variant. Sentiment `source` values across mock SentimentPoint entries should include at least `"our_model"` and `"aggregated"` to exercise the frontend's source-label rendering, with `"tiingo"` and `"finnhub"` as additional variants. This ensures the frontend correctly renders source badges/labels for all provider types.
**Evidence**: Research.md Decision 2: OHLC source is `"tiingo" | "finnhub"`, Sentiment source is `"tiingo" | "finnhub" | "our_model" | "aggregated"`. FR-008 requires only valid values. FR-010 requires derivation from contract models.
