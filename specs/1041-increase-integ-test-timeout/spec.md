# Feature Specification: Increase Preprod Integration Test Timeout

**Feature Branch**: `1041-increase-integ-test-timeout`
**Created**: 2025-12-24
**Status**: Implementation
**Input**: Pipeline failure - Integration tests timed out at 480s

## Problem Statement

The Preprod Integration Tests are timing out at 480s (8 minutes) after Dashboard Lambda container deployment. The tests themselves are passing but the overall timeout is insufficient for:
- Dashboard Lambda container cold starts (new container image deployment)
- Full E2E test suite including Playwright tests
- Multiple Lambda invocations across different endpoints

This blocks the Deploy Pipeline, preventing deployment of the OHLC resolution selector feature.

## Root Cause Analysis

1. Dashboard Lambda was recreated as a container image (Feature 1036)
2. Container Lambda cold starts take longer than ZIP deployments
3. The 480s timeout was set in specs/1029-fix-e2e-test-timeout when E2E suite grew
4. With container deployment, this timeout is no longer sufficient

## User Scenarios & Testing

### User Story 1 - Deploy Pipeline Passes (Priority: P1)

As a developer, when I push code to main branch, the Deploy Pipeline should complete successfully so that changes are deployed to preprod.

**Acceptance Scenarios**:

1. **Given** preprod deployment succeeds, **When** integration tests run, **Then** tests complete within the timeout without being killed

---

## Requirements

### Functional Requirements

- **FR-001**: Preprod integration test timeout MUST be increased from 480s to 720s (12 minutes)
- **FR-002**: Comment MUST be updated to reflect the new timeout value and rationale

### Files to Modify

- `.github/workflows/deploy.yml` - Update timeout in "Run Preprod Integration Tests" step

## Success Criteria

### Measurable Outcomes

- **SC-001**: Deploy Pipeline "Preprod Integration Tests" job completes without timeout
- **SC-002**: Integration tests have sufficient time to complete even with Lambda cold starts
- **SC-003**: Deploy to Production proceeds after successful integration tests
