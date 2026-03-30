# Feature Specification: Accessibility Timing Audit

**Feature Branch**: `1272-a11y-timing-audit`
**Created**: 2026-03-28
**Status**: Draft
**Input**: User description: "Fix ARIA attribute assertion race conditions and waitForTimeout anti-patterns in 4 Playwright test files that share the same timing bug discovered in Feature 1270."

## User Scenarios & Testing *(mandatory)*

### User Story 1 - ARIA Attribute Assertions Pass Deterministically (Priority: P1)

A developer pushes a PR that touches frontend code. The CI pipeline runs the full Playwright E2E suite. Tests that assert ARIA attributes (aria-live, aria-pressed) immediately after a visibility check pass on the first attempt without relying on CI retries. Currently, these assertions race against the browser's accessibility tree stabilization -- the element is visible in the DOM but its ARIA attributes have not yet been computed, causing intermittent failures.

**Why this priority**: These race conditions cause CI flake. Every flaky test erodes trust in the pipeline and wastes developer time re-running checks.

**Independent Test**: Run each affected test file with `--retries=0` and confirm all ARIA attribute assertions pass on the first attempt.

**Acceptance Scenarios**:

1. **Given** the health banner is visible after 3 API failures in `chaos-degradation.spec.ts`, **When** the test asserts `aria-live="assertive"`, **Then** the assertion uses a timeout so it waits for the accessibility tree to stabilize rather than checking synchronously.
2. **Given** the health banner is visible in `error-visibility-banner.spec.ts`, **When** the test asserts `aria-live="assertive"`, **Then** the assertion uses a timeout to avoid racing the accessibility tree.
3. **Given** the health banner is visible in `chaos-cross-browser.spec.ts`, **When** the test asserts `aria-live="assertive"`, **Then** the assertion uses a timeout to avoid racing the accessibility tree.
4. **Given** chart toggle buttons are visible in `sanity.spec.ts`, **When** the test asserts `aria-pressed` attributes (both existence and value), **Then** each assertion that immediately follows a visibility check uses a timeout.

---

### User Story 2 - Blind Waits Replaced with Event-Based Waiting (Priority: P1)

A developer reads any of the 4 affected files and sees zero `waitForTimeout()` calls. Instead, the tests use event-based waiting mechanisms (waitForResponse, waitForLoadState, expect with timeout, expect.poll). This makes tests faster on fast machines (no unnecessary delays) and more reliable on slow CI runners (waits adapt to actual timing).

**Why this priority**: Blind waits are the root cause of both false-pass and false-fail outcomes. They paper over timing issues rather than solving them. Replacing them in the files being modified prevents the timing fixes from User Story 1 from being undermined by adjacent blind waits in the same tests.

**Independent Test**: Search each modified file for `waitForTimeout` and confirm zero instances remain. Run the tests and confirm they still pass.

**Acceptance Scenarios**:

1. **Given** `chaos-degradation.spec.ts` currently has 7 `waitForTimeout()` calls, **When** the audit is complete, **Then** all 7 are replaced with event-based waits and no `waitForTimeout` calls remain.
2. **Given** `error-visibility-banner.spec.ts` currently has 19 `waitForTimeout()` calls, **When** the audit is complete, **Then** all 19 are replaced with event-based waits and no `waitForTimeout` calls remain.
3. **Given** `chaos-cross-browser.spec.ts` currently has 3 `waitForTimeout()` calls, **When** the audit is complete, **Then** all 3 are replaced with event-based waits and no `waitForTimeout` calls remain.
4. **Given** `chaos-accessibility.spec.ts` currently has 3 `waitForTimeout()` calls (in beforeEach and individual tests), **When** the audit is complete, **Then** all 3 are replaced with event-based waits and no `waitForTimeout` calls remain.
5. **Given** `sanity.spec.ts` currently has 0 `waitForTimeout()` calls, **When** the audit is complete, **Then** the file remains free of `waitForTimeout` calls (no regression).

---

### User Story 3 - Shared Helper waitForTimeout Calls Also Fixed (Priority: P2)

The `triggerHealthBanner()` helper in `chaos-helpers.ts` is called by 3 of the 4 affected files. It contains 3 `waitForTimeout(1500)` calls between search interactions to accumulate API failures. These blind waits must also be replaced with event-based alternatives to fully eliminate the anti-pattern from the affected test flows.

**Why this priority**: If the shared helper retains blind waits, the files that call it still execute blind waits indirectly. The fix would be cosmetic rather than substantive.

**Independent Test**: Search `chaos-helpers.ts` for `waitForTimeout`. Confirm zero instances remain. Run all tests that call `triggerHealthBanner()` and confirm they still pass.

**Acceptance Scenarios**:

1. **Given** `triggerHealthBanner()` in `chaos-helpers.ts` has 3 `waitForTimeout(1500)` calls, **When** the audit is complete, **Then** all 3 are replaced with event-based waits (e.g., `waitForResponse` on the API call triggered by each search).
2. **Given** other test files also call `triggerHealthBanner()`, **When** the helper is modified, **Then** all callers continue to pass (no regression).

---

### Edge Cases

- What happens when the accessibility tree takes longer than 3000ms to stabilize? The timeout is sufficient for all tested browsers in both local and CI environments. If a test fails, the timeout can be increased per-assertion.
- What happens if a `waitForTimeout` is genuinely needed (e.g., waiting for an SSE reconnection interval with no observable event)? Document the justification inline with a comment explaining why event-based waiting is not possible.
- What happens if replacing `waitForTimeout` in a beforeEach block affects unrelated tests in the same describe block? Each test must be verified independently after the change.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: All `toHaveAttribute('aria-live', ...)` assertions that follow a `toBeVisible()` check MUST include a `{ timeout: 3000 }` option in `chaos-degradation.spec.ts`, `error-visibility-banner.spec.ts`, and `chaos-cross-browser.spec.ts`.
- **FR-002**: All `toHaveAttribute('aria-pressed', ...)` assertions that follow a `toBeVisible()` check (without an intervening click or user action) MUST include a `{ timeout: 3000 }` option in `sanity.spec.ts`.
- **FR-003**: All `toHaveAttribute('aria-pressed')` existence-only checks (no value assertion) MUST include a `{ timeout: 3000 }` option in `sanity.spec.ts`.
- **FR-004**: All `waitForTimeout()` calls in `chaos-degradation.spec.ts` (7 instances) MUST be replaced with event-based waiting mechanisms.
- **FR-005**: All `waitForTimeout()` calls in `error-visibility-banner.spec.ts` (19 instances) MUST be replaced with event-based waiting mechanisms.
- **FR-006**: All `waitForTimeout()` calls in `chaos-cross-browser.spec.ts` (3 instances) MUST be replaced with event-based waiting mechanisms.
- **FR-007**: All `waitForTimeout()` calls in `chaos-accessibility.spec.ts` (3 instances) MUST be replaced with event-based waiting mechanisms.
- **FR-008**: `waitForTimeout` replacements MUST use appropriate Playwright primitives: `waitForResponse()` for waiting on API calls, `waitForLoadState('networkidle')` for page load settling, `expect(locator).toBeVisible({ timeout })` for element appearance, or `expect.poll()` for custom conditions.
- **FR-009**: The `triggerHealthBanner()` helper in `chaos-helpers.ts` contains 3 `waitForTimeout(1500)` calls between search interactions. The helper MUST be audited and its blind waits replaced with event-based alternatives.
- **FR-010**: No `waitForTimeout()` calls may remain in any of the modified files after the fix is complete.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: All affected test files contain zero `waitForTimeout()` calls after the fix (chaos-degradation, error-visibility-banner, chaos-cross-browser, chaos-accessibility, plus the triggerHealthBanner helper).
- **SC-002**: All ARIA attribute assertions that follow visibility checks include explicit timeouts (3000ms).
- **SC-003**: All affected test files pass with `--retries=0` on the first attempt across all configured Playwright projects.
- **SC-004**: No test execution time regression exceeding 20% compared to the current blind-wait baseline (event-based waits should be equal or faster on average).

## Assumptions

- The `waitForAccessibilityTree()` helper from Feature 1270 will be available in `frontend/tests/e2e/helpers/a11y-helpers.ts` when this feature is implemented.
- The `triggerHealthBanner()` helper in `chaos-helpers.ts` is a shared dependency; changes to it must not break other test files that call it.
- A timeout of 3000ms is sufficient for accessibility tree stabilization across Chrome, Firefox, and WebKit in both local and CI environments.
- `sanity.spec.ts` ARIA assertions after click() actions (e.g., lines 178, 187) do NOT need the timeout fix because the click itself triggers a synchronous state change; the race condition only exists between visibility and initial attribute computation.
- `chaos-accessibility.spec.ts` is included in scope because its `waitForTimeout` calls were not addressed by Feature 1270 (which focused on the axe-core race, not the blind waits).

## Dependencies

- **Feature 1270** (`a11y-race-fix`): Provides the `waitForAccessibilityTree()` helper and establishes the pattern.

## Scope Boundaries

### In Scope

- The 4 files named in the feature description plus `chaos-accessibility.spec.ts` (5 files total)
- The `triggerHealthBanner()` helper in `chaos-helpers.ts` (shared dependency of multiple affected files)
- ARIA assertion timeout fixes
- `waitForTimeout` replacement with event-based waiting

### Out of Scope

- The remaining ~97 `waitForTimeout` instances across the other ~17 test files in the E2E suite
- Adding new tests or new accessibility assertions
- Modifying React components or application code
- Changing Playwright configuration (retry count, timeouts, etc.)
- Auditing the `clean-state.ts` helper's `waitForTimeout` calls

## Risk Assessment

| Risk | Impact | Mitigation |
|------|--------|------------|
| Replacing waitForTimeout in triggerHealthBanner() breaks other callers | HIGH -- could break 3+ other test files | Run full E2E suite after changing the shared helper |
| Event-based waits are slower than blind waits on CI | LOW -- unlikely, but possible for some patterns | Measure before/after execution time; SC-004 gates this |
| 3000ms timeout too short for WebKit on slow CI runners | MEDIUM -- would cause consistent failure on one browser | Monitor CI results; increase timeout per-assertion if needed |
| waitForTimeout(5000) in SSE reconnection test has no event-based alternative | MEDIUM -- SSE reconnection is inherently timer-based | Use expect.poll on request count as event-based proxy |

## Clarifications

### Session 2026-03-28

No critical ambiguities detected. All taxonomy categories assessed as Clear:
- Functional scope fully bounded (5 files + 1 helper, explicit out-of-scope)
- No data model (test infrastructure only)
- Edge cases covered in spec and AR#1
- Success criteria measurable (SC-001 through SC-004)
- Terminology consistent throughout
- Feature 1270 dependency and shared helper regression risk documented

---

## Adversarial Review #1 (AR#1)

**Reviewer**: Adversarial self-review
**Date**: 2026-03-28

### Findings

**AR1-F1 (MEDIUM): Scope creep from 4 files to 6 files**

The user specified 4 affected files. The spec expanded scope to include `chaos-accessibility.spec.ts` (5th file) and `chaos-helpers.ts` (6th file). Both additions are justified:
- `chaos-accessibility.spec.ts` has `waitForTimeout` calls that were not fixed by Feature 1270
- `chaos-helpers.ts::triggerHealthBanner()` is called by 3 of the 4 affected files

However, `chaos-error-boundary.spec.ts` also calls `triggerHealthBanner()` and is NOT in scope. If `triggerHealthBanner()` changes behavior, this 6th consumer could break.

**Resolution**: Add `chaos-error-boundary.spec.ts` to the regression testing list (not to modification scope). FR-009 already covers the helper; the risk table already covers the regression scenario. No spec change needed -- the mitigation (run full E2E suite) covers this.

**AR1-F2 (LOW): Assumption about click() not needing timeout may be wrong**

The spec assumes ARIA assertions after `click()` (e.g., `aria-pressed` changing from `true` to `false`) do not need timeouts because the click triggers a synchronous state change. However, in React, state updates and re-renders are asynchronous -- a `click()` triggers `setState()` which triggers a re-render which updates the `aria-pressed` attribute. This is NOT synchronous.

**Resolution**: Playwright's `toHaveAttribute` with an expected value already auto-retries by default (5s default timeout). The issue in the spec only exists for assertions WITHOUT a value (lines 790, 805-806 in sanity.spec.ts) where `toHaveAttribute('aria-pressed')` checks existence, not value. The value-based assertions already have implicit retry. No spec change needed -- FR-002 and FR-003 correctly scope to the dangerous patterns.

**AR1-F3 (LOW): The `beforeEach` waitForTimeout(2000) serves React hydration, not a11y**

Several files use `waitForTimeout(2000)` in `beforeEach` after `page.goto('/')`. This wait is for React/Next.js hydration, NOT for accessibility tree settling. The replacement must use `waitForLoadState('networkidle')` or similar, NOT `waitForAccessibilityTree()`. The spec correctly does NOT mandate using the a11y helper for these cases (FR-008 lists multiple appropriate primitives).

**Resolution**: No spec change needed. FR-008 already specifies the correct replacement primitives.

**AR1-F4 (MEDIUM): 19 waitForTimeout instances in error-visibility-banner.spec.ts is the largest batch**

This file has the most instances (19). Many follow the same pattern: `searchInput.fill('X') -> waitForTimeout(1500)` repeated 3 times per test, across 5 tests. The replacement pattern must be consistent and correct: wait for the API response (or the route handler fulfillment) triggered by the search, not for an arbitrary duration.

**Resolution**: During planning, this file should be decomposed into its repeating patterns. The 19 instances likely reduce to 2-3 distinct replacement patterns applied repeatedly. No spec change needed.

**AR1-F5 (LOW): SC-004 (20% time regression) is unmeasurable in practice**

Measuring per-file test execution time with 20% precision is noisy -- CI runners have variable performance. This criterion is aspirational rather than strictly measurable.

**Resolution**: Accept as-is. The intent is correct (don't make tests slower), even if the exact 20% threshold is impractical to enforce.

### Summary

| ID | Severity | Status |
|----|----------|--------|
| AR1-F1 | MEDIUM | Accepted -- mitigation adequate |
| AR1-F2 | LOW | Accepted -- existing Playwright retry handles it |
| AR1-F3 | LOW | Accepted -- FR-008 covers this |
| AR1-F4 | MEDIUM | Accepted -- defer to planning phase |
| AR1-F5 | LOW | Accepted -- aspirational but directionally correct |

**Verdict**: PASS -- 0 CRITICAL, 0 HIGH findings. Spec is ready for planning.
