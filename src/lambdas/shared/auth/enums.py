"""Canonical enum definitions for auth RBAC (Feature 1184).

This module defines the valid roles used throughout the application.
Roles are validated at decoration time to catch typos early.

All auth-related enums should be defined here to ensure a single source of truth.
"""

from __future__ import annotations

from enum import StrEnum


class Role(StrEnum):
    """Canonical user roles for role-based access control.

    Roles are additive:
    - anonymous: UUID token holders only
    - free: Authenticated users (includes anonymous upgrade)
    - paid: Active subscription holders (has free + paid)
    - operator: Administrative access (has free + paid + operator)
    """

    ANONYMOUS = "anonymous"
    FREE = "free"
    PAID = "paid"
    OPERATOR = "operator"


# Immutable set for O(1) validation at decoration time
VALID_ROLES: frozenset[str] = frozenset(role.value for role in Role)
