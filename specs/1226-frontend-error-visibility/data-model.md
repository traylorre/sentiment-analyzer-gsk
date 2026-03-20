# Data Model: Frontend Error Visibility

## Entities

### API Health State (Zustand store)

| Field | Type | Description |
|-------|------|-------------|
| failures | `{ timestamp: number }[]` | Sliding window of failure timestamps (epoch ms) within last 60 seconds |
| isUnreachable | `boolean` | True when 3+ failures in the 60-second window |
| bannerDismissed | `boolean` | True when user manually dismissed the banner; resets on recovery |

**State Transitions:**

```
HEALTHY (isUnreachable: false)
  ├─ recordFailure() → if failures.length >= 3 in 60s → UNREACHABLE
  └─ recordFailure() → if failures.length < 3 → stays HEALTHY

UNREACHABLE (isUnreachable: true)
  ├─ recordSuccess() → clear failures, set isUnreachable: false → HEALTHY
  ├─ dismissBanner() → set bannerDismissed: true → UNREACHABLE (banner hidden)
  └─ recordFailure() → stays UNREACHABLE

UNREACHABLE + DISMISSED (bannerDismissed: true)
  ├─ recordSuccess() → clear all, bannerDismissed: false → HEALTHY
  └─ recordFailure() → stays UNREACHABLE + DISMISSED (banner stays hidden)
  └─ (new failure cycle after recovery) → bannerDismissed resets → banner shows again
```

**Actions:**

| Action | Trigger | Effect |
|--------|---------|--------|
| `recordFailure()` | QueryCache.onError fires | Push timestamp to failures array, prune entries older than 60s, evaluate threshold |
| `recordSuccess()` | QueryCache.onSuccess fires (any query) | Clear failures array, set isUnreachable: false, reset bannerDismissed |
| `dismissBanner()` | User clicks X on banner | Set bannerDismissed: true (banner hidden but state stays unreachable) |

### Error Context (derived, not stored)

React Query already provides per-query error state. No new storage needed. The `ApiClientError` class (existing) carries:

| Field | Type | Source |
|-------|------|--------|
| status | `number` | HTTP status code (0 for network errors) |
| code | `ErrorCode` | `NETWORK_ERROR`, `TIMEOUT`, `SERVER_ERROR`, `CLIENT_ERROR`, `AUTH_ERROR`, `UNKNOWN_ERROR` |
| message | `string` | Human-readable error message |

The ticker search component reads `isError` and `error` from its `useQuery` result to distinguish error from empty.

### Auth Session Health (extension to existing auth-store)

| Field | Type | Description |
|-------|------|-------------|
| refreshFailureCount | `number` | Consecutive session refresh failures (resets on success) |
| sessionDegraded | `boolean` | True when refreshFailureCount >= 2 |

**State Transitions:**

```
HEALTHY (refreshFailureCount: 0, sessionDegraded: false)
  └─ refreshSession() fails → increment count
     ├─ count < 2 → stays HEALTHY
     └─ count >= 2 → sessionDegraded: true → DEGRADED

DEGRADED (sessionDegraded: true)
  └─ refreshSession() succeeds → count: 0, sessionDegraded: false → HEALTHY
```

### Console Event Schema

Each error state transition emits a structured console warning:

```typescript
{
  event: 'api_health_banner_shown' | 'api_health_banner_dismissed' |
         'api_health_recovered' | 'search_error_displayed' |
         'auth_degradation_warning',
  timestamp: string,     // ISO 8601
  details: {
    failureCount?: number,
    endpoint?: string,
    errorCode?: string,
    errorMessage?: string,
  }
}
```
