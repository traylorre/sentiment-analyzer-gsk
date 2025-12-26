# Tasks: Feature 1059 - E2E Test for /api/v2/metrics Auth Scenarios

## Implementation Tasks

### T001: Create test_metrics_auth.py file [P1]
- Create new file `tests/e2e/test_metrics_auth.py`
- Add module docstring explaining the endpoint distinction from `/api/v2/metrics/dashboard`
- Add pytest markers: `@pytest.mark.e2e`, `@pytest.mark.preprod`
- Import: pytest, PreprodAPIClient, existing fixtures

**Files**: `tests/e2e/test_metrics_auth.py` (new)
**Verification**: File exists with proper structure

### T002: Implement 401 test for missing auth [P1]
- Test function: `test_metrics_401_without_auth`
- Make GET /api/v2/metrics request WITHOUT any auth headers
- Assert status_code == 401
- Assert "Missing user identification" in response detail

**Files**: `tests/e2e/test_metrics_auth.py`
**Verification**: Test fails before auth fix, passes after

### T003: Implement 200 test for anonymous session [P1]
- Test function: `test_metrics_200_with_anonymous_session`
- Create anonymous session via POST /api/v2/auth/anonymous
- Extract token from response
- Call api_client.set_access_token(token)
- Make GET /api/v2/metrics request
- Assert status_code == 200
- Assert response contains metrics fields (total, positive, neutral, negative)
- Clean up in finally block

**Files**: `tests/e2e/test_metrics_auth.py`
**Verification**: Test passes with valid anonymous session

### T004: Implement 200 test for JWT auth [P1]
- Test function: `test_metrics_200_with_jwt_auth`
- Use `authenticated_api_client` fixture from conftest.py
- Make GET /api/v2/metrics request with JWT
- Assert status_code == 200
- Assert response contains metrics fields

**Files**: `tests/e2e/test_metrics_auth.py`
**Verification**: Test passes with valid JWT

### T005: Run local test validation [P1]
- Run: `pytest tests/e2e/test_metrics_auth.py -v --collect-only`
- Verify test collection works
- Verify markers are applied correctly

**Verification**: Tests are discoverable

## Verification Checklist

- [ ] T001: test_metrics_auth.py exists with proper docstring
- [ ] T002: 401 test implemented and verifies error message
- [ ] T003: Anonymous session test creates session and gets 200
- [ ] T004: JWT test uses authenticated fixture and gets 200
- [ ] T005: All tests collect without errors
