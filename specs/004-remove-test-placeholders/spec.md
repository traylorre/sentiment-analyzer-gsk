# 004: Remove Test Placeholders

## Problem Statement

Multiple preprod integration tests contain empty `pass` statements that do nothing, providing false confidence that tests are comprehensive. These placeholders were scaffolded but never implemented:

### Affected Files

**test_e2e_lambda_invocation_preprod.py:**
- Line 373: `test_malformed_json_handled_gracefully` - Empty pass, no actual test
- Line 556: `test_benchmark_cold_start_time` - Empty pass, no actual benchmark

**test_ingestion_preprod.py:**
- Line 328: Exception handler with empty pass
- Line 405: Exception handler with empty pass
- Line 480: Exception handler with empty pass

**test_newsapi_adapter.py:**
- Line 289: Empty pass in exception handler
- Line 334: Empty pass in test body

**test_metrics.py:**
- Line 307: Empty pass in exception handler

## Goal

Remove all empty `pass` placeholders from test files. Either implement the test or delete it entirely.

## Requirements

### Functional Requirements

1. **FR-001:** No `pass` statements in test methods (except `__init__.py`)
2. **FR-002:** Exception handlers must either re-raise, log, or assert
3. **FR-003:** Placeholder tests must be implemented or removed
4. **FR-004:** Each test must have at least one assertion

### Non-Functional Requirements

1. **NFR-001:** No reduction in actual test coverage
2. **NFR-002:** Clear error messages when tests fail
3. **NFR-003:** Tests must be deterministic

## Technical Approach

### For Empty Test Methods

**Option A: Implement the test**
```python
# BEFORE
def test_malformed_json_handled_gracefully(self):
    """E2E: Malformed requests are handled gracefully."""
    pass

# AFTER
def test_malformed_json_handled_gracefully(self, auth_headers):
    """E2E: Malformed requests are handled gracefully."""
    response = requests.post(
        f"{DASHBOARD_URL}/api/analyze",
        headers=auth_headers,
        data="not valid json",
        timeout=REQUEST_TIMEOUT,
    )
    assert response.status_code in [400, 422], (
        f"Expected 400/422 for malformed JSON, got {response.status_code}"
    )
```

**Option B: Delete with explanation**
```python
# DELETE the test entirely and add to TEST-DEBT.md if needed
```

### For Empty Exception Handlers

**Option A: Re-raise the exception**
```python
# BEFORE
except Exception:
    pass

# AFTER
except Exception as e:
    pytest.fail(f"Unexpected exception: {e}")
```

**Option B: Explicit assertion on exception**
```python
# AFTER
except SpecificException as e:
    assert "expected message" in str(e)
except Exception as e:
    pytest.fail(f"Wrong exception type: {type(e).__name__}: {e}")
```

### Specific Fixes

#### test_e2e_lambda_invocation_preprod.py:373
```python
def test_malformed_json_handled_gracefully(self, auth_headers):
    """E2E: POST endpoints handle malformed JSON gracefully."""
    # Skip if no POST endpoints exist
    # Otherwise test with invalid JSON body
    response = requests.post(
        f"{DASHBOARD_URL}/api/chaos/experiments",
        headers={**auth_headers, "Content-Type": "application/json"},
        data="{{invalid json",
        timeout=REQUEST_TIMEOUT,
    )
    assert response.status_code == 422, (
        f"Expected 422 Unprocessable Entity, got {response.status_code}"
    )
```

#### test_e2e_lambda_invocation_preprod.py:556
```python
def test_benchmark_cold_start_time(self):
    """BENCHMARK: Measure cold start time by forcing new Lambda instance."""
    # Force cold start by updating function config
    # This test is complex - defer to spec 003 warmup implementation
    pytest.skip("Cold start benchmark requires Lambda config update - implement in spec 003")
```

#### test_ingestion_preprod.py exception handlers
```python
# Replace all:
except Exception:
    pass

# With:
except requests.Timeout:
    pytest.fail("Request timed out - Lambda may be throttled")
except requests.ConnectionError as e:
    pytest.fail(f"Connection failed: {e}")
except Exception as e:
    pytest.fail(f"Unexpected error: {type(e).__name__}: {e}")
```

## Files to Modify

1. `tests/integration/test_e2e_lambda_invocation_preprod.py`
2. `tests/integration/test_ingestion_preprod.py`
3. `tests/unit/test_newsapi_adapter.py`
4. `tests/unit/test_metrics.py`

## Test Debt Resolution

This spec resolves:
- **TD-002:** E2E Lambda Tests Have Empty Placeholders
- **TD-003:** Ingestion Preprod Tests Have Empty Exception Handlers

## Acceptance Criteria

1. [ ] Zero `pass` statements in test methods (grep confirms)
2. [ ] All exception handlers either re-raise, assert, or call pytest.fail
3. [ ] No reduction in test count (tests replaced, not deleted)
4. [ ] All tests have at least one assertion
5. [ ] CI passes after changes

## Verification Script

```bash
# Should return 0 matches (excluding __init__.py)
grep -r "^\s*pass$" tests/ --include="*.py" | grep -v "__init__"
```

## Risks

- **Risk:** Implementing placeholder tests may reveal real bugs
- **Mitigation:** Run tests locally first, fix issues before merging
