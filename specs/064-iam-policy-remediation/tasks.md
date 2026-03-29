# Tasks: IAM Policy Remediation - LAMBDA-007 Suppression Parity & IAM-002 Wildcard Justification

**Input**: Design documents from `/specs/064-iam-policy-remediation/`
**Prerequisites**: spec.md, plan.md

**Tests**: Not required - this is an investigation and documentation feature.

**Organization**: Tasks are grouped by user story to enable independent implementation and testing of each story.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (e.g., US1, US2)
- Include exact file paths in descriptions

## Path Conventions

- **Template repo**: `/home/traylorre/projects/terraform-gsk-template/`
- **Target repo**: `/home/traylorre/projects/sentiment-analyzer-gsk/`

---

## Phase 1: Setup (Investigation Infrastructure)

**Purpose**: Understand current state before making changes

- [x] T001 Read target repo iam-allowlist.yaml to verify existing LAMBDA-007 suppression entry in /home/traylorre/projects/sentiment-analyzer-gsk/iam-allowlist.yaml
- [x] T002 [P] Read template repo iam_allowlist.py to understand suppression logic in /home/traylorre/projects/terraform-gsk-template/src/validators/iam_allowlist.py
- [x] T003 [P] Read template repo lambda_iam.py to understand LAMBDA-007 detection in /home/traylorre/projects/terraform-gsk-template/src/validators/lambda_iam.py

---

## Phase 2: Foundational (Debug LAMBDA-007 Suppression)

**Purpose**: Determine why existing LAMBDA-007 suppression isn't being applied

**CRITICAL**: This investigation blocks all subsequent work

- [x] T004 Run /lambda-iam-validate on target repo with DEBUG logging enabled
- [x] T005 Verify allowlist file is being loaded (check log output for "Loaded N IAM allowlist entries")
- [x] T006 Check if passrole_scoped context evaluation is passing or failing
- [x] T007 If context fails: Identify specific condition in check_passrole_scoped() that fails
- [x] T008 Document root cause of LAMBDA-007 suppression failure in specs/064-iam-policy-remediation/investigation-notes.md

**Checkpoint**: Root cause of LAMBDA-007 suppression failure identified

---

## Phase 3: User Story 1 - Clean Validation Baseline (Priority: P1)

**Goal**: Run `/validate` on target repo with zero blocking LAMBDA-007 findings

**Independent Test**: Run `/validate` on sentiment-analyzer-gsk and verify LAMBDA-007 shows as SUPPRESSED

### Implementation for User Story 1

- [x] T009 [US1] If passrole_scoped check fails due to Resource:"\*" elsewhere in file: Add PR comment explaining AWS API limitation
- [x] T010 [US1] If allowlist not loading: Verify file path matches load_iam_allowlist() expectations
- [x] T011 [US1] If context condition missing: Add required context to iam-allowlist.yaml entry in /home/traylorre/projects/sentiment-analyzer-gsk/iam-allowlist.yaml
- [x] T012 [US1] Run /validate on target repo to verify LAMBDA-007 is now SUPPRESSED
- [x] T013 [US1] Document resolution in specs/064-iam-policy-remediation/investigation-notes.md

**Checkpoint**: LAMBDA-007 shows as SUPPRESSED in validation output

---

## Phase 4: User Story 2 - Canonical Source Compliance (Priority: P2)

**Goal**: All suppressed findings cite canonical AWS documentation per Amendment 1.5

**Independent Test**: Grep `iam-allowlist.yaml` for `canonical_source` field on all entries

### Implementation for User Story 2

- [x] T014 [US2] Verify existing LAMBDA-007 suppression has canonical_source field in /home/traylorre/projects/sentiment-analyzer-gsk/iam-allowlist.yaml
- [x] T015 [US2] Document IAM-002 canonical source justification (CloudFront List operations require \*) in /home/traylorre/projects/sentiment-analyzer-gsk/docs/IAM_JUSTIFICATIONS.md
- [~] T016 [P] [US2] Add inline comment to CloudFront statement in preprod-deployer-policy.json (SKIPPED: JSON doesn't support comments, documented in IAM_JUSTIFICATIONS.md instead)
- [~] T017 [P] [US2] Add inline comment to CloudFront statement in prod-deployer-policy.json (SKIPPED: JSON doesn't support comments)
- [x] T018 [US2] Verify all allowlist entries have canonical_source field

**Checkpoint**: All suppressions cite canonical sources per Amendment 1.5

---

## Phase 5: Polish & Validation

**Purpose**: Verify success criteria and close out feature

- [x] T019 Run full /validate on target repo and capture output
- [x] T020 Verify SC-001: Zero LAMBDA-007 FAIL findings (should be SUPPRESSED)
- [x] T021 Verify SC-002: IAM-002 is documented as expected (IAMValidator doesn't support suppression)
- [x] T022 Verify SC-003: All suppressions cite canonical sources
- [x] T023 Verify SC-004: git diff --stat src/ in template repo shows no changes
- [x] T024 Update spec.md status from Draft to Complete in /home/traylorre/projects/terraform-gsk-template/specs/064-iam-policy-remediation/spec.md

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies - can start immediately
- **Foundational (Phase 2)**: Depends on Setup completion - BLOCKS user stories
- **User Story 1 (Phase 3)**: Depends on Foundational - implements LAMBDA-007 fix
- **User Story 2 (Phase 4)**: Can run in parallel with US1 after Foundational
- **Polish (Phase 5)**: Depends on US1 and US2 completion

### User Story Dependencies

- **User Story 1 (P1)**: Depends on Phase 2 investigation results
- **User Story 2 (P2)**: Independent of US1 - can run in parallel

### Parallel Opportunities

- T002 and T003 can run in parallel (different files)
- T016 and T017 can run in parallel (different files)
- US1 and US2 can run in parallel after Foundational phase

---

## Parallel Example: Setup Phase

```bash
# Launch parallel setup tasks:
Task: "Read template repo iam_allowlist.py"
Task: "Read template repo lambda_iam.py"
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 1: Setup (understand current state)
2. Complete Phase 2: Foundational (debug LAMBDA-007)
3. Complete Phase 3: User Story 1 (fix LAMBDA-007)
4. **STOP and VALIDATE**: Verify LAMBDA-007 is SUPPRESSED
5. Proceed to US2 or close feature

### Investigation-First Approach

This feature is primarily investigation, not implementation:

1. T001-T003: Gather information
2. T004-T008: Debug root cause
3. T009-T013: Apply fix based on findings
4. T014-T018: Document justifications
5. T019-T024: Validate and close

---

## Notes

- [P] tasks = different files, no dependencies
- [Story] label maps task to specific user story for traceability
- Template repo changes require explicit user confirmation (per feature constraints)
- IAM-002 cannot be suppressed (IAMValidator lacks allowlist support) - document only
- Focus on LAMBDA-007 suppression as primary deliverable
