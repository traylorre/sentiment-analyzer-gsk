# Implementation Plan: GSI Query Optimization

**Branch**: `502-gsi-query-optimization` | **Date**: 2025-12-18 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `/specs/502-gsi-query-optimization/spec.md`

## Summary

Replace all DynamoDB `table.scan()` fallbacks with GSI-based `table.query()` calls across 5 Lambda modules to achieve O(result) rather than O(table) query performance. The GSIs (`by_entity_status`, `by_sentiment`, `by_email`) are already defined in Terraform and deployed. This is a code-level refactoring with corresponding test updates.

## Technical Context

**Language/Version**: Python 3.13
**Primary Dependencies**: boto3>=1.34.0, aws-xray-sdk>=2.12.0
**Storage**: DynamoDB with GSIs (by_entity_status, by_sentiment, by_email)
**Testing**: pytest>=7.4.3, moto>=4.2.0 for DynamoDB mocking
**Target Platform**: AWS Lambda (serverless)
**Project Type**: Serverless microservices
**Performance Goals**: Query response time O(result size) not O(table size)
**Constraints**: Read capacity consumption proportional to result selectivity
**Scale/Scope**: 5 Lambda modules, ~10 scan->query conversions, ~15 test file updates

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Gate | Status | Notes |
|------|--------|-------|
| Unit tests accompany all changes | ✅ PASS | Test updates explicitly required in spec (FR-007, FR-008, FR-009) |
| No pipeline bypass | ✅ PASS | Standard PR workflow, no bypass needed |
| DynamoDB best practices | ✅ PASS | GSI queries align with Section 5 (Use DynamoDB as primary persistence, define GSIs for query access patterns) |
| Parameterized queries | ✅ PASS | All KeyConditionExpression and FilterExpression use ExpressionAttributeValues |
| Pre-push requirements | ✅ PASS | Standard lint/format/test workflow applies |

**No constitution violations. Proceed to Phase 0.**

## Project Structure

### Documentation (this feature)

```text
specs/502-gsi-query-optimization/
├── plan.md              # This file
├── research.md          # Phase 0 output
├── data-model.md        # Phase 1 output (GSI schema reference)
├── quickstart.md        # Phase 1 output
├── contracts/           # Phase 1 output (query patterns)
└── tasks.md             # Phase 2 output (/speckit.tasks)
```

### Source Code (repository root)

```text
src/lambdas/
├── ingestion/
│   └── handler.py           # _get_active_tickers() GSI conversion
├── sse_streaming/
│   └── polling.py           # _scan_table() → _query_by_sentiment()
├── notification/
│   ├── alert_evaluator.py   # _find_alerts_by_ticker() GSI conversion
│   └── digest_service.py    # get_users_due_for_digest() GSI conversion
└── dashboard/
    └── auth.py              # get_user_by_email() → NotImplementedError

tests/unit/
├── lambdas/
│   ├── ingestion/           # Mock table.query() for tickers
│   ├── sse_streaming/       # Mock table.query() for sentiment
│   ├── notification/        # Mock table.query() for alerts/digest
│   └── dashboard/           # Test NotImplementedError path
└── conftest.py              # GSI-aware moto table fixtures
```

**Structure Decision**: Existing serverless Lambda structure. No new modules needed - only refactoring existing scan patterns to query patterns.

## Complexity Tracking

> No constitution violations requiring justification.

| Violation | Why Needed | Simpler Alternative Rejected Because |
|-----------|------------|-------------------------------------|
| N/A | N/A | N/A |
