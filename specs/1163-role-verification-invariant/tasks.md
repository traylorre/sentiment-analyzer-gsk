# Tasks: Role-Verification Invariant Validator

**Branch**: `1163-role-verification-invariant`
**Spec**: [spec.md](./spec.md) | **Plan**: [plan.md](./plan.md)
**Created**: 2026-01-06

## Task Breakdown

### Phase 1: Core Implementation

#### Task 1.1: Add model_validator import
**Status**: [ ] Not Started
**File**: `src/lambdas/shared/models/user.py`
**Action**: Add `model_validator` to pydantic imports
**Acceptance**: Import statement includes `model_validator`

#### Task 1.2: Implement role-verification validator
**Status**: [ ] Not Started
**File**: `src/lambdas/shared/models/user.py`
**Action**: Add `@model_validator(mode='after')` method to User class
**Acceptance**:
- Method named `validate_role_verification_state`
- Auto-upgrades anonymous:verified → free:verified
- Rejects non-anonymous with non-verified status
- Returns self

### Phase 2: Unit Tests

#### Task 2.1: Create test file for invariant validator
**Status**: [ ] Not Started
**File**: `tests/unit/lambdas/shared/models/test_user_role_verification_invariant.py`
**Action**: Create new test file with comprehensive test cases
**Acceptance**: File exists with proper imports and test class

#### Task 2.2: Test valid state combinations
**Status**: [ ] Not Started
**File**: `tests/unit/lambdas/shared/models/test_user_role_verification_invariant.py`
**Action**: Add tests for all valid states
**Test Cases**:
- `test_anonymous_none_valid`
- `test_anonymous_pending_valid`
- `test_free_verified_valid`
- `test_paid_verified_valid`
- `test_operator_verified_valid`
**Acceptance**: All 5 tests pass

#### Task 2.3: Test auto-upgrade behavior
**Status**: [ ] Not Started
**File**: `tests/unit/lambdas/shared/models/test_user_role_verification_invariant.py`
**Action**: Add test for anonymous:verified auto-upgrade
**Test Cases**:
- `test_anonymous_verified_auto_upgrades_to_free`
**Acceptance**: User created with anonymous:verified has role="free" after construction

#### Task 2.4: Test invalid state rejection
**Status**: [ ] Not Started
**File**: `tests/unit/lambdas/shared/models/test_user_role_verification_invariant.py`
**Action**: Add tests for invalid state combinations
**Test Cases**:
- `test_free_none_raises_valueerror`
- `test_free_pending_raises_valueerror`
- `test_paid_none_raises_valueerror`
- `test_paid_pending_raises_valueerror`
- `test_operator_none_raises_valueerror`
- `test_operator_pending_raises_valueerror`
**Acceptance**: All 6 tests pass with ValueError containing appropriate message

#### Task 2.5: Test backward compatibility
**Status**: [ ] Not Started
**File**: `tests/unit/lambdas/shared/models/test_user_role_verification_invariant.py`
**Action**: Add tests for legacy DynamoDB items
**Test Cases**:
- `test_legacy_item_without_role_verification_valid`
- `test_roundtrip_preserves_valid_state`
**Acceptance**: Legacy items deserialize without error (defaults to anonymous:none)

### Phase 3: Verification

#### Task 3.1: Run full test suite
**Status**: [ ] Not Started
**Action**: Execute `python -m pytest tests/unit/` and verify no regressions
**Acceptance**: All tests pass including Feature 1162 tests

#### Task 3.2: Commit and push
**Status**: [ ] Not Started
**Action**: Commit changes with proper message, push to branch
**Acceptance**: Branch pushed to origin

#### Task 3.3: Create PR
**Status**: [ ] Not Started
**Action**: Create PR with auto-merge enabled
**Acceptance**: PR created, auto-merge with squash enabled

## Summary

| Phase | Tasks | Status |
|-------|-------|--------|
| Phase 1: Core Implementation | 2 | Not Started |
| Phase 2: Unit Tests | 5 | Not Started |
| Phase 3: Verification | 3 | Not Started |
| **Total** | **10** | **0/10 Complete** |

## Dependencies

- Feature 1162 (PR #613) must be merged first OR this branch must be based on 1162 branch
