# Tasks: User Model Federation Fields

**Feature**: 1162-user-model-federation
**Branch**: `1162-user-model-federation`
**Created**: 2026-01-07
**Total Tasks**: 8

## Task Summary

| Phase | Description | Tasks | Parallelizable |
|-------|-------------|-------|----------------|
| Phase 1 | Setup | 1 | 0 |
| Phase 2 | Foundational (ProviderMetadata) | 2 | 1 |
| Phase 3 | User Story 1+2: Role & Provider Fields | 3 | 2 |
| Phase 4 | Polish & Validation | 2 | 1 |

## Dependencies

```
Phase 1 (Setup)
    ↓
Phase 2 (ProviderMetadata class)
    ↓
Phase 3 (User model fields)
    ↓
Phase 4 (Polish)
```

---

## Phase 1: Setup

**Goal**: Verify current state and establish baseline

- [x] T001 Verify current User model structure in `src/lambdas/shared/models/user.py`

---

## Phase 2: Foundational (ProviderMetadata Class)

**Goal**: Create the ProviderMetadata nested model required by User

- [x] T002 Create ProviderMetadata class in `src/lambdas/shared/models/user.py`
- [x] T003 [P] Write unit tests for ProviderMetadata in `tests/unit/lambdas/shared/models/test_user_federation_fields.py`

**ProviderMetadata Fields**:
- `sub: str | None` (OAuth subject claim)
- `email: str | None`
- `avatar: str | None`
- `linked_at: datetime` (required)
- `verified_at: datetime | None`

---

## Phase 3: User Story 1+2 - Role & Provider Fields

**Goal**: Add 9 federation fields to User model with backward compatibility

**Story 1 Test**: Create user with linked_providers, verify provider_metadata populated
**Story 2 Test**: Create user with role, verify role value persisted

- [x] T004 [US1+2] Add new fields to User class in `src/lambdas/shared/models/user.py`:
  - `role: Literal["anonymous", "free", "paid", "operator"]` (default: "anonymous")
  - `verification: Literal["none", "pending", "verified"]` (default: "none")
  - `pending_email: str | None` (default: None)
  - `primary_email: str | None` (default: None, with alias "email")
  - `linked_providers: list[Literal["email", "google", "github"]]` (default: [])
  - `provider_metadata: dict[str, ProviderMetadata]` (default: {})
  - `last_provider_used: Literal["email", "google", "github"] | None` (default: None)
  - `role_assigned_at: datetime | None` (default: None)
  - `role_assigned_by: str | None` (default: None)

- [x] T005 [P] [US1+2] Add field alias for backward compatibility: `email` → `primary_email` in `src/lambdas/shared/models/user.py`

- [x] T006 [P] [US1+2] Write unit tests for new User fields in `tests/unit/lambdas/shared/models/test_user_federation_fields.py`:
  - Test default values
  - Test serialization with new fields
  - Test backward compatibility (existing records without new fields)
  - Test `email` alias works for `primary_email`

---

## Phase 4: Polish & Validation

**Goal**: Add deprecation markers and verify all tests pass

- [x] T007 Add deprecation docstrings to `auth_type` and `is_operator` fields in `src/lambdas/shared/models/user.py`

- [x] T008 [P] Run full test suite and verify no regressions (2747 tests pass)

---

## Implementation Strategy

**MVP Scope**: Phases 1-3 (T001-T006)
- Delivers all 9 federation fields
- Unit tests for new functionality
- Backward compatible with existing records

**Parallel Execution**:
- T003 can run in parallel after T002
- T005 and T006 can run in parallel after T004

**Test Coverage Requirements**:
- New ProviderMetadata class: 100%
- New User fields: 100%
- Backward compatibility: at least 1 test case

---

## Completion Checklist

- [x] ProviderMetadata class exists with all fields
- [x] User model has all 9 new fields
- [x] `email` alias works for `primary_email`
- [x] Existing User records load without errors
- [x] All unit tests pass (39 new tests, 2747 total)
- [x] Deprecation markers on `auth_type` and `is_operator`
