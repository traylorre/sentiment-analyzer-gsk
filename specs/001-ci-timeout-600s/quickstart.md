# Quickstart: Increase Playwright CI Timeout to 600s

**Feature**: 001-ci-timeout-600s
**Date**: 2026-03-29

## Overview

Suite-level Playwright timeout increased from 300s to 600s. Configurable via environment variable with a 1800s max ceiling.

## What Changed

| File | Change |
|------|--------|
| `src/playwright/executor.py` | Default timeout 300 -> 600, added `MAX_SUITE_TIMEOUT = 1800` clamping |
| `src/playwright/runner.py` | Reads `PLAYWRIGHT_SUITE_TIMEOUT` env var instead of hardcoding 300 |
| `specs/029-playwright-e2e-implementation/contracts/playwright-api.yaml` | Updated default and documented max ceiling |

## Verification

### 1. Confirm default changed

```bash
grep -n "timeout=600" src/playwright/executor.py
# Expected: line 119 shows timeout=600 in run_suite signature

grep -n "MAX_SUITE_TIMEOUT" src/playwright/executor.py
# Expected: MAX_SUITE_TIMEOUT = 1800
```

### 2. Confirm runner uses env var

```bash
grep -n "PLAYWRIGHT_SUITE_TIMEOUT" src/playwright/runner.py
# Expected: os.environ.get("PLAYWRIGHT_SUITE_TIMEOUT", "600")
```

### 3. Run unit tests

```bash
make test-local
# All timeout clamping tests should pass
```

### 4. Test env var override

```bash
# Override timeout to 900s (within ceiling)
PLAYWRIGHT_SUITE_TIMEOUT=900 python -m src.playwright.runner --dry-run
# Should use 900s timeout

# Override above ceiling (should clamp to 1800)
PLAYWRIGHT_SUITE_TIMEOUT=9999 python -m src.playwright.runner --dry-run
# Should clamp to 1800s timeout
```

### 5. Verify contract docs updated

```bash
grep -A2 "timeout" specs/029-playwright-e2e-implementation/contracts/playwright-api.yaml
# Expected: default 600, maximum 1800
```

## Troubleshooting

### Suite still timing out at 300s?

1. Check runner.py is not still hardcoding 300: `grep "timeout=300" src/playwright/runner.py`
2. Check env var is not overriding to 300: `echo $PLAYWRIGHT_SUITE_TIMEOUT`
3. Verify executor.py default updated: `grep "def run_suite" src/playwright/executor.py`

### Timeout not being clamped?

1. Verify `MAX_SUITE_TIMEOUT` constant exists in executor.py
2. Verify `min(timeout, MAX_SUITE_TIMEOUT)` is applied before subprocess call
3. Run clamping unit tests: `pytest tests/unit -k "timeout_clamp" -v`
