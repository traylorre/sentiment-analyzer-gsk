# Implementation Plan: Role-Verification Invariant Validator

**Branch**: `1163-role-verification-invariant` | **Date**: 2026-01-06 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `/specs/1163-role-verification-invariant/spec.md`

## Summary

Implement a `@model_validator(mode='after')` on the User model to enforce the role-verification state machine invariants:
1. Reject `anonymous:verified` as impossible state (verification IS the role upgrade)
2. Auto-upgrade `anonymous→free` when verification="verified" is set
3. Reject non-anonymous roles without `verification="verified"`

## Technical Context

**Language/Version**: Python 3.13
**Primary Dependencies**: pydantic (model_validator decorator)
**Storage**: DynamoDB (no schema changes - validation only)
**Testing**: pytest with existing test patterns
**Target Platform**: AWS Lambda
**Project Type**: Web application (backend Lambda)
**Performance Goals**: N/A (validation is O(1) field check)
**Constraints**: Must not break existing User instantiations or DynamoDB deserialization
**Scale/Scope**: Single model change + unit tests

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Gate | Status | Notes |
|------|--------|-------|
| No implementation details in spec | PASS | Spec is technology-agnostic |
| Testable requirements | PASS | FR-001 through FR-005 are all testable |
| Full speckit workflow | PASS | Using specify→plan→tasks→implement |
| Sub-agents for scanning | PASS | Used Explore agent for User model analysis |

## Project Structure

### Documentation (this feature)

```text
specs/1163-role-verification-invariant/
├── spec.md              # Feature specification (DONE)
├── plan.md              # This file
├── tasks.md             # Task breakdown (next: /speckit.tasks)
└── checklists/
    └── requirements.md  # Specification quality checklist (DONE)
```

### Source Code (repository root)

```text
src/lambdas/shared/models/
└── user.py              # Add @model_validator to User class

tests/unit/lambdas/shared/models/
└── test_user_role_verification_invariant.py  # New test file
```

**Structure Decision**: Single file modification + single new test file. Follows existing project patterns.

## Implementation Approach

### Phase 1: Add model_validator to User class

**File**: `src/lambdas/shared/models/user.py`

**Changes Required**:

1. **Import addition** (line ~3):
   ```python
   from pydantic import BaseModel, EmailStr, Field, model_validator
   ```

2. **Add validator method** (after line 115, before properties):
   ```python
   @model_validator(mode='after')
   def validate_role_verification_state(self) -> 'User':
       """Enforce role-verification state machine invariants."""
       # Rule 1 & 2: anonymous + verified → auto-upgrade to free
       if self.role == "anonymous" and self.verification == "verified":
           object.__setattr__(self, 'role', 'free')

       # Rule 3: non-anonymous requires verified
       if self.role != "anonymous" and self.verification != "verified":
           raise ValueError(
               f"Invalid state: {self.role} role requires verified status, "
               f"got verification={self.verification}"
           )

       return self
   ```

**Design Decision**: Auto-upgrade vs Reject

Per spec FR-002, we auto-upgrade `anonymous→free` rather than rejecting. This provides:
- Better UX during verification flows
- Atomic state transition (no intermediate invalid state)
- Simpler calling code (set verification, role auto-corrects)

### Phase 2: Unit Tests

**File**: `tests/unit/lambdas/shared/models/test_user_role_verification_invariant.py`

Test cases matching spec acceptance scenarios:

| Test | Input | Expected |
|------|-------|----------|
| `test_anonymous_none_valid` | role=anonymous, verification=none | PASS |
| `test_anonymous_pending_valid` | role=anonymous, verification=pending | PASS |
| `test_anonymous_verified_auto_upgrades` | role=anonymous, verification=verified | role becomes "free" |
| `test_free_verified_valid` | role=free, verification=verified | PASS |
| `test_free_none_invalid` | role=free, verification=none | ValueError |
| `test_free_pending_invalid` | role=free, verification=pending | ValueError |
| `test_paid_verified_valid` | role=paid, verification=verified | PASS |
| `test_paid_none_invalid` | role=paid, verification=none | ValueError |
| `test_operator_verified_valid` | role=operator, verification=verified | PASS |
| `test_operator_pending_invalid` | role=operator, verification=pending | ValueError |
| `test_roundtrip_preserves_valid_state` | DynamoDB item → User → DynamoDB item | Fields match |
| `test_legacy_item_defaults_valid` | DynamoDB item without role/verification | anonymous:none (valid) |

### Phase 3: Backward Compatibility Verification

Ensure existing tests pass:
- Feature 1162 tests (39 tests for federation fields)
- All existing User model tests
- Integration tests that create Users

**Risk Mitigation**: The validator runs AFTER field assignment, so:
- Default values (anonymous:none) are always valid
- Legacy DynamoDB items without role/verification load with valid defaults
- Explicit valid combinations pass through unchanged

## Dependencies

| Dependency | Status | Impact |
|------------|--------|--------|
| Feature 1162 (federation fields) | PR #613 pending | Must have role & verification fields |
| pydantic model_validator | Available | No new dependencies |

## Complexity Tracking

No constitution violations. This is a minimal change:
- 1 import addition
- 1 method addition (~15 lines)
- 1 new test file (~100 lines)

## Risks and Mitigations

| Risk | Probability | Impact | Mitigation |
|------|-------------|--------|------------|
| Existing tests fail | Low | High | Run full test suite before PR |
| DynamoDB deserialization breaks | Low | High | Legacy items get valid defaults |
| Performance regression | Very Low | Low | O(1) check, negligible overhead |

## Definition of Done

- [ ] `@model_validator` added to User class
- [ ] Import statement added for model_validator
- [ ] All 12+ test cases pass
- [ ] Existing tests pass (no regressions)
- [ ] PR created and merged
