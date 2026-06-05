# Implementation Plan: Fix Vacuous E2E Tests

**Branch**: `1322-fix-vacuous-e2e-tests` | **Date**: 2026-04-05 | **Spec**: [spec.md](spec.md)
**Input**: Feature specification from `/specs/1322-fix-vacuous-e2e-tests/spec.md`

## Summary

Fix 2 vacuous Playwright E2E tests in `first-impression.spec.ts` that pass without asserting real behavior. The navigation tabs test skips all assertions on desktop (CI viewport). The reduced motion test asserts a tautology (`typeof boolean === 'boolean'`). Both are fixed with substantive assertions that verify actual behavior.

## Technical Context

**Language/Version**: TypeScript (Playwright test files)
**Primary Dependencies**: `@playwright/test` (existing)
**Storage**: N/A
**Testing**: Modified tests must pass in CI (Desktop Chrome, 1280px viewport)
**Target Platform**: Customer Dashboard (Next.js/Amplify)
**Project Type**: Test quality fix
**Performance Goals**: No more than 2s additional execution time per test
**Constraints**: Must not modify `chaos.spec.ts`. Desktop navigation element selectors must match the current UI.
**Scale/Scope**: 2 test modifications in 1 file

## Constitution Check

- No new production code
- No infrastructure changes
- No cost impact
- Test quality improvement only

## Project Structure

### Modified Files

```text
frontend/tests/e2e/first-impression.spec.ts   # Fix 2 vacuous tests (R1, R2)
```

### Unchanged Files (documented decision)

```text
frontend/tests/e2e/chaos.spec.ts              # Auth test confirmed legitimate (R3)
```

### Spec Artifacts

```text
specs/1322-fix-vacuous-e2e-tests/
├── spec.md              # Feature specification
├── plan.md              # This file
└── tasks.md             # Task list
```

## Key Design Decisions

1. **Desktop `else` block, not removing mobile branch**: The mobile `if` block is valid for mobile viewport tests. The fix adds an `else` block for desktop, not removing the existing mobile path. Both paths now have assertions.

2. **`page.emulateMedia` over `matchMedia` query**: The original test only queried `matchMedia` -- it never emulated the media preference. The fix uses `page.emulateMedia({ reducedMotion: 'reduce' })` which is the Playwright-native way to simulate the media feature, then checks the resulting computed CSS.

3. **Check computed style on `document.body`**: The `globals.css` rule applies to `*` (all elements), so `document.body` is a reliable target. No need to find a specific animated element. The computed `animation-duration` and `transition-duration` will reflect the `0.01ms !important` override.

4. **Hardcoded tab names**: The desktop navigation assertions use hardcoded names (Dashboard, Configs, Alerts, Settings) matching the mobile tab names. This is intentional -- the test verifies exact navigation items, not just "some navigation exists."

## Changes

### Change 1: Navigation Tabs Test -- Add Desktop Assertions

**File**: `frontend/tests/e2e/first-impression.spec.ts`
**Lines**: 21-36 (the `should have working navigation tabs` test)
**Requirement**: R1

**Current code**:
```typescript
test('should have working navigation tabs', async ({ page }) => {
  const nav = page.getByRole('tablist', { name: /main navigation/i });
  const isMobile = await page.evaluate(() => window.innerWidth < 768);
  if (isMobile) {
    await expect(nav).toBeVisible();
    await expect(page.getByRole('tab', { name: /dashboard/i })).toBeVisible();
    await expect(page.getByRole('tab', { name: /configs/i })).toBeVisible();
    await expect(page.getByRole('tab', { name: /alerts/i })).toBeVisible();
    await expect(page.getByRole('tab', { name: /settings/i })).toBeVisible();
  }
});
```

**Changed code** (add `else` block after the `if (isMobile)` block):
```typescript
test('should have working navigation tabs', async ({ page }) => {
  const nav = page.getByRole('tablist', { name: /main navigation/i });
  const isMobile = await page.evaluate(() => window.innerWidth < 768);
  if (isMobile) {
    await expect(nav).toBeVisible();
    await expect(page.getByRole('tab', { name: /dashboard/i })).toBeVisible();
    await expect(page.getByRole('tab', { name: /configs/i })).toBeVisible();
    await expect(page.getByRole('tab', { name: /alerts/i })).toBeVisible();
    await expect(page.getByRole('tab', { name: /settings/i })).toBeVisible();
  } else {
    // Desktop: mobile tablist is hidden (verified by "should show desktop layout" test).
    // Here we verify desktop navigation elements exist with correct names.
    const desktopNav = page.getByRole('navigation', { name: /main/i });
    await expect(desktopNav).toBeVisible();

    // Verify all expected navigation links are present
    const navLinks = desktopNav.getByRole('link');
    await expect(navLinks).toHaveCount(4);
    await expect(desktopNav.getByRole('link', { name: /dashboard/i })).toBeVisible();
    await expect(desktopNav.getByRole('link', { name: /configs/i })).toBeVisible();
    await expect(desktopNav.getByRole('link', { name: /alerts/i })).toBeVisible();
    await expect(desktopNav.getByRole('link', { name: /settings/i })).toBeVisible();
  }
});
```

**Rationale**: On desktop, navigation is rendered as a sidebar with `role="navigation"` and `role="link"` elements (not `role="tablist"` / `role="tab"` which are mobile-only). The `else` block asserts: (a) desktop nav container is visible, (b) exactly 4 navigation links exist, (c) each link has the expected name. This gives 6 assertions on desktop vs. the previous 0.

---

### Change 2: Reduced Motion Test -- Replace Tautology with CSS Check

**File**: `frontend/tests/e2e/first-impression.spec.ts`
**Lines**: 65-73 (the `should respect reduced motion preference` test)
**Requirement**: R2

**Current code**:
```typescript
test('should respect reduced motion preference', async ({ page }) => {
  const hasReducedMotion = await page.evaluate(() => {
    return window.matchMedia('(prefers-reduced-motion: reduce)').matches;
  });
  expect(typeof hasReducedMotion).toBe('boolean');
});
```

**Changed code**:
```typescript
test('should respect reduced motion preference', async ({ page }) => {
  // Emulate reduced motion preference
  await page.emulateMedia({ reducedMotion: 'reduce' });
  await page.goto('/');

  // Verify CSS actually disables animations and transitions
  // globals.css applies: animation-duration: 0.01ms !important; transition-duration: 0.01ms !important;
  const styles = await page.evaluate(() => {
    const el = document.body;
    const computed = window.getComputedStyle(el);
    return {
      animationDuration: computed.animationDuration,
      transitionDuration: computed.transitionDuration,
    };
  });

  expect(styles.animationDuration).toBe('0.01ms');
  expect(styles.transitionDuration).toBe('0.01ms');

  // Verify that without reduced motion, durations are NOT 0.01ms
  await page.emulateMedia({ reducedMotion: 'no-preference' });
  await page.goto('/');

  const normalStyles = await page.evaluate(() => {
    const el = document.body;
    const computed = window.getComputedStyle(el);
    return {
      animationDuration: computed.animationDuration,
      transitionDuration: computed.transitionDuration,
    };
  });

  expect(normalStyles.animationDuration).not.toBe('0.01ms');
  expect(normalStyles.transitionDuration).not.toBe('0.01ms');
});
```

**Rationale**: The test now: (a) emulates `prefers-reduced-motion: reduce`, (b) verifies the CSS override takes effect (`0.01ms` matching `globals.css` lines 94-101), (c) emulates `no-preference` and verifies durations revert. This gives 4 substantive assertions vs. the previous tautological 1.

## Adversarial Review #2

**Reviewed**: 2026-04-05

| Severity | Finding | Resolution |
|----------|---------|------------|
| LOW | Change 1 assumes desktop nav uses `role="navigation"` with `role="link"` elements. If the actual DOM uses different roles, assertions will fail. | Acceptable -- if the DOM structure doesn't match, the test failure during T3 (local run) will reveal the mismatch, and selectors will be adjusted before merge. This is exactly what the local verification step is for. |
| LOW | Change 2 does a second `page.goto('/')` for the normal-styles check, adding ~1s to the test. | Within the 2s budget (NR2). The second navigation is necessary to get a clean page without the reduced-motion emulation. |

**Drift check**: Plan changes map 1:1 to spec requirements. R1 -> Change 1, R2 -> Change 2, R3 -> no change to chaos.spec.ts. No drift detected.

**Gate**: 0 CRITICAL, 0 HIGH remaining.
