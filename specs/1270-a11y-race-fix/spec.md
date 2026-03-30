# Feature Specification: Accessibility Tree Race Condition Fix

**Feature Branch**: `1270-a11y-race-fix`
**Created**: 2026-03-28
**Status**: Draft
**Input**: User description: "Fix deterministic timing bug in chaos-accessibility.spec.ts where toBeVisible() succeeds but AxeBuilder.analyze() runs before the browser's accessibility tree (ARIA attributes, accessible names, computed roles) has stabilized, causing transient violations that fail CI consistently"

## User Scenarios & Testing *(mandatory)*

### User Story 1 - CI Pipeline Runs Accessibility Tests Deterministically (Priority: P1)

The CI pipeline runs `chaos-accessibility.spec.ts` against the customer dashboard. Currently, all three tests fail consistently because `AxeBuilder.analyze()` executes in the gap between DOM visibility and accessibility tree stabilization. After this fix, the tests wait for ARIA attributes to be fully computed before running axe-core, and all three tests pass on the first attempt without retries.

**Why this priority**: These tests block the CI pipeline. Every PR that touches frontend code either fails or relies on the retry mechanism (2 retries in CI) to pass by luck. The tests are not flaky -- they have a deterministic timing bug that causes consistent failure on the first run.

**Independent Test**: Run `npx playwright test chaos-accessibility.spec.ts --retries=0` locally. All 3 tests should pass on first attempt.

**Acceptance Scenarios**:

1. **Given** the health banner is triggered via API failures, **When** the banner becomes visible in the DOM, **Then** the test waits for `aria-live="assertive"` and the dismiss button's `aria-label` to be present and computed before running `AxeBuilder.analyze()`, and the scan returns zero critical/serious violations.
2. **Given** the error boundary is triggered via `__TEST_FORCE_ERROR`, **When** "Something went wrong" text is visible, **Then** the test waits for all three action buttons to have computed accessible names (not just DOM presence) before running `AxeBuilder.analyze()`, and the scan returns zero critical/serious violations.
3. **Given** the error boundary buttons are rendered, **When** the test checks keyboard focusability, **Then** `getByRole('button', { name: ... })` succeeds because the accessible names are fully computed, and focus/blur operations work correctly.

---

### User Story 2 - Shared Helper Provides Reusable A11y Wait Pattern (Priority: P1)

A test author writing new accessibility tests in any Playwright spec can import `waitForAccessibilityTree()` from the helpers directory and use it to wait for ARIA attribute stabilization before running axe-core scans. The helper does NOT use `waitForTimeout()` (blind waits) -- it uses `page.waitForFunction()` to poll for specific accessibility-relevant attributes in the DOM.

**Why this priority**: Without a shared helper, every future accessibility test will reproduce this same timing bug. The pattern must be extracted once and reused.

**Independent Test**: Import the helper in a new test file and verify it correctly waits for specified ARIA attributes.

**Acceptance Scenarios**:

1. **Given** a page with elements that have `aria-live`, `aria-label`, and `role` attributes, **When** `waitForAccessibilityTree()` is called with selectors for those elements, **Then** the function resolves only after all specified attributes are present and non-empty in the DOM.
2. **Given** a page where ARIA attributes take 500ms to compute (simulated via delayed React state updates), **When** `waitForAccessibilityTree()` is called, **Then** it waits without timeout and resolves correctly (no blind `waitForTimeout`).
3. **Given** `waitForAccessibilityTree()` is called with a timeout of 5000ms and the attributes never appear, **When** the timeout expires, **Then** the function throws a descriptive error indicating which specific ARIA attributes were missing.

---

### User Story 3 - Components Themselves Are Actually Accessible (Priority: P1)

The fix must verify that the components under test (ApiHealthBanner, ErrorFallback) are genuinely accessible -- the problem is in the test timing, NOT the components. This verification is a prerequisite before committing any test changes, to ensure we are not papering over real accessibility violations.

**Why this priority**: If the components have genuine ARIA issues, fixing the test timing would hide real bugs. We must confirm that the components are accessible when the accessibility tree has stabilized.

**Independent Test**: Manual axe-core scan with sufficient wait time (or Playwright test with generous explicit waits) confirms zero critical/serious violations.

**Acceptance Scenarios**:

1. **Given** the `ApiHealthBanner` component, **When** fully rendered and stabilized, **Then** it has `role="alert"`, `aria-live="assertive"`, and the dismiss button has `aria-label="Dismiss connectivity warning"`.
2. **Given** the `ErrorFallback` component, **When** fully rendered and stabilized, **Then** all three buttons ("Try Again", "Reload Page", "Go Home") have visible text content that serves as their accessible name, and they are keyboard-focusable (`tabindex` is not `-1`).
3. **Given** axe-core runs on the fully stabilized page, **When** scanning with `['wcag2a', 'wcag2aa', 'wcag21a', 'wcag21aa']` tags, **Then** zero critical or serious violations are found for either component.

---

## Functional Requirements

### FR-001: Shared `waitForAccessibilityTree()` Helper

Create a helper function in `frontend/tests/e2e/helpers/a11y-helpers.ts` that:

1. Accepts a `Page` object and a list of accessibility attribute expectations (selectors + expected ARIA attributes)
2. Uses `page.waitForFunction()` to poll the DOM for the specified attributes
3. Returns only when ALL specified attributes are present and non-empty
4. Has a configurable timeout (default: 5000ms)
5. On timeout, throws a descriptive error listing which attributes were missing
6. Does NOT use `page.waitForTimeout()` or any blind/fixed delay

**Signature** (TypeScript):
```typescript
interface A11yExpectation {
  /** CSS selector for the element */
  selector: string;
  /** ARIA attributes that must be present and non-empty */
  attributes: string[];
}

async function waitForAccessibilityTree(
  page: Page,
  expectations: A11yExpectation[],
  options?: { timeout?: number }
): Promise<void>;
```

### FR-002: Fix Test T025 (Health Banner A11y)

Between `expect(banner).toBeVisible()` and `AxeBuilder.analyze()`, insert a call to `waitForAccessibilityTree()` that waits for:
- `[role="alert"]` has `aria-live` attribute present
- `button[aria-label]` within the banner has a non-empty `aria-label`

### FR-003: Fix Test T026 (Error Boundary Fallback A11y)

Between `expect(page.getByText(/something went wrong/i)).toBeVisible()` and `AxeBuilder.analyze()`, insert a call to `waitForAccessibilityTree()` that waits for:
- All three buttons have computed text content (accessible names)
- The error boundary container is fully rendered with all child elements

### FR-004: Fix Test T027 (Error Boundary Keyboard Focus)

Between the visibility check and the `getByRole`/focus assertions, insert a call to `waitForAccessibilityTree()` that waits for:
- Buttons with roles `button` and accessible names matching "Try Again", "Reload Page", "Go Home" are present in the accessibility tree

### FR-005: No Blind Waits

The existing `waitForTimeout(1000)` and `waitForTimeout(2000)` calls in `beforeEach` and individual tests should be evaluated. If they serve only as timing hacks for accessibility tree settling, they should be replaced by the new helper. If they serve a different purpose (e.g., waiting for React hydration or API route setup), they should be documented but left in place.

## Non-Functional Requirements

### NFR-001: Deterministic First-Run Pass
All three tests must pass on the first attempt with `--retries=0`. The Playwright config currently sets `retries: process.env.CI ? 2 : 0` -- this fix should make those retries unnecessary for these tests (though we do not change the global retry setting).

### NFR-002: No Performance Regression
The `waitForAccessibilityTree()` helper should add minimal overhead. When ARIA attributes are already present (fast render), it should resolve in under 100ms. The polling interval should be short (50-100ms) to detect attributes quickly without CPU waste.

### NFR-003: Helper Is Reusable
The helper must be generic enough to use in any future accessibility test -- not hardcoded to the specific selectors in these three tests.

## Technical Constraints

- **Playwright version**: Must work with the version specified in `frontend/package.json`
- **Browser scope**: Must work across all 5 Playwright projects (Mobile Chrome, Mobile Safari, Desktop Chrome, Firefox, WebKit)
- **No component changes**: The components (`api-health-banner.tsx`, `error-boundary.tsx`) should NOT be modified unless a genuine accessibility defect is discovered during Stage 2 adversarial review
- **File location**: Helper goes in `frontend/tests/e2e/helpers/a11y-helpers.ts` following existing pattern (`chaos-helpers.ts`, `auth-helper.ts`, etc.)

## Out of Scope

- Changing the Playwright retry configuration
- Adding new accessibility tests beyond fixing the existing three
- Manual screen reader testing (per existing spec comment in the test file)
- Modifying axe-core tag configuration
- Changing the global `beforeEach` wait pattern for non-accessibility tests

## Risk Assessment

| Risk | Impact | Mitigation |
|------|--------|------------|
| Components have real a11y defects | HIGH -- fix papers over real bugs | Stage 2 adversarial review verifies component ARIA markup before test changes |
| `page.waitForFunction()` unreliable in WebKit | MEDIUM -- test fails on one browser | Test across all 5 Playwright projects; WebKit may need longer timeout |
| Polling interval too aggressive causes CPU issues in CI | LOW -- CI uses `workers: 1` | Use 50-100ms interval; CI has single worker already |
| New helper introduces import cycle or bundling issue | LOW | Helper is test-only code, not shipped to production |
