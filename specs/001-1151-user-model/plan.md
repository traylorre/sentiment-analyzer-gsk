# Implementation Plan: Add RBAC Fields to User Model

## Overview

Add 3 RBAC fields to User model to support `get_roles_for_user()` function.

## Implementation Steps

### Step 1: Add Fields to User Model

**File**: `src/lambdas/shared/models/user.py`

Add after line ~44 (after `merged_at` field):

```python
# Feature 1151 - RBAC fields
subscription_active: bool = False
subscription_expires_at: datetime | None = None
is_operator: bool = False
```

### Step 2: Update to_dynamodb_item()

**File**: `src/lambdas/shared/models/user.py`

Add serialization for new fields in `to_dynamodb_item()` method:

```python
"subscription_active": self.subscription_active,
"is_operator": self.is_operator,
```

For `subscription_expires_at`, only include if not None:
```python
if self.subscription_expires_at:
    item["subscription_expires_at"] = self.subscription_expires_at.isoformat()
```

### Step 3: Update from_dynamodb_item()

**File**: `src/lambdas/shared/models/user.py`

Add deserialization with defaults for missing keys:

```python
subscription_active=item.get("subscription_active", False),
subscription_expires_at=datetime.fromisoformat(item["subscription_expires_at"]) if item.get("subscription_expires_at") else None,
is_operator=item.get("is_operator", False),
```

### Step 4: Add Unit Tests

**File**: `tests/unit/lambdas/shared/models/test_user.py`

Add tests for:
1. Default values on new User instance
2. `to_dynamodb_item()` includes RBAC fields
3. `from_dynamodb_item()` parses RBAC fields
4. `from_dynamodb_item()` uses defaults for legacy items
5. Datetime roundtrip for `subscription_expires_at`

## Verification

1. Run existing User model tests - must pass
2. Run new RBAC field tests
3. Run `get_roles_for_user()` tests - should still pass (uses getattr defensively)
4. Run full unit test suite

## Risk Assessment

- **Low risk**: Adding optional fields with defaults is backward compatible
- **No migration**: DynamoDB is schemaless
- **No breaking changes**: All new fields are optional
