# Feature 1173: Frontend User Type Federation Fields

## Problem Statement

The frontend `User` interface in `frontend/src/types/auth.ts` is missing federation fields that the backend now returns from `/api/v2/auth/me`:

- `role`: Authorization tier (anonymous/free/paid/operator)
- `linked_providers`: List of connected OAuth providers
- `verification`: Email verification status (none/pending/verified)
- `last_provider_used`: Most recent provider for avatar selection

Without these fields, the frontend cannot:
- Display role-based UI elements
- Show linked provider badges
- Gate features based on verification status
- Select avatars from the correct provider

## Root Cause

Feature 1172 added these fields to the backend API response, but the frontend TypeScript types weren't updated to consume them.

## Solution

Add federation fields to the frontend `User` interface and related types:

1. **Update User interface** with new optional fields
2. **Add TypeScript type aliases** for role/verification/provider types
3. **Update auth-store initialization** to include new fields

## Technical Specification

### Type Changes

**File:** `frontend/src/types/auth.ts`

```typescript
// New type aliases for federation
export type UserRole = 'anonymous' | 'free' | 'paid' | 'operator';
export type VerificationStatus = 'none' | 'pending' | 'verified';
export type ProviderType = 'email' | 'google' | 'github';

export interface User {
  userId: string;
  authType: AuthType;
  email?: string;
  createdAt: string;
  configurationCount: number;
  alertCount: number;
  emailNotificationsEnabled: boolean;
  // Feature 1173: Federation fields
  role?: UserRole;
  linkedProviders?: ProviderType[];
  verification?: VerificationStatus;
  lastProviderUsed?: ProviderType;
}
```

### API Response Mapping

The backend returns snake_case fields that map to camelCase:

| Backend Field | Frontend Field |
|---------------|----------------|
| `role` | `role` |
| `linked_providers` | `linkedProviders` |
| `verification` | `verification` |
| `last_provider_used` | `lastProviderUsed` |

### Default Values

All new fields are optional with sensible defaults:
- `role`: defaults to `'anonymous'` when not provided
- `linkedProviders`: defaults to `[]`
- `verification`: defaults to `'none'`
- `lastProviderUsed`: defaults to `undefined`

## Acceptance Criteria

1. `User` interface includes `role` field with `UserRole` type
2. `User` interface includes `linkedProviders` field with `ProviderType[]` type
3. `User` interface includes `verification` field with `VerificationStatus` type
4. `User` interface includes `lastProviderUsed` field with `ProviderType | undefined` type
5. TypeScript compiles without errors
6. All fields are optional (won't break existing code)
7. Type tests validate the interface

## Out of Scope

- Auth store consumption of these fields (Feature 1174)
- UI components using these fields (separate features)
- API layer mapping changes (if needed)

## Dependencies

- **Requires:** Feature 1172 (API returns federation fields) - MERGED
- **Blocks:** Feature 1174 (auth store federation)

## Testing Strategy

### Type Tests

Add type tests in `frontend/tests/unit/types/auth.test.ts`:
1. User object with all federation fields compiles
2. User object without federation fields still compiles (backward compatible)
3. Invalid role/verification values cause type errors

## References

- Feature 1172: API /me endpoint federation fields
- `frontend/src/types/auth.ts` (current User interface)
- `frontend/src/stores/auth-store.ts` (uses User type)
