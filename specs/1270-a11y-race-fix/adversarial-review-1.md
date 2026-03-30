# Adversarial Review #1: Component Accessibility Audit

**Feature**: 1270-a11y-race-fix
**Date**: 2026-03-28
**Question**: Could the components themselves have real accessibility issues that this fix papers over?

## Methodology

Manually audited ARIA attributes, roles, accessible names, keyboard focusability, and color contrast for both components under test.

## Component 1: ApiHealthBanner (`api-health-banner.tsx`)

| Check | Status | Evidence |
|-------|--------|----------|
| `role="alert"` | PASS | Line 58, statically in JSX |
| `aria-live="assertive"` | PASS | Line 59, statically in JSX |
| Dismiss button `aria-label` | PASS | Line 69: `aria-label="Dismiss connectivity warning"` |
| Visible text content | PASS | Line 63-65: "We're having trouble connecting..." |
| Keyboard focus indicator | PASS | Tailwind `hover:bg-amber-800` + browser default focus |
| Color contrast | PASS | `text-amber-100` on `bg-amber-900/90` -- high contrast |

**Key observation**: ALL ARIA attributes are statically present in JSX. They are NOT dynamically added via `useEffect`. The race condition is between DOM insertion and browser accessibility tree computation, not between render phases.

## Component 2: ErrorFallback (`error-boundary.tsx`)

| Check | Status | Evidence |
|-------|--------|----------|
| Buttons use native `<button>` | PASS | `Button` component renders native `<button>` (button.tsx:43) |
| Accessible names from visible text | PASS | "Try Again", "Reload Page", "Go Home" are visible text |
| Keyboard focusable | PASS | Native `<button>` is inherently focusable |
| Focus indicator | PASS | `focus-visible:ring-2` via buttonVariants (button.tsx:7) |
| Heading semantics | PASS | `<h2>` for "Something went wrong" (error-boundary.tsx:88) |
| Icons are decorative | PASS | Lucide `<svg>` without `role="img"`, accompanies text |

**Key observation**: All accessible names derive from visible text content, not from ARIA attributes. The race is the browser computing the text-to-accessible-name mapping, not React rendering the text.

## Attack: Does `waitForAccessibilityTree()` Paper Over Real Issues?

**NO**. Reasoning:

1. Static ARIA: All attributes are in JSX markup, not added by effects
2. Text-based names: Accessible names come from visible text, not computed ARIA
3. The bug is browser-level: After React DOM commit, the browser's accessibility tree needs a rendering cycle to update. Axe-core queries the accessibility tree (not the DOM), so it finds stale/incomplete data
4. Evidence: The tests pass with retries (the 2nd/3rd attempt finds attributes because enough time has passed)

## Attack: Are Existing `waitForTimeout()` Calls Hiding Issues?

The `beforeEach` `waitForTimeout(2000)` and per-test `waitForTimeout(1000)` serve different purposes:
- `beforeEach` 2000ms: Waits for React hydration + initial API calls (present in all e2e tests)
- Per-test 1000ms: Waits for error boundary lifecycle after navigation (React-specific timing)

These are NOT accessibility-related waits. They are unrelated to the race condition being fixed.

## Verdict

**Components are genuinely accessible.** The fix correctly targets test timing, not component defects. No component modifications needed.
