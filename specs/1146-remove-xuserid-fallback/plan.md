# Implementation Plan: Remove X-User-ID Header Fallback

**Branch**: `1146-remove-xuserid-fallback` | **Date**: 2026-01-05 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `/specs/1146-remove-xuserid-fallback/spec.md`

## Summary

Remove the X-User-ID header fallback mechanism from auth_middleware.py that allows user impersonation attacks. The middleware currently accepts X-User-ID header as a fallback when Bearer token is missing, enabling CVSS 9.1 Critical vulnerability. Fix requires removing fallback code and updating tests to use proper session-based authentication.

## Technical Context

**Language/Version**: Python 3.13
**Primary Dependencies**: FastAPI, PyJWT, boto3 (DynamoDB)
**Storage**: DynamoDB (users table, sessions)
**Testing**: pytest, moto (AWS mocks)
**Target Platform**: AWS Lambda
**Project Type**: Web application (backend + frontend)
**Performance Goals**: No latency impact (removing code)
**Constraints**: Must not break legitimate auth flows (magic link, OAuth, anonymous)
**Scale/Scope**: Security fix - minimal code change, significant test updates

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Gate | Status | Notes |
|------|--------|-------|
| Security & Access Control (§3) | PASS | Removing insecure fallback improves security |
| NoSQL/Expression safety (§100) | N/A | No DynamoDB changes |
| Functional Integrity Principle (§240-252) | PASS | Tests will be updated to use proper auth |
| Implementation Accompaniment Rule (§232-239) | PASS | All changes accompanied by test updates |
| Pipeline Check Bypass (§446-470) | N/A | Will not bypass |
| Environment Testing Matrix (§181-206) | PASS | Unit tests with mocks, E2E with real AWS |

**Pre-Phase 0 Result**: PASS - No violations

## Project Structure

### Documentation (this feature)

```text
specs/1146-remove-xuserid-fallback/
├── spec.md              # Feature specification
├── plan.md              # This file
├── research.md          # Phase 0 output
├── data-model.md        # N/A (no data model changes)
├── quickstart.md        # N/A (security fix, no new features)
├── contracts/           # N/A (no API contract changes)
└── tasks.md             # Phase 2 output
```

### Source Code (affected files)

```text
# Backend - Core Changes
src/lambdas/shared/middleware/
└── auth_middleware.py          # Lines 204-212, 314-325: Remove X-User-ID fallback

src/lambdas/dashboard/
└── router_v2.py                # Lines 283, 321, 420: Remove X-User-ID reads

# Frontend - Changes Required
frontend/src/lib/api/
└── client.ts                   # Lines 54-63, 115-121: Remove X-User-ID header

frontend/src/stores/
└── auth-store.ts               # Lines 70-71, 262-264: Remove setUserId sync

# CI/CD - Changes Required
.github/workflows/
└── deploy.yml                  # Lines 1252-1280: Update warmup requests

# Tests - Major Updates Required
tests/unit/dashboard/
├── test_auth.py                # Update: 5 tests use X-User-ID
├── test_ohlc.py                # Update: 17+ tests use X-User-ID headers
├── test_sentiment_history.py   # Update: AUTH_HEADERS uses X-User-ID
└── test_sse.py                 # Update: 1 test uses X-User-ID

tests/unit/lambdas/shared/auth/
└── test_session_consistency.py # Update: 6 tests use X-User-ID

tests/e2e/
├── test_metrics_auth.py        # Review/update
└── test_anonymous_restrictions.py # Review/update
```

**Structure Decision**: Web application with backend/ and frontend/ directories. Changes span both, plus CI/CD workflows.

## Complexity Tracking

No violations requiring justification. This is a removal/simplification, not an addition of complexity.

## Phase 0: Research Summary

### R1: X-User-ID Fallback Locations

**Primary Fallback (MUST REMOVE)**:
- `auth_middleware.py:204-212` in `extract_user_id()`:
  ```python
  # Lines to remove:
  user_id = normalized_headers.get("x-user-id")
  if user_id:
      return user_id
  ```

- `auth_middleware.py:314-325` in `extract_auth_context_typed()`:
  ```python
  # Lines to remove:
  user_id = normalized_headers.get("x-user-id")
  if user_id and _is_valid_uuid(user_id):
      return AuthContext(
          user_id=user_id,
          auth_type=AuthType.ANONYMOUS,
          auth_method="x-user-id",
          ...
      )
  ```

**Secondary Reads (EVALUATE)**:
- `router_v2.py:283` - GET /validate reads X-User-ID (optional linking)
- `router_v2.py:321` - POST /magic-link reads X-User-ID (optional linking)
- `router_v2.py:420` - Similar optional read

### R2: Authentication Flow Preservation

**Flows that MUST continue working**:
1. **Anonymous**: POST /auth/anonymous → returns UUID token → Bearer {uuid}
2. **Magic Link**: Request → email → verify → JWT tokens → Bearer {jwt}
3. **OAuth**: Redirect → provider → callback → JWT tokens → Bearer {jwt}

**Key insight**: All legitimate flows already use Bearer tokens. X-User-ID is ONLY used by:
- Legacy test code (must update)
- Frontend fallback (must remove)
- Warmup requests in CI (must update to use Bearer)

### R3: Test Migration Strategy

**Tests requiring update** (total ~30 tests):
- Replace `headers={"X-User-ID": uuid}` with `headers={"Authorization": f"Bearer {uuid}"}`
- For authenticated tests, use proper JWT fixture
- No behavior change expected - just header format

### R4: Frontend Impact

**client.ts:115-121** sets X-User-ID when no Bearer token:
```typescript
// Must remove this fallback:
if (!accessToken && state.userId) {
  headers['X-User-ID'] = state.userId;
}
```
After removal, frontend MUST use Bearer token always. Anonymous sessions already get a token from POST /auth/anonymous, so this is safe.

## Phase 1: Design

### D1: Backend Changes

**auth_middleware.py**:
1. Remove X-User-ID fallback from `extract_user_id()` (lines 204-212)
2. Remove X-User-ID fallback from `extract_auth_context_typed()` (lines 314-325)
3. Update function docstrings to clarify Bearer-only authentication

**router_v2.py**:
1. Evaluate each X-User-ID read - if for optional linking, remove
2. If any endpoint REQUIRES X-User-ID, refactor to use Bearer token

### D2: Frontend Changes

**client.ts**:
1. Remove X-User-ID header fallback (lines 115-121)
2. Ensure all requests use Authorization: Bearer header

**auth-store.ts**:
1. Remove setUserId sync to API client (lines 70-71, 262-264)
2. Keep userId in store for display purposes only

### D3: CI/CD Changes

**deploy.yml**:
1. Update warmup requests to use Bearer token format
2. Use a valid anonymous UUID as Bearer token

### D4: Test Updates

**Strategy**: Global find/replace where safe, manual review for edge cases

Pattern transformation:
```python
# Before:
headers={"X-User-ID": TEST_USER_ID}

# After:
headers={"Authorization": f"Bearer {TEST_USER_ID}"}
```

**Files to update**:
- tests/unit/dashboard/test_auth.py (5 tests)
- tests/unit/dashboard/test_ohlc.py (17+ tests)
- tests/unit/dashboard/test_sentiment_history.py (AUTH_HEADERS constant)
- tests/unit/dashboard/test_sse.py (1 test)
- tests/unit/lambdas/shared/auth/test_session_consistency.py (6 tests)

### D5: Test Cases to ADD

New tests to verify security fix:
1. `test_x_user_id_header_ignored()` - X-User-ID in request should be completely ignored
2. `test_x_user_id_without_bearer_returns_401()` - No Bearer + X-User-ID = 401
3. `test_bearer_only_authentication()` - Verify only Bearer is accepted

## Risks & Mitigations

| Risk | Mitigation |
|------|------------|
| Tests fail after header change | Automated find/replace with manual review |
| Frontend breaks for anonymous users | Verify /auth/anonymous returns token before deployment |
| Warmup requests fail | Test warmup with Bearer format in staging |
| Hidden X-User-ID dependencies | Comprehensive grep search before merge |

## Success Criteria Verification

| Criterion | How to Verify |
|-----------|---------------|
| SC-001: X-User-ID rejected without session | New test: send X-User-ID only, expect 401 |
| SC-002: Valid sessions work | All existing auth tests pass with Bearer |
| SC-003: Auth flows unchanged | E2E tests pass in preprod |
| SC-004: No regressions | Full test suite green |
| SC-005: Attack blocked | New test: X-User-ID spoofing returns 401 |
