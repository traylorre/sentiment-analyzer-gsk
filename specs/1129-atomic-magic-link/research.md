# Research: Atomic Magic Link Token Consumption

**Feature**: 1129-atomic-magic-link
**Date**: 2026-01-05

## Summary

Research complete - the atomic function already exists in the codebase. This feature is a routing change to use it.

## Existing Atomic Implementation

### Decision: Use existing `verify_and_consume_token()`

**Location**: `/home/traylorre/projects/sentiment-analyzer-gsk/src/lambdas/dashboard/auth.py:1236-1360`

**Key Features**:
1. Uses DynamoDB conditional update: `ConditionExpression="used = :false"`
2. Single atomic operation - no race window
3. Records audit fields: `used_at`, `used_by_ip`
4. Proper error handling via custom exceptions

**Rationale**: This function was implemented in feature 014 and has comprehensive test coverage. Rewriting would be duplicative and error-prone.

### Alternatives Considered

1. **Rewrite atomic logic in router** - Rejected (violates DRY, function already exists)
2. **Add locking layer** - Rejected (DynamoDB conditional updates are the correct pattern)
3. **Use transactions** - Rejected (overkill for single-item update)

## Current Vulnerable Pattern

**Location**: `/home/traylorre/projects/sentiment-analyzer-gsk/src/lambdas/dashboard/auth.py:1364-1476`

**Pattern**: `verify_magic_link()` uses:
1. `get_item()` to fetch token
2. In-memory validation
3. `update_item()` without condition

**Vulnerability**: Between steps 1 and 3, another request can consume the same token.

## Router Integration Point

**Location**: `/home/traylorre/projects/sentiment-analyzer-gsk/src/lambdas/dashboard/router_v2.py:348`

**Current Call**: `auth_service.verify_magic_link(token)`

**Required Change**: `auth_service.verify_and_consume_token(token, client_ip)`

## Error Handling Already Exists

The router already handles the error types from the atomic function:
- `TokenAlreadyUsedError` → 409 Conflict (line 352-355)
- `TokenExpiredError` → 410 Gone (line 356-359)

## References

- DynamoDB Conditional Writes: https://docs.aws.amazon.com/amazondynamodb/latest/developerguide/Expressions.ConditionExpressions.html
- Feature 014 Implementation: Original atomic token verification
