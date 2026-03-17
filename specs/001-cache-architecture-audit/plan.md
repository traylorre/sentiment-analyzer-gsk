# Implementation Plan: Cache Architecture Audit and Remediation

**Branch**: `001-cache-architecture-audit` | **Date**: 2026-03-17 | **Spec**: [spec.md](spec.md)
**Input**: Feature specification from `/specs/001-cache-architecture-audit/spec.md`

## Summary

Fix three high-risk cache coherence bugs (JWKS unbounded, quota tracker cross-Lambda lag, ticker cold-start-only load), add TTL jitter to all 12 caches, bound the unbounded metrics cache, emit cache performance metrics to CloudWatch, and document failure policies per cache. All changes target the historical/REST data tier only. No new infrastructure services — uses existing DynamoDB and CloudWatch.

## Technical Context

**Language/Version**: Python 3.13
**Primary Dependencies**: boto3 (AWS SDK), pydantic (validation), functools (current caching)
**Storage**: DynamoDB (quota ledger, circuit breaker state, OHLC persistent cache), S3 (ticker list)
**Testing**: pytest 8.0+ with moto (AWS mocking), freezegun (time control), threading (concurrency tests)
**Target Platform**: AWS Lambda (container-image based, 1024-2048MB memory)
**Project Type**: Serverless backend (Lambda + DynamoDB + S3)
**Performance Goals**: Cold start increase < 100ms, cache hit/miss metric emission < 5ms overhead per request
**Constraints**: Monthly DynamoDB cost increase < $5, no new AWS services, backward-compatible cache behavior
**Scale/Scope**: 12 caches across 8 source files, up to 20 concurrent Lambda instances, expanding from 22 to 8K tickers

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Gate | Status | Notes |
|------|--------|-------|
| Unit tests accompany all code (Section 7) | PASS | Every cache modification gets corresponding unit tests |
| Deterministic time in tests (Amendment 1.5) | PASS | TTL/jitter tests use freezegun, not datetime.now() |
| GPG-signed commits (Section 8) | PASS | Standard workflow |
| No pipeline bypass (Section 8) | PASS | Standard workflow |
| External deps mocked in tests (Section 7) | PASS | S3, DynamoDB, Cognito all mocked with moto |
| Secrets not in source (Section 3) | PASS | No secrets involved — cache config via env vars |
| Least-privilege IAM (Section 5) | PASS | No new IAM permissions needed — existing DynamoDB/S3/CloudWatch access sufficient |
| Local SAST before push (Amendment 1.6) | PASS | Standard make validate workflow |

**Result**: All gates pass. No violations to justify.

## Project Structure

### Documentation (this feature)

```text
specs/001-cache-architecture-audit/
├── plan.md              # This file
├── research.md          # Phase 0: Technology decisions
├── data-model.md        # Phase 1: Cache entity models
├── quickstart.md        # Phase 1: Developer onboarding
├── contracts/           # Phase 1: Internal cache contracts
│   └── cache-metrics.md # Metric names and dimensions
└── tasks.md             # Phase 2: Task breakdown (via /speckit.tasks)
```

### Source Code (repository root)

```text
src/
├── lambdas/shared/
│   ├── auth/cognito.py          # JWKS cache: replace @lru_cache with TTL + refresh-on-failure
│   ├── quota_tracker.py         # Quota: atomic DynamoDB counters, 25% fallback, alert
│   ├── cache/
│   │   ├── ticker_cache.py      # Ticker: TTL refresh with S3 ETag, empty-list rejection
│   │   └── ohlc_cache.py        # OHLC: add cache stats tracking
│   ├── circuit_breaker.py       # Add jitter to recovery timeout
│   └── secrets.py               # Add cache stats, bound cache
│   └── adapters/
│       ├── tiingo.py            # Add jitter to TTL, cache stats
│       └── finnhub.py           # Add jitter to TTL, cache stats
├── lambdas/dashboard/
│   ├── configurations.py        # Add jitter to TTL, cache stats
│   ├── sentiment.py             # Add jitter to TTL, cache stats
│   ├── metrics.py               # Bound cache (add max_entries), cache stats
│   └── ohlc.py                  # Add jitter to TTL, cache stats
└── lib/
    ├── metrics.py               # Existing emit_metric() — reused for cache metrics
    └── cache_utils.py           # NEW: jitter utility, cache stats helper, metric emission wrapper

tests/
├── unit/
│   ├── test_jwks_cache.py       # NEW: TTL expiry, refresh-on-failure, grace period
│   ├── test_quota_tracker_atomic.py  # NEW: atomic counters, 25% fallback, alert
│   ├── test_ticker_cache_ttl.py # NEW: TTL refresh, ETag, empty-list rejection
│   ├── test_cache_jitter.py     # NEW: jitter distribution, statistical spread
│   ├── test_cache_metrics.py    # NEW: metric emission for all caches
│   └── test_cache_bounds.py     # NEW: max_entries enforcement on all caches
└── conftest.py                  # Add autouse cache-clearing fixture
```

**Structure Decision**: Modifications to existing files in their current locations. One new utility module (`src/lib/cache_utils.py`) for shared jitter/stats/metrics logic to avoid duplicating the same pattern across 12 files.

## Complexity Tracking

No constitution violations — table not needed.
