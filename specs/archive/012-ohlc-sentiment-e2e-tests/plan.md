# Implementation Plan: OHLC & Sentiment History E2E Test Suite

**Branch**: `012-ohlc-sentiment-e2e-tests` | **Date**: 2025-12-01 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `/specs/012-ohlc-sentiment-e2e-tests/spec.md`

## Summary

Implement a comprehensive test suite for the OHLC price data and sentiment history endpoints introduced in Feature 011 (Price-Sentiment Overlay). The test suite validates system behavior under normal conditions, erratic data source behavior (network failures, malformed responses, rate limiting), and edge cases (boundary values, data consistency, ordering). Tests are organized as integration tests (with mock adapters) and E2E tests (against preprod with synthetic data).

## Technical Context

**Language/Version**: Python 3.13
**Primary Dependencies**: pytest, pytest-asyncio, httpx, responses, moto (unit tests only)
**Storage**: N/A (test suite - no storage requirements)
**Testing**: pytest with markers (`integration`, `e2e`, `preprod`, `unit`)
**Target Platform**: Linux (CI/CD pipeline)
**Project Type**: Single project (test suite extending existing codebase)
**Performance Goals**: Integration tests < 5 minutes, E2E tests < 10 minutes
**Constraints**: Mock all external APIs (Tiingo, Finnhub) except canary/smoke tests
**Scale/Scope**: 157 acceptance scenarios across 7 user stories

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

### Testing & Validation (Section 7)

| Requirement | Status | Implementation |
|-------------|--------|----------------|
| Environment Testing Matrix (LOCAL mirrors DEV with mocks) | COMPLIANT | Integration tests use mock adapters |
| PREPROD mirrors PROD (E2E without AWS mocks) | COMPLIANT | E2E tests run against real preprod infrastructure |
| External dependencies mocked in ALL environments | COMPLIANT | Tiingo/Finnhub adapters mocked via MockTiingoAdapter/MockFinnhubAdapter |
| Synthetic test data for E2E | COMPLIANT | Using existing generators: `tests/fixtures/synthetic/` |
| Implementation Accompaniment Rule | COMPLIANT | Test suite IS the implementation |
| Functional Integrity Principle | COMPLIANT | Tests verify endpoint behavior comprehensively |

### Security & Access Control (Section 3)

| Requirement | Status | Implementation |
|-------------|--------|----------------|
| Authentication required for endpoints | TESTED | US6 covers X-User-ID validation |
| Injection prevention | TESTED | US6 covers SQL/XSS injection attempts |
| Secrets not in source control | COMPLIANT | Tests use mock adapters, no API keys needed |

### Git Workflow & CI/CD (Section 8)

| Requirement | Status | Implementation |
|-------------|--------|----------------|
| Tests runnable in CI/CD | COMPLIANT | pytest with markers for selective execution |
| Never bypass pipeline | COMPLIANT | No bypass mechanisms in test code |

**Constitution Gate: PASS** - No violations found.

## Project Structure

### Documentation (this feature)

```text
specs/012-ohlc-sentiment-e2e-tests/
├── plan.md              # This file
├── spec.md              # Comprehensive test specification (157 scenarios)
├── research.md          # Phase 0 output (mock adapter patterns)
├── data-model.md        # Phase 1 output (test entity definitions)
├── quickstart.md        # Phase 1 output (running the tests)
├── contracts/           # Phase 1 output (API contract schemas)
│   ├── ohlc-response.md
│   └── sentiment-history-response.md
├── checklists/
│   └── requirements.md  # Validation checklist (created)
└── tasks.md             # Phase 2 output (NOT created by /speckit.plan)
```

### Source Code (repository root)

```text
# Existing test structure (extending)
tests/
├── fixtures/
│   ├── mocks/
│   │   ├── mock_tiingo.py      # Existing - extend with failure injection
│   │   ├── mock_finnhub.py     # Existing - extend with failure injection
│   │   └── failure_injector.py # NEW: Configurable failure modes
│   └── synthetic/
│       ├── ticker_generator.py  # Existing - extend for edge cases
│       ├── sentiment_generator.py # Existing
│       └── ohlc_generator.py    # NEW: Enhanced OHLC generator
├── integration/
│   ├── ohlc/                    # NEW: OHLC endpoint integration tests
│   │   ├── test_happy_path.py
│   │   ├── test_error_resilience.py
│   │   ├── test_boundary_values.py
│   │   ├── test_data_consistency.py
│   │   └── test_authentication.py
│   └── sentiment_history/       # NEW: Sentiment history integration tests
│       ├── test_happy_path.py
│       ├── test_source_filtering.py
│       ├── test_boundary_values.py
│       └── test_authentication.py
├── e2e/
│   └── test_ohlc_sentiment_preprod.py  # NEW: E2E preprod tests
└── conftest.py                  # Extend with new fixtures
```

**Structure Decision**: Extending existing test structure with new subdirectories for OHLC and sentiment history tests. Follows existing patterns established in `tests/integration/` and `tests/e2e/`.

## Complexity Tracking

> No constitution violations to justify.

| Pattern | Justification | Simpler Alternative Rejected |
|---------|---------------|------------------------------|
| Failure Injector class | Required by FR-008 to FR-014 (configurable failure modes) | Direct exception raising is less maintainable |
| Test Oracle pattern | Required by constitution (Section 7) for synthetic data validation | Hardcoded expected values are brittle |

## Phase 0: Research Summary

### Mock Adapter Extension Pattern

**Decision**: Extend existing `MockTiingoAdapter` and `MockFinnhubAdapter` with `FailureInjector` composition.

**Rationale**: Existing mock adapters already track calls and support `fail_mode`. Composition with a `FailureInjector` class provides fine-grained control over:
- HTTP error codes (400, 401, 404, 429, 500, 502, 503, 504)
- Connection errors (timeout, refused, DNS failure)
- Malformed responses (invalid JSON, empty, truncated)
- Field-level errors (missing fields, null values, NaN/Infinity)

**Alternatives Considered**:
- Inline failure logic in each test: Rejected - high duplication
- Separate mock classes per failure mode: Rejected - explosion of classes

### Test Data Generation Strategy

**Decision**: Use seeded random with deterministic test oracle.

**Rationale**: Constitution Section 7 requires synthetic data with computed expectations. Hash of ticker as seed ensures:
- Same ticker always produces same test data
- Different tickers have different but deterministic data
- Tests are reproducible across runs

**Implementation**: Extend `tests/fixtures/synthetic/` generators with:
- `generate_edge_case_ohlc()` for boundary values
- `generate_malformed_ohlc()` for invalid data scenarios
- `compute_expected_response()` for test oracle

### pytest Marker Strategy

**Decision**: Use hierarchical markers for test selection.

**Markers**:
- `@pytest.mark.integration` - All integration tests
- `@pytest.mark.e2e` - All E2E tests
- `@pytest.mark.preprod` - Preprod-only tests (excluded locally)
- `@pytest.mark.ohlc` - OHLC endpoint tests
- `@pytest.mark.sentiment_history` - Sentiment history tests
- `@pytest.mark.error_resilience` - Error injection tests
- `@pytest.mark.boundary` - Boundary value tests

**Usage**:
```bash
# Run all OHLC integration tests
pytest -m "integration and ohlc"

# Run boundary tests only
pytest -m "boundary"

# Exclude preprod tests (local development)
pytest -m "not preprod"
```

## Phase 1: Design Artifacts

### Key Test Entities

1. **FailureInjector**: Configures mock adapters with specific failure modes
2. **TestOracle**: Computes expected responses from synthetic input
3. **OHLCValidator**: Validates OHLC response structure and constraints
4. **SentimentValidator**: Validates sentiment history response structure

### API Contract Verification

Tests will verify responses against contracts defined in `specs/012-ohlc-sentiment-e2e-tests/contracts/`:
- `ohlc-response.md`: OHLCResponse schema with PriceCandle array
- `sentiment-history-response.md`: SentimentHistoryResponse schema with SentimentPoint array

### Integration with Existing Infrastructure

- **Adapter injection**: Use FastAPI dependency override to inject mock adapters
- **Fixture composition**: Build on existing `conftest.py` patterns
- **Synthetic data**: Extend existing generators in `tests/fixtures/synthetic/`

## Next Steps

1. Run `/speckit.tasks` to generate task breakdown
2. Implement `FailureInjector` class
3. Extend mock adapters with failure injection support
4. Implement test suites per user story
5. Add pytest markers and conftest fixtures
