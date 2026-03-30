# Implementation Plan: Auth Cache-Control Headers

**Branch**: `1157-auth-cache-headers` | **Date**: 2026-01-06 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `/specs/1157-auth-cache-headers/spec.md`

## Summary

Add security headers (`Cache-Control: no-store, no-cache, must-revalidate`, `Pragma: no-cache`, `Expires: 0`) to all 12 auth endpoints in router_v2.py to prevent browser and proxy caching of sensitive authentication data. This is a non-breaking backend change that enhances security without affecting functionality.

## Technical Context

**Language/Version**: Python 3.13
**Primary Dependencies**: FastAPI (Response headers)
**Storage**: N/A (header-only change)
**Testing**: pytest with existing auth endpoint tests
**Target Platform**: AWS Lambda (containerized)
**Project Type**: Web application (backend-only change)
**Performance Goals**: N/A (negligible overhead from headers)
**Constraints**: Must not break existing auth functionality
**Scale/Scope**: 12 auth endpoints in single file

## Constitution Check

_GATE: Must pass before Phase 0 research. Re-check after Phase 1 design._

| Gate                               | Status  | Notes                                         |
| ---------------------------------- | ------- | --------------------------------------------- |
| Amendment 1.6 - No Quick Fixes     | PASS    | Following full speckit workflow               |
| Amendment 1.11 - Clean Workspace   | PASS    | Template repo clean (untracked spec dir only) |
| Amendment 1.12 - Mandatory Speckit | PASS    | Currently in /speckit.plan phase              |
| Amendment 1.14 - Validator Usage   | PENDING | Will run validators before commit             |
| Cost sensitivity                   | PASS    | No infrastructure changes, zero cost impact   |
| Security                           | PASS    | This IS a security enhancement                |

## Project Structure

### Documentation (this feature)

```text
specs/1157-auth-cache-headers/
├── plan.md              # This file
├── research.md          # Phase 0 output (minimal - straightforward feature)
├── checklists/          # Requirements checklist
│   └── requirements.md
└── tasks.md             # Phase 2 output (from /speckit.tasks)
```

### Source Code (target repository)

```text
# Target: sentiment-analyzer-gsk

src/lambdas/dashboard/
└── router_v2.py         # Contains all 12 auth endpoints to modify

tests/unit/
└── test_cache_headers.py  # New test file for header verification
```

**Structure Decision**: Backend-only change in target repository. Single file modification with new test file.

## Complexity Tracking

No violations. This is a straightforward, non-breaking change.

---

## Phase 0: Research

### Research Tasks

1. **FastAPI response header patterns** - Best practice for setting headers
2. **HTTP cache header standards** - Verify header combination is correct per RFC

### Findings

**Decision 1: Header Setting Approach**

- **Decision**: Use FastAPI middleware or response decorator pattern
- **Rationale**: Consistent application across all auth endpoints without modifying each handler
- **Alternatives considered**:
  - Manual `response.headers` in each endpoint (rejected: repetitive, error-prone)
  - APIRouter dependency injection (viable alternative)

**Decision 2: Header Values**

- **Decision**: Use exact values from spec: `Cache-Control: no-store, no-cache, must-revalidate`, `Pragma: no-cache`, `Expires: 0`
- **Rationale**: Per RFC 7234, `no-store` prevents caching entirely, `no-cache` requires revalidation, `must-revalidate` ensures stale responses aren't used. Combined with HTTP/1.0 `Pragma` and `Expires` for legacy proxy compatibility.
- **Canonical Source**: RFC 7234 Section 5.2.2.3 (no-store), Section 5.2.2.1 (no-cache)

---

## Phase 1: Design

### Implementation Approach

**Option A: Middleware/Dependency Injection (Recommended)**

Create a reusable dependency or middleware that sets cache headers for all auth routes:

```python
# Dependency injection approach
async def no_cache_headers(response: Response):
    response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate"
    response.headers["Pragma"] = "no-cache"
    response.headers["Expires"] = "0"
    return response
```

Apply to auth router:

```python
auth_router = APIRouter(
    prefix="/auth",
    dependencies=[Depends(no_cache_headers)]
)
```

**Option B: Response Model Pattern**

Use a custom response class that automatically sets headers:

```python
class NoCacheJSONResponse(JSONResponse):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.headers["Cache-Control"] = "no-store, no-cache, must-revalidate"
        self.headers["Pragma"] = "no-cache"
        self.headers["Expires"] = "0"
```

**Selected Approach**: Option A (Dependency Injection)

- Cleaner separation of concerns
- Easier to test in isolation
- Doesn't require changing response_class on every endpoint

### Data Model

N/A - No data model changes required.

### API Contracts

No contract changes - only response header additions. Existing response bodies unchanged.

### Affected Endpoints (12 total)

| Endpoint                       | Method | Description                |
| ------------------------------ | ------ | -------------------------- |
| /api/v2/auth/anonymous         | POST   | Anonymous session creation |
| /api/v2/auth/validate          | GET    | Session validation         |
| /api/v2/auth/magic-link        | POST   | Magic link initiation      |
| /api/v2/auth/magic-link/verify | GET    | Magic link verification    |
| /api/v2/auth/oauth/urls        | GET    | OAuth provider URLs        |
| /api/v2/auth/oauth/callback    | POST   | OAuth callback handling    |
| /api/v2/auth/refresh           | POST   | Token refresh              |
| /api/v2/auth/signout           | POST   | Sign out                   |
| /api/v2/auth/session           | GET    | Session info               |
| /api/v2/auth/check-email       | POST   | Email availability check   |
| /api/v2/auth/link-accounts     | POST   | Account linking            |
| /api/v2/auth/merge-status      | GET    | Merge status check         |

---

## Next Steps

1. Run `/speckit.tasks` to generate implementation tasks
2. Run `/speckit.implement` to execute implementation
3. Run validators before commit
4. Push, create PR, merge
