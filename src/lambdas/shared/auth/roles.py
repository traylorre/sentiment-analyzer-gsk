"""Role assignment logic for RBAC (Feature 1150).

This module provides the get_roles_for_user() function that determines
which roles a user has based on their state.

Roles are additive:
- anonymous: UUID token holders only
- free: Authenticated users (includes anonymous upgrade)
- paid: Active subscription holders (has free + paid)
- operator: Administrative access (has free + paid + operator)
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING

from src.lambdas.shared.auth.enums import Role

if TYPE_CHECKING:
    from src.lambdas.shared.models.user import User


def get_roles_for_user(user: User) -> list[str]:
    """Determine roles based on user state.

    Args:
        user: The User object to evaluate

    Returns:
        List of role strings, ordered by precedence (base role first)

    Examples:
        >>> # Anonymous user
        >>> get_roles_for_user(user_with_auth_type_anonymous)
        ['anonymous']

        >>> # Free authenticated user
        >>> get_roles_for_user(user_with_auth_type_email)
        ['free']

        >>> # Paid user
        >>> get_roles_for_user(user_with_subscription_active)
        ['free', 'paid']

        >>> # Operator
        >>> get_roles_for_user(user_with_is_operator)
        ['free', 'paid', 'operator']
    """
    # Anonymous users get only the anonymous role
    # They cannot have any other roles (security: anonymous cannot be operator)
    if user.auth_type == "anonymous":
        return [Role.ANONYMOUS.value]

    # Authenticated users start with free role
    roles = [Role.FREE.value]

    # Check subscription status (fields may not exist yet - Feature 1151)
    subscription_active = getattr(user, "subscription_active", False)
    subscription_expires_at = getattr(user, "subscription_expires_at", None)

    # Paid role: subscription_active AND not expired
    if subscription_active:
        is_expired = False
        if subscription_expires_at is not None:
            # Compare with current UTC time
            now = datetime.now(UTC)
            # Handle both aware and naive datetimes
            if subscription_expires_at.tzinfo is None:
                # Assume UTC for naive datetimes
                is_expired = subscription_expires_at < now.replace(tzinfo=None)
            else:
                is_expired = subscription_expires_at < now

        if not is_expired:
            roles.append(Role.PAID.value)

    # Operator role: is_operator flag (implies paid access)
    is_operator = getattr(user, "is_operator", False)
    if is_operator:
        # Ensure paid is included if not already (operators get all access)
        if Role.PAID.value not in roles:
            roles.append(Role.PAID.value)
        roles.append(Role.OPERATOR.value)

    return roles
