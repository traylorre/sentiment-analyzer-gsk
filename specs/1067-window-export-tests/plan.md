# Plan: Feature 1067 - Window Export Validation Tests

## Overview

Add static analysis tests that verify all required window exports exist in vanilla JS dashboard files. Uses regex parsing - no browser required.

## Implementation Steps

### Step 1: Create Window Export Registry

**File**: `tests/unit/dashboard/window_export_registry.py`

Define the expected window exports for each dashboard JS file:

```python
WINDOW_EXPORT_REGISTRY = {
    "src/dashboard/ohlc.js": [
        "initOHLCChart",
        "updateOHLCTicker",
        "setOHLCResolution",
        "hideOHLCResolutionSelector",
        "loadOHLCSentimentOverlay",
    ],
    "src/dashboard/timeseries.js": [
        "initTimeseriesChart",
        "updateTimeseriesTicker",
    ],
    "src/dashboard/unified-resolution.js": [
        "initUnifiedResolutionSelector",
        "setResolution",
    ],
}
```

### Step 2: Create Window Export Validator

**File**: `tests/unit/dashboard/test_window_exports.py`

```python
import re
from pathlib import Path
import pytest
from .window_export_registry import WINDOW_EXPORT_REGISTRY

def find_window_exports(js_content: str) -> set[str]:
    """Parse JS file to find window.X = X export patterns."""
    pattern = r'window\.(\w+)\s*=\s*\1\s*[;,]?'
    return set(re.findall(pattern, js_content))

@pytest.mark.parametrize("js_file,expected_exports", WINDOW_EXPORT_REGISTRY.items())
def test_window_exports_exist(js_file: str, expected_exports: list[str]):
    """Verify all required window exports exist in JS file."""
    repo_root = Path(__file__).parents[3]
    js_path = repo_root / js_file

    assert js_path.exists(), f"JS file not found: {js_file}"

    content = js_path.read_text()
    actual_exports = find_window_exports(content)

    missing = set(expected_exports) - actual_exports
    assert not missing, (
        f"Missing window exports in {js_file}:\n"
        f"  Expected: window.{', window.'.join(sorted(missing))}\n"
        f"  Pattern: window.<name> = <name>;"
    )
```

### Step 3: Verify with Current State

Run tests to confirm they pass with Feature 1066 fix in place.

## Files Changed

| File | Change |
|------|--------|
| `tests/unit/dashboard/window_export_registry.py` | NEW - Export registry |
| `tests/unit/dashboard/test_window_exports.py` | NEW - Validation tests |

## Testing

1. Run: `pytest tests/unit/dashboard/test_window_exports.py -v`
2. Verify all parametrized tests pass
3. Temporarily remove an export to verify test catches it

## Risk Assessment

- **Low risk**: Read-only tests, no production code changes
- **Fast feedback**: Static analysis, no browser needed
- **Regression prevention**: Would have caught Feature 1066

## Definition of Done

- [ ] Window export registry defines all exports
- [ ] Tests pass for all dashboard JS files
- [ ] Tests run in < 1 second (static analysis)
- [ ] Error messages clearly identify missing exports
