# Implementation Plan: Market Data Ingestion

**Branch**: `072-market-data-ingestion` | **Date**: 2025-12-09 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `/specs/072-market-data-ingestion/spec.md`

## Summary

Implement a robust market data ingestion system that collects sentiment data from multiple external sources (Tiingo, Finnhub) with automatic failover, deduplication, and operational alerting. The system must maintain <15 minute data freshness during market hours (9:30 AM - 4:00 PM ET) with 99.5% collection success rate.

**Key behaviors**:
- Scheduled collection every 5 minutes during market hours
- Primary/secondary source failover within 10 seconds on failure
- Deduplication via composite key (headline + source + publication date)
- Alert operations after 3 consecutive failures within 15 minutes
- Notify dependent systems within 30 seconds of new data storage

## Technical Context

**Language/Version**: Python 3.13 (per pyproject.toml `requires-python = ">=3.13"`)
**Primary Dependencies**: boto3 (AWS SDK), httpx/requests (HTTP client), pydantic (validation)
**Storage**: DynamoDB (existing infrastructure per constitution)
**Testing**: pytest with moto for AWS mocking, httpx-mock for external APIs
**Target Platform**: AWS Lambda (serverless, event-driven per constitution)
**Project Type**: Single serverless project with Lambda functions
**Performance Goals**: Collection completes within 60 seconds, failover within 10 seconds
**Constraints**: <15 min data staleness, $50/month data source budget
**Scale/Scope**: 10,000+ news items/day, 99.5% collection success rate

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Constitution Requirement | Status | Notes |
|-------------------------|--------|-------|
| **1) Functional: Ingest from external endpoints** | PASS | Tiingo/Finnhub APIs via adapters |
| **1) Functional: Multiple source types with pluggable adapters** | PASS | Existing adapter pattern in `src/lambdas/ingestion/adapters/` |
| **1) Functional: Deduplicate items** | PASS | Composite key deduplication defined |
| **1) Functional: Return sentiment with confidence** | PASS | Sentiment score + confidence per spec |
| **2) Non-Functional: 99.5% availability** | PASS | Multi-source failover supports this |
| **2) Non-Functional: P90 ≤500ms response** | N/A | Ingestion is batch, not request/response |
| **3) Security: Auth for admin endpoints** | PASS | Uses existing IAM/Lambda auth |
| **3) Security: TLS in transit** | PASS | HTTPS for all external API calls |
| **3) Security: Secrets in managed service** | PASS | AWS Secrets Manager per existing pattern |
| **5) Deployment: Serverless Lambda/SNS/SQS/DynamoDB** | PASS | Aligns with preferred architecture |
| **5) Deployment: Terraform IaC** | PASS | Existing infra pattern |
| **6) Observability: Structured logs** | PASS | CloudWatch integration |
| **6) Observability: Metrics export** | PASS | Collection success rate, error counts |
| **7) Testing: Unit + integration tests** | PASS | Required per Implementation Accompaniment Rule |
| **7) Testing: Mock external APIs** | PASS | Tiingo/Finnhub mocked in all environments |
| **7) Testing: Deterministic dates** | PASS | Fixed trading days for tests |
| **8) Git Workflow: GPG-signed commits** | PASS | Standard workflow |
| **10) Local SAST** | PASS | Bandit + Semgrep pre-push |

**Gate Result**: PASS - No violations. Proceed to Phase 0.

## Project Structure

### Documentation (this feature)

```text
specs/072-market-data-ingestion/
├── spec.md              # Feature specification (completed)
├── plan.md              # This file
├── research.md          # Phase 0 output
├── data-model.md        # Phase 1 output
├── quickstart.md        # Phase 1 output
├── contracts/           # Phase 1 output
└── tasks.md             # Phase 2 output (via /speckit.tasks)
```

### Source Code (repository root)

```text
src/lambdas/ingestion/
├── __init__.py
├── handler.py           # Lambda handler (existing, to be enhanced)
├── config.py            # Configuration (existing)
└── adapters/
    ├── __init__.py
    ├── base.py          # Base adapter class (existing)
    ├── tiingo.py        # Primary source adapter (to verify/enhance)
    └── finnhub.py       # Secondary source adapter (to verify/enhance)

src/lambdas/shared/
├── models/              # Shared data models
├── utils/               # Shared utilities
└── adapters/            # Shared adapter implementations (if needed)

tests/
├── unit/
│   └── ingestion/       # Unit tests for ingestion
└── integration/
    └── ingestion/       # Integration tests for ingestion
```

**Structure Decision**: Enhance existing `src/lambdas/ingestion/` structure. No new directories needed - feature extends existing codebase.

## Complexity Tracking

No constitution violations requiring justification.

---

## Phase 0: Research

*Output: research.md*

### Research Tasks

1. **Existing Adapter Implementation**: Review `src/lambdas/ingestion/adapters/` to understand current patterns
2. **Tiingo API**: Document endpoints, rate limits, response format, authentication
3. **Finnhub API**: Document endpoints, rate limits, response format, authentication
4. **DynamoDB Deduplication**: Best practices for conditional writes with composite keys
5. **Failover Patterns**: Circuit breaker vs simple retry with fallback

### Unknowns to Resolve

- Current adapter implementation status (what exists vs what needs building)
- Existing DynamoDB table schema for news items
- Current alerting mechanism for operations team
- EventBridge scheduler configuration for collection timing

---

## Phase 1: Design & Contracts

*Output: data-model.md, contracts/, quickstart.md*

### Entities (from spec)

1. **News Item** - Uniquely identified by (headline + source + publication_date)
2. **Sentiment Score** - Value (-1.0 to 1.0) with confidence (0.0 to 1.0) and label
3. **Collection Event** - Record of collection attempt with success/failure
4. **Data Source** - Provider configuration with priority and availability status

### Contracts to Generate

1. **Internal**: News item storage schema (DynamoDB)
2. **Internal**: Collection event schema (DynamoDB)
3. **Internal**: Source configuration schema
4. **External**: Downstream notification payload (SNS/SQS message format)

---

## Decision Log

| Decision | Choice | Rationale | Alternatives Considered |
|----------|--------|-----------|------------------------|
| Deduplication key | headline + source + date | Per clarification session, balances uniqueness with robustness | URL only (fragile), content hash (expensive) |
| Alert threshold | 3 consecutive failures in 15 min | Per clarification session, reduces alert fatigue | Single failure (noisy), 50% rate (delayed) |
| Failure detection | HTTP error OR timeout OR malformed body | Per clarification session, comprehensive coverage | HTTP only (misses silent failures) |
