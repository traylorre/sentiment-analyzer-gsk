# Tasks: E2E Worker Isolation

**Branch**: `1324-e2e-worker-isolation` | **Plan**: [plan.md](./plan.md) | **Spec**: [spec.md](./spec.md)

## Task Breakdown

### T1: Fix magic-link.spec.ts Resource Naming

**File**: `frontend/tests/e2e/magic-link.spec.ts`
**Effort**: Small
**Dependencies**: None

**Implementation**:
1. Remove the describe-scoped `testEmail` variable (line 12):
   ```typescript
   // DELETE: const testEmail = `e2e-magiclink-${Date.now()}@test.example.com`;
   ```
2. In test 1 (`requesting magic link shows confirmation message`), add at the top of the test body (after the opening `{`):
   ```typescript
   const testEmail = `e2e-magiclink-${test.info().testId}@test.example.com`;
   ```
3. In test 2 (`valid magic link token authenticates user`), add at the top of the test body:
   ```typescript
   const testEmail = `e2e-magiclink-${test.info().testId}@test.example.com`;
   ```
4. Tests 3 and 4 do NOT reference `testEmail` -- no changes needed.

**Acceptance**:
- [ ] No `Date.now()` in magic-link.spec.ts
- [ ] Each test that uses `testEmail` constructs its own via `test.info().testId`
- [ ] Tests 3 and 4 still compile and reference hardcoded tokens only

---

### T2: Fix dialog-dismissal.spec.ts Resource Naming

**File**: `frontend/tests/e2e/dialog-dismissal.spec.ts`
**Effort**: Small
**Dependencies**: None

**Implementation**:
1. In `delete dialog: cancel preserves item` test (line 88), replace:
   ```typescript
   // OLD: const configName = `e2e-delete-test-${Date.now()}`;
   // NEW:
   const configName = `e2e-delete-test-${test.info().testId}`;
   ```
2. In `delete dialog: escape closes` test (line 121), replace:
   ```typescript
   // OLD: const configName = `e2e-escape-test-${Date.now()}`;
   // NEW:
   const configName = `e2e-escape-test-${test.info().testId}`;
   ```

**Acceptance**:
- [ ] No `Date.now()` in dialog-dismissal.spec.ts config names
- [ ] Both config names use `test.info().testId`

---

### T3: Verify With Parallel Run

**Effort**: Small
**Dependencies**: T1, T2

**Implementation**:
1. Run full E2E suite with parallel workers:
   ```bash
   cd frontend && npx playwright test --workers=4
   ```
2. Run stress test for collision detection:
   ```bash
   cd frontend && npx playwright test --workers=4 --repeat-each=5
   ```
3. Audit for remaining Date.now() in resource names:
   ```bash
   grep -rn 'Date.now()' frontend/tests/e2e/ --include='*.ts'
   ```
   Verify no remaining instances are used for resource naming (some may exist for timeouts or non-resource purposes -- those are fine).

**Acceptance**:
- [ ] `--workers=4` run passes with zero failures
- [ ] `--repeat-each=5` run passes with zero collision-related failures
- [ ] No `Date.now()` remains in resource name contexts

---

## Task Summary

| Task | Description | Effort | Status |
|------|-------------|--------|--------|
| T1 | Fix magic-link.spec.ts resource naming | Small | Pending |
| T2 | Fix dialog-dismissal.spec.ts resource naming | Small | Pending |
| T3 | Verify with parallel run | Small | Pending |

**Total Effort**: ~30 minutes
**Critical Path**: T1 + T2 (parallel) -> T3

---

## Adversarial Review #3

**Reviewer**: Adversarial Analysis
**Date**: 2026-04-05

### Assessment

Tasks are minimal, correctly scoped, and directly traceable to spec requirements (R1 -> T1, R2 -> T2). No unnecessary complexity. The verification task (T3) covers both functional correctness and collision prevention.

### Gate Statement

Tasks are **READY FOR IMPLEMENTATION**.
