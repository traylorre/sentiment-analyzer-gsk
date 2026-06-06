# Feature 1345: Improve chaos-accessibility.spec.ts Scope and Coverage

## Status: DRAFT

## Problem Statement

`chaos-accessibility.spec.ts` has two issues with test precision and one duplicate test:

1. **AxeBuilder scans the entire page** (line 51) instead of scoping to the error boundary
   container. When the error boundary is active, the entire page IS the error boundary
   fallback, so the scan incidentally covers the right area. But if the error boundary
   doesn't fully replace the page (e.g., a partial error boundary in a sub-component),
   axe-core would scan unrelated DOM and either miss the error boundary or report
   violations from healthy UI. Scoping with `.include()` makes the test's intent explicit
   and future-proof.

2. **Color contrast exclusion undocumented** (line 53). `disableRules(['color-contrast'])`
   is intentional (dark theme error boundary has known contrast issues tracked separately),
   but the comment is minimal. Future developers may question whether this is a lazy skip
   or a deliberate decision.

3. **Keyboard nav test duplicates error-boundary spec** (lines 72-113). The T027 test in
   this file and T024 in `chaos-error-boundary.spec.ts` test identical behavior: focus
   each error boundary button with `.focus()` and assert `.toBeFocused()`. This file
   should focus on AUTOMATED axe-core scanning, not manual keyboard interaction tests.
   The keyboard test belongs in the error boundary spec where the other keyboard tests live.

## User Stories

### US-001: Scope AxeBuilder to Error Boundary Container
**As a** test author maintaining a11y tests,
**I want** the axe-core scan scoped to the error boundary fallback container,
**So that** the test explicitly targets the error boundary DOM and doesn't accidentally
pass/fail based on unrelated page content.

### US-002: Document Color Contrast Exclusion
**As a** developer reviewing disabled a11y rules,
**I want** a clear inline comment explaining WHY color-contrast is disabled, what the
known issue is, and where it's tracked,
**So that** the exclusion isn't mistaken for a lazy skip.

### US-003: Remove Duplicate Keyboard Test
**As a** test suite maintainer reducing duplication,
**I want** the keyboard focusability test (T027) removed from this file,
**So that** this file focuses exclusively on automated axe-core scanning and keyboard
navigation is tested in one place (chaos-error-boundary.spec.ts T024).

## Requirements

### Functional Requirements

#### FR-001: Scope AxeBuilder with .include()
- The `new AxeBuilder({ page })` call (line 51) must be chained with
  `.include('#error-boundary-fallback')` (or the actual container selector)
- If no element with that ID exists, determine the actual error boundary container
  selector by examining the ErrorBoundary component's fallback render
- Per Playwright docs (Context7): `new AxeBuilder({ page }).include('#selector').analyze()`
- The scan must still use `.withTags(['wcag2a', 'wcag2aa', 'wcag21a', 'wcag21aa'])`
- The scan must still use `.disableRules(['color-contrast'])`

#### FR-002: Document Error Boundary Container Selector
- Add a comment above the `.include()` call documenting which component renders this
  container and why we scope to it
- If the selector is a CSS class rather than an ID, document that it's fragile and may
  need updating if the component changes

#### FR-003: Document Color Contrast Exclusion
- Replace the existing comment (line 49-50):
  ```
  // Run axe-core scan — exclude color-contrast which is a known issue in dark theme
  // error boundary (tracked separately). Testing structural a11y here, not theme colors.
  ```
  with an expanded comment that includes:
  - What the known issue is (insufficient contrast ratio in dark theme error boundary)
  - Where it's tracked (or "tracked in project backlog" if no specific issue number)
  - That this exclusion applies ONLY to the error boundary fallback, not the main dashboard

#### FR-004: Delete Duplicate Keyboard Test (T027)
- Remove the entire T027 test block (lines 71-113)
- This test is a near-exact duplicate of T024 in `chaos-error-boundary.spec.ts:86-108`
- After removal, this file should have exactly 1 test (T026: axe-core scan)
- Verify T024 in error-boundary spec covers the same buttons (tryAgain, reload, goHome)

#### FR-005: Update File-Level JSDoc
- Update the file-level JSDoc to reflect the new scope: "Automated axe-core scanning of
  error boundary fallback. Manual keyboard and focus tests live in
  chaos-error-boundary.spec.ts."
- Remove the bullet point about "Error boundary buttons are keyboard-focusable" from the
  JSDoc header

### Non-Functional Requirements

#### NFR-001: No Test Coverage Loss
- Keyboard focusability is still tested in `chaos-error-boundary.spec.ts` T024
- The axe-core scan still covers WCAG 2.0 A/AA and WCAG 2.1 A/AA tags
- The color-contrast rule remains disabled (no accidental re-enable)

#### NFR-002: Selector Resilience
- The `.include()` selector should be as stable as possible (prefer `role` attributes,
  `data-testid`, or semantic HTML over CSS classes)
- If the selector is a class name, document its fragility

#### NFR-003: Single Test File Focus
- After changes, this file tests exactly ONE thing: automated axe-core a11y scanning of
  the error boundary. No keyboard tests, no focus tests, no banner tests.

## Success Criteria

1. AxeBuilder uses `.include()` to scope scan to error boundary container
2. Color contrast exclusion has expanded documentation with tracking reference
3. T027 (keyboard test) is removed from this file
4. File has exactly 1 `test(...)` call (T026)
5. T024 in `chaos-error-boundary.spec.ts` covers the same 3 buttons (tryAgain, reload, goHome)
6. File-level JSDoc reflects automated-scanning-only scope
7. Test passes locally with `npx playwright test chaos-accessibility`

## Out of Scope

- Fixing the actual color contrast issue in the error boundary component
- Adding focus-order (Tab sequence) validation (known limitation: chained Tab banned in
  headless Chromium, documented in chaos-error-boundary.spec.ts line 94-95)
- Modifying `chaos-error-boundary.spec.ts` (T024 already covers keyboard nav)
- Adding new axe-core rules or WCAG 2.2 tags
- Scoping to sub-components within the error boundary

## Risk Assessment

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| Wrong `.include()` selector | Medium | High | Inspect ErrorBoundary component render output to find actual container |
| Scoping hides real violations | Low | Medium | Compare scan results before/after scoping to verify same violations found |
| T024 doesn't fully cover T027 | Low | Low | T024 tests same 3 buttons with same `.focus()` + `.toBeFocused()` pattern |

---

## Appendix: Adversarial Review #1

### Ambiguity Check
- **FR-001**: What is the actual selector for the error boundary container? The spec says
  `#error-boundary-fallback` as an example, but the actual selector must be determined by
  reading the ErrorBoundary component. The implementation task must resolve this. If no
  stable selector exists, add `data-testid="error-boundary-fallback"` to the component
  OR use a broader semantic selector like `[role="alert"]` if the fallback uses one.

### Contradiction Check
- FR-001 says `.include('#error-boundary-fallback')` but the actual component may not use
  this ID. Resolution: FR-001 is aspirational -- the implementation must discover the real
  selector and update accordingly. FR-002 mandates documenting whichever selector is chosen.

### Edge Cases
- If the ErrorBoundary fallback renders as `<main>` (replacing the entire page content),
  then `.include('main')` would be equivalent to scanning the full page. This is still
  better than no `.include()` because it documents the intent and would catch a future
  refactor where the fallback renders inside a `<div>` instead.

## Clarifications

**Q: Should we add `data-testid="error-boundary-fallback"` to the React component?**
A: Only if no stable selector already exists. Check the ErrorBoundary component first.
If it renders a container with a role attribute or existing testid, use that. Adding a
testid is a production code change and should be minimal.

**Q: Does removing T027 reduce a11y coverage?**
A: No. T024 in `chaos-error-boundary.spec.ts` tests identical keyboard focusability with
the same 3 buttons (tryAgain, reload, goHome) using the same `.focus()` + `.toBeFocused()`
pattern. Lines 96-108 of that file are functionally identical to lines 104-112 of this file.

**Q: Should the `.include()` call be on the AxeBuilder in a11y-helpers.ts instead?**
A: No. The scope is test-specific (error boundary container), not universal. Different
a11y tests may scan different containers. The `.include()` belongs in the test file, not
the shared helper.
