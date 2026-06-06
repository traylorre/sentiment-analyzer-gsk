# Feature 1340: Fix Green Dashboard Syndrome in chaos-scenarios.spec.ts

## Status: DRAFT

## Problem Statement

`chaos-scenarios.spec.ts` contains 6 tests (T016-T021) that validate customer outcomes
during 5 chaos injection types plus recovery. Multiple assertions are structurally weak:
they pass when the dashboard shows ANY content rather than verifying it shows the CORRECT
content. Freshness indicator checks are wrapped in `.catch(() => false)` making them
optional. The recovery test swallows errors and uses an OR condition that passes even when
no API response is received. All timing is `waitForTimeout`-based rather than
response-driven.

These tests could pass even if a bug replaced dashboard data with an error page, or if
the freshness indicator was completely broken, or if recovery never actually occurred.

## User Stories

### US-001: Content Identity Verification
**As a** chaos test author,
**I want** the ingestion failure and trigger failure tests to assert that `textDuring`
contains key fragments from `textBefore`,
**So that** a bug that replaces real data with an error page is detected.

### US-002: Mandatory Freshness Indicator Assertions
**As a** chaos test author,
**I want** freshness indicator assertions to be REQUIRED (not wrapped in catch),
**So that** a broken freshness indicator causes a test failure instead of being silently
skipped.

### US-003: Strict Recovery Verification
**As a** chaos test author,
**I want** the recovery test to REQUIRE a successful API 200 response (not pass when
response is null),
**So that** recovery is actually proven, not assumed.

### US-004: AND-Logic for API Timeout Outcomes
**As a** chaos test author,
**I want** the API timeout test to assert BOTH a health banner AND content presence
(not OR),
**So that** a blank screen with only a banner (or content with no banner) is caught.

### US-005: Response-Driven Waits
**As a** chaos test author,
**I want** `waitForTimeout` calls replaced with `waitForResponse` or
`expect(locator).toBeVisible({ timeout })` where possible,
**So that** tests are deterministic and faster.

### US-006: Page-Ready beforeEach
**As a** chaos test author,
**I want** `beforeEach` to wait for an actual page ready signal (e.g., main content
locator visible) instead of `waitForTimeout(3000)`,
**So that** tests don't have a 3s floor on every run.

## Requirements

### Functional Requirements

| ID | Requirement | Source |
|----|-------------|--------|
| FR-001 | T016/T019: `textDuring` must contain at least one 10+ char substring from `textBefore` | US-001 |
| FR-002 | T016/T019: Freshness indicator MUST be visible (remove `.catch(() => false)`) | US-002 |
| FR-003 | T021: `response` must not be null -- remove `.catch(() => null)` | US-003 |
| FR-004 | T021: Assert `response.ok()` directly (not `response === null \|\| response.ok()`) | US-003 |
| FR-005 | T020: Change `bannerVisible \|\| hasContent` to `bannerVisible && hasContent` | US-004 |
| FR-006 | T017: Replace 3x `waitForTimeout(1500)` with `waitForResponse` after each search fill | US-005 |
| FR-007 | T018: Remove `.catch()` on skeleton visibility -- require skeletons during cold start | US-005 |
| FR-008 | `beforeEach`: Replace `waitForTimeout(3000)` with `expect(page.locator('main')).toBeVisible({ timeout: 10000 })` | US-006 |

### Non-Functional Requirements

| ID | Requirement |
|----|-------------|
| NFR-001 | No new dependencies added |
| NFR-002 | All 6 tests must still pass against the current dashboard (no false negatives introduced) |
| NFR-003 | Use 1339 infrastructure helpers where applicable (captureContentSnapshot, assertContentPersistence) |

## Success Criteria

1. Freshness indicator tests FAIL if the `[data-testid="data-freshness-indicator"]` element is absent
2. Recovery test FAILS if no 200 response is received within timeout
3. API timeout test FAILS if banner is not visible (even if content is present)
4. Content comparison FAILS if `textDuring` does not contain fragments of `textBefore`
5. All `waitForTimeout` calls in search interactions replaced with response-based waits

## Edge Cases

| Case | Expected Behavior |
|------|-------------------|
| Dashboard loads very slowly (>5s) | beforeEach timeout (10s) catches this |
| Freshness indicator renders but with wrong state | Test catches wrong state via `expect(['stale', 'critical']).toContain(state)` |
| textBefore is very short (<20 chars) | Content comparison still works -- checks substring presence |
| Recovery response arrives before search fill completes | `waitForResponse` promise created before fill triggers it |
| Cold start skeletons render and resolve before assertion | Skeleton assertion uses 2s timeout -- if cold start is <2s, test may fail; this is acceptable because the test scenario injects a 3s delay |

## Out of Scope

- Refactoring test structure (test IDs, describe blocks)
- Changing chaos scenario configurations in chaos-helpers.ts
- Adding new test scenarios
- Modifying the dashboard application code

---

## Appendix A: Adversarial Review #1 (Spec)

### AR1-Q1: Could tightening freshness assertions cause false negatives?
**Risk**: The freshness indicator may not render in all environments (e.g., local dev
without feature flag).
**Mitigation**: The freshness indicator component is part of Feature 1266 which is
already merged. The test sends a mock sentiment response with `cache_status: 'stale'`
which explicitly triggers the indicator. If the indicator is broken, that IS a real bug
the test should catch.
**Verdict**: ACCEPT -- the assertion is correct.

### AR1-Q2: Is AND-logic for T020 (API timeout) too strict?
**Risk**: In some failure modes, the banner might not appear within the timeout if the
health tracker needs more than 3 failures. The test already sends 3 search interactions.
**Mitigation**: T017 (dynamodb_throttle) uses the same 3-interaction pattern and already
asserts the banner is visible with `{ timeout: 5000 }`. T020 should behave identically.
If the banner doesn't appear after 3 consecutive timeouts, that's a health tracker bug.
**Verdict**: ACCEPT -- AND is correct.

### AR1-Q3: Will removing `.catch(() => null)` from recovery test cause flakiness?
**Risk**: If the server doesn't have data for 'TSLA', the response might be a 404 not a 200.
**Mitigation**: The test uses `page.waitForResponse((r) => r.url().includes('/api/') && r.ok())` --
it waits for ANY ok API response, not specifically the TSLA search. After unblocking routes,
the dashboard's own background refetches will also produce ok responses. The 10s timeout
is generous.
**Verdict**: ACCEPT -- removing catch is safe.

### AR1-Q4: Content substring matching -- what if textBefore contains only generic text?
**Risk**: `textBefore` might be something like "Loading..." which would match error pages too.
**Mitigation**: The `beforeEach` now waits for main content to be visible, and
`textBefore` is captured AFTER initial data renders. The assertion also requires
`textBefore.length > 10`. If the dashboard legitimately shows "Loading..." for >3s
after page ready, that's a rendering bug worth catching.
**Verdict**: ACCEPT with note -- document that textBefore must be captured after data renders.

---

## Appendix B: Clarifications

### C1: What constitutes "content fragments" for FR-001?
Extract the first 20 characters of `textBefore` as a substring and assert `textDuring`
includes it. This avoids timestamp drift while catching wholesale content replacement.

### C2: Should FR-008 (page ready) use networkidle?
No. `networkidle` is deprecated in Playwright's best practices. Use
`expect(page.locator('main')).toBeVisible({ timeout: 10000 })` which waits for the
main content area to render without depending on network quiescence.

### C3: Does FR-006 require changing triggerHealthBanner()?
No. `triggerHealthBanner()` in chaos-helpers.ts already uses `waitForResponse` (see
line 240-246). FR-006 applies only to the inline search interactions in T017/T020 within
this spec file.
