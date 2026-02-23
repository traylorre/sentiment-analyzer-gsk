# Implementation Plan: OAuth Role Advancement

**Branch**: `1170-oauth-role-advancement` | **Date**: 2026-01-07 | **Spec**: [spec.md](spec.md)
**Input**: Feature specification from `/specs/1170-oauth-role-advancement/spec.md`

## Summary

Add role advancement logic to OAuth flow. When users complete OAuth authentication with role="anonymous", advance them to role="free" and populate audit fields (`role_assigned_at`, `role_assigned_by`). Preserve higher roles (free/paid/operator) without modification.

## Technical Context

**Language/Version**: Python 3.13
**Primary Dependencies**: FastAPI, boto3 (DynamoDB), pydantic
**Storage**: DynamoDB (existing User table)
**Testing**: pytest with moto mocks
**Target Platform**: AWS Lambda
**Project Type**: Web application (backend focus for this feature)
**Performance Goals**: Role advancement must complete within OAuth callback (<100ms added latency)
**Constraints**: Must be atomic with OAuth completion - no partial states
**Scale/Scope**: Affects all OAuth users (~1000s per day)

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Gate | Status | Notes |
|------|--------|-------|
| No quick fixes | PASS | Full speckit workflow followed |
| No workspace destruction | PASS | Modifying existing code, not deleting |
| GPG signing | PASS | Will sign commits |
| Cost sensitivity | PASS | No new AWS resources |
| No implementation in spec | PASS | Spec is technology-agnostic |

## Project Structure

### Documentation (this feature)

```text
specs/1170-oauth-role-advancement/
├── spec.md              # Feature specification
├── plan.md              # This file
├── research.md          # Phase 0 output
├── tasks.md             # Phase 2 output
└── checklists/
    └── requirements.md  # Specification quality checklist
```

### Source Code (repository root)

```text
src/lambdas/dashboard/
└── auth.py              # Modify: handle_oauth_callback(), add _advance_role()

tests/unit/dashboard/
└── test_role_advancement.py  # New: unit tests for role advancement
```

**Structure Decision**: Backend-only change. Modifying existing `auth.py` which already contains `handle_oauth_callback()` and `_link_provider()` functions.

## Implementation Approach

### Option A: Integrate into _link_provider() (REJECTED)

Add role advancement to the existing `_link_provider()` function.

**Rejected because**: `_link_provider()` has a specific responsibility (federation field population). Adding role logic violates single responsibility principle and would make the function harder to test and maintain.

### Option B: Create _advance_role() helper (SELECTED)

Create a new `_advance_role()` helper function called from `handle_oauth_callback()` after `_link_provider()`.

**Selected because**:
- Single responsibility: role advancement logic is isolated
- Testable: can unit test independently
- Follows pattern established by `_link_provider()` and `_update_cognito_sub()`
- Clear audit trail with dedicated function

### Implementation Details

1. **Create `_advance_role()` function** (~lines 1740-1790):
   - Parameters: `user: User`, `provider: str`, `dynamodb_client`
   - Check if `user.role == "anonymous"`
   - If yes: update role to "free", set `role_assigned_at` to `datetime.now(UTC)`, set `role_assigned_by` to `f"oauth:{provider}"`
   - Use same DynamoDB update pattern as `_link_provider()`
   - Return updated user or original if no change needed

2. **Call from `handle_oauth_callback()`** (after `_link_provider()` call):
   - Both for new users and existing users linking OAuth
   - Apply to both paths in the function

3. **Unit tests** in `tests/unit/dashboard/test_role_advancement.py`:
   - Test: anonymous → free advancement
   - Test: free/paid/operator preservation
   - Test: audit fields populated correctly
   - Test: DynamoDB update called correctly

## Complexity Tracking

No violations. Simple feature with clear scope.
