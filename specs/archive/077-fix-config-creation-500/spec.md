# Feature Specification: Fix Config Creation 500 Error

**Feature Branch**: `077-fix-config-creation-500`
**Created**: 2025-12-10
**Status**: Draft
**Input**: User description: "Fix Config Creation 500 Error to Unblock E2E Tests"

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Create Configuration Successfully (Priority: P1)

An authenticated user wants to create a new configuration to track sentiment for specific stock tickers. Currently, when they submit a valid configuration request, the system returns a 500 error instead of creating the configuration.

**Why this priority**: This is the core bug that blocks all downstream functionality. Without config creation, users cannot use the dashboard's primary feature of tracking custom ticker portfolios.

**Independent Test**: Can be fully tested by sending a POST request to `/api/v2/configurations` with a valid payload and verifying a 201 response with the created configuration.

**Acceptance Scenarios**:

1. **Given** an authenticated user with a valid session, **When** they submit a configuration with valid tickers (e.g., AAPL, MSFT), **Then** the system returns HTTP 201 with the created configuration including a unique ID
2. **Given** an authenticated user, **When** they submit a configuration request, **Then** the configuration is persisted and retrievable via GET
3. **Given** an authenticated user, **When** they submit an invalid configuration (e.g., empty tickers), **Then** the system returns HTTP 400 with a descriptive error message (not 500)

---

### User Story 2 - E2E Tests Pass Without Skipping (Priority: P2)

The development team needs E2E tests to execute fully without skipping due to config creation failures. Currently, approximately 8 E2E tests skip with "Config creation endpoint returning 500 - API issue".

**Why this priority**: Test coverage is essential for maintaining code quality. Skipping tests masks potential issues and reduces confidence in deployments.

**Independent Test**: Run the affected E2E test files and verify they complete without skipping due to config creation issues.

**Acceptance Scenarios**:

1. **Given** the config creation endpoint is fixed, **When** running `test_auth_anonymous.py`, **Then** tests that depend on config creation execute fully
2. **Given** the config creation endpoint is fixed, **When** running `test_failure_injection.py`, **Then** config-dependent tests pass or fail on their own merits (not skip)
3. **Given** the config creation endpoint is fixed, **When** running `test_notifications.py` and `test_dashboard_buffered.py`, **Then** all config-dependent tests execute

---

### User Story 3 - Error Handling Returns Appropriate Status Codes (Priority: P3)

When errors occur during configuration creation, the system should return appropriate HTTP status codes (400 for client errors, 500 only for genuine server errors) with helpful error messages.

**Why this priority**: Proper error handling improves debuggability and user experience, but is secondary to basic functionality.

**Independent Test**: Send malformed requests and verify appropriate 4xx responses instead of 500 errors.

**Acceptance Scenarios**:

1. **Given** a malformed JSON payload, **When** submitting to config creation, **Then** return HTTP 400 (Bad Request)
2. **Given** missing required fields, **When** submitting to config creation, **Then** return HTTP 422 (Unprocessable Entity) with field-specific errors
3. **Given** an invalid ticker symbol, **When** submitting to config creation, **Then** return HTTP 400 with a message indicating the invalid ticker

---

### Edge Cases

- What happens when the user has reached maximum allowed configurations? (Should return 400/403, not 500)
- How does the system handle duplicate configuration names? (Should return appropriate client error)
- What happens when database connectivity is temporarily unavailable? (May legitimately return 500 with retry guidance)
- How does the system handle extremely long configuration names or ticker lists? (Should validate and return 400)

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: System MUST accept valid configuration creation requests and return HTTP 201 with the created resource
- **FR-002**: System MUST validate all input fields before attempting to persist the configuration
- **FR-003**: System MUST return HTTP 4xx status codes for client-side errors (validation failures, invalid input)
- **FR-004**: System MUST preserve existing unit tests for configuration creation functionality
- **FR-005**: System MUST log errors with sufficient detail to diagnose issues without exposing sensitive data
- **FR-006**: System MUST NOT log user-generated content (ticker symbols, configuration names, request payloads) to prevent log injection vulnerabilities (CWE-117)

### Key Entities

- **Configuration**: Represents a user's custom portfolio of tickers to track. Key attributes: unique ID, user association, ticker list, name, creation timestamp, active status
- **User Session**: The authenticated user context required to create configurations

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Configuration creation endpoint returns HTTP 201 for valid requests (currently returns 500)
- **SC-002**: All 8 config-dependent E2E tests execute without skipping due to config creation issues
- **SC-003**: No regression in existing unit tests (all current tests continue to pass)
- **SC-004**: Root cause of 500 error is identified and documented in the commit message
- **SC-005**: No new CodeQL log injection warnings (CWE-117) introduced by this fix

## Assumptions

- The configuration creation endpoint exists and is routed correctly (the issue is in execution, not routing)
- Unit tests for configuration creation pass (indicating the bug may be environment or integration-related)
- The fix should not require schema changes to the database
- Valid configuration payloads follow the existing API contract
