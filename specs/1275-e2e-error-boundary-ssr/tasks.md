# Feature 1275: e2e-error-boundary-ssr - Tasks

## Task 1: Refactor ErrorTrigger for SSR-safe flag detection
- **File**: `frontend/src/components/ui/error-trigger.tsx`
- **Type**: Bug fix
- **Dependencies**: None
- **Description**: Split ErrorTrigger into outer (production gate) and inner (hooks-based) components. The inner component uses `useState(false)` + `useEffect` to check `window.__TEST_FORCE_ERROR` after hydration, then throws on re-render if flag is set.
- **Acceptance**: Component compiles without TypeScript errors. Production path has zero hook overhead. Non-production path defers flag check to post-mount.

### Subtasks
- [x] 1.1: Add `useState`, `useEffect` imports from React
- [x] 1.2: Create `ErrorTriggerInner` component with `shouldError` state
- [x] 1.3: Move `window.__TEST_FORCE_ERROR` check into `useEffect([], ...)`
- [x] 1.4: Keep synchronous throw when `shouldError` is `true`
- [x] 1.5: Keep `ErrorTrigger` as outer wrapper with production early-return
- [x] 1.6: Preserve `declare global` Window interface augmentation
- [x] 1.7: Update JSDoc to document SSR-safe behavior

## Task 2: Verify chaos-error-boundary.spec.ts passes (regression)
- **File**: `frontend/tests/e2e/chaos-error-boundary.spec.ts`
- **Type**: Verification
- **Dependencies**: Task 1
- **Description**: Run T022, T023, T024 to confirm no regression from the refactor.
- **Acceptance**: All three tests pass.
- **Status**: TypeScript compiles clean. E2E test execution requires running dev server (out of scope for battleplan; verify in CI).

## Task 3: Verify chaos-accessibility.spec.ts passes (fix confirmation)
- **File**: `frontend/tests/e2e/chaos-accessibility.spec.ts`
- **Type**: Verification
- **Dependencies**: Task 1
- **Description**: Run T026, T027 to confirm the fix resolves the failing tests. T025 (health banner) should also pass as it's unrelated.
- **Acceptance**: All three tests pass, including the two that were previously failing.
- **Status**: TypeScript compiles clean. E2E test execution requires running dev server (out of scope for battleplan; verify in CI).
