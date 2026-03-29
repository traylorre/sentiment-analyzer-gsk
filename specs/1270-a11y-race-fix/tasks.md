# Feature 1270: Accessibility Race Fix — Tasks

## Task Dependency Graph

```
T1 (helper function) ──→ T2 (fix test 1) ──→ T5 (verify all pass)
                    ├──→ T3 (fix test 2)  ──┘
                    └──→ T4 (fix test 3)  ──┘
```

## Tasks

### T1: Create `waitForAccessibilityTree()` helper

**File**: `frontend/tests/e2e/helpers/a11y-helpers.ts` (NEW)
**Depends on**: None

Create a helper that polls the DOM for accessibility-relevant attributes before axe-core runs:

```typescript
import { Page } from '@playwright/test';

interface A11yWaitOptions {
  selector: string;
  attributes?: string[];
  timeout?: number;
  pollInterval?: number;
}

/**
 * Wait for the browser's accessibility tree to stabilize for a given element.
 *
 * Polls the DOM until the specified element exists AND has all required
 * ARIA attributes with non-empty values. This bridges the gap between
 * DOM visibility (element in viewport) and accessibility readiness
 * (ARIA tree computed).
 *
 * Use between toBeVisible() and AxeBuilder.analyze().
 */
export async function waitForAccessibilityTree(
  page: Page,
  options: A11yWaitOptions
): Promise<void> {
  const { selector, attributes = [], timeout = 5000, pollInterval = 50 } = options;

  await page.waitForFunction(
    ({ sel, attrs }) => {
      const el = document.querySelector(sel);
      if (!el) return false;
      // Element exists — check all required attributes have non-empty values
      return attrs.every((attr: string) => {
        const val = el.getAttribute(attr);
        return val !== null && val !== '';
      });
    },
    { sel: selector, attrs: attributes },
    { timeout, polling: pollInterval }
  );
}
```

**Acceptance criteria**:
- Exported function, importable from test files
- Uses `page.waitForFunction()` (NOT `waitForTimeout`)
- Polls at 50ms intervals by default
- Times out with clear error after 5s by default
- Works across all Playwright projects (Chrome, Firefox, WebKit)

---

### T2: Fix "health banner has zero critical accessibility violations"

**File**: `frontend/tests/e2e/chaos-accessibility.spec.ts`
**Location**: Lines 24-52 (test 1)
**Depends on**: T1

After `await expect(banner).toBeVisible();` (line 30), add:

```typescript
await waitForAccessibilityTree(page, {
  selector: '[role="alert"]',
  attributes: ['aria-live'],
});
```

Import `waitForAccessibilityTree` from the new helper.

---

### T3: Fix "error boundary fallback has zero critical accessibility violations"

**File**: `frontend/tests/e2e/chaos-accessibility.spec.ts`
**Location**: Lines 55-87 (test 2)
**Depends on**: T1

After the error boundary text visibility check (line 67), add:

```typescript
// Wait for error boundary buttons to have accessible names
await waitForAccessibilityTree(page, {
  selector: '[data-testid="error-boundary"] button, [role="alert"] button',
  attributes: ['type'],
});
```

Also verify that the error boundary component has proper ARIA attributes — if buttons are missing accessible names, that's a COMPONENT bug, not just a timing issue.

---

### T4: Fix "error boundary buttons are keyboard-focusable with accessible labels"

**File**: `frontend/tests/e2e/chaos-accessibility.spec.ts`
**Location**: Lines 90-124 (test 3)
**Depends on**: T1

Same pattern: add `waitForAccessibilityTree()` before any axe scan or ARIA assertion.

---

### T5: Verify deterministic pass

**Depends on**: T2, T3, T4

Run the accessibility tests with `--retries=0` to confirm they pass deterministically:

```bash
cd frontend && npx playwright test chaos-accessibility --retries=0 --reporter=list
```

Must pass on first attempt, not via retry.

## Adversarial Review #3

**Highest-risk task**: T1 — the helper must work across Chrome, Firefox, and WebKit accessibility tree implementations. Each browser computes the a11y tree differently.

**Most likely rework**: T3 — if the error boundary component has a REAL accessibility bug (missing aria-labels on buttons), the fix is in the component, not the test.

**Gate**: READY FOR IMPLEMENTATION — 0 CRITICAL, 0 HIGH remaining.
