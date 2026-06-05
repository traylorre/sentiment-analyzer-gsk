# Implementation Plan -- Feature 1345: Improve chaos-accessibility.spec.ts Scope

## Files to Modify

### 1. `frontend/tests/e2e/chaos-accessibility.spec.ts` (PRIMARY)

This is the only file with code changes. The error boundary component may need inspection
but is NOT modified.

### 2. ErrorBoundary component (READ-ONLY inspection)

Must read the ErrorBoundary fallback render to determine the correct `.include()` selector.
Likely locations:
- `frontend/src/components/ErrorBoundary.tsx`
- `frontend/src/app/error.tsx` (Next.js error boundary)

## Current State (114 lines)

```
Lines 1-4:     Imports (test, expect, AxeBuilder, waitForAccessibilityTree)
Lines 6-19:    File-level JSDoc
Lines 20-23:   test.describe + setTimeout(30_000)
Lines 25-69:   T026: axe-core scan test
Lines 71-113:  T027: keyboard focusability test (DUPLICATE of T024)
Line 114:      Close describe
```

## Planned State (~75 lines)

```
Lines 1-4:     Imports (unchanged -- waitForAccessibilityTree still used by T026)
Lines 6-17:    Updated file-level JSDoc (scanning-only scope)
Lines 18-21:   test.describe + setTimeout(30_000) (unchanged)
Lines 23-73:   T026: axe-core scan test (scoped, documented)
Line 74:       Close describe
```

## Pre-Implementation: Discover Error Boundary Selector

Before making changes, read the ErrorBoundary component to determine what container
element wraps the fallback UI. Look for:
1. A `data-testid` attribute on the fallback wrapper
2. A `role` attribute (e.g., `role="alert"`)
3. An `id` attribute
4. A stable CSS class

If none exist, the implementation must decide between:
- **Option A**: Add `data-testid="error-boundary-fallback"` to the component (minimal
  production change, stable selector)
- **Option B**: Use a CSS selector that matches the fallback's structure (fragile,
  document why)
- **Option C**: Use `role="alert"` or `role="main"` if the fallback uses semantic HTML
  (good if it exists)

## Change Details

### Change 1: Update File-Level JSDoc

**Before**:
```typescript
/**
 * Chaos: Accessibility During Degraded States (Feature 1265, US4/FR-010/SC-005)
 *
 * Validates that degraded UI states maintain accessibility:
 * - Error boundary fallback passes WCAG audit
 * - Error boundary buttons are keyboard-focusable
 *
 * T025 (health banner a11y) was DELETED: triggerHealthBanner fires consecutive
 * API failures that trigger the error boundary BEFORE the health banner appears,
 * making it test the wrong thing. Redundant with T026/T027 below.
 *
 * Scope: Automated structural checks only (ARIA attributes, keyboard navigation,
 * focus management). Manual screen reader testing is out of scope.
 */
```

**After**:
```typescript
/**
 * Chaos: Accessibility During Degraded States (Feature 1265, US4/FR-010/SC-005)
 *
 * Automated axe-core WCAG scanning of the error boundary fallback UI.
 * Verifies zero critical/serious violations when the app is in a degraded state.
 *
 * Keyboard focusability tests live in chaos-error-boundary.spec.ts (T024).
 * Manual screen reader testing is out of scope.
 *
 * History: T025 (health banner a11y) deleted — triggerHealthBanner caused error
 * boundary to fire before banner appeared. T027 (keyboard nav) moved to
 * chaos-error-boundary.spec.ts to consolidate keyboard tests in one file.
 */
```

### Change 2: Scope AxeBuilder with .include()

**Before** (line 51-54):
```typescript
const results = await new AxeBuilder({ page })
  .withTags(['wcag2a', 'wcag2aa', 'wcag21a', 'wcag21aa'])
  .disableRules(['color-contrast'])
  .analyze();
```

**After**:
```typescript
// Scope axe-core to the error boundary container rather than scanning the
// full page. This makes the test intent explicit: we're validating the
// ERROR BOUNDARY's a11y, not the entire app. If the fallback changes from
// full-page to partial-page in the future, this scope ensures we still
// scan the right DOM subtree.
// Selector: [determined during implementation based on component inspection]
const results = await new AxeBuilder({ page })
  .include('[SELECTOR_TBD]')
  .withTags(['wcag2a', 'wcag2aa', 'wcag21a', 'wcag21aa'])
  .disableRules(['color-contrast'])
  .analyze();
```

The `[SELECTOR_TBD]` placeholder is resolved during T1 (component inspection).

### Change 3: Expand Color Contrast Documentation

**Before** (lines 49-50):
```typescript
// Run axe-core scan — exclude color-contrast which is a known issue in dark theme
// error boundary (tracked separately). Testing structural a11y here, not theme colors.
```

**After**:
```typescript
// Exclude color-contrast rule: The error boundary's dark theme fallback has
// insufficient contrast ratios on secondary text (gray-on-dark-gray). This is
// a KNOWN issue tracked in the project backlog. Fixing requires a design review
// of the error boundary color palette. This exclusion applies ONLY to this test
// (error boundary fallback), not to main dashboard a11y tests.
```

### Change 4: Delete T027 Keyboard Test

Remove lines 71-113 (the entire T027 test block):
```typescript
// T027: Error boundary buttons are keyboard-focusable
test('error boundary buttons are keyboard-focusable with accessible labels', async ({
  page,
}) => {
  // ... 40 lines of keyboard focus testing ...
});
```

**Justification**: T024 in `chaos-error-boundary.spec.ts:86-108` tests identical behavior:
- Same 3 buttons: tryAgain, reload, goHome
- Same pattern: `.focus()` then `expect().toBeFocused()`
- Same error boundary trigger: `addInitScript` + `goto`

Diff between T024 and T027:
- T027 uses `waitForAccessibilityTree()` before focus checks; T024 does not
- T027 locates goHome as `getByRole('link').or(getByRole('button'))`; T024 uses
  `getByRole('button')` only

Neither difference is significant:
- `waitForAccessibilityTree` is defensive but not required for `.focus()` to work
- The goHome link/button distinction is handled by T024's simpler locator (if the
  component renders a button, both work)

## Import Verification After Deletion

| Import | Used by T026? |
|--------|---------------|
| `test, expect` from `@playwright/test` | Yes |
| `AxeBuilder` from `@axe-core/playwright` | Yes |
| `waitForAccessibilityTree` from `./helpers/a11y-helpers` | Yes (T026 lines 43-47) |

All imports remain in use after T027 deletion. No cleanup needed.

## Files NOT Modified

- `chaos-error-boundary.spec.ts` -- T024 already covers keyboard nav, no changes needed
- `a11y-helpers.ts` -- `waitForAccessibilityTree` and `assertNoA11yViolations` unchanged
- ErrorBoundary component -- read-only inspection (unless `data-testid` must be added)

---

## Appendix: Adversarial Review #2

### Completeness Check
- FR-001 (scope AxeBuilder) -> Change 2
- FR-002 (document selector) -> Change 2 comment
- FR-003 (document color contrast) -> Change 3
- FR-004 (delete T027) -> Change 4
- FR-005 (update JSDoc) -> Change 1

### Risk Assessment
- **Change 2**: If no stable selector exists on the error boundary, we must either add
  a `data-testid` (production code change) or use a fragile CSS selector. The
  pre-implementation discovery step handles this.
- **Change 4**: The T027 deletion removes `waitForAccessibilityTree` usage from the
  keyboard test, but T026 still uses it, so the import stays. No coverage gap because
  T024 tests the same buttons.

### Selector Discovery Risk
The biggest implementation risk is finding a stable selector for `.include()`. Fallback
plan if the ErrorBoundary renders no identifiable container:
1. Check if the fallback uses `<main>` or `<section>` with a unique attribute
2. Look for text content that could serve as a scoping anchor (e.g., "Something went wrong"
   heading's parent container)
3. Last resort: add `data-testid="error-boundary-fallback"` to the component and document
   the change as a minimal production modification
