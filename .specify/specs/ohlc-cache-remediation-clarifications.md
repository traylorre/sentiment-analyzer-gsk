# OHLC Cache Remediation - Clarification History

**Parent Spec:** [ohlc-cache-remediation.md](ohlc-cache-remediation.md)
**Feature ID:** CACHE-001

This document archives the clarification Q&A sessions from the spec development process. For the current spec, see the parent document.

---

## Session 2026-02-03 (Round 1)
- Q: Env var fallback policy for `_get_table_name()` when `OHLC_CACHE_TABLE` is not set? → A: Remove fallback, raise ValueError if env var missing (fail-fast)
- Q: Resolution format mismatch - docstring shows "5m" but code passes "5"? → A: Use OHLCResolution enum values as-is ("5", "60", "D") - fix misleading docstring
- Q: Distinguishing cache miss vs cache error? → A: Log at ERROR level for failures, add CloudWatch metric for cache errors, add alarm that fires once on non-zero then mutes for 1 hour
- Q: Async/sync event loop blocking from sync DynamoDB calls in async endpoint? → A: Wrap sync DynamoDB calls in `asyncio.to_thread()` now
- Q: Integration test to prevent regression of cache not being called? → A: Functional test - first request writes to mock DDB, second request reads from it (verify actual data round-trip)

## Session 2026-02-03 (Round 2)
- Q: Volume=None from Tiingo IEX crashes cache write with int(None) - how to handle? → A: Fix at adapter layer - Tiingo adapter should return volume=0 when unavailable, not None. Normalize data at system boundary.
- Q: DynamoDB query pagination not handled - silent truncation if >1MB? → A: Add warning log if LastEvaluatedKey present, but don't paginate (detect before it bites)
- Q: Estimate function has math error - line 353 multiplies by 7 instead of 6.5? → A: Fix math to `return int(days * 5 / 7 * 6.5)` to match comment
- Q: 80% coverage threshold allows serving incomplete/stale data - acceptable? → A: Remove 80% threshold entirely - require 100% expected candles for cache hit. User always gets complete data.
- Q: Three cache layers with separate invalidation - risk of partial invalidation bugs? → A: Add unified `invalidate_all_caches(ticker)` that clears all layers. Remove/replace obsolete partial invalidate functions - ONE function clears ALL layers.

## Session 2026-02-03 (Round 3)
- Q: Unprocessed BatchWriteItems logged but NOT retried - data silently lost? → A: Add retry loop with exponential backoff (max 3 retries) + CloudWatch metric for unprocessed items
- Q: DynamoDB client created fresh every call - connection overhead? → A: Cache client at module level (singleton pattern) + audit ALL cache clients across codebase are singletons
- Q: Finnhub adapter also has volume=None bug (line 378) - fix for consistency? → A: Fix Finnhub adapter to return volume=0 when unavailable (same as Tiingo fix)
- Q: No circuit breaker for DynamoDB failures - latency penalty during outages? → A: Add simple circuit breaker (skip DDB for 60s after 3 consecutive failures) + CloudWatch metric that triggers alarm then mutes for 1 hour
- Q: No production verification of cache effectiveness - mocked tests don't catch deployment issues? → A: Add post-deployment smoke test that fetches ticker twice and verifies cache hit in logs

## Session 2026-02-03 (Round 4)
- Q: DynamoDB TTL / Data Retention - items stored indefinitely causing unbounded growth? → A: 90-day TTL - balance between data availability and cost control; automatic cleanup without operational burden
- Q: Cold start thundering herd - multiple Lambdas calling Tiingo simultaneously for same ticker? → A: Distributed lock via DynamoDB conditional write - first caller wins, others wait/retry from cache
- Q: Alerting thresholds - when to page vs. tolerate graceful degradation? → A: Tiered alerting - CacheError >10/min → Slack; CircuitBreakerOpen → page on-call; Truncation → page on-call
- Q: Rollback strategy - feature flag for instant disable? → A: No feature flag - trust the tests, fix-forward if issues arise; simplicity over kill-switch complexity
- Q: DynamoDB partition key design - hot partition risk for popular tickers? → A: Accept current design - monitor for throttling, optimize with sharding if/when it occurs; premature optimization adds complexity

## Session 2026-02-04 (Round 5)
- Q: Lock key vs cache key format mismatch - lock missing date anchor blocks unrelated requests? → A: Include date anchor in lock key (`LOCK#AAPL#D#1W#2026-02-04`) to match cache key granularity; prevents false contention

## Session 2026-02-04 (Round 6)
- Q: In-memory cache maxsize eviction behavior when 1000 entries reached? → A: LRU eviction (cachetools default) - oldest unused entries removed first; acceptable since DynamoDB provides durable layer
- Q: How does `put_cached_candles` determine `end_date` for TTL calculation? → A: Add explicit `end_date` parameter to `_write_through_to_dynamodb` and `put_cached_candles`; caller passes the request's end_date
- Q: Lock wait timeout (500ms) shorter than Tiingo API latency (500-2000ms) - waiters timeout and cause thundering herd? → A: Increase to 3000ms total (15×200ms) to cover worst-case Tiingo latency plus write-through overhead
- Q: Smoke test authentication - OHLC endpoint requires auth? → A: Yes - use `SMOKE_TEST_API_KEY` env var; pipeline worker retrieves from AWS Secrets Manager at job start
- Q: Strong consistent reads (2x cost) for all DynamoDB queries - cost trade-off? → A: Hybrid approach - eventual consistency for initial cache read, strong consistency only for lock waiter retries (halves read cost for happy path)

## Session 2026-02-04 (Round 7)
- Q: Data Flow diagram shows "Wait 100ms, retry (up to 5 times)" but implementation uses 200ms × 15 retries - inconsistent? → A: Update diagram to match implementation (200ms × 15 retries = 3000ms total)
- Q: Section 6.5 says "acceptable for now" but Section 11.4 says "wrap in asyncio.to_thread() now" - contradiction? → A: Section 11.4 is authoritative; update Section 6.5; ALSO audit codebase for other async functions making sync network calls without await
- Q: Code examples show inline `boto3.client()` but 11.13 says use singletons - inconsistent? → A: Update all code examples to use eager singleton factory; add `_reset_all_clients()` for testing
- Q: Compatibility with future WebSocket ingestion for real-time prices? → A: Documented in `future/realtime-ohlc-two-zone-architecture.md` - current work focuses on Zone 1 (filled buckets); designed for reuse when adding Zone 2 (partial buckets)
- Q: Today's intraday data - Zone 1 or Zone 2? Cache staleness within same day? → A: Short TTL (5min) for today's intraday cache entries; treats all as Zone 1 for now; simplest migration path to Zone 2 (no Zone 1 changes needed, just add Zone 2 on top)
- Q: DynamoDB eventual consistency on read-after-write causing lock waiters to miss just-written data? → A: Read-through cache pattern with strong consistent DynamoDB reads; in-memory cache for same-instance speed (~1ms), strong DDB reads for cross-instance consistency (~40ms); lock only protects Tiingo fetch
- Q: CloudWatch client created fresh on every metric emission (+50-100ms overhead)? → A: ALL boto3 clients must be singletons - DynamoDB, CloudWatch, and any future service clients; establish as architectural principle
- Q: Smoke test checks log string "OHLC cache hit (DynamoDB)" - fragile if message changes? → A: Add `X-Cache-Source` response header for immediate verification; values: "in-memory", "dynamodb", "tiingo"; useful for debugging and smoke tests

## Session 2026-02-04 (Round 8 - Testing Deep Dive)

Principal-level review of testing strategy, working backwards from failure modes.

**Methodology Applied:**
- Worked backwards from production failures, not forwards from implementation
- Identified 8 failure categories: Cache Keys, Data Integrity, Timing/TTL, Race Conditions, Dependency Failures, State Management, Edge Cases, Playwright/UI
- Generated 110+ test cases across unit, integration, and E2E layers
- Created test fixtures and failure injection helpers for resilience testing
- Documented test priority matrix (P0-P3) based on impact and likelihood

**Key Additions (Section 15):**
- 15.1: Test Taxonomy Overview diagram
- 15.2: Category A - Cache Key Correctness (10 tests)
- 15.3: Category B - Data Integrity (12 tests)
- 15.4: Category C - Timing & TTL (12 tests)
- 15.5: Category D - Race Conditions (12 tests)
- 15.6: Category E - Dependency Failures (18 tests including reboot consequences)
- 15.7: Category F - State Management (9 tests)
- 15.8: Category G - Edge Cases (19 tests)
- 15.9: Category H - Playwright/UI (20 tests including viewport, network, animation)
- 15.10: Test Priority Matrix (P0-P3 justifications)
- 15.11: Test Fixtures Required (CacheTestScenario, parameterized scenarios)
- 15.12: Failure Injection Helpers (CacheFailureInjector patterns)
- 15.13: Playwright Test Utilities (cache metrics tracking, viewport helpers)
- 15.14: Test Execution Order (CI/CD workflow)
- 15.15: Test Coverage Gates (thresholds and actions)
- 15.16: Debugging Test Failures (investigation order, common patterns)

**Reboot Consequence Tests (E15-E18):**
- Cold start after reboot reads from DynamoDB (in-memory cleared)
- Reboot during write-through: verify data integrity on recovery
- Reboot clears circuit breaker state (module reload)
- Stale lock after reboot: TTL releases orphaned locks

**Playwright-Specific Tests (H11-H20):**
- Viewport resize maintains data (widths: 1920, 1280, 768, 375)
- Mobile viewport chart readable (375x667 visual regression)
- Fullscreen toggle preserves data
- Landscape to portrait rotation
- Slow 3G shows loading state
- Offline shows graceful error with retry button (no service worker)
- Reconnect after offline refreshes data
- Chart animation completes without glitch
- Hover tooltip accuracy
- Zoom animation smoothness (performance metrics)

## Session 2026-02-04 (Round 9 - Test Implementability)
- Q: How should thundering herd tests (D1) simulate concurrency in single-process pytest? → A: Use `asyncio.gather()` with 10 async tasks in single pytest process; matches async nature of cache implementation
- Q: How should time-dependent TTL tests (C1-C11) handle time manipulation without waiting? → A: Use `freezegun` library to freeze/advance time; standard Python time mocking, integrates with pytest
- Q: How should cross-Lambda isolation (F8) be simulated with isolated module singletons? → A: Use `importlib.reload()` to reset module state; simulates cold start realistically, catches bugs mocking would miss
- Q: What is expected offline behavior for chart (H16)? → A: No service worker; offline shows graceful error state with retry button; test verifies error message displayed, not crash
- Q: Which DynamoDB mock for integration tests - moto vs LocalStack vs preprod? → A: Hybrid approach - moto (`@mock_aws`) for unit + integration tests (fast CI, failure injection); expand existing smoke test for preprod sanity tests (real AWS validation for B11, B12, F8)

## Session 2026-02-04 (Round 10 - Observability Testing)
- Q: How should tests verify logging and metric emission (E1-E12)? → A: Use pytest `caplog` fixture for log assertions + mock `put_metric_data` for metrics; RETROACTIVE: audit existing tests for missing observability assertions

## Session 2026-02-04 (Round 11 - Testing Deep Dive Backwards)
- Q: How to prevent timing-dependent tests (C6, C11-C12, D1, D4-D5, H2-H3) from flaking in CI? → A: Tolerance bands in CI, exact assertions locally; use `CI_TOLERANCE_FACTOR=1.5` env var; assertions like `assert 1500 < response_time < 4500` in CI vs `assert 2800 < response_time < 3200` locally
- Q: How to prevent Playwright tests failing with generic "element not found" when data-testid missing? → A: Bootstrap assertion in Playwright globalSetup verifies all required selectors exist before tests run; clear error message names exactly which data-testids are missing
- Q: How to isolate preprod sanity test data from production data and concurrent CI runs? → A: Belt-and-suspenders: (1) test-prefixed cache keys `TEST#{run_id}#ohlc:...` with 5-minute TTL auto-cleanup, (2) explicit delete after test run for immediate isolation
- Q: What is the scope of retroactive observability audit for caplog/metric assertions? → A: Current scope limited to this spec's 4 alerting metrics (CacheError, CircuitBreakerOpen, CachePaginationTruncation, UnprocessedWriteItems); full codebase audit punted to future work doc `future/observability-metric-coverage-audit.md`; pattern established here first, then ported to entire codebase
- Q: How to prevent async test pollution (event loop closed, pending tasks) in race condition tests D1-D12? → A: `pytest-asyncio` strict mode with per-test event loop isolation + `autouse` fixture that verifies no pending tasks remain after each test

## Session 2026-02-04 (Round 12 - Testing Deep Dive Continued)
- Q: What tooling for visual regression tests (H12, H18)? → A: Playwright built-in `toHaveScreenshot()` with 0.1% pixel diff threshold; baselines stored in repo; simpler than external services, works offline, CI-friendly
- Q: How to generate test data for edge cases (G1-G19) - weekends, holidays, splits, ticker changes? → A: Synthetic generator using `exchange_calendars` library for dynamic trading day computation + recorded golden fixtures for complex scenarios (splits, ticker changes); avoids brittle hardcoded dates
- Q: Should tests verify user-facing error messages are helpful, not just HTTP status codes? → A: Yes, test ~5 user-visible error scenarios with actionable messages; don't test internal errors (those are for logs); contract tests assert both status code AND response body contains actionable guidance
- Q: How to ensure production bugs get regression tests to prevent reoccurrence? → A: PR template requires regression test section for bug fixes; test ID format `R{issue_number}` (e.g., `R1234_cache_key_missing_date_anchor`); test must fail before fix, pass after; linked to issue for traceability
- Q: What quantitative thresholds define "smooth" for performance tests (H20) and cache response times? → A: Specific thresholds - cache hit <100ms, cache miss <2500ms, animation ≥30fps, no frame drops >100ms; baselines stored in config; alert on >20% regression from baseline

## Session 2026-02-04 (Round 13 - Testing Final Pass)
- Q: How to verify moto mock behaves like real DynamoDB (mock fidelity)? → A: Weekly mock fidelity test comparing moto vs preprod behavior; scheduling via GitHub API query for last successful run date - if >7 days, trigger fidelity test in CI; self-contained, no external scheduler needed
- Q: Should tests verify dangerous things DON'T happen (secrets logged, PII cached, stack traces leaked)? → A: Yes, dedicated security test category S1-S5 for negative assertions; tests that secrets not in logs, PII not cached, error responses don't leak internals, cache keys don't contain sensitive data
- Q: Should Playwright tests run on multiple browsers or Chromium only? → A: All tests (H1-H20) on all 3 browsers (Chromium, Firefox, WebKit/Safari); comprehensive coverage worth slower CI; visual regression baselines stored per-browser
- Q: How to prevent tests from going stale (mocking outdated signatures)? → A: Mock signature validation using `inspect.signature()` to verify mocked functions match real function signatures; new code paths covered by existing 90% coverage gate

## Session 2026-02-04 (Round 14 - Testing Backwards Analysis)
- Q: How should the test suite verify cache key correctness when Lambda executes in a timezone different from market timezone (ET)? → A: Add C13 test `test_cross_timezone_lambda_execution` that mocks Lambda in us-west-2 at 11pm PT, verifies cache key uses ET date anchor regardless of execution timezone
- Q: Should we rely on AWS Lambda Powertools for observability rather than custom logging tests? → A: Yes, use full AWS Lambda Powertools (Logger + Metrics + X-Ray 100%) for maximum visibility (~$18/month at 100K req/day); trust framework, add one smoke test verifying correlation ID in logs
- Q: How should tests verify that browser-level caching doesn't cause confusion when backend cache refreshes with new data? → A: Add H21-H22 tests verifying `Cache-Control: no-store` or short max-age header prevents browser from caching stale OHLC responses
- Q: How should tests verify that missing or misconfigured environment variables fail fast rather than causing silent cache misconfigurations? → A: Full approach - (1) CI lint rule blocks direct `os.environ` access, forces all env vars through pydantic Settings class, (2) pydantic validates at import time, (3) custom Secrets Manager fetch with actionable errors, (4) E24-E26 tests verify error messages are actionable
- Q: How should Playwright tests verify that changing ticker mid-request doesn't cause stale data from the previous ticker to display? → A: Skip H23 - frontend uses TanStack Query (@tanstack/react-query v5) which automatically cancels in-flight requests when query key changes; library handles this race condition by design

## Session 2026-02-07 (Round 19 - Source Code Blind Spots)

**Methodology:** Post-testing deep analysis of source code implications. Cross-referenced spec against actual codebase (7 source files, 4 dependency files, 3 adapter files) to find implementation-breaking blind spots.

**Decisions (Q1-Q5 + FQ1-FQ5):**

- Q1: `CircuitBreakerManager` circular dependency — persists state TO DynamoDB, can't record DynamoDB failure when DynamoDB is down? → A: **In-memory-only `LocalCircuitBreaker`** for DynamoDB cache service. `@protect_me` decorator pattern (module-level singleton, nanosecond `is_open()` check). Protects both reads and writes. **Supersedes Round 18 Q4** — `"dynamodb_cache"` NOT added to distributed `CircuitBreakerManager`.

- Q2: Resolution fallback creates orphaned lock — lock key uses original resolution, data written under fallback resolution, waiters never find data? → A: **Cache aliasing (double write)** — write under BOTH original and fallback resolution keys. Alias gets shorter TTL.

- Q3: `_tiingo_cache` survives Round 18 consolidation — 4th cache layer causes TTL inversion (adapter's 1hr TTL defeats DynamoDB's 5min intraday TTL)? → A: **Surgical bypass** — OHLC methods pass `use_cache=False`, News/Sentiment keep adapter cache. Adapter stateless for OHLC only.

- Q4: `@dynamodb_retry` + `dynamodb_batch_write_with_retry` compound to 9 retries? → A: **Strict boundary** — `@dynamodb_retry` single-item only, `batch_write_with_retry` batch only, never nest. 10s hard cap. EMF metrics inside worker thread. X-Ray on event loop thread only.

- Q5: `cachetools` missing from all deps, `from typing import Callable` violates Ruff UP035? → A: **Skip `cachetools`** — reuse `ResolutionCache` (existing `OrderedDict` LRU). Modify to accept `default_ttl` parameter. `from collections.abc import Callable, Awaitable`.

- FQ1: Cache alias rejected by completeness check — 5 daily candles ≠ 390 expected 5-min candles? → A: **Add `res_a` metadata field** — completeness check validates against actual resolution, not requested. Frontend uses existing `resolution_fallback: true`.

- FQ2: Removing `_tiingo_cache` breaks News/Sentiment (shared dict)? → A: **Option A — surgical bypass** — OHLC methods hardcode `use_cache=False`, News/Sentiment unchanged.

- FQ3: X-Ray subsegments inside `asyncio.to_thread()` are orphaned (thread-local storage gap)? → A: **Post-await instrumentation** — X-Ray subsegments on event loop thread, EMF metrics inside worker thread. `batch_write_with_retry` returns `BatchWriteStats` dict for annotation enrichment.

- FQ4: Round 15 SLRU decision conflicts with `ResolutionCache` reuse? → A: **Simple LRU, rollback SLRU** — DynamoDB ~20ms miss penalty makes SLRU unjustified. Lambda lifecycle too short for frequency tracking. Modify `ResolutionCache` to accept optional `default_ttl: int | None = None` (~3-5 line delta).

- FQ5: `@protect_me` on writes too? → A: **Protect both reads and writes** — prevents "zombie writes" wasting Lambda duration and thread pool resources during DynamoDB brownout.

**Rollbacks:**
- Round 18 Q4 (`CircuitBreakerManager` for `dynamodb_cache`) → Superseded by in-memory `LocalCircuitBreaker`
- Round 15 (SLRU ~30 lines custom code) → Downgraded to simple LRU via existing `ResolutionCache`

**Total tests:** 160 across 11 categories (unchanged from Round 18)

## Session 2026-02-08 (Round 25 - Post-Round-24 Full Drift Audit)

**Methodology:** Full drift audit of spec (2830 lines) and test plan (3950 lines) post-Round-24. Parallel subagent scan with line-by-line verification against `OHLCRequestContext` refactoring. Found: 2 undefined helper functions blocking handler construction (100% crash rate), sync/async naming collision, observability section with stale signatures, test plan with broken imports and pre-R24 positional args, quick reference count drift. 5 HIGH, 3 MEDIUM, 1 LOW = 9 actionable issues.

**Decisions (Q1-Q5):**

- Q1: `_get_default_source(ticker)` and `_resolve_date_range(time_range)` called at handler entry but never defined — double NameError before `OHLCRequestContext` even constructed. → A: **Define both in new Section 4.0.1** — `_resolve_date_range` maps "1D/1W/1M/3M/6M/1Y/YTD" to `(start_date, end_date)` using ET market timezone. `_get_default_source` returns `"tiingo"` (centralized failover knob). Also fixed Section 4.3 bare variables → `ctx.*`.

- Q2: Section 4.3 `_read_from_dynamodb` defined as sync `def` but called with `await` everywhere — `TypeError` at every call site (same bug class as Round 23 Q4). → A: **Rename to `_read_from_dynamodb_sync`** with cross-reference to Section 11.7 async wrapper. Naming symmetry with write path.

- Q3: Section 12.4 observability snippets use pre-Round-24 `(ticker: str, source: str, ...)` signature, bare `cache_key`, and `@tracer.capture_method` on sync function (orphaned X-Ray segments). → A: **Update to `ctx: OHLCRequestContext` + post-await X-Ray instrumentation.** "Clean Room" pattern: sync = pure I/O, async wrapper = orchestration + tracing.

- Q4: Section 15 Quick Reference says 176 tests / D:28 — stale after R24 added D36-D39 (180 / D:36). → A: **Update counts to match canonical test plan.** D: 28→36, Total: 176→180, add R24/R25 mentions.

- Q5: Test C14 calls `_resolve_date_range` and `_get_ohlc_cache_key` without importing. Test M1/M2 use pre-R24 positional string args. → A: **Fix both to ctx pattern** — C14 adds explicit imports, M1/M2 construct `OHLCRequestContext` and use `await`.

**Tests Fixed:** C14 (missing imports), M1 (old signature), M2 (old signature). R25 helper function tests to be formally numbered during `/speckit.plan`.

**Sections Updated:** 4.0.1 (NEW: handler entry helpers), 4.3 (renamed to `_read_from_dynamodb_sync` + cross-ref), 12.4 (ctx pattern + post-await X-Ray), 15 Quick Reference (counts + R24/R25), Clarifications (Round 25 session), test plan (C14 imports, M1/M2 ctx pattern).

## Session 2026-02-08 (Round 24 - OHLCRequestContext & Circuit Breaker Audit)

**Methodology:** Deep audit using parallel subagent scan of the full spec post-Round-23. Principal-level scrutiny of: Data Clump anti-pattern in call chain signatures, circuit breaker observability gaps (write-side blind spot), error-path/happy-path parameter parity, test plan coverage for new constructs, and supplementary section drift from canonical implementation. Found 1 NameError (undeclared params), 1 design gap (breaker deaf to writes), 1 TypeError (missing param in error path), 1 test coverage gap, 1 stale code drift.

**Decisions (Q1-Q5):**

- Q1: Handler uses `start_date`, `end_date`, `source` as bare variables not in intermediate function signatures — NameError. Call chain passes 5-7 individual params (Data Clump). → A: **Introduce frozen `OHLCRequestContext` dataclass** — constructed once at handler entry, passed as single `ctx` param. Frozen for `asyncio.to_thread()` safety. `to_metadata()` for X-Ray/EMF. Write context dict simplified to `{"ctx": ctx, "candles": candles}`. Refactored 4 function signatures.

- Q2: `_write_through_to_dynamodb` never calls `record_failure()`/`record_success()` — circuit breaker "deaf" to write-side DynamoDB health. Write failures burn ~200ms per request on dead path. → A: **Writes contribute to same `_DDB_BREAKER`** — `is_open()` guard encapsulated inside function (handler guard simplified to `if pending_write:`). `record_success()` after write, `record_failure()` in except. During HALF_OPEN, write success helps close circuit faster.

- Q3: Handler timeout fallback calls `_estimate_cache_age_from_dynamodb(stale_candles)` — missing `resolution` param. TypeError turns graceful degradation into dashboard crash. Happy path already passes `ctx.resolution`. → A: **Pass `ctx.resolution`** — matches happy-path pattern. Correct TTL lookup (5min intraday vs 90d daily). Zero data bloat.

- Q4: Test plan has zero Round 24 coverage. No R24 column. OHLCRequestContext, breaker write visibility, timeout age fix all untested. C14 uses stale `.create()` factory method. → A: **Add D36-D39** — D36: write success → `record_success()`, D37: write failures trip breaker, D38: timeout age uses `ctx.resolution`, D39: frozen + `to_metadata()` + `replace()`. Fixed C14. Total 176 → 180.

- Q5: Sections 11.3 and 11.7 async wrappers use pre-Round-24 individual params. Section 11.7 write wrapper missing `_DDB_BREAKER` calls. Implementers copying would get NameErrors and re-introduce breaker blind spot. → A: **Update all three snippets to `ctx: OHLCRequestContext` pattern** — read wrapper: `(ctx, consistent_read)` + breaker. Write wrapper: `(ctx, candles)` + `is_open()` + `record_success/failure`. Zero architectural drift between supplementary and canonical sections.

**Tests Added:** D36-D39 (+4 tests, total 180 across 11 categories). C14 stale factory method fixed.

**Sections Updated:** 4.0 (NEW: OHLCRequestContext dataclass), 4.2 (ctx param + breaker calls), 4.3 (ctx param + consistent_read), 4.8 (ctx param + write context dict), 4.9 (ctx param), 4.10 (ctx construction + simplified Phase 2 guard), 11.3 (ctx in breaker snippet), 11.7 (ctx in async wrappers + breaker calls), test plan (D36-D39 + R24 column + C14 fix)

## Session 2026-02-08 (Round 23 - Post-Round-22 Deep Audit)

**Methodology:** Deep audit using 3 parallel subagent scans across the full spec (2600+ lines) and test plan (3600+ lines). Principal-level scrutiny of: kwargs contract alignment, method completeness across delegation chains, sync/async boundary correctness, test plan canonical accuracy, and cache API sentinel behavior. Found 3 runtime-crashing bugs (TypeError, AttributeError, TypeError) and 1 documentation inconsistency.

**Decisions (Q1-Q5):**

- Q1: `_write_through_to_dynamodb(**pending_write)` crashes — write context dict key `"candles"` mismatches function parameter `ohlc_candles`. L2 cache never populated. → A: **Rename parameter to `candles`** — ubiquitous domain language, kwargs unpacking self-documenting. Type hint tightened to `list[PriceCandle]`.

- Q2: `OHLCReadThroughCache` missing `.invalidate()` and `.clear()` methods — Section 11.11 public API calls them, crashes with `AttributeError`. → A: **Delegate to `ResolutionCache`** — add `invalidate(prefix)` and `clear()` to data layer, `OHLCReadThroughCache` wraps as thin delegates. O(1000) scan <1ms.

- Q3: Test plan says 162 tests, main spec says 172. D21-D31 never propagated to canonical test plan. Round 22/23 constructs untested. → A: **Update test plan as canonical source** — added D21-D35, E31. Total 162 → 178. Summary table extended.

- Q4: `_write_through_to_dynamodb` is `def` (sync) but handler does `await` on it — `TypeError`. Also blocks event loop during DDB I/O. → A: **Make `async def` with `asyncio.to_thread(put_cached_candles, ...)`** — aligns with Round 1 Q4 architectural decision.

- Q5: `ResolutionCache.get_with_age()` behavior on missing keys unspecified — `get_age()` tuple unpacking crashes with `TypeError`. → A: **Return `(None, 0.0)` sentinel tuple** — zero-surprise contract, callers always destructure safely.

**Tests Added:** D32-D35 (+4 tests, total 178 across 11 categories)

**Sections Updated:** 4.2 (async def + to_thread + param rename), 4.8 OHLCReadThroughCache (.invalidate/.clear methods), ResolutionCache modification spec (sentinel tuple, invalidate, clear), 11.1 (test example public API), 11.7 (stale ohlc_candles reference), 11.11 (confirmed working after Q2), test plan file (D21-D35 + E31 + summary table)

## Session 2026-02-08 (Round 22 - Post-Round-21 Consistency Audit)

**Methodology:** Systematic audit of cascading consistency failures introduced by Round 21's Two-Phase Handler refactor. Principal-level scan for: return type mismatches, memory leaks from new data structures, stale code references to removed/renamed entities, and terminology drift from superseded designs.

**Decisions (Q1-Q5):**

- Q1: `_fetch_with_lock` has inconsistent return types — Step 7 returns tuple but all other paths return bare values. Handler destructures `result, pending_write = await ...` which crashes on bare returns. → A: **Uniform tuple contract**: ALL return paths return `(candles, write_context | None)`. Type signature: `-> tuple[list[PriceCandle], dict | None]`.

- Q2: `OHLCReadThroughCache._timestamps` dict (Round 21 Q4) grows unbounded — `ResolutionCache` evicts LRU but `_timestamps` keys never removed, causing memory leak and zombie ages. → A: **Store `(value, inserted_at)` tuples inside `ResolutionCache` directly** — atomic eviction removes both in same `popitem()`. New `get_with_age()` method. Zero maintenance, zero leak.

- Q3: Section 4.9 `get_ohlc_data()` references non-existent `dynamodb_result.age_seconds` and uses pre-Round-21 single-return pattern conflicting with two-phase handler. → A: **Rewrite as `_get_ohlc_data_with_write_context()`** — returns `tuple[OHLCResponse, dict | None]`. L1 age via `get_age()`, L2 age via `_estimate_cache_age_from_dynamodb()`.

- Q4: Section 11.11 `invalidate_all_caches()` imports `_ohlc_cache` (removed Round 18) and calls phantom `_invalidate_ohlc_response_cache()`. ImportError crashes entire invalidation subsystem. → A: **Export named `invalidate_ohlc_cache(ticker)` function from `ohlc.py`** — public API delegates to `_ohlc_read_through_cache`. `cache_manager.py` imports function, not private instance. Encapsulation preserved, mockable, X-Ray traceable.

- Q5: Section 4.2 "Fire-and-forget" docstring and constraints contradict Round 20/21 "awaited" design. Term implies no `await`, safe to skip — misleads developers into re-introducing Lambda freeze bug. → A: **Replace with "Phase 2 awaited"** — docstring: "Awaited before handler returns to prevent Lambda freeze mid-write. Invisible to user latency; additive to billed duration only (~50ms)." Constraints: "Phase 2 awaited: errors logged, non-fatal, write completion guaranteed."

**Tests Added:** None (consistency fixes to existing spec sections, no new behavioral requirements)

**Sections Updated:** 4.2 (docstring + constraints + call sites), 4.8 (_fetch_with_lock uniform tuple), 4.8 (OHLCReadThroughCache atomic tuple storage), 4.9 (rewritten as _get_ohlc_data_with_write_context), 11.11 (invalidation encapsulation boundary)

## Session 2026-02-08 (Round 21 - Two-Phase Handler Architecture)

**Methodology:** Post-Round-20 architectural reconciliation. Cross-referenced timing constraints, circuit breaker state machine, resolution fallback races, undefined helper functions, and DST edge cases. Principal-level analysis focused on implementation-breaking contradictions.

**Decisions (Q1-Q5):**

- Q1: Write-through `await` inside `asyncio.wait_for(timeout=5.0)` contradicts `batch_write_with_retry` 10s hard cap — timeout cancels write mid-batch. → A: **Two-Phase Handler Architecture**: Phase 1 (Response, 5s cap) returns `(response, pending_write_context)`. Phase 2 (Persistence, outside timeout) awaits write-through before handler returns. User latency capped. Write integrity guaranteed. Refines Round 20 Q2+Q3.

- Q2: `LocalCircuitBreaker` half-open probe behavior unspecified — how many probes, what closes/re-opens. → A: **Single-probe model**: OPEN→HALF_OPEN after 30s timeout, 1 request probes. Success → CLOSED. Failure → OPEN (another 30s). Matches existing `CircuitBreakerManager` for SRE consistency. Multi-probe/gradual ramp over-engineering for Lambda lifecycle.

- Q3: Concurrent resolution fallback creates duplicate Tiingo calls — different locks for 5-min/60-min both fall back to daily. → A: **Accept as known trade-off**. Natural cap ~3 resolutions. Idempotent writes. Self-correcting. Secondary lock risks deadlocks. Documented in Section 6.9.

- Q4: `_estimate_cache_age_from_dynamodb()` and `get_age()` referenced but never defined — X-Cache-Age always 0. → A: **Derivation over redundancy**. L1: `_timestamps` dict tracks insertion time. L2: derive from `ExpiresAt - TTL_DURATION`. No new DynamoDB attribute needed.

- Q5: `_estimate_expected_candles()` drifts by 1 candle on DST transition days (2/year) — forces unnecessary re-fetch. → A: **Accept as known limitation**. ~100 extra API calls/year. Self-correcting. `exchange_calendars` adds maintenance tax. 1-candle tolerance weakens data contract for 363 normal days.

**Tests Added:** D28-D31 (+4 tests, total 172 across 11 categories)

**Sections Updated:** 4.8 (fetch_with_lock step 7, guarantees), 4.10 (two-phase handler), 5 (data flow diagram), 6.9 (new: concurrent resolution fallback), 11.9 (DST limitation), 11.16 (half-open state machine + full implementation), OHLCReadThroughCache (age tracking)

## Session 2026-02-06 (Round 18 - Architecture Reconciliation)

- Q: BatchWriteItem vs ConditionExpression (`updated_at`) incompatibility — DynamoDB BatchWriteItem does NOT support ConditionExpression? → A: Drop `updated_at` ConditionExpression for cache writes — candle data is idempotent. Lock PutItem retains its ConditionExpression. Tests D15/D16 removed.
- Q: 4 cache layers (not 3) — `_ohlc_cache` dict + `OHLCReadThroughCache` are parallel in-memory caches storing different types? → A: Replace `_ohlc_cache` with `OHLCReadThroughCache` — single in-memory layer. Remove `_ohlc_cache`, `_get_cached_ohlc()`, `_set_cached_ohlc()`, `_ohlc_cache_stats`, `invalidate_ohlc_cache()`.
- Q: `_calculate_ttl()` uses `date.today()` (UTC) — ~3 hours/day incorrect TTL assignment? → A: Use `datetime.now(ZoneInfo("America/New_York")).date()` — market-timezone-aware, covers DST automatically.
- Q: Existing `CircuitBreakerManager` (474 lines, DynamoDB-persisted, thread-safe) vs spec's simple dict-based CB? → A: ~~Reuse existing — add `"dynamodb_cache"` as service.~~ (SUPERSEDED by Round 19 Q1: Use in-memory `LocalCircuitBreaker` instead — avoids circular dependency where DynamoDB monitors itself.)
- Q: Eager singleton `aws_clients.py` breaks moto/LocalStack test isolation? → A: Lazy singleton in existing `dynamodb.py` with `_reset_all_clients()`. No new file.

## Session 2026-02-04 (Round 15 - Session Summary)

**Tests Added:** D14, E27-E30, F10-F11, H24-H27, O2 (+12 tests, total 146)

**Key Decisions:**
- Cold start cascade: Rely on Tiingo's 429 response (no proactive throttling)
- Partial batch writes: Atomic semantics - rollback if any item fails
- Lock safety margin: Explicit invariant test: TTL ≥ 2× max latency
- Tab staleness: Auto-refresh on focus after 5+ minutes
- Schema drift: Trust adapter layer (no contract tests)
- Time mocking: Use freezegun (not cross-timezone patch)
- Cache eviction: ~~Implement SLRU (~30 lines custom code)~~ (SUPERSEDED by Round 19 FQ4: Simple LRU via existing `ResolutionCache` with `default_ttl` parameter — DynamoDB ~20ms miss penalty makes SLRU unjustified in Lambda's short lifecycle)
- Animation testing: Deterministic stubs (not disabled, not real-time)
- DB isolation: Autouse cleanup + short TTL (already established)
- Error retry: TanStack recommended + 429 Retry-After handling

**Deferred:**
1. WebSocket/Real-Time Cache Invalidation
2. Multi-Region/Disaster Recovery

## Session 2026-02-08 (Round 26 - Source Code Cross-Reference Audit)

**Methodology:** Cross-referenced ~2930 lines of spec against ~2795 lines of source code across 7 files (ohlc.py, ohlc_cache.py, models/ohlc.py, cache.py, circuit_breaker.py, base.py, tiingo.py). Verified function signatures, import paths, module boundaries, and deeply-piped data structures. Found 3 HIGH (runtime-crashing), 2 MEDIUM (implementation blockers). All pre-existing from original spec construction meeting source code reality — none introduced by previous rounds.

**Decisions (Q1-Q5):**

- Q1 (HIGH): `OHLCResponse(status="degraded")` in timeout handler (Section 4.10) crashes — OHLCResponse has no `status`/`message` field, missing 7 required fields. Every timeout = pydantic `ValidationError`. → A: **Discriminated union `OHLCHandlerResponse = Union[OHLCResponse, OHLCErrorResponse]`** — dedicated `OHLCErrorResponse(status, message, candles, ticker)` for timeout/failure paths. Clean contract separation: success model strict (99% path), error model cheap to construct (emergency path). Frontend TypeScript type guard on `status` field.

- Q2 (HIGH): `_estimate_expected_candles` has 3 incompatible signatures: source (date, date, OHLCResolution), spec 4.3 (ctx.start_date, ctx.end_date, ctx.resolution as str), spec 11.9 (days: int, resolution: str). → A: **Keep source signature `(start_date: date, end_date: date, resolution: OHLCResolution)`** — most correct and complete. Fixed Section 11.9 to match. Section 4.3 call site adds `OHLCResolution(ctx.resolution)` conversion.

- Q3 (HIGH): `get_ohlc_handler` (spec Section 4.10) disconnected from actual FastAPI route `get_ohlc_data` — 5 incompatibilities (enum vs string, Depends, custom dates, timezone, time range values). → A: **OPEN — BLOCKED on FastAPI+Mangum removal.** Deep dive confirmed FastAPI is production architecture (Mangum + Lambda Function URL + API Gateway dual entry points). However, user has decided to rip out FastAPI+Mangum before continuing cache work. Q3 resolution deferred until new handler architecture is established.

- Q4 (MEDIUM): `put_cached_candles` missing `end_date` param, `ExpiresAt` attribute, `get_cached_candles` missing `ExpiresAt` in ProjectionExpression. → A: **Spec already correct** — Sections 4.2 (line 337), 4.6 (line 494, 543-548), 11.16 (line 1247-1277) all specify ExpiresAt correctly. This is a source-code-only gap; no spec changes needed.

- Q5 (MEDIUM): Tests D21-D27 use pre-R24 positional params, M3 uses pre-R19 dict breaker. → A: **Fixed immediately** — D21/D22 updated to `_fetch_with_lock(ctx)`, D23/D25-D27 updated with explicit `get_ohlc_handler("AAPL", "D", "1W", mock_response)`, D27 updated to assert `OHLCErrorResponse`. M3 updated from `_record_failure()` standalone function to `_DDB_BREAKER.record_failure()` method.

**Tests Fixed:** M3 (pre-R19 dict breaker → LocalCircuitBreaker), D21-D22 (positional → ctx), D23/D25-D27 (ellipsis → explicit params), D27 (OHLCResponse → OHLCErrorResponse assertion).

**Sections Updated:** 4.3 (OHLCResolution enum conversion at call site), 4.10 (OHLCErrorResponse model + discriminated union + fixed timeout constructors), 11.9 (signature aligned to source), test plan (M3, D21-D27).

**Status: BENCHED** — Cache remediation work paused pending FastAPI+Mangum removal (thicker architectural change). Q3 remains OPEN.

---

## Standing Architectural Notes

**DO NOT SUGGEST FastAPI + Mangum (Standing Note, 2026-02-08):**
The FastAPI + Mangum + Lambda Function URL architecture is scheduled for removal. Do not suggest, re-introduce, or build upon this pattern. The caching layer must not depend on FastAPI routing, `Depends()` injection, or Mangum event translation. When cache work resumes post-removal, Q3 will be re-evaluated against the new handler architecture.
