"""Status field utilities for entity status management.

This module provides constants and helper functions for managing entity status
across CONFIGURATION, ALERT_RULE, and DIGEST_SETTINGS entities.

The status field is a string that replaces boolean fields (is_active, is_enabled, enabled)
to enable efficient GSI queries via the by_entity_status index.
"""

from typing import Any

# Status constants
ACTIVE = "active"
INACTIVE = "inactive"
ENABLED = "enabled"
DISABLED = "disabled"

# Valid status values by entity type
CONFIGURATION_STATUSES = frozenset([ACTIVE, INACTIVE])
ALERT_RULE_STATUSES = frozenset([ENABLED, DISABLED])
DIGEST_SETTINGS_STATUSES = frozenset([ENABLED, DISABLED])


def get_status_from_item(item: dict[str, Any], entity_type: str) -> str:
    """Get status from DynamoDB item with backward compatibility for boolean fields.

    This function supports both the new string status field and legacy boolean fields
    during the migration transition period.

    Args:
        item: DynamoDB item dictionary
        entity_type: Entity type (CONFIGURATION, ALERT_RULE, DIGEST_SETTINGS)

    Returns:
        Status string: "active", "inactive", "enabled", or "disabled"
    """
    # Prefer string status field if present
    if "status" in item:
        return item["status"]

    # Fallback to boolean fields during migration
    if entity_type == "CONFIGURATION":
        is_active = item.get("is_active", True)
        return ACTIVE if is_active else INACTIVE

    if entity_type == "ALERT_RULE":
        is_enabled = item.get("is_enabled", True)
        return ENABLED if is_enabled else DISABLED

    if entity_type == "DIGEST_SETTINGS":
        enabled = item.get("enabled", False)  # Digest defaults to disabled
        return ENABLED if enabled else DISABLED

    # Unknown entity type - return active as safe default
    return ACTIVE


def is_status_active(status: str) -> bool:
    """Check if a status value represents an active/enabled state.

    Args:
        status: Status string

    Returns:
        True if status is "active" or "enabled"
    """
    return status in (ACTIVE, ENABLED)


def validate_status(status: str, entity_type: str) -> bool:
    """Validate that a status value is valid for the given entity type.

    Args:
        status: Status string to validate
        entity_type: Entity type

    Returns:
        True if status is valid for entity type
    """
    if entity_type == "CONFIGURATION":
        return status in CONFIGURATION_STATUSES

    if entity_type in ("ALERT_RULE", "DIGEST_SETTINGS"):
        return status in ALERT_RULE_STATUSES

    return False
