# Feature Specification: Frontend OAuth Federation Wiring

**Feature Branch**: `1177-frontend-oauth-federation-wiring`
**Created**: 2025-01-09
**Status**: Draft
**Input**: Wire frontend to consume federation fields from OAuth callback response.
**Depends On**: Feature 1176 (backend now returns federation fields in OAuthCallbackResponse)

## User Scenarios & Testing

### User Story 1 - Receive Federation State After OAuth (Priority: P1)

After authenticating via OAuth, the frontend auth store receives and stores the user's role, verification status, linked providers, and last provider used. This enables RBAC-aware UI decisions.

**Why this priority**: Core gap - backend now sends federation fields but frontend doesn't extract them.

**Independent Test**: After OAuth callback, auth store contains correct `role`, `verification`, `linkedProviders`, `lastProviderUsed`.

**Acceptance Scenarios**:

1. **Given** anonymous user authenticating via Google, **When** OAuth callback completes, **Then** auth store has `role="free"`, `verification="verified"`, `linkedProviders=["google"]`, `lastProviderUsed="google"`

2. **Given** existing user re-authenticating, **When** OAuth callback completes, **Then** auth store preserves existing role and adds provider to linkedProviders

---

### Edge Cases

- What happens on conflict response? Frontend should handle `status="conflict"` gracefully without crashing.
- What happens if federation fields are missing? Frontend should use defaults (backward compatibility).

## Requirements

### Functional Requirements

- **FR-001**: Frontend MUST define `OAuthCallbackResponse` interface matching backend snake_case fields
- **FR-002**: Frontend MUST map OAuth callback response to User type with federation fields
- **FR-003**: `exchangeOAuthCode` MUST return properly typed response with federation fields
- **FR-004**: Auth store MUST receive and store federation fields from OAuth response
- **FR-005**: Frontend MUST handle missing federation fields gracefully (defaults)

### Key Entities

- **OAuthCallbackResponse**: Backend response type (snake_case)
- **User**: Frontend user type (camelCase, includes federation fields from 1173)
- **mapOAuthCallbackResponse**: New mapping function

## Success Criteria

- **SC-001**: OAuth callback response federation fields mapped to User type
- **SC-002**: Auth store contains correct federation state after OAuth
- **SC-003**: Existing frontend tests still pass
- **SC-004**: New unit tests verify federation field mapping

## Technical Context

### Current State

**Backend response** (`OAuthCallbackResponse` from auth.py):
```python
status: str
email_masked: str | None
auth_type: str | None
tokens: dict | None
role: str = "anonymous"  # Feature 1176
verification: str = "none"  # Feature 1176
linked_providers: list[str] = []  # Feature 1176
last_provider_used: str | None  # Feature 1176
```

**Frontend expects** (`AuthResponse` from auth.ts):
```typescript
user: User;
tokens: AuthTokens;
```

**Gap**: No mapping from backend snake_case OAuth response to frontend camelCase User type.

### Required Changes

1. Add `OAuthCallbackResponse` interface in `auth.ts`
2. Add `mapOAuthCallbackResponse()` function
3. Update `exchangeOAuthCode` to use the mapping
4. Add unit tests for the mapping
