# Tasks: Per-Cache Jitter Assertion Tests

**Feature Branch**: `001-jitter-assertion-tests`
**Generated**: 2026-03-17

## Phase 1: Implementation

- [ ] T001 Create tests/unit/test_cache_jitter_integration.py with test class and shared fixtures
- [ ] T002 [P] [US1] Add jitter assertion test for circuit_breaker cache (base TTL 60s) in tests/unit/test_cache_jitter_integration.py
- [ ] T003 [P] [US1] Add jitter assertion test for secrets cache (base TTL 300s) in tests/unit/test_cache_jitter_integration.py
- [ ] T004 [P] [US1] Add jitter assertion test for tiingo adapter cache (base TTL 1800s) in tests/unit/test_cache_jitter_integration.py
- [ ] T005 [P] [US1] Add jitter assertion test for finnhub adapter cache (base TTL 1800s) in tests/unit/test_cache_jitter_integration.py
- [ ] T006 [P] [US1] Add jitter assertion test for configurations cache (base TTL 60s) in tests/unit/test_cache_jitter_integration.py
- [ ] T007 [P] [US1] Add jitter assertion test for sentiment cache (base TTL 300s) in tests/unit/test_cache_jitter_integration.py
- [ ] T008 [P] [US1] Add jitter assertion test for metrics cache (base TTL 300s) in tests/unit/test_cache_jitter_integration.py
- [ ] T009 [P] [US1] Add jitter assertion test for ohlc response cache (base TTL 300-3600s) in tests/unit/test_cache_jitter_integration.py
- [ ] T010 [P] [US1] Add jitter assertion test for timeseries resolution cache (base TTL = resolution duration) in tests/unit/test_cache_jitter_integration.py
- [ ] T011 [P] [US1] Add jitter assertion test for ticker cache (base TTL 300s) in tests/unit/test_cache_jitter_integration.py

## Phase 2: Validation

- [ ] T012 Run new tests and verify all 10 pass
- [ ] T013 Run full test suite and verify no regressions (3484+ baseline)
