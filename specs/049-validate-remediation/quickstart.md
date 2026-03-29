# Quickstart: Validation Finding Remediation

## Overview

This feature fixes three validation issues discovered by running `/validate` on sentiment-analyzer-gsk:

1. **Property tests fail to import** (PROP-001) - Fix pytest conftest pattern
2. **SQS-009 not suppressed** - Enhance allowlist CI policy detection
3. **IAM-006 false positive** - Skip Deny statements in wildcard detection

## Prerequisites

- Python 3.11+
- pytest with hypothesis plugin
- Access to both terraform-gsk-template and sentiment-analyzer-gsk repos

## Implementation Steps

### Step 1: Fix Property Test Imports (Target Repo)

In `sentiment-analyzer-gsk/tests/property/`, change test file imports from:

```python
# BEFORE - Direct import (FAILS)
from conftest import lambda_response, sentiment_response
```

To:

```python
# AFTER - No import needed, use fixture injection
# conftest.py strategies are automatically available as fixtures
```

Or if not using fixtures:

```python
# AFTER - Relative import from same package
from .conftest import lambda_response, sentiment_response
```

### Step 2: Add CI Policy Detection (Template Repo)

In `src/validators/iam_allowlist.py`, add pattern for CI policies:

```python
def is_ci_policy(file_path: str) -> bool:
    """Check if file is a CI/CD deployment policy."""
    return bool(re.search(r"ci[-_]?user.*\.tf$|ci[-_]?policy", file_path, re.IGNORECASE))
```

Update `evaluate_context_conditions()` to handle `ci_policy` context.

### Step 3: Add Deny Effect Detection (Template Repo)

In `src/validators/iam.py`, modify `_check_file()` to skip Deny statements:

```python
def _is_deny_statement_context(self, content: str, line_num: int) -> bool:
    """Check if the line is within a Deny statement context."""
    # Parse JSON or analyze surrounding lines for Effect: Deny
    ...
```

## Verification

After implementation:

```bash
# Verify property tests pass
cd /path/to/sentiment-analyzer-gsk
pytest tests/property/ -v

# Verify validation findings reduced
cd /path/to/terraform-gsk-template
python3 scripts/validate-runner.py --repo /path/to/sentiment-analyzer-gsk
```

Expected outcomes:

- Property tests: 33/33 passing
- HIGH findings: 0 unsuppressed
- IAM-006 findings: 0 for Deny statements
