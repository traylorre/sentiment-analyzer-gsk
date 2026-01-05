# Data Model: Remove Zustand Persist Middleware

**Feature**: 1131-remove-zustand-persist
**Date**: 2026-01-05

## Entities

### 1. AuthState (Zustand Store State)

**Location**: `frontend/src/stores/auth-store.ts`

| Field | Type | Persisted Before | Persisted After | Notes |
|-------|------|------------------|-----------------|-------|
| `user` | `User \| null` | Yes | Yes | Non-sensitive profile data |
| `tokens` | `AuthTokens \| null` | **Yes** | **NO** | **SECURITY FIX** |
| `sessionExpiresAt` | `number \| null` | Yes | Yes | Timestamp only |
| `isAuthenticated` | `boolean` | Yes | Yes | Session flag |
| `isAnonymous` | `boolean` | Yes | Yes | Session flag |
| `isLoading` | `boolean` | No | No | Runtime state |
| `isInitialized` | `boolean` | No | No | Runtime state |
| `error` | `string \| null` | No | No | Runtime state |
| `_hasHydrated` | `boolean` | No | No | Internal flag |

### 2. AuthTokens (Token Container)

**Location**: `frontend/src/stores/auth-store.ts`

| Field | Type | Storage Location |
|-------|------|------------------|
| `accessToken` | `string` | Memory ONLY (not persisted) |
| `refreshToken` | `string` | Memory ONLY (not persisted) |
| `idToken` | `string \| undefined` | Memory ONLY (not persisted) |

**Security Constraint**: These fields MUST NEVER be written to localStorage, sessionStorage, or any client-side persistent storage.

### 3. localStorage Schema (After Fix)

**Key**: `auth-store`

**Before**:
```json
{
  "state": {
    "user": { "userId": "...", "authType": "..." },
    "tokens": { "accessToken": "...", "refreshToken": "...", "idToken": "..." },
    "sessionExpiresAt": 1234567890,
    "isAuthenticated": true,
    "isAnonymous": false
  },
  "version": 0
}
```

**After**:
```json
{
  "state": {
    "user": { "userId": "...", "authType": "..." },
    "sessionExpiresAt": 1234567890,
    "isAuthenticated": true,
    "isAnonymous": false
  },
  "version": 0
}
```

**Note**: The `tokens` field is completely absent from the persisted state.

## State Transitions

### Token Lifecycle

```
User Login
    ↓
Tokens received from backend
    ↓
Stored in memory (zustand state)
    ↓
Synced to httpOnly cookies (setAuthCookies)
    ↓
Used for API requests via auth headers
    ↓
Page Refresh
    ├── Tokens LOST (memory cleared)
    └── httpOnly cookies remain (backend can validate)
```

### Migration Flow (One-Time)

```
App Initialization
    ↓
zustand persist rehydrates from localStorage
    ↓
onRehydrate callback fires
    ↓
Check for existing tokens in stored data
    ├── Tokens found → Delete from localStorage, clear from state
    └── No tokens → Continue normally
    ↓
App ready with clean state
```

## Validation Rules

| Rule | Enforcement | Error Handling |
|------|-------------|----------------|
| Tokens must not be in localStorage | partialize excludes tokens | N/A (design prevents) |
| Existing tokens must be cleared | onRehydrate migration | Silent cleanup |
| Session flags can persist | partialize includes flags | N/A |
