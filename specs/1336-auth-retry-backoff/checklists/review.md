# Review Checklist: Auth Retry Backoff

**Feature**: 1336-auth-retry-backoff
**Date**: 2026-04-05

## Code Quality

- [ ] Retry logic is in the shared utility, not duplicated across test files
- [ ] Constants (MAX_ATTEMPTS, BASE_DELAY_MS) are named clearly, not magic numbers
- [ ] Sleep implementation is a simple promise wrapper (no external deps)
- [ ] Error discrimination uses `instanceof TypeError` (not string matching)
- [ ] No `console.log` -- only `console.warn` for retry notifications

## Correctness

- [ ] HTTP errors (4xx/5xx) are NOT retried (server responded, connection works)
- [ ] Only network failures (TypeError from fetch) trigger retry
- [ ] Exponential backoff delays are correct: 1000ms, 2000ms (not 1000, 1000)
- [ ] Final error message includes attempt count for debugging
- [ ] Existing error message for HTTP failures preserved
- [ ] Return type unchanged: `Promise<{user_id, auth_type, session_expires_at}>`

## Timing

- [ ] Worst-case retry adds 3s to a single test (1s + 2s), not blocking other workers
- [ ] No infinite loops possible (bounded by MAX_ATTEMPTS)
- [ ] No `await sleep()` on the final failed attempt (throw immediately)

## Blast Radius

- [ ] Only `auth-helper.ts` modified (single file change)
- [ ] `setupAuthSession` signature unchanged
- [ ] `createAnonymousSession` signature unchanged
- [ ] `mockAnonymousAuth` untouched
- [ ] `waitForAuth` untouched
- [ ] `mockOAuthRedirect` untouched
- [ ] No test files modified

## Edge Cases

- [ ] What if fetch throws a non-TypeError error? -- Re-thrown immediately (correct)
- [ ] What if server returns 201 on retry? -- Returns normally (correct)
- [ ] What if server returns 500 on first attempt? -- Throws immediately (correct)
- [ ] What if all 3 attempts get ECONNREFUSED? -- Throws with attempt count (correct)
