# Feature Specification: Formatter Pragma Comment Stability

**Feature Branch**: `057-pragma-comment-stability`
**Created**: 2025-12-09
**Status**: Draft
**Input**: User description: "Ensure code formatters never break security and linting suppression comments"

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Developer Adds Pragma Comment (Priority: P1)

A developer adds a security suppression comment (`# nosec`) or linting suppression comment (`# noqa`) to an intentionally flagged line. When they run the formatter and linter, the pragma comment remains attached to the correct line of code it was meant to suppress.

**Why this priority**: This is the core problem - formatters moving pragma comments away from their intended targets silently breaks security suppressions, causing either false positives to resurface or (worse) false negatives where suppressions apply to wrong lines.

**Independent Test**: Can be fully tested by adding a pragma comment to a long line, running the formatter, and verifying the comment still suppresses the intended finding.

**Acceptance Scenarios**:

1. **Given** a line with `# noqa: E501` comment exceeding 88 characters, **When** the formatter runs, **Then** the `# noqa` comment remains on the same logical statement it was suppressing
2. **Given** a line with `# nosec B324` for MD5 usage, **When** the formatter runs, **Then** Bandit does not flag that line as a security issue
3. **Given** a multiline statement with pragma comment on last line, **When** the formatter reflows the statement, **Then** the pragma comment applies to the correct code element

---

### User Story 2 - CI Pipeline Validates Pragma Comment Placement (Priority: P1)

The CI pipeline automatically detects when a pragma comment has become misaligned from its intended target, preventing silent security regression.

**Why this priority**: Without automated detection, misaligned pragma comments silently break security suppressions and go unnoticed until a manual audit.

**Independent Test**: Can be tested by intentionally misaligning a pragma comment and verifying CI fails with a clear error message.

**Acceptance Scenarios**:

1. **Given** a pragma comment that has drifted to a different line than the code it suppresses, **When** CI runs, **Then** the pipeline fails with a clear error identifying the misaligned comment
2. **Given** all pragma comments correctly aligned, **When** CI runs, **Then** the validation passes without warnings

---

### User Story 3 - Developer Audits Existing Pragma Comments (Priority: P2)

A developer can audit all existing pragma comments in the codebase to verify they are correctly placed and still needed.

**Why this priority**: The codebase has 25+ noqa and 6+ nosec comments that may already be misaligned from previous formatter runs. Before solving the ongoing problem, we need to validate the current state.

**Independent Test**: Can be tested by running an audit command and reviewing its output against known pragma comment locations.

**Acceptance Scenarios**:

1. **Given** a codebase with multiple pragma comments, **When** the audit runs, **Then** each comment is listed with its location and whether it appears to be correctly aligned
2. **Given** a pragma comment that no longer suppresses any active finding, **When** the audit runs, **Then** the comment is flagged as potentially obsolete

---

### User Story 4 - Team Migrates to Stable Formatter (Priority: P3)

If the chosen solution requires changing formatters, the migration is documented, tested, and causes zero disruption to existing code semantics.

**Why this priority**: Formatter migration affects the entire codebase and requires careful coordination, but is only needed if the current formatter cannot be configured to preserve pragma comments.

**Independent Test**: Can be tested by running both old and new formatters on a test file and comparing semantic equivalence of outputs.

**Acceptance Scenarios**:

1. **Given** a decision to migrate formatters, **When** the migration runs, **Then** all existing code formatting is preserved or explicitly reviewed
2. **Given** a migration plan, **When** developers review changed files, **Then** only formatting differences exist (no semantic code changes)

---

### Edge Cases

- What happens when a pragma comment is on a line that gets split across multiple lines?
- How does the system handle pragma comments in multiline strings or docstrings?
- What happens when multiple pragma comments exist on the same line (`# noqa: E501 # nosec B324`)?
- How are pragma comments handled in generated code or vendored dependencies?
- What happens when a pragma comment references a rule that no longer exists in the linter version?

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: System MUST preserve pragma comment alignment after formatter execution - comments must remain on the same logical statement they were originally placed on
- **FR-002**: System MUST detect when a pragma comment has become misaligned from its intended target during CI validation
- **FR-003**: System MUST provide an audit capability to list all pragma comments and their alignment status
- **FR-004**: System MUST support all pragma comment types used in Python: `# noqa`, `# nosec`, `# type:`, `# fmt:`, `# pylint:`
- **FR-005**: System MUST NOT require modifying application code to add special markers or annotations beyond standard pragma comments
- **FR-006**: System MUST work with both pre-commit hooks and CI pipeline execution
- **FR-007**: System MUST provide clear error messages when pragma comment drift is detected, including file, line, and original target
- **FR-008**: System MUST support a documented process for handling pragma comments on lines that exceed line length limits even without the comment

### Key Entities

- **Pragma Comment**: An inline comment that controls linter/security tool behavior for a specific line (e.g., `# noqa: E501`, `# nosec B324`)
- **Comment Target**: The specific code element (variable, function call, expression) that a pragma comment is intended to suppress findings for
- **Comment Drift**: The condition where a pragma comment has moved (due to formatting) to a different line than its intended target
- **Suppression Rule**: The specific linter/security rule being suppressed (e.g., E501, B324, S108)

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Zero pragma comment drift after any formatter execution - 100% of pragma comments remain aligned with their targets
- **SC-002**: All 31+ existing pragma comments (25 noqa + 6 nosec) validated and confirmed correctly placed
- **SC-003**: CI pipeline detects 100% of intentionally misaligned pragma comments (tested with at least 5 deliberately broken cases)
- **SC-004**: Audit report generated in under 10 seconds for full codebase scan
- **SC-005**: Solution documented in decision record with tradeoff analysis of evaluated alternatives

## Assumptions

- The existing pragma comments in the codebase were originally placed correctly and serve valid purposes (will be validated in P2 story)
- Black 25.11.0 and Ruff v0.1.6 are the current formatter/linter versions (confirmed from .pre-commit-config.yaml)
- Line length limit is 88 characters (Black default, confirmed in pyproject.toml)
- Python 3.13 is the target runtime (confirmed in pyproject.toml)
- Pre-commit hooks and CI must remain in sync (both must use same formatter behavior)

## Research Questions

The following questions require investigation during the planning phase to inform the technical approach:

1. **Formatter Behavior Analysis**: How do Black, Ruff formatter, autopep8, and yapf each handle pragma comments on long lines? Which formatters exclude pragma comments from line length calculations?

2. **Industry Best Practices**: What is the industry standard for managing pragma comments in large Python codebases? Are there established tools or patterns?

3. **Detection Mechanisms**: Can pragma comment drift be detected programmatically? What heuristics identify when a comment has moved away from its intended target?

4. **Migration Cost Assessment**: If formatter migration is required, what is the blast radius? How many files change? Can changes be reviewed incrementally?

5. **Pre-processing vs Native Support**: Are there pre/post processing tools that preserve pragma comments regardless of formatter choice, or is native formatter support required?

## Current State Inventory

**Pragma Comment Types Found**:
- `# noqa`: 25 instances (E402 import order, S108 /tmp usage, S311 random, S110 bare except, S105 error codes, ARG001 unused args, S202 tarfile)
- `# nosec`: 6 instances (B324 MD5, B108 /tmp storage, B202 tarfile extractall)
- `# type:`: 1 instance (type ignore for arg-type)
- `# fmt:`: 0 instances
- `# pylint:`: 0 instances

**Current Tooling**:
- Formatter: Black 25.11.0 + ruff-format (both enabled in pre-commit)
- Linter: Ruff v0.1.6
- Security: Bandit 1.7.10, detect-secrets, gitleaks

**Files with Most Pragma Comments**:
- `src/lambdas/ingestion/handler.py`: 8 noqa (E402 - X-Ray patching requires import order)
- `src/lambdas/analysis/sentiment.py`: 3 nosec + 1 noqa (Lambda /tmp storage)
- `src/lambdas/analysis/handler.py`: 4 noqa (E402 - X-Ray patching)
