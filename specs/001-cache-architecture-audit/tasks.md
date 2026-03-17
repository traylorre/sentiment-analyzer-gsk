# Tasks: Cache Architecture Audit and Remediation

**Feature Branch**: `001-cache-architecture-audit`
**Generated**: 2026-03-17
**Spec**: [spec.md](spec.md) | **Plan**: [plan.md](plan.md)

## Phase 1: Setup

- [x] T001 Run baseline test suite (`make test-local`) and record pass count for regression tracking
- [x] T002 Create shared cache utility module in src/lib/cache_utils.py with `jittered_ttl(base_ttl, jitter_pct)` function using `random.uniform(1.0 - jitter_pct, 1.0 + jitter_pct)`
- [x] T003 Add `CacheStats` dataclass to src/lib/cache_utils.py with fields: name, hits, misses, evictions, refresh_failures, last_flush_at
- [x] T004 Add `CacheMetricEmitter` class to src/lib/cache_utils.py that accumulates CacheStats per cache and flushes to CloudWatch via `emit_metrics_batch()` every 60 seconds
- [x] T005 Add `validate_non_empty(data, cache_name)` helper to src/lib/cache_utils.py that raises ValueError on empty/None data
- [x] T006 Add unit tests for cache_utils module in tests/unit/test_cache_utils.py covering jittered_ttl distribution, CacheStats accumulation, CacheMetricEmitter flush, and validate_non_empty
- [x] T007 Add autouse cache-clearing fixture to tests/conftest.py that clears all module-level caches between tests (import clear functions from each cache module)

## Phase 2: Foundational

- [x] T008 Add `JWKS_CACHE_TTL`, `JWKS_GRACE_PERIOD`, `TICKER_CACHE_TTL`, `QUOTA_READ_CACHE_TTL`, `CACHE_JITTER_PCT`, `CACHE_METRICS_FLUSH_INTERVAL`, `METRICS_CACHE_MAX_ENTRIES` env var reads to respective modules with defaults per quickstart.md
- [x] T009 Verify all existing tests still pass after Phase 1 and Phase 2 changes (`make test-local`)

## Phase 3: User Story 1 — Reliable Authentication During Key Rotation (P1)

**Resolution**: Risk eliminated by removal. `_get_jwks()` was dead code — the app uses self-issued HMAC/HS256 JWTs via `validate_jwt()` in auth_middleware.py, not Cognito JWKS verification. Removed the dead `_get_jwks()` function and unused `lru_cache` import from cognito.py. All 23 cognito tests pass.

- [x] T010 [US1] Remove dead `_get_jwks()` function and unused `lru_cache` import from src/lambdas/shared/auth/cognito.py
- [x] T020 [US1] Verify all existing auth tests still pass (`pytest tests/unit/ -k cognito -v` — 23 passed)

## Phase 4: User Story 2 — Accurate API Quota Tracking (P1)

**Goal**: Replace batch put_item sync with atomic DynamoDB counters + 25% fallback + alert.
**Independent Test**: Multiple concurrent threads incrementing quota → aggregate within 10% of actual.

- [x] T021 [US2] Refactor `_sync_to_dynamodb()` in src/lambdas/shared/quota_tracker.py — replace `put_item()` with `update_item()` using `ADD #svc :count` atomic increment for writes
- [x] T022 [US2] Add `_atomic_increment_usage(service, count)` method to QuotaTrackerManager in src/lambdas/shared/quota_tracker.py that performs atomic DynamoDB increment on every API call
- [x] T023 [US2] Refactor quota read path in src/lambdas/shared/quota_tracker.py — reduced read cache TTL to 10s (from 60s), use ConsistentRead=True on cache miss
- [x] T024 [US2] Implement 25% rate reduction fallback in src/lambdas/shared/quota_tracker.py — on DynamoDB write failure, set `_reduced_rate_mode = True`, reduce allowed calls to 25% of normal limit
- [x] T025 [US2] Implement quota disconnected alert in src/lambdas/shared/quota_tracker.py — emit `QuotaTracker/Disconnected` metric immediately when entering reduced-rate mode, with alert spam prevention (max once per 5 min)
- [x] T026 [US2] Implement 80% threshold warning in src/lambdas/shared/quota_tracker.py — emit `QuotaTracker/ThresholdWarning` metric when usage exceeds 80% of limit for a service
- [ ] T027 [US2] Add CacheStats instance for quota read cache in src/lambdas/shared/quota_tracker.py — track hits, misses for the local read cache
- [x] T028 [US2] Add unit tests for atomic increment in tests/unit/test_quota_tracker_atomic.py — mock DynamoDB, verify update_item called with ADD expression
- [x] T029 [US2] Add unit tests for 25% fallback in tests/unit/test_quota_tracker_atomic.py — mock DynamoDB write failure, verify rate reduced to 25%
- [x] T030 [US2] Add unit tests for disconnected alert in tests/unit/test_quota_tracker_atomic.py — verify QuotaTracker/Disconnected metric emitted on DynamoDB failure
- [x] T031 [US2] Add unit tests for cross-instance accuracy in tests/unit/test_quota_tracker_atomic.py — use threading.Thread to simulate concurrent instances, verify aggregate within 10%
- [x] T032 [US2] Add unit tests for 80% threshold warning in tests/unit/test_quota_tracker_atomic.py — verify metric emitted when usage exceeds 80%
- [x] T033 [US2] Verify all existing quota tracker tests still pass (68 passed + 13 new = 81 total)

## Phase 5: User Story 3 — Fresh Ticker Data After List Updates (P2)

**Goal**: Replace @lru_cache with TTL + S3 ETag conditional refresh + empty-list rejection.
**Independent Test**: Update S3 object → cache refreshes within TTL window → new tickers visible.

- [ ] T034 [US3] Remove `@lru_cache(maxsize=1)` from `get_ticker_cache()` in src/lambdas/shared/cache/ticker_cache.py and replace with module-level `_ticker_cache_entry` tuple (timestamp, TickerCache, etag)
- [ ] T035 [US3] Implement TTL-based refresh in `get_ticker_cache()` in src/lambdas/shared/cache/ticker_cache.py — check timestamp, if expired call S3 head_object() to compare ETag
- [ ] T036 [US3] Implement ETag conditional refresh in src/lambdas/shared/cache/ticker_cache.py — if ETag unchanged skip download and reset timer, if changed download new list via get_object()
- [ ] T037 [US3] Implement empty-list rejection in src/lambdas/shared/cache/ticker_cache.py — use `validate_non_empty()` before swapping cache, keep previous list if new list is empty
- [ ] T038 [US3] Implement fail-open behavior in src/lambdas/shared/cache/ticker_cache.py — on S3 failure (head_object or get_object), log warning and return stale cached list
- [ ] T039 [US3] Add CacheStats instance for ticker cache in src/lambdas/shared/cache/ticker_cache.py — track hits, misses, refresh_failures
- [ ] T040 [US3] Add unit tests for TTL refresh in tests/unit/test_ticker_cache_ttl.py — use @freeze_time, verify head_object called after TTL expires
- [ ] T041 [US3] Add unit tests for ETag conditional refresh in tests/unit/test_ticker_cache_ttl.py — mock S3 head_object with matching/different ETag, verify download skipped/triggered
- [ ] T042 [US3] Add unit tests for empty-list rejection in tests/unit/test_ticker_cache_ttl.py — mock S3 returning empty JSON, verify previous list retained
- [ ] T043 [US3] Add unit tests for S3 failure fallback in tests/unit/test_ticker_cache_ttl.py — mock S3 ClientError, verify stale cache returned with warning logged
- [ ] T044 [US3] Verify all existing ticker cache tests still pass (`pytest tests/unit/ -k ticker -v`)

## Phase 6: User Story 4 — Consistent Cache Behavior Under Upstream Failures (P2)

**Goal**: Document and implement consistent failure policies per cache; verify via fault injection.
**Independent Test**: Inject failure per upstream → each cache behaves per documented policy.

- [ ] T045 [US4] Create cache failure policy runbook at docs/cache-failure-policies.md documenting all 12 caches with: name, failure policy (open/closed/conservative), grace period, expected behavior, and recovery action
- [ ] T046 [US4] Implement fail-closed with 15-min grace on secrets cache in src/lambdas/shared/secrets.py — on Secrets Manager failure, serve cached secret if within grace period, raise SecretAccessDeniedError after
- [ ] T047 [US4] Verify circuit breaker already fails-open (returns closed state on DynamoDB read failure) in src/lambdas/shared/circuit_breaker.py — add explicit comment documenting this policy
- [ ] T048 [US4] Add fault injection tests for JWKS fail-closed behavior in tests/unit/test_jwks_cache.py — verify auth denied after 15-min grace when Cognito unreachable
- [ ] T049 [US4] Add fault injection tests for secrets fail-closed behavior in tests/unit/test_secrets_failure.py — mock Secrets Manager failure, verify grace period then raise
- [ ] T050 [P] [US4] Add fault injection tests for ticker fail-open behavior in tests/unit/test_ticker_cache_ttl.py — verify stale list served indefinitely when S3 unreachable
- [ ] T051 [P] [US4] Add fault injection tests for quota tracker fail-conservative in tests/unit/test_quota_tracker_atomic.py — verify 25% rate reduction on DynamoDB failure
- [ ] T052 [P] [US4] Add fault injection tests for circuit breaker fail-open in tests/unit/test_circuit_breaker_failure.py — mock DynamoDB, verify closed state returned on read failure
- [ ] T053 [US4] Run full test suite to verify no regressions from failure policy changes (`make test-local`)

## Phase 7: User Story 5 — Cache Performance Visibility (P3)

**Goal**: Emit hit/miss/eviction metrics per cache to CloudWatch via CacheMetricEmitter.
**Independent Test**: Generate cache traffic → verify metrics appear in CloudWatch within 60s.

- [ ] T054 [P] [US5] Integrate CacheStats into src/lambdas/shared/auth/cognito.py — increment hits/misses on JWKS cache access, register with CacheMetricEmitter
- [ ] T055 [P] [US5] Integrate CacheStats into src/lambdas/shared/quota_tracker.py — increment hits/misses on quota read cache access
- [ ] T056 [P] [US5] Integrate CacheStats into src/lambdas/shared/cache/ticker_cache.py — increment hits/misses on ticker cache access
- [ ] T057 [P] [US5] Integrate CacheStats into src/lambdas/shared/circuit_breaker.py — increment hits/misses on circuit breaker state read
- [ ] T058 [P] [US5] Integrate CacheStats into src/lambdas/shared/secrets.py — increment hits/misses on secrets cache access
- [ ] T059 [P] [US5] Integrate CacheStats into src/lambdas/shared/adapters/tiingo.py — increment hits/misses on Tiingo API response cache access
- [ ] T060 [P] [US5] Integrate CacheStats into src/lambdas/shared/adapters/finnhub.py — increment hits/misses on Finnhub API response cache access
- [ ] T061 [P] [US5] Integrate CacheStats into src/lambdas/dashboard/configurations.py — increment hits/misses on config cache access
- [ ] T062 [P] [US5] Integrate CacheStats into src/lambdas/dashboard/sentiment.py — increment hits/misses on sentiment cache access
- [ ] T063 [P] [US5] Integrate CacheStats into src/lambdas/dashboard/metrics.py — increment hits/misses on metrics cache access
- [ ] T064 [P] [US5] Integrate CacheStats into src/lambdas/dashboard/ohlc.py — increment hits/misses on OHLC response cache access
- [ ] T065 [P] [US5] Integrate CacheStats into src/lambdas/shared/cache/ohlc_cache.py — increment hits/misses on OHLC persistent cache access
- [ ] T066 [US5] Wire CacheMetricEmitter flush into Lambda handler response path in src/lambdas/dashboard/handler.py — call flush before returning response
- [ ] T067 [US5] Add unit tests for metric emission in tests/unit/test_cache_metrics.py — mock emit_metrics_batch, verify all 12 caches emit metrics with correct dimensions
- [ ] T068 [US5] Verify no cold start latency regression — measure import time of modified modules

## Phase 8: User Story 6 — No Thundering Herd on Cache Expiry (P3)

**Goal**: Add ±10% TTL jitter to all 12 caches to spread expiry times.
**Independent Test**: Generate 100 jittered TTLs → standard deviation >= 5% of base TTL.

- [ ] T069 [P] [US6] Add jitter to JWKS cache TTL in src/lambdas/shared/auth/cognito.py — use `jittered_ttl(JWKS_CACHE_TTL)` when storing cache entry
- [ ] T070 [P] [US6] Add jitter to ticker cache TTL in src/lambdas/shared/cache/ticker_cache.py — use `jittered_ttl(TICKER_CACHE_TTL)` when storing cache entry
- [ ] T071 [P] [US6] Add jitter to circuit breaker recovery timeout in src/lambdas/shared/circuit_breaker.py — use `jittered_ttl(recovery_timeout_seconds)` when checking elapsed time
- [ ] T072 [P] [US6] Add jitter to secrets cache TTL in src/lambdas/shared/secrets.py — use `jittered_ttl(SECRETS_CACHE_TTL_SECONDS)` when storing expires_at
- [ ] T073 [P] [US6] Add jitter to Tiingo API cache TTL in src/lambdas/shared/adapters/tiingo.py — use `jittered_ttl()` when storing cache entry timestamp
- [ ] T074 [P] [US6] Add jitter to Finnhub API cache TTL in src/lambdas/shared/adapters/finnhub.py — use `jittered_ttl()` when storing cache entry timestamp
- [ ] T075 [P] [US6] Add jitter to configuration cache TTL in src/lambdas/dashboard/configurations.py — use `jittered_ttl(CONFIG_CACHE_TTL)` when storing cache entry
- [ ] T076 [P] [US6] Add jitter to sentiment cache TTL in src/lambdas/dashboard/sentiment.py — use `jittered_ttl(SENTIMENT_CACHE_TTL)` when storing cache entry
- [ ] T077 [P] [US6] Add jitter to metrics cache TTL in src/lambdas/dashboard/metrics.py — use `jittered_ttl(METRICS_CACHE_TTL)` when storing cache entry
- [ ] T078 [P] [US6] Add jitter to OHLC response cache TTL in src/lambdas/dashboard/ohlc.py — use `jittered_ttl()` when storing OHLC cache entry
- [ ] T079 [P] [US6] Add jitter to resolution timeseries cache TTL in src/lib/timeseries/cache.py — use `jittered_ttl(ttl_seconds)` in ResolutionCache entry creation
- [ ] T080 [P] [US6] Add jitter to quota read cache TTL in src/lambdas/shared/quota_tracker.py — use `jittered_ttl(QUOTA_READ_CACHE_TTL)` for read cache expiry
- [ ] T081 [US6] Add max_entries bound to metrics cache in src/lambdas/dashboard/metrics.py — add METRICS_CACHE_MAX_ENTRIES (default 100) with LRU eviction (FR-008)
- [ ] T082 [US6] Add unit tests for jitter distribution in tests/unit/test_cache_jitter.py — generate 1000 jittered TTLs, verify standard deviation >= 5% of base TTL
- [ ] T083 [US6] Add unit tests for jitter bounds in tests/unit/test_cache_jitter.py — verify all jittered TTLs fall within [base * 0.9, base * 1.1]
- [ ] T084 [US6] Add unit tests for metrics cache max_entries in tests/unit/test_cache_bounds.py — add entries exceeding limit, verify oldest evicted

## Phase 9: Polish & Cross-Cutting

- [ ] T085 Update tests/conftest.py autouse cache-clearing fixture to include all new clear functions (clear_jwks_cache, updated clear_ticker_cache, etc.)
- [ ] T086 Run full test suite (`make test-local`) and verify all 3428+ existing tests plus new tests pass
- [ ] T087 Run `make validate` (fmt + lint + security + ci validation) and fix any issues
- [ ] T088 Verify cold start latency increase is < 100ms by timing Lambda import chain before and after changes
- [ ] T089 Review all modified files for backward compatibility — verify old cache behavior preserved when new env vars are not set (defaults match previous behavior where applicable)

## Dependencies

```text
Phase 1 (Setup) ──→ Phase 2 (Foundational) ──→ Phase 3 (US1: JWKS) ──┐
                                               Phase 4 (US2: Quota) ──┤
                                               Phase 5 (US3: Ticker) ─┤
                                                                       ├──→ Phase 6 (US4: Failure Policies)
                                                                       ├──→ Phase 7 (US5: Metrics)
                                                                       ├──→ Phase 8 (US6: Jitter)
                                                                       └──→ Phase 9 (Polish)
```

- Phases 3, 4, 5 are **independent** — can be done in parallel after Phase 2
- Phases 6, 7, 8 depend on Phases 3-5 (they reference the caches modified in those phases)
- Phase 7 tasks T054-T065 are all **parallelizable** (different files, no shared dependencies)
- Phase 8 tasks T069-T080 are all **parallelizable** (different files, no shared dependencies)

## Parallel Execution Examples

### After Phase 2 completes (3 independent streams):
```text
Stream A: T010→T011→T012→T013→T014→T015→T016→T017→T018→T019→T020
Stream B: T021→T022→T023→T024→T025→T026→T027→T028→T029→T030→T031→T032→T033
Stream C: T034→T035→T036→T037→T038→T039→T040→T041→T042→T043→T044
```

### Phase 7 (all parallel):
```text
T054 | T055 | T056 | T057 | T058 | T059 | T060 | T061 | T062 | T063 | T064 | T065 (all files independent)
Then: T066→T067→T068 (sequential, depends on all above)
```

### Phase 8 (all parallel):
```text
T069 | T070 | T071 | T072 | T073 | T074 | T075 | T076 | T077 | T078 | T079 | T080 (all files independent)
Then: T081→T082→T083→T084 (sequential)
```

## Implementation Strategy

**MVP (minimum viable)**: Phases 1-3 (Setup + JWKS fix) — fixes the highest-severity bug with the smallest scope. Can be merged independently.

**Recommended PR grouping**:
1. **PR 1**: Phases 1-2 (Setup + Foundational) — cache_utils.py, env vars, test fixtures
2. **PR 2**: Phase 3 (US1: JWKS) — self-contained security fix
3. **PR 3**: Phase 4 (US2: Quota) — self-contained quota accuracy fix
4. **PR 4**: Phase 5 (US3: Ticker) — self-contained ticker refresh fix
5. **PR 5**: Phases 6-8 (US4-6: Failure policies + Metrics + Jitter) — cross-cutting sweep
6. **PR 6**: Phase 9 (Polish) — final validation and cleanup
