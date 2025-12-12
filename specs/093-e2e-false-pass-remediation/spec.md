# 093: E2E False-Pass Remediation

## Problem Statement

The E2E test suite contains **139 `pytest.skip()` calls** that mask real failures, making the tests meaningless. When an endpoint returns 500, the test skips instead of failing. When functionality is missing, the test skips instead of documenting the gap. This creates a **false sense of confidence** - the test suite appears healthy (green) while hiding critical issues.

### Severity: Critical

A test suite that passes when the system is broken provides negative value - it's worse than having no tests at all because it actively deceives.

## Current State Analysis

### Skip Categories (139 total)

| Category | Count | Example | Risk Level |
|----------|-------|---------|------------|
| **500 Error Masking** | 6 | `if status_code == 500: pytest.skip("API issue")` | **CRITICAL** |
| **Endpoint Not Implemented** | 59 | `pytest.skip("endpoint not implemented")` | **HIGH** |
| **Config Creation Unavailable** | 17 | `pytest.skip("Config creation not available")` | **HIGH** |
| **Rate Limit Not Triggered** | 4 | `pytest.skip("Could not trigger rate limit")` | MEDIUM |
| **Environment Constraints** | ~20 | `pytest.skip("PREPROD_API_URL not set")` | LOW |
| **Synthetic Token Unavailable** | ~10 | `pytest.skip("Synthetic token not available")` | MEDIUM |
| **Other** | ~23 | Various infrastructure conditions | VARIES |

### Files with Most Skips

```
tests/e2e/test_notifications.py          - 9 skips
tests/e2e/test_anonymous_restrictions.py - 7 skips
tests/e2e/test_auth_magic_link.py        - 6 skips (500 masking)
tests/e2e/test_market_status.py          - 6 skips
tests/e2e/test_rate_limiting.py          - 5 skips (500 masking)
tests/e2e/test_failure_injection.py      - 5 skips
tests/e2e/test_dashboard_buffered.py     - 3 skips
tests/e2e/test_circuit_breaker.py        - 3 skips
```

### The Core Problem

```python
# WRONG: This test passes (via skip) when the server is broken
if response.status_code == 500:
    pytest.skip("Magic link endpoint unavailable - email service may not be configured")
```

A 500 error is a **server failure**, not an acceptable alternative outcome. The test should:
1. **FAIL** if the endpoint is supposed to work
2. Be marked `@pytest.mark.xfail` if the endpoint is known broken with a ticket
3. Be **deleted** if the functionality doesn't exist and isn't planned

## Success Criteria

| ID | Criterion | Measurement |
|----|-----------|-------------|
| SC-001 | Zero 500-error masking skips | `grep -c "status_code == 500.*skip" == 0` |
| SC-002 | All "not implemented" skips converted to xfail with ticket | Each xfail has issue URL |
| SC-003 | Skip rate < 15% in CI | TestMetrics.skip_rate < 0.15 |
| SC-004 | No new false-pass patterns in future PRs | Pre-commit hook validates |
| SC-005 | Documented remediation for each category | Audit report complete |

## Remediation Strategy

### Phase 1: Critical - Remove 500 Error Masking (6 files)

**Action**: Delete `if status_code == 500: pytest.skip()` patterns. Let tests fail.

Files:
- `tests/e2e/test_auth_magic_link.py` (5 instances)
- `tests/e2e/test_rate_limiting.py` (1 instance)

**Result**: Tests will fail if endpoints return 500. This is correct behavior.

### Phase 2: High - Convert "Not Implemented" to xfail (59 instances)

**Action**: Replace `pytest.skip("endpoint not implemented")` with:

```python
@pytest.mark.xfail(
    reason="Endpoint not implemented - tracking issue #XXX",
    raises=AssertionError,
    strict=False,
)
```

**Or delete the test** if:
- The endpoint is not planned
- The test was speculative/wishful

### Phase 3: High - Fix "Config Creation Unavailable" (17 instances)

**Action**: Investigate root cause. Options:
1. Fix infrastructure so config creation works
2. Mark as xfail with issue
3. Remove tests if functionality is deprecated

### Phase 4: Medium - Rate Limit Skips (4 instances)

**Action**: These may be legitimate (preprod has different limits). Convert to:

```python
@pytest.mark.skipif(
    os.getenv("CI") == "true",
    reason="Rate limits differ in CI vs preprod"
)
```

### Phase 5: Low - Environment Constraint Skips (~20 instances)

**Action**: These are mostly legitimate. Verify each uses `SkipInfo` pattern from conftest.py.

### Phase 6: Prevention - Add Pre-commit Hook

Create validation that:
1. Blocks `status_code == 500.*pytest.skip` patterns
2. Requires xfail to have issue URL
3. Enforces skip rate threshold

## Out of Scope

- Unit test skip patterns (different concern)
- Integration test skip patterns (different concern)
- Refactoring test structure

## Technical Approach

### Skip Classification Script

```python
# scripts/audit-e2e-skips.py
"""Audit E2E test skips and classify them."""

import ast
import re
from pathlib import Path
from dataclasses import dataclass
from enum import Enum

class SkipCategory(Enum):
    ERROR_500_MASKING = "500_masking"  # CRITICAL
    NOT_IMPLEMENTED = "not_implemented"  # HIGH
    CONFIG_UNAVAILABLE = "config_unavailable"  # HIGH
    RATE_LIMIT = "rate_limit"  # MEDIUM
    ENVIRONMENT = "environment"  # LOW
    SYNTHETIC = "synthetic"  # MEDIUM
    OTHER = "other"  # VARIES

@dataclass
class SkipAuditEntry:
    file: str
    line: int
    category: SkipCategory
    message: str
    context: str  # surrounding code
```

### TestMetrics Skip Rate Enforcement

```python
# In tests/e2e/conftest.py
def pytest_sessionfinish(session, exitstatus):
    """Enforce skip rate threshold."""
    metrics = TestMetrics()
    if metrics.skip_rate > 0.15:
        print(f"ERROR: Skip rate {metrics.skip_rate:.1%} exceeds 15% threshold")
        session.exitstatus = 1
```

## Dependencies

- None (self-contained cleanup)

## Risks

| Risk | Mitigation |
|------|------------|
| Tests fail after removing 500 masking | Expected - exposes real issues |
| Skip rate threshold too aggressive | Start at 15%, adjust based on data |
| Some skips are legitimate | Classify before removing |

## Timeline

This spec does not include timeline estimates per project guidelines.

## References

- `tests/e2e/conftest.py` - TestMetrics class
- `tests/conftest.py` - SkipInfo pattern
- Forensic analysis from 091 dry-run showing this as Dec 10 stale work
