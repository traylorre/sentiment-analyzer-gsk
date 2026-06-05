# Feature 1336: auth-retry-backoff

## Problem Statement

Seven E2E tests across 4 spec files fail intermittently with `ECONNREFUSED` when
Playwright's 4 parallel workers simultaneously call `setupAuthSession()`, which POSTs to
the single-threaded Python API server at `127.0.0.1:8000`. The server's TCP connection
queue fills, causing Node 18's `fetch()` to receive connection refused on subsequent
attempts. This is a race condition at the TCP level, not an application error.

## Root Cause

`createAnonymousSession()` in `frontend/tests/e2e/helpers/auth-helper.ts` performs a
single `fetch()` with zero retries. When 4+ workers call `setupAuthSession()` in their
`beforeEach` hooks concurrently, the Python server's `listen(5)` backlog is exceeded.
The OS rejects the SYN with RST, Node surfaces this as `TypeError: fetch failed` with
cause `ECONNREFUSED`.

Secondary factor: Node 18+ resolves `localhost` to `::1` (IPv6) first. If the Python
server binds only on `0.0.0.0` (IPv4), the IPv6 attempt fails immediately. The existing
code already mitigates this by using `127.0.0.1` directly, but the ECONNREFUSED under
load remains.

## Affected Tests (7)

| File | Tests Using `setupAuthSession` | Count |
|------|-------------------------------|-------|
| `alerts-crud.spec.ts` | `beforeEach` on all 4 tests | 1 call site |
| `navigation.spec.ts` | `Alerts Page` describe block `beforeEach` | 1 call site |
| `magic-link.spec.ts` | None (navigates to `/auth/signin` -- no auth needed) | 0 |
| `session-lifecycle.spec.ts` | None (tests session clearing/expiry, uses anonymous browsing) | 0 |

**Correction from initial report**: After reading the actual test files:
- `magic-link.spec.ts` does NOT use `setupAuthSession` -- it navigates to `/auth/signin`
  and mocks API routes. These tests fail for a DIFFERENT reason if at all (not ECONNREFUSED).
- `session-lifecycle.spec.ts` does NOT use `setupAuthSession` -- it navigates directly.
- The 7 affected tests are: 4 in `alerts-crud.spec.ts` + 2 in `navigation.spec.ts`
  (Alerts Page describe) = 6 total that call `setupAuthSession`.

The fix benefits ALL callers of `createAnonymousSession`, which is the shared utility.

## Fix: Two-Part Solution

### Part 1: Retry with Exponential Backoff in `createAnonymousSession`

Add retry logic to `createAnonymousSession()`:

- **Max attempts**: 3
- **Delays**: 1s, 2s (exponential backoff, base 1s, factor 2x)
- **Retry condition**: `TypeError` from `fetch()` (covers ECONNREFUSED, ETIMEDOUT,
  connection reset). These are network-level failures where the server never responded.
- **No retry on**: HTTP error responses (4xx, 5xx). If the server responded, the
  connection worked -- retrying won't help.
- **Throw on exhaustion**: After 3 failed attempts, throw with all attempt details.

### Part 2: No Changes to magic-link or session-lifecycle

After reading the actual code:
- `magic-link.spec.ts` already uses route mocking (`page.route()`), not real API calls.
  It does NOT call `setupAuthSession`. No changes needed.
- `session-lifecycle.spec.ts` navigates to pages directly without auth setup.
  No changes needed.

## Design Decisions

### Why retry at the utility level (not per-test)

Retry logic in `createAnonymousSession` protects ALL callers automatically. Adding retry
in each test's `beforeEach` would duplicate logic and be easy to forget in new tests.

### Why exponential backoff (not fixed delay)

Fixed delay risks all workers retrying simultaneously (thundering herd). Exponential
backoff with the natural jitter from different failure times spreads retries apart.

### Why no jitter

The natural timing variation from different test execution speeds provides sufficient
spreading. Adding random jitter to a 3-retry loop adds complexity without measurable
benefit in a 4-worker scenario.

### Why 3 attempts (not 5 or 10)

The connection queue recovers in <1s once a slot frees. 3 attempts with 1s+2s delays
gives 3s total wait, which is sufficient. More attempts would slow down genuine failures.

### Why TypeError check (not error message parsing)

`fetch()` throws `TypeError` for ALL network-level failures (ECONNREFUSED, ETIMEDOUT,
DNS failures). Checking `instanceof TypeError` is the stable, documented API. Parsing
error messages like "fetch failed" is fragile across Node versions.

## Acceptance Criteria

1. `createAnonymousSession` retries up to 3 times on network errors (TypeError).
2. `createAnonymousSession` does NOT retry on HTTP error responses (4xx/5xx).
3. Retry delays follow exponential backoff: 1000ms, 2000ms.
4. After all retries exhausted, error message includes attempt count and last error.
5. All existing tests pass (no behavioral change for the success path).
6. No changes to `magic-link.spec.ts` or `session-lifecycle.spec.ts`.

## Risk Assessment

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| Retry masks real server crash | Low | Medium | Only retries TypeError (network), not HTTP errors |
| Backoff delays slow tests | Low | Low | Max 3s added; only on failure path |
| New tests forget to use utility | Medium | Low | `setupAuthSession` is the only auth entry point |

## Out of Scope

- Increasing Python server backlog/thread count (infrastructure change, separate ticket)
- Worker count reduction (already set to 4, reducing defeats parallelism)
- Connection pooling in fetch (Node 18 default agent is adequate)
