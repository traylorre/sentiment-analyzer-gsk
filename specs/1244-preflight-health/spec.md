# Feature Specification: Pre-Flight Health Check Button

**Feature Branch**: `1244-preflight-health`
**Created**: 2026-03-27
**Status**: Draft
**Input**: "Feature 1244: Pre-Flight Health Check Button — expose `_capture_baseline(env)` via `/chaos/health` API endpoint + UI button in chaos.html"

## User Scenarios & Testing _(mandatory)_

### User Story 1 - Run Pre-Flight Health Check from Dashboard (Priority: P1)

Before starting a chaos experiment, the operator wants to click a button in the chaos dashboard to check all dependency health (DynamoDB, SSM, CloudWatch, Lambda) and see color-coded status cards showing which services are healthy vs degraded. This replaces running `scripts/chaos/status.sh` from the command line.

**Why this priority**: This is the only user story. The entire feature is a single API endpoint wiring an existing function to a UI button.

**Independent Test**: Click the health check button, verify 4 dependency cards appear with green/red status matching actual infrastructure state.

**Acceptance Scenarios**:

1. **Given** the chaos dashboard is loaded, **When** the operator clicks the "Pre-Flight Check" button, **Then** a health status panel appears showing 4 dependency cards (DynamoDB, SSM, CloudWatch, Lambda) with green badges for healthy and red badges for degraded.
2. **Given** all dependencies are healthy, **When** the health check completes, **Then** a summary shows "All systems healthy - safe to proceed" with a green indicator.
3. **Given** one or more dependencies are degraded, **When** the health check completes, **Then** a warning shows "N services degraded - do NOT inject chaos" with error details per degraded service.
4. **Given** a health check is in progress, **When** the button is clicked again, **Then** the second click is ignored (debounced) until the current check completes.

---

### User Story 2 - Stale Health Data Awareness (Priority: P2)

The operator wants to see when the last health check was performed, so they don't rely on stale data from 30 minutes ago when deciding to start an experiment.

**Acceptance Scenarios**:

1. **Given** a completed health check, **When** the operator views the status panel, **Then** a timestamp shows when the check was performed (e.g., "Checked 2 minutes ago").
2. **Given** the health check was performed more than 5 minutes ago, **When** the operator views the panel, **Then** the timestamp is displayed in a warning color indicating stale data.

---

### Edge Cases

- What happens when the API call to `/chaos/health` times out (Lambda cold start + slow AWS API calls)?
  - The UI shows a "Health check timed out — try again" message after 15 seconds. The button re-enables.
- What happens when the operator is not authenticated?
  - Returns 401. The UI shows "Authentication required" (same as all chaos endpoints).
- What happens when the environment is prod?
  - The chaos module's `check_environment_allowed()` prevents execution. Returns 403.
- What happens when SSM is unreachable but other services are healthy?
  - SSM shows degraded, others show healthy. The overall status is "degraded" because SSM is required for kill switch verification.

## Requirements _(mandatory)_

### Functional Requirements

- **FR-001**: System MUST expose a `GET /chaos/health` endpoint that returns dependency health for DynamoDB, SSM, CloudWatch, and Lambda.
- **FR-002**: System MUST reuse the existing `_capture_baseline(env)` function from `chaos.py` (line 1025) without modification.
- **FR-003**: System MUST enforce authentication using `_get_chaos_user_id_from_event()` pattern.
- **FR-004**: System MUST return a JSON response with `all_healthy` boolean, `dependencies` object (per-service status), and `captured_at` timestamp.
- **FR-005**: The UI MUST debounce the health check button to prevent rapid repeated calls (minimum 3 seconds between requests).

### Key Entities

- **Health Check Result**: The response from `_capture_baseline()` containing: `captured_at`, `dependencies` (map of service name to status/error), `all_healthy`, `degraded_services`.

## Success Criteria _(mandatory)_

- **SC-001**: Health check button triggers API call and renders 4 dependency status cards within 10 seconds.
- **SC-002**: Degraded services display with red badge and error message; healthy services display with green badge.
- **SC-003**: Authentication enforcement — unauthenticated requests return 401.

## Assumptions

- The existing `_capture_baseline(env)` function is sufficient; no modifications needed.
- The health check is a point-in-time snapshot, not a continuous monitor.
- Response time is acceptable (< 10s) given it makes 4 AWS API calls sequentially.

## Scope Boundaries

### In Scope
- `GET /chaos/health` API endpoint in handler.py
- Health check button + status cards in chaos.html
- Unit test for the endpoint

### Out of Scope
- Continuous health monitoring / polling
- Health check history
- Modifying `_capture_baseline()` behavior

## Dependencies

- **Feature 1237** (External Refactor): DONE — provides chaos.py infrastructure
- **Feature 1245** (Gate Toggle): Independent, no dependency
- **Feature 1246** (Andon Cord): Independent, no dependency
