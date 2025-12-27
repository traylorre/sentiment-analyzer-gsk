# Feature 1067: Window Export Validation Tests

## Problem Statement

The vanilla JavaScript dashboard files (`src/dashboard/*.js`) have NO automated tests despite being critical for chart initialization and user interaction. This test coverage gap allowed Feature 1066's regression (missing window exports) to slip through to production.

### Background

- Backend API tests exist (`tests/unit/dashboard/test_ohlc.py` - 200+ lines)
- React frontend tests exist (`frontend/src/components/charts/*.test.tsx`)
- **Gap**: NO tests for `src/dashboard/*.js` vanilla JS files
- Silent failures from `typeof X === 'function'` guards hide missing exports

### Impact

Without window export validation tests:
- Missing exports are not detected until manual testing
- Silent failures in `app.js` go unnoticed
- Regressions like Feature 1066 reach production

## Requirements

### R01: Static Window Export Verification

Create tests that verify all required window exports exist in each dashboard JS file by parsing the source code.

**Files to validate:**
- `src/dashboard/ohlc.js` - OHLC chart functions
- `src/dashboard/timeseries.js` - Timeseries chart functions
- `src/dashboard/unified-resolution.js` - Resolution selector functions
- `src/dashboard/app.js` - App initialization functions

### R02: Export Registry Definition

Define an explicit registry of required window exports per file. This makes the contract explicit and prevents accidental removal.

**Expected exports:**
```
ohlc.js:
  - initOHLCChart
  - updateOHLCTicker
  - setOHLCResolution
  - hideOHLCResolutionSelector
  - loadOHLCSentimentOverlay

timeseries.js:
  - initTimeseriesChart
  - updateTimeseriesTicker
  - setTimeseriesResolution (if exists)

unified-resolution.js:
  - initUnifiedResolutionSelector
  - setResolution

app.js:
  - initDashboard (if exists)
```

### R03: Fast Feedback

Tests must run as part of the standard `pytest` test suite without requiring a browser. Use static analysis (regex parsing) of JavaScript source files.

### R04: Clear Error Messages

When an export is missing, the test failure message must clearly identify:
- Which file is missing the export
- Which function is not exported
- The expected export pattern

## Test Requirements

### T01: Test detects missing export

Given ohlc.js WITHOUT `window.initOHLCChart = initOHLCChart`, the test MUST fail with a clear message.

### T02: Test passes with all exports

Given ohlc.js WITH all 5 required exports, the test MUST pass.

### T03: Test catches partial exports

If a file has some but not all required exports, the test MUST identify which specific exports are missing.

## Implementation Notes

- Use Python regex to parse JS files for `window.X = X` patterns
- Test file location: `tests/unit/dashboard/test_window_exports.py`
- No browser/Playwright required for static validation
- Run with standard pytest markers

## Definition of Done

- [ ] All dashboard JS files have explicit export registries
- [ ] Tests verify all exports exist via static analysis
- [ ] Tests run as part of `pytest tests/unit/dashboard/`
- [ ] Clear error messages identify missing exports
- [ ] Tests would have caught Feature 1066 regression

## Related Features

- Feature 1066: Fix Missing Window Exports (the bug this prevents)
- Feature 1064: Unified Resolution Selector
- Feature 1065: Sentiment-Price Overlay
