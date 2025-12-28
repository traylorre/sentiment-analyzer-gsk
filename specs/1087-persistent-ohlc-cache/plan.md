# Implementation Plan: Persistent OHLC + Sentiment Cache

**Branch**: `1087-persistent-ohlc-cache` | **Date**: 2025-12-28 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `/specs/1087-persistent-ohlc-cache/spec.md`

## Summary

Implement a persistent write-through cache for OHLC (Open-High-Low-Close) price data using DynamoDB as L2 cache layer. Historical ticker data is permanent record and should be cached indefinitely to eliminate redundant external API calls (Tiingo/Finnhub), reduce latency from 500ms+ to <100ms, and improve reliability. The existing L1 Lambda memory cache remains as hot-path optimization.

## Technical Context

**Language/Version**: Python 3.13 (existing project standard)
**Primary Dependencies**: boto3 (AWS SDK), pydantic (validation), existing adapters (tiingo.py, finnhub.py)
**Storage**: DynamoDB - new `{env}-ohlc-cache` table with composite keys
**Testing**: pytest 8.0+, moto (AWS mocking), LocalStack for integration
**Target Platform**: AWS Lambda (serverless)
**Project Type**: Web application (Lambda backend + React frontend)
**Performance Goals**: <100ms historical queries (vs 500ms+ from external API), <50ms L1 cache hits
**Constraints**: Must not break existing frontend consumption (panning, resolution switching)
**Scale/Scope**: All resolutions (1m, 5m, 15m, 30m, 1h, D), ~2000 candles per 1-month 5m query

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Gate | Status | Notes |
|------|--------|-------|
| Uses DynamoDB (preferred persistence) | ✅ PASS | Aligns with Constitution §5 Serverless preference |
| Uses parameterized queries | ✅ PASS | boto3 Query API uses ExpressionAttributeValues |
| No secrets in code | ✅ PASS | Uses existing Secrets Manager pattern |
| Unit tests required | ✅ PASS | Will add comprehensive unit tests |
| Integration tests use real dev resources | ✅ PASS | Will use LocalStack/real AWS |
| No pipeline bypass | ✅ PASS | Standard PR workflow |
| Deterministic time handling | ✅ PASS | Will use fixed historical dates in tests |

## Project Structure

### Documentation (this feature)

```text
specs/1087-persistent-ohlc-cache/
├── spec.md              # Feature specification (complete)
├── plan.md              # This file
├── research.md          # Phase 0 output (to generate)
├── data-model.md        # Phase 1 output (to generate)
├── quickstart.md        # Phase 1 output (to generate)
├── contracts/           # Phase 1 output (to generate)
└── tasks.md             # Phase 2 output (/speckit.tasks command)
```

### Source Code (repository root)

```text
# Web application structure (existing)
src/lambdas/
├── dashboard/
│   └── ohlc.py              # Endpoint + L1 cache (modify)
└── shared/
    ├── adapters/
    │   ├── base.py          # Abstract interface (reference)
    │   ├── tiingo.py        # L2 adapter cache (reference)
    │   └── finnhub.py       # L2 adapter cache (reference)
    ├── models/
    │   └── ohlc.py          # Data models (modify)
    └── cache/
        ├── ticker_cache.py  # Symbol validation cache (reference)
        └── ohlc_cache.py    # NEW: L3 persistent cache

infrastructure/terraform/
├── modules/
│   ├── dynamodb/
│   │   ├── main.tf          # Table definitions (modify)
│   │   └── outputs.tf       # Table outputs (modify)
│   └── iam/
│       └── main.tf          # Permissions (modify)
└── main.tf                  # Module calls (modify)

tests/
├── unit/
│   ├── dashboard/
│   │   └── test_ohlc_cache.py  # Existing L1 tests (extend)
│   └── shared/
│       └── cache/
│           └── test_ohlc_persistent_cache.py  # NEW
└── integration/
    └── test_ohlc_persistent_cache.py  # NEW

frontend/src/  # No changes needed (existing contract maintained)
```

**Structure Decision**: Follows existing Lambda-based web application structure. New persistent cache module added under `src/lambdas/shared/cache/` following the existing `ticker_cache.py` pattern.

## Complexity Tracking

> No violations requiring justification. Design follows existing patterns.

| Violation | Why Needed | Simpler Alternative Rejected Because |
|-----------|------------|-------------------------------------|
| N/A | - | - |
