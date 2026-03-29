# Feature Specification: Scope axe-core to Error Boundary Element

**Feature Branch**: `1271-axe-scope-error-boundary`
**Created**: 2026-03-29
**Status**: Draft
**Input**: User description: "Scope axe-core accessibility tests to error boundary element in chaos dashboard Playwright tests, not full page. Avoids false positives from third-party CDN elements."

## User Scenarios & Testing _(mandatory)_

### User Story 1 - Scoped Accessibility Audit on Dashboard Content (Priority: P1)

As a developer running the chaos dashboard Playwright test suite, I want accessibility checks to scan only the main content container of the chaos dashboard so that violations from third-party CDN-loaded libraries (Tailwind JIT, DaisyUI, Chart.js, Alpine.js) do not produce false positives that obscure real issues in our code.

**Why this priority**: False positives erode trust in the test suite. If developers learn to ignore accessibility failures because "it's just a CDN thing," they will also ignore real violations. Scoping to our content eliminates noise and makes every violation actionable.

**Independent Test**: Can be fully tested by running the accessibility test against the chaos dashboard and verifying that (a) violations are reported only for elements within the main content container, and (b) known CDN-injected elements (e.g., Tailwind JIT `<style>` tags) do not appear in the violation list.

**Acceptance Scenarios**:

1. **Given** the chaos dashboard is loaded, **When** the accessibility audit runs, **Then** only elements within the main content container are scanned.
2. **Given** the chaos dashboard has a known accessibility violation in the report list view, **When** the audit runs, **Then** the violation is detected and reported with element path.
3. **Given** CDN-loaded libraries inject elements outside the main content container, **When** the audit runs, **Then** those elements are excluded from the scan.

---

### User Story 2 - Per-View Accessibility Audit (Priority: P2)

As a developer, I want the option to run accessibility checks against a specific visible view (e.g., reports list, experiment detail, diff view) so that I can isolate violations to the view I'm working on.

**Why this priority**: The chaos dashboard uses Alpine.js `x-show` to toggle views — all views remain in the DOM. Scanning only the active/visible view prevents false positives from hidden views whose ARIA states may be incomplete when not displayed.

**Independent Test**: Can be tested by navigating to a specific view, running the scoped audit, and confirming only that view's elements appear in the results.

**Acceptance Scenarios**:

1. **Given** the reports list view is active, **When** a view-scoped audit runs, **Then** only elements within the reports list section are scanned.
2. **Given** the experiments view is active and the reports view is hidden via `x-show`, **When** a view-scoped audit runs, **Then** hidden report view elements are excluded.

---

### Edge Cases

- What happens when the dashboard is in a loading state (skeleton/spinner) — are loading indicators accessible?
- What happens when the dashboard has no data (empty state) — does the empty state container meet accessibility standards?
- What happens when a modal (e.g., Andon cord confirmation) is open — is the modal scanned as part of the main content or separately?
- What happens when Chart.js canvases are rendered — do they have appropriate alternative text or ARIA labels?

## Requirements _(mandatory)_

### Functional Requirements

- **FR-001**: Accessibility audits MUST scan only the main content container element, excluding the navigation bar and any CDN-injected elements outside the container.
- **FR-002**: The main content container MUST be identifiable by a stable selector (a `data-testid` attribute or semantic landmark role) that does not depend on utility CSS class names.
- **FR-003**: Accessibility violations MUST be reported with the element selector path relative to the scoped container, enabling developers to locate the issue.
- **FR-004**: The test suite MUST support an optional per-view scoping mode that targets only the currently visible view section.
- **FR-005**: The accessibility audit MUST fail the test suite when any violation of severity "critical" or "serious" is found within the scoped area.
- **FR-006**: Violations of severity "moderate" or "minor" MUST be logged as warnings but MUST NOT fail the test suite.
- **FR-007**: The dashboard HTML MUST include a `data-testid="chaos-dashboard-content"` attribute on the main content container to serve as the stable scope anchor.
- **FR-008**: The test MUST wait for dynamic content (Alpine.js state transitions, Chart.js rendering) to settle before running the audit. Readiness MUST be verified by asserting a minimum number of rendered child elements within the scope container (at least 1 interactive element visible) to prevent false-green results from failed hydration.
- **FR-009**: The accessibility audit MUST also scan modal dialogs (e.g., Andon cord confirmation) that are rendered as siblings or portals outside the main content container. Modals MUST be scanned when visible, using a separate scope selector targeting modal elements.
- **FR-010**: The `@axe-core/playwright` dependency MUST be pinned to a specific major.minor version to prevent upstream rule reclassifications from breaking CI without warning. Version upgrades MUST be deliberate and reviewed.
- **FR-011**: The axe-core audit MUST be configured to run only WCAG 2.1 AA rules (via `runOnly` tags), not the full rule set, to ensure consistent behavior aligned with the stated conformance target.

### Key Entities

- **Scope Container**: The main content area of the chaos dashboard that wraps all interactive views. Identified by `data-testid="chaos-dashboard-content"`. Excludes navigation, CDN style injections, and script elements.
- **Violation**: An accessibility issue found within the scope container, with severity (critical, serious, moderate, minor), element path, and WCAG rule reference.

## Success Criteria _(mandatory)_

### Measurable Outcomes

- **SC-001**: 100% of reported accessibility violations originate from elements within the scoped content container — zero false positives from CDN or navigation elements.
- **SC-002**: The accessibility audit adds less than 5 seconds to the total test suite execution time.
- **SC-003**: Developers can identify and locate any reported violation within 30 seconds using the element path in the report.
- **SC-004**: The test suite correctly detects at least 3 categories of WCAG 2.1 AA violations (e.g., missing alt text, insufficient color contrast, missing form labels) when intentionally introduced.

## Assumptions

- The chaos dashboard is served from `src/dashboard/chaos.html` and uses Alpine.js for state management with `x-show` for view toggling.
- The main content container is currently `<div class="container mx-auto p-4 max-w-7xl">` at approximately line 60 of chaos.html. A `data-testid` attribute will be added.
- Third-party CDN resources (Tailwind JIT, DaisyUI CSS, Chart.js, Alpine.js) may inject `<style>`, `<script>`, or `<canvas>` elements that are outside our control.
- WCAG 2.1 AA is the target conformance level (industry standard for web applications).
- The Playwright test environment runs Chromium only (per existing config).

## Scope Boundaries

**In scope**:
- Adding `@axe-core/playwright` as a test dependency
- Adding `data-testid` attribute to the chaos dashboard main content container
- Creating scoped accessibility test(s) in the Playwright suite
- Configuring severity-based pass/fail thresholds

**Out of scope**:
- Fixing existing accessibility violations in the dashboard (separate effort)
- Accessibility testing of the customer-facing Amplify/Next.js dashboard (different app)
- Multi-browser accessibility testing (Chromium only for now)
- Accessibility testing of the navigation bar (can be added later)

## Adversarial Review #1

**Reviewed**: 2026-03-29

| Severity | Finding | Resolution |
|----------|---------|------------|
| CRITICAL | False-green when Alpine.js hydration fails — zero violations pass CI on broken dashboard | Added FR-008 readiness gate: minimum rendered child element count before audit runs |
| HIGH | Modal/portal elements render outside scope container — invisible to audit | Added FR-009: modals scanned separately when visible using dedicated modal selector |
| HIGH | Unpinned axe-core allows upstream rule reclassification to break CI | Added FR-010: version pinned to major.minor, upgrades require review |
| MEDIUM | WCAG 2.1 AA stated as target but no `runOnly` configuration — runs ALL rules | Added FR-011: explicit WCAG 2.1 AA tag configuration via `runOnly` |
| MEDIUM | SC-001 "zero false positives" untestable without synthetic injection test | Accepted as MEDIUM risk — implementation should include a boundary test |
| MEDIUM | Line 60 reference fragile, duplicate data-testid unhandled | data-testid is the real anchor (line ref removed from assumptions is informational only) |
| LOW | Alpine.js `x-if` vs `x-show` assumption | Documented: spec assumes `x-show` as currently implemented |
| LOW | Unpinned @axe-core/playwright supply chain risk | Covered by FR-010 version pinning |

**Gate**: 0 CRITICAL, 0 HIGH remaining. All resolved via spec edits.

## Clarifications

### Q1: Does chaos.html exist yet, or is it being created by Feature 1242?
**Answer**: chaos.html does NOT yet exist in this template repo (`src/dashboard/` directory does not exist). It is specified for creation by Feature 1242 (chaos-report-viewer), which adds ~550 lines of Alpine.js state, views, and Chart.js integration to `src/dashboard/chaos.html`. Feature 1271 depends on 1242 being implemented first, since the `data-testid="chaos-dashboard-content"` attribute must be added to a container that 1242 creates.
**Evidence**: `Glob('src/dashboard/**')` returns no files. Spec 1242 plan.md line 37: `chaos.html # MODIFY: Add ~550 lines`. The 1242 tasks.md references `src/dashboard/chaos.html` as the target file for all tasks.

### Q2: What are the exact dashboard views that need per-view scoping (FR-004)?
**Answer**: The chaos dashboard has 5 views managed by Alpine.js `currentView` state: "experiments" (default), "reports", "detail", "diff", and "trends". These are toggled via `x-show` directives, meaning all views remain in the DOM simultaneously. Per-view scoping should target only the currently visible view section.
**Evidence**: Feature 1242 research.md line 15: `currentView: 'experiments', // experiments | reports | detail | diff | trends`.

### Q3: Does `@axe-core/playwright` already exist as a dependency, or must it be added?
**Answer**: It must be added. The current `e2e/playwright/package.json` has only three devDependencies: `@playwright/test ^1.40.0`, `@types/node ^20.10.0`, and `typescript ^5.3.0`. No axe-core package is present. The CLAUDE.md active technologies section for 1265-chaos-playwright-e2e lists `@axe-core/playwright` as a new dependency, confirming it was planned but not yet added.
**Evidence**: `e2e/playwright/package.json` lines 14-18 show only 3 devDependencies. CLAUDE.md: `@axe-core/playwright (new dependency for accessibility audits)`.

### Q4: What modal element specifically needs scanning per FR-009 (Andon cord confirmation)?
**Answer**: The Andon cord confirmation modal is defined in Feature 1245 (gate-toggle). It uses a DaisyUI `<dialog>` element opened via `showModal()`, triggered by Alpine.js `x-on:click`. The modal shows a confirmation prompt: "Arm chaos gate? Experiments will inject real faults." The correct scope selector for FR-009 is `[role="dialog"]` or `dialog[open]`, which will catch the native `<dialog>` element when visible. Feature 1245 may or may not be implemented before 1271, so the modal scanning should be conditional on dialog visibility.
**Evidence**: Spec 1245-gate-toggle spec.md line 21: confirmation dialog on arm. Keyboard-nav-focus research.md lines 29-30: DaisyUI `<dialog>` with `showModal()`.

### Q5: Where should the new test file (`accessibility.spec.ts`) and helper (`accessibility.ts`) live relative to existing Playwright structure?
**Answer**: They should be placed in the existing Playwright directory structure: `e2e/playwright/tests/accessibility.spec.ts` alongside existing `smoke.spec.ts` and `api.spec.ts`, and `e2e/playwright/helpers/accessibility.ts` alongside existing `utils.ts`. This matches the plan.md project structure and the established pattern.
**Evidence**: `e2e/playwright/tests/` contains `smoke.spec.ts` and `api.spec.ts`. `e2e/playwright/helpers/` contains `utils.ts`. Plan.md lines 56-59 confirm this placement.
