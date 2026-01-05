# Research: Remove X-User-ID Header Fallback

**Feature**: 1146-remove-xuserid-fallback
**Date**: 2026-01-05

## Research Questions

### RQ1: Where is X-User-ID fallback implemented?

**Decision**: Remove fallback from two locations in auth_middleware.py

**Findings**:
- `extract_user_id()` at lines 204-212: Falls back to X-User-ID after Bearer token check
- `extract_auth_context_typed()` at lines 314-325: Returns AuthContext with auth_method="x-user-id"
- Both functions normalize headers to lowercase and check for `x-user-id` key

**Rationale**: These are the ONLY locations where X-User-ID is accepted as identity source. Other router_v2.py reads are for optional account linking, not primary identity.

**Alternatives Considered**:
- Deprecation warning first: Rejected - this is a CVSS 9.1 Critical vulnerability
- Feature flag: Rejected - security fixes must be immediate, not gradual

### RQ2: What legitimate code uses X-User-ID?

**Decision**: Update all legitimate uses to Bearer token format

**Findings**:
1. **Frontend client.ts:115-121**: Sets X-User-ID when no Bearer token (fallback)
2. **Frontend auth-store.ts:70-71**: Syncs userId to API client for X-User-ID
3. **CI deploy.yml:1252-1280**: Warmup requests use X-User-ID header
4. **Tests**: ~30 test functions use X-User-ID for test authentication

**Rationale**: All legitimate authentication already supports Bearer tokens. The /auth/anonymous endpoint returns a UUID that can be used as Bearer token. X-User-ID is redundant.

**Alternatives Considered**:
- Keep X-User-ID for backwards compatibility: Rejected - security vulnerability
- Add migration period: Rejected - no external clients depend on this header

### RQ3: How should tests be updated?

**Decision**: Replace X-User-ID headers with Bearer authorization headers

**Findings**:
- Anonymous auth uses UUID as both user_id and token
- Pattern: `headers={"X-User-ID": uuid}` → `headers={"Authorization": f"Bearer {uuid}"}`
- Tests for X-User-ID rejection should be ADDED (not existing behavior)

**Rationale**: This is the minimal change that preserves test coverage while using the correct authentication method.

**Alternatives Considered**:
- Create new auth fixture with JWT mocking: Overkill for anonymous tests
- Use actual session creation in tests: Adds complexity without benefit

### RQ4: What is the frontend impact?

**Decision**: Remove X-User-ID fallback from client.ts, rely on Bearer token only

**Findings**:
- Frontend stores accessToken from /auth/anonymous response
- accessToken IS the user_id for anonymous sessions
- X-User-ID is only set when accessToken is missing (edge case that shouldn't occur)

**Rationale**: If accessToken is missing, the user should re-authenticate via /auth/anonymous rather than fall back to insecure header.

**Alternatives Considered**:
- Keep X-User-ID as backup: Rejected - defeats the security fix
- Auto-redirect to /auth/anonymous if no token: Could add, but out of scope for this fix

## Summary

| Question | Decision | Confidence |
|----------|----------|------------|
| RQ1: Fallback location | Remove from auth_middleware.py (2 functions) | High |
| RQ2: Legitimate uses | Update frontend, CI, tests to use Bearer | High |
| RQ3: Test strategy | Find/replace header format | High |
| RQ4: Frontend impact | Remove fallback, require Bearer token | High |

All research questions resolved. No NEEDS CLARIFICATION items remaining.
