# Feature Specification: Bidirectional Validation for Target Repos

**Feature Branch**: `055-target-bidirectional`
**Created**: 2025-12-07
**Status**: Draft
**Input**: User description: "Add bidirectional validation for target repo (sentiment-analyzer-gsk)"

## User Scenarios & Testing _(mandatory)_

### User Story 1 - Intrinsic Bidirectional Detection (Priority: P1)

When a developer runs `/validate` against a target repo that has specification files but no `make test-bidirectional` target, the BidirectionalValidator should automatically detect spec files and validate them against corresponding code implementations using semantic comparison.

**Why this priority**: This enables bidirectional validation to work on ANY target repo with specs, without requiring the target repo to adopt template-specific infrastructure. Zero friction adoption.

**Independent Test**: Run `/validate --validator bidirectional --repo /path/to/target-repo` on a repo with `specs/*/spec.md` files but no `make test-bidirectional`; validator should PASS/FAIL based on spec-code alignment, not SKIP.

**Acceptance Scenarios**:

1. **Given** a target repo with `specs/001-feature/spec.md` and corresponding code in `src/`, **When** BidirectionalValidator runs without `make test-bidirectional`, **Then** validator uses intrinsic detection to find and validate specs
2. **Given** a target repo spec with acceptance scenarios, **When** BidirectionalValidator analyzes the code, **Then** it verifies each scenario has corresponding implementation
3. **Given** a spec requirement "System MUST X", **When** code does not implement X, **Then** validator reports BIDIR-001 finding with specific spec-code mismatch

---

### User Story 2 - Thin Make Target Delegation (Priority: P2)

Target repos can optionally add a thin `make test-bidirectional` target that delegates to template-provided verification logic. This allows target repos to customize thresholds or add project-specific checks while keeping methodology implementation in the template.

**Why this priority**: Supports progressive adoption - repos can start with intrinsic detection (P1) then add make target for customization.

**Independent Test**: Add `make test-bidirectional` to target repo that invokes template tooling; verify validator uses make target when present.

**Acceptance Scenarios**:

1. **Given** a target repo with `make test-bidirectional` target, **When** BidirectionalValidator runs, **Then** validator uses make target instead of intrinsic detection
2. **Given** make target fails, **When** validator runs, **Then** validator reports FAIL with make output
3. **Given** make target passes, **When** validator runs, **Then** validator reports PASS

---

### User Story 3 - Semantic Spec-Code Comparison (Priority: P1)

The bidirectional verification must use semantic comparison, not string matching. If a spec says "users can authenticate" and code implements `def login()`, that should match semantically. The methodology is the "secret sauce" in the template repo.

**Why this priority**: String matching is brittle and creates false negatives. Semantic comparison is the core value of this methodology.

**Independent Test**: Create a spec with requirement "System MUST allow users to search products" and code with `def find_products()` - verify semantic match is detected.

**Acceptance Scenarios**:

1. **Given** spec requirement using different terminology than code, **When** semantic comparison runs, **Then** equivalent concepts are matched
2. **Given** spec acceptance scenario "user can view dashboard", **When** code has `render_dashboard()`, **Then** scenario is marked as implemented
3. **Given** spec and code with semantic drift (spec updated but code not), **When** comparison runs, **Then** drift is detected and reported

---

### User Story 4 - Code-to-Spec Regeneration Check (Priority: P3)

For round-trip verification, the system should be able to infer what a spec SHOULD say based on the code, and compare that against what the spec DOES say. This detects stale specs that no longer reflect reality.

**Why this priority**: Detects spec rot - when code evolves but specs don't get updated. Lower priority because spec-to-code is more critical.

**Independent Test**: Modify code to add a feature not in spec; verify validator detects "undocumented functionality".

**Acceptance Scenarios**:

1. **Given** code with functionality not mentioned in spec, **When** code-to-spec analysis runs, **Then** undocumented functionality is flagged
2. **Given** spec with deprecated requirement that code removed, **When** analysis runs, **Then** stale spec content is detected
3. **Given** fully aligned spec and code, **When** round-trip verification runs, **Then** no drift is reported

---

### Edge Cases

- What happens when spec file exists but has no acceptance scenarios?
  - Answer: Validator should report INFO-level finding "Spec lacks acceptance scenarios" but not FAIL
- How does system handle multiple specs mapping to same code module?
  - Answer: Each spec is validated independently; code can satisfy multiple specs
- What if target repo has no specs at all?
  - Answer: Validator SKIPs with reason "no specs/\*/spec.md files found"
- What if code uses different language than expected?
  - Answer: Semantic comparison is language-agnostic; methodology handles multiple languages

## Requirements _(mandatory)_

### Functional Requirements

- **FR-001**: BidirectionalValidator MUST use intrinsic detection when `make test-bidirectional` is unavailable
- **FR-002**: Intrinsic detection MUST find all `specs/*/spec.md` files in target repo
- **FR-003**: For each spec, validator MUST identify corresponding code based on feature name/path mapping
- **FR-004**: Validator MUST use semantic comparison, not string matching, to verify spec-code alignment
- **FR-005**: Validator MUST report specific findings for spec requirements without code implementation
- **FR-006**: Validator MUST report specific findings for code functionality without spec documentation
- **FR-007**: Validator MUST support optional `make test-bidirectional` target for custom verification
- **FR-008**: When make target exists, validator MUST delegate to it instead of intrinsic detection
- **FR-009**: Implementation logic MUST remain in template repo (target repos get thin delegation only)
- **FR-010**: Validator MUST produce actionable findings with file paths, line numbers, and remediation

### Key Entities

- **Specification**: A `spec.md` file containing user stories, acceptance scenarios, and requirements
- **Implementation**: Code in `src/` that fulfills specification requirements
- **Alignment**: The degree to which code implements spec requirements (semantic match)
- **Drift**: Divergence between spec and code that indicates staleness or missing implementation

## Success Criteria _(mandatory)_

### Measurable Outcomes

- **SC-001**: Running `/validate --validator bidirectional` on sentiment-analyzer-gsk produces PASS or actionable findings (not SKIP)
- **SC-002**: 100% of spec requirements with corresponding implementations are detected as aligned
- **SC-003**: 100% of spec requirements WITHOUT implementations produce BIDIR-XXX findings
- **SC-004**: Target repo requires only thin make target (under 10 lines) to customize validation
- **SC-005**: Semantic comparison correctly matches equivalent concepts (e.g., "authenticate" matches "login") in 90%+ of cases
- **SC-006**: Zero methodology implementation code copied into target repo

## Assumptions

- Target repos follow convention of `specs/###-feature-name/spec.md` for specifications
- Target repos have code in `src/` or similar conventional locations
- Semantic comparison can leverage existing NLP/embedding capabilities in template
- Target repo constitution does not affect bidirectional validation behavior
