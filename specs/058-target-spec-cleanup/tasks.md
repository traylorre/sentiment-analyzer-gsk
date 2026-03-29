# Tasks: Target Repo Spec Cleanup

**Input**: Design documents from `/specs/058-target-spec-cleanup/`
**Prerequisites**: plan.md, spec.md, research.md

## Repository Boundaries (DO NOT CONFUSE)

| Entity                       | CWD                                               | Changes Allowed                     |
| ---------------------------- | ------------------------------------------------- | ----------------------------------- |
| **Template Repo Spec**       | `/home/traylorre/projects/terraform-gsk-template` | NO CHANGE                           |
| **Template Repo Validators** | `/home/traylorre/projects/terraform-gsk-template` | FIX-001 ONLY (detect_repo_type bug) |
| **Target Repo Spec**         | `/home/traylorre/projects/sentiment-analyzer-gsk` | YES - Clean up specs                |
| **Target Repo Src**          | `/home/traylorre/projects/sentiment-analyzer-gsk` | SPECOVERHAUL - Future work only     |

### CWD Markers in Tasks

- `[TEMPLATE]` = Work in `/home/traylorre/projects/terraform-gsk-template`
- `[TARGET]` = Work in `/home/traylorre/projects/sentiment-analyzer-gsk`
- **Default** = Target repo (most tasks)

### SPECOVERHAUL Tag

When cleaning up target specs (US3, US4), if you discover spec-to-src mismatches:

- **Do NOT fix target repo src** - this is out of scope
- Tag with `SPECOVERHAUL:MISSING_IMPL`, `SPECOVERHAUL:UNDOCUMENTED`, or `SPECOVERHAUL:DRIFT`
- Document in a `SPECOVERHAUL.md` file in target repo for future work

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (e.g., US1, US2, US3)
- Include exact file paths in descriptions

---

## Phase 1: Setup

**Purpose**: Establish working environment and validate baseline

- [x] T001 [TARGET] Switch to target repo working directory: `cd /home/traylorre/projects/sentiment-analyzer-gsk`
- [x] T002 [TARGET] Run `/validate` to capture baseline state with all findings
- [x] T003 [TARGET] List all 22 spec directories in `specs/` and categorize by status (active, obsolete, needs update)
- [x] T004 [TARGET] Create archive directory `specs/_archive/` for obsolete specs

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Fix template bug and add Makefile targets required by validators

**⚠️ CRITICAL**: The `detect_repo_type` bug MUST be fixed first. Without this fix, Amendment 1.7 SKIP logic is never triggered for target repos.

### Part A: Fix Template Bug (FIX-001)

- [ ] T005 [TEMPLATE] Remove constitution fallback in `src/validators/utils.py:76-79`
- [ ] T006 [TEMPLATE] Update unit tests in `tests/unit/test_utils.py` to mock git remote instead of relying on constitution fallback
- [ ] T007 [TEMPLATE] Run `make test-unit` to verify no regressions
- [ ] T008 [TEMPLATE] Verify `detect_repo_type` returns "dependent" for target repo path

### Part B: Add Target Repo Make Targets

- [ ] T009 [TARGET] Add `test-property` target to `Makefile` that runs `python3 -m pytest tests/property/ -v`
- [ ] T010 [P] [TARGET] Add `test-spec` target to `Makefile` (placeholder that exits 0 with message "spec coherence N/A for target repo")
- [ ] T011 [P] [TARGET] Add `test-bidirectional` target to `Makefile` (placeholder that exits 0 with message "bidirectional N/A for target repo")
- [ ] T012 [P] [TARGET] Add `test-mutation` target to `Makefile` (placeholder that exits 0 with message "mutation testing N/A for target repo")

**Checkpoint**: Template bug fixed, target repo correctly classified as "dependent". Re-run `/validate` to verify Amendment 1.7 SKIP behavior works.

---

## Phase 3: User Story 1 - Property Test Remediation (Priority: P1) 🎯 MVP

**Goal**: Make property tests pass when run via validator subprocess

**CWD**: `/home/traylorre/projects/sentiment-analyzer-gsk`

**Independent Test**: Run `make test-property` in target repo and verify exit code 0

### Implementation for User Story 1

- [ ] T013 [TARGET] [US1] Run `python3 -m pytest tests/property/ -v` directly to verify 33 tests pass
- [ ] T014 [TARGET] [US1] Run `make test-property` and compare output to direct pytest run
- [ ] T015 [TARGET] [US1] If T014 fails, debug environment differences (PATH, PYTHONPATH, venv activation)
- [ ] T016 [TARGET] [US1] Fix any test failures found - investigate as source bugs first per spec guidance
- [ ] T017 [TARGET] [US1] Verify `/property-validate` passes with zero PROP-001 findings

**Checkpoint**: Property tests pass via both direct pytest and make target. PROP-001 resolved.

---

## Phase 4: User Story 2 - Canonical Source Citations (Priority: P1)

**Goal**: Add canonical AWS documentation citations to all IAM policies in TARGET REPO

**CWD**: `/home/traylorre/projects/sentiment-analyzer-gsk`

**Independent Test**: Run `/canonical-validate` on target repo and verify zero CAN-002 findings

### Implementation for User Story 2

**Note**: Canonical source format is `// Canonical: <url>` for JSON or `# Canonical: <url>` for HCL

- [ ] T018 [P] [TARGET] [US2] Add canonical citations to `infrastructure/iam-policies/prod-deployer-policy.json`
- [ ] T019 [P] [TARGET] [US2] Add canonical citations to `infrastructure/iam-policies/preprod-deployer-policy.json`
- [ ] T020 [P] [TARGET] [US2] Add canonical citations to `docs/iam-policies/dev-deployer-policy.json`
- [ ] T021 [P] [TARGET] [US2] Add canonical citations to `infrastructure/terraform/ci-user-policy.tf`
- [ ] T022 [TARGET] [US2] Verify each citation links to correct AWS IAM Actions Reference page
- [ ] T023 [TARGET] [US2] Run `/canonical-validate` and verify zero CAN-002 findings

**Canonical Source Reference**: https://docs.aws.amazon.com/service-authorization/latest/reference/list_amazons3.html (replace service name as needed)

**Checkpoint**: All 4 IAM files have canonical source citations. CAN-002 resolved.

---

## Phase 5: User Story 3 - Spec Coherence Fixes (Priority: P2)

**Goal**: Resolve all spec contradictions and ambiguities in TARGET REPO SPECS ONLY

**CWD**: `/home/traylorre/projects/sentiment-analyzer-gsk`

**Independent Test**: Run `/spec-coherence-validate` on target repo and verify zero SPEC-001 findings

### Implementation for User Story 3

- [ ] T024 [TARGET] [US3] Audit spec `specs/001-interactive-dashboard-demo/spec.md` for contradictions
- [ ] T025 [P] [TARGET] [US3] Audit spec `specs/002-mobile-sentiment-dashboard/spec.md` for contradictions
- [ ] T026 [P] [TARGET] [US3] Audit spec `specs/003-*/spec.md` through `specs/019-*/spec.md` (batch audit)
- [ ] T027 [TARGET] [US3] Identify obsolete specs (features no longer implemented) and move to `specs/_archive/`
- [ ] T028 [TARGET] [US3] For each contradiction found, resolve by clarifying intent or removing duplicates
- [ ] T029 [TARGET] [US3] For each ambiguity found, rewrite using precise testable language (MUST, SHOULD, MAY)
- [ ] T030 [TARGET] [US3] Run `/spec-coherence-validate` and verify zero SPEC-001 findings

**⚠️ SPECOVERHAUL**: If spec fixes reveal that TARGET REPO SRC doesn't match spec:

- Do NOT fix `sentiment-analyzer-gsk/src/` - that is OUT OF SCOPE
- Document mismatch in `sentiment-analyzer-gsk/SPECOVERHAUL.md` with tag (MISSING_IMPL, UNDOCUMENTED, DRIFT)
- Leave src changes as future work

**Note**: After FIX-001 is complete (T005-T008), Amendment 1.7 will correctly SKIP this for target repos without spec coherence infrastructure.

**Checkpoint**: All specs internally consistent. SPEC-001 resolved (or SKIP if Amendment 1.7 applies).

---

## Phase 6: User Story 4 - Bidirectional Verification Alignment (Priority: P2)

**Goal**: Achieve 100% spec-to-code coverage in TARGET REPO (no orphan requirements, no undocumented code)

**CWD**: `/home/traylorre/projects/sentiment-analyzer-gsk`

**Independent Test**: Run `/bidirectional-validate` on target repo and verify 100% coverage ratio

### Implementation for User Story 4

- [ ] T031 [TARGET] [US4] Generate list of all spec requirements across 22 spec directories
- [ ] T032 [TARGET] [US4] For each requirement, verify corresponding implementation code exists
- [ ] T033 [TARGET] [US4] For orphan requirements (no code): Tag `SPECOVERHAUL:MISSING_IMPL` and archive spec OR add spec to describe existing code
- [ ] T034 [TARGET] [US4] For undocumented code (no spec): Add explicit spec requirement to `specs/` (DO NOT change src)
- [ ] T035 [TARGET] [US4] Add spec requirements for scaffolding/infrastructure code:
  - Provider blocks
  - Backend configuration
  - Module structure
  - Variable definitions
- [ ] T036 [TARGET] [US4] Run `/bidirectional-validate` and verify 100% coverage

**⚠️ SPECOVERHAUL**: This phase will likely find many spec-to-src mismatches:

- **Orphan requirement** (spec exists, no code): Tag `SPECOVERHAUL:MISSING_IMPL` - archive spec or defer impl
- **Undocumented code** (code exists, no spec): ADD SPEC to document existing code - DO NOT change src
- **Drift** (spec and code both exist but don't match): Tag `SPECOVERHAUL:DRIFT` - do NOT fix src, only document

**Key Principle**: This phase ADDS SPECS to document existing code. It does NOT change src to match specs.

**Note**: Per user clarification, implicit code must become explicit in spec. "Being explicit with spec to code mapping...will be the very comb to untangle knots."

**Checkpoint**: 100% bidirectional coverage. BIDIR-001 resolved (or SKIP if Amendment 1.7 applies).

---

## Phase 7: User Story 5 - Mutation Test Infrastructure (Priority: P3)

**Goal**: Configure mutation testing to measure test quality in TARGET REPO

**CWD**: `/home/traylorre/projects/sentiment-analyzer-gsk`

**Independent Test**: Run mutation tests and verify they complete (pass/fail/skip all acceptable per spec)

### Implementation for User Story 5

- [ ] T037 [TARGET] [US5] Add `mutmut` to `requirements-dev.txt`
- [ ] T038 [TARGET] [US5] Create `.mutmut` configuration file with sensible defaults
- [ ] T039 [TARGET] [US5] Configure mutmut to target critical paths only (not entire codebase per spec)
- [ ] T040 [TARGET] [US5] Run initial mutation test to establish baseline score
- [ ] T041 [TARGET] [US5] If surviving mutants found, document or strengthen tests (per spec: acceptable with rationale)
- [ ] T042 [TARGET] [US5] Update `Makefile` `test-mutation` target to run mutmut instead of placeholder
- [ ] T043 [TARGET] [US5] Run `/mutation-validate` and verify MUT-001 resolved

**Checkpoint**: Mutation testing configured and runnable. MUT-001 resolved (or SKIP if Amendment 1.7 applies).

---

## Phase 8: Polish & Cross-Cutting Concerns

**Purpose**: Final validation, SPECOVERHAUL documentation, and commits

### Validation

- [ ] T044 [TARGET] Run full `/validate` on target repo
- [ ] T045 [TARGET] Verify zero FAIL status validators (SC-001)
- [ ] T046 [TARGET] Verify zero WARN status validators (SC-002)

### SPECOVERHAUL Documentation

- [ ] T047 [TARGET] Create/update `SPECOVERHAUL.md` with all tagged findings from US3 and US4
- [ ] T048 [TARGET] Ensure each finding has: tag, file path, description, and suggested future action

### Commits (Separate Repos, Separate Commits)

- [ ] T049 [TEMPLATE] Update `specs/058-target-spec-cleanup/research.md` with final status
- [ ] T050 [TEMPLATE] Commit template changes (FIX-001 only) with message referencing feature 058
- [ ] T051 [TARGET] Commit target repo changes (specs, Makefile, SPECOVERHAUL.md) with message referencing feature 058

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies - can start immediately
- **Foundational (Phase 2)**: Depends on Setup - BLOCKS all user stories
  - Part A (T005-T008): Fix template detect_repo_type bug - MUST complete first
  - Part B (T009-T012): Add target repo make targets - after Part A
- **US1 Property Tests (Phase 3)**: Depends on T009 (make test-property target)
- **US2 Canonical Citations (Phase 4)**: Can start after Setup - independent of other stories
- **US3 Spec Coherence (Phase 5)**: Depends on FIX-001 - Amendment 1.7 will correctly SKIP
- **US4 Bidirectional (Phase 6)**: Depends on FIX-001 - Amendment 1.7 will correctly SKIP
- **US5 Mutation Tests (Phase 7)**: Depends on T037 (mutmut install)
- **Polish (Phase 8)**: Depends on all user stories being complete

### User Story Dependencies

```
          ┌─────────────────────────────────────────────────────────────────┐
          │                    Phase 2: Foundational                        │
          │    Part A: FIX-001 (Template) - Fix detect_repo_type bug       │
          │    Part B: Add make targets to target repo                      │
          └─────────────────────────────────────────────────────────────────┘
                                        │
          ┌─────────────────────────────┼─────────────────────────────┐
          │                             │                             │
          ▼                             ▼                             ▼
    ┌───────────┐               ┌───────────┐               ┌───────────┐
    │    US1    │               │    US2    │               │   US3-5   │
    │  Property │               │ Canonical │               │ Coherence │
    │   Tests   │               │ Citations │               │  Bidir    │
    │   (P1)    │               │   (P1)    │               │ Mutation  │
    └───────────┘               └───────────┘               └───────────┘
          │                             │                         │
          │ ◄── MVP Checkpoint ──►      │                         │
          │                             │     (Amendment 1.7 SKIP) │
          └─────────────────────────────┴─────────────────────────┘
                                        │
                                        ▼
                              ┌───────────────────┐
                              │  Phase 8: Polish  │
                              │ (Full validation) │
                              └───────────────────┘
```

### Parallel Opportunities

**Phase 2 Part B** (Target Make Targets):

- T010, T011, T012 can run in parallel (different make targets)

**Phase 4** (Canonical Citations):

- T018, T019, T020, T021 can ALL run in parallel (different IAM files)

**Phase 5** (Spec Coherence):

- T025, T026 can run in parallel (different spec files)

---

## Parallel Example: User Story 2 (Canonical Citations)

```bash
# Launch all IAM file updates in parallel:
Task: "Add canonical citations to infrastructure/iam-policies/prod-deployer-policy.json"
Task: "Add canonical citations to infrastructure/iam-policies/preprod-deployer-policy.json"
Task: "Add canonical citations to docs/iam-policies/dev-deployer-policy.json"
Task: "Add canonical citations to infrastructure/terraform/ci-user-policy.tf"
```

---

## Implementation Strategy

### MVP First (User Stories 1 + 2 Only)

1. Complete Phase 1: Setup
2. Complete Phase 2: Foundational (Add make targets)
3. Complete Phase 3: User Story 1 (Property Tests) - resolves PROP-001 FAIL
4. Complete Phase 4: User Story 2 (Canonical Citations) - resolves CAN-002 FAIL
5. **STOP and VALIDATE**: Run `/validate` - both FAIL statuses should be resolved
6. This is MVP: No FAIL validators

### Full Delivery

1. Complete MVP (Phases 1-4)
2. Complete US3-US5 (Phases 5-7) - Amendment 1.7 will correctly SKIP validators after FIX-001
3. Run full validation in Phase 8

### Known Blockers (Deferred)

| Deferred ID      | Issue                         | Impact               | Status                             |
| ---------------- | ----------------------------- | -------------------- | ---------------------------------- |
| ~~DEFERRED-001~~ | detect_repo_type bug          | Blocks Amendment 1.7 | **IN SCOPE** (FIX-001, T005-T008)  |
| DEFERRED-002     | Subprocess pytest environment | May cause PROP-001   | Deferred (workaround: make target) |
| DEFERRED-003     | Canonical outside PR context  | CAN-002 detection    | Deferred (opportunistic fix later) |

---

## Notes

### 4-Entity Relationship (Critical - DO NOT CONFUSE)

| Entity                   | Repo                   | Path            | This Feature      |
| ------------------------ | ---------------------- | --------------- | ----------------- |
| Template Repo Spec       | terraform-gsk-template | specs/          | NO CHANGE         |
| Template Repo Validators | terraform-gsk-template | src/validators/ | FIX-001 ONLY      |
| Target Repo Spec         | sentiment-analyzer-gsk | specs/          | YES - Clean up    |
| Target Repo Src          | sentiment-analyzer-gsk | src/            | SPECOVERHAUL only |

### Key Rules

1. **[TEMPLATE]** tasks = CWD is `/home/traylorre/projects/terraform-gsk-template`
2. **[TARGET]** tasks = CWD is `/home/traylorre/projects/sentiment-analyzer-gsk`
3. **Template specs** define methodology - DO NOT CHANGE
4. **Template validators** - ONLY fix detect_repo_type bug (FIX-001)
5. **Target specs** - Clean up, add missing, archive obsolete
6. **Target src** - If mismatch found, tag `SPECOVERHAUL` and document, DO NOT FIX

### Success Criteria

- Per spec: Zero FAIL and Zero WARN required for success
- Per spec: 100% bidirectional coverage required
- Per user guidance: All test failures are source bugs until proven otherwise
- Per user guidance: Make implicit explicit - scaffolding code needs explicit specs
- SPECOVERHAUL findings documented in `sentiment-analyzer-gsk/SPECOVERHAUL.md`
- DEFERRED items documented in research.md
