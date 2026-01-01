# Feature Specification: CORS API Gateway Fix

**Feature Branch**: `1114-cors-api-gateway-fix`
**Created**: 2026-01-01
**Status**: Complete
**Input**: User description: "Fix CORS architecture mismatch blocking dashboard. Frontend uses API Gateway but Lambda omits CORS headers assuming Lambda Function URL handles it."

## Clarifications

### Session 2026-01-01

- Q: Which solution approach should be implemented to fix the CORS issue? → A: API Gateway integration responses - Add CORS headers in Terraform at gateway level (no Lambda changes). This maintains architectural separation where Lambda stays CORS-agnostic.

## Problem Statement

The dashboard is completely blocked by CORS errors. Users cannot:
- Load the dashboard (runtime config fails)
- Search for tickers (search API fails)
- Perform any API operations from the browser

**Root Cause**: The system has two paths to the Lambda function:
1. **Lambda Function URL** - Has CORS configured at infrastructure level
2. **API Gateway** - Frontend actually uses this path, but Lambda responses lack CORS headers

The Lambda code was designed assuming Lambda Function URL handles CORS, but the frontend environment variable `NEXT_PUBLIC_API_URL` points to API Gateway. API Gateway's OPTIONS mock returns CORS headers (preflight succeeds), but the actual GET/POST responses from Lambda have no CORS headers (browser blocks).

**Evidence**:
- `curl` requests succeed (200 OK with valid data)
- Browser requests fail with `net::ERR_FAILED(200)` - CORS blocked
- OPTIONS preflight returns `Access-Control-Allow-Origin: *`
- GET/POST responses have no CORS headers

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Dashboard Load (Priority: P1)

A user opens the dashboard URL and the application initializes successfully, fetching runtime configuration and displaying the main interface.

**Why this priority**: Without this working, users cannot access any dashboard functionality at all. This is the absolute minimum for demo-ability.

**Independent Test**: Can be fully tested by opening the dashboard URL in a browser and verifying the runtime config loads without CORS errors. Delivers value by enabling basic dashboard access.

**Acceptance Scenarios**:

1. **Given** a user opens the dashboard in a browser, **When** the page loads and fetches `/api/v2/runtime`, **Then** the request succeeds and returns SSE URL configuration without CORS errors
2. **Given** the dashboard is loading, **When** the frontend makes any API request, **Then** the browser receives proper CORS headers allowing the response to be processed

---

### User Story 2 - Ticker Search (Priority: P1)

A user types a ticker symbol in the search bar and receives autocomplete suggestions from the API.

**Why this priority**: Ticker search is the primary user interaction for the dashboard. Equal priority to dashboard load.

**Independent Test**: Can be fully tested by typing "AAPL" in the search bar and verifying suggestions appear. Delivers value by enabling ticker discovery.

**Acceptance Scenarios**:

1. **Given** a user is on the dashboard, **When** they type "AAPL" in the ticker search, **Then** the search request to `/api/v2/tickers/search` succeeds and returns results without CORS errors
2. **Given** the search request is made from a browser, **When** the API responds, **Then** the response includes proper CORS headers (`Access-Control-Allow-Origin`)

---

### User Story 3 - All API Operations (Priority: P2)

All authenticated API operations (alerts, configurations, sentiment requests) work correctly from the browser.

**Why this priority**: These are secondary features that depend on Stories 1 and 2 working first.

**Independent Test**: Can be tested by performing any API operation (create alert, fetch configurations) and verifying no CORS errors occur.

**Acceptance Scenarios**:

1. **Given** a user is authenticated on the dashboard, **When** they perform any API operation, **Then** the request succeeds without CORS blocking
2. **Given** any POST/PUT/DELETE request is made, **When** the API responds, **Then** the response includes proper CORS headers for cross-origin access

---

### Edge Cases

- What happens when the frontend origin changes (different domain/port)? The CORS configuration should use wildcard or accept multiple origins.
- How does the system handle preflight caching (OPTIONS responses)? Standard browser caching based on `Access-Control-Max-Age` header.
- What happens if an API returns an error (4xx/5xx) - do error responses also include CORS headers? Yes, all responses must include CORS headers regardless of status code.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: All API responses MUST include `Access-Control-Allow-Origin` header matching the request origin or wildcard
- **FR-002**: All API responses MUST include `Access-Control-Allow-Headers` header listing accepted headers (Content-Type, Authorization, X-User-ID, X-Auth-Type)
- **FR-003**: All API responses MUST include `Access-Control-Allow-Methods` header listing allowed methods (GET, POST, PUT, DELETE, OPTIONS)
- **FR-004**: Error responses (4xx, 5xx) MUST include the same CORS headers as success responses
- **FR-005**: CORS headers MUST be consistent between preflight (OPTIONS) and actual requests

### Assumptions

- **Solution Approach**: API Gateway integration responses will add CORS headers at the gateway level via Terraform configuration (no Lambda code changes required)
- Wildcard origin (`*`) is acceptable for this application (no credentials mode requiring specific origin)
- The existing Lambda Function URL CORS configuration remains unchanged (no regression for direct Lambda URL access)
- Lambda remains CORS-agnostic - architectural separation maintained

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Dashboard loads successfully in browser without any CORS errors in console
- **SC-002**: Ticker search works from browser - typing "AAPL" returns suggestions within 2 seconds
- **SC-003**: 100% of API endpoints return proper CORS headers when accessed via API Gateway
- **SC-004**: Zero CORS-related errors in browser developer console during normal dashboard operation
- **SC-005**: Both authenticated and anonymous API requests work without CORS blocking
