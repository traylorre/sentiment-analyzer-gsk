# Research: OAuth Role Advancement

**Feature**: 1170-oauth-role-advancement
**Date**: 2026-01-07

## Summary

No external research required. All context available from existing codebase:

1. **Role hierarchy**: Confirmed from User model - `RoleType = Literal["anonymous", "free", "paid", "operator"]`
2. **Audit fields**: Confirmed - `role_assigned_at: datetime | None`, `role_assigned_by: str | None`
3. **Implementation pattern**: Follows `_link_provider()` pattern from Feature 1169
4. **DynamoDB update pattern**: Existing pattern in auth.py uses `UpdateItem` with `SET` expressions

## Decisions

| Topic | Decision | Rationale |
|-------|----------|-----------|
| Function placement | Separate `_advance_role()` helper | Single responsibility, testable, follows existing patterns |
| Audit trail format | `role_assigned_by = "oauth:{provider}"` | Consistent with existing `role_assigned_by` examples ("stripe_webhook", "admin:{user_id}") |
| Role comparison | Direct string comparison (`role == "anonymous"`) | Simple, clear, matches existing code patterns |
| Error handling | Silent failure with logging | Follows `_link_provider()` pattern - OAuth must not fail for role issues |

## Alternatives Considered

None applicable - straightforward feature with clear implementation path from existing code patterns.
