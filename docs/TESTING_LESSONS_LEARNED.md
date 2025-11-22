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

## Lesson #4: Don't Unit Test Infinite Streams (SSE/WebSockets)

**Date**: 2025-11-22
**Context**: Dashboard SSE endpoint testing for first production deployment

### The Anti-Pattern (What We Tried)

Attempted to test Server-Sent Events (SSE) streaming endpoint using FastAPI's synchronous `TestClient`:

```python
# ❌ THIS HANGS INDEFINITELY
@mock_aws
def test_sse_stream_sends_metrics_events(self, client, auth_headers):
    with client.stream("GET", "/api/stream", headers=auth_headers) as response:
        for line in response.iter_lines():
            if line.startswith("data:"):
                events.append(line)
                if len(events) >= 1:
                    break  # Even with break, stream never stops
```

**Problem**: SSE endpoints have infinite `while True` loops. Synchronous test clients block waiting for streams to end (which never happens).

### Why This Happens

FastAPI SSE handler:
```python
async def event_generator():
    while True:  # ← Infinite loop by design
        yield {"data": json.dumps(metrics)}
        await asyncio.sleep(10)
```

FastAPI's `TestClient` is synchronous (wraps async with `anyio`) and can't gracefully disconnect from infinite async generators.

### The Correct Approach

**For Unit Tests**: Test authentication and business logic separately

```python
# ✅ WORKS - Test auth, not streaming behavior
def test_sse_requires_auth(self, client):
    response = client.get("/api/stream")
    assert response.status_code == 401

# ✅ WORKS - Test business logic separately
@mock_aws
def test_metrics_aggregation_correct(self):
    from src.lambdas.dashboard.metrics import aggregate_dashboard_metrics

    # Test the pure function, not the endpoint
    metrics = aggregate_dashboard_metrics(table, hours=24)
    assert metrics["total"] == 3
```

**For Integration Tests**: Use async client with timeout OR manual validation

```python
# ✅ Option 1: Async client (complex but complete)
import httpx
import asyncio

@pytest.mark.asyncio
async def test_sse_full_streaming():
    async with httpx.AsyncClient() as client:
        async with client.stream("GET", url, headers=headers, timeout=5.0) as response:
            async for line in response.aiter_lines():
                if line.startswith("data:"):
                    # Verify first event, then break
                    break

# ✅ Option 2: Manual validation in preprod/prod (simpler)
def test_sse_stream_endpoint_exists(self, client, auth_headers):
    # Just verify endpoint exists and requires auth
    response_no_auth = client.get("/api/stream")
    assert response_no_auth.status_code == 401

    # Note: Full SSE behavior tested manually or in E2E tests
```

### Key Takeaway

**Don't unit test infinite streams.** Test the testable parts:
1. ✅ Authentication/authorization (unit test)
2. ✅ Business logic (test pure functions separately)
3. ✅ Response headers if needed (unit test with timeout)
4. ⏸️ Full streaming behavior (integration/E2E or manual validation)

---

## Lesson #5: Test What Matters, Not What's Easy

**Date**: 2025-11-22
**Context**: Deciding what dashboard tests to implement vs defer

### The Trap

It's tempting to achieve "100% test coverage" by forcing difficult-to-test code into unit tests. This wastes time and creates brittle tests.

Example: Spent 30+ minutes trying to make SSE streaming work in unit tests with:
- `signal.alarm()` timeouts
- Thread pool executors
- Asyncio event loops
- All failed or were flaky

### Better Approach

**Ask**: "What failure mode does this test prevent?"

For SSE streaming:
- ❌ "Does the stream send events every 10 seconds?" → Hard to unit test, low added value
- ✅ "Does the endpoint require authentication?" → Easy to unit test, prevents unauthorized access
- ✅ "Do metrics aggregate correctly?" → Easy to unit test (separate function), core business logic
- ✅ "Does the stream work in preprod?" → Easy to validate manually, high confidence for prod

### Decision Matrix

| Risk | Easy to Test | Action |
|------|--------------|--------|
| **High** | **Yes** | ✅ Unit test NOW |
| **High** | **No** | 📋 Integration test OR manual validation |
| **Low** | **Yes** | ⏸️ Unit test if time allows |
| **Low** | **No** | ⏸️ Skip or document as "tested manually" |

### Key Takeaway

**Prioritize tests by risk and ease of testing, not by coverage percentage.**

Time spent debugging flaky SSE test: 30 minutes
Time spent simplifying test + documenting in backlog: 5 minutes
Value delivered: Same (endpoint still validated, just differently)

**Perfect is the enemy of shipped.**

---

## Lesson #6: Create Test Backlogs for Non-Urgent Tests

**Date**: 2025-11-22
**Context**: Dashboard has good functional coverage but missing NFR tests

### The Dilemma

While adding dashboard tests, identified many **important but non-urgent** test scenarios:
- Performance (cold start time, P95 latency)
- Load testing (concurrent requests, large datasets)
- Security (timing attacks, input validation)
- Chaos engineering (fault injection, resource exhaustion)

**Option A**: Try to implement everything before production
- ❌ Delays production deployment for weeks
- ❌ Perfect becomes enemy of good

**Option B**: Skip these tests entirely
- ❌ No plan to add them later
- ❌ They never get done ("out of sight, out of mind")

### The Solution: Test Backlog Document

Created `docs/DASHBOARD_TESTING_BACKLOG.md` with:
- **6 categories** of tests (performance, resilience, load, security, operational, chaos)
- **4-phase implementation plan** (pre-prod, week 1, month 1, continuous)
- **Specific test scenarios** with code examples
- **Tools identified** (pytest-benchmark, locust, AWS FIS)
- **Success metrics** for each phase

### Benefits

1. ✅ **Ship faster** - Implement only critical tests (Phase 1)
2. ✅ **Stay organized** - Know exactly what's missing
3. ✅ **Build confidence** - Clear plan to improve over time
4. ✅ **Enable delegation** - Others can pick up backlog items

### Template Structure

```markdown
# [Component] Testing Backlog

## Executive Summary
Current state: X/10, Goal: Y/10, Key gaps: [list]

## Test Categories
### 1. Category Name
**Priority**: HIGH/MEDIUM/LOW
**Rationale**: Why this matters
**Tests to Add**: - [ ] Scenario 1

## Implementation Phases
- Phase 1: Pre-Production (blockers)
- Phase 2: Post-Production Week 1 (high priority)
- Phase 3: Post-Production Month 1 (medium priority)
- Phase 4: Continuous (ongoing)

## Success Metrics
Coverage, performance, reliability targets
```

### Key Takeaway

**Always create a test backlog when you can't implement all tests immediately.**

This prevents the trap of:
- ❌ Delaying production for perfection
- ❌ Forgetting what needs testing
- ❌ Losing momentum post-production

---

## Lesson #7: Document What You Can't Test (Yet)

**Date**: 2025-11-22
**Context**: DynamoDB throttling and chaos scenarios

### What Happened

Identified critical test scenarios that are **impractical to implement now**:
- DynamoDB throttling behavior (`moto` doesn't simulate)
- Network partition handling (requires chaos tools)
- Lambda cold start time in production (needs real Lambda environment)

### The Temptation

**Don't**: Ignore them (they'll never get tested)
**Don't**: Spend weeks building test infrastructure now (delays production)

### The Solution

**Document in test backlog with explanation**:

```markdown
#### 2.1 DynamoDB Failures
**Priority**: HIGH
**Tests to Add**:
- [ ] **DynamoDB throttling** (ProvisionedThroughputExceededException)
  - Expected: 503 with retry-after header
  - **Note**: moto doesn't simulate throttling - requires chaos testing

**Implementation**:
```python
@pytest.mark.resilience
def test_dynamodb_throttling_graceful_degradation(self):
    # moto doesn't simulate throttling well
    # In production, use chaos testing (see TC-003)
    pass  # Implement with AWS Fault Injection Simulator post-prod
```
```

### Benefits

1. ✅ Acknowledged the gap (not ignored)
2. ✅ Explained why it's hard (tool limitations)
3. ✅ Proposed solution (chaos testing post-prod)
4. ✅ Linked to tech debt (TC-003)

### Key Takeaway

**If you can't test something now, document:**
1. What needs testing
2. Why it's difficult (tool limitations, complexity, etc.)
3. When/how you'll test it (post-prod, chaos tools, etc.)
4. Where it's tracked (backlog, tech debt registry)

This maintains test coverage awareness and prevents "out of sight, out of mind."

---

## Lesson #8: moto Has Limits - Know When to Stop Mocking

**Date**: 2025-11-22
**Context**: Attempting to test AWS failure scenarios

### What moto Can Do ✅

- ✅ Standard CRUD operations (GetItem, PutItem, Query, Scan)
- ✅ Table not found (use wrong table name)
- ✅ Empty result sets (don't seed data)
- ✅ Large datasets (seed with 10K+ items)

### What moto Cannot Do ❌

- ❌ Throttling (ProvisionedThroughputExceededException)
- ❌ Network timeouts
- ❌ Eventual consistency delays
- ❌ Partition key hot spots
- ❌ GSI performance characteristics

### Decision Matrix

| Scenario | Unit Test (moto) | Integration Test | Chaos Test |
|----------|------------------|------------------|------------|
| Table not found | ✅ `monkeypatch` | ✅ Delete table | N/A |
| Empty table | ✅ Don't seed | ✅ Real empty table | N/A |
| Throttling | ❌ Can't mock | ⚠️ Hard to reproduce | ✅ AWS FIS |
| Network timeout | ❌ Can't mock | ⚠️ Hard to reproduce | ✅ Chaos Mesh |
| Large results | ✅ Seed 10K items | ✅ Real data | N/A |

### Key Takeaway

**For error scenarios moto can't simulate:**
1. ✅ Document in test backlog
2. ✅ Plan chaos testing post-production
3. ✅ Test error handling code paths separately (mock the boto3 exception directly)

Example:
```python
# ✅ Test exception handling without moto
def test_handles_throttling_exception():
    with patch('boto3.resource') as mock_boto:
        mock_table = mock_boto.return_value.Table.return_value
        mock_table.query.side_effect = ClientError(
            {'Error': {'Code': 'ProvisionedThroughputExceededException'}},
            'Query'
        )

        # Test your error handling code
        result = get_metrics(table_name="test")
        assert result["statusCode"] == 503
```

---

## Lesson #9: Static File Packaging is Easy to Forget

**Date**: 2025-11-22
**Context**: Lambda dependency bundling (PR #50)

### The Risk

When bundling Lambda dependencies, it's easy to remember Python packages but forget static files:
- ✅ Python code (handlers, modules)
- ✅ Python dependencies (pip packages)
- ❌ Static assets (HTML, CSS, JS, images) ← FORGOTTEN

If static files aren't copied, API works but web UI returns 404.

### The Solution

**Add explicit test for file existence**:

```python
class TestStaticFilePackaging:
    def test_static_files_exist_in_package(self):
        """Test that static HTML/CSS/JS files are bundled."""
        import os
        from src import dashboard

        dashboard_dir = os.path.dirname(dashboard.__file__)

        # Verify files exist
        assert os.path.exists(os.path.join(dashboard_dir, "index.html"))
        assert os.path.exists(os.path.join(dashboard_dir, "static", "styles.css"))
        assert os.path.exists(os.path.join(dashboard_dir, "static", "app.js"))
```

**In CI/CD workflow**:
```bash
# Package Dashboard Lambda
mkdir -p packages/dashboard-build
cp -r packages/deps/* packages/dashboard-build/        # Dependencies
cp -r src/lambdas/dashboard/* packages/dashboard-build/  # Python code
cp -r src/dashboard packages/dashboard-build/src/      # ← Static files!
cd packages/dashboard-build && zip -r ../dashboard.zip .
```

### Key Takeaway

**When packaging Lambdas, enumerate all required files:**
1. Python handlers and modules
2. Python dependencies (pip)
3. Static assets (HTML/CSS/JS)
4. Config files

Add tests that verify file existence to catch packaging issues early.

---

## Quick Reference: Testing Decision Tree

```
Need to test a feature?
│
├─ Is it a critical path (auth, data validation, business logic)?
│  ├─ YES → Unit test (high priority)
│  └─ NO → Continue...
│
├─ Is it easy to test in isolation?
│  ├─ YES → Unit test
│  └─ NO → Continue...
│
├─ Does it require real infrastructure (DynamoDB, S3)?
│  ├─ YES → Integration test
│  └─ NO → Continue...
│
├─ Does it involve async/streaming/long-running operations?
│  ├─ YES → Integration test OR manual validation
│  └─ NO → Continue...
│
├─ Does it involve failure injection (chaos)?
│  ├─ YES → Document in backlog (post-production)
│  └─ NO → Continue...
│
└─ Is it low risk or already covered indirectly?
   └─ YES → Skip or document as "tested manually"
```

---

## Summary: Key Testing Principles

From lessons 1-9:

1. **Separation of Concerns** - Production code should never know it's being tested
2. **Expected Behavior Must Be Asserted** - Including logs and errors
3. **Follow Industry Patterns** - Learn from Django, Requests, SQLAlchemy
4. **Don't Unit Test Infinite Streams** - Test auth/logic separately, defer streaming to integration
5. **Test What Matters** - Prioritize by risk and ease, not coverage percentage
6. **Create Test Backlogs** - Document non-urgent tests for future implementation
7. **Document Limitations** - Explain why certain tests are deferred
8. **Know Your Tools' Limits** - moto can't simulate all AWS failures
9. **Verify Static Files** - Don't forget non-code assets in Lambda packages

---

**Last Updated**: 2025-11-22
**Authors**: @traylorre, Claude Code
**Status**: Active - update after each major testing effort
