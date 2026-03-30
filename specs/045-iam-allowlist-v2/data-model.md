# Data Model: IAM Allowlist V2

**Feature**: 045-iam-allowlist-v2
**Date**: 2025-12-05

## Entities

### IAMAllowlistEntry

Represents a single allowlisted IAM finding pattern.

| Field            | Type                         | Required | Description                                                |
| ---------------- | ---------------------------- | -------- | ---------------------------------------------------------- |
| id               | string                       | Yes      | Unique identifier (e.g., "lambda-cicd-deployment")         |
| pattern          | string                       | Yes      | Regex pattern for matching (informational)                 |
| classification   | "runtime" \| "documentation" | Yes      | How entry is applied                                       |
| finding_ids      | list[string]                 | Yes      | Validator rule IDs to suppress (LAMBDA-007, SQS-009, etc.) |
| justification    | string                       | Yes      | Why this pattern is acceptable                             |
| canonical_source | string                       | Yes      | URL to authoritative documentation (Amendment 1.5)         |
| context_required | dict                         | No       | Conditions for context-aware suppression                   |

**context_required options**:

- `environment`: list[str] - Only suppress for matching environments (dev, preprod, prod)
- `passrole_scoped`: bool - Only suppress if PassRole has Resource constraints

### IAMAllowlistPath

Represents a file path excluded from scanning.

| Field         | Type   | Required | Description                      |
| ------------- | ------ | -------- | -------------------------------- |
| pattern       | string | Yes      | Glob/regex pattern for file path |
| justification | string | Yes      | Why path is excluded             |

### IAMAllowlist

Container for all allowlist data.

| Field        | Type                    | Required | Description                  |
| ------------ | ----------------------- | -------- | ---------------------------- |
| version      | string                  | Yes      | Schema version (e.g., "1.0") |
| last_updated | string                  | Yes      | ISO date of last update      |
| patterns     | list[IAMAllowlistEntry] | Yes      | Allowlisted finding patterns |
| paths        | list[IAMAllowlistPath]  | No       | Excluded file paths          |

### Status Enum Extension

Current values: PASS, FAIL, WARN, SKIP, ERROR

**Add new value**:

- `SUPPRESSED` - Finding matched allowlist entry with valid canonical source

### Finding (extended)

Existing Finding entity gains optional field:

| Field         | Type   | Required | Description                                |
| ------------- | ------ | -------- | ------------------------------------------ |
| suppressed_by | string | No       | Allowlist entry ID that caused suppression |

## State Transitions

### Finding Status Flow

```
[Detected] → (check allowlist) → [FAIL] (no match or no canonical source)
                              → [SUPPRESSED] (match with valid canonical source)
```

### Allowlist Loading Flow

```
[Validator Init] → (check iam-allowlist.yaml exists)
                       → [Allowlist Loaded] (file exists, valid YAML)
                       → [No Allowlist] (file missing - graceful degradation)
                       → [ERROR] (file exists but invalid)
```

## Context Evaluation Rules

### Environment Context

Derived from file path:

- `/dev-*`, `/dev/`, `dev-deployer` → environment = "dev"
- `/preprod-*`, `/preprod/`, `preprod-deployer` → environment = "preprod"
- `/prod-*`, `/prod/`, `prod-deployer` → environment = "prod"

### PassRole Scoped Context

Derived from policy content:

- If `iam:PassRole` action has `Resource` with specific ARN patterns → passrole_scoped = true
- If `iam:PassRole` has `Resource: "*"` → passrole_scoped = false

## Matching Algorithm

Per FR-008 (clarification session 2025-12-05):

1. Find all allowlist entries where `finding_ids` contains the finding's rule ID
2. For each matching entry, check if context_required conditions are satisfied
3. Filter to entries where all context conditions pass
4. Select entry with most context_required conditions (most specific)
5. If tie, use first matching entry
6. If selected entry has valid canonical_source, suppress finding

```python
def select_best_match(matches: list[IAMAllowlistEntry]) -> IAMAllowlistEntry | None:
    """Select most specific matching entry."""
    if not matches:
        return None

    # Sort by number of context conditions (descending)
    sorted_matches = sorted(
        matches,
        key=lambda e: len(e.context_required or {}),
        reverse=True
    )

    return sorted_matches[0]
```

## YAML Schema (iam-allowlist.yaml)

```yaml
version: "1.0"
last_updated: "2025-12-05"

patterns:
  - id: lambda-cicd-deployment
    pattern: "lambda:CreateFunction.*iam:PassRole"
    classification: runtime
    finding_ids:
      - LAMBDA-007
    justification: >
      CI/CD pipelines legitimately require lambda:CreateFunction + iam:PassRole...
    canonical_source: "https://docs.aws.amazon.com/prescriptive-guidance/..."
    context_required:
      passrole_scoped: true

  - id: dev-preprod-sqs-delete
    pattern: "sqs:DeleteQueue"
    classification: runtime
    finding_ids:
      - SQS-009
    justification: >
      Dev/preprod CI deployers require sqs:DeleteQueue for terraform destroy...
    canonical_source: "https://cheatsheetseries.owasp.org/..."
    context_required:
      environment:
        - dev
        - preprod

paths:
  - pattern: "tests/fixtures/.*"
    justification: "Test fixtures may contain intentional policy violations"
```
