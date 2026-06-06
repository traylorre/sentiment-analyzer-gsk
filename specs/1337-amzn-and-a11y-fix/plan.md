# Feature 1337: Implementation Plan

## Architecture Impact

**Scope**: Test-only changes + minor component a11y enhancement.
No new dependencies. No API changes. No infrastructure changes.

## Change Map

### Sub-Issue A: AMZN -> AAPL (Test-Only)

| File | Change | Lines |
|------|--------|-------|
| `frontend/tests/e2e/chart-zoom-data.spec.ts` | Replace `AMZN` with `AAPL` in 3 test blocks | 44-51, 99-104, 177-182 |

**Details**: Six string replacements total:
1. `searchInput.fill('AMZN')` -> `searchInput.fill('AAPL')` (x3)
2. `getByRole('option', { name: /AMZN/i })` -> `getByRole('option', { name: /AAPL/i })` (x3)

### Sub-Issue B: Error Boundary A11y

#### B1: Component Enhancement (error-boundary.tsx)

| Change | Location | Rationale |
|--------|----------|-----------|
| Add `id="error-boundary-heading"` to `<h2>` | Line 87 | Enable `aria-labelledby` reference |
| Add `aria-labelledby="error-boundary-heading"` to alert div | Line 81 | Associate heading with alert region |
| Add `tabIndex={-1}` to alert div | Line 81 | Enable programmatic focus |
| Add `useRef` + `useEffect` auto-focus | New import + new code | Move focus to error boundary on render |

Import changes needed:
- Add `useRef, useEffect` to React import (line 3 area — `ErrorFallback` is a function component)

Focus implementation:
```tsx
export function ErrorFallback({ error, onReset, onReload, onGoHome }: ErrorFallbackProps) {
  const containerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    containerRef.current?.focus();
  }, []);

  return (
    <div
      ref={containerRef}
      role="alert"
      aria-labelledby="error-boundary-heading"
      tabIndex={-1}
      className="min-h-[400px] flex items-center justify-center p-4"
    >
      ...
      <h2 id="error-boundary-heading" ...>Something went wrong</h2>
      ...
    </div>
  );
}
```

#### B2: Test Fix (chaos-error-boundary.spec.ts T024)

Replace chained Tab presses with programmatic `.focus()`:

**Before** (lines 95-121):
```typescript
await page.keyboard.press('Tab');
const firstFocused = await page.evaluate(() => document.activeElement?.textContent?.trim());
await page.keyboard.press('Tab');
const secondFocused = ...
await page.keyboard.press('Tab');
const thirdFocused = ...
```

**After**:
```typescript
const tryAgainButton = page.getByRole('button', { name: /try again/i });
const reloadButton = page.getByRole('button', { name: /reload page/i });
const goHomeButton = page.getByRole('button', { name: /go home/i });

await tryAgainButton.focus();
await expect(tryAgainButton).toBeFocused();

await reloadButton.focus();
await expect(reloadButton).toBeFocused();

await goHomeButton.focus();
await expect(goHomeButton).toBeFocused();
```

This matches the established pattern from:
- `keyboard.ts:focusAndAssert()` (FR-001, FR-002)
- `chaos-accessibility.spec.ts` T027 (lines 129-147)

## Dependency Order

```
B1 (component fix) -> B2 (test fix, depends on B1 for focus behavior)
A (ticker change)  -> independent, can execute in parallel with B
```

## Risk Assessment

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| AAPL ticker data disappears from Tiingo | Very Low | Medium | AAPL is the most common test ticker; mock-api-data.ts already uses it |
| Auto-focus breaks other tests | Low | Medium | Focus only fires on ErrorFallback mount, which is test-triggered only |
| axe-core still finds violations after fix | Low | Medium | aria-labelledby + heading ID is the standard fix for unlabeled alert regions |

## Non-Goals

- Changing health banner (T025) — already passes
- Adding `aria-label` to buttons — they use visible text content (WCAG compliant)
- Changing ErrorBoundary class component to function component
- Modifying mock-api-data.ts or chaos-helpers.ts
