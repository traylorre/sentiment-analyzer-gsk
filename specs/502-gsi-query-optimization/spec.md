# Feature Specification: GSI Query Optimization

**Feature Branch**: `502-gsi-query-optimization`
**Created**: 2025-12-18
**Status**: Draft
**Input**: User description: "Remove all DynamoDB table.scan() fallbacks and replace with GSI queries for O(n) efficiency"

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Efficient Ticker Lookup (Priority: P1)

The ingestion service needs to retrieve active tickers efficiently. Currently, scanning the entire table wastes read capacity and increases latency as data grows.

**Why this priority**: Ingestion is the primary data pipeline. Inefficient ticker lookups directly impact data freshness and costs.

**Independent Test**: Can be fully tested by verifying the ingestion handler retrieves active tickers using the `by_entity_status` GSI query instead of table scan.

**Acceptance Scenarios**:

1. **Given** the users table contains 10,000 records with 50 active tickers, **When** `_get_active_tickers()` is called, **Then** only the 50 active ticker records are retrieved via GSI query without scanning all 10,000 records
2. **Given** no active tickers exist, **When** `_get_active_tickers()` is called, **Then** an empty result is returned efficiently via GSI query

---

### User Story 2 - Efficient Sentiment Item Retrieval (Priority: P1)

The SSE streaming service needs to retrieve sentiment items by sentiment type for real-time updates. Scanning all items is prohibitively expensive at scale.

**Why this priority**: SSE streaming is user-facing and performance-critical. Slow queries degrade user experience.

**Independent Test**: Can be fully tested by verifying polling service retrieves sentiment items using the `by_sentiment` GSI query instead of table scan.

**Acceptance Scenarios**:

1. **Given** 100,000 sentiment items exist with 500 matching a specific sentiment, **When** polling for that sentiment, **Then** only the 500 matching records are retrieved via GSI query
2. **Given** a sentiment type with no matching items, **When** polling for that sentiment, **Then** an empty result is returned efficiently

---

### User Story 3 - Efficient Alert Lookup by Ticker (Priority: P2)

The notification service needs to find alerts for specific tickers. Scanning and filtering wastes resources.

**Why this priority**: Alert evaluation runs on schedules. While not user-facing, inefficiency accumulates costs over time.

**Independent Test**: Can be fully tested by verifying `_find_alerts_by_ticker()` uses the `by_entity_status` GSI query.

**Acceptance Scenarios**:

1. **Given** 5,000 alerts exist with 20 for ticker "AAPL", **When** finding alerts for "AAPL", **Then** only the 20 matching alerts are retrieved via GSI query
2. **Given** no alerts exist for a ticker, **When** finding alerts for that ticker, **Then** an empty result is returned efficiently

---

### User Story 4 - Efficient Digest User Lookup (Priority: P2)

The digest service needs to find users due for digest notifications. Scanning all users is inefficient.

**Why this priority**: Digest processing is batch-oriented but should still be efficient for cost management.

**Independent Test**: Can be fully tested by verifying `get_users_due_for_digest()` uses the `by_entity_status` GSI query.

**Acceptance Scenarios**:

1. **Given** 50,000 users exist with 100 due for digest, **When** retrieving users due for digest, **Then** only the 100 matching users are retrieved via GSI query

---

### User Story 5 - Email Lookup Deprecation (Priority: P3)

The auth module's `get_user_by_email()` function should no longer be used directly. Callers should use `get_user_by_email_gsi()` instead.

**Why this priority**: This is a code hygiene task to prevent future misuse. Existing callers already use the GSI version.

**Independent Test**: Can be fully tested by verifying `get_user_by_email()` raises NotImplementedError with guidance message.

**Acceptance Scenarios**:

1. **Given** any code calls `get_user_by_email()`, **When** the function executes, **Then** it raises NotImplementedError directing callers to use `get_user_by_email_gsi()`

---

### Edge Cases

- What happens when a GSI query returns more results than expected (pagination)?
  - System should handle pagination automatically using LastEvaluatedKey
- What happens when the GSI doesn't exist in the deployed table?
  - Error should be logged with clear message identifying the missing GSI
- How does system handle partial GSI propagation (eventual consistency)?
  - Queries use eventual consistency by default; no special handling needed unless strong consistency is required
- Exception: chaos.py admin tool retains table.scan() with Limit=100 for debugging purposes

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: Ingestion handler MUST use `by_entity_status` GSI query in `_get_active_tickers()` to retrieve active tickers
- **FR-002**: SSE polling service MUST use `by_sentiment` GSI query in `_query_by_sentiment()` to replace `_scan_table()`
- **FR-003**: Notification alert evaluator MUST use `by_entity_status` GSI query in `_find_alerts_by_ticker()`
- **FR-004**: Digest service MUST use `by_entity_status` GSI query in `get_users_due_for_digest()`
- **FR-005**: Auth module MUST raise NotImplementedError in `get_user_by_email()` directing callers to `get_user_by_email_gsi()`
- **FR-006**: Chaos.py admin tool MAY retain table.scan() with Limit=100 for debugging (exception to scan prohibition)
- **FR-007**: All unit tests MUST mock `table.query()` instead of `table.scan()` for affected functions
- **FR-008**: Test fixtures MUST include GSI definitions in moto DynamoDB table creation
- **FR-009**: Query mocks MUST use function-based `side_effect` for repeatable query behavior

### Key Entities

- **Users Table**: Contains user records with `by_entity_status` GSI (hash=entity_type, range=status) and `by_email` GSI (hash=email)
- **Sentiment Items Table**: Contains sentiment analysis results with `by_sentiment` GSI (hash=sentiment, range=timestamp)
- **GSI Query Parameters**: IndexName, KeyConditionExpression, and optional FilterExpression for targeted retrieval

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: All five target files use GSI queries instead of table scans (100% migration)
- **SC-002**: Read capacity consumption for affected operations decreases proportionally to data selectivity (e.g., retrieving 50 of 10,000 items should use ~200x less read capacity than a full scan)
- **SC-003**: All unit tests pass with updated mocks using `table.query()` and GSI definitions
- **SC-004**: No table.scan() calls remain in production code except for the documented chaos.py exception
- **SC-005**: Query response time scales with result size, not table size (O(result) not O(table))

## Assumptions

- GSIs (`by_entity_status`, `by_sentiment`, `by_email`) already exist in the Terraform configuration and are deployed
- Branch `2-remove-scan-fallbacks` contains a working reference implementation (though behind main)
- Moto library supports GSI creation and querying for unit tests
- Eventual consistency is acceptable for all GSI queries (no strong consistency requirement)
