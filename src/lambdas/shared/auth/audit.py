"""Role assignment audit trail helpers (Feature 1175).

Provides consistent audit field generation for role changes.
Supports multiple sources: OAuth, Stripe webhooks, admin operations.
"""

from datetime import UTC, datetime
from typing import Literal

RoleChangeSource = Literal["oauth", "stripe", "admin"]


def create_role_audit_entry(
    source: RoleChangeSource,
    identifier: str,
) -> dict[str, str]:
    """Create audit trail entry for role changes.

    Generates role_assigned_at and role_assigned_by fields for DynamoDB updates.
    Follows consistent format: {source}:{identifier} for attribution.

    Args:
        source: Origin of role change (oauth, stripe, admin)
        identifier: Context-specific identifier:
            - oauth: provider name (google, github)
            - stripe: event type (subscription_activated, subscription_cancelled)
            - admin: admin user ID

    Returns:
        Dict with role_assigned_at (ISO 8601 UTC) and role_assigned_by

    Examples:
        >>> create_role_audit_entry("oauth", "google")
        {'role_assigned_at': '2026-01-08T12:00:00+00:00', 'role_assigned_by': 'oauth:google'}

        >>> create_role_audit_entry("stripe", "subscription_activated")
        {'role_assigned_at': '2026-01-08T12:00:00+00:00', 'role_assigned_by': 'stripe:subscription_activated'}

        >>> create_role_audit_entry("admin", "admin-user-123")
        {'role_assigned_at': '2026-01-08T12:00:00+00:00', 'role_assigned_by': 'admin:admin-user-123'}
    """
    now = datetime.now(UTC)
    return {
        "role_assigned_at": now.isoformat(),
        "role_assigned_by": f"{source}:{identifier}",
    }
