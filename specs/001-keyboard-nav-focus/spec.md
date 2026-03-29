# Feature Specification: Fix Keyboard Navigation Test to Use .focus()

**Feature Branch**: `001-keyboard-nav-focus`
**Created**: 2026-03-29
**Status**: Draft
**Input**: User description: "Fix keyboard navigation test in chaos dashboard Playwright tests to use programmatic .focus() instead of simulated Tab key presses."

## User Scenarios & Testing _(mandatory)_

### User Story 1 - Reliable Keyboard Navigation Verification (Priority: P1)

As a developer running Playwright E2E tests, I want keyboard navigation tests to use programmatic `.focus()` calls instead of simulated Tab key presses so that focus order verification is reliable in headless Chromium and does not produce flaky failures.

**Why this priority**: Simulated Tab key presses are unreliable in headless browsers — the browser's focus management differs from interactive mode, causing tests to pass locally but fail in CI. This is the primary source of flakiness for keyboard accessibility tests.

**Independent Test**: Can be fully tested by running the keyboard navigation test suite in both headed and headless Chromium modes and verifying identical pass/fail results.

**Acceptance Scenarios**:

1. **Given** a keyboard navigation test targets a specific interactive element, **When** the test runs in headless Chromium, **Then** the element receives focus via `.focus()` and the test passes.
2. **Given** the chaos dashboard has multiple interactive elements in tab order, **When** tests verify focus is on the correct element, **Then** each test uses `.focus()` to place focus and `toBeFocused()` to assert, without relying on sequential Tab presses.
3. **Given** a test needs to verify that an element is keyboard-accessible, **When** the test focuses the element and simulates Enter/Space, **Then** the expected action occurs (e.g., button click, link navigation).

---

### User Story 2 - Focus Indicator Visibility Verification (Priority: P2)

As a developer, I want to verify that focused elements display visible focus indicators (outlines, rings) so that keyboard-only users can see where they are on the page.

**Why this priority**: Focus indicators are a WCAG 2.1 AA requirement. Verifying their presence ensures the dashboard is usable without a mouse.

**Independent Test**: Can be tested by focusing an element and asserting that the computed CSS includes a visible outline or box-shadow.

**Acceptance Scenarios**:

1. **Given** an interactive element (button, link, tab) receives focus, **When** inspected, **Then** the element has a visible focus indicator (outline, ring, or box-shadow with sufficient contrast).
2. **Given** a non-interactive element, **When** focus is attempted, **Then** the element does not receive focus (verifying correct tabindex absence).

---

### Edge Cases

- What happens when Alpine.js re-renders a view — does focus persist on the currently focused element or get lost?
- What happens when a modal opens — does focus trap inside the modal and return to the trigger when closed?
- What happens when `x-show` hides a view containing the focused element — is focus moved to a visible element?
- What happens when Chart.js canvas elements are in the tab order — are they skippable or do they trap focus?

## Requirements _(mandatory)_

### Functional Requirements

- **FR-001**: Keyboard navigation tests MUST use `.focus()` to programmatically set focus on target elements instead of simulating Tab key presses.
- **FR-002**: Focus assertions MUST use Playwright's built-in focus matchers (`toBeFocused()`) to verify which element has focus.
- **FR-003**: Tests MUST verify keyboard interaction (Enter, Space, Escape) on focused elements to confirm the elements respond to keyboard input.
- **FR-004**: Tests MUST verify that interactive elements (buttons, links, tabs, form controls) have visible focus indicators when focused.
- **FR-005**: Tests MUST verify that focus is not trapped by non-interactive elements (e.g., decorative containers, Chart.js canvases).
- **FR-006**: Tests MUST pass identically in both headed and headless Chromium modes — no behavioral difference allowed.
- **FR-007**: Tests MUST NOT use `page.keyboard.press('Tab')` for sequential navigation between elements. The ONLY permitted Tab usage is a single-Tab focus-order assertion: focus element A via `.focus()`, press Tab once, assert element B has focus. Chained Tab presses (2+) are banned.
- **FR-008**: Tests MUST verify that Alpine.js view transitions (via `x-show`) do not leave focus on a hidden element. After view change, focus MUST be on a visible element or the document body.
- **FR-009**: Tests MUST verify modal focus trap behavior: when a modal opens, focus MUST move into the modal; when it closes, focus MUST return to the trigger element.
- **FR-010**: Tests MUST verify that Chart.js canvas elements do not trap keyboard focus — either they have `tabindex="-1"` or focus passes through them to the next interactive element.

### Key Entities

- **Focusable Element**: Any interactive element in the chaos dashboard that should be reachable and operable via keyboard (buttons, links, tabs, form inputs, toggle switches).
- **Focus Indicator**: The visible CSS treatment (outline, ring, shadow) that shows which element currently has keyboard focus.

## Success Criteria _(mandatory)_

### Measurable Outcomes

- **SC-001**: Zero flaky keyboard navigation test failures over a 7-day CI window (all runs in that period must pass).
- **SC-002**: 100% of interactive elements in the chaos dashboard have verified keyboard accessibility (focusable + operable + visible indicator).
- **SC-003**: Keyboard navigation tests execute in under 10 seconds total (no slow Tab-stepping through the entire page).
- **SC-004**: Test results are identical between headed and headless Chromium execution modes.

## Assumptions

- The chaos dashboard uses DaisyUI components which include default focus styles (ring/outline) for most interactive elements.
- Playwright's `.focus()` method reliably sets focus in headless Chromium.
- Alpine.js `x-show` hides elements visually but keeps them in the DOM — hidden elements should not be focusable.
- The test targets the chaos dashboard's interactive elements: view tabs, safety control buttons, filter dropdowns, pagination controls, report list items.

## Scope Boundaries

**In scope**:
- Replacing Tab-based navigation with `.focus()` in keyboard nav tests
- Adding focus indicator visibility assertions
- Verifying keyboard operability (Enter/Space/Escape) for interactive elements
- Ensuring headless/headed parity

**Out of scope**:
- Adding new keyboard shortcuts to the dashboard
- Full WCAG 2.1 AA keyboard compliance static analysis (covered by axe-core in Feature 1271; this feature covers behavioral keyboard testing, which is complementary)
- Screen reader testing (requires separate tooling)
- Keyboard navigation for the customer-facing Amplify dashboard

## Adversarial Review #1

**Reviewed**: 2026-03-29

| Severity | Finding | Resolution |
|----------|---------|------------|
| CRITICAL | FR-007 self-contradicts — "Tab for assertion" loophole allows reintroducing flakiness | Rewrote FR-007: explicit single-Tab-only pattern, chained Tab (2+) banned |
| HIGH | SC-001 "10 consecutive runs" not statistically rigorous | Changed to 7-day CI window — larger sample, time-based |
| HIGH | 4 edge cases listed (lines 43-46) but no FRs cover them | Added FR-008 (view transition focus), FR-009 (modal focus trap), FR-010 (canvas focus trap) |
| MEDIUM | .focus() reliability on hidden elements unproven | Accepted — FR-008 addresses this by requiring focus on visible elements after view change |
| MEDIUM | Chart.js canvas focus behavior undefined | Added FR-010: explicit tabindex=-1 or pass-through requirement |
| MEDIUM | SC-003 10s timeout has no baseline | Accepted as reasonable budget — can be adjusted during implementation |
| MEDIUM | FR-004 focus indicator contrast requires WCAG tooling deferred to Feature 1271 | Accepted — FR-004 checks visibility, axe-core checks contrast |
| LOW | CSS computed style doesn't detect OS high-contrast mode | Out of scope — high-contrast mode testing is a separate concern |
| LOW | Alpine.js x-show behavior varies by version | Documented in assumptions |

**Gate**: 0 CRITICAL, 0 HIGH remaining. All resolved via spec edits.

## Clarifications

### Q1: What are the ~20 interactive elements across 6 dashboard views that need keyboard testing?
**Answer**: The 6 views come from Feature 1242's `currentView` state machine: "experiments", "reports", "detail", "diff", "trends", plus the base navigation/safety controls visible across all views. Interactive elements include: view tab buttons (5 tabs), safety control buttons (Andon cord, gate toggle from Feature 1245), filter dropdowns (scenario/verdict filters in reports view), pagination controls (cursor-based in reports list), report list items (clickable rows), diff selection checkboxes (2 report selection in diff view), Chart.js canvas elements (trends view), and standard link/button elements within each view. The exact count of ~20 is an estimate from the plan.md and will be finalized once Features 1242 and 1245 are implemented.
**Evidence**: Plan.md line 20: "~20 interactive elements across 6 dashboard views, 1 modal". Feature 1242 research.md enumerates 5 views. Feature 1245 adds gate toggle. Spec assumptions line 83: "view tabs, safety control buttons, filter dropdowns, pagination controls, report list items".

### Q2: Does this feature depend on Feature 1242 and/or 1245 being implemented first?
**Answer**: Yes. This feature tests keyboard navigation of the chaos dashboard, which is being built by Features 1242 (report viewer views) and 1245 (gate toggle). Without those features, there are no views or interactive elements to test. Feature 1271 (axe-core scoping) is a sibling dependency, not a blocker — the keyboard-nav tests can run independently of accessibility auditing. The dependency chain is: 1242 (create dashboard views) -> 1245 (add gate toggle) -> 001-keyboard-nav-focus (test keyboard navigation of both).
**Evidence**: Spec line 94: "Full WCAG 2.1 AA keyboard compliance audit (covered by axe-core in Feature 1271)" — confirms 1271 is separate. Plan.md line 111: "Chaos dashboard running at BASE_URL (same as smoke.spec.ts and api.spec.ts)" — requires the dashboard to be deployed.

### Q3: How should the single-Tab assertion pattern (FR-007) interact with modal focus traps (FR-009)?
**Answer**: FR-007 bans chained Tab presses (2+) for navigation but explicitly allows a single Tab press for focus-order assertion. FR-009 requires verifying modal focus trap behavior. These are compatible: the test should `.focus()` the first element inside the modal, press Tab once, and assert the next focused element is still inside the modal boundary (not escaped to an element outside). The research.md Decision 4 confirms this pattern: "Tabbing through all modal elements violates FR-007. Instead: focus the first modal element, Tab once, assert focus stayed inside the modal boundary." No contradiction exists.
**Evidence**: FR-007: "The ONLY permitted Tab usage is a single-Tab focus-order assertion". Research.md Decision 4 lines 33-34: "Tabbing through all modal elements — violates FR-007".

### Q4: How should focus indicators be detected given DaisyUI's variety of focus styles (ring, outline, box-shadow)?
**Answer**: FR-004 requires visible focus indicators, and the research.md Decision 3 specifies checking computed CSS properties: `outline`, `outlineWidth`, and `boxShadow`. The test helper `assertFocusIndicatorVisible(locator)` should evaluate `getComputedStyle()` on the focused element and assert that at least one of these properties has a non-default value (outline-width > 0, or box-shadow is not "none"). This is framework-agnostic and works for DaisyUI's `focus:ring`, `focus:outline`, and `focus-visible:ring` utilities. Contrast sufficiency is deferred to Feature 1271's axe-core audit.
**Evidence**: Research.md Decision 3: "DaisyUI applies focus styles via Tailwind CSS utilities (focus:ring, focus:outline, focus-visible:ring)". Plan.md line 79: `assertFocusIndicatorVisible(locator) — check computed CSS for visible outline/ring/shadow`.

### Q5: Where does keyboard-nav.spec.ts live and what existing infrastructure does it reuse?
**Answer**: The test lives at `e2e/playwright/tests/keyboard-nav.spec.ts` alongside existing `smoke.spec.ts` and `api.spec.ts`. The helper lives at `e2e/playwright/helpers/keyboard.ts` alongside existing `utils.ts`. It reuses the existing Playwright configuration from `playwright.config.ts` (Chromium only, BASE_URL from env, 60s per-test timeout, retry-on-CI). No new npm packages are needed — all APIs (`locator.focus()`, `toBeFocused()`, `evaluate()`) are built into `@playwright/test ^1.40.0`.
**Evidence**: Plan.md lines 54-58: project structure. Plan.md line 112: "No new npm packages required". Package.json shows `@playwright/test ^1.40.0` as existing dependency.
