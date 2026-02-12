# Implementation Plan: Require Role Decorator

**Branch**: `1130-require-role-decorator` | **Date**: 2026-01-05 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `/specs/1130-require-role-decorator/spec.md`

## Summary

Create a `@require_role(role: str)` decorator for FastAPI endpoints that validates user roles from JWT claims before allowing access. The decorator integrates with existing `extract_auth_context_typed()` and prevents role enumeration attacks by using generic 403 error messages. This is a Phase 0 security-critical component that enables protection of admin endpoints (`/admin/sessions/revoke`, `/users/lookup`).

## Technical Context

**Language/Version**: Python 3.13
**Primary Dependencies**: FastAPI, functools (stdlib), typing (stdlib)
**Storage**: N/A (roles read from JWT, no database access)
**Testing**: pytest 7.4.3+ with pytest-asyncio 0.23.0+
**Target Platform**: AWS Lambda via Mangum adapter
**Project Type**: Serverless Lambda (existing web application)
**Performance Goals**: <50ms overhead per decorated endpoint
**Constraints**: Must not leak role information in error responses
**Scale/Scope**: Applied to 2 admin endpoints initially, extensible to all role-protected endpoints

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Gate | Requirement | Status |
|------|-------------|--------|
| Security & Access Control | All admin endpoints must require authentication | **PASS** - Decorator enforces auth before role check |
| No Unauthenticated Management Access | Admin endpoints protected | **PASS** - 401 for no auth, 403 for wrong role |
| TLS in Transit | N/A for decorator | **N/A** |
| Secrets Management | No secrets in decorator | **PASS** - Roles from JWT, not hardcoded |
| Testing Requirements | Unit tests accompany implementation | **PENDING** - Will be created |
| Pre-Push Requirements | Code linted/formatted | **PENDING** - Will be validated |
| Pipeline Check Bypass | Never bypass | **PASS** - Standard merge flow |

**Gate Result**: PASS - No violations. Ready for Phase 0.

## Project Structure

### Documentation (this feature)

```text
specs/1130-require-role-decorator/
├── spec.md              # Feature specification
├── plan.md              # This file
├── research.md          # Phase 0 research output
├── data-model.md        # Phase 1 data model
├── quickstart.md        # Phase 1 quickstart guide
├── contracts/           # Phase 1 API contracts
│   └── role-decorator.yaml
├── checklists/
│   └── requirements.md  # Specification checklist
└── tasks.md             # Phase 2 task breakdown
```

### Source Code (repository root)

```text
src/lambdas/shared/
├── middleware/
│   ├── __init__.py           # Export require_role
│   ├── auth_middleware.py    # Existing auth context extraction
│   └── require_role.py       # NEW: @require_role decorator
├── auth/
│   └── constants.py          # NEW: Canonical role definitions
└── errors/
    └── auth_errors.py        # NEW: Role-specific error types

tests/unit/lambdas/shared/middleware/
└── test_require_role.py      # NEW: Unit tests for decorator

tests/unit/lambdas/shared/auth/
└── test_constants.py         # NEW: Role enum tests
```

**Structure Decision**: Extends existing `src/lambdas/shared/middleware/` structure. New module `require_role.py` follows established pattern of separate concerns per file (auth_middleware.py, rate_limit.py, security_headers.py).

## Complexity Tracking

> No violations requiring justification. Implementation follows existing patterns.

| Aspect | Decision | Rationale |
|--------|----------|-----------|
| Decorator vs Depends | Decorator wrapping Depends | Cleaner syntax `@require_role('operator')` vs `role=Depends(require_role('operator'))` |
| Role storage | JWT claims | No database lookup required, roles included in token per Phase 1.5 |
| Error messages | Generic "Access denied" | Prevents role enumeration attacks per FR-004 |

---

## Phase 0: Research Output

### Decision 1: Decorator Implementation Pattern

**Decision**: Use a decorator factory that returns a FastAPI dependency wrapper.

**Rationale**:
- FastAPI's `Depends()` is the standard pattern in this codebase
- A decorator factory `@require_role(role)` provides clean syntax
- The decorator internally creates a dependency that extracts auth context and validates role

**Alternatives Rejected**:
- Pure dependency function: Requires verbose `Depends(lambda: check_role('operator'))` syntax
- Middleware-based: Too broad, applies to all routes instead of selective protection

### Decision 2: Role Enumeration Prevention

**Decision**: Use identical generic error message for all role failures: "Access denied"

**Rationale**:
- FR-004 requires preventing role leakage
- Attacker cannot distinguish "role not found" from "wrong role" from "role disabled"
- Same 403 status code and message regardless of failure reason

**Alternatives Rejected**:
- Role-specific messages: Enables enumeration ("requires operator" reveals operator role exists)
- Different status codes: Could fingerprint different failure modes

### Decision 3: Role Validation Location

**Decision**: Validate role parameter at decoration time (module import), not runtime

**Rationale**:
- FR-005 requires startup-time validation
- Invalid roles like `@require_role('admn')` fail immediately on app startup
- Prevents runtime surprises and silent failures

**Implementation**: Check against `VALID_ROLES` set during decorator factory execution

### Decision 4: Integration with Existing Auth

**Decision**: Reuse `extract_auth_context_typed()` for token parsing, extend `AuthContext` with optional `roles` field

**Rationale**:
- FR-010 requires integration with existing auth
- `AuthContext` already has `user_id`, `auth_type`, `auth_method`
- Adding `roles: list[str] | None` follows existing pattern
- Feature 1048 guarantees auth_type from token validation, not headers

**Alternatives Rejected**:
- Separate role extraction function: Duplicates token parsing logic
- Database lookup: Adds latency, violates JWT-based role assumption

---

## Phase 1: Design Output

### Data Model

See [data-model.md](./data-model.md) for complete entity definitions.

**Key Entities**:

1. **Role** (Enum/Constants)
   - `ANONYMOUS = "anonymous"`
   - `FREE = "free"`
   - `PAID = "paid"`
   - `OPERATOR = "operator"`

2. **AuthContext** (Extended)
   - Existing: `user_id`, `auth_type`, `auth_method`
   - New: `roles: list[str] | None`

3. **RoleError** (Exception)
   - `InsufficientRoleError` - For internal use, caught and converted to HTTPException

### API Contracts

See [contracts/role-decorator.yaml](./contracts/role-decorator.yaml) for OpenAPI spec.

**Error Responses**:

| Condition | Status | Body |
|-----------|--------|------|
| No authentication | 401 | `{"detail": "Authentication required"}` |
| Missing roles claim | 401 | `{"detail": "Invalid token structure"}` |
| Insufficient role | 403 | `{"detail": "Access denied"}` |

### Quickstart

See [quickstart.md](./quickstart.md) for usage examples.

**Basic Usage**:
```python
from src.lambdas.shared.middleware import require_role

@auth_router.post("/admin/sessions/revoke")
@require_role("operator")
async def revoke_sessions(request: Request):
    # Only operators reach here
    ...
```

---

## Artifacts Generated

| Artifact | Path | Status |
|----------|------|--------|
| Specification | specs/1130-require-role-decorator/spec.md | Complete |
| Plan | specs/1130-require-role-decorator/plan.md | Complete |
| Research | specs/1130-require-role-decorator/research.md | Pending |
| Data Model | specs/1130-require-role-decorator/data-model.md | Pending |
| Contracts | specs/1130-require-role-decorator/contracts/ | Pending |
| Quickstart | specs/1130-require-role-decorator/quickstart.md | Pending |
| Tasks | specs/1130-require-role-decorator/tasks.md | Pending (Phase 2) |
