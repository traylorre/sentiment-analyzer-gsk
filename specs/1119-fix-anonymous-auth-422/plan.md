# Implementation Plan: Fix Anonymous Auth 422 Error

**Branch**: `1119-fix-anonymous-auth-422` | **Date**: 2026-01-02 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `/specs/1119-fix-anonymous-auth-422/spec.md`

## Summary

Fix POST /api/v2/auth/anonymous returning 422 when frontend sends no request body. The backend endpoint requires a Pydantic body parameter, but should accept requests with no body by using FastAPI's `Body(default=None)` pattern and instantiating defaults when body is None.

## Technical Context

**Language/Version**: Python 3.13
**Primary Dependencies**: FastAPI, Pydantic v2
**Storage**: DynamoDB (existing users table)
**Testing**: pytest with moto mocks (unit), real AWS (integration)
**Target Platform**: AWS Lambda
**Project Type**: Web application (backend Lambda + frontend Next.js)
**Performance Goals**: P90 response time ≤ 500ms
**Constraints**: Must not break existing frontend code

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Gate | Status | Notes |
|------|--------|-------|
| Parameterized queries | PASS | No DB query changes - existing auth_service handles DynamoDB |
| TLS enforced | PASS | Lambda Function URL uses HTTPS |
| Secrets in secrets manager | PASS | No new secrets |
| Auth required for admin endpoints | N/A | Anonymous endpoint is public by design |
| Unit tests accompany implementation | REQUIRED | Will add tests for no-body and empty-body cases |
| No pipeline bypass | REQUIRED | Will use normal PR workflow |
| GPG-signed commits | REQUIRED | Will sign commits |

## Project Structure

### Documentation (this feature)

```text
specs/1119-fix-anonymous-auth-422/
├── plan.md              # This file
├── research.md          # Phase 0 output
├── data-model.md        # Phase 1 output (N/A - no model changes)
├── quickstart.md        # Phase 1 output
├── contracts/           # Phase 1 output (N/A - no contract changes)
└── tasks.md             # Phase 2 output (/speckit.tasks)
```

### Source Code (repository root)

```text
src/lambdas/dashboard/
├── router_v2.py         # MODIFY: create_anonymous_session endpoint
└── auth.py              # NO CHANGE: AnonymousSessionRequest model already has defaults

tests/unit/
└── test_dashboard_handler.py  # ADD: tests for no-body and empty-body cases
```

**Structure Decision**: Backend-only fix in existing Lambda handler. No new files needed.

## Complexity Tracking

No violations. This is a minimal, targeted fix affecting only the endpoint signature.

---

## Phase 0: Research

### Research Task 1: FastAPI Optional Body Pattern

**Decision**: Use `Body(default=None)` to make the entire request body optional.

**Rationale**: In FastAPI/Pydantic v2, when a function parameter is typed as a Pydantic model without a default, FastAPI requires a request body to be present for parsing. Even if all model fields have defaults, the body itself must exist. To allow truly optional body (no body at all), the pattern is:

```python
from fastapi import Body

async def endpoint(
    body: MyModel | None = Body(default=None),
):
    if body is None:
        body = MyModel()  # Use defaults
```

**Alternatives considered**:
1. Frontend sends empty `{}` body - rejected because it requires frontend changes
2. Use `Body(default=MyModel())` - rejected because Body() expects JSON-serializable default
3. Catch validation error and return defaults - rejected because it's a workaround, not proper API design

### Research Task 2: Existing Codebase Patterns

**Decision**: Follow existing router_v2.py patterns with minimal changes.

**Rationale**: The endpoint at line 250-265 needs only signature change. The auth_service.create_anonymous_session function already handles the AnonymousSessionRequest model correctly.

**Current signature** (line 251-255):
```python
async def create_anonymous_session(
    request: Request,
    body: auth_service.AnonymousSessionRequest,
    table=Depends(get_users_table),
):
```

**New signature**:
```python
async def create_anonymous_session(
    request: Request,
    body: auth_service.AnonymousSessionRequest | None = Body(default=None),
    table=Depends(get_users_table),
):
    if body is None:
        body = auth_service.AnonymousSessionRequest()
```

---

## Phase 1: Design

### Data Model

**No changes required**. The existing `AnonymousSessionRequest` model in `auth.py` already has proper defaults:

```python
class AnonymousSessionRequest(BaseModel):
    timezone: str = Field(default="America/New_York")
    device_fingerprint: str | None = Field(default=None)
```

### API Contract

**No contract changes**. The endpoint behavior remains the same - it's now more permissive (accepts no body in addition to existing body formats).

| Scenario | Before | After |
|----------|--------|-------|
| No body | 422 Unprocessable Entity | 201 Created (uses defaults) |
| Empty body `{}` | 201 Created | 201 Created |
| Body with fields | 201 Created | 201 Created |

### Quickstart

See `quickstart.md` for testing the fix.

---

## Implementation Summary

**Files to modify**: 1
- `src/lambdas/dashboard/router_v2.py` - Change function signature

**Tests to add**: 2-3 test cases
- Test no body → 201 with defaults
- Test empty body `{}` → 201 with defaults
- Test body with fields → 201 with provided values

**Estimated effort**: Small (1-2 hours including tests)
