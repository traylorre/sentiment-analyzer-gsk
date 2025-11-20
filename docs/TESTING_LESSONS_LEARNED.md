# Testing & Logging Lessons Learned

> **Purpose**: Document critical mistakes made in test infrastructure and logging design. These lessons prevented proper separation of concerns and polluted production code with test-awareness logic.

## Executive Summary

A fundamental error was made: **production code was modified to suppress logs during testing**, violating Separation of Concerns. This approach polluted production code with test-awareness (`"pytest" in sys.modules`) and created a maintenance burden.

**Key Lesson**: Test infrastructure should handle test-specific concerns. Production code should never know it's being tested.

---

## Lesson #1: Don't Pollute Production Code with Test-Awareness

### The Anti-Pattern (What We Did Wrong)

Created `log_expected_warning()` utility that checked if pytest was running:

```python
# src/lib/logging_utils.py - WRONG APPROACH
def log_expected_warning(logger: logging.Logger, message: str) -> None:
    """Suppress warnings in tests."""
    if "pytest" in sys.modules:  # <-- Production code knows about tests!
        logger.debug(message)
    else:
        logger.warning(message)
```

Then modified 10+ production files:

```python
# Production code - WRONG
from src.lib.logging_utils import log_expected_warning

def some_function():
    if condition:
        log_expected_warning(logger, "Retry attempt")  # <-- Test-aware logging
```

### Why This Is Wrong

1. **Violates Separation of Concerns**: Production code shouldn't know about test infrastructure
2. **Creates maintenance burden**: Every log call requires choosing `logger.warning()` vs `log_expected_warning()`
3. **Hides legitimate issues**: What if that warning indicates a real problem in production?
4. **Defeats the purpose of tests**: Tests verify behavior; suppressing logs hides behavior

### The Correct Approach

**Production code logs normally. Test infrastructure controls output.**

```python
# Production code - CORRECT
def some_function():
    if condition:
        logger.warning("Retry attempt")  # Just log it
```

```python
# conftest.py - Test infrastructure handles it
@pytest.fixture
def expect_warning():
    """Fixture for tests that expect specific warnings."""
    # See implementation below
```

---

## Lesson #2: Expected Logs Must Be Asserted

### The Problem

Tests that trigger error paths produce ERROR logs, polluting CI output:

```
2025-11-20 05:58:27 [ERROR] src.lambdas.ingestion.handler: Adapter error for tag climate
2025-11-20 05:58:29 [ERROR] src.lambdas.analysis.handler: Model load error: Model not found
```

These aren't failures - they're **expected errors being tested**. But they look like failures.

### The Wrong Solution

Suppress all ERROR logs below CRITICAL:

```ini
# pytest.ini - WRONG
[pytest]
log_cli_level = CRITICAL  # Hides all errors
```

**Problem**: This also hides **unexpected** errors that indicate real bugs.

### The Correct Solution

**Expected logs must be explicitly asserted as part of the test contract.**

```python
# Test for error-handling path
@pytest.mark.expect_errors("Model load error")
def test_handler_model_load_error(self, caplog):
    with patch('load_model', side_effect=ModelLoadError("Model not found")):
        result = handler(event, context)

    assert result["statusCode"] == 500
    assert "Model load error" in caplog.text  # Assert expected log
```

**Benefits**:
- Tests document what logs they expect
- Unexpected logs cause test failure
- CI output is clean (only unexpected errors shown)

---

## Lesson #3: Industry Standard Practices

Research into Django, Requests, and SQLAlchemy revealed:

### Django Approach

Uses `assertLogs` context manager - tests explicitly capture and assert on expected logs:

```python
def test_validation_error_logged(self):
    with self.assertLogs('myapp.views', level='WARNING') as logs:
        validate_bad_input()

    self.assertIn('Invalid input', logs.output[0])
```

### Requests Approach

**Mocks at the boundary** - error paths that would log are never executed because exceptions are raised earlier:

```python
@mock.patch('urllib3.poolmanager.PoolManager')
def test_connection_error(self, mock_pool):
    mock_pool.return_value.urlopen.side_effect = ConnectionError()

    with pytest.raises(requests.ConnectionError):
        requests.get('http://example.com')
    # No logging code is reached - exception propagates up
```

### SQLAlchemy Approach

**Fails tests on unexpected warnings** - treats unexpected log output as a test failure:

```python
@pytest.fixture
def expect_warnings(recwarn):
    """Fail if unexpected warnings occur."""
    yield

    unexpected = [w for w in recwarn if not _is_expected(w)]
    if unexpected:
        pytest.fail(f"Unexpected warnings: {unexpected}")
```

---

## The Correct Pattern: Fixture-Based Log Assertions

### Design Principles

1. **Production code never knows about tests**
2. **Expected logs are explicitly asserted**
3. **Unexpected logs fail the test**
4. **Fixtures handle boilerplate**
5. **Decorators document expectations**

### Implementation

```python
# conftest.py
@pytest.fixture
def expect_logs():
    """Fixture for tests that expect specific log messages."""
    class LogExpectation:
        def __init__(self):
            self.expected = []

        def error(self, pattern: str):
            self.expected.append(('ERROR', pattern))
            return self

        def warning(self, pattern: str):
            self.expected.append(('WARNING', pattern))
            return self

        def verify(self, caplog):
            for level, pattern in self.expected:
                assert any(
                    r.levelname == level and pattern in r.message
                    for r in caplog.records
                ), f"Expected {level} log matching '{pattern}' not found"

    return LogExpectation()

# Usage in tests
def test_model_load_error(self, caplog, expect_logs):
    expect_logs.error("Model load error: Model not found")

    with patch('load_model', side_effect=ModelLoadError("Model not found")):
        result = handler(event, context)

    assert result["statusCode"] == 500
    expect_logs.verify(caplog)
```

### With Markers (Even Cleaner)

```python
# conftest.py - pytest marker implementation
def pytest_configure(config):
    config.addinivalue_line(
        "markers",
        "expect_errors(*patterns): Mark test as expecting ERROR logs matching patterns"
    )

@pytest.fixture(autouse=True)
def validate_expected_logs(request, caplog):
    """Automatically validate expected logs after test."""
    marker = request.node.get_closest_marker("expect_errors")
    expected_errors = marker.args if marker else ()

    yield

    # After test runs, verify expected errors occurred
    if expected_errors:
        for pattern in expected_errors:
            assert any(
                r.levelname == "ERROR" and pattern in r.message
                for r in caplog.records
            ), f"Expected ERROR log matching '{pattern}' not found"

# Usage - no boilerplate in test!
@pytest.mark.expect_errors("Model load error")
def test_handler_model_load_error(self):
    with patch('load_model', side_effect=ModelLoadError("Model not found")):
        result = handler(event, context)

    assert result["statusCode"] == 500
    # Log assertion happens automatically via fixture
```

---

## Refactoring Checklist

When removing test-awareness from production code:

- [ ] Remove `src/lib/logging_utils.py` entirely
- [ ] Revert all `log_expected_warning()` calls to `logger.warning()`
- [ ] Revert all `log_expected_error()` calls to `logger.error()`
- [ ] Remove `_is_running_in_pytest()` checks from production code
- [ ] Add pytest markers: `@pytest.mark.expect_errors`, `@pytest.mark.expect_warnings`
- [ ] Add `conftest.py` fixture to auto-validate expected logs
- [ ] Update tests to declare expected logs via markers
- [ ] Run full test suite - any test with unexpected logs should fail
- [ ] Fix tests that have unexpected logs (either assert on them or fix the code)

---

## Key Takeaways

1. **Separation of Concerns is sacred** - Test concerns belong in test infrastructure
2. **Expected behavior must be asserted** - Including log output
3. **Clean CI output requires explicit expectations** - Not blanket suppression
4. **Follow industry patterns** - Django, Requests, SQLAlchemy all do this correctly
5. **Markers > Manual assertions** - Less boilerplate, clearer intent

---

**Last Updated**: 2025-11-19
**Author**: @traylorre
**Status**: Lesson learned - proper implementation in progress
