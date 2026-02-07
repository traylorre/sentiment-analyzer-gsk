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

## Session 2026-02-06 (Round 18 - Architecture Reconciliation)

- Q: BatchWriteItem vs ConditionExpression (`updated_at`) incompatibility — DynamoDB BatchWriteItem does NOT support ConditionExpression? → A: Drop `updated_at` ConditionExpression for cache writes — candle data is idempotent. Lock PutItem retains its ConditionExpression. Tests D15/D16 removed.
- Q: 4 cache layers (not 3) — `_ohlc_cache` dict + `OHLCReadThroughCache` are parallel in-memory caches storing different types? → A: Replace `_ohlc_cache` with `OHLCReadThroughCache` — single in-memory layer. Remove `_ohlc_cache`, `_get_cached_ohlc()`, `_set_cached_ohlc()`, `_ohlc_cache_stats`, `invalidate_ohlc_cache()`.
- Q: `_calculate_ttl()` uses `date.today()` (UTC) — ~3 hours/day incorrect TTL assignment? → A: Use `datetime.now(ZoneInfo("America/New_York")).date()` — market-timezone-aware, covers DST automatically.
- Q: Existing `CircuitBreakerManager` (474 lines, DynamoDB-persisted, thread-safe) vs spec's simple dict-based CB? → A: Reuse existing — add `"dynamodb_cache"` as service. Remove spec's dict-based `_circuit_breaker`.
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
- Cache eviction: Implement SLRU (~30 lines custom code)
- Animation testing: Deterministic stubs (not disabled, not real-time)
- DB isolation: Autouse cleanup + short TTL (already established)
- Error retry: TanStack recommended + 429 Retry-After handling

**Deferred:**
1. WebSocket/Real-Time Cache Invalidation
2. Multi-Region/Disaster Recovery
