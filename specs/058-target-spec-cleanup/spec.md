# Feature Specification: Target Repo Spec Cleanup

**Feature Branch**: `058-target-spec-cleanup`
**Created**: 2025-12-07
**Status**: Draft
**Input**: User description: "Resolve HIGH and MEDIUM severity validation findings in target repo (sentiment-analyzer-gsk). Clean up spec files for spec-coherence, bidirectional, and mutation validation failures so spec-driven development can resume without flawed specs."

## Clarifications

### Session 2025-12-07

- Q: What is the acceptable WARN count threshold for SC-002 to pass validation? → A: Zero WARN required (all warnings must be resolved)
- Q: What bidirectional coverage ratio threshold defines "acceptable" alignment? → A: 100% - Every spec requirement must map to code; implied/scaffolding requirements (e.g., provider blocks) must be added to specs to make implicit explicit
- Q: When property tests fail, what is the verification strategy? → A: All failures are source bugs until proven otherwise

## Context

This feature is a **cross-repo operation** with strict boundaries between what changes where.

### Repository Roles (DO NOT CONFUSE)

| Entity                       | Path                                     | Changes Allowed           | Notes                                                                |
| ---------------------------- | ---------------------------------------- | ------------------------- | -------------------------------------------------------------------- |
| **Template Repo Spec**       | `terraform-gsk-template/specs/`          | NO CHANGE                 | Defines methodology - already correct                                |
| **Template Repo Validators** | `terraform-gsk-template/src/validators/` | FIX-001, FIX-002, FIX-003 | Bug fixes to detect_repo_type, bidirectional mapper, canonical state |
| **Target Repo Spec**         | `sentiment-analyzer-gsk/specs/`          | YES - CHANGE              | Clean up spec files (US3, US4)                                       |
| **Target Repo Src**          | `sentiment-analyzer-gsk/src/`            | SPECOVERHAUL              | If spec changes reveal src mismatch, tag for future work             |

### Critical Boundaries

1. **Template specs** define the methodology - they are the source of truth, DO NOT CHANGE
2. **Template validators** run against target repos - FIX-001 and FIX-002 bug fixes allowed
3. **Target specs** are being cleaned up to comply with methodology
4. **Target src** may need changes if specs reveal mismatches - but this is FUTURE WORK tagged `SPECOVERHAUL`

### SPECOVERHAUL Tag

When cleaning up target repo specs (US3, US4), if you discover:

- Spec requirement with no corresponding src code → Tag `SPECOVERHAUL:MISSING_IMPL`
- Src code with no corresponding spec requirement → Tag `SPECOVERHAUL:UNDOCUMENTED`
- Spec-to-src mismatch → Tag `SPECOVERHAUL:DRIFT`

**Do NOT fix target repo src in this feature.** Document discrepancies and leave src changes as future work.

**Target Repository**: `/home/traylorre/projects/sentiment-analyzer-gsk`
**Template Repository**: `/home/traylorre/projects/terraform-gsk-template`
**Validation Run Date**: 2025-12-07
**Validation Results**:

- FAIL: canonical-validate (CAN-002), property (PROP-001)
- WARN: spec-coherence (SPEC-001), bidirectional (BIDIR-001), mutation (MUT-001)
- 8 findings SUPPRESSED via allowlist (intentional IAM permissions)

## User Scenarios & Testing _(mandatory)_

### User Story 0 - Fix detect_repo_type Bug (Priority: P0) - TEMPLATE FIX

As a developer running validators on any target repo, I want the `detect_repo_type` function to correctly identify my repo as "dependent" so that Amendment 1.7 SKIP behavior works correctly.

**Why this priority**: P0 because this bug blocks Amendment 1.7 for ALL target repos. Without this fix, target repos are incorrectly classified as "template" and validators FAIL instead of SKIP.

**Root Cause**: `src/validators/utils.py:76-79` has a fallback that classifies any repo with `constitution.md` as "template". This is wrong because target repos that adopt speckit also have a constitution.

**Solution**: Remove the constitution fallback. The rule is unambiguous:

- `terraform-gsk-template` is the ONLY template repo in existence, ever
- All other repos are dependent/target repos
- If git remote check fails, default to "dependent" (not "template")

**Independent Test**: Run `detect_repo_type("/home/traylorre/projects/sentiment-analyzer-gsk")` and verify it returns "dependent".

**Acceptance Scenarios**:

1. **Given** a repo with remote URL containing "terraform-gsk-template", **When** detect_repo_type is called, **Then** it returns "template"
2. **Given** a repo with any other remote URL, **When** detect_repo_type is called, **Then** it returns "dependent"
3. **Given** a repo with no git remote configured, **When** detect_repo_type is called, **Then** it returns "dependent" (not "template")
4. **Given** the target repo (sentiment-analyzer-gsk), **When** validators run, **Then** Amendment 1.7 SKIP behavior triggers correctly

---

### User Story 0.5 - Fix Bidirectional Mapper Bug (Priority: P0) - TEMPLATE FIX

As a developer running bidirectional validation on a target repo, I want the mapper to search all code directories (not just `src/`) so that infrastructure specs correctly map to their implementations.

**Why this priority**: P0 because this bug causes false-positive BIDIR-001 findings for all infrastructure/pipeline specs. Infrastructure specs produce changes in `infrastructure/` not `src/`, but the mapper only searches `src/`.

**Root Cause**: `src/validators/bidirectional/mapper.py` hardcodes `src/` as the only code directory to search. This is incorrect - specs can produce code in:

- `src/` (application code)
- `infrastructure/` (Terraform modules, IAM policies)
- `tests/` (test code, e2e suites)
- `.github/` (CI/CD workflows)

**Solution**: Implement two-phase matching in the mapper:

1. **Phase 1 (Feature Name Matching)**: Search for code files containing the feature keyword
2. **Phase 2 (File Reference Matching - FIX-002)**: If Phase 1 finds nothing, extract explicit file references from spec content (e.g., `ci-user-policy.tf`, `preprod-deployer-policy.json`) and search for those files

**Implementation Status**: ✅ COMPLETE

- Added `extract_file_references()` method to `SpecFile` class
- Updated `map_spec_to_code()` with two-phase matching
- Added `_find_files_by_name()` helper for exact filename search
- Added 7 unit tests for file reference extraction

**Known Limitation (Infrastructure Semantic Matching)**:
The bidirectional comparator uses token similarity to match requirements to code. This works well for Python code (functions, classes, docstrings) but does NOT work for:

- **JSON files**: No extractable symbols (functions, classes, docstrings)
- **Terraform HCL**: Only comments are extracted, no resource/data block semantics
- **YAML files**: No extractable symbols

For infrastructure-heavy repos like sentiment-analyzer-gsk, the bidirectional validator will show false-positive BIDIR-001 findings for requirements that ARE implemented in JSON/Terraform but can't be semantically matched. This requires either:

- LLM-based semantic comparison (enable `use_llm=True`)
- Manual verification and suppression via allowlist

**Independent Test**: Run bidirectional validation on spec `018-tfstate-bucket-fix` and verify it finds matching code files (even if individual requirements fail semantic matching).

**Acceptance Scenarios**:

1. **Given** an infrastructure spec (e.g., 018-tfstate-bucket-fix), **When** bidirectional validation runs, **Then** it finds matching code files in `infrastructure/` directory via file reference extraction
2. **Given** a test spec (e.g., 008-e2e-validation-suite), **When** bidirectional validation runs, **Then** it finds matching code in `tests/` directory
3. **Given** an application spec (e.g., existing Lambda specs), **When** bidirectional validation runs, **Then** it still finds matching code in `src/` directory
4. **Given** a spec with code in multiple directories, **When** bidirectional validation runs, **Then** it finds all matching code files
5. **Given** an infrastructure spec with JSON/Terraform files, **When** semantic matching runs, **Then** it MAY report false-positive BIDIR-001 findings due to limited symbol extraction (KNOWN LIMITATION)

---

### User Story 0.6 - Fix Canonical Validator PR State Bug (Priority: P0) - TEMPLATE FIX

As a developer running canonical validation on a target repo, I want the validator to skip merged/closed PRs so that historical PRs don't cause false-positive findings.

**Why this priority**: P0 because this bug causes CAN-002 findings for repos on branches with merged PRs. The validator incorrectly validates PR body even when PR is no longer open.

**Root Cause**: `src/validators/canonical.py:_get_pr_body()` returns the PR body regardless of PR state. `gh pr view` returns the PR for the current branch even if it's MERGED or CLOSED.

**Solution**: Rename `_get_pr_body()` to `_get_pr_info()` and return both body and state. Only validate OPEN PRs.

**Implementation Status**: ✅ COMPLETE

- Renamed `_get_pr_body()` to `_get_pr_info()` returning `(body, state)` tuple
- Added state check: only validate when `state == "OPEN"`
- Updated 17 unit tests to use new method signature
- Added 2 new tests for MERGED and CLOSED PR states

**Acceptance Scenarios**:

1. **Given** an OPEN PR modifying IAM files, **When** canonical validation runs, **Then** it checks for "Canonical Sources Cited" section
2. **Given** a MERGED PR, **When** canonical validation runs, **Then** it returns SKIP status
3. **Given** a CLOSED PR, **When** canonical validation runs, **Then** it returns SKIP status
4. **Given** no PR context, **When** canonical validation runs with staged_only=True, **Then** it returns CAN-001 warnings

---

### User Story 1 - Property Test Remediation (Priority: P1)

As a developer running validation on the target repo, I want property tests to pass so that invariant verification is active and catches bugs early.

**Why this priority**: PROP-001 FAIL blocks the validation suite from passing. Property tests are a gating requirement for spec-driven development.

**Independent Test**: Run `make test-property` in target repo and verify exit code 0.

**Acceptance Scenarios**:

1. **Given** a target repo with property tests, **When** I run `make test-property`, **Then** all property tests pass or are explicitly skipped with documented rationale
2. **Given** a missing hypothesis fixture, **When** I run property tests, **Then** the test framework skips gracefully with WARN, not FAIL
3. **Given** a flaky property test, **When** I investigate the root cause, **Then** I fix the source code or mark the test as expected-to-fail with issue tracking

---

### User Story 2 - Canonical Source Citations (Priority: P1)

As a developer reviewing infrastructure changes, I want all IAM policy changes to cite canonical AWS documentation so that permissions can be audited against authoritative sources.

**Why this priority**: CAN-002 FAIL indicates IAM policies lack canonical source citations. This is a security and audit requirement.

**Independent Test**: Run `/canonical-validate` on target repo and verify zero CAN-002 findings.

**Acceptance Scenarios**:

1. **Given** an IAM policy granting permissions, **When** the policy is reviewed, **Then** it includes a comment citing the AWS documentation URL for those permissions
2. **Given** a policy without canonical citation, **When** I add the citation, **Then** it follows the format `# Canonical: https://docs.aws.amazon.com/...`
3. **Given** a legacy policy without citations, **When** I remediate it, **Then** I verify the permissions are still required before adding citations

---

### User Story 3 - Spec Coherence Fixes (Priority: P2)

As a developer reading spec files, I want all specs to be internally consistent so that requirements don't contradict each other.

**Why this priority**: SPEC-001 WARN indicates contradictions or ambiguities in spec files. Incoherent specs lead to incorrect implementations.

**Independent Test**: Run `/spec-coherence-validate` on target repo and verify zero SPEC-001 findings.

**Acceptance Scenarios**:

1. **Given** a spec with contradictory requirements, **When** I review the spec, **Then** I resolve the contradiction by clarifying intent or removing duplicate requirements
2. **Given** a spec with ambiguous language, **When** I rewrite the requirement, **Then** it uses precise, testable language (MUST, SHOULD, MAY)
3. **Given** an outdated spec that no longer matches implementation, **When** I update it, **Then** I verify the implementation is correct before updating the spec

---

### User Story 4 - Bidirectional Verification Alignment (Priority: P2)

As a developer, I want spec requirements to map to implemented code so that I can trust the codebase implements what the spec describes.

**Why this priority**: BIDIR-001 WARN indicates spec-to-code drift. Untracked drift undermines the spec-driven methodology.

**Independent Test**: Run `/bidirectional-validate` on target repo and verify coverage ratio improves with each triage pass.

**Approach: Tag-based Triage (NOT Archival)**:

Per user guidance, archiving specs is counterproductive for spec-driven development because it:

- Loses context that specs document intent
- Creates busy work moving files around
- Increases recovery cost when specs need to be "poached back"

Instead, use **tag-based triage** to mark requirement status:

```markdown
<!-- IMPLEMENTED --> - Verified implemented in code
<!-- VAPORWARE --> - Not implemented, not planned (suppress in validator)
<!-- TODO --> - Not implemented, planned for future
<!-- PARTIAL --> - Partially implemented
```

**Multi-pass Refinement Strategy**:

1. **Pass 1**: Quick scan to tag obvious vaporware (frontend specs, UI specs without code)
2. **Pass 2**: Deep dive into code to verify claimed implementations
3. **Pass 3**: Reconcile tags, suppress validator findings for tagged items

**Acceptance Scenarios**:

1. **Given** a spec requirement with no corresponding code, **When** I investigate, **Then** I tag it as `<!-- VAPORWARE -->` or `<!-- TODO -->` based on intent
2. **Given** code with no corresponding spec requirement, **When** I investigate, **Then** I add the missing spec requirement to make implicit explicit
3. **Given** scaffolding/infrastructure code (e.g., provider blocks, backend config), **When** it has no spec, **Then** I add explicit spec requirements for it
4. **Given** a partial implementation, **When** I compare spec to code, **Then** I tag it as `<!-- PARTIAL -->` and document what's missing
5. **Given** a tagged vaporware requirement, **When** the validator runs, **Then** it MAY suppress the finding (future enhancement)

---

### User Story 5 - Mutation Test Infrastructure (Priority: P3)

As a developer, I want mutation testing configured so that test quality can be measured.

**Why this priority**: MUT-001 WARN indicates mutation testing is not running. This is lower priority than the FAIL items but important for test quality.

**Independent Test**: Run mutation tests and verify they complete (pass or provide actionable findings).

**Acceptance Scenarios**:

1. **Given** a target repo without mutmut installed, **When** I configure mutation testing, **Then** I add mutmut to dev dependencies
2. **Given** mutation tests that run slowly, **When** I configure the runner, **Then** I target only critical paths (not entire codebase)
3. **Given** surviving mutants, **When** I review them, **Then** I either strengthen tests or mark as acceptable with rationale

---

### Edge Cases

- What happens if a spec is completely obsolete and no longer implemented?
  - Answer: Tag all requirements with `<!-- VAPORWARE -->` to preserve context; archival loses spec intent
- What if fixing spec coherence requires changing implementation?
  - Answer: Per user instruction, investigate source code as root cause, don't assume validator is wrong
- What if property tests require external dependencies not available in CI?
  - Answer: Investigate as source bug first; if external dependency confirmed, mock per target repo constitution (Amendment 1.1)
- What if canonical sources don't exist for a permission?
  - Answer: Use AWS IAM Actions Reference as canonical source, cite the action page

## Requirements _(mandatory)_

### Functional Requirements

- **FR-000**: `detect_repo_type()` MUST return "dependent" for all repos except terraform-gsk-template
- **FR-001**: All property tests in target repo MUST pass or have documented skip reason
- **FR-002**: All IAM policies MUST include canonical source citations for granted permissions
- **FR-003**: Spec files MUST be internally coherent (no contradictions between requirements)
- **FR-004**: Spec requirements MUST have corresponding implementation code (tracked alignment)
- **FR-005**: Mutation testing MUST be configured and runnable (pass/fail/skip all acceptable)
- **FR-006**: Vaporware requirements MUST be tagged with `<!-- VAPORWARE -->` rather than archived/deleted (preserves context)
- **FR-007**: All fixes MUST be validated by re-running the appropriate validator
- **FR-008**: Implicit/scaffolding code MUST have explicit spec requirements added (no undocumented code)
- **FR-009**: Bidirectional mapper MUST search all code directories (`src/`, `infrastructure/`, `tests/`, `.github/`) not just `src/`

### Key Entities

- **Spec File**: Markdown file in `specs/###-feature-name/spec.md` describing feature requirements
- **Canonical Citation**: Comment in code citing authoritative AWS documentation URL
- **Property Test**: Hypothesis-based test verifying invariants
- **Mutation Test**: Test that verifies test quality by injecting code mutations

## Success Criteria _(mandatory)_

### Measurable Outcomes

- **SC-000**: `detect_repo_type(target_repo_path)` returns "dependent" (not "template")
- **SC-001**: `/validate target repo` shows zero FAIL status validators (excluding known infrastructure limitations)
- **SC-002**: `/validate target repo` shows zero WARN status validators (excluding known infrastructure limitations)
- **SC-003**: All IAM policies contain canonical source citations
- **SC-004**: No SPEC-001 findings in spec-coherence-validate output
- **SC-005**: Bidirectional coverage ratio meets threshold:
  - Python/application specs: 100% coverage
  - Infrastructure specs (JSON/Terraform): File matching PASS, semantic matching EXEMPT (known limitation)
- **SC-006**: Property tests run to completion without unexpected failures

### Bidirectional Exemption Criteria

Infrastructure specs (those referencing JSON/Terraform/HCL files) are EXEMPT from semantic matching requirements due to the known limitation documented in US-0.5. These specs MUST:

1. Have their referenced files found by the mapper (file matching)
2. Be manually verified that implementations match requirements
3. Document verification status in the spec's clarifications section

## Assumptions

- The target repo has 22 spec directories, some may be obsolete
- Property test failures are source bugs until proven otherwise (investigate code first)
- Canonical citations can be added without changing policy behavior
- Some specs may need to be archived rather than fixed (obsolete features)
- Mutation testing must pass or be explicitly configured (zero WARN required per SC-002)
