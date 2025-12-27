# Feature Specification: Fix SSE Same-Origin Configuration

**Feature Branch**: `1068-fix-sse-same-origin`
**Created**: 2025-12-26
**Status**: Draft
**Input**: User description: "Fix SSE connection failure when same-origin configuration uses empty strings"

## Problem Statement

The SSE (Server-Sent Events) connection fails to establish when `API_BASE_URL` and `SSE_BASE_URL` are configured as empty strings, which is the correct configuration for same-origin requests.

### Root Cause

In `src/dashboard/timeseries.js:575-579`, the check `if (!baseUrl)` treats empty string as falsy, blocking SSE connection:

```javascript
const baseUrl = this.sseBaseUrl || this.apiBaseUrl;
if (!baseUrl) {  // BUG: '' is falsy but valid for same-origin
    console.warn('No SSE base URL configured');
    return;  // SSE connection blocked!
}
```

### Impact

1. Console warning: "No SSE base URL configured"
2. SSE EventSource never instantiated
3. Sentiment Trends chart shows initial data but never updates with real-time data
4. Resolution selector buttons work but SSE reconnection fails silently on switch

### Regression Context

- Introduced in PR #524 (Feature 1064: Unified Resolution Selector)
- PR #526 and #527 attempted fixes but addressed window exports, not the actual SSE connection issue

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Real-Time Sentiment Updates (Priority: P1)

As a dashboard user, I want to see sentiment data update in real-time so that I can make informed decisions based on current market sentiment.

**Why this priority**: This is the core value proposition of the dashboard - real-time sentiment visualization. Without SSE, the dashboard is static and loses most of its utility.

**Independent Test**: Can be tested by opening the dashboard, observing the console for SSE connection logs, and verifying data updates flow through without page refresh.

**Acceptance Scenarios**:

1. **Given** dashboard loads with same-origin config (empty string URLs), **When** page initialization completes, **Then** SSE connection MUST be established (no "No SSE base URL configured" warning)
2. **Given** SSE connection is established, **When** sentiment data is published, **Then** the Sentiment Trends chart MUST update without page refresh
3. **Given** user changes resolution, **When** resolution switch completes, **Then** SSE MUST reconnect with new resolution filter

---

### User Story 2 - Browser Console Clean Startup (Priority: P2)

As a developer debugging the dashboard, I want the console to be free of spurious warnings when the configuration is correct, so I can focus on actual issues.

**Why this priority**: Developer experience and observability. False warnings create noise and mask real problems.

**Independent Test**: Can be tested by opening browser DevTools console during dashboard load and verifying no warnings appear for valid configurations.

**Acceptance Scenarios**:

1. **Given** `CONFIG.SSE_BASE_URL` is empty string (same-origin), **When** `connectSSE()` is called, **Then** no warning MUST be logged
2. **Given** `CONFIG.SSE_BASE_URL` is `null` or `undefined`, **When** `connectSSE()` is called, **Then** a warning SHOULD be logged (actual config error)

---

### User Story 3 - Cross-Origin SSE Support (Priority: P3)

As a deployment engineer, I want to configure SSE to use a separate Lambda URL when using two-Lambda architecture, so I can scale SSE independently.

**Why this priority**: Important for production deployments but not blocking for basic functionality.

**Independent Test**: Can be tested by setting `CONFIG.SSE_BASE_URL` to a different hostname and verifying SSE connects to that URL.

**Acceptance Scenarios**:

1. **Given** `CONFIG.SSE_BASE_URL` is set to `https://sse-lambda.example.com`, **When** `connectSSE()` is called, **Then** EventSource MUST connect to that URL

---

### Edge Cases

- What happens when `apiBaseUrl` is set but `sseBaseUrl` is empty? (Should use `apiBaseUrl` fallback)
- What happens when both are explicitly `null`? (Should warn and return early)
- What happens when SSE URL is invalid? (Should fail gracefully at EventSource level)

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: System MUST establish SSE connection when `SSE_BASE_URL` is empty string (same-origin configuration)
- **FR-002**: System MUST use `apiBaseUrl` as fallback when `sseBaseUrl` is empty string but `apiBaseUrl` is set
- **FR-003**: System MUST only warn when both URLs are `null` or `undefined` (not just falsy)
- **FR-004**: System MUST construct valid same-origin URLs (e.g., `/api/v2/stream`) when baseUrl is empty string
- **FR-005**: System MUST reconnect SSE on resolution switch with new parameters

### Key Entities

- **CONFIG**: Global configuration object with `SSE_BASE_URL` and `API_BASE_URL`
- **TimeseriesManager**: Class managing SSE connection and sentiment data
- **EventSource**: Browser API for SSE connection

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: No "No SSE base URL configured" warning in console when using empty string configuration
- **SC-002**: SSE connection established within 1 second of `connectSSE()` call
- **SC-003**: Sentiment Trends chart receives real-time updates via SSE `bucket_update` events
- **SC-004**: Resolution selector changes trigger SSE reconnection without errors

## Technical Approach

### Fix Location

`src/dashboard/timeseries.js`, `connectSSE()` method (lines 569-613)

### Proposed Change

Replace truthy check with explicit null/undefined check:

```javascript
// Before (buggy)
const baseUrl = this.sseBaseUrl || this.apiBaseUrl;
if (!baseUrl) {
    console.warn('No SSE base URL configured');
    return;
}

// After (correct)
// Get base URL with proper fallback chain
// Empty string '' is valid for same-origin requests
const sseUrl = this.sseBaseUrl;
const apiUrl = this.apiBaseUrl;

// Only warn if both are truly unconfigured (null/undefined), not just empty
if ((sseUrl === null || sseUrl === undefined) &&
    (apiUrl === null || apiUrl === undefined)) {
    console.warn('No SSE base URL configured');
    return;
}

// Use nullish coalescing to allow empty string through
const baseUrl = sseUrl ?? apiUrl ?? '';
```

### Test Requirements

Unit tests should verify:
1. SSE connects when both URLs are empty strings
2. SSE connects when only `sseBaseUrl` is set
3. SSE connects when only `apiBaseUrl` is set
4. SSE warns and returns when both are `null`/`undefined`
