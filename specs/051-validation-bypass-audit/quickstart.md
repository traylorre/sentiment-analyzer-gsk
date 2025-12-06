# Quickstart: Validation Bypass Audit

**Date**: 2025-12-06
**Feature**: 051-validation-bypass-audit

## Overview

Fix validation bypasses so `git push` succeeds without `SKIP=` environment variables.

## Target Files

| File | Action | Description |
|------|--------|-------------|
| `src/lambdas/dashboard/chaos.py` | MODIFY | Replace 9 datetime.utcnow() calls |
| `src/lambdas/shared/adapters/tiingo.py` | MODIFY | Replace 2 datetime.utcnow() calls |
| `src/lambdas/shared/adapters/finnhub.py` | MODIFY | Replace 3 datetime.utcnow() calls |
| `src/lambdas/shared/cache/ticker_cache.py` | MODIFY | Replace 2 datetime.utcnow() calls |
| `src/lambdas/shared/circuit_breaker.py` | MODIFY | Replace 3 datetime.utcnow() calls |
| `src/lambdas/shared/volatility.py` | MODIFY | Replace 1 datetime.utcnow() call |
| `.pre-commit-config.yaml` | MODIFY | Fix pytest hook configuration |

## Step 1: Fix datetime.utcnow() (26 instances)

### Pattern

```python
# Before
from datetime import datetime
created_at = datetime.utcnow().isoformat() + "Z"

# After
from datetime import datetime, UTC
created_at = datetime.now(UTC).isoformat().replace('+00:00', 'Z')
```

### Files to Update

Run this sed command to preview changes:
```bash
grep -rn "datetime.utcnow" --include="*.py" src/
```

For each file, add `UTC` to imports and replace calls:

**chaos.py** (9 instances):
```python
from datetime import datetime, timedelta, UTC

# Replace all:
datetime.utcnow() → datetime.now(UTC)
```

**tiingo.py** (2 instances):
```python
from datetime import datetime, timedelta, UTC
```

**finnhub.py** (3 instances):
```python
from datetime import datetime, timedelta, UTC
```

**ticker_cache.py** (2 instances):
```python
from datetime import datetime, UTC
```

**circuit_breaker.py** (3 instances):
```python
from datetime import datetime, UTC
```

**volatility.py** (1 instance):
```python
from datetime import datetime, date, UTC
```

## Step 2: Fix Pre-commit pytest Hook

### Current (Broken)

```yaml
- id: pytest
  name: pytest
  entry: python -m pytest tests/ -x --tb=short -q
  language: system
  types: [python]
  pass_filenames: false
  always_run: true
  stages: [push]
```

### Fixed

```yaml
- id: pytest
  name: pytest
  entry: pytest tests/ -x --tb=short -q
  language: python
  additional_dependencies: [pytest, pytest-asyncio, pytest-timeout]
  types: [python]
  pass_filenames: false
  always_run: true
  stages: [push]
```

## Verification Checklist

After implementation, verify:

- [ ] All unit tests pass: `pytest tests/unit/ -v`
- [ ] No deprecation warnings from datetime: `pytest 2>&1 | grep -c "utcnow"`
- [ ] Pre-commit hooks pass: `pre-commit run --all-files`
- [ ] Push succeeds without SKIP: `git push origin 051-validation-bypass-audit`

## Expected Outcome

- 0 datetime.utcnow() deprecation warnings (was 365+)
- `git push` works without `SKIP=pytest`
- All existing tests continue to pass
