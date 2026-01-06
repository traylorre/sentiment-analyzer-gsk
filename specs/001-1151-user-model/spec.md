# Feature Specification: Add RBAC Fields to User Model

**Feature Branch**: `1151-user-model-role-fields`
**Created**: 2026-01-06
**Status**: Draft
**Phase**: 1.5.2 - RBAC Infrastructure
**Depends On**: Feature 1150 (get_roles_for_user function)

## Context

The `get_roles_for_user()` function (merged in #603) uses defensive `getattr()` calls for three User model fields that don't exist yet:
- `subscription_active`
- `subscription_expires_at`
- `is_operator`

This feature adds these fields to complete the RBAC infrastructure foundation.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - RBAC Role Determination (Priority: P1)

As a system component calling `get_roles_for_user(user)`, I need the User model to have RBAC fields so role determination works correctly instead of always falling back to defaults.

**Why this priority**: Core RBAC functionality - without these fields, `@require_role("paid")` and `@require_role("operator")` can never succeed.

**Independent Test**: Create a User with `subscription_active=True`, call `get_roles_for_user()`, verify `["free", "paid"]` is returned.

**Acceptance Scenarios**:

1. **Given** a User with `subscription_active=True` and `subscription_expires_at` in the future, **When** `get_roles_for_user()` is called, **Then** it returns `["free", "paid"]`
2. **Given** a User with `is_operator=True`, **When** `get_roles_for_user()` is called, **Then** it returns `["free", "paid", "operator"]`
3. **Given** a User with no RBAC fields set (all defaults), **When** `get_roles_for_user()` is called, **Then** it returns `["free"]` (authenticated default)

---

### User Story 2 - DynamoDB Persistence (Priority: P1)

As the system, I need RBAC fields to persist to DynamoDB and restore correctly so role assignments survive Lambda cold starts.

**Why this priority**: Without persistence, role assignments would be lost on every session restore.

**Independent Test**: Create User with RBAC fields, call `to_dynamodb_item()`, then `from_dynamodb_item()`, verify all fields roundtrip correctly.

**Acceptance Scenarios**:

1. **Given** a User with `subscription_active=True`, **When** `to_dynamodb_item()` is called, **Then** the item contains `subscription_active: true`
2. **Given** a DynamoDB item with `subscription_expires_at` timestamp, **When** `from_dynamodb_item()` is called, **Then** User has correctly parsed datetime
3. **Given** a DynamoDB item missing RBAC fields (legacy user), **When** `from_dynamodb_item()` is called, **Then** User has default values (subscription_active=False, is_operator=False)

---

### User Story 3 - Backward Compatibility (Priority: P1)

As a system handling existing users, I need the new fields to have sensible defaults so existing users aren't broken.

**Why this priority**: Production has existing users without these fields - they must continue working.

**Independent Test**: Load a legacy DynamoDB item without RBAC fields, verify User model loads with correct defaults.

**Acceptance Scenarios**:

1. **Given** an existing DynamoDB item without `subscription_active` key, **When** `from_dynamodb_item()` is called, **Then** `subscription_active` defaults to `False`
2. **Given** an existing DynamoDB item without `is_operator` key, **When** `from_dynamodb_item()` is called, **Then** `is_operator` defaults to `False`
3. **Given** an existing DynamoDB item without `subscription_expires_at` key, **When** `from_dynamodb_item()` is called, **Then** `subscription_expires_at` is `None`

---

### Edge Cases

- **Expired subscription**: User has `subscription_active=True` but `subscription_expires_at` is in the past - `get_roles_for_user()` handles this (returns `["free"]`)
- **Operator without subscription**: Edge case - `is_operator=True` but `subscription_active=False` - per spec, operator implies paid, so this should still return operator roles
- **None datetime handling**: `subscription_expires_at=None` means no expiration (lifetime subscription or just not subscribed)

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: User model MUST have `subscription_active: bool` field with default `False`
- **FR-002**: User model MUST have `subscription_expires_at: datetime | None` field with default `None`
- **FR-003**: User model MUST have `is_operator: bool` field with default `False`
- **FR-004**: All new fields MUST be optional (nullable or with defaults) for backward compatibility
- **FR-005**: `to_dynamodb_item()` MUST serialize new fields to DynamoDB format
- **FR-006**: `from_dynamodb_item()` MUST deserialize new fields, using defaults for missing keys
- **FR-007**: Datetime fields MUST be stored in ISO8601 format in DynamoDB

### Key Entities

- **User**: Extended with 3 new RBAC fields alongside existing auth/session fields
  - `subscription_active: bool = False` - Whether user has active paid subscription
  - `subscription_expires_at: datetime | None = None` - When subscription expires (None = no expiry or not subscribed)
  - `is_operator: bool = False` - Administrative flag for operator access

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: All existing User model tests continue to pass (no regression)
- **SC-002**: `get_roles_for_user()` tests pass without using defensive `getattr()` (fields exist)
- **SC-003**: New unit tests achieve 100% coverage of RBAC field serialization/deserialization
- **SC-004**: Integration tests verify DynamoDB roundtrip of RBAC fields

## Technical Notes

### No Migration Required

DynamoDB is schemaless - existing items simply won't have the new keys. The `from_dynamodb_item()` method handles missing keys with defaults.

### Field Placement

Add new fields after the existing merge tracking fields (`merged_to`, `merged_at`) to maintain logical grouping:
1. Primary identifiers
2. Authentication state
3. Preferences
4. Session management (Feature 014)
5. Account merging (Feature 014)
6. **RBAC fields (new - Feature 1151)**

### Type Alignment

- Match existing patterns: use `bool` not `Optional[bool]` for flags with defaults
- Match existing datetime pattern: `datetime | None` for optional timestamps
