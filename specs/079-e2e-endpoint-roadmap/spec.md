# Feature Specification: E2E Endpoint Implementation Roadmap

**Feature Branch**: `079-e2e-endpoint-roadmap`
**Created**: 2025-12-10
**Status**: Planned
**Input**: Implementation roadmap for ~60 missing API endpoints causing E2E test skips

## Overview

This specification documents a phased roadmap for implementing missing API endpoints that are currently causing ~60 E2E tests to skip. Each phase represents a cohesive set of functionality that can be delivered independently.

**Note**: This is a **planning document** that defines the scope and priority of endpoint implementations. Each phase should be implemented as a separate feature (080, 081, etc.) with its own spec, plan, and tasks.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Alerts Management (Priority: P1)

Users need to create and manage sentiment/volatility alerts for their tracked tickers. Without alerts, users must manually check the dashboard for threshold breaches.

**Why this priority**: Alerts are a core differentiator for the sentiment analyzer. Users who track multiple tickers cannot manually monitor all of them. This unlocks ~9 E2E tests.

**Independent Test**: Can be fully tested by creating, modifying, and deleting alerts on a configuration, verifying notification triggers.

**Acceptance Scenarios**:

1. **Given** a user with a configuration, **When** they create a sentiment alert with threshold 0.7, **Then** the alert is saved and returned with an alert_id
2. **Given** an existing alert, **When** the user updates the threshold, **Then** the change persists and is reflected in subsequent reads
3. **Given** an existing alert, **When** the user deletes it, **Then** it is no longer retrievable (404)
4. **Given** a user, **When** they request their alerts list, **Then** all their alerts are returned with pagination support

---

### User Story 2 - Market Status Information (Priority: P1)

Users need to know whether markets are open, closed, or in pre/post-market hours to contextualize sentiment data. Real-time trading decisions depend on market state.

**Why this priority**: Market context is essential for interpreting sentiment. Users need to know if low activity is due to closed markets. This unlocks ~6 E2E tests.

**Independent Test**: Can be fully tested by querying market status at different times and verifying correct status (open/closed/pre-market).

**Acceptance Scenarios**:

1. **Given** market hours, **When** user queries market status, **Then** system returns "open" with current session info
2. **Given** after-hours, **When** user queries market status, **Then** system returns "closed" with next open time
3. **Given** pre-market window, **When** user queries pre-market status, **Then** system returns pre-market activity indicators

---

### User Story 3 - Ticker Search and Validation (Priority: P1)

Users need to search for and validate ticker symbols before adding them to configurations. Invalid tickers waste resources and confuse users.

**Why this priority**: Foundation for configuration management. Without validation, users can add invalid tickers that fail silently. This unlocks ~7 E2E tests.

**Independent Test**: Can be fully tested by searching for tickers and validating symbols against known good/bad inputs.

**Acceptance Scenarios**:

1. **Given** a partial ticker name, **When** user searches, **Then** matching tickers are returned with company names
2. **Given** a valid ticker symbol, **When** user validates it, **Then** system confirms validity with metadata
3. **Given** an invalid ticker symbol, **When** user validates it, **Then** system returns validation error with reason

---

### User Story 4 - Notification Management (Priority: P2)

Users need to view and manage their notifications (alert triggers, system messages). Without this, users miss important events.

**Why this priority**: Enables users to see historical alert triggers and system messages. Builds on alerts (P1). This unlocks ~7 E2E tests.

**Independent Test**: Can be fully tested by triggering alerts, viewing notification list, and marking as read.

**Acceptance Scenarios**:

1. **Given** a user with notifications, **When** they request notification list, **Then** all notifications are returned with timestamps
2. **Given** unread notifications, **When** user marks them as read, **Then** notification state updates
3. **Given** a notification, **When** user deletes it, **Then** it is removed from their list

---

### User Story 5 - Notification Preferences (Priority: P2)

Users need to control how and when they receive notifications (email, push, digest frequency). Without preferences, all users get default behavior.

**Why this priority**: User experience customization. Some users want immediate alerts, others prefer daily digests. This unlocks ~13 E2E tests.

**Independent Test**: Can be fully tested by setting preferences and verifying notification delivery respects settings.

**Acceptance Scenarios**:

1. **Given** a user, **When** they view preferences, **Then** current settings are displayed
2. **Given** a user, **When** they update notification frequency, **Then** future notifications respect the new setting
3. **Given** a user, **When** they disable all notifications, **Then** no notifications are sent until re-enabled

---

### User Story 6 - Quota Management (Priority: P2)

Users need to see their usage quotas (alerts per config, notifications per period). Without visibility, users hit limits unexpectedly.

**Why this priority**: Transparency and user experience. Users should understand their limits before hitting them. This unlocks ~6 E2E tests.

**Independent Test**: Can be fully tested by checking quota, using resources, and verifying quota decrements.

**Acceptance Scenarios**:

1. **Given** a user, **When** they query alert quota, **Then** current usage and limits are returned
2. **Given** a user at quota limit, **When** they try to create another alert, **Then** helpful error message explains the limit

---

### User Story 7 - Magic Link Authentication (Priority: P3)

Users need passwordless authentication via email magic links for improved security and UX. Currently only anonymous sessions are supported.

**Why this priority**: Security and UX improvement, but anonymous auth works for MVP. This unlocks ~13 E2E tests.

**Independent Test**: Can be fully tested by requesting magic link, clicking it, and verifying authenticated session.

**Acceptance Scenarios**:

1. **Given** a user email, **When** they request magic link, **Then** email is sent with valid token
2. **Given** a valid magic link token, **When** user clicks it, **Then** authenticated session is created
3. **Given** an expired magic link, **When** user clicks it, **Then** appropriate error is shown
4. **Given** anonymous session with data, **When** user authenticates via magic link, **Then** anonymous data is auto-merged to authenticated account

---

### User Story 8 - Rate Limiting Feedback (Priority: P3)

Users need clear feedback when rate limited, including retry timing. Currently rate limiting may occur but feedback is inconsistent.

**Why this priority**: UX improvement for high-volume users. Basic functionality works without this. This unlocks ~4 E2E tests.

**Independent Test**: Can be fully tested by making rapid requests and verifying rate limit response includes retry-after.

**Acceptance Scenarios**:

1. **Given** rate limit hit, **When** user makes request, **Then** 429 response includes Retry-After header
2. **Given** rate limit active, **When** retry period passes, **Then** requests succeed again

---

### User Story 9 - Dashboard Enhancements (Priority: P3)

Users need heatmap and metrics views for better data visualization. Basic sentiment data is available but advanced visualizations are not.

**Why this priority**: Nice-to-have visualization. Core functionality exists. This unlocks ~2 E2E tests.

**Independent Test**: Can be fully tested by requesting heatmap/metrics endpoints and verifying data structure.

**Acceptance Scenarios**:

1. **Given** a configuration, **When** user requests heatmap, **Then** sentiment data is returned in heatmap-compatible format
2. **Given** a configuration, **When** user requests metrics, **Then** aggregated metrics are returned

---

### Edge Cases

- What happens when user tries to create more alerts than their quota allows? → Return 429 with quota exceeded message
- How does system handle ticker validation for delisted stocks? → Return `is_delisted: true` with optional successor symbol
- What happens when magic link expires mid-session? → Return 401 with "token expired" message
- How does system handle rate limiting across multiple concurrent sessions? → Per-user limit shared across sessions
- What happens when market status source is unavailable? → Return cached status with stale indicator
- **External API unavailable** → Return cached ticker data with staleness indicator (resolved Q5)

## Requirements *(mandatory)*

### Functional Requirements

**Phase 1 - Core User Features**
- **FR-001**: System MUST allow users to create sentiment threshold alerts for their configurations
- **FR-002**: System MUST allow users to create volatility (ATR-based) alerts
- **FR-003**: System MUST support alert CRUD operations (create, read, update, delete)
- **FR-004**: System MUST provide current market status (open/closed/pre-market)
- **FR-005**: System MUST provide market schedule information
- **FR-006**: System MUST support ticker symbol search with partial matching
- **FR-007**: System MUST validate ticker symbols before accepting them

**Phase 2 - Notifications System**
- **FR-008**: System MUST store and retrieve user notifications
- **FR-009**: System MUST support marking notifications as read
- **FR-010**: System MUST allow notification preferences management
- **FR-011**: System MUST support disable-all notifications option
- **FR-012**: System MUST track and display alert/notification quotas

**Phase 3 - Authentication Extensions**
- **FR-013**: System MUST support magic link authentication flow
- **FR-014**: System MUST validate and expire magic link tokens appropriately
- **FR-015**: System MUST provide rate limit feedback with retry timing (default: 30 requests/minute per user)

**Phase 4 - Dashboard Enhancements**
- **FR-016**: System MUST provide heatmap data view for configurations
- **FR-017**: System MUST provide aggregated metrics view

### Key Entities

- **Alert**: Threshold-based notification rule (type: sentiment/volatility, threshold, condition, enabled status)
- **Notification**: User-facing message from alert trigger or system event (timestamp, read status, type, content; TTL: 30 days auto-delete)
- **NotificationPreference**: User settings for notification delivery (channel, frequency, enabled)
- **Quota**: Usage limits per user/configuration (alert count: default 10 per user, notification rate)
- **MagicLinkToken**: Temporary authentication token (email, token, expiry, used status)
- **MarketStatus**: Current market state (status, session times, next transition)

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Phase 1 implementation reduces E2E skip count by at least 20 tests (~9 alerts + ~6 market + ~7 ticker)
- **SC-002**: Phase 2 implementation reduces E2E skip count by at least 25 tests (~7 notifications + ~13 preferences + ~6 quota)
- **SC-003**: Phase 3 implementation reduces E2E skip count by at least 15 tests (~13 magic link + ~4 rate limiting)
- **SC-004**: Phase 4 implementation reduces E2E skip count by at least 2 tests
- **SC-005**: All implemented endpoints return proper HTTP status codes (not 404/500)
- **SC-006**: Each phase maintains existing test pass rate (no regressions)
- **SC-007**: E2E tests for implemented endpoints execute without pytest.skip()

## Implementation Phases

| Phase | Endpoints                                | E2E Tests | Priority |
|-------|------------------------------------------|-----------|----------|
| 1     | Alerts, Market Status, Ticker Validation | ~22       | High     |
| 2     | Notifications, Preferences, Quota        | ~26       | Medium   |
| 3     | Magic Link, Rate Limiting                | ~17       | Lower    |
| 4     | Heatmap, Metrics                         | ~2        | Low      |

**Total**: ~67 E2E tests currently skipping due to missing endpoints

## Caching Strategy

All endpoint implementations SHOULD consider caching to reduce latency and DynamoDB costs.

### Caching Recommendations by Feature

| Feature | Cache Layer | TTL | Invalidation |
|---------|-------------|-----|--------------|
| Market Status | In-memory (Lambda) | 60s | Time-based only |
| Market Schedule | In-memory (Lambda) | 24h | Time-based only |
| Market Holidays | In-memory (Lambda) | 24h | Time-based only |
| Ticker Validation | DynamoDB + in-memory | 24h | On delisting event |
| Ticker Search | DynamoDB + in-memory | 24h | On new ticker |
| User Alerts | None (mutable) | - | - |
| Notifications | None (mutable) | - | - |
| Preferences | In-memory (per-request) | 5min | On update |
| Quota | In-memory (per-request) | 1min | On usage change |
| Rate Limits | In-memory (Lambda) | Request duration | Per-request |

### Implementation Guidelines

1. **Read-Heavy, Rarely-Changing Data** (market status, tickers):
   - Use Lambda instance-level caching (module-level dict)
   - DynamoDB TTL for persistent cache layer
   - Example: `@lru_cache(maxsize=1000, ttl=3600)`

2. **User-Specific, Frequently-Read** (preferences, quota):
   - Cache within request context only
   - No cross-request caching (staleness risk)
   - Use `functools.cache` with request-scoped lifetime

3. **Mutable User Data** (alerts, notifications):
   - No caching - always read from DynamoDB
   - Write-through for consistency

4. **External API Responses** (Tiingo ticker data):
   - DynamoDB cache with 24h TTL
   - Fallback to external API on cache miss
   - TTL attribute for automatic cleanup

### Cache Invalidation Patterns

```python
# Pattern 1: Time-based (market status)
MARKET_STATUS_CACHE = {}
CACHE_TTL = 60  # seconds

def get_market_status():
    now = time.time()
    if "status" in MARKET_STATUS_CACHE:
        cached, timestamp = MARKET_STATUS_CACHE["status"]
        if now - timestamp < CACHE_TTL:
            return cached
    status = compute_market_status()
    MARKET_STATUS_CACHE["status"] = (status, now)
    return status

# Pattern 2: Write-through invalidation (preferences)
def update_preferences(user_id: str, prefs: dict):
    # Update DynamoDB
    table.put_item(Item={...})
    # Invalidate cache
    PREFS_CACHE.pop(user_id, None)
```

### Non-Functional Requirements (Caching)

- **NFR-C01**: Market status endpoint P90 latency ≤ 50ms (cached)
- **NFR-C02**: Ticker validation P90 latency ≤ 100ms (cached)
- **NFR-C03**: Cache hit rate for market endpoints ≥ 90%
- **NFR-C04**: No stale data > TTL for any cached endpoint

## Out of Scope

- Token refresh (OAuth feature, separate auth system)
- Circuit breaker state queries (internal observability, not user-facing)
- v1 API endpoints (deprecated per Feature 076)

## Development Methodology: TDD with Blackbox Scaffolding

### Approach

Each phase MUST follow Test-Driven Development (TDD) using existing E2E tests as the blackbox specification:

1. **Tests as Specifications**: Existing E2E tests (currently skipping) define the expected blackbox behavior
2. **Entity Scaffolding from Tests**: Derive entity structures from test assertions and API payloads
3. **Red-Green-Refactor**:
   - RED: Remove pytest.skip() - tests fail with 404/500
   - GREEN: Implement minimum code to pass tests
   - REFACTOR: Clean up implementation while tests remain green

### Entity Discovery Process

For each endpoint category:

1. **Extract Request/Response Contracts** from E2E test files:
   - Input payloads (what tests POST/PUT)
   - Expected response fields (what tests assert)
   - HTTP status codes (what tests expect)

2. **Scaffold Entity Models** based on contracts:
   - Create pydantic models matching test expectations
   - Define DynamoDB access patterns from test scenarios
   - Build router stubs returning expected structures

3. **Implement Progressively**:
   - Start with hardcoded responses matching test expectations
   - Replace with real logic incrementally
   - Each step must keep existing tests green

### Example: Alert Entity Scaffolding

From `test_alerts.py` acceptance scenarios, derive:

```
Alert Entity (from test assertions):
├── alert_id (returned in create response)
├── type: "sentiment" | "volatility" (from test payloads)
├── ticker (from test payloads)
├── threshold: float (from test payloads, updateable)
├── condition: "above" | "below" (from test payloads)
└── enabled: bool (toggled in tests)

API Contract (from test HTTP calls):
├── POST /api/v2/configurations/{id}/alerts → 201 + {alert_id, ...}
├── GET /api/v2/configurations/{id}/alerts → 200 + [{alert}, ...]
├── PATCH /api/v2/alerts/{id} → 200 + {alert}
├── DELETE /api/v2/alerts/{id} → 200|204
└── GET /api/v2/alerts/{id} → 200 + {alert} | 404
```

### Benefits

- **No Speculative Design**: Entities match what tests actually need
- **Continuous Validation**: Tests validate implementation at every step
- **Minimal Implementation**: Only build what tests require
- **Documentation as Code**: E2E tests document the API contract

## Clarifications

### Session 2025-12-10

- Q: What should be the default alert quota per user? → A: 10 alerts per user
- Q: What should be the default API rate limit per user per minute? → A: 30 requests/minute
- Q: How long should notifications be retained before automatic deletion? → A: 30 days
- Q: When user authenticates via magic link after anonymous session, migrate data? → A: Auto-merge
- Q: When Tiingo/Finnhub APIs are unavailable for ticker validation, what should happen? → A: Return cached data with staleness indicator

## Assumptions

- Each phase will be implemented as a separate feature branch (080, 081, etc.)
- DynamoDB schema may need updates for new entities (alerts, notifications, preferences)
- Existing authentication middleware supports the new endpoints
- Market data sources (Tiingo, Finnhub) provide market status information
- Magic link implementation will use SES for email delivery
- **TDD Constraint**: Implementation MUST pass existing E2E tests before adding new functionality
