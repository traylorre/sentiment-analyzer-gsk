# Test Log Assertions - TODO Tracker

**Purpose**: Track which tests need explicit caplog assertions added.

**Goal**: Zero unexpected ERROR logs in test output. Every ERROR log must be explicitly asserted.

---

## Unique Error Messages (21 total)

### Analysis Handler (6)
- [ ] `Inference error: CUDA error`
- [ ] `Invalid SNS message format: missing 'timestamp'`
- [ ] `Model load error: Model not found`
- [ ] `Failed to load model: Model files missing`
- [ ] `Failed to load model: Model not found`
- [ ] `Inference failed: CUDA error`

### Ingestion Handler (6)
- [ ] `Circuit breaker opened - too many consecutive failures`
- [ ] `NewsAPI authentication failed`
- [ ] `Authentication error: Invalid NewsAPI key`
- [ ] `Authentication failed for NewsAPI`
- [ ] `Configuration error: WATCH_TAGS environment variable is not set`
- [ ] `Unexpected error: Secret not found`

### Shared Errors (6)
- [ ] `Database operation failed: put_item`
- [ ] `Database operation failed: query`
- [ ] `Failed to retrieve configuration`
- [ ] `Internal error details: {'stack_trace': 'sensitive info'}`
- [ ] `Model loading failed`
- [ ] `Sentiment analysis failed`

### Secrets (2)
- [ ] `Failed to parse secret as JSON`
- [ ] `Secret not found`

### Metrics (1)
- [ ] `Failed to emit metric: An error occurred (InvalidClientTokenId)`

---

## Test Files to Update

Based on error messages, these test files need updates:

### Priority 1: Core Handler Tests
- [ ] `tests/unit/test_analysis_handler.py` - 4+ error paths
- [ ] `tests/unit/test_ingestion_handler.py` - 6+ error paths
- [ ] `tests/unit/test_sentiment.py` - 3+ error paths

### Priority 2: Adapter Tests
- [ ] `tests/unit/test_newsapi_adapter.py` - Circuit breaker, auth failures

### Priority 3: Shared Module Tests
- [ ] `tests/unit/test_errors.py` - All error helper functions
- [ ] `tests/unit/test_secrets.py` - Secret failure paths
- [ ] `tests/unit/test_metrics.py` - Metric emission failures

### Priority 4: Integration Tests
- [ ] `tests/integration/test_*.py` - Any error path tests

---

## Pattern to Apply

### Before (Current - Logs Without Assertion)
```python
def test_model_load_error(self):
    with patch('load_model', side_effect=ModelLoadError("Model not found")):
        result = handler(event, context)

    assert result["statusCode"] == 500
    # ERROR log appears in output but isn't validated!
```

### After (Correct - Explicit Assertion)
```python
def test_model_load_error(self, caplog):
    with patch('load_model', side_effect=ModelLoadError("Model not found")):
        result = handler(event, context)

    assert result["statusCode"] == 500
    # Explicitly assert expected error was logged
    assert_error_logged(caplog, "Model load error")
```

---

## Helper Functions Available

In `tests/conftest.py`:

```python
def assert_error_logged(caplog, pattern: str):
    """Assert an ERROR log was captured matching pattern."""

def assert_warning_logged(caplog, pattern: str):
    """Assert a WARNING log was captured matching pattern."""
```

---

## Progress Tracking

**Total Tests**: ~400
**Tests Needing Updates**: ~20-30 (estimated)
**Unique Error Patterns**: 21
**Time Estimate**: 2-3 hours

---

## Next Session Plan

1. Start with `test_analysis_handler.py` (Priority 1)
2. Add `caplog` parameter to each test that expects errors
3. Add `assert_error_logged(caplog, "pattern")` after assertions
4. Run tests to verify clean output
5. Move to next file systematically

---

**Status**: PARTIALLY COMPLETE (086-test-debt-burndown)
**Branch**: `086-test-debt-burndown`

### Implementation (2025-12-11)

- **Pre-commit hook** added: `scripts/check-error-log-assertions.sh`
- **Existing assertions**: 28 `assert_error_logged()` calls across 4 test files
- **Coverage**: 9 of 21 documented patterns have explicit assertions
- **Advisory mode**: Hook warns but doesn't block (can be made blocking later)

### Files with Log Assertions

- `tests/unit/test_analysis_handler.py`: 3 assertions
- `tests/unit/test_errors.py`: 2 assertions
- `tests/unit/test_secrets.py`: 2 assertions
- `tests/unit/test_sentiment.py`: 2 assertions

### Remaining Work (Future Sprint)

The remaining 12 patterns can be added incrementally. The pre-commit hook will
alert developers to unasserted ERROR logs, creating awareness and gradual
improvement.
