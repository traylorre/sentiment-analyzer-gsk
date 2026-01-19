# Tasks: Remove CloudFront References from Documentation

**Input**: Design documents from `/specs/1209-remove-cloudfront-docs/`
**Prerequisites**: plan.md (required), spec.md (required for user stories), research.md

**Tests**: No test tasks included - this is documentation-only update. Validation is via Mermaid syntax checking and link verification.

**Organization**: Tasks are grouped by user story to enable independent implementation and testing of each story.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (e.g., US1, US2, US3, US4)
- Include exact file paths in descriptions

## Path Conventions

- All paths are relative to repository root `/home/zeebo/projects/sentiment-analyzer-gsk/`
- Documentation files in `docs/` and root level
- Mermaid diagrams in `docs/diagrams/` and `docs/`

---

## Phase 1: Setup

**Purpose**: No setup required - documentation-only change

*No tasks in this phase - proceed directly to Phase 2*

---

## Phase 2: Foundational

**Purpose**: No foundational tasks required - each user story can be completed independently

*No tasks in this phase - proceed directly to User Stories*

---

## Phase 3: User Story 1 - Developer Reads Accurate Architecture (Priority: P1) 🎯 MVP

**Goal**: Update README.md and DEMO_URLS.local.md so developers see accurate architecture (Amplify frontend, Lambda Function URLs)

**Independent Test**: Read README.md and verify architecture descriptions show Amplify as frontend hosting with no CloudFront references as active components

### Implementation for User Story 1

- [x] T001 [P] [US1] Update Architecture section to describe Amplify as frontend hosting in README.md:151
- [x] T002 [P] [US1] Update Key Features to remove CloudFront-delivered UI reference in README.md:176-178
- [x] T003 [P] [US1] Update Edge Layer in architecture diagram to show Amplify without CloudFront in README.md:207-210
- [x] T004 [P] [US1] Remove CloudFront participant from auth flow diagram in README.md:496
- [x] T005 [P] [US1] Remove or update CloudFront Routing documentation reference in README.md:1015
- [x] T006 [P] [US1] Replace CloudFront URL with Amplify URL in Architecture Highlights in DEMO_URLS.local.md:90

**Checkpoint**: README.md and DEMO_URLS.local.md accurately describe Amplify architecture with no CloudFront as active component

---

## Phase 4: User Story 2 - Operations Engineer Uses Runbooks (Priority: P2)

**Goal**: Update operational documentation so ops engineers have accurate component references during incidents

**Independent Test**: Review scaling runbook and preflight checklist, verify all component references match deployed infrastructure

### Implementation for User Story 2

- [x] T007 [P] [US2] Update architecture table to show Amplify instead of CloudFront in docs/runbooks/scaling.md:13
- [x] T008 [P] [US2] Update cost considerations table CloudFront reference in docs/runbooks/scaling.md:201
- [x] T009 [P] [US2] Update CORS configuration guidance to reference Amplify domain in docs/PRODUCTION_PREFLIGHT_CHECKLIST.md:57

**Checkpoint**: Operational docs reference Amplify and Lambda Function URLs, not CloudFront

---

## Phase 5: User Story 3 - Architect Reviews Security Diagrams (Priority: P2)

**Goal**: Update all architecture and security diagrams to accurately show request flows without CloudFront

**Independent Test**: Compare diagram flows against actual AWS resource configurations (Amplify, Lambda Function URLs)

### Implementation for User Story 3

- [x] T010 [P] [US3] Remove CloudFront participant and update SSE flow to show Browser → Lambda Function URL in docs/diagrams/sse-lambda-streaming.mmd:5,59
- [x] T011 [P] [US3] Replace ZONE 0 CloudFront boundary with Lambda Function URL security controls in docs/diagrams/security-flow.mmd:2-3,47
- [x] T012 [P] [US3] Remove CloudFront from Edge Layer, keep Amplify in docs/diagrams/dataflow-all-flows.mmd:20
- [x] T013 [P] [US3] Remove CloudFront CDN subgraph and update request flows in docs/architecture.mmd:12-13,56
- [x] T014 [P] [US3] Remove CloudFront participant from auth sequence and show Amplify serving SPA in docs/USE-CASE-DIAGRAMS.md:226

**Checkpoint**: All diagrams show Amplify and Lambda Function URLs as entry points, no CloudFront in request flows

---

## Phase 6: User Story 4 - Security Analyst Reviews Gap Analysis (Priority: P3)

**Goal**: Add clarifications to security analysis documents distinguishing current state from proposed enhancements

**Independent Test**: Read gap analysis docs and verify CloudFront sections clearly state it is a proposed future enhancement, not current architecture

### Implementation for User Story 4

- [x] T015 [P] [US4] Add clarification note that CloudFront is proposed future enhancement in docs/DASHBOARD_SECURITY_ANALYSIS.md:167,323-341,370
- [x] T016 [P] [US4] Add clarification note that CloudFront cost options are for consideration in docs/API_GATEWAY_GAP_ANALYSIS.md:181,241,438

**Checkpoint**: Gap analysis documents clearly distinguish "current state" from "proposed enhancements" for CloudFront

---

## Phase 7: Polish & Validation

**Purpose**: Validate all changes and ensure no broken links or invalid Mermaid syntax

- [x] T017 [P] Validate Mermaid syntax for docs/diagrams/sse-lambda-streaming.mmd
- [x] T018 [P] Validate Mermaid syntax for docs/diagrams/security-flow.mmd
- [x] T019 [P] Validate Mermaid syntax for docs/diagrams/dataflow-all-flows.mmd
- [x] T020 [P] Validate Mermaid syntax for docs/architecture.mmd
- [x] T021 [P] Validate Mermaid syntax for embedded diagrams in README.md
- [x] T022 [P] Validate Mermaid syntax for embedded diagrams in docs/USE-CASE-DIAGRAMS.md
- [x] T023 Check for broken internal documentation links after changes
- [x] T024 Final scan for remaining CloudFront-as-deployed references across all files

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: Skipped - no setup required
- **Foundational (Phase 2)**: Skipped - no blocking prerequisites
- **User Stories (Phase 3-6)**: All user stories are independent - can proceed in any order or parallel
- **Polish (Phase 7)**: Depends on all user story phases being complete

### User Story Dependencies

- **User Story 1 (P1)**: No dependencies - can start immediately
- **User Story 2 (P2)**: No dependencies - can start immediately, parallel with US1
- **User Story 3 (P2)**: No dependencies - can start immediately, parallel with US1/US2
- **User Story 4 (P3)**: No dependencies - can start immediately, parallel with others

### Within Each User Story

- All tasks within a user story are marked [P] (parallel) since they modify different files
- Each task is atomic and can be completed independently

### Parallel Opportunities

- **Maximum Parallelization**: All tasks T001-T016 can run in parallel (all modify different files)
- **Per-Story Parallelization**: All tasks within each user story can run in parallel
- **Validation Phase**: All T017-T022 can run in parallel, then T023-T024 sequentially

---

## Parallel Example: User Story 1

```bash
# Launch all README.md and DEMO_URLS.local.md updates together:
Task: "Update Architecture section in README.md:151"
Task: "Update Key Features in README.md:176-178"
Task: "Update Edge Layer diagram in README.md:207-210"
Task: "Remove CloudFront from auth flow in README.md:496"
Task: "Update CloudFront Routing reference in README.md:1015"
Task: "Replace CloudFront URL in DEMO_URLS.local.md:90"
```

---

## Parallel Example: User Story 3 (Diagrams)

```bash
# Launch all Mermaid diagram updates together:
Task: "Update SSE flow diagram in docs/diagrams/sse-lambda-streaming.mmd"
Task: "Update security flow diagram in docs/diagrams/security-flow.mmd"
Task: "Update dataflow diagram in docs/diagrams/dataflow-all-flows.mmd"
Task: "Update architecture diagram in docs/architecture.mmd"
Task: "Update auth sequence in docs/USE-CASE-DIAGRAMS.md"
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 3: User Story 1 (README.md + DEMO_URLS.local.md)
2. **STOP and VALIDATE**: Verify README.md accurately describes Amplify architecture
3. Deploy/demo if ready - developers can now see correct architecture

### Incremental Delivery

1. Add User Story 1 → Test independently → Primary docs accurate (MVP!)
2. Add User Story 2 → Test independently → Ops docs accurate
3. Add User Story 3 → Test independently → All diagrams accurate
4. Add User Story 4 → Test independently → Gap analysis clarified
5. Complete Phase 7 → All validation passes

### Recommended Execution Order

Given all tasks can run in parallel, recommended order for single-developer execution:

1. **US1** (T001-T006): Highest impact - README is first thing developers see
2. **US3** (T010-T014): Second highest impact - diagrams inform architecture understanding
3. **US2** (T007-T009): Operational docs for incident response
4. **US4** (T015-T016): Lowest priority - clarifications only
5. **Validation** (T017-T024): Must be last

---

## Summary

| Phase | User Story | Tasks | Files |
|-------|------------|-------|-------|
| 3 | US1 - Developer Reads Accurate Architecture | T001-T006 (6) | README.md, DEMO_URLS.local.md |
| 4 | US2 - Operations Engineer Uses Runbooks | T007-T009 (3) | scaling.md, PRODUCTION_PREFLIGHT_CHECKLIST.md |
| 5 | US3 - Architect Reviews Security Diagrams | T010-T014 (5) | 4 .mmd files + USE-CASE-DIAGRAMS.md |
| 6 | US4 - Security Analyst Reviews Gap Analysis | T015-T016 (2) | DASHBOARD_SECURITY_ANALYSIS.md, API_GATEWAY_GAP_ANALYSIS.md |
| 7 | Validation | T017-T024 (8) | All modified files |

**Total Tasks**: 24
**Parallel Opportunities**: 16/24 tasks can run fully parallel (T001-T016)
**MVP Scope**: User Story 1 only (6 tasks)

---

## Notes

- [P] tasks = different files, no dependencies
- [Story] label maps task to specific user story for traceability
- Each user story is independently completable and testable
- Commit after each task or logical group
- Stop at any checkpoint to validate story independently
- All Mermaid diagrams must render valid syntax after modifications
