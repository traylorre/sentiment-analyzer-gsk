# Feature Specification: OHLC Cache Reconciliation

**Feature Branch**: `1218-ohlc-cache-reconciliation`
**Created**: 2026-02-12
**Status**: Draft
**Input**: Post-framework-purge reconciliation of OHLC cache specification and implementation quality
**Predecessor**: CACHE-001 (ohlc-cache-remediation, 26 clarification rounds)
**Supersedes**: The BENCHED status declared in ohlc-cache-remediation-clarifications.md (Round 26). The architectural blocker (removal of the previous web framework) is now complete. This spec reconciles the original CACHE-001 spec against the current codebase state.

## Background: Audit Summary

A deep audit on 2026-02-12 established that the original CACHE-001 checklist is **stale**. All five original work orders have been implemented in code. However, the implementation contains quality defects and the specification documents contain references to removed architectural patterns that must be purged.

**What exists and works:**
1. Cache key includes end_date (prevents cross-day staleness)
2. Write-through to persistent storage after external API fetch
3. Read-before-fetch: persistent storage checked before calling external API
4. Local development environment creates the cache table
5. Five test files cover unit and integration scenarios

**What is broken or missing:**
1. Cache layer silently swallows ALL errors — operators cannot distinguish "cache miss" from "cache is broken"
2. Persistent storage response parsing has a latent bug masked by a secondary code path
3. Cache write failures are silently lost (unprocessed items never retried)
4. No cache observability headers — consumers cannot tell if data came from cache vs. live API
5. No time-to-live on cached items — storage grows unbounded
6. Specification documents reference removed architectural patterns (must be purged to prevent reintroduction)
7. Code documentation (docstrings) contains inaccurate format descriptions

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Transparent Cache Failures (Priority: P1)

As an on-call engineer investigating elevated API latency, I need cache failures to be visible — not hidden — so I can distinguish between "cache is empty" (normal) and "cache is broken" (incident).

**Why this priority**: Silent failures are the most dangerous defect class. When the cache silently degrades, every request hits the external API. This appears as increased latency and rate-limiting (429 errors), but the root cause (broken cache) is invisible. The operator wastes time investigating the external API instead of the cache infrastructure. This is the #1 production risk.

**Independent Test**: Can be verified by intentionally misconfiguring cache storage permissions and confirming that the system surfaces an error rather than silently falling through.

**Acceptance Scenarios**:

1. **Given** the persistent cache storage is unreachable (permissions error, table deleted, or capacity exhausted), **When** a price data request arrives, **Then** the system MUST: (a) log at ERROR level with error category, (b) fetch data from the external API as an explicit degradation path, (c) return the data with a response header indicating degraded mode (`X-Cache-Source: live-api-degraded`), and (d) include an `X-Cache-Error` header describing the cache failure. This is a designed fallback — not silent degradation — because the failure is visible to operators (ERROR log), consumers (headers), and monitoring (metrics).
2. **Given** a cache write fails after fetching data from the external API, **When** the write error occurs, **Then** the system MUST: (a) log at ERROR level with error category, (b) still return the fetched data to the user (data is already in hand), and (c) include `X-Cache-Write-Error: true` header so consumers know subsequent requests will also miss the persistent cache.
3. **Given** the cache storage response contains unparseable data (corrupted items), **When** parsing fails, **Then** the system MUST raise an error with the specific parsing failure — not silently fall through to a secondary code path. The handler will catch this and apply the explicit degradation path (fetch from API with degraded headers).

---

### User Story 2 - Cache Observability Headers (Priority: P2)

As a frontend developer debugging stale chart data, I need to see where price data came from (in-memory cache, persistent cache, or live API) so I can determine if the issue is stale cache data or a data provider problem.

**Why this priority**: Without observability, debugging data freshness issues requires backend log access. Adding response headers enables frontend developers and QA to self-serve diagnosis. This reduces support burden and accelerates debugging.

**Independent Test**: Can be verified by making two sequential identical requests and confirming the response headers indicate "live-api" on the first and "persistent-cache" or "in-memory-cache" on the second.

**Acceptance Scenarios**:

1. **Given** price data is served from the in-memory cache, **When** the response is returned, **Then** it MUST include a header indicating the data source was "in-memory" and the age of the cached data in seconds.
2. **Given** price data is served from the persistent cache, **When** the response is returned, **Then** it MUST include a header indicating the data source was "persistent-cache" and the cache age.
3. **Given** price data is fetched from the external API (cache miss), **When** the response is returned, **Then** it MUST include a header indicating the data source was "live-api" with age of zero.
4. **Given** a cache write fails after a live API fetch, **When** the response is returned, **Then** it MUST include a header indicating the write failure occurred, so consumers know subsequent requests will also miss the cache.

---

### User Story 3 - Cached Data Expiration (Priority: P3)

As a product owner concerned about storage costs and data freshness, I need cached price data to automatically expire so that storage does not grow unbounded and stale intraday data is not served after market close.

**Why this priority**: Without expiration, the cache table grows indefinitely. Historical daily data is immutable and can be retained longer, but intraday data for the current trading day changes with every candle. Serving stale intraday data is worse than a cache miss.

**Independent Test**: Can be verified by writing a cached item with a short expiration, waiting for expiration, and confirming the item is no longer returned.

**Acceptance Scenarios**:

1. **Given** historical daily price data is cached, **When** 90 days elapse, **Then** the cached data MUST be automatically removed from persistent storage.
2. **Given** intraday price data for the current trading day is cached, **When** 5 minutes elapse, **Then** the cached data MUST be treated as expired (re-fetched from API on next request).
3. **Given** intraday price data for a completed (past) trading day is cached, **When** the trading day has ended, **Then** the cached data MUST be treated as immutable and retained for the full 90-day period (same as historical daily data).

---

### User Story 4 - Specification and Documentation Hygiene (Priority: P4)

As a developer onboarding to the codebase, I need specification documents and code documentation to accurately reflect the current architecture so I don't accidentally reintroduce removed patterns or build on incorrect assumptions.

**Why this priority**: The existing 3,000+ line specification references a web framework that was removed from the project. If a developer reads the spec and follows its code examples, they will introduce dependencies that no longer exist. Additionally, code docstrings describe data formats that don't match reality, creating confusion.

**Independent Test**: Can be verified by running the project's banned-term scanner against specification and documentation files and confirming zero violations.

**Acceptance Scenarios**:

1. **Given** the specification documents for cache remediation, **When** scanned for references to removed architectural patterns, **Then** zero references MUST be found.
2. **Given** the cache documentation directory, **When** the banned-term scanner runs without exclusions for that directory, **Then** zero violations MUST be found (the scanner exclusion for `docs/cache/` can be removed).
3. **Given** the cache module code documentation, **When** a developer reads the docstring for resolution format, **Then** the documented format MUST match the actual format used at runtime (e.g., if the system uses "5", the docstring must not say "5m").
4. **Given** the BENCHED status in the clarification history, **When** a developer reads it, **Then** it MUST be updated to reflect that the architectural blocker is resolved and work has resumed.

---

### User Story 5 - Latent Bug Remediation (Priority: P5)

As a reliability engineer, I need code paths that only work "by accident" (via fallback to secondary logic after a primary path silently fails) to be fixed so the primary path works correctly by design.

**Why this priority**: Code that works by accident is fragile. A seemingly unrelated change could remove the secondary path that masks the primary path's failure, causing a production outage with no warning.

**Independent Test**: Can be verified by confirming the primary parsing path succeeds directly without relying on exception-handler fallback logic.

**Acceptance Scenarios**:

1. **Given** cached price data is read from persistent storage, **When** the response is parsed, **Then** the primary parsing path MUST correctly extract field values without triggering an exception that falls through to a secondary parsing path.
2. **Given** a batch write to persistent storage has unprocessed items, **When** the batch write response indicates unprocessed items, **Then** the system MUST retry unprocessed items with exponential backoff (not silently log and discard them).
3. **Given** the market-hours utility function, **When** it determines if the market is open, **Then** it MUST NOT contain dead import paths for unsupported runtime versions.

---

### Edge Cases

- What happens when the persistent cache table does not exist (e.g., new environment, Terraform not yet applied)? The cache module raises an exception. The handler applies explicit degradation: serve from external API with `X-Cache-Source: live-api-degraded` and `X-Cache-Error: table-not-found` headers, plus ERROR-level logging.
- What happens when a cache write partially succeeds (some items written, some unprocessed)? The system MUST retry unprocessed items with exponential backoff and report the final outcome accurately. If retries are exhausted, the remaining unprocessed items are logged at ERROR level with item count.
- What happens when the external API returns data that differs from previously cached data for the same time period (e.g., exchange correction)? Write-through overwrites are acceptable since the latest data from the authoritative source is always correct.
- What happens during a cache storage outage (planned maintenance, capacity event)? The handler applies explicit degradation: serve from external API with degradation headers. The outage is visible in ERROR logs, response headers, and monitoring dashboards — never silent.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: System MUST propagate persistent cache read errors as exceptions from the cache module. The endpoint handler MUST catch these and apply explicit degradation: fetch from external API, log at ERROR level, return data with `X-Cache-Source: live-api-degraded` and `X-Cache-Error` headers.
- **FR-002**: System MUST propagate persistent cache write errors as exceptions from the cache module. The endpoint handler MUST catch these, log at ERROR level, and include `X-Cache-Write-Error: true` header on the response (the data itself was already fetched successfully and should still be returned).
- **FR-003**: System MUST include a response header on every price data response indicating the data source (in-memory, persistent-cache, or live-api).
- **FR-004**: System MUST include a response header on every price data response indicating the cache age in seconds (0 for live-api).
- **FR-005**: System MUST write a time-to-live attribute on every cached item (90 days for historical/daily data, 5 minutes for current-day intraday data).
- **FR-006**: System MUST correctly parse persistent storage responses using actual attribute names — not rely on expression alias names that never appear in responses.
- **FR-007**: System MUST retry unprocessed batch write items with exponential backoff (max 3 retries).
- **FR-008**: System MUST remove all references to removed architectural patterns from specification documents, code documentation, and cache-related documentation files.
- **FR-009**: System MUST update code documentation (docstrings) to accurately describe the resolution format used at runtime.
- **FR-010**: System MUST remove dead code paths (unused import fallbacks for unsupported runtime versions).
- **FR-011**: The banned-term scanner exclusion for the cache documentation directory MUST be removed after documentation cleanup is complete.
- **FR-012**: The specification clarification history MUST be updated to reflect that the architectural blocker is resolved.

### Error Handling Policy

The following error handling policy distinguishes between **designed fallback** (acceptable) and **silent degradation** (prohibited):

- **Designed fallback (acceptable)**: Cache miss (no data found) → fetch from external API. This is the normal cache-aside pattern and is by design.
- **Silent degradation (PROHIBITED)**: Cache error (table unreachable, permission denied, parse failure) → silently return None and fetch from external API with no indication anything went wrong. This hides infrastructure problems.
- **Explicit degradation (REQUIRED for cache errors)**: Cache error → the cache module raises an exception → the endpoint handler catches it, logs at ERROR level, fetches from external API, and returns data with degradation headers (`X-Cache-Source: live-api-degraded`, `X-Cache-Error`). The failure is visible to operators, consumers, and monitoring. This is a **designed fallback**: the degradation path is intentional, documented, observable, and distinguishable from normal cache-miss behavior.
- **Policy**: Cache errors MUST propagate as exceptions from the cache module. The cache module itself MUST NOT catch and suppress errors. The endpoint handler applies the explicit degradation pattern described above.

### Key Entities

- **Cached Candle**: A single OHLC price data point stored in persistent cache. Attributes: ticker, source, resolution, timestamp, open/high/low/close prices, volume, fetch timestamp, expiration timestamp.
- **Cache Result**: The outcome of a cache query. Attributes: list of cached candles, cache-hit boolean, cache age in seconds.
- **Cache Source**: Enumeration of where price data was served from: in-memory, persistent-cache, or live-api.

## Assumptions

1. The persistent cache storage (DynamoDB) supports automatic item expiration via TTL attribute — the feature will set the attribute; the storage engine handles deletion.
2. The current handler architecture (Lambda Powertools) supports setting custom response headers on the Response object directly — no middleware or dependency injection pattern is needed.
3. Exponential backoff for batch write retries is bounded at 3 retries with base interval of 100ms (100ms → 200ms → 400ms) to stay within Lambda execution time budgets.
4. The thundering herd prevention feature (distributed locking) from the original CACHE-001 spec section 4.7 is **deferred** to a future feature — it adds significant complexity and the current traffic levels do not warrant it.
5. Historical daily price data is immutable once the trading day is complete. Intraday data for the current trading day is mutable until market close.

## Scope Boundaries

**In scope:**
- Fix error handling in cache read/write paths (fail fast, not silent degradation)
- Add cache observability response headers
- Add TTL attributes to cached items
- Fix latent parsing bug in persistent storage response handling
- Add retry logic for unprocessed batch write items
- Purge removed-framework references from all spec and doc files
- Fix inaccurate code documentation
- Remove dead code paths
- Remove banned-term scanner exclusion for docs/cache/

**Out of scope:**
- Thundering herd prevention (deferred — original spec section 4.7)
- Cache warming strategy for popular tickers (deferred — no current traffic justification)
- Real-time WebSocket OHLC updates (separate future feature)
- Changes to cache key design (already correctly implemented)
- Changes to the two-tier cache architecture (already correctly implemented)
- Changes to the write-through pattern (already correctly implemented, needs error handling fix only)

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: When persistent cache storage is unreachable, 100% of affected requests produce an ERROR-level log entry within the same request lifecycle (currently: 0% — errors logged at WARNING level only).
- **SC-002**: 100% of price data responses include a data-source header and cache-age header (currently: 0%).
- **SC-003**: All cached items have a time-to-live attribute set at write time (currently: 0% of items have TTL).
- **SC-004**: The banned-term scanner passes on the cache documentation directory without exclusions (currently: directory is excluded from scanning).
- **SC-005**: The persistent storage response parsing primary code path succeeds without triggering exception-handler fallback (currently: primary path always fails, secondary path handles it).
- **SC-006**: Unprocessed batch write items are retried and the retry outcome is logged (currently: unprocessed items are silently discarded).
- **SC-007**: Code documentation for the cache module accurately describes the resolution format used at runtime (currently: docstring says "5m", runtime uses "5").
