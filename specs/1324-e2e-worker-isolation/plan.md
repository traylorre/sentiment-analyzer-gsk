# Implementation Plan: E2E Worker Isolation

**Branch**: `1324-e2e-worker-isolation` | **Date**: 2026-04-05 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `/specs/1324-e2e-worker-isolation/spec.md`

## Summary

Replace `Date.now()` with `test.info().testId` in 2 E2E test files to eliminate resource name collisions under 4-worker parallel execution. The fix aligns both files with the canonical pattern already used in `config-crud.spec.ts`.

## Technical Context

**Language/Version**: TypeScript (Playwright 1.57+)
**Primary Dependencies**: `@playwright/test`
**Storage**: N/A (test infrastructure only)
**Testing**: Playwright E2E with `--workers=4`
**Target Platform**: CI (GitHub Actions) and local development
**Project Type**: Test infrastructure fix
**Constraints**: Must not change test behavior, only resource naming
**Scale/Scope**: 2 files, ~10 lines changed total

## Constitution Check

*GATE: Must pass before implementation.*

- [x] No new dependencies required
- [x] No infrastructure changes
- [x] No new API endpoints
- [x] Existing test patterns apply (copying from config-crud.spec.ts)
- [x] No backend changes

## Project Structure

### Documentation (this feature)

```text
specs/1324-e2e-worker-isolation/
├── spec.md              # Feature specification (complete)
├── plan.md              # This file
└── tasks.md             # Task breakdown
```

### Source Code (files to modify)

```text
frontend/tests/e2e/
├── magic-link.spec.ts        # CHANGE: Move testEmail into test bodies, use testId
├── dialog-dismissal.spec.ts  # CHANGE: Replace Date.now() with testId in 2 tests
├── config-crud.spec.ts       # REFERENCE: Canonical testId pattern (no changes)
└── helpers/
    └── clean-state.ts        # No changes
```

## Implementation Phases

### Change 1: magic-link.spec.ts -- Move testEmail Into Test Bodies (R1)

**Goal**: Eliminate describe-scoped `Date.now()` email. Construct per-test unique emails inside each `test()` callback using `test.info().testId`.

**File**: `frontend/tests/e2e/magic-link.spec.ts`

**Current code** (line 12):
```typescript
const testEmail = `e2e-magiclink-${Date.now()}@test.example.com`;
```
This is at describe scope -- shared across all 4 tests. `test.info()` is NOT available here.

**Changes**:

1. **Remove** line 12 (`const testEmail = ...` at describe scope)
2. **In test 1** (`requesting magic link shows confirmation message`, line 14): Add at the top of the test body:
   ```typescript
   const testEmail = `e2e-magiclink-${test.info().testId}@test.example.com`;
   ```
3. **In test 2** (`valid magic link token authenticates user`, line 29): Add at the top of the test body:
   ```typescript
   const testEmail = `e2e-magiclink-${test.info().testId}@test.example.com`;
   ```
4. **Tests 3 and 4** (`reused magic link token`, `expired magic link`): These do NOT use `testEmail` -- they navigate directly to `/auth/verify?token=already-used-token` and `/auth/verify?token=expired-old-token`. No changes needed.

**Why inline instead of beforeEach**: Only 2 of 4 tests use `testEmail`. A `beforeEach` would run unnecessary setup for tests 3 and 4. Inline is simpler and matches the pattern in `config-crud.spec.ts`.

### Change 2: dialog-dismissal.spec.ts -- Replace Date.now() With testId (R2)

**Goal**: Replace millisecond-based config names with testId-based names.

**File**: `frontend/tests/e2e/dialog-dismissal.spec.ts`

**Current code** (lines 88, 121):
```typescript
// Line 88 (delete dialog: cancel preserves item)
const configName = `e2e-delete-test-${Date.now()}`;

// Line 121 (delete dialog: escape closes)
const configName = `e2e-escape-test-${Date.now()}`;
```

**Changes**:

1. **Line 88**: Replace with:
   ```typescript
   const configName = `e2e-delete-test-${test.info().testId}`;
   ```
2. **Line 121**: Replace with:
   ```typescript
   const configName = `e2e-escape-test-${test.info().testId}`;
   ```

Both are already inside `test()` callbacks, so `test.info()` is available. No structural changes needed.

## Test Strategy

### Verification

1. **Parallel run**: `npx playwright test --workers=4` -- all tests pass
2. **Stress test**: `npx playwright test --workers=4 --repeat-each=5` -- zero collisions across 5 repetitions
3. **Grep audit**: `grep -r 'Date.now()' frontend/tests/e2e/` returns zero matches in resource naming contexts

### What NOT to test

- No new unit tests needed -- this is a naming change, not logic
- No changes to test assertions -- resource names are only used for creation/lookup within each test

## Risk Assessment

| Risk | Likelihood | Mitigation |
|------|-----------|------------|
| testId format changes in future Playwright version | Very Low | testId is part of Playwright's public API; format is stable |
| Config name too long with testId | Very Low | `e2e-delete-test-` (16 chars) + testId (~12 hex chars) = ~28 chars. Well within typical limits |
| Tests 3-4 in magic-link.spec.ts silently depend on shared email | Very Low | Verified: tests 3-4 use hardcoded token strings, not testEmail |

## Rollback Plan

Single PR with 2-file change. Revert PR if any regression detected.

---

## Adversarial Review #2

**Reviewer**: Adversarial Analysis
**Date**: 2026-04-05

### Findings

| Severity | Finding | Resolution |
|----------|---------|------------|
| MEDIUM | Plan correctly identifies that tests 3-4 in magic-link.spec.ts don't use `testEmail`, but should verify this claim. Test 2 (`valid magic link token`) re-fills the same email -- after the fix, test 2 will use a DIFFERENT email than test 1 (each gets its own testId). This changes behavior: test 2 previously relied on test 1 having requested a magic link for the same email. | This is actually an IMPROVEMENT. Tests sharing state across `test()` boundaries is itself an anti-pattern -- each test should be independent. With the fix, test 2 requests its own magic link, making it properly self-contained. |
| LOW | The plan does not mention updating the `import` statement. `test` is already imported from `@playwright/test` on line 9 of both files, so `test.info()` is available without additional imports. | No action needed. Verified imports are already correct. |

### Gate Statement

Plan is **APPROVED**. The behavioral change in test 2 (own email instead of shared) is a net positive for test isolation. Implementation can proceed.
