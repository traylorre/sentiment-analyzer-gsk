# Implementation Plan: SSE Reconnect Race Condition Fix

**Feature**: 1274-sse-reconnect-race
**Created**: 2026-03-28
**Spec**: [spec.md](spec.md)

## Summary

Replace `waitForTimeout(5000)` + synchronous count assertion with `expect.poll()` in the SSE reconnection test of `chaos-cross-browser.spec.ts`. This eliminates the race condition between the test's fixed wait time and the app's exponential backoff timing.

## Design Decision

**Approach**: `expect.poll()` with generous timeout

**Alternatives considered**:
1. **Increase `waitForTimeout` to 15s**: Still a blind wait; wastes time when reconnection is fast, still races when slow. Rejected.
2. **Mock the backoff to be faster in tests**: Requires injecting test hooks into production code (`SSEConnection` constructor options). Violates NFR-001 (no production code changes). Rejected.
3. **Use `page.waitForRequest` with count**: Playwright's `waitForRequest` only waits for a single request. Would need nested calls, making the test harder to read. Rejected.
4. **`expect.poll()`**: Polls a condition at configurable intervals until it passes or times out. Already used in `chaos-sse-recovery.spec.ts` (T036) for the same pattern. Adopted.

## Implementation Steps

### Step 1: Replace blind wait with polling assertion

**File**: `frontend/tests/e2e/chaos-cross-browser.spec.ts`
**Lines**: 64-67

Replace:
```typescript
// Wait for at least 2 reconnection attempts
await page.waitForTimeout(5000);

// Should have multiple SSE requests (reconnection behavior works)
expect(sseRequests.length).toBeGreaterThanOrEqual(2);
```

With:
```typescript
// Wait for at least 2 reconnection attempts (poll instead of blind wait)
await expect
  .poll(() => sseRequests.length, {
    message: 'Expected 2+ SSE reconnection attempts',
    timeout: 15000,
    intervals: [500],
  })
  .toBeGreaterThanOrEqual(2);
```

### Step 2: Verify backoff interval assertion still works

The existing backoff interval check (lines 69-73) reads `sseRequests[0]` and `sseRequests[1]`, which are guaranteed to exist after the poll passes. No change needed.

## Verification

1. `npx playwright test chaos-cross-browser.spec.ts --retries=0` -- all tests pass
2. `grep -c 'waitForTimeout' frontend/tests/e2e/chaos-cross-browser.spec.ts` -- still shows 2 (the `beforeEach` wait + cached data test wait, which are out of scope for this feature)
3. The SSE reconnection test specifically has zero `waitForTimeout` calls

## Risk Assessment

- **Risk**: None. Single-line test change with no production code impact.
- **Rollback**: Revert the single file change.
