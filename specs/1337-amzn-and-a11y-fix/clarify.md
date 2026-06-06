# Feature 1337: Clarification Record

## Pre-Clarification Analysis

All 5 potential ambiguities were resolved through source code inspection. No user
interaction required — the codebase provides definitive answers.

## Q1: Does chart-zoom-data.spec.ts use the GOOG->AAPL search regex?

**Answer**: No. The feature description mentioned "GOOG->AAPL ticker search regex" but
inspection of `chart-zoom-data.spec.ts` shows it uses only `AMZN` as a plain string fill
(`searchInput.fill('AMZN')`) and `getByRole('option', { name: /AMZN/i })`. There is no
GOOG reference in this file. The GOOG reference in the feature description was incorrect
or referred to a different file.

**Resolution**: Replace `AMZN` with `AAPL` in all 3 instances. No GOOG cleanup needed.

## Q2: Is "Go Home" a button or a link in the rendered DOM?

**Answer**: Button. In `error-boundary.tsx:117`, `onGoHome` renders as
`<Button type="button" onClick={onGoHome}>`. The `Button` component (`button.tsx`) renders
a `<button>` element (not an `<a>`). The test in `chaos-accessibility.spec.ts:131-133`
correctly handles both cases with `.getByRole('link').or(getByRole('button'))`.

**Resolution**: No change needed for "Go Home" role matching. The `.or()` pattern is
already robust.

## Q3: What specific axe-core violations does the error boundary produce?

**Answer**: Predicted violations based on component structure:
- The `role="alert"` container at line 81 lacks `aria-labelledby` or `aria-label`
- This may trigger axe rule `aria-allowed-attr` or `region` violation
- The heading `<h2>` at line 87-89 has no `id` for programmatic association

**Resolution**: Add `id="error-boundary-heading"` to `<h2>` and
`aria-labelledby="error-boundary-heading"` to the `role="alert"` div.

## Q4: Should focus auto-move to the error boundary when it appears?

**Answer**: WCAG 2.1 SC 4.1.3 (Status Messages) and SC 2.4.3 (Focus Order) recommend
that when dynamic content replaces the main view (as the error boundary does), focus
should move to the new content. The `role="alert"` provides screen reader announcement,
but keyboard users need focus management too.

However, adding `autoFocus` or a focus `useRef` to the error boundary could be invasive.
Since the component is a class component (`ErrorBoundary`) that delegates to a functional
`ErrorFallback`, the simplest approach is adding `tabIndex={-1}` to the alert container
and using a `useRef` + `useEffect` in `ErrorFallback` to auto-focus on mount.

**Resolution**: Add `tabIndex={-1}` and auto-focus via `useRef` to the alert container in
`ErrorFallback`. This is minimal, follows WCAG guidance, and makes the Tab-focus test
reliable because focus starts inside the error boundary.

## Q5: Does the T024 keyboard nav test need exact focus order or just presence?

**Answer**: Inspecting `chaos-error-boundary.spec.ts:111-121`:
```typescript
const focusedElements = [firstFocused, secondFocused, thirdFocused].filter(Boolean);
expect(focusedElements.length).toBeGreaterThanOrEqual(2);
const hasRecoveryAction = focusedElements.some(
  (text) => /try again|reload|go home/i.test(text || ''),
);
expect(hasRecoveryAction).toBeTruthy();
```

The test only requires >= 2 focused elements and at least one matching a recovery action.
It does NOT assert exact order (Try Again -> Reload -> Go Home). This is a lenient check.

**Resolution**: Replace chained Tab with programmatic `.focus()` on each button. The
assertions already accommodate flexible focus — just need reliable focus targeting.

## Summary: All Questions Self-Resolved

No blocking ambiguities remain. Proceed to planning.
