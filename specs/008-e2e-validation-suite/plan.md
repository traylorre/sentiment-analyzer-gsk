# Implementation Plan: E2E Validation Suite

**Branch**: `008-e2e-validation-suite` | **Date**: 2025-11-28 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `/specs/008-e2e-validation-suite/spec.md`

## Summary

Comprehensive E2E test suite validating all service use-cases against preprod environment. Tests execute exclusively in CI pipeline (GitHub Actions) with isolated test data per run, synthetic data generators for external APIs (Tiingo/Finnhub), full auth flow testing, and observability validation (CloudWatch logs, metrics, X-Ray traces).

## Technical Context

**Language/Version**: Python 3.13
**Primary Dependencies**: pytest, pytest-asyncio, httpx, boto3, moto (for local unit tests only), aws-xray-sdk
**Storage**: DynamoDB (preprod - real AWS, no mocks for E2E)
**Testing**: pytest with JUnit XML output, coverage reports
**Target Platform**: GitHub Actions CI runner → AWS preprod environment
**Project Type**: Test suite (extends existing `tests/` structure)
**Performance Goals**: Individual test < 60s, full suite < 30 minutes
**Constraints**: Preprod-only execution, isolated test data, no external API calls (synthetic data)
**Scale/Scope**: 12 user stories, ~50+ test cases covering all API endpoints

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Constitution Requirement | Status | Notes |
|-------------------------|--------|-------|
| **7) Testing & Validation** | ✅ PASS | E2E tests in preprod with real AWS, mocked external APIs per constitution |
| **Environment Matrix** | ✅ PASS | PREPROD mirrors PROD, E2E tests only, mock external APIs, real AWS |
| **External Dependency Mocking** | ✅ PASS | Tiingo/Finnhub/SendGrid mocked via synthetic data generators |
| **Synthetic Test Data** | ✅ PASS | Deterministic synthetic data with seed, test oracle pattern |
| **Implementation Accompaniment** | ✅ PASS | All test code has corresponding validation |
| **8) Git Workflow** | ✅ PASS | GPG-signed commits, feature branch, no bypass |
| **5) Deployment** | ✅ PASS | Uses existing preprod infrastructure via Terraform |
| **6) Observability** | ✅ PASS | Validates CloudWatch logs, metrics, X-Ray traces |
| **3) Security** | ✅ PASS | Uses GitHub Secrets for AWS credentials, no secrets in code |

**Gate Result**: PASS - All constitution requirements satisfied

## Project Structure

### Documentation (this feature)

```text
specs/008-e2e-validation-suite/
├── plan.md              # This file
├── research.md          # Phase 0 output
├── data-model.md        # Phase 1 output
├── quickstart.md        # Phase 1 output
├── contracts/           # Phase 1 output (test contracts/fixtures)
└── tasks.md             # Phase 2 output (/speckit.tasks)
```

### Source Code (repository root)

```text
tests/
├── e2e/                         # E2E test suite (PREPROD ONLY)
│   ├── conftest.py              # Shared fixtures, TestContext, synthetic data
│   ├── fixtures/                # Synthetic data generators
│   │   ├── __init__.py
│   │   ├── tiingo.py            # Tiingo synthetic responses
│   │   ├── finnhub.py           # Finnhub synthetic responses
│   │   ├── sendgrid.py          # SendGrid synthetic responses
│   │   └── ohlc.py              # OHLC price data for ATR
│   ├── helpers/                 # Test utilities
│   │   ├── __init__.py
│   │   ├── auth.py              # Auth flow helpers (anonymous, magic link, OAuth)
│   │   ├── api_client.py        # Preprod API client wrapper
│   │   ├── cloudwatch.py        # CloudWatch log/metrics query helpers
│   │   ├── xray.py              # X-Ray trace query helpers
│   │   └── cleanup.py           # Test data cleanup utilities
│   ├── test_auth_anonymous.py   # US1: Anonymous session tests
│   ├── test_auth_magic_link.py  # US1: Magic link auth tests
│   ├── test_auth_oauth.py       # US2: OAuth flow tests
│   ├── test_config_crud.py      # US3: Configuration CRUD tests
│   ├── test_sentiment.py        # US4: Sentiment/volatility data tests
│   ├── test_alerts.py           # US5: Alert rule lifecycle tests
│   ├── test_notifications.py    # US6: Notification pipeline tests
│   ├── test_rate_limiting.py    # US7: Rate limiting tests
│   ├── test_circuit_breaker.py  # US8: Circuit breaker tests
│   ├── test_ticker_validation.py # US9: Ticker validation tests
│   ├── test_sse.py              # US10: SSE streaming tests
│   ├── test_observability.py    # US11: CloudWatch/X-Ray tests
│   └── test_market_status.py    # US12: Market status tests
├── unit/                        # Existing unit tests (LOCAL/DEV only)
├── contract/                    # Existing contract tests
└── integration/                 # Existing integration tests

.github/
└── workflows/
    └── e2e-preprod.yml          # E2E test workflow for preprod
```

**Structure Decision**: Extends existing `tests/` structure with new `tests/e2e/` directory. Follows constitution's environment matrix where E2E tests run only in preprod with real AWS resources and mocked external APIs.

## Complexity Tracking

> No violations - all requirements align with constitution.
