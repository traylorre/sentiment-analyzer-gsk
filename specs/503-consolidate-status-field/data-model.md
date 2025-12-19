# Data Model: Consolidate Status Field

**Feature**: 503-consolidate-status-field
**Date**: 2025-12-19

## Overview

This feature consolidates boolean status attributes into a single string `status` field to enable efficient GSI queries via the `by_entity_status` index.

## Schema Changes

### Before (Current State)

| Entity | Attribute | Type | Values |
|--------|-----------|------|--------|
| CONFIGURATION | is_active | bool | true, false |
| ALERT_RULE | is_enabled | bool | true, false |
| DIGEST_SETTINGS | enabled | bool | true, false |

### After (Target State)

| Entity | Attribute | Type | Values |
|--------|-----------|------|--------|
| CONFIGURATION | status | string | "active", "inactive" |
| ALERT_RULE | status | string | "enabled", "disabled" |
| DIGEST_SETTINGS | status | string | "enabled", "disabled" |

## Entity Definitions

### CONFIGURATION

```python
class Configuration:
    """User ticker tracking configuration."""

    # Primary keys
    PK: str          # "USER#{user_id}"
    SK: str          # "CONFIG#{config_id}"

    # Entity type (for GSI)
    entity_type: str = "CONFIGURATION"

    # Status (NEW - replaces is_active)
    status: str      # "active" | "inactive"

    # [REMOVED] is_active: bool  # Replaced by status

    # Other fields unchanged
    config_id: str
    user_id: str
    name: str
    tickers: list[dict]
    created_at: str
    updated_at: str
```

### ALERT_RULE

```python
class AlertRule:
    """User price alert rule."""

    # Primary keys
    PK: str          # "USER#{user_id}"
    SK: str          # "ALERT#{alert_id}"

    # Entity type (for GSI)
    entity_type: str = "ALERT_RULE"

    # Status (NEW - replaces is_enabled)
    status: str      # "enabled" | "disabled"

    # [REMOVED] is_enabled: bool  # Replaced by status

    # Other fields unchanged
    alert_id: str
    user_id: str
    ticker: str
    condition: str
    threshold: float
    created_at: str
    updated_at: str
```

### DIGEST_SETTINGS

```python
class DigestSettings:
    """User daily digest preferences."""

    # Primary keys
    PK: str          # "USER#{user_id}"
    SK: str          # "DIGEST_SETTINGS"

    # Entity type (for GSI)
    entity_type: str = "DIGEST_SETTINGS"

    # Status (NEW - replaces enabled)
    status: str      # "enabled" | "disabled"

    # [REMOVED] enabled: bool  # Replaced by status

    # Other fields unchanged
    user_id: str
    frequency: str
    delivery_hour: int
    timezone: str
```

## GSI Query Patterns

### by_entity_status GSI

**Keys**:
- Hash Key: `entity_type` (S)
- Range Key: `status` (S)

**Query Patterns**:

| Use Case | Key Condition | Filter |
|----------|---------------|--------|
| Active configurations | `entity_type = "CONFIGURATION" AND status = "active"` | - |
| Enabled alerts for ticker | `entity_type = "ALERT_RULE" AND status = "enabled"` | `ticker = :ticker` |
| Enabled digest settings | `entity_type = "DIGEST_SETTINGS" AND status = "enabled"` | - |
| Disabled alerts | `entity_type = "ALERT_RULE" AND status = "disabled"` | - |

## Migration Script

### Algorithm

```python
def migrate_item(item: dict) -> dict:
    """Convert boolean status to string status."""
    entity_type = item.get("entity_type")

    if entity_type == "CONFIGURATION":
        is_active = item.get("is_active", True)
        item["status"] = "active" if is_active else "inactive"

    elif entity_type in ("ALERT_RULE", "DIGEST_SETTINGS"):
        # ALERT_RULE uses is_enabled, DIGEST_SETTINGS uses enabled
        is_enabled = item.get("is_enabled", item.get("enabled", True))
        item["status"] = "enabled" if is_enabled else "disabled"

    return item
```

### Execution

```bash
# Dry run (read-only, shows what would change)
python scripts/migrate_status_field.py --table preprod-sentiment-users --dry-run

# Execute migration
python scripts/migrate_status_field.py --table preprod-sentiment-users

# Verify migration
python scripts/migrate_status_field.py --table preprod-sentiment-users --verify
```

## Validation Rules

### Status Field

- MUST be one of: "active", "inactive", "enabled", "disabled"
- MUST match entity type semantics:
  - CONFIGURATION: only "active" or "inactive"
  - ALERT_RULE: only "enabled" or "disabled"
  - DIGEST_SETTINGS: only "enabled" or "disabled"

### State Transitions

| Entity | From | To | Trigger |
|--------|------|-----|---------|
| CONFIGURATION | active | inactive | Soft delete |
| CONFIGURATION | inactive | active | Restore |
| ALERT_RULE | enabled | disabled | User toggles off |
| ALERT_RULE | disabled | enabled | User toggles on |
| DIGEST_SETTINGS | enabled | disabled | User disables digest |
| DIGEST_SETTINGS | disabled | enabled | User enables digest |

## Backward Compatibility

During migration transition:

```python
def get_effective_status(item: dict, entity_type: str) -> str:
    """Get status with fallback to boolean fields."""
    # Prefer string status
    if "status" in item:
        return item["status"]

    # Fallback to boolean (during migration)
    if entity_type == "CONFIGURATION":
        return "active" if item.get("is_active", True) else "inactive"
    else:
        is_enabled = item.get("is_enabled", item.get("enabled", True))
        return "enabled" if is_enabled else "disabled"
```

## No Schema Changes Required

The DynamoDB table schema and GSI definitions remain unchanged. The `by_entity_status` GSI already expects `status` as the range key. This migration adds the missing `status` attribute to existing items.
