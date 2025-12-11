# Tasks: Validation Findings Remediation

**Input**: Design documents from `/specs/084-validation-findings-remediation/`
**Prerequisites**: plan.md (complete), spec.md (complete)

**Tests**: N/A - configuration changes only, validated by re-running validators.

**Organization**: Tasks grouped by functional requirement.

## Format: `[ID] [P?] Description`

- **[P]**: Can run in parallel (different files, no dependencies)

---

## Phase 1: IAM Allowlist (FR-001, FR-002)

**Purpose**: Suppress false-positive CloudFront wildcard finding

- [x] T001 Add cloudfront-cache-policy-read entry to `iam-allowlist.yaml`

---

## Phase 2: Spec Status Tags (FR-003, FR-004, FR-005)

**Purpose**: Mark roadmap specs with status to distinguish from missing implementations

- [x] T002 [P] Add `Status: Planned` to `specs/079-e2e-endpoint-roadmap/spec.md`
- [x] T003 [P] Add `Status: Planned` to `specs/080-fix-integ-test-failures/spec.md`
- [x] T004 [P] Add `Status: In Progress` to `specs/082-fix-sse-e2e-timeouts/spec.md`

---

## Phase 3: Orphan Code Coverage (FR-006, FR-007)

**Purpose**: Create spec for orphan validators

- [x] T005 Spec `specs/075-validation-gaps/` already exists
- [x] T006 Updated `specs/075-validation-gaps/spec.md` with implementation section

---

## Phase 4: Makefile Targets (FR-008, FR-009)

**Purpose**: Add missing make targets for skipped validators

- [x] T007 Add `test-spec` target to Makefile
- [x] T008 Add `test-mutation` target to Makefile

---

## Phase 5: Validation

**Purpose**: Verify remediation worked

- [x] T009 Re-run `/validate --repo` from template and verify:
  - IAM-002 finding: STILL FLAGGED (allowlist entry added but IAM validator doesn't read allowlist yet - FW-003)
  - spec-coherence validator: NOW RUNS (was SKIP, now PASS)
  - mutation validator: NOW RUNS (was SKIP, now PASS)
  - MEDIUM findings for orphan code: RESOLVED (075 spec covers them)
- [x] T010 Update tasks.md with results

---

## Dependencies & Execution Order

- Phase 1 through 4 can run in parallel (different files)
- Phase 5 depends on all previous phases

## Success Criteria Mapping

| Success Criteria | Tasks | Validation |
|-----------------|-------|------------|
| SC-001 (IAM wildcard suppressed) | T001 | `/iam-validate` passes |
| SC-002 (Status tags) | T002-T004 | Grep for `Status:` |
| SC-003 (Orphan code covered) | T005-T006 | MEDIUM findings = 0 |
| SC-004 (Makefile targets) | T007-T008 | `make test-spec` works |
| SC-005 (Validators don't skip) | T009 | No SKIP status |
