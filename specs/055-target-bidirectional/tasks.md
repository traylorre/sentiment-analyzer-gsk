# Tasks: Bidirectional Validation for Target Repos

**Input**: Design documents from `/specs/055-target-bidirectional/`
**Prerequisites**: plan.md, spec.md, research.md, data-model.md, quickstart.md

**Tests**: Unit tests are included as the plan.md specifies test files in the project structure.

**Organization**: Tasks are grouped by user story to enable independent implementation and testing.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (US1, US2, US3, US4)
- Include exact file paths in descriptions

## Path Conventions

Based on plan.md structure:

- **Source**: `src/validators/` and `src/validators/bidirectional/`
- **Tests**: `tests/unit/` and `tests/fixtures/bidirectional/`

---

## Phase 1: Setup (Module Structure)

**Purpose**: Create the new bidirectional submodule structure

- [x] T001 Create bidirectional module directory at src/validators/bidirectional/
- [x] T002 Create src/validators/bidirectional/**init**.py with public exports
- [x] T003 [P] Create tests/fixtures/bidirectional/aligned/ directory with sample spec-code pair
- [x] T004 [P] Create tests/fixtures/bidirectional/misaligned/ directory with drift sample

---

## Phase 2: Foundational (Data Models)

**Purpose**: Create data models that ALL user stories depend on

**⚠️ CRITICAL**: No user story work can begin until this phase is complete

- [x] T005 Create SpecFile dataclass in src/validators/bidirectional/models.py per data-model.md
- [x] T006 Create Requirement dataclass in src/validators/bidirectional/models.py
- [x] T007 Create CodeModule dataclass in src/validators/bidirectional/models.py
- [x] T008 Create AlignmentResult dataclass in src/validators/bidirectional/models.py
- [x] T009 Add BidirectionalFinding to src/validators/models.py with BIDIR-001 through BIDIR-005

**Checkpoint**: Foundation ready - user story implementation can now begin

---

## Phase 3: User Story 1 + 3 - Intrinsic Detection with Semantic Comparison (Priority: P1) 🎯 MVP

**Goal**: Enable BidirectionalValidator to detect and validate specs in target repos without make targets, using semantic comparison

**Independent Test**: Run `/validate --validator bidirectional --repo /path/to/target-repo` on a repo with `specs/*/spec.md` files but no `make test-bidirectional`; validator should PASS/FAIL based on spec-code alignment, not SKIP

**Why Combined**: US3 (Semantic Comparison) is the mechanism for US1 (Intrinsic Detection) - they form the core MVP together

### Unit Tests for US1+US3

- [x] T010 [P] [US1] Create test_bidirectional_detector.py in tests/unit/ with tests for detect_specs()
- [x] T011 [P] [US1] Create test_bidirectional_mapper.py in tests/unit/ with tests for map_spec_to_code()
- [x] T012 [P] [US3] Create test_bidirectional_comparator.py in tests/unit/ with tests for semantic_compare()

### Implementation for US1+US3

- [x] T013 [US1] Implement detect_specs() in src/validators/bidirectional/detector.py per research.md algorithm
- [x] T014 [US1] Implement parse_spec_file() in src/validators/bidirectional/detector.py to extract FR-NNN requirements
- [x] T015 [US1] Implement map_spec_to_code() in src/validators/bidirectional/mapper.py using feature name matching
- [x] T016 [US1] Implement extract_code_symbols() in src/validators/bidirectional/mapper.py to parse functions/classes
- [x] T017 [US3] Implement semantic_compare() in src/validators/bidirectional/comparator.py using Claude API
- [x] T018 [US3] Implement classify_gaps() in src/validators/bidirectional/comparator.py per research.md thresholds
- [x] T019 [US3] Implement offline fallback calculate_token_similarity() in src/validators/bidirectional/comparator.py
- [x] T020 [US1] Implement alignment_to_findings() in src/validators/bidirectional/comparator.py to generate BIDIR-XXX findings
- [x] T021 [US1] Modify BidirectionalValidator.validate() in src/validators/verification.py to use intrinsic detection when has_make_target() returns False

**Checkpoint**: User Story 1+3 complete - intrinsic detection with semantic comparison works on target repos

---

## Phase 4: User Story 2 - Thin Make Target Delegation (Priority: P2)

**Goal**: Target repos can optionally add a thin `make test-bidirectional` target for custom verification

**Independent Test**: Add `make test-bidirectional` to target repo that invokes template tooling; verify validator uses make target when present instead of intrinsic detection

### Unit Tests for US2

- [x] T022 [P] [US2] Add test case to tests/unit/test_verification_validators.py for make target precedence

### Implementation for US2

- [x] T023 [US2] Ensure has_make_target() check runs BEFORE intrinsic detection in src/validators/verification.py
- [x] T024 [US2] Add logging to indicate which path was taken (make target vs intrinsic) in src/validators/verification.py
- [x] T025 [US2] Document thin make target example in specs/055-target-bidirectional/quickstart.md

**Checkpoint**: User Story 2 complete - make target delegation works correctly

---

## Phase 5: User Story 4 - Code-to-Spec Regeneration Check (Priority: P3)

**Goal**: Detect undocumented code functionality and stale spec content via reverse comparison

**Independent Test**: Modify code to add a feature not in spec; verify validator detects BIDIR-002 "undocumented functionality"

### Unit Tests for US4

- [ ] T026 [P] [US4] Add test cases to test_bidirectional_comparator.py for code-to-spec direction

### Implementation for US4

- [ ] T027 [US4] Implement infer_spec_from_code() in src/validators/bidirectional/comparator.py using Claude API
- [ ] T028 [US4] Implement detect_undocumented_code() in src/validators/bidirectional/comparator.py
- [ ] T029 [US4] Implement detect_stale_spec() in src/validators/bidirectional/comparator.py
- [ ] T030 [US4] Integrate code-to-spec check into alignment_to_findings() in src/validators/bidirectional/comparator.py

**Checkpoint**: User Story 4 complete - round-trip verification detects spec rot

---

## Phase 6: Polish & Cross-Cutting Concerns

**Purpose**: Final integration, documentation, and validation

- [ ] T031 [P] Add BIDIR-XXX finding examples to docs/ or methodology documentation
- [ ] T032 [P] Update .specify/methodologies/index.yaml if bidirectional methodology entry needs update
- [ ] T033 Run make validate to ensure no regressions
- [ ] T034 Run make test-unit to verify all new tests pass
- [ ] T035 Test against sentiment-analyzer-gsk to verify SC-001 (produces PASS or actionable findings, not SKIP)

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies - can start immediately
- **Foundational (Phase 2)**: Depends on Setup completion - BLOCKS all user stories
- **US1+US3 (Phase 3)**: Depends on Foundational - core MVP
- **US2 (Phase 4)**: Depends on Foundational - can run in parallel with US1+US3
- **US4 (Phase 5)**: Depends on US3 comparator being complete
- **Polish (Phase 6)**: Depends on all user stories being complete

### User Story Dependencies

- **US1+US3 (P1)**: Core functionality - no dependencies on other stories
- **US2 (P2)**: Independent of US1+US3 - just adds make target check
- **US4 (P3)**: Extends US3 comparator with reverse direction

### Within Each User Story

- Tests MUST be written and FAIL before implementation
- Models → Detection → Mapping → Comparison → Integration
- Story complete before moving to next priority

### Parallel Opportunities

- **Phase 1**: T003 and T004 can run in parallel
- **Phase 3**: T010, T011, T012 tests can run in parallel
- **Phase 4**: T022 can run in parallel with US1+US3 tasks
- **Phase 5**: T026 can run in parallel with earlier implementation
- **Phase 6**: T031 and T032 can run in parallel

---

## Parallel Example: Phase 3 (US1+US3)

```bash
# Launch all tests together (they target different files):
Task: "Create test_bidirectional_detector.py in tests/unit/"
Task: "Create test_bidirectional_mapper.py in tests/unit/"
Task: "Create test_bidirectional_comparator.py in tests/unit/"
```

---

## Implementation Strategy

### MVP First (User Stories 1+3 Only)

1. Complete Phase 1: Setup
2. Complete Phase 2: Foundational (CRITICAL - blocks all stories)
3. Complete Phase 3: User Story 1+3 (Intrinsic Detection + Semantic Comparison)
4. **STOP and VALIDATE**: Test against sentiment-analyzer-gsk
5. Deploy if ready - basic bidirectional validation works

### Incremental Delivery

1. Complete Setup + Foundational → Foundation ready
2. Add US1+US3 → Test → MVP delivers intrinsic detection
3. Add US2 → Test → Target repos can customize via make target
4. Add US4 → Test → Full round-trip verification
5. Polish → Complete feature

### Success Criteria Mapping

| Task       | Success Criteria                                                               |
| ---------- | ------------------------------------------------------------------------------ |
| T021       | SC-001: Running on sentiment-analyzer-gsk produces PASS or findings (not SKIP) |
| T017, T018 | SC-005: Semantic comparison matches equivalent concepts 90%+                   |
| T025       | SC-004: Thin make target under 10 lines                                        |
| All        | SC-006: Zero methodology code copied to target repo                            |

---

## Notes

- [P] tasks = different files, no dependencies
- [Story] label maps task to specific user story for traceability
- Reuse existing `.specify/verification/` infrastructure per research.md
- Claude API required for full semantic comparison; offline fallback for degraded mode
- All findings use BIDIR-XXX IDs per data-model.md
