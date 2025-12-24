# Feature Specification: Dashboard Smoke Test Environment Variables

**Feature Branch**: `1039-dashboard-smoke-test-env`
**Created**: 2025-12-24
**Status**: Draft
**Input**: User description: "Fix Dashboard Lambda smoke test missing environment variables"

## User Scenarios & Testing

### User Story 1 - CI Pipeline Passes After Dashboard Lambda Build (Priority: P1)

As a developer, when I push code to main branch, the Deploy Pipeline should complete successfully so that changes are deployed to preprod.

**Why this priority**: Deploy Pipeline is blocked - no code can be deployed until this is fixed.

**Independent Test**: Push to main and verify Deploy Pipeline passes the "Build Dashboard Lambda Image (Preprod)" job.

**Acceptance Scenarios**:

1. **Given** a push to main branch, **When** the Dashboard Lambda image builds successfully, **Then** the smoke test should pass without KeyError
2. **Given** the smoke test runs, **When** it imports `from handler import lambda_handler`, **Then** the ENVIRONMENT and DATABASE_TABLE env vars are available

---

### Edge Cases

- Smoke test should fail if imports actually break (not mask failures with fallbacks)
- Environment variables should match what Lambda receives at runtime

## Requirements

### Functional Requirements

- **FR-001**: Dashboard smoke test MUST pass `-e ENVIRONMENT=preprod` to docker run
- **FR-002**: Dashboard smoke test MUST pass `-e DATABASE_TABLE=preprod-sentiment-items` to docker run
- **FR-003**: Smoke test MUST follow the same pattern as SSE Lambda smoke test (which works correctly)

### Files to Modify

- `.github/workflows/deploy.yml` - Add missing env vars to Dashboard smoke test docker run command

## Success Criteria

### Measurable Outcomes

- **SC-001**: Deploy Pipeline "Build Dashboard Lambda Image (Preprod)" job passes
- **SC-002**: Smoke test validates imports work with realistic environment variables
- **SC-003**: Deploy to Preprod proceeds after smoke test passes

## Root Cause Analysis

The SSE Lambda smoke test correctly passes environment variables:
```bash
docker run --rm -e PYTHONPATH=/app/packages:/app -e DATABASE_TABLE=preprod-sentiment-items --entrypoint python "$IMAGE"
```

The Dashboard Lambda smoke test is missing them:
```bash
docker run --rm --entrypoint python "$IMAGE"  # Missing -e flags
```

The `chaos.py` module requires `ENVIRONMENT` at import time (line 43), which is correct behavior - it should fail if not set. The fix is to provide the env vars in the smoke test, not add fallbacks to code.
