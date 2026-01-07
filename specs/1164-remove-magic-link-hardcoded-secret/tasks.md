# Tasks: Remove Hardcoded MAGIC_LINK_SECRET

**Branch**: `1164-remove-magic-link-hardcoded-secret`
**Spec**: [spec.md](./spec.md) | **Plan**: [plan.md](./plan.md)
**Created**: 2026-01-06

## Task Breakdown

### Phase 1: Security Fix

#### Task 1.1: Remove hardcoded fallback and add validation
**Status**: [ ] Not Started
**File**: `src/lambdas/dashboard/auth.py`
**Action**: Replace hardcoded fallback with fail-fast validation
**Acceptance**:
- No hardcoded secret string in code
- RuntimeError raised if env var not set
- Clear error message with guidance

### Phase 2: Dead Code Removal

#### Task 2.1: Remove orphaned _verify_magic_link_signature function
**Status**: [ ] Not Started
**File**: `src/lambdas/dashboard/auth.py`
**Action**: Delete the function that is never called
**Acceptance**: Function no longer exists in codebase

### Phase 3: Test Updates

#### Task 3.1: Add env var fixture to test_auth_us2.py
**Status**: [ ] Not Started
**File**: `tests/unit/lambdas/dashboard/test_auth_us2.py`
**Action**: Add pytest fixture to set MAGIC_LINK_SECRET
**Acceptance**: Fixture sets env var before tests run

#### Task 3.2: Remove tests for deleted function
**Status**: [ ] Not Started
**File**: `tests/unit/lambdas/dashboard/test_auth_us2.py`
**Action**: Remove test_verify_valid_signature and test_verify_invalid_signature
**Acceptance**: No tests reference deleted function

### Phase 4: Verification

#### Task 4.1: Run full test suite
**Status**: [ ] Not Started
**Action**: Execute pytest and verify no regressions
**Acceptance**: All tests pass

#### Task 4.2: Verify no hardcoded secrets remain
**Status**: [ ] Not Started
**Action**: grep -r "default-dev-secret" to confirm removal
**Acceptance**: Zero matches

#### Task 4.3: Commit, push, and create PR
**Status**: [ ] Not Started
**Action**: Create PR with auto-merge enabled
**Acceptance**: PR created and merged

## Summary

| Phase | Tasks | Status |
|-------|-------|--------|
| Phase 1: Security Fix | 1 | Not Started |
| Phase 2: Dead Code | 1 | Not Started |
| Phase 3: Test Updates | 2 | Not Started |
| Phase 4: Verification | 3 | Not Started |
| **Total** | **7** | **0/7 Complete** |
