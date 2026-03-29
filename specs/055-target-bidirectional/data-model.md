# Data Model: Bidirectional Validation for Target Repos

**Feature**: 055-target-bidirectional
**Date**: 2025-12-06

## Entities

### SpecFile

Represents a specification file discovered in the target repository.

```python
@dataclass
class SpecFile:
    """A specification file in the target repository."""

    path: Path                    # Absolute path to spec.md
    feature_name: str             # Extracted from parent dir (e.g., "001-auth")
    feature_number: int | None    # Numeric prefix if present (e.g., 1)
    requirements: list[Requirement]  # Parsed FR-NNN requirements
    user_stories: list[UserStory]    # Parsed user stories
    acceptance_scenarios: list[AcceptanceScenario]  # Acceptance criteria

    @classmethod
    def from_path(cls, path: Path) -> "SpecFile":
        """Parse a spec file from disk."""
        ...
```

### Requirement

Represents a functional requirement extracted from a spec.

```python
@dataclass
class Requirement:
    """A functional requirement from the specification."""

    id: str                       # e.g., "FR-001"
    text: str                     # Full requirement text
    priority: str | None          # P1, P2, P3 if specified
    testable: bool                # True if has measurable criteria
    rfc2119_keyword: str | None   # MUST, SHOULD, MAY if present

    # Validation state (populated during comparison)
    implemented: bool = False
    implementation_path: Path | None = None
    implementation_line: int | None = None
    confidence: float = 0.0       # 0.0-1.0 semantic match confidence
```

### CodeModule

Represents a code file/module that may implement spec requirements.

```python
@dataclass
class CodeModule:
    """A code file that may implement requirements."""

    path: Path                    # Absolute path to source file
    language: str                 # python, terraform, javascript, etc.
    functions: list[str]          # Function/method names
    classes: list[str]            # Class names
    exports: list[str]            # Public exports (if applicable)

    # Extracted from content
    docstrings: list[str]         # Documentation strings
    comments: list[str]           # Inline comments
```

### AlignmentResult

Represents the alignment between a spec and its implementation.

```python
@dataclass
class AlignmentResult:
    """Result of comparing a spec to its implementation."""

    spec: SpecFile
    code_modules: list[CodeModule]

    # Gap classification (from research.md)
    missing: list[Requirement]      # Spec req without implementation
    undocumented: list[CodeModule]  # Code without spec coverage
    misinterpreted: list[tuple[Requirement, CodeModule, float]]  # Partial match
    aligned: list[tuple[Requirement, CodeModule, float]]  # Full match

    # Metrics
    coverage_ratio: float           # aligned / total requirements
    drift_score: float              # misinterpreted + missing / total

    def to_findings(self) -> list[Finding]:
        """Convert gaps to BIDIR-XXX findings."""
        ...
```

### BidirectionalFinding

Extended finding type for bidirectional validation.

```python
@dataclass
class BidirectionalFinding:
    """A finding from bidirectional validation."""

    id: str                        # BIDIR-001, BIDIR-002, etc.
    severity: Severity
    spec_file: str                 # Relative path to spec
    spec_requirement: str | None   # FR-NNN if applicable
    code_file: str | None          # Relative path to code if applicable
    code_line: int | None
    message: str
    remediation: str
    confidence: float              # Semantic match confidence

    # Source tracking
    comparison_mode: str           # "llm" or "offline"
    cached: bool                   # True if from cache
```

## Relationships

```
SpecFile 1──* Requirement      # A spec has many requirements
SpecFile 1──* UserStory        # A spec has many user stories
SpecFile 1──* AcceptanceScenario

AlignmentResult 1──1 SpecFile  # Each alignment is for one spec
AlignmentResult 1──* CodeModule # A spec may map to multiple code files

Requirement *──* CodeModule    # Many-to-many: requirements map to code
```

## State Transitions

### Validation Lifecycle

```
PENDING → DETECTING → PARSING → MAPPING → COMPARING → COMPLETE
                                              ↓
                                           DEGRADED (if API unavailable)
```

| State     | Description                              |
| --------- | ---------------------------------------- |
| PENDING   | Validation not started                   |
| DETECTING | Discovering spec files via glob          |
| PARSING   | Extracting requirements from specs       |
| MAPPING   | Finding corresponding code modules       |
| COMPARING | Running semantic comparison              |
| COMPLETE  | All comparisons done, findings generated |
| DEGRADED  | Completed with offline-only validation   |

### Requirement Status

```
UNKNOWN → IMPLEMENTED (confidence ≥ 0.7)
        → MISINTERPRETED (0.4 ≤ confidence < 0.7)
        → MISSING (confidence < 0.4 or no match)
```

## Validation Rules

### SpecFile Validation

- `path` must exist and be readable
- `feature_name` must be non-empty
- `requirements` should have at least one FR-NNN (warning if empty)

### Requirement Validation

- `id` must match pattern `FR-\d{3}`
- `text` must be non-empty
- `testable` should be True for MUST/SHALL requirements

### AlignmentResult Validation

- `coverage_ratio` must be 0.0-1.0
- `drift_score` must be 0.0-1.0
- All findings must have valid BIDIR-XXX IDs

## Finding Types

| ID        | Severity | Trigger                            | Remediation                                 |
| --------- | -------- | ---------------------------------- | ------------------------------------------- |
| BIDIR-001 | HIGH     | Requirement with no implementation | Add code to implement FR-NNN                |
| BIDIR-002 | MEDIUM   | Code with no spec documentation    | Add requirement to spec or remove dead code |
| BIDIR-003 | LOW      | Semantic drift (40-70% match)      | Update spec or code to align                |
| BIDIR-004 | INFO     | Spec lacks testable criteria       | Add measurable acceptance criteria          |
| BIDIR-005 | HIGH     | Contradiction in spec              | Resolve conflicting requirements            |

## Integration Points

### Input

- Target repository path (`Path`)
- Optional: specific spec files to validate (`list[Path]`)
- Optional: staged-only mode (`bool`)

### Output

- `ValidationResult` with `BidirectionalFinding` list
- Status: PASS, FAIL, WARN, SKIP, or ERROR
- YAML-serializable via `.to_dict()`

### Dependencies

- `.specify/verification/spec_parser` - `parse_spec_file()`
- `.specify/verification/llm_client` - `query_consensus()`
- `.specify/verification/bidirectional` - `classify_gaps()`, `calculate_semantic_similarity()`
