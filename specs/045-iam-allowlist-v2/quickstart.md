# Quickstart: IAM Allowlist V2

**Feature**: 045-iam-allowlist-v2

## Overview

Add allowlist consumption to IAM validators to suppress documented acceptable risks.

## Prerequisites

- Python 3.11+
- PyYAML installed
- Existing validators: lambda_iam.py, sqs_iam.py

## Quick Implementation Guide

### 1. Add SUPPRESSED Status

```python
# src/validators/models.py
class Status(str, Enum):
    PASS = "PASS"
    FAIL = "FAIL"
    WARN = "WARN"
    SKIP = "SKIP"
    ERROR = "ERROR"
    SUPPRESSED = "SUPPRESSED"  # NEW
```

### 2. Create IAM Allowlist Loader

```python
# src/validators/iam_allowlist.py
from pathlib import Path
import yaml
from dataclasses import dataclass

@dataclass
class IAMAllowlistEntry:
    id: str
    finding_ids: list[str]
    justification: str
    canonical_source: str
    context_required: dict | None = None

def load_iam_allowlist(repo_path: Path) -> list[IAMAllowlistEntry] | None:
    """Load iam-allowlist.yaml from repo root."""
    allowlist_path = repo_path / "iam-allowlist.yaml"
    if not allowlist_path.exists():
        return None

    with open(allowlist_path) as f:
        data = yaml.safe_load(f)

    entries = []
    for p in data.get("patterns", []):
        # Only load entries with canonical_source (Amendment 1.5)
        if "canonical_source" not in p:
            continue
        entries.append(IAMAllowlistEntry(
            id=p["id"],
            finding_ids=p.get("finding_ids", []),
            justification=p["justification"],
            canonical_source=p["canonical_source"],
            context_required=p.get("context_required"),
        ))
    return entries
```

### 3. Add Context Evaluation

```python
# src/validators/iam_allowlist.py (continued)
import re

def derive_environment(file_path: str) -> str | None:
    """Derive environment from file path."""
    if re.search(r'(^|/)dev[-_/]|dev-deployer', file_path, re.I):
        return "dev"
    if re.search(r'(^|/)preprod[-_/]|preprod-deployer', file_path, re.I):
        return "preprod"
    if re.search(r'(^|/)prod[-_/]|prod-deployer', file_path, re.I):
        return "prod"
    return None

def check_passrole_scoped(content: str) -> bool:
    """Check if iam:PassRole has Resource constraints."""
    # Look for PassRole with specific Resource (not *)
    if '"iam:PassRole"' not in content:
        return True  # No PassRole = vacuously scoped
    # Check if Resource is NOT "*"
    if re.search(r'"Resource"\s*:\s*"\*"', content):
        return False
    return True
```

### 4. Integrate with Validator

```python
# In lambda_iam.py validate() method

from .iam_allowlist import load_iam_allowlist, should_suppress

class LambdaIAMValidator(BaseValidator):
    def validate(self, repo_path, files=None, staged_only=False):
        # Load allowlist once
        allowlist = load_iam_allowlist(repo_path)

        # ... existing scanning code ...

        for finding_data in raw_findings:
            # Check suppression before adding
            if allowlist and should_suppress(
                allowlist,
                finding_data.rule_id,
                finding_data.file_path,
                finding_data.content
            ):
                finding = self.create_finding(
                    id=finding_data.rule_id,
                    status=Status.SUPPRESSED,  # Not FAIL
                    # ... other fields ...
                )
            else:
                finding = self.create_finding(...)

            result.add_finding(finding)
```

### 5. Update Target Repo Allowlist

```yaml
# In target repo: iam-allowlist.yaml
# Update SQS-009 to cover dev environment
- id: dev-preprod-sqs-delete
  pattern: "sqs:DeleteQueue"
  classification: runtime
  finding_ids:
    - SQS-009
  justification: >
    Dev and preprod CI deployers require sqs:DeleteQueue for terraform destroy...
  canonical_source: "https://cheatsheetseries.owasp.org/cheatsheets/CI_CD_Security_Cheat_Sheet.html"
  context_required:
    environment:
      - dev
      - preprod
```

## Validation

```bash
# Run template validation against target
python3 scripts/validate-runner.py --repo ../sentiment-analyzer-gsk

# Expected: 0 CRITICAL, ≤2 HIGH (down from 5/5)
```

## Key Points

1. **Backward compatible**: Missing allowlist = no suppression
2. **Amendment 1.5 enforced**: Entries without canonical_source are skipped
3. **Most specific match**: Entry with most context conditions wins
4. **Audit trail**: Suppressed findings include `suppressed_by` entry ID
