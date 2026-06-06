# Implementation Plan: Auth Retry Backoff

**Feature Branch**: `1336-auth-retry-backoff`
**Created**: 2026-04-05
**Estimated Effort**: Small (~30 lines modified in 1 file)

## Files to Modify

### Production Code

| File | Change | Lines Added | Risk |
|------|--------|-------------|------|
| `frontend/tests/e2e/helpers/auth-helper.ts` | Add retry loop with exponential backoff to `createAnonymousSession` | ~25 | Low -- isolated utility, no callers change |

### No Other Files Changed

- Zero Python changes (server-side unchanged)
- Zero Terraform changes
- Zero test file changes (callers of `setupAuthSession` are unaffected)
- Zero config changes (playwright.config.ts unchanged)

---

## Architecture

### Retry Flow

```
createAnonymousSession(baseUrl)
  │
  ├── Attempt 1: fetch(POST /api/v2/auth/anonymous)
  │     ├── Success (201) → return JSON
  │     ├── HTTP error (4xx/5xx) → throw immediately (no retry)
  │     └── TypeError (ECONNREFUSED) → wait 1000ms
  │
  ├── Attempt 2: fetch(POST /api/v2/auth/anonymous)
  │     ├── Success (201) → return JSON
  │     ├── HTTP error → throw immediately
  │     └── TypeError → wait 2000ms
  │
  └── Attempt 3: fetch(POST /api/v2/auth/anonymous)
        ├── Success (201) → return JSON
        ├── HTTP error → throw immediately
        └── TypeError → throw with "after 3 attempts" message
```

### Timing Under Load (4 workers)

```
Worker 1: ──[fetch]──────────────────> OK
Worker 2: ──[fetch]──────────────────> OK
Worker 3: ──[fetch]─X─[1s wait]──[fetch]──> OK
Worker 4: ──[fetch]─X─[1s wait]──[fetch]──> OK
                   │
                   └── ECONNREFUSED (queue full)
```

Worst case: Worker waits 3s total (1s + 2s) before final attempt. All workers converge
within ~4s of test start.

## Implementation Strategy

### Single-function modification

The entire change is within `createAnonymousSession()`. The function signature and return
type remain identical. `setupAuthSession()` calls it unchanged.

### Sleep utility

Use a simple inline promise-based sleep:
```typescript
const sleep = (ms: number) => new Promise(resolve => setTimeout(resolve, ms));
```

This is defined inside the function or as a module-level helper. No external dependencies.

### Error discrimination

```typescript
try {
  const response = await fetch(...);
  // Got HTTP response -- server is alive
  if (response.status !== 201) {
    throw new Error(`HTTP ${response.status}`);  // No retry
  }
  return response.json();
} catch (error) {
  if (error instanceof TypeError) {
    // Network error (ECONNREFUSED, ETIMEDOUT, etc.) -- retry
    continue;
  }
  throw error;  // HTTP error or unknown -- don't retry
}
```

The key insight: `fetch()` throws `TypeError` for network failures. HTTP errors come via
the `Response` object. We only need to check `instanceof TypeError` to distinguish them.

## Constraints

- Must preserve the existing function signature (callers unchanged)
- Must preserve the existing JSDoc comments
- Must not add external dependencies
- Must not modify playwright.config.ts worker count
- Must not modify any test files

## Rollback Plan

Revert the single file change. No data migration, no config changes, no side effects.
