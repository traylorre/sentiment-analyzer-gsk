# Implementation Plan: Accessibility Timeout Stack Fix

**Branch**: `1272-a11y-timeout-stack` | **Date**: 2026-03-28 | **Spec**: [spec.md](spec.md)
**Input**: Feature specification from `specs/1272-a11y-timeout-stack/spec.md`

## Summary

Fix three accessibility tests in `chaos-accessibility.spec.ts` that fail in CI by stacking multiple long-running operations (triggerHealthBanner + waitForAccessibilityTree + AxeBuilder.analyze). The fix applies three complementary strategies: (1) reduce the `waitForAccessibilityTree` default timeout from 5000ms to 2000ms, (2) set an explicit per-test timeout of 30s for the accessibility describe block, and (3) scope AxeBuilder scans to the relevant component where a stable selector exists.

## Technical Context

**Language/Version**: TypeScript (Playwright test files targeting Node.js 18+)
**Primary Dependencies**: `@playwright/test ^1.57.0`, `@axe-core/playwright`
**Storage**: N/A (test infrastructure only)
**Testing**: Playwright Test runner (`npx playwright test`)
**Target Platform**: CI runners (GitHub Actions) and local dev machines
**Project Type**: Web application (frontend E2E tests)
**Constraints**: Must work across all 5 Playwright projects (Mobile Chrome, Mobile Safari, Desktop Chrome, Firefox, WebKit)
**Scale/Scope**: 2 files modified, ~5 discrete edits

## Constitution Check

| Gate | Status | Notes |
|------|--------|-------|
| Unit test accompaniment | N/A | This IS a test fix |
| GPG-signed commits | PASS | Will use `git commit -S` |
| Pipeline bypass prohibition | PASS | No bypasses |
| Feature branch workflow | PASS | On branch `1272-a11y-timeout-stack` |
| Environment testing matrix | PASS | E2E tests run in CI |
| Local SAST | N/A | No Python code changes |
| Tech debt tracking | PASS | This feature reduces tech debt |

**Verdict**: PASS

## Project Structure

### Documentation (this feature)

```text
specs/1272-a11y-timeout-stack/
├── plan.md              # This file
├── research.md          # Phase 0 output
├── spec.md              # Feature specification
├── checklists/
│   └── requirements.md  # Quality checklist
└── tasks.md             # Phase 2 output
```

### Source Code (files to modify)

```text
frontend/tests/e2e/
├── chaos-accessibility.spec.ts   # T025, T026, T027 (add setTimeout, scope AxeBuilder)
└── helpers/
    └── a11y-helpers.ts           # Reduce default timeout from 5000ms to 2000ms
```

**Structure Decision**: No new files. All changes are edits to existing test files.

## Phase 0: Research

See [research.md](research.md) for full analysis including:
- R1: Timeout stack analysis with timing breakdown
- R2: waitForAccessibilityTree default timeout analysis
- R3: AxeBuilder.include() scoping API
- R4: test.setTimeout() codebase patterns
- R5: Playwright default timeout behavior
- R6: Error boundary DOM structure analysis

## Phase 1: Design

### Change 1: a11y-helpers.ts -- Reduce Default Timeout

```typescript
// Before
const { selector, attributes = [], timeout = 5000 } = options;

// After
const { selector, attributes = [], timeout = 2000 } = options;
```

**Rationale**: ARIA attributes compute in <200ms. The 5000ms default inflates worst-case timing budget by 3s unnecessarily. The 2000ms default provides 10x headroom over expected resolution time.

### Change 2: chaos-accessibility.spec.ts -- Add test.setTimeout()

```typescript
test.describe('Chaos: Accessibility During Degradation', () => {
  test.setTimeout(30_000);  // a11y tests stack triggerHealthBanner + waitForAccessibilityTree + AxeBuilder

  test.beforeEach(async ({ page }) => {
    // ...
  });
```

**Rationale**: Follows existing codebase pattern (8 other files use this). Documents that a11y tests legitimately take longer due to axe-core scanning overhead.

### Change 3: chaos-accessibility.spec.ts -- Scope AxeBuilder in T025

```typescript
// Before
const results = await new AxeBuilder({ page })
  .withTags(['wcag2a', 'wcag2aa', 'wcag21a', 'wcag21aa'])
  .analyze();

// After (T025 only -- health banner has [role="alert"])
const results = await new AxeBuilder({ page })
  .include('[role="alert"]')
  .withTags(['wcag2a', 'wcag2aa', 'wcag21a', 'wcag21aa'])
  .analyze();
```

**Rationale**: Scoping to `[role="alert"]` reduces DOM traversal from hundreds of nodes to ~5-10. This is the health banner's semantic selector -- stable, not tied to CSS classes.

### Change 4: chaos-accessibility.spec.ts -- T026 AxeBuilder (no scoping)

Per AR#1-F2, the error boundary fallback has no stable CSS selector without modifying application code (out of scope). The full-page scan is retained. The other optimizations (reduced waitForAccessibilityTree timeout + explicit test timeout) provide sufficient headroom.

### Change 5: chaos-accessibility.spec.ts -- Replace beforeEach waitForTimeout

```typescript
// Before
test.beforeEach(async ({ page }) => {
  await page.goto('/');
  await page.waitForTimeout(2000);
});

// After
test.beforeEach(async ({ page }) => {
  await page.goto('/');
  await page.waitForLoadState('networkidle');
});
```

**Rationale**: The 2000ms blind wait exists for React hydration. `waitForLoadState('networkidle')` waits for the actual event (no network requests for 500ms) which is both faster and more reliable. This may overlap with Feature 1271 -- whoever merges first addresses it.

### No New Data Models or Contracts

This feature modifies test infrastructure only.

## Complexity Tracking

No constitution violations. No complexity justification needed.

## Adversarial Review of Plan

**Highest-risk change**: Change 1 (reducing waitForAccessibilityTree default). If any future caller depends on the 5000ms budget, it could fail. Mitigated by: (a) currently no other callers, (b) callers can pass explicit timeout to override default.

**Most likely rework**: Change 5 (beforeEach replacement) may conflict with Feature 1271 if both target the same line. Trivial merge resolution.

**Gate**: READY FOR TASKS
