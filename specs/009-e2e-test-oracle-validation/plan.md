# Implementation Plan: E2E Test Oracle Validation

**Branch**: `009-e2e-test-oracle-validation` | **Date**: 2025-11-29 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `/specs/009-e2e-test-oracle-validation/spec.md`

## Summary

Improve E2E test quality by implementing proper oracle validation for sentiment tests, eliminating dual-outcome assertions (`assert A or B`), extending synthetic data coverage across all preprod tests, and adding failure injection tests for processing layer error handling. This feature addresses findings from the E2E test audit conducted 2025-11-29.

## Technical Context

**Language/Version**: Python 3.13
**Primary Dependencies**: pytest, pytest-asyncio, httpx, boto3, moto (unit tests only)
**Storage**: DynamoDB (preprod - real AWS, no mocks for E2E)
**Testing**: pytest with synthetic data generators and test oracle pattern
**Target Platform**: AWS Lambda (preprod environment)
**Project Type**: single
**Performance Goals**: E2E test suite completes in <15 minutes
**Constraints**: Tests must be deterministic with seeded random data; skip rate <15%
**Scale/Scope**: ~20 E2E test files, ~130 test cases

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Requirement | Section | Status | Notes |
|-------------|---------|--------|-------|
| Synthetic Test Data for E2E | 7.209-230 | ALIGNED | Spec requires test oracle computing expected values from synthetic data |
| Test Oracle Pattern | 7.214-216 | ALIGNED | Constitution mandates "test oracle that calculates correct answers from input data" |
| External Dependency Mocking | 7.199-207 | ALIGNED | All external APIs (Tiingo, Finnhub, SendGrid) mocked in E2E |
| Environment Matrix | 7.181-196 | ALIGNED | Feature targets PREPROD E2E tests with real AWS, mocked external APIs |
| Implementation Accompaniment | 7.231-238 | ALIGNED | All test improvements will include unit tests for oracle logic |
| Functional Integrity | 7.240-251 | ALIGNED | Eliminates tests with trivial outcomes that mask regressions |

**No constitution violations detected.** Feature aligns with Section 7 Testing & Validation requirements.

## Project Structure

### Documentation (this feature)

```text
specs/009-e2e-test-oracle-validation/
├── plan.md              # This file (/speckit.plan command output)
├── research.md          # Phase 0 output (/speckit.plan command)
├── data-model.md        # Phase 1 output (/speckit.plan command)
├── quickstart.md        # Phase 1 output (/speckit.plan command)
├── contracts/           # Phase 1 output (/speckit.plan command)
└── tasks.md             # Phase 2 output (/speckit.tasks command - NOT created by /speckit.plan)
```

### Source Code (repository root)

```text
tests/
├── fixtures/
│   └── synthetic/
│       ├── test_oracle.py       # Extended oracle with sentiment comparison
│       ├── ticker_generator.py  # Existing synthetic ticker data
│       ├── news_generator.py    # Existing synthetic news data
│       └── sentiment_generator.py # Existing synthetic sentiment data
├── e2e/
│   ├── conftest.py              # Updated fixtures with oracle validation
│   ├── test_sentiment.py        # Fixed oracle comparison tests
│   ├── test_rate_limiting.py    # Split dual-outcome assertions
│   ├── test_*.py                # All 20 test files updated
│   └── fixtures/                # Synthetic handlers (Tiingo, Finnhub, SendGrid)
└── unit/
    └── fixtures/
        └── test_oracle_unit.py  # Unit tests for oracle logic
```

**Structure Decision**: Single project structure. Changes are confined to the `tests/` directory, specifically enhancing the existing E2E test framework with proper oracle validation and deterministic synthetic data.

## Complexity Tracking

> No constitution violations requiring justification.
