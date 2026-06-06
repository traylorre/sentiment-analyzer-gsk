# Feature 1344: Clean Up chaos-cross-browser.spec.ts Dead Code and Duplicates

## Status: DRAFT

## Problem Statement

`chaos-cross-browser.spec.ts` has three tests. One is dead code (`test.fixme()` SSE
reconnection test at line 74) that can never pass because the mock API doesn't implement
SSE endpoints -- this was documented in the FIXME comment itself. The other two tests
(banner lifecycle and cached data persistence) duplicate primary tests in
`chaos-degradation.spec.ts` and `chaos-cached-data.spec.ts` respectively. However, these
duplicates serve a valid purpose: they are the ONLY tests that run under Playwright's
Mobile Chrome and Mobile Safari projects, providing cross-browser smoke coverage.

Additionally, the file has quality issues shared with the primary chaos specs:
- `waitForTimeout(2000)` in `beforeEach` (line 23) is a blind wait, not response-based
- `waitForTimeout(500)` in cached data test (line 61) for settle
- No content comparison in the cached data test (checks `textDuring` is truthy but doesn't
  compare to `textBefore` -- Green Dashboard Syndrome)
- Missing JSDoc documenting the cross-browser smoke test rationale

## User Stories

### US-001: Remove Dead SSE Test
**As a** test maintainer reading this file,
**I want** the dead `test.fixme()` SSE reconnection test removed entirely,
**So that** there is no confusion about whether SSE testing is operational in this suite.

### US-002: Document Cross-Browser Smoke Test Purpose
**As a** developer deciding whether to delete duplicate-looking tests,
**I want** explicit file-level and test-level documentation explaining these are
cross-browser smoke tests (Playwright runs them on Mobile Chrome + Mobile Safari),
**So that** future cleanup efforts don't accidentally remove cross-browser coverage.

### US-003: Apply Green Dashboard Syndrome Fixes
**As a** test consumer reviewing CI results,
**I want** the cached data test to compare content before and after chaos injection,
**So that** a bug replacing real data with an error page would fail the test instead of
passing because "something is visible."

### US-004: Replace Blind Waits with Response-Based Waits
**As a** a CI pipeline running these tests,
**I want** `waitForTimeout` calls replaced with response-based or DOM-based waits,
**So that** tests are deterministic and don't flake due to timing.

## Requirements

### Functional Requirements

#### FR-001: Delete SSE Reconnection Test
- Remove lines 68-104 (the entire `test.fixme('SSE reconnection...')` block)
- Remove any imports that become unused after deletion (check if `page.route` for SSE
  patterns is referenced elsewhere)
- No unused imports should remain

#### FR-002: Add Cross-Browser Smoke Test Documentation
- File-level JSDoc must include: "These tests deliberately duplicate primary tests from
  chaos-degradation.spec.ts and chaos-cached-data.spec.ts. The duplication is intentional:
  Playwright's project config runs THIS file on Mobile Chrome and Mobile Safari, providing
  cross-browser validation that the primary single-browser tests do not cover."
- Each test must have a comment line: "// Cross-browser smoke test (primary: <filename>)"

#### FR-003: Replace beforeEach waitForTimeout
- Replace `await page.waitForTimeout(2000)` in `beforeEach` (line 23) with a DOM-ready
  assertion (e.g., wait for the search input to be visible)
- The search input is `page.getByPlaceholder(/search tickers/i)`

#### FR-004: Fix Cached Data Content Comparison
- After chaos injection, compare `textDuring` against `textBefore` to detect content
  replacement (not just "is something visible")
- Assert that `textDuring` contains at least one key substring from `textBefore` (e.g.,
  ticker name "AAPL")
- This prevents Green Dashboard Syndrome where error pages pass as "content"

#### FR-005: Replace Settle waitForTimeout
- Replace `await page.waitForTimeout(500)` (line 61) with a response-based wait or
  `expect.poll()` that detects when the route block has taken effect
- Acceptable alternatives: `page.waitForResponse()` that matches a 503, or
  `expect.poll(() => page.locator(...).textContent())` that detects no NEW content
  appeared

### Non-Functional Requirements

#### NFR-001: Test Count Change
- File should have exactly 2 tests after cleanup (down from 3)
- Both remaining tests must pass in CI

#### NFR-002: No New waitForTimeout
- Zero `waitForTimeout` calls in the file after changes (except the 500ms settle which
  may remain if no reliable response-based alternative exists -- document why if kept)

#### NFR-003: Import Cleanup
- No unused imports after SSE test removal

## Success Criteria

1. SSE `test.fixme()` block is completely removed (lines 68-104)
2. File has exactly 2 `test(...)` calls
3. File-level JSDoc explains cross-browser smoke test rationale
4. Each test has a "Cross-browser smoke test" comment referencing its primary test
5. `beforeEach` uses DOM-ready assertion instead of `waitForTimeout(2000)`
6. Cached data test compares `textDuring` to `textBefore` (not just truthy check)
7. No unused imports remain
8. Both tests pass locally with `npx playwright test chaos-cross-browser`

## Out of Scope

- Modifying `chaos-degradation.spec.ts` or `chaos-cached-data.spec.ts` (primary tests)
- Adding new cross-browser tests beyond the existing two
- SSE mock infrastructure (tracked in Feature 1280)
- Adopting `assertChaosLifecycle()` from Feature 1339 (that's a follow-up migration)

## Risk Assessment

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| Removing SSE test breaks something | Very Low | None | Test was `test.fixme()` -- never ran |
| Content comparison too strict | Low | Medium | Use substring check, not exact match |
| beforeEach DOM-ready wait too slow | Low | Low | Use generous timeout (5s) on search input |

---

## Appendix: Adversarial Review #1

### Ambiguity Check
- **FR-005 "response-based wait"**: What specific response should we wait for? The 503
  from `blockAllApi()`? Clarified: wait for the first 503 response after `blockAllApi()`
  is called, OR keep the 500ms settle with a comment explaining it's a brief settle for
  in-flight requests (matching the pattern in `chaos-cached-data.spec.ts`).

### Edge Cases
- The `textBefore` / `textDuring` comparison: what if the page has dynamic timestamps
  that change between captures? Mitigation: compare a structural indicator (e.g., "AAPL"
  ticker name presence) rather than full text equality.

### Contradiction Check
- NFR-002 says "zero waitForTimeout" but FR-005 allows keeping 500ms settle if documented.
  Resolution: FR-005 takes precedence -- the 500ms settle is acceptable ONLY if a comment
  explains why a response-based wait is insufficient (in-flight requests may have already
  been sent before the route was installed).

## Clarifications

**Q: Should the cached data test use `assertContentPersistence()` from Feature 1339?**
A: No. Feature 1339 adds shared helpers but explicitly states it does NOT modify existing
spec files (NFR-001 in 1339). Feature 1344 applies the FIX inline. A future feature can
migrate to the shared helper.

**Q: Is the 500ms settle in the cached data test acceptable?**
A: Yes, with documentation. The settle exists because `blockAllApi()` installs route
handlers, but React Query may have already dispatched in-flight requests before the routes
were installed. The 500ms wait allows those in-flight requests to complete. This matches
the pattern in `chaos-cached-data.spec.ts:56` which has the same settle with the same
comment.

**Q: What happens to the `test.fixme()` test ID (T043)?**
A: T043 is retired. If SSE testing is implemented in the future (Feature 1280), it will
get a new test ID.
