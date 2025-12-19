# Research: Consolidate Status Field

**Feature**: 503-consolidate-status-field
**Date**: 2025-12-19

## Research Summary

This feature consolidates boolean status fields into string status fields to enable efficient GSI queries. Research focused on current field usage, migration strategy, and backward compatibility.

## Decision 1: Status Field Values

**Decision**: Use semantic status values that reflect the boolean meaning

| Entity | Boolean | True Value | False Value |
|--------|---------|------------|-------------|
| CONFIGURATION | is_active | "active" | "inactive" |
| ALERT_RULE | is_enabled | "enabled" | "disabled" |
| DIGEST_SETTINGS | enabled | "enabled" | "disabled" |

**Rationale**:
- CONFIGURATION uses "active/inactive" because it represents soft-delete state (visible vs hidden)
- ALERT_RULE and DIGEST_SETTINGS use "enabled/disabled" because they represent feature toggles (on vs off)
- These values align with the GSI `by_entity_status` design which uses `status` as range key

**Alternatives Considered**:
1. Single "active/inactive" for all → Rejected: loses semantic meaning of enable/disable
2. "true/false" strings → Rejected: doesn't improve readability over boolean
3. Numeric 0/1 → Rejected: DynamoDB GSI works better with descriptive strings

## Decision 2: Migration Strategy

**Decision**: In-place migration with backward-compatible reads during transition

**Migration Steps**:
1. Update models to write BOTH boolean and string fields
2. Update read paths to prefer string, fall back to boolean
3. Run migration script to add string fields to all existing items
4. Update models to write ONLY string field
5. Remove boolean field handling from read paths
6. (Optional) Run cleanup to remove boolean fields from items

**Rationale**:
- Zero downtime: no service interruption during migration
- Backward compatibility: existing items still readable during transition
- Atomicity: each item update is atomic via DynamoDB conditional write

**Alternatives Considered**:
1. Big bang migration (stop service, migrate, restart) → Rejected: requires downtime
2. New table with sync → Rejected: overly complex for simple field change
3. Blue/green deployment → Rejected: overkill for data model change

## Decision 3: Boolean Field Removal Timing

**Decision**: Remove boolean fields in Phase 2 (separate PR after migration verified)

**Rationale**:
- Allows verification that all items have status field before removing fallback
- Reduces risk of breaking changes
- Enables rollback if issues discovered

**Alternatives Considered**:
1. Remove immediately with migration → Rejected: no rollback safety
2. Keep forever (dual write) → Rejected: permanent complexity debt

## Decision 4: Read Path Fallback Logic

**Decision**: Use explicit fallback with logging

```python
def get_status(item: dict, entity_type: str) -> str:
    """Get status from item, falling back to boolean if needed."""
    if "status" in item:
        return item["status"]

    # Fallback during migration
    if entity_type == "CONFIGURATION":
        is_active = item.get("is_active", True)
        return "active" if is_active else "inactive"
    else:  # ALERT_RULE, DIGEST_SETTINGS
        is_enabled = item.get("is_enabled", item.get("enabled", True))
        return "enabled" if is_enabled else "disabled"
```

**Rationale**:
- Handles items not yet migrated
- Default to active/enabled preserves existing behavior
- Single function centralizes conversion logic

## Decision 5: TICKER_INFO Exclusion

**Decision**: Exclude TICKER_INFO from this migration

**Rationale**:
- TICKER_INFO is reference data (stock listings), not user data
- Different lifecycle: delisting is permanent, not a toggle
- Not queried via `by_entity_status` GSI
- Separate concern that should be handled independently if needed

## Technical Findings

### Current GSI Configuration (Terraform)

```hcl
global_secondary_index {
  name            = "by_entity_status"
  hash_key        = "entity_type"
  range_key       = "status"
  projection_type = "ALL"
}
```

The GSI is correctly configured. The issue is that items lack the `status` attribute.

### Current Data State (Preprod)

From DynamoDB scan:
- CONFIGURATION items: have `is_active: bool`, no `status`
- ALERT_RULE items: have `is_enabled: bool`, no `status`
- DIGEST_SETTINGS items: have `enabled: bool`, no `status`

### Ingestion Lambda (Already Fixed)

PR #431 updated ingestion handler to query with `status = :status`:
```python
response = table.query(
    IndexName="by_entity_status",
    KeyConditionExpression="entity_type = :et AND status = :status",
    ExpressionAttributeValues={":et": "CONFIGURATION", ":status": "active"},
)
```

This returns 0 results because no items have `status` attribute.

## Risk Assessment

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| Items without status after migration | Low | High | Verification script before removing fallback |
| Performance regression during dual-read | Low | Low | Fallback is simple dict lookup |
| Test failures from model changes | High | Medium | Comprehensive test updates in separate PR |
| Production data corruption | Low | High | Use conditional writes, test in preprod first |

## References

- Terraform GSI definition: `infrastructure/terraform/modules/dynamodb/main.tf:318-328`
- Configuration model: `src/lambdas/shared/models/configuration.py`
- AlertRule model: `src/lambdas/shared/models/alert_rule.py`
- DigestSettings model: `src/lambdas/shared/models/notification.py`
- PR #431 (GSI query changes): Already merged, awaiting data migration
