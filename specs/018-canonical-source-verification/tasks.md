# Tasks: Canonical Source Verification & Cognitive Discipline

**Input**: Design documents from `/specs/018-canonical-source-verification/`
**Prerequisites**: plan.md (required), spec.md (required for user stories)

**Tests**: Not applicable - this is a documentation/process feature validated by manual review.

**Organization**: Tasks are grouped by user story to enable independent implementation and testing of each story.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (e.g., US1, US2, US3)
- Include exact file paths in descriptions

## Path Conventions

This feature modifies documentation and configuration files only:
- `.specify/memory/constitution.md` - Constitution document
- `.specify/testing/taxonomy-registry.yaml` - Testing taxonomy
- `.github/PULL_REQUEST_TEMPLATE.md` - PR template

---

## Phase 1: Setup (Verification)

**Purpose**: Verify prerequisites exist and are in expected state

- [x] T001 Verify constitution exists and is at version 1.4 in .specify/memory/constitution.md
- [x] T002 Verify taxonomy registry exists and has valid YAML structure in .specify/testing/taxonomy-registry.yaml
- [x] T003 Check if PR template exists in .github/PULL_REQUEST_TEMPLATE.md (create directory if needed)

---

## Phase 2: User Story 3 - Constitution Amendment (Priority: P1) 🎯 MVP

**Goal**: Enshrine four cognitive anti-patterns as absolute rules in the constitution

**Independent Test**: Read constitution and verify Section 10 + Amendment 1.5 exist with all four principles

### Implementation for User Story 3

- [x] T004 [US3] Add Section "10) Canonical Source Verification & Cognitive Discipline" to .specify/memory/constitution.md
- [x] T005 [US3] Add subsection "Cognitive Anti-Patterns (ABSOLUTE RULES)" with four principles in .specify/memory/constitution.md
- [x] T006 [US3] Add subsection "Canonical Source Requirements" with 5-step verification process in .specify/memory/constitution.md
- [x] T007 [US3] Add subsection "Verification Gate (PR Template)" describing PR requirements in .specify/memory/constitution.md
- [x] T008 [US3] Add Amendment 1.5 entry to Amendments section in .specify/memory/constitution.md
- [x] T009 [US3] Update version to 1.5 and Last Amended date to 2025-12-03 in .specify/memory/constitution.md

**Checkpoint**: Constitution Amendment 1.5 complete - cognitive discipline principles enshrined

---

## Phase 3: User Story 1 & 2 - PR Template Gate (Priority: P1/P2)

**Goal**: Add active verification checklist to PR template for developer and reviewer enforcement

**Independent Test**: Create a test PR and verify the template includes canonical source citation section

### Implementation for User Story 1 & 4

- [x] T010 [US1] Create .github/ directory if it does not exist
- [x] T011 [US1] Create or update .github/PULL_REQUEST_TEMPLATE.md with "Canonical Sources Cited" section
- [x] T012 [US1] Add checklist item "[ ] Cited canonical source for external system behavior claims (IAM, APIs, libraries)" to template
- [x] T013 [US1] Add HTML comment with format instructions for canonical source citations

**Checkpoint**: PR template gate active - developers guided to cite sources, reviewers can validate

---

## Phase 4: User Story 5 - Taxonomy Stubs (Priority: P3)

**Goal**: Add minimal stubs to testing taxonomy for future formalization (TAXGAP1)

**Independent Test**: Parse taxonomy YAML and verify three stub entries exist with status: stub

### Implementation for User Story 5

- [x] T014 [P] [US5] Add concern stub `canonical_source_verification` to .specify/testing/taxonomy-registry.yaml
- [x] T015 [P] [US5] Add property stub `external_behavior_claims_cited` to .specify/testing/taxonomy-registry.yaml
- [x] T016 [P] [US5] Add validator stub `canonical_source_citation_validator` to .specify/testing/taxonomy-registry.yaml

**Checkpoint**: Taxonomy stubs in place - ready for future /speckit.specify formalization

---

## Phase 5: Polish & Validation

**Purpose**: Final validation and commit preparation

- [x] T017 Validate constitution YAML-like indentation is consistent in .specify/memory/constitution.md
- [x] T018 Validate taxonomy YAML parses without errors using `python -c "import yaml; yaml.safe_load(open('.specify/testing/taxonomy-registry.yaml'))"`
- [x] T019 Validate PR template renders correctly in GitHub preview
- [x] T020 Update spec status from Draft to Complete in specs/018-canonical-source-verification/spec.md
- [x] T021 Commit all changes with message referencing Amendment 1.5

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies - verification only
- **Constitution (Phase 2)**: Depends on Setup - core policy document
- **PR Template (Phase 3)**: Depends on Constitution (references its rules)
- **Taxonomy (Phase 4)**: Can run in parallel with Phase 3 (different files)
- **Polish (Phase 5)**: Depends on all previous phases

### User Story Dependencies

- **User Story 3 (Constitution)**: No dependencies - creates the policy
- **User Story 1 & 4 (PR Template)**: Logically depends on US3 (implements its rules)
- **User Story 5 (Taxonomy)**: No dependencies - independent scaffolding

### Parallel Opportunities

- T014, T015, T016 can all run in parallel (different YAML sections)
- Phase 3 and Phase 4 can run in parallel (different files)

---

## Parallel Example: Taxonomy Stubs

```bash
# Launch all taxonomy stub tasks together:
Task: "Add concern stub canonical_source_verification to .specify/testing/taxonomy-registry.yaml"
Task: "Add property stub external_behavior_claims_cited to .specify/testing/taxonomy-registry.yaml"
Task: "Add validator stub canonical_source_citation_validator to .specify/testing/taxonomy-registry.yaml"
```

---

## Implementation Strategy

### MVP First (Constitution Only)

1. Complete Phase 1: Setup verification
2. Complete Phase 2: Constitution Amendment
3. **STOP and VALIDATE**: Amendment 1.5 exists with all four principles
4. This alone establishes the policy even without enforcement automation

### Full Implementation

1. Phase 1: Verify prerequisites
2. Phase 2: Constitution Amendment (creates policy)
3. Phase 3: PR Template (enforces policy via checklist)
4. Phase 4: Taxonomy Stubs (scaffolds future automation)
5. Phase 5: Validation and commit

---

## Notes

- This is a documentation/process feature - no code testing required
- Manual validation via reading documents and checking structure
- All files are in version control - standard git workflow applies
- Commit after each phase for easy rollback if needed
- User Story 2 (Gatekeeper Validates) is a human process, not a task - enabled by PR template
