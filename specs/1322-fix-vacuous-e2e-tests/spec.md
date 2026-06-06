# Feature Specification: Fix Vacuous E2E Tests

**Feature Branch**: `1322-fix-vacuous-e2e-tests`
**Created**: 2026-04-05
**Status**: Draft
**Input**: "Adversarial review of pipeline Playwright tests found 2 vacuous/near-vacuous passing tests in first-impression.spec.ts. A third candidate (chaos auth test) was confirmed legitimate. Fix the 2 vacuous tests so they assert real behavior."

## Context

The CI pipeline runs 104 Playwright E2E tests. Adversarial review identified 3 candidate vacuous tests. Investigation confirmed 2 are genuinely vacuous and 1 is legitimate:

1. **`should have working navigation tabs`** (line 21): Branches on `isMobile` via `window.innerWidth < 768`. Desktop Chrome CI runs at 1280px, so `isMobile` is always `false`. All assertions live inside the `if (isMobile)` block. The test body executes zero assertions on desktop -- it passes vacuously.

2. **`should respect reduced motion preference`** (line 65): Asserts `typeof hasReducedMotion === 'boolean'`. Since `window.matchMedia().matches` always returns a boolean, this assertion is a tautology. The test never verifies that reduced motion actually changes behavior.

3. **`should require authentication`** (chaos.spec.ts line 313): Asserts `resp.status() === 401` on an unauthenticated chaos API call. This is a substantive assertion that would fail if auth were broken. **Legitimate -- no change needed.**

## User Scenarios & Testing _(mandatory)_

### User Story 1 - Navigation Tabs Test Asserts Real Desktop Behavior (Priority: P1)

When the navigation tabs test runs on Desktop Chrome (the CI project), it should assert real behavior about the desktop navigation rather than silently skipping all assertions because the viewport is not mobile.

**Why this priority**: A vacuous test is worse than no test -- it creates false confidence that navigation works when nothing was actually checked.

**Independent Test**: Remove the desktop assertions added by this fix. The test must fail, proving it was not vacuous.

**Acceptance Scenarios**:

1. **Given** the test runs on Desktop Chrome (1280px viewport), **When** the `isMobile` check evaluates to `false`, **Then** the `else` block executes assertions about desktop navigation elements (tab count, tab names).
2. **Given** the desktop navigation tabs exist, **When** the test runs, **Then** it asserts the correct number of navigation links and their names (Dashboard, Configs, Alerts, Settings).
3. **Given** the mobile tablist is hidden on desktop (already verified by "should show desktop layout on large screens"), **When** this test runs on desktop, **Then** it focuses on navigation functionality (element existence, correct names) not layout visibility (which the other test covers).

---

### User Story 2 - Reduced Motion Test Verifies Actual CSS Behavior (Priority: P1)

When the reduced motion test runs, it should verify that CSS animations and transitions are actually disabled under `prefers-reduced-motion: reduce`, not merely confirm that `matchMedia` returns a boolean.

**Why this priority**: The existing test is a tautology. `typeof boolean === 'boolean'` is always `true`. This creates false confidence that the accessibility feature works.

**Independent Test**: Remove the CSS assertions. The test must fail, proving it was not vacuous.

**Acceptance Scenarios**:

1. **Given** Playwright's `page.emulateMedia({ reducedMotion: 'reduce' })` is called, **When** the page renders, **Then** `animation-duration` on a page element is `0.01ms` (matching the global CSS rule in `globals.css` lines 94-101).
2. **Given** Playwright's `page.emulateMedia({ reducedMotion: 'reduce' })` is called, **When** the page renders, **Then** `transition-duration` on a page element is `0.01ms`.
3. **Given** the reduced motion media query is NOT emulated (default), **When** the page renders, **Then** `animation-duration` and `transition-duration` are NOT `0.01ms` (confirming the media query actually changes behavior).

---

### User Story 3 - Chaos Auth Test Confirmed Legitimate (Priority: N/A)

The `should require authentication` test in chaos.spec.ts asserts `resp.status() === 401` on an unauthenticated API call. This is a substantive, non-vacuous assertion.

**Decision**: No change. Documented here to record that the test was reviewed and confirmed legitimate.

---

### Edge Cases

- **Desktop nav structure changes**: If navigation tabs are renamed or removed, the test should fail (good -- it catches regressions). The tab names are hardcoded in the test assertions to match the current UI.
- **No animated elements on page**: The reduced motion test checks `animation-duration` on any element via the global `*` selector in `globals.css`. Even if no element has an explicit animation, the computed style reflects the `0.01ms !important` override. The `body` element is a safe target since the CSS rule applies to `*`.
- **Tailwind CSS purges reduced motion styles**: Unlikely since the rule is in `globals.css` (not utility classes), but if it happened, the reduced motion test would fail -- which is correct behavior (it would reveal a real regression).

## Requirements _(mandatory)_

### Functional Requirements

- **R1**: MUST add an `else` block to the navigation tabs test that asserts desktop navigation elements exist with correct names (Dashboard, Configs, Alerts, Settings) when `isMobile` is `false`.
- **R2**: MUST replace the reduced motion test's tautological `typeof` assertion with: (a) `page.emulateMedia({ reducedMotion: 'reduce' })`, (b) assertion that `animation-duration` computed style is `0.01ms`, (c) assertion that `transition-duration` computed style is `0.01ms`.
- **R3**: MUST NOT modify the chaos auth test (`chaos.spec.ts` line 313). Document the decision that it is legitimate.

### Non-Functional Requirements

- **NR1**: Both fixed tests must still pass in CI (Desktop Chrome, 1280px viewport).
- **NR2**: Test execution time must not increase by more than 2 seconds per test.

## Success Criteria _(mandatory)_

### Measurable Outcomes

- **SC-001**: Navigation tabs test executes at least 2 assertions on Desktop Chrome (currently executes 0).
- **SC-002**: Reduced motion test verifies actual CSS property values, not `typeof` checks.
- **SC-003**: Both tests fail if their new assertions are removed (proving non-vacuousness).
- **SC-004**: Chaos auth test remains unchanged. `git diff` shows no modifications to `chaos.spec.ts`.

## Scope Boundaries

**In scope**: Fix 2 vacuous tests in `first-impression.spec.ts`, document chaos auth test decision
**Out of scope**: Fixing other failing tests, adding new E2E tests, modifying chaos.spec.ts, refactoring test infrastructure

## Adversarial Review #1

**Reviewed**: 2026-04-05

| Severity | Finding | Resolution |
|----------|---------|------------|
| MEDIUM | The reduced motion test depends on finding an animated element. If no animated element exists on the page, the test needs a fallback assertion. | The CSS rule in `globals.css` lines 94-101 applies to `*, *::before, *::after` with `!important`. This means `animation-duration` and `transition-duration` are overridden on ALL elements when reduced motion is active. Checking `document.body` or any container element is sufficient -- no specific "animated element" is needed. The computed style will reflect `0.01ms` regardless. |
| MEDIUM | Desktop nav assertions may duplicate the "should show desktop layout" test (line 94), creating maintenance burden if nav structure changes. | Intentional separation of concerns. The "desktop layout" test asserts VISIBILITY (mobile nav hidden). The navigation tabs test asserts FUNCTIONALITY (correct tab count, correct names). These are orthogonal properties. If nav structure changes, both tests should be updated -- they verify different things. |
| LOW | Hardcoded tab names (Dashboard, Configs, Alerts, Settings) create brittleness. | Accepted. Hardcoded names are intentional -- they verify the exact navigation items users see. If names change, the test should fail and be updated. A regex-based approach would weaken the assertion. |

**Gate**: 0 CRITICAL, 0 HIGH remaining.

## Clarifications

All self-answered based on codebase investigation:

1. **Q: What CSS properties does the reduced motion media query override?** A: `globals.css` lines 94-101 set `animation-duration: 0.01ms !important`, `animation-iteration-count: 1 !important`, and `transition-duration: 0.01ms !important` on `*, *::before, *::after`.

2. **Q: What viewport does CI use for Desktop Chrome?** A: The default Playwright Desktop Chrome project uses 1280x720. This means `window.innerWidth < 768` is always `false` in CI.

3. **Q: Are there desktop navigation elements to assert against?** A: Yes. The "should show desktop layout on large screens" test (line 94) confirms `mobileNav` with role `tablist` is hidden on desktop. The desktop layout uses a sidebar with navigation links. The navigation tabs test should assert against these sidebar navigation elements.

4. **Q: Does `page.emulateMedia({ reducedMotion: 'reduce' })` work in Playwright?** A: Yes. Playwright supports `page.emulateMedia()` for `reducedMotion` with values `'reduce'` or `'no-preference'`. This is the standard approach for testing accessibility media queries.

5. **Q: Why `0.01ms` instead of `0s`?** A: The CSS in `globals.css` uses `0.01ms` (not `0s`). This is a common pattern -- `0s` can cause `transitionend` events to never fire, which can break JS that listens for them. `0.01ms` is effectively instant but still fires events.
