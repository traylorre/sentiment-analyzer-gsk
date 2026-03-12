# Feature Specification: Fix Anonymous Auth 422 Error

**Feature Branch**: `1060-fix-anonymous-auth-422`
**Created**: 2025-12-26
**Status**: Draft
**Input**: POST /api/v2/auth/anonymous returns 422 Unprocessable Entity

## Problem Statement

The vanilla JS dashboard (`src/dashboard/app.js`) sends a POST request to `/api/v2/auth/anonymous` with `Content-Type: application/json` header but **no request body**. FastAPI/Pydantic rejects this with 422 because it expects a JSON object (even if empty `{}`).

**Root Cause**: Line 106-114 in app.js:
```javascript
const response = await fetch(url, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' }
    // Missing: body: JSON.stringify({})
});
```

## User Scenarios & Testing _(mandatory)_

### User Story 1 - Anonymous Session Creation (Priority: P1)

As a dashboard user, I want to automatically get an anonymous session when I load the dashboard so that I can view metrics without explicit login.

**Why this priority**: Without a working anonymous session, the entire dashboard returns 401 on all API calls. This is a complete blocker for the demo-able URL goal.

**Acceptance Scenarios**:

1. **Given** a user loads the dashboard, **When** the page initializes, **Then** POST /api/v2/auth/anonymous returns 201 with a valid session token.

2. **Given** the session is created, **When** subsequent API calls are made, **Then** they include the X-User-ID header and return 200.

---

### Edge Cases

- What if localStorage is not available? The code already handles this gracefully (line 100-102).
- What if the server returns an error? The code throws and shows an error in the skeleton UI.

## Requirements _(mandatory)_

### Functional Requirements

- **FR-001**: POST /api/v2/auth/anonymous MUST include `body: JSON.stringify({})` in the fetch options.
- **FR-002**: The change MUST NOT alter the response handling (lines 116-128).
- **FR-003**: Existing E2E tests MUST continue to pass (they already send `json={}`).

### Key Entities

- **app.js**: Vanilla JS dashboard at `src/dashboard/app.js`
- **AnonymousSessionRequest**: Pydantic model expecting optional `timezone` and `device_fingerprint` fields

## Success Criteria _(mandatory)_

### Measurable Outcomes

- **SC-001**: Dashboard loads without 422 errors in browser console.
- **SC-002**: E2E test `test_auth_anonymous.py` continues to pass.
- **SC-003**: After page load, sessionUserId is populated with a valid UUID.

## Implementation Notes

Single-line fix:

```diff
  const response = await fetch(
      `${CONFIG.API_BASE_URL}${CONFIG.ENDPOINTS.AUTH_ANONYMOUS}`,
      {
          method: 'POST',
          headers: {
              'Content-Type': 'application/json'
-         }
+         },
+         body: JSON.stringify({})
      }
  );
```
