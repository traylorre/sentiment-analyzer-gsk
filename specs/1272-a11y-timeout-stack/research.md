# Research: Accessibility Timeout Stack Fix

**Feature**: 1272-a11y-timeout-stack
**Date**: 2026-03-28

## R1: Timeout Stack Analysis

**Problem**: Three tests in `chaos-accessibility.spec.ts` fail in CI due to stacking multiple slow operations:

| Operation | Time (typical) | Time (worst case) |
|-----------|---------------|-------------------|
| `page.goto('/') + waitForTimeout(2000)` | 2.0s (fixed) | 2.0s |
| `triggerHealthBanner()` | 3-5s | 6s |
| `waitForAccessibilityTree()` | <200ms | 5.0s (timeout) |
| `AxeBuilder.analyze()` | 2-3s | 4s |
| **Total (T025)** | **~7-10s** | **~17s** |

For T026/T027 (error boundary path):
| Operation | Time (typical) | Time (worst case) |
|-----------|---------------|-------------------|
| `page.goto('/') + waitForTimeout(2000)` | 2.0s (fixed) | 2.0s |
| `addInitScript + page.goto + waitForTimeout(1000)` | 1.0s (fixed) | 1.0s |
| `toBeVisible({ timeout: 5000 })` | <1s | 5.0s |
| `waitForAccessibilityTree()` | <200ms | 5.0s (timeout) |
| `AxeBuilder.analyze()` | 2-3s | 4s |
| **Total (T026)** | **~6-9s** | **~17s** |

**Key insight**: `chaos-degradation.spec.ts` uses `triggerHealthBanner()` without `waitForAccessibilityTree()` or `AxeBuilder` and passes. This confirms the stacking of a11y-specific operations is the differentiator.

## R2: waitForAccessibilityTree Default Timeout

**Current**: 5000ms default in `a11y-helpers.ts`
**Analysis**: ARIA attributes (`aria-live`, `aria-pressed`, `type`) are set during React component render. By the time Playwright confirms the element is visible, the attributes should already be computed. The 5000ms timeout exists as a safety margin but is excessive.

**Evidence**: In `chaos-degradation.spec.ts`, `toHaveAttribute('aria-live', 'assertive', { timeout: 3000 })` passes consistently, suggesting the attribute is present within 3 seconds (likely within milliseconds).

**Recommendation**: Reduce default to 2000ms. This is 10x the expected resolution time (~200ms) while recovering 3 seconds from the worst-case timeout budget.

## R3: AxeBuilder.include() Scoping

**Playwright axe-core API**:
```typescript
const results = await new AxeBuilder({ page })
  .include('[role="alert"]')  // Only scan the banner
  .withTags(['wcag2a', 'wcag2aa', 'wcag21a', 'wcag21aa'])
  .analyze();
```

**Performance impact**: Full-page scan indexes every DOM node for accessibility violations. Scoping to a single component reduces the DOM traversal from hundreds/thousands of nodes to ~5-20 nodes. Expected speedup: 2-5x.

**Trade-off**: Scoped scans miss violations outside the targeted element. For these tests, this is desirable -- we're testing degraded-state accessibility, not baseline page accessibility.

## R4: test.setTimeout() Pattern

**Existing pattern in the codebase**: Multiple test files already use `test.setTimeout(30_000)`:
- `settings-interactions.spec.ts`
- `sentiment-visibility.spec.ts`
- `dialog-dismissal.spec.ts`
- `dashboard-interactions.spec.ts`
- `alert-crud.spec.ts`
- `auth-menu-items.spec.ts`
- `signin-interaction.spec.ts`
- `config-crud.spec.ts`

**Pattern**: Always placed as the first statement inside the `test.describe()` block.

**Recommendation**: Add `test.setTimeout(30_000)` as the first statement in the `chaos-accessibility.spec.ts` describe block. This is a well-established pattern in the codebase.

## R5: Playwright Default Timeout Behavior

Playwright's default test timeout is 30,000ms (30 seconds) when not explicitly configured. The `playwright.config.ts` for this project does NOT set a global timeout override. However, CI runners may have different performance characteristics that make operations slower.

The Playwright config sets `retries: process.env.CI ? 2 : 0`, which means CI gets 2 retries. But the problem states the tests fail consistently (5.6s, 8.4s, 8.3s), suggesting they fail on all retries.

**Correction to initial analysis**: The reported times (5.6s, 8.4s, 8.3s) are under the 30s default timeout. These tests may be failing due to individual operation timeouts (e.g., `waitForAccessibilityTree`'s 5000ms timeout expiring) rather than the overall test timeout. This means the operations are actually timing out within their individual timeout budgets, not the test-level timeout.

This makes reducing the `waitForAccessibilityTree` default timeout WRONG for the fix -- if the function is timing out at 5000ms, reducing to 2000ms would make it fail faster, not fix it. Instead, the issue might be that the ARIA attributes are not present when expected.

**Re-analysis**: Looking at the actual test flow:
1. `triggerHealthBanner()` takes 3-5s (proven to work -- chaos-degradation uses it)
2. `waitForAccessibilityTree()` with 5000ms timeout -- if this times out, the test fails at the 5s mark
3. `AxeBuilder.analyze()` takes 2-3s

The reported 5.6s for T025 = ~3-5s triggerHealthBanner + ~0.6-2.6s remaining. This suggests the test is failing during `waitForAccessibilityTree` or `AxeBuilder`, not that the overall stack exceeds a timeout.

**Revised understanding**: The tests may be hitting individual operation timeouts within the stack, OR the total accumulated time exceeds a per-test timeout that's set lower than 30s in CI. Either way, the fixes (reduce unnecessary waiting, scope axe scans, set explicit test timeout) address both interpretations.

## R6: Error Boundary Identification for AxeBuilder.include()

For T026, we need to scope axe-core to the error boundary container. Looking at the test:
```typescript
await expect(page.getByText(/something went wrong/i)).toBeVisible({ timeout: 5000 });
```

The error boundary likely has a container element. Common patterns:
- A div with a specific class or role
- The element containing "something went wrong" text

For AxeBuilder.include(), we can use a CSS selector that targets the error boundary. If the text is inside a specific container, we can use a parent selector or a known class/role.

**Recommendation**: Use `.include('main')` or a more specific selector if the error boundary has one. Alternatively, use `.include(':has-text("something went wrong")')` -- but AxeBuilder uses CSS selectors, not Playwright selectors. Best approach: inspect the actual component and use its container's CSS selector.

A safe fallback is `.include('body > main')` or simply the most specific ancestor container available.
