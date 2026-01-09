# Feature 1175: Role Assignment Audit Trail

## Problem Statement

Role changes need consistent audit trail tracking for compliance. Currently:
- `_advance_role()` (Feature 1170) sets `role_assigned_at` and `role_assigned_by` correctly
- Future role change sources (Stripe, admin) will need the same pattern
- No centralized helper to ensure consistency

## Root Cause

Role assignment audit logic is currently embedded in `_advance_role()`. As more role change sources are added (Stripe webhooks, admin operations), this pattern needs to be extracted into a reusable helper.

## Solution

Create `create_role_audit_entry()` helper function that:
1. Generates consistent audit field values
2. Supports multiple sources (oauth, stripe, admin)
3. Returns dict ready for DynamoDB update expressions

## Technical Specification

### New Helper Function

**File:** `src/lambdas/shared/auth/audit.py` (new file)

```python
from datetime import UTC, datetime
from typing import Literal

RoleChangeSource = Literal["oauth", "stripe", "admin"]

def create_role_audit_entry(
    source: RoleChangeSource,
    identifier: str,
) -> dict[str, str]:
    """Create audit trail entry for role changes.

    Args:
        source: Origin of role change (oauth, stripe, admin)
        identifier: Provider name (oauth) or admin user ID

    Returns:
        Dict with role_assigned_at and role_assigned_by

    Examples:
        >>> create_role_audit_entry("oauth", "google")
        {'role_assigned_at': '2026-01-08T...', 'role_assigned_by': 'oauth:google'}

        >>> create_role_audit_entry("stripe", "subscription_activated")
        {'role_assigned_at': '2026-01-08T...', 'role_assigned_by': 'stripe:subscription_activated'}

        >>> create_role_audit_entry("admin", "admin-user-123")
        {'role_assigned_at': '2026-01-08T...', 'role_assigned_by': 'admin:admin-user-123'}
    """
    now = datetime.now(UTC)
    return {
        "role_assigned_at": now.isoformat(),
        "role_assigned_by": f"{source}:{identifier}",
    }
```

### Refactor _advance_role()

Update `_advance_role()` to use the new helper:

```python
from src.lambdas.shared.auth.audit import create_role_audit_entry

# In _advance_role():
audit = create_role_audit_entry("oauth", provider)
table.update_item(
    Key={"PK": user.pk, "SK": user.sk},
    UpdateExpression="SET #role = :new_role, role_assigned_at = :assigned_at, role_assigned_by = :assigned_by",
    ExpressionAttributeNames={"#role": "role"},
    ExpressionAttributeValues={
        ":new_role": "free",
        ":assigned_at": audit["role_assigned_at"],
        ":assigned_by": audit["role_assigned_by"],
    },
)
```

## Acceptance Criteria

1. `create_role_audit_entry()` function exists in `audit.py`
2. Function returns dict with `role_assigned_at` and `role_assigned_by`
3. `role_assigned_by` format is `{source}:{identifier}`
4. `_advance_role()` uses the new helper (optional refactor)
5. Unit tests cover all source types
6. Existing role advancement tests still pass

## Out of Scope

- Stripe webhook implementation (separate feature)
- Admin role change UI (separate feature)
- Role downgrade logic

## Dependencies

- **Requires:** Feature 1170 (role advancement) - MERGED
- **Blocks:** Stripe subscription feature, admin role management

## Testing Strategy

### Unit Tests

Create `tests/unit/shared/auth/test_audit.py`:
1. `test_oauth_source_format` - oauth:google format
2. `test_stripe_source_format` - stripe:subscription_activated format
3. `test_admin_source_format` - admin:user-id format
4. `test_timestamp_is_utc_iso` - ISO 8601 format

## References

- Feature 1170: Role Advancement
- `src/lambdas/dashboard/auth.py:1784-1844` (_advance_role)
- `src/lambdas/shared/models/user.py:110-115` (audit fields)
