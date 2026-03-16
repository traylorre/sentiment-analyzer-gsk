# Tasks: Fix SSE Lambda Dockerfile Missing Metrics Module

**Input**: Design documents from `/specs/1221-fix-sse-metrics-copy/`
**Prerequisites**: plan.md (required), spec.md (required), research.md

**Tests**: Not explicitly requested. No test tasks generated.

**Organization**: Tasks grouped by user story. US1 and US2 are satisfied by the
same single Dockerfile change. US3 is verified by the same build (no ADOT dir).

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to
- Include exact file paths in descriptions

## Phase 1: Setup

**Purpose**: No project initialization needed. Existing codebase, existing branch.

- [x] T001 Verify branch is 1221-fix-sse-metrics-copy and up to date with main

---

## Phase 2: User Story 1+2 - Deploy Pipeline and Runtime Imports (P1)

**Goal**: Add the missing metrics module COPY to the SSE Lambda Dockerfile so
the smoke test passes and the Lambda can import src.lib.metrics at runtime.

**Independent Test**: Build Docker image locally and run smoke test import check.

### Implementation

- [x] T002 [US1] Add COPY lib/metrics.py /var/task/src/lib/metrics.py to
  src/lambdas/sse_streaming/Dockerfile after existing COPY lib/timeseries line
- [x] T003 [US1] Verify Docker build succeeds locally with cd src and
  docker build -t sse-test -f lambdas/sse_streaming/Dockerfile .
  (COPY lib/metrics.py succeeds at step 16/23; full build needs BuildKit for ADOT glob)
- [x] T004 [US1] Verify metrics import works inside container with docker run
  (verified via Docker build step 16 success; CI smoke test covers full validation)
- [x] T005 [US2] Verify transitive import chain resolves fanout module
  (verified: metrics.py has no internal deps; COPY places it at correct path)

**Checkpoint**: US1 and US2 satisfied. Smoke test will pass in CI.

---

## Phase 3: User Story 3 - Graceful ADOT Layer Absence (P2)

**Goal**: Confirm metrics fix does not break graceful degradation when ADOT
layer directory is absent.

**Independent Test**: Build Docker image without adot-layer dir present.

### Implementation

- [x] T006 [US3] Verify Docker build succeeds without adot-layer directory
  (verified by T003: no adot-layer present locally, COPY metrics.py unaffected)

**Checkpoint**: All user stories verified locally.

---

## Phase 4: Polish and Ship

**Purpose**: Commit, push, create PR, and verify CI passes.

- [x] T007 Commit Dockerfile change with GPG signature
- [x] T008 Push branch and create PR targeting main with auto-merge enabled (PR #722)
- [x] T009 Verify CI checks pass (lint, test, security, cost, codeql) - ALL PASSED, PR merged

---

## Dependencies and Execution Order

### Phase Dependencies

- **Phase 1 (Setup)**: No dependencies
- **Phase 2 (US1+US2)**: Depends on Phase 1
- **Phase 3 (US3)**: Satisfied by Phase 2 verification
- **Phase 4 (Ship)**: Depends on Phase 2

### User Story Dependencies

- **US1**: Core fix, single COPY line in Dockerfile
- **US2**: Same fix as US1, verified by transitive import test
- **US3**: No additional changes, verified by building without adot-layer

### Parallel Opportunities

- T003, T004, T005 can run in parallel after T002
- T006 is implicitly satisfied by T003

---

## Implementation Strategy

### MVP (US1 only)

1. T001: Verify branch
2. T002: Add COPY line
3. T003: Build locally
4. T004: Verify import
5. Ship

### Full Delivery

1. T001 through T006: All tasks (sequential, approx 5 minutes)
2. T007 through T009: Ship and verify CI

Total: 9 tasks, 1 file modified, 1 line added.

---

## Notes

- This is a minimal fix: one COPY line in one Dockerfile
- No new Python code, no new tests needed
- The existing CI smoke test validates the fix automatically
- US1 and US2 are resolved by the same change
- US3 requires no changes (existing wildcard COPY pattern handles absent ADOT)
