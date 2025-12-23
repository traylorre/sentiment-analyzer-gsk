# Implementation Plan: Validate 80% Cache Hit Rate

**Branch**: `1020-validate-cache-hit-rate` | **Date**: 2025-12-22 | **Spec**: [spec.md](spec.md)
**Input**: Feature specification from `/specs/1020-validate-cache-hit-rate/spec.md`
**Parent**: specs/1009-realtime-multi-resolution/spec.md (T066, SC-008)

## Summary

Add structured cache metrics logging to the SSE streaming Lambda using the existing ResolutionCache.CacheStats, provide CloudWatch Logs Insights queries for cache performance analysis, create E2E test validating >80% hit rate, and document cache behavior patterns and tuning recommendations.

## Technical Context

**Language/Version**: Python 3.13 (existing project standard)
**Primary Dependencies**: structlog (existing), boto3 (existing), pytest-playwright (E2E)
**Storage**: CloudWatch Logs (structured JSON via structlog)
**Testing**: pytest with moto (unit), playwright (E2E against preprod)
**Target Platform**: AWS Lambda (SSE streaming)
**Project Type**: single (Lambda + dashboard)
**Performance Goals**: >80% cache hit rate during normal usage
**Constraints**: <1KB/minute log volume, non-blocking logging, 60s E2E timeout
**Scale/Scope**: 13 tickers, 8 resolutions, 100 concurrent users

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Gate | Status | Notes |
|------|--------|-------|
| 1.1 Spec First | PASS | spec.md created with 4 user stories, 11 FRs |
| 1.2 TDD | PASS | Test designs in spec.md, E2E test validates SC-008 |
| 1.5 Canonical Sources | PASS | [CS-005], [CS-006], [CS-015] cited |
| 1.6 No Quick Fixes | PASS | Full speckit workflow followed |
| 2.1 Single Project | PASS | Changes to existing Lambda + docs |
| 2.2 Minimal Deps | PASS | structlog already exists, no new deps |

## Project Structure

### Documentation (this feature)

```text
specs/1020-validate-cache-hit-rate/
├── spec.md              # Feature specification (done)
├── plan.md              # This file
├── research.md          # Phase 0 output
├── data-model.md        # Phase 1 output (log schema)
├── quickstart.md        # Phase 1 output
├── contracts/           # Phase 1 output (Logs Insights queries)
│   └── cache-metrics-queries.yaml
├── checklists/
│   └── requirements.md  # Requirements checklist (done)
└── tasks.md             # Phase 2 output
```

### Source Code (repository root)

```text
src/
├── lib/
│   └── timeseries/
│       └── cache.py           # Existing ResolutionCache with CacheStats
└── lambdas/
    └── sse_streaming/
        ├── stream.py          # Add cache metrics logging calls
        └── cache_logger.py    # NEW: Structured cache metrics logging

tests/
├── unit/
│   └── test_cache_metrics_logger.py  # NEW: Unit tests for logging
└── e2e/
    └── test_cache_hit_rate.py        # NEW: E2E validation of >80%

docs/
└── cache-performance.md              # NEW: Cache behavior documentation
```

**Structure Decision**: Extend existing SSE Lambda with new cache_logger.py module. Follow existing pattern from latency_logger.py (T065).

## Research Questions (Phase 0)

### RQ1: How to access cache stats from SSE Lambda?

**Context**: ResolutionCache is in src/lib/timeseries/cache.py with global instance via get_global_cache(). SSE Lambda needs to read stats without modifying cache internals.

**Decision Needed**: Import path for cache stats access

### RQ2: Optimal logging frequency for cache metrics?

**Context**: Too frequent = log spam and cost; too infrequent = missed patterns. Need balance.

**Decision Needed**: Periodic interval and event triggers

### RQ3: CloudWatch Logs Insights query patterns for cache metrics?

**Context**: Need efficient queries that work within Logs Insights limits (10K results, timeout).

**Decision Needed**: Query templates for aggregate, by-ticker, and time-series analysis

### RQ4: How to simulate normal usage patterns in E2E test?

**Context**: Need realistic cache access patterns to validate >80% hit rate.

**Decision Needed**: Test scenario design with resolution switching and multi-ticker access

### RQ5: What constitutes "normal operation" for cache hit rate?

**Context**: Cold starts, TTL expiration, and LRU eviction naturally reduce hit rate. Need to define steady-state measurement window.

**Decision Needed**: Measurement methodology and exclusions (e.g., first 30s warm-up)

## Phase 1 Deliverables

1. **research.md**: Answers to RQ1-RQ5 with cited sources
2. **data-model.md**: Cache metric log schema (event_type, hits, misses, hit_rate, ticker, resolution)
3. **contracts/cache-metrics-queries.yaml**: CloudWatch Logs Insights query templates
4. **quickstart.md**: How to validate cache performance, run queries, interpret results

## Complexity Tracking

No violations - all work uses existing patterns and infrastructure.
