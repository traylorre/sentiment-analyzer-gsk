# Feature Specification: E2E OAuth Federation Flow Test

**Feature Branch**: `1178-e2e-oauth-federation-flow`
**Created**: 2025-01-09
**Status**: Draft
**Depends On**: 1176 (backend federation fields), 1177 (frontend mapping)

## User Scenarios & Testing

### User Story 1 - Verify Federation Fields in /me Response (Priority: P1)

After user authenticates (via any method), the `/api/v2/auth/me` endpoint returns federation fields (role, verification, linked_providers, last_provider_used).

**Why this priority**: Core E2E verification that federation data flows end-to-end.

**Acceptance Scenarios**:

1. **Given** authenticated user with JWT, **When** GET /api/v2/auth/me, **Then** response includes `role`, `verification`, `linked_providers`, `last_provider_used` fields

---

### User Story 2 - Verify OAuth Callback Contract Includes Federation (Priority: P2)

The OAuth callback endpoint contract includes federation fields in the response schema.

**Why this priority**: Validates Feature 1176 backend implementation.

**Acceptance Scenarios**:

1. **Given** OAuth callback request (with invalid code), **When** response is returned, **Then** error response structure is correct
2. **Given** OAuth callback response documentation, **When** fields are checked, **Then** federation fields are documented

---

### Edge Cases

- OAuth callback with invalid code returns proper error (not 500)
- Federation fields have sensible defaults even for error responses

## Requirements

### Functional Requirements

- **FR-001**: E2E test MUST verify `/api/v2/auth/me` returns federation fields
- **FR-002**: E2E test MUST verify OAuth callback error response structure
- **FR-003**: Tests MUST use existing E2E patterns (pytest-asyncio, PreprodAPIClient)
- **FR-004**: Tests MUST work with JWT authentication (authenticated_api_client fixture)

## Success Criteria

- **SC-001**: New E2E tests pass in preprod environment
- **SC-002**: Tests follow existing E2E patterns in test_auth_oauth.py
- **SC-003**: Tests use proper skip patterns for unimplemented features

## Technical Notes

E2E OAuth tests cannot test the full OAuth browser flow. Instead they test:
1. API contract verification (endpoints return expected fields)
2. Federation fields in /me response with JWT auth
3. Error handling for invalid OAuth codes
