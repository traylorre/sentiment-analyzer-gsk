# Quickstart: Session Initialization Timeout

**Feature**: 1112-session-init-timeout
**Date**: 2025-12-31

## Overview

This feature adds timeout handling to anonymous session initialization, preventing the "Initializing session..." infinite loading state.

## Prerequisites

- Node.js 18+
- npm 9+
- Access to frontend directory

## Development Setup

```bash
cd frontend
npm install
npm run dev
```

No new dependencies required - uses native `AbortController` API.

## Files to Modify

| File | Change |
|------|--------|
| `src/lib/api/client.ts` | Add timeout support to RequestOptions |
| `src/lib/api/auth.ts` | Add timeout to createAnonymousSession |
| `src/lib/constants.ts` | Add SESSION_INIT_TIMEOUT_MS constant |

## Testing

### Unit Tests

```bash
cd frontend
npm test -- --testPathPattern=client.test
```

### Manual Testing

1. Open browser DevTools → Network → Throttling → Offline
2. Navigate to dashboard URL
3. Verify:
   - Loading indicator appears immediately
   - Error message appears within 15 seconds
   - Retry button is available
   - Clicking retry attempts new session

### Edge Cases to Test

| Scenario | Expected Behavior |
|----------|-------------------|
| Network offline | Error + retry within 15s |
| Slow network (3G) | Success or timeout + retry |
| Backend down | Error + retry within 15s |
| Valid localStorage session | Instant dashboard (no API call) |
| Expired localStorage session | API call with timeout |

## Configuration

```typescript
// frontend/src/lib/constants.ts
export const SESSION_INIT_TIMEOUT_MS = 10000;  // 10 seconds

// Usage in auth.ts
authApi.createAnonymousSession({ timeout: SESSION_INIT_TIMEOUT_MS });
```

## Error Messages

| Error Code | User Message |
|------------|--------------|
| TIMEOUT | "Connection timed out. Please check your network and try again." |
| NETWORK_ERROR | "Unable to connect. Please check your internet connection." |

## Verification Checklist

- [ ] Timeout fires after configured duration
- [ ] Error message is user-friendly (no technical jargon)
- [ ] Retry button works
- [ ] Existing localStorage session restoration still works
- [ ] No orphaned connections after timeout
