# Feature Specification: Cache Architecture Audit and Remediation

**Feature Branch**: `001-cache-architecture-audit`
**Created**: 2026-03-17
**Status**: Draft
**Input**: Feature 1224 — Cache Architecture Audit and Remediation

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Reliable Authentication During Key Rotation (Priority: P1)

A user is actively using the Sentiment Analyzer dashboard when the identity provider rotates its signing keys. The user's session continues without interruption — the system detects the new keys and validates tokens seamlessly. Users are never forced to re-authenticate due to stale key material in the application's cache.

**Why this priority**: Authentication failures are the highest-severity user-facing issue. A stale key cache causes a complete auth outage for all users on affected application instances, with no self-service recovery. This is a security-adjacent correctness bug that must be fixed first.

**Independent Test**: Can be tested by simulating a key rotation event and verifying that token validation succeeds within one refresh cycle, without requiring an application restart.

**Acceptance Scenarios**:

1. **Given** a user is authenticated and the identity provider rotates signing keys, **When** the user makes a subsequent request, **Then** the system refreshes its key cache and validates the token successfully without user intervention.
2. **Given** the key cache has expired, **When** a token verification fails due to an unknown key ID, **Then** the system fetches fresh keys and retries verification before returning an authentication error.
3. **Given** the key provider is temporarily unreachable, **When** the system attempts to refresh keys, **Then** it continues using the last known valid keys for up to 15 minutes, then fails closed (denies authentication) if the provider remains unreachable.

---

### User Story 2 - Accurate API Quota Tracking Under Concurrent Load (Priority: P1)

The operations team scales the application to handle increased load (more concurrent instances processing more tickers). The system accurately tracks API usage across all instances and stays within provider rate limits. The team is never surprised by quota overages or unexpected API bills.

**Why this priority**: Quota overages at 8K tickers would cause cascading failures (API providers throttle or ban the account), impacting all users simultaneously. This is the primary blocker for the planned ticker expansion.

**Independent Test**: Can be tested by running multiple concurrent application instances, each consuming API quota, and verifying that the aggregate usage reported matches actual API calls within an acceptable margin.

**Acceptance Scenarios**:

1. **Given** multiple application instances are running concurrently, **When** each instance makes API calls, **Then** the total tracked usage across all instances is within 10% of actual API calls made.
2. **Given** the aggregate API usage approaches the provider's rate limit (80% threshold), **When** any instance checks its remaining quota, **Then** it receives an accurate-enough count to avoid exceeding the limit.
3. **Given** the shared quota store is temporarily unreachable, **When** an instance cannot sync its usage, **Then** it reduces its API call rate to 25% of normal, raises an alert to the operations team, and continues at the reduced rate until connectivity is restored.

---

### User Story 3 - Fresh Ticker Data After List Updates (Priority: P2)

The data team updates the ticker symbol list (adding new tickers or removing delisted ones). Within a short, predictable window, all running application instances serve the updated list to users. Users searching for newly added tickers find them without waiting for application restarts.

**Why this priority**: At 22 tickers, staleness is invisible. At 8K tickers with weekly updates, users will notice missing or phantom tickers. This blocks the planned expansion but is lower severity than auth or quota issues because the impact is cosmetic (stale list) rather than systemic (outage or overage).

**Independent Test**: Can be tested by updating the ticker list in the data source and verifying that all application instances serve the new list within the defined refresh window.

**Acceptance Scenarios**:

1. **Given** a new ticker is added to the authoritative list, **When** a user searches for it after the refresh window, **Then** the ticker appears in results.
2. **Given** a ticker is removed from the authoritative list, **When** a user searches for it after the refresh window, **Then** the ticker no longer appears.
3. **Given** the data source is temporarily unreachable during a refresh attempt, **When** the system cannot load the updated list, **Then** it continues serving the last known valid list and retries on the next refresh cycle.

---

### User Story 4 - Consistent Cache Behavior Under Upstream Failures (Priority: P2)

When an upstream dependency (data store, API provider, secrets manager) experiences a transient failure, each cache in the system responds according to a predictable, documented policy. Operations staff can reason about system behavior during outages without reading source code.

**Why this priority**: Inconsistent failure modes make incidents harder to diagnose and resolve. Standardizing failure behavior reduces mean time to recovery and prevents surprising cascading failures.

**Independent Test**: Can be tested by injecting failures into each upstream dependency and verifying that the corresponding cache behaves according to its documented failure policy.

**Acceptance Scenarios**:

1. **Given** an upstream data store is unreachable, **When** a cache serving user-facing data attempts to refresh, **Then** it serves the last known valid data (stale-while-revalidate) and logs a warning.
2. **Given** an upstream dependency for security-critical data (secrets, keys) is unreachable, **When** a cache attempts to refresh, **Then** it continues using cached data for a bounded grace period, then fails closed (denies access) if the outage persists.
3. **Given** all caches have documented failure policies, **When** an operator reviews the cache runbook, **Then** they can determine the expected behavior of every cache during any single upstream failure.

---

### User Story 5 - Cache Performance Visibility for Operations (Priority: P3)

The operations team can monitor cache health in real time via their existing monitoring dashboard. They can see hit rates, miss rates, and eviction counts for each cache, enabling proactive capacity planning and rapid incident detection (e.g., a sudden drop in hit rate signals a misconfiguration or upstream issue).

**Why this priority**: Observability is a force multiplier for all other improvements. However, it doesn't fix any bugs on its own — it enables faster detection and diagnosis of problems. Lower priority than correctness fixes.

**Independent Test**: Can be tested by generating cache traffic and verifying that corresponding metrics appear in the monitoring system within the expected reporting interval.

**Acceptance Scenarios**:

1. **Given** the application is running and serving traffic, **When** the operations team opens the monitoring dashboard, **Then** they can see hit rate, miss rate, and eviction count for each named cache.
2. **Given** a cache's hit rate drops below 50%, **When** the monitoring system detects this, **Then** an alert is raised to the operations team.
3. **Given** a cache experiences a burst of evictions, **When** this appears in the monitoring dashboard, **Then** the metric is attributable to a specific named cache (not aggregated across all caches).

---

### User Story 6 - No Thundering Herd on Cache Expiry (Priority: P3)

When multiple application instances are running and their caches expire at similar times, the upstream dependencies do not experience a sudden spike of concurrent requests. Cache expiry times are spread out to smooth the load, preventing self-inflicted rate limiting or upstream overload.

**Why this priority**: At current scale (22 tickers, low concurrency), thundering herds are invisible. At 8K tickers with higher concurrency, synchronized cache expiry could exceed API rate limits even when average usage is within budget. Important for scaling but not currently causing failures.

**Independent Test**: Can be tested by observing the timing of cache refresh requests across multiple instances and verifying that they are distributed over a window rather than clustered at a single point.

**Acceptance Scenarios**:

1. **Given** 10 application instances with the same cache TTL, **When** the TTL expires across all instances, **Then** the refresh requests are spread over a time window (not all hitting the upstream at the same instant).
2. **Given** a cache with a 60-second TTL, **When** the effective expiry times are measured across instances, **Then** the standard deviation of expiry times is at least 5% of the TTL.

---

### Edge Cases

- What happens when the ticker list data source returns an empty list? System MUST reject it as invalid and keep the previous list, to prevent serving an empty dashboard.
- What happens when a cache's upstream returns corrupted or malformed data? System MUST reject the update and continue serving the last known valid data.
- What happens during a rolling deployment when some instances have the new cache code and others have the old code? Cache behavior MUST be backward-compatible — old instances continue functioning with their existing TTL/eviction behavior.
- What happens when the system clock drifts on an instance? TTL calculations should be resilient to small clock skew (< 5 seconds).
- What happens when the shared data store throttles quota tracker writes during a traffic spike? System MUST shed load conservatively (reduce API call rate) rather than allow potential overage.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: System MUST refresh its identity provider key cache periodically (at most every 5 minutes) and on verification failure, rather than caching keys indefinitely.
- **FR-002**: System MUST bound the identity key cache to a fixed maximum size and evict entries that are no longer referenced by the provider's published key set.
- **FR-003**: System MUST track API quota usage with cross-instance accuracy within 10% of actual calls when operating at expected concurrency (up to 20 concurrent instances).
- **FR-004**: System MUST refresh the ticker symbol list from the authoritative source at a configurable interval (default: every 5 minutes) rather than only on cold start, using change detection (ETag or last-modified) to skip re-download when the list is unchanged.
- **FR-005**: System MUST validate that a refreshed ticker list is non-empty before replacing the current cached list (reject empty lists as invalid).
- **FR-006**: System MUST add randomized jitter (plus or minus 10% of TTL) to all cache expiry times to prevent synchronized expiry across instances.
- **FR-007**: System MUST emit cache performance metrics (hits, misses, evictions) to the monitoring system for each named cache.
- **FR-008**: System MUST bound all in-memory caches to a configured maximum size with least-recently-used eviction.
- **FR-009**: System MUST document a failure policy for each cache specifying whether it fails open (serves stale data or allows traffic) or fails closed (denies access or raises error) when its upstream is unreachable.
- **FR-010**: System MUST implement the documented failure policy consistently — security-critical caches (secrets, keys) fail closed after a 15-minute grace period; data caches (metrics, prices, sentiment) fail open with stale data.
- **FR-011**: System MUST raise an alert to the operations team when the shared quota store is unreachable and an instance enters reduced-rate mode (25% of normal).

### Key Entities

- **Cache Entry**: A cached value with associated metadata (creation time, effective TTL with jitter, source identifier, hit/miss counters).
- **Cache Policy**: A per-cache configuration defining TTL, max size, failure mode (open or closed), and jitter range.
- **Quota Ledger**: A shared record of API usage across instances, partitioned by time period and API provider, supporting concurrent updates from multiple instances.
- **Key Set**: The collection of signing keys published by the identity provider, refreshable on a schedule and on verification failure.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Users experience zero authentication disruptions during identity provider key rotation events (verified by end-to-end test simulating rotation).
- **SC-002**: Aggregate API quota tracking accuracy is within 10% of actual usage when running 10+ concurrent instances (verified by load test with metered API calls).
- **SC-003**: Ticker list updates are visible to all running instances within 10 minutes of the source update (verified by updating the list and querying each instance).
- **SC-004**: All in-memory caches are bounded — no cache can grow beyond its configured maximum entry count (verified by unit tests that exceed the limit and assert eviction).
- **SC-005**: Cache performance metrics (hit rate, miss rate, eviction count) are visible in the monitoring system within 60 seconds of the events occurring (verified by generating cache traffic and checking dashboards).
- **SC-006**: Cache expiry times across 10 instances show statistical spread (standard deviation >= 5% of TTL) rather than clustering at a single point (verified by timestamp analysis in load test).
- **SC-007**: Every cache has a documented failure policy, and the system behaves according to that policy when its upstream is unreachable (verified by fault injection tests for each cache).
- **SC-008**: All existing tests continue to pass with no regressions (3428+ tests).
- **SC-009**: Cold start latency does not increase by more than 100ms compared to pre-change baseline (verified by measuring cold start times before and after).
- **SC-010**: Monthly data store costs do not increase by more than $5 compared to pre-change baseline at current scale (verified by cost monitoring).

## Clarifications

### Session 2026-03-17

- Q: How long should the system tolerate stale identity provider keys before denying authentication? → A: 15 minutes — balances availability with security exposure.
- Q: When the shared quota store is unreachable, how aggressively should instances reduce their API call rate? → A: Reduce to 25% of normal rate and raise an alert to operations.
- Q: Should the ticker list refresh use change detection (ETag) to avoid re-downloading an unchanged list? → A: Yes, use ETag/conditional-GET to skip re-download if unchanged.
- Note: This spec addresses only the historical/REST-polling data tier (~99.9% of data, fully cacheable). A future WebSocket integration for real-time streaming data will introduce a separate "live partial-bucket" tier with push-based invalidation and different quota models (connection-count + message-rate). Cache designs in this feature must not preclude that future architecture.

## Assumptions

- The identity provider (Cognito) rotates signing keys on an unpredictable schedule, typically every few weeks to months. The system cannot predict when rotation will occur.
- The maximum expected concurrency is 20 Lambda instances. The quota tracking accuracy target (10%) is calibrated for this level.
- The ticker list update frequency remains weekly. The 5-minute refresh interval provides a reasonable balance between freshness and S3 request costs.
- The existing CloudWatch metrics infrastructure is sufficient for emitting cache metrics — no new monitoring tools are required.
- DynamoDB on-demand pricing is used. Atomic counter operations (for quota tracking) are within the existing cost envelope at current scale.
- The 60-minute OHLC/API cache TTL is a product decision outside this feature's scope. This feature does not change TTL values, only adds jitter to existing TTLs.
- The application has two data tiers: historical data (~99.9%, fetched via REST polling, fully cacheable with TTL) and a future live data tier (real-time streaming via WebSocket, push-based invalidation). This feature addresses only the historical/REST tier. The live data tier will be designed as part of the WebSocket integration feature. Cache abstractions introduced here (metrics emission, failure policies) should be generic enough to support a future live-data cache.
- Current quota tracking is based on REST API request counts. WebSocket connections have fundamentally different quota models (connection limits, message rates). The quota tracker design in this feature does not need to accommodate WebSocket quotas.
