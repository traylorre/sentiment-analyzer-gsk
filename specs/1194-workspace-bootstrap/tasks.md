# Tasks: Workspace Bootstrap with Local Secrets Cache

**Feature**: 1194-workspace-bootstrap
**Generated**: 2026-01-11
**Total Tasks**: 17

## Overview

This task list implements a workspace bootstrap system for new developer setup with local secrets caching. Tasks are organized by user story priority to enable incremental, independently testable delivery.

## Dependencies

```
Phase 1 (Setup) → Phase 2 (Foundational) → Phase 3 (US1: Bootstrap)
                                                ↓
                                         Phase 4 (US2: Offline)
                                                ↓
                                         Phase 5 (US3: Verification)
                                                ↓
                                         Phase 6 (US4: Refresh)
                                                ↓
                                         Phase 7 (Documentation)
```

**Notes**:
- US1 (Bootstrap) is the MVP - all other stories depend on it
- US2 (Offline) is inherently tested by US1's design (no code changes)
- US3-US4 are independent utilities that enhance the core
- Documentation can be parallelized with US3-US4

---

## Phase 1: Setup

**Goal**: Create project scaffolding and template files

- [x] T001 Create `.env.example` template file at repository root
- [x] T002 Verify `.env.local` is in `.gitignore` (should already exist, confirm)

---

## Phase 2: Foundational

**Goal**: Create shared utility functions and common infrastructure

- [x] T003 Create `scripts/lib/` directory for shared bash functions
- [x] T004 [P] Create `scripts/lib/colors.sh` with terminal color constants
- [x] T005 [P] Create `scripts/lib/prereqs.sh` with prerequisite checking functions (version comparison, tool detection)
- [x] T006 [P] Create `scripts/lib/secrets.sh` with AWS Secrets Manager fetch and age encryption functions

---

## Phase 3: User Story 1 - New Developer Workspace Setup (P1)

**Story Goal**: Developer runs single bootstrap command to set up workspace with secrets caching

**Independent Test**: Run `./scripts/bootstrap-workspace.sh` on fresh WSL with AWS credentials → workspace ready in <10 min

- [x] T007 [US1] Create `scripts/bootstrap-workspace.sh` with main orchestration logic
- [x] T008 [US1] Implement prerequisites check section in `scripts/bootstrap-workspace.sh` (calls prereqs.sh functions)
- [x] T009 [US1] Implement age identity generation in `scripts/bootstrap-workspace.sh` (one-time setup)
- [x] T010 [US1] Implement secrets fetch and cache in `scripts/bootstrap-workspace.sh` (calls secrets.sh functions)
- [x] T011 [US1] Implement `.env.local` generation in `scripts/bootstrap-workspace.sh` (decrypt cache, write env file)
- [x] T012 [US1] Add atomic operation handling in `scripts/bootstrap-workspace.sh` (no partial state on failure)

---

## Phase 4: User Story 2 - Offline Development (P2)

**Story Goal**: Developer can work offline after bootstrap without AWS calls

**Independent Test**: Disconnect network after bootstrap → `pytest` passes with cached secrets

**Note**: This story is satisfied by US1's design. No additional code needed - the `.env.local` file enables offline work. Verification happens during US1 testing.

- [x] T013 [US2] Document offline development workflow in `specs/1194-workspace-bootstrap/quickstart.md` (update existing)

---

## Phase 5: User Story 3 - Environment Verification (P3)

**Story Goal**: Developer can verify environment status with clear pass/fail indicators

**Independent Test**: Run `./scripts/verify-dev-environment.sh` → see all checks with status and remediation

- [x] T014 [P] [US3] Create `scripts/verify-dev-environment.sh` with environment validation checks

---

## Phase 6: User Story 4 - Cache Refresh (P4)

**Story Goal**: Developer can force-refresh secrets cache when rotated

**Independent Test**: Run `./scripts/refresh-secrets-cache.sh` → cache updated atomically

- [x] T015 [P] [US4] Create `scripts/refresh-secrets-cache.sh` with force-refresh logic

---

## Phase 7: Documentation & Polish

**Goal**: Complete documentation for workspace setup

- [x] T016 [P] Create `docs/WORKSPACE_SETUP.md` with comprehensive setup guide (WSL2, pyenv, AWS, troubleshooting)
- [x] T017 Update `README.md` with "New Developer Setup" section linking to WORKSPACE_SETUP.md

---

## Parallel Execution Examples

### Maximum Parallelism (Phase 2)
```bash
# These tasks can run simultaneously (different files):
T004 (colors.sh) | T005 (prereqs.sh) | T006 (secrets.sh)
```

### Story-Level Parallelism (Phases 5-7)
```bash
# After US1 complete, these can run in parallel:
T014 (verify script) | T015 (refresh script) | T016 (docs)
```

---

## Implementation Strategy

### MVP (Minimum Viable Product)
**Complete Phase 1-3 (User Story 1)**: This delivers the core value - a working bootstrap script that:
- Checks prerequisites
- Fetches secrets from AWS Secrets Manager
- Caches them locally with age encryption
- Generates `.env.local` for development

**Test**: `./scripts/bootstrap-workspace.sh && source .env.local && pytest`

### Incremental Delivery
1. **MVP**: US1 (bootstrap script) - enables workspace setup
2. **Enhancement 1**: US3 (verify script) - enables environment troubleshooting
3. **Enhancement 2**: US4 (refresh script) - enables secret rotation handling
4. **Polish**: Documentation updates for discoverability

---

## Task Summary by Story

| Story | Priority | Tasks | Parallel | Description |
|-------|----------|-------|----------|-------------|
| Setup | - | 2 | 1 | Project scaffolding |
| Foundational | - | 4 | 3 | Shared libraries |
| US1: Bootstrap | P1 | 6 | 0 | Core bootstrap script |
| US2: Offline | P2 | 1 | 0 | Documentation only |
| US3: Verify | P3 | 1 | 1 | Verification script |
| US4: Refresh | P4 | 1 | 1 | Refresh utility |
| Docs | - | 2 | 1 | Final documentation |

**Total**: 17 tasks, 7 parallelizable

---

## File Manifest

| File | Task | Status |
|------|------|--------|
| `.env.example` | T001 | New |
| `scripts/lib/colors.sh` | T004 | New |
| `scripts/lib/prereqs.sh` | T005 | New |
| `scripts/lib/secrets.sh` | T006 | New |
| `scripts/bootstrap-workspace.sh` | T007-T012 | New |
| `scripts/verify-dev-environment.sh` | T014 | New |
| `scripts/refresh-secrets-cache.sh` | T015 | New |
| `docs/WORKSPACE_SETUP.md` | T016 | New |
| `README.md` | T017 | Update |
