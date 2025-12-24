# Feature Specification: Fix Warmup Lambda Auth 401

**Feature Branch**: `1042-fix-warmup-auth`
**Created**: 2025-12-24
**Status**: Implementation
**Input**: Pipeline warmup step returning HTTP 401 on authenticated endpoints

## Problem Statement

The "Warm Up Lambdas for Metrics" step in the Deploy Pipeline is returning HTTP 401 on authenticated endpoints (`/api/v2/metrics`, `/api/v2/sentiment`). This is caused by two issues:

1. **Missing Bearer prefix**: The warmup script sends `-H "Authorization: ${API_KEY}"` but the Dashboard Lambda auth middleware expects `Authorization: Bearer <token>` format (see `handler.py:240-242`)

2. **Silent failure**: The warmup commands use `|| true` which silently swallows auth failures, hiding misconfigurations from operators

## Root Cause Analysis

1. `deploy.yml:1254` sends: `Authorization: ${API_KEY}` (raw token)
2. `handler.py:240-242` validates: `parts = authorization.split(" ")` expecting `Bearer <token>`
3. When format check fails, 401 is returned, but `|| true` hides this

## User Scenarios & Testing

### User Story 1 - Auth Failures are Visible (Priority: P1)

As a DevOps engineer, when the warmup step fails authentication, I need to see the failure clearly so I can diagnose secret misconfiguration quickly.

**Why this priority**: Silent failures waste debugging time and mask real issues.

**Independent Test**: Run warmup step with invalid/missing API key - pipeline should fail visibly.

**Acceptance Scenarios**:

1. **Given** DASHBOARD_API_KEY secret is missing, **When** warmup runs, **Then** step fails with clear error message
2. **Given** authenticated warmup call returns 401, **When** operator views logs, **Then** error is visible (not hidden by fallback)

---

### User Story 2 - Warmup Auth Works Correctly (Priority: P1)

As the Deploy Pipeline, when warming up authenticated endpoints, I need to send correctly formatted auth headers so CloudWatch metrics are generated from real authenticated requests.

**Why this priority**: Without proper auth, warmup only exercises unauthenticated paths.

**Independent Test**: Warmup step returns HTTP 200 on `/api/v2/metrics` and `/api/v2/sentiment` endpoints.

**Acceptance Scenarios**:

1. **Given** DASHBOARD_API_KEY secret is configured, **When** warmup calls `/api/v2/metrics`, **Then** HTTP 200 is returned
2. **Given** DASHBOARD_API_KEY secret is configured, **When** warmup calls `/api/v2/sentiment`, **Then** HTTP 200 is returned

---

### Edge Cases

- What happens if API_KEY env var is empty string? Should fail explicitly.
- What happens if DASHBOARD_URL is malformed? Should fail with clear error.

## Requirements

### Functional Requirements

- **FR-001**: Warmup auth calls MUST use `Authorization: Bearer ${API_KEY}` format
- **FR-002**: Warmup auth calls MUST NOT use `|| true` fallback - failures must be visible
- **FR-003**: Warmup step MUST validate API_KEY is non-empty before making auth calls
- **FR-004**: Warmup step MUST fail the pipeline if authenticated endpoints return non-200

### Files to Modify

- `.github/workflows/deploy.yml` - Update warmup step auth headers and error handling

## Success Criteria

### Measurable Outcomes

- **SC-001**: Warmup `/api/v2/metrics` call returns HTTP 200
- **SC-002**: Warmup `/api/v2/sentiment` call returns HTTP 200
- **SC-003**: Pipeline fails visibly if DASHBOARD_API_KEY is missing or invalid
- **SC-004**: No `|| true` fallbacks on authenticated warmup calls
