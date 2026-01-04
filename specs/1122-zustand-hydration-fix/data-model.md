# Data Model: Zustand Persist Hydration Fix

**Feature**: 1122-zustand-hydration-fix
**Date**: 2026-01-03

## Entities

### AuthState (Modified)

The auth store state interface is extended with hydration tracking:

```typescript
interface AuthState {
  // === Existing Fields (unchanged) ===
  user: User | null
  tokens: AuthTokens | null
  sessionExpiresAt: string | null
  isAuthenticated: boolean
  isAnonymous: boolean
  isLoading: boolean
  error: string | null
  isInitialized: boolean

  // === NEW: Hydration Tracking ===
  _hasHydrated: boolean  // true after zustand persist rehydrates from localStorage
}
```

**Validation Rules**:
- `_hasHydrated` MUST be `false` at store initialization (SSR-safe)
- `_hasHydrated` MUST be set to `true` ONLY via `onRehydrateStorage` callback
- `_hasHydrated` MUST NOT be persisted to localStorage (would defeat purpose)

### HydrationState (Conceptual)

Components subscribe to hydration state for progressive rendering:

```typescript
// Derived state pattern - not stored, computed from store
type HydrationState =
  | 'pending'    // _hasHydrated: false
  | 'complete'   // _hasHydrated: true
  | 'timeout'    // _hasHydrated: false after 5s timeout
```

### SessionInitState (Hook Return Type)

The `useSessionInit` hook return type is unchanged but behavior is modified:

```typescript
interface SessionInitResult {
  isInitializing: boolean  // true during init, false after
  isError: boolean         // true if init failed
  error: Error | null      // error details if failed
  isReady: boolean         // true when init complete + successful
}
```

**State Transitions**:

```
Initial:      { isInitializing: false, isError: false, error: null, isReady: false }
    ↓ (hydration completes)
Initializing: { isInitializing: true,  isError: false, error: null, isReady: false }
    ↓ (success)
Ready:        { isInitializing: false, isError: false, error: null, isReady: true }
    OR ↓ (failure)
Error:        { isInitializing: false, isError: true,  error: Error, isReady: false }
```

## Relationships

```
AuthStore (zustand)
    │
    ├─→ _hasHydrated ──→ useHasHydrated() ──→ Components
    │                           │
    │                           ├─→ ProtectedRoute (blocks redirect until hydrated)
    │                           ├─→ UserMenu (shows skeleton until hydrated)
    │                           └─→ useSessionInit (waits for hydration)
    │
    ├─→ isAuthenticated ──→ useAuth() ──→ Components (AFTER hydration)
    │
    └─→ user ──→ useUser() ──→ Components (AFTER hydration)
```

## State Machine: Session Initialization

```
┌──────────────────────────────────────────────────────────────────┐
│                        Page Load                                  │
└─────────────────────────────┬────────────────────────────────────┘
                              │
                              ▼
┌──────────────────────────────────────────────────────────────────┐
│  HYDRATING                                                        │
│  - _hasHydrated: false                                           │
│  - UI: Show skeletons for auth-dependent elements                │
│  - Actions: NONE (wait for zustand persist)                      │
└─────────────────────────────┬────────────────────────────────────┘
                              │
            ┌─────────────────┴─────────────────┐
            │                                   │
            ▼                                   ▼
┌───────────────────────┐           ┌───────────────────────┐
│ onRehydrateStorage    │           │ TIMEOUT (5s)          │
│ fires                 │           │                       │
└───────────┬───────────┘           └───────────┬───────────┘
            │                                   │
            ▼                                   ▼
┌───────────────────────┐           ┌───────────────────────┐
│ _hasHydrated: true    │           │ Proceed with empty    │
│ Check restored state  │           │ state (graceful       │
└───────────┬───────────┘           │ degradation)          │
            │                       └───────────┬───────────┘
            │                                   │
    ┌───────┴───────┐                          │
    │               │                          │
    ▼               ▼                          │
┌─────────┐   ┌─────────────┐                 │
│ Valid   │   │ No valid    │                 │
│ session │   │ session     │←────────────────┘
└────┬────┘   └──────┬──────┘
     │               │
     ▼               ▼
┌─────────┐   ┌─────────────┐
│ READY   │   │ Call        │
│ (skip   │   │ signIn      │
│  API)   │   │ Anonymous() │
└─────────┘   └──────┬──────┘
                     │
             ┌───────┴───────┐
             │               │
             ▼               ▼
       ┌─────────┐     ┌─────────┐
       │ SUCCESS │     │ ERROR   │
       │ → READY │     │ (show   │
       └─────────┘     │ retry)  │
                       └─────────┘
```

## localStorage Schema

### Key: `sentiment-auth-tokens`

```json
{
  "state": {
    "user": {
      "userId": "string",
      "authType": "anonymous|email|google|github",
      "email": "string|null",
      "createdAt": "ISO8601",
      "configurationCount": "number",
      "alertCount": "number",
      "emailNotificationsEnabled": "boolean"
    },
    "tokens": {
      "idToken": "string",
      "accessToken": "string",
      "refreshToken": "string",
      "expiresIn": "number"
    },
    "sessionExpiresAt": "ISO8601|null",
    "isAuthenticated": "boolean",
    "isAnonymous": "boolean"
  },
  "version": 0
}
```

**Note**: `_hasHydrated`, `isLoading`, `error`, and `isInitialized` are NOT persisted.
These are runtime-only state that must be recomputed on each page load.

## Component Prop Types

### ProtectedRoute (Modified)

```typescript
interface ProtectedRouteProps {
  children: React.ReactNode
  requireAuth?: boolean      // default: true
  requireUpgraded?: boolean  // default: false
  fallback?: React.ReactNode // optional fallback UI
  redirectTo?: string        // default: '/auth/signin'
}

// Internal state derived from hooks
type ProtectedRouteState = {
  hasHydrated: boolean      // NEW: from useHasHydrated()
  isInitialized: boolean    // from useAuth()
  isLoading: boolean        // from useAuth()
  isAuthenticated: boolean  // from useAuth()
  isAnonymous: boolean      // from useAuth()
}
```

### UserMenu (Modified)

```typescript
// No prop changes - internal state changes only
// Renders:
//   - Skeleton     when !hasHydrated
//   - SignInButton when hasHydrated && !isAuthenticated
//   - UserDropdown when hasHydrated && isAuthenticated
```
