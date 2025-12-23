# Tasks: Validate 80% Cache Hit Rate

**Feature**: 1020-validate-cache-hit-rate
**Created**: 2025-12-22
**MVP Scope**: Phases 1-5 (19 tasks) - Core logging + E2E validation

---

## Phase 1: Setup & Verification

- [X] T001 Verify src/lib/timeseries/cache.py exists with CacheStats and get_global_cache()
- [X] T002 Verify src/lambdas/sse_streaming/ directory structure for adding cache_logger.py

## Phase 2: Foundation (Read existing code)

- [X] T003 Read cache.py to understand CacheStats interface (hits, misses, hit_rate)
- [X] T004 Read stream.py to understand where to add cache metric logging calls
- [X] T005 [P] Read latency_logger.py (T065) as pattern for structured logging module

## Phase 3: Cache Logger Module (US2 - Log Cache Metrics)

- [X] T006 [US2] Create src/lambdas/sse_streaming/cache_logger.py with log_cache_metrics()
- [X] T007 [US2] Add _is_cold_start tracking (module-level, similar to latency_logger.py)
- [X] T008 [US2] Implement structured JSON logging with all fields from data-model.md
- [X] T009 [US2] Add WARNING level log when hit_rate < 0.80 (threshold alert)

## Phase 4: Integration (US2 - Periodic Logging)

- [X] T010 [US2] Add import of cache_logger in stream.py
- [X] T011 [US2] Add periodic logging call (every 60s) in SSE generator loop
- [X] T012 [US2] Add cold start log on Lambda initialization
- [X] T013 [P] [US2] Add connection_count from ConnectionManager to log context

## Phase 5: E2E Test (US1 - Validate >80%)

- [X] T014 [US1] Create tests/e2e/test_cache_hit_rate.py with pytest-playwright
- [X] T015 [US1] Implement test_cache_hit_rate_exceeds_80_percent with warm-up exclusion
- [X] T016 [US1] Implement test_cache_metrics_logged_to_cloudwatch using Logs Insights
- [X] T017 [P] [US1] Add CacheMetrics and CachePerformanceReport dataclasses
- [X] T018 [US1] Add 30-second warm-up period before measurement
- [X] T019 [US1] Assert aggregate hit_rate > 0.80 after warm-up

## Phase 6: Documentation (US3, US4)

- [X] T020 [US4] Create docs/cache-performance.md with TTL behavior explanation
- [X] T021 [US4] Document LRU eviction behavior and max_entries sizing guidance
- [X] T022 [US4] Document cold start impact and warm-up patterns
- [X] T023 [US4] Add troubleshooting section for low hit rate scenarios
- [X] T024 [US3] Verify contracts/cache-metrics-queries.yaml has all 7 queries
- [X] T025 [US3] Add AWS CLI example for running queries

## Phase 7: Polish & Validation

- [X] T026 Run ruff check on new files
- [X] T027 Run pytest --collect-only to verify E2E test discovery
- [ ] T028 Run E2E test against preprod (if available) - SKIPPED: preprod unavailable
- [X] T029 Update quickstart.md with link to cache-performance.md
- [X] T030 Mark all tasks complete in tasks.md

---

## Task Summary

| Metric | Count |
|--------|-------|
| Total Tasks | 30 |
| Phase 1 (Setup) | 2 |
| Phase 2 (Foundation) | 3 |
| Phase 3 (US2 - Logger) | 4 |
| Phase 4 (US2 - Integration) | 4 |
| Phase 5 (US1 - E2E Test) | 6 |
| Phase 6 (US3/US4 - Docs) | 6 |
| Phase 7 (Polish) | 5 |
| Parallel [P] | 3 |

**MVP Scope**: Phases 1-5 (19 tasks) delivers logging + E2E validation
**Full Scope**: All 30 tasks including documentation

**Completion Status**: 29/30 complete (T028 skipped - preprod unavailable)

---

## Canonical Source References

- [CS-005] AWS Lambda Best Practices - Global scope caching
- [CS-006] Yan Cui - Warm invocation caching
- [CS-015] CloudWatch Logs Insights Query Syntax

## Files to Create/Modify

| File | Action | Phase |
|------|--------|-------|
| src/lambdas/sse_streaming/cache_logger.py | CREATE | Phase 3 |
| src/lambdas/sse_streaming/stream.py | MODIFY | Phase 4 |
| tests/e2e/test_cache_hit_rate.py | CREATE | Phase 5 |
| docs/cache-performance.md | CREATE | Phase 6 |
