# Implementation Checklist: 1274-sse-reconnect-race

## Pre-Implementation
- [ ] Read full `chaos-cross-browser.spec.ts` to confirm current state matches spec
- [ ] Confirm `expect.poll()` pattern from `chaos-sse-recovery.spec.ts` T036

## Implementation
- [ ] Replace `waitForTimeout(5000)` + count assertion with `expect.poll()` (FR-001, FR-002, FR-003)
- [ ] Verify backoff interval assertion still follows the poll (FR-004)
- [ ] Confirm no other lines in the test function use `waitForTimeout` (FR-005)

## Post-Implementation
- [ ] No production code changes (NFR-001)
- [ ] Only the SSE reconnection test was modified (NFR-002)
- [ ] Grep for `waitForTimeout` in SSE reconnection test -- zero instances
- [ ] Test passes (if local Playwright available)

## Patterns
- [ ] `expect.poll()` uses `message` parameter for diagnostics
- [ ] `expect.poll()` uses `timeout: 15000` (generous for backoff)
- [ ] `expect.poll()` uses `intervals: [500]` (efficient polling)
