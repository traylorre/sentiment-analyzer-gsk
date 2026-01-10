# Feature Specification: Role Enum Centralization

**Feature Branch**: `1184-role-enum-centralization`
**Created**: 2026-01-10
**Status**: Draft
**Input**: A18: Centralize Role/Tier enum in src/lambdas/shared/auth/enums.py. Define ANONYMOUS, FREE, PAID, OPERATOR roles. Update User model, @require_role decorator, and JWT generation to use this single source. Reject tokens without roles claim with 401. Phase 1.5 RBAC foundation.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Developer Imports Role Enum from Single Source (Priority: P1)

A developer working on the authentication system needs to use the Role enum. They import it from a single, canonical location (`src/lambdas/shared/auth/enums.py`) rather than hunting through multiple files.

**Why this priority**: Code organization and maintainability are foundational. Scattered enum definitions lead to import confusion, potential inconsistencies, and harder-to-maintain code.

**Independent Test**: Can be tested by verifying all Role enum usages across the codebase import from `enums.py` and the old `constants.py` file is removed.

**Acceptance Scenarios**:

1. **Given** a developer needs the Role enum, **When** they search for the canonical location, **Then** they find it in `src/lambdas/shared/auth/enums.py`
2. **Given** the old `constants.py` file, **When** the migration is complete, **Then** the file is deleted and no imports reference it

---

### User Story 2 - System Validates Role at Decoration Time (Priority: P1)

When a developer applies `@require_role("invalid")` to an endpoint, the system catches the typo at application startup rather than at runtime when a user hits the endpoint.

**Why this priority**: Early error detection prevents production bugs and improves developer experience.

**Independent Test**: Can be tested by attempting to decorate an endpoint with an invalid role and verifying `InvalidRoleError` is raised at import time.

**Acceptance Scenarios**:

1. **Given** a valid role string "operator", **When** used in @require_role, **Then** decoration succeeds
2. **Given** an invalid role string "admin", **When** used in @require_role, **Then** InvalidRoleError is raised at decoration time with descriptive message

---

### User Story 3 - AuthType Enum Consolidated (Priority: P2)

The `AuthType` enum (currently in `auth_middleware.py`) is moved to `enums.py` so all auth-related enums are in one place.

**Why this priority**: Consistency with the Role enum centralization. Reduces cognitive load for developers.

**Independent Test**: Can be tested by verifying AuthType imports come from `enums.py` and no duplicate definitions exist.

**Acceptance Scenarios**:

1. **Given** the AuthType enum in auth_middleware.py, **When** migration is complete, **Then** AuthType is defined in enums.py
2. **Given** code importing AuthType, **When** the migration is complete, **Then** all imports use `from .enums import AuthType`

---

### Edge Cases

- What happens when a module imports from the old location after migration? Build/lint should fail.
- How does the system handle circular imports? The enums.py should have no dependencies on other auth modules.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: System MUST define a single `Role` StrEnum in `src/lambdas/shared/auth/enums.py` with values: ANONYMOUS, FREE, PAID, OPERATOR
- **FR-002**: System MUST define a single `AuthType` StrEnum in `src/lambdas/shared/auth/enums.py` with values: anonymous, email, google, github
- **FR-003**: System MUST provide `VALID_ROLES` frozenset for O(1) role validation
- **FR-004**: System MUST delete `src/lambdas/shared/auth/constants.py` after migration
- **FR-005**: System MUST update all imports across the codebase to use the new `enums.py` location
- **FR-006**: The `enums.py` module MUST have no imports from other auth modules (prevents circular dependencies)
- **FR-007**: System MUST maintain backward compatibility - no runtime behavior changes, only import location changes

### Key Entities

- **Role**: Enum representing user access levels (ANONYMOUS < FREE < PAID < OPERATOR)
- **AuthType**: Enum representing authentication methods (anonymous, email, google, github)
- **VALID_ROLES**: Immutable set for O(1) validation at decoration time

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: All Role enum usages across the codebase import from `src/lambdas/shared/auth/enums.py`
- **SC-002**: All AuthType enum usages across the codebase import from `src/lambdas/shared/auth/enums.py`
- **SC-003**: The file `src/lambdas/shared/auth/constants.py` no longer exists
- **SC-004**: All existing unit tests pass without modification (behavioral compatibility)
- **SC-005**: `ruff check` and `ruff format` pass with no errors
- **SC-006**: No circular import errors when loading the auth modules

## Assumptions

- The existing Role enum in `constants.py` has the correct values (ANONYMOUS, FREE, PAID, OPERATOR)
- The existing AuthType enum in `auth_middleware.py` has the correct values (anonymous, email, google, github)
- This is a pure refactoring task with no behavior changes
- The `enums.py` file does not currently exist and will be created

## Out of Scope

- Adding new roles or auth types
- Changing role hierarchy or permissions
- Modifying the @require_role decorator behavior
- JWT claim changes (that's a separate feature)
