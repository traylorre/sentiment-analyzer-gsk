# Tasks -- Feature 1345: Improve chaos-accessibility.spec.ts Scope

## Task Dependencies

```
T1 (discover selector) ──> T2 (scope AxeBuilder)
                       ──> T2a (optional: add data-testid to component)
T2 ──> T5 (verify)
T3 (document color contrast) ──> T5
T4 (delete T027 + update JSDoc) ──> T5
```

T1 must be done first (determines selector). T2-T4 are independent of each other.

## Tasks

### T1: Discover Error Boundary Container Selector
**File**: Read-only inspection of ErrorBoundary component
**Action**: Find the fallback render output and identify a stable CSS selector
**Details**:
- Read `frontend/src/components/ErrorBoundary.tsx` (or wherever the component lives)
- Find the fallback UI render path (the JSX returned when `hasError` is true)
- Look for: `data-testid`, `id`, `role` attribute, or semantic element on the outermost
  container of the fallback
- Record the selector (e.g., `[data-testid="error-boundary-fallback"]`, `#error-fallback`,
  `[role="alert"]`, or `.error-boundary-container`)
- If NO stable selector exists, document this and proceed to T2a

**Output**: A CSS selector string to use in `.include()`, or a determination that T2a is
needed.

**Acceptance**: A concrete selector is identified, or T2a is flagged as required.

---

### T2a (CONDITIONAL): Add data-testid to ErrorBoundary Component
**File**: ErrorBoundary component (location determined in T1)
**Action**: Add `data-testid="error-boundary-fallback"` to the fallback container element
**Condition**: Only execute if T1 finds no stable selector
**Details**:
- Add the attribute to the outermost element in the fallback render
- Do NOT change any styling, behavior, or other attributes
- This is a minimal production code change for test infrastructure purposes

**Acceptance**: The error boundary fallback renders with `data-testid="error-boundary-fallback"`
visible in the DOM when `__TEST_FORCE_ERROR` is true. No visual or behavioral changes.

---

### T2: Scope AxeBuilder to Error Boundary Container
**File**: `frontend/tests/e2e/chaos-accessibility.spec.ts`
**Action**: Add `.include()` to the AxeBuilder chain in T026 test
**Details**:
- Using the selector from T1 (or `[data-testid="error-boundary-fallback"]` from T2a),
  add `.include(selector)` to the AxeBuilder chain
- The chain becomes:
  ```typescript
  const results = await new AxeBuilder({ page })
    .include('SELECTOR_FROM_T1')
    .withTags(['wcag2a', 'wcag2aa', 'wcag21a', 'wcag21aa'])
    .disableRules(['color-contrast'])
    .analyze();
  ```
- Add a comment above explaining:
  - Why scoping: explicit intent, future-proofing for partial error boundaries
  - What the selector targets: the error boundary fallback container from `<ComponentName>`
  - That this does NOT change which rules are checked, only the DOM scope

**Acceptance**: `AxeBuilder.include()` is called with a valid selector. The axe-core scan
returns results scoped to the error boundary container. Test still passes (same violations
found within the scoped area).

---

### T3: Expand Color Contrast Exclusion Documentation
**File**: `frontend/tests/e2e/chaos-accessibility.spec.ts`
**Action**: Replace the existing 2-line comment above `disableRules`
**Details**:
- Replace:
  ```
  // Run axe-core scan — exclude color-contrast which is a known issue in dark theme
  // error boundary (tracked separately). Testing structural a11y here, not theme colors.
  ```
- With:
  ```
  // Exclude color-contrast rule: The error boundary's dark theme fallback has
  // insufficient contrast ratios on secondary text (gray-on-dark-gray). This is
  // a KNOWN issue tracked in the project backlog. Fixing requires a design review
  // of the error boundary color palette. This exclusion applies ONLY to this test
  // (error boundary fallback), not to main dashboard a11y tests.
  ```

**Acceptance**: The comment clearly states WHAT the issue is, WHERE it's tracked, and
SCOPE of the exclusion. No code changes beyond the comment.

---

### T4: Delete T027 and Update File-Level JSDoc
**File**: `frontend/tests/e2e/chaos-accessibility.spec.ts`
**Action**: Remove T027 test block and update file documentation
**Details**:

1. Delete the entire T027 test (lines 71-113):
   ```typescript
   // T027: Error boundary buttons are keyboard-focusable
   test('error boundary buttons are keyboard-focusable with accessible labels', async ({
     page,
   }) => { ... });
   ```

2. Replace the file-level JSDoc (lines 6-19) with:
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

3. Verify all imports are still used after T027 deletion:
   - `waitForAccessibilityTree` -- still used by T026 (lines 43-47)
   - `AxeBuilder` -- still used by T026
   - All imports should remain

**Acceptance**: File has exactly 1 `test(...)` call. File-level JSDoc mentions "automated
axe-core scanning" as the sole scope. No unused imports. T027 is gone.

---

### T5: Verification
**Action**: Read-only verification (no file changes)
**Details**:
1. Count `test(` calls in `chaos-accessibility.spec.ts` -- must be exactly 1
2. Verify `AxeBuilder` chain includes `.include()` with a selector
3. Verify color contrast comment has 4+ lines explaining the exclusion
4. Verify file-level JSDoc does NOT mention "keyboard-focusable"
5. Verify `chaos-error-boundary.spec.ts` T024 still tests the same 3 buttons:
   - `page.getByRole('button', { name: /try again/i })`
   - `page.getByRole('button', { name: /reload page/i })`
   - `page.getByRole('button', { name: /go home/i })`
6. Verify no unused imports in `chaos-accessibility.spec.ts`
7. Run `npx playwright test chaos-accessibility --project=chromium` if local server available
8. Verify TypeScript compiles: `cd frontend && npx tsc --noEmit`
9. If T2a was executed, verify the ErrorBoundary component renders `data-testid` in the
   fallback DOM

**Acceptance**: All checks pass. Zero test regressions. T024 coverage confirmed.

---

## Appendix: Adversarial Review #3

### READY FOR IMPLEMENTATION gate

| Criterion | Status | Evidence |
|-----------|--------|----------|
| All FRs mapped to tasks | PASS | FR-001->T2, FR-002->T2 comment, FR-003->T3, FR-004->T4, FR-005->T4 |
| All NFRs addressed | PASS | NFR-001->T5 step 5, NFR-002->T1+T2a, NFR-003->T4 |
| Success criteria testable | PASS | All 7 criteria map to T5 verification steps |
| No ambiguous acceptance criteria | PASS | T1 output explicitly defines selector or flags T2a |
| Risk mitigations documented | PASS | Selector discovery has 3-option fallback plan |
| Dependencies explicit | PASS | T1 before T2/T2a, T2-T4 independent, T5 last |
| File list complete | PASS | Primary: chaos-accessibility.spec.ts. Conditional: ErrorBoundary component |
| No scope creep | PASS | Does not modify error-boundary spec or fix contrast issue |
| Conditional task documented | PASS | T2a clearly marked CONDITIONAL with trigger criteria |

**VERDICT: READY FOR IMPLEMENTATION**
