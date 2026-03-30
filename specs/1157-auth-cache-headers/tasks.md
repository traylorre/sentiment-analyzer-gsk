# Tasks: Auth Cache-Control Headers

**Input**: Design documents from `/specs/1157-auth-cache-headers/`
**Prerequisites**: plan.md (required), spec.md (required), research.md
**Target Repository**: `/home/traylorre/projects/sentiment-analyzer-gsk`

**Tests**: Unit tests included as this is a security-critical feature.

**Organization**: Tasks grouped by user story. Both user stories (US1: Browser caching, US2: Proxy caching) are P1 priority and share the same implementation, so they are combined into a single implementation phase.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (e.g., US1, US2)
- Include exact file paths in descriptions

---

## Phase 1: Setup

**Purpose**: No setup required - modifying existing file

_No setup tasks needed. The target file (`router_v2.py`) already exists._

---

## Phase 2: Foundational

**Purpose**: Create the cache header dependency that will be used by all auth endpoints

- [x] T001 Create `no_cache_headers` dependency function in `src/lambdas/dashboard/router_v2.py`
  - Function signature: `async def no_cache_headers(response: Response) -> None`
  - Set `Cache-Control: no-store, no-cache, must-revalidate`
  - Set `Pragma: no-cache`
  - Set `Expires: 0`

**Checkpoint**: Dependency ready - can now apply to auth router

---

## Phase 3: User Story 1 & 2 - Prevent Browser and Proxy Caching (Priority: P1) MVP

**Goal**: Apply cache-control headers to all 12 auth endpoints to prevent browser and proxy caching

**Independent Test**: Make requests to any auth endpoint and verify response headers contain all three required headers

### Tests for User Stories 1 & 2

- [x] T002 [P] [US1,US2] Create unit test file `tests/unit/dashboard/test_cache_headers.py`
  - Test that `no_cache_headers` dependency sets correct Cache-Control header
  - Test that `no_cache_headers` dependency sets correct Pragma header
  - Test that `no_cache_headers` dependency sets correct Expires header

### Implementation for User Stories 1 & 2

- [x] T003 [US1,US2] Apply `no_cache_headers` dependency to auth router in `src/lambdas/dashboard/router_v2.py`
  - Add `dependencies=[Depends(no_cache_headers)]` to auth APIRouter
  - Verify all 12 endpoints receive the headers via router-level dependency

**Affected Endpoints** (12 total):

1. POST /api/v2/auth/anonymous
2. GET /api/v2/auth/validate
3. POST /api/v2/auth/magic-link
4. GET /api/v2/auth/magic-link/verify
5. GET /api/v2/auth/oauth/urls
6. POST /api/v2/auth/oauth/callback
7. POST /api/v2/auth/refresh
8. POST /api/v2/auth/signout
9. GET /api/v2/auth/session
10. POST /api/v2/auth/check-email
11. POST /api/v2/auth/link-accounts
12. GET /api/v2/auth/merge-status

**Checkpoint**: All auth endpoints now return cache-prevention headers

---

## Phase 4: Polish & Cross-Cutting Concerns

**Purpose**: Verification and cleanup

- [x] T004 Run existing auth unit tests to verify no regressions
- [x] T005 Run `/security-validate` to verify security improvement
- [x] T006 Verify non-auth endpoints do NOT receive cache headers (scope check)

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: N/A - no setup required
- **Foundational (Phase 2)**: T001 must complete before T003
- **User Stories (Phase 3)**: T002 (tests) and T003 (implementation) can run after T001
- **Polish (Phase 4)**: After T003 completes

### Task Dependencies

```
T001 (create dependency)
  └── T002 (tests) [P]
  └── T003 (apply to router)
        └── T004, T005, T006 (verification) [P]
```

### Parallel Opportunities

- T002 (write tests) can run in parallel with T003 (apply dependency) - different files
- T004, T005, T006 can all run in parallel after T003 completes

---

## Parallel Example

```bash
# After T001 completes, launch in parallel:
Task: "Create unit test file tests/unit/dashboard/test_cache_headers.py"
Task: "Apply no_cache_headers dependency to auth router"

# After T003 completes, launch in parallel:
Task: "Run existing auth unit tests"
Task: "Run /security-validate"
Task: "Verify non-auth endpoints do NOT receive cache headers"
```

---

## Implementation Strategy

### MVP (Minimal Implementation)

1. T001: Create the dependency function
2. T003: Apply to router
3. Done - headers now applied to all 12 auth endpoints

### Full Implementation (with tests)

1. T001: Create dependency function
2. T002 + T003: Tests and implementation in parallel
3. T004-T006: Verification

---

## Notes

- This is a backend-only change in target repository
- Single file modification (`router_v2.py`) plus one new test file
- No data model or contract changes
- Non-breaking: existing auth functionality unchanged
- All changes in target repo: `/home/traylorre/projects/sentiment-analyzer-gsk`
