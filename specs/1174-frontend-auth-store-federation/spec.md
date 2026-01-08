# Feature 1174: Frontend Auth Store Federation

## Problem Statement

The frontend auth store (`auth-store.ts`) doesn't populate federation fields when updating user state. Even though:
1. Feature 1172 added federation fields to the `/api/v2/auth/me` backend response
2. Feature 1173 added federation fields to the frontend `User` type

The auth store never maps these fields from API responses to state, so:
- `user.role` is always undefined
- `user.linkedProviders` is always undefined
- `user.verification` is always undefined
- `user.lastProviderUsed` is always undefined

## Root Cause

The `setUser()` calls in auth-store.ts receive User objects from API responses but:
1. Anonymous session initialization hardcodes fields without federation
2. Other auth paths pass through the API response, but we need to verify mapping

## Solution

Update auth-store.ts to include federation fields in all user state updates:

1. **Anonymous init**: Set default federation values
2. **API response mapping**: Ensure backend response fields are properly mapped
3. **Add profile refresh**: Fetch `/api/v2/auth/me` to get updated federation data

## Technical Specification

### Anonymous Session Initialization

**File:** `frontend/src/stores/auth-store.ts` (lines 100-107)

```typescript
setUser({
  userId: data.userId,
  authType: 'anonymous',
  createdAt: data.createdAt,
  configurationCount: 0,
  alertCount: 0,
  emailNotificationsEnabled: false,
  // Feature 1174: Federation fields
  role: 'anonymous',
  linkedProviders: [],
  verification: 'none',
  lastProviderUsed: undefined,
});
```

### API Response Mapping

The backend `/api/v2/auth/me` returns snake_case:
- `role` → `role` (no change)
- `linked_providers` → `linkedProviders`
- `verification` → `verification` (no change)
- `last_provider_used` → `lastProviderUsed`

Add response mapper function to handle snake_case → camelCase.

### Profile Refresh Function

Add `refreshUserProfile()` action that:
1. Calls `/api/v2/auth/me`
2. Maps response to User with federation fields
3. Updates state via `setUser()`

## Acceptance Criteria

1. Anonymous users have `role: 'anonymous'` in state
2. OAuth users have federation fields populated from API
3. `linkedProviders` reflects actual connected providers
4. `verification` reflects email verification status
5. TypeScript compiles without errors
6. Existing tests still pass

## Out of Scope

- UI components using federation fields (separate features)
- Role-based access control logic
- Provider linking UI

## Dependencies

- **Requires:** Feature 1172 (API returns fields) - MERGED
- **Requires:** Feature 1173 (User type has fields) - MERGED
- **Blocks:** Frontend RBAC components

## Testing Strategy

### Unit Tests

Update `tests/unit/stores/auth-store.test.ts`:
1. Anonymous init includes federation defaults
2. OAuth callback populates federation fields
3. Profile refresh updates federation fields

## References

- Feature 1172: API /me endpoint federation
- Feature 1173: Frontend User type
- `frontend/src/stores/auth-store.ts` (store implementation)
