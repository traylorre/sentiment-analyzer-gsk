# Data Model: Session Initialization Timeout

**Feature**: 1112-session-init-timeout
**Date**: 2025-12-31

## Entities

### Existing Entities (No Changes Required)

#### Session
Represents user authentication state.

| Field | Type | Description |
|-------|------|-------------|
| userId | string | Unique user identifier |
| expiresAt | number | Unix timestamp of session expiry |
| authType | 'anonymous' \| 'authenticated' | Type of authentication |

#### InitializationState
Tracks progress of session creation (implicit in Zustand store).

| Field | Type | Description |
|-------|------|-------------|
| isLoading | boolean | Whether session init is in progress |
| isInitialized | boolean | Whether init has completed (success or failure) |
| error | string \| null | Error message if init failed |

### Modified Entities

#### ApiClientError
Extended to support timeout-specific errors.

| Field | Type | Description |
|-------|------|-------------|
| message | string | Human-readable error message |
| status | number | HTTP status code (0 for network errors) |
| code | ErrorCode | Error classification |

**ErrorCode Union Type**:
```typescript
type ErrorCode =
  | 'NETWORK_ERROR'
  | 'TIMEOUT'        // NEW: Added for timeout handling
  | 'AUTH_ERROR'
  | 'SERVER_ERROR'
  | 'CLIENT_ERROR'
  | 'UNKNOWN';
```

### New Types

#### RequestOptions (Extended)
Options for API client requests.

| Field | Type | Description |
|-------|------|-------------|
| method | string | HTTP method |
| headers | Record<string, string> | Request headers |
| body | unknown | Request body |
| timeout | number \| undefined | **NEW**: Request timeout in milliseconds |

## State Transitions

### Session Initialization Flow

```
[Initial]
    │
    ▼
[Loading] ──timeout──► [Error: "Connection timed out"]
    │                         │
    │                         ▼
    │                   [Retry Available]
    │                         │
    │                    retry clicked
    │                         │
    ▼◄────────────────────────┘
[Success]
    │
    ▼
[Dashboard Ready]
```

## Validation Rules

1. **Timeout must be positive**: `timeout > 0` when specified
2. **Timeout has reasonable bounds**: `1000 <= timeout <= 60000` (1-60 seconds)
3. **Error message must be user-friendly**: No technical jargon (stack traces, error codes)

## Relationships

```
RequestOptions (1) ──contains── (0..1) timeout
ApiClientError (1) ──has── (1) ErrorCode
AuthStore (1) ──manages── (1) InitializationState
```
