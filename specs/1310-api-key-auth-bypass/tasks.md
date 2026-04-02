# Feature 1310: Tasks

## Task Overview

| ID | Task | File | Depends On | Status |
|----|------|------|------------|--------|
| T1 | Update module docstring | alert_evaluator.py | -- | TODO |
| T2 | Remove INTERNAL_API_KEY variable | alert_evaluator.py | -- | TODO |
| T3 | Simplify verify_internal_auth | alert_evaluator.py | T2 | TODO |
| T4 | Rewrite TestVerifyInternalAuth | test_alert_evaluator.py | T2, T3 | TODO |
| T5 | Run tests and verify | -- | T1-T4 | TODO |

## Tasks

### T1: Update Module Docstring

**File**: `src/lambdas/notification/alert_evaluator.py`
**Line**: 14
**Traces**: AR1-FINDING-02

Change line 14 from:
```
    - Internal endpoints require X-Internal-Auth header
```
To:
```
    - Internal endpoints are restricted to dev/test environments
```

### T2: Remove INTERNAL_API_KEY Variable

**File**: `src/lambdas/notification/alert_evaluator.py`
**Line**: 38
**Traces**: FR-001, AC1

Remove the line:
```python
INTERNAL_API_KEY = os.environ.get("INTERNAL_API_KEY", "")
```

Clean up resulting double blank line (AR2-FINDING-04). After removal, lines 36-39 should be:
```python
# Environment variables
DYNAMODB_TABLE = os.environ["DATABASE_TABLE"]


```
(One blank line between DYNAMODB_TABLE and the next section, matching existing style.)

### T3: Simplify verify_internal_auth

**File**: `src/lambdas/notification/alert_evaluator.py`
**Lines**: 288-301 (line numbers will shift by -1 after T2)
**Traces**: FR-002, AC2, AC3, AC4

Replace the entire function body with:
```python
def verify_internal_auth(auth_header: str | None) -> bool:
    """Verify internal API authentication.

    Internal endpoints are only accessible in dev/test environments.
    Production internal calls use IAM-authenticated Lambda invocations,
    not HTTP API keys.

    Args:
        auth_header: X-Internal-Auth header value (unused, kept for
            interface stability)

    Returns:
        True if environment allows internal access, False otherwise
    """
    return os.environ["ENVIRONMENT"] in ("dev", "test")
```

### T4: Rewrite TestVerifyInternalAuth

**File**: `tests/unit/notification/test_alert_evaluator.py`
**Lines**: 408-431
**Traces**: FR-003, AC6, AR2-FINDING-02

Replace the entire `TestVerifyInternalAuth` class with:
```python
class TestVerifyInternalAuth:
    """Tests for verify_internal_auth function.

    After Feature 1310, auth is purely environment-gated.
    INTERNAL_API_KEY was removed (never provisioned in Terraform).
    """

    @patch.dict("os.environ", {"ENVIRONMENT": "dev"})
    def test_allows_dev(self):
        """Allows dev environment."""
        assert verify_internal_auth(None) is True

    @patch.dict("os.environ", {"ENVIRONMENT": "test"})
    def test_allows_test(self):
        """Allows test environment."""
        assert verify_internal_auth(None) is True

    @patch.dict("os.environ", {"ENVIRONMENT": "preprod"})
    def test_rejects_preprod(self):
        """Rejects preprod environment."""
        assert verify_internal_auth(None) is False

    @patch.dict("os.environ", {"ENVIRONMENT": "prod"})
    def test_rejects_prod(self):
        """Rejects prod environment."""
        assert verify_internal_auth(None) is False

    @patch.dict("os.environ", {"ENVIRONMENT": "dev"})
    def test_ignores_auth_header(self):
        """Auth header is ignored -- environment gates only."""
        assert verify_internal_auth("any-value") is True
        assert verify_internal_auth("") is True
        assert verify_internal_auth(None) is True

    @patch.dict("os.environ", {"ENVIRONMENT": "prod"})
    def test_rejects_prod_even_with_header(self):
        """Prod rejects regardless of auth header value."""
        assert verify_internal_auth("secret123") is False
        assert verify_internal_auth("") is False
        assert verify_internal_auth(None) is False

    def test_missing_environment_raises(self):
        """Missing ENVIRONMENT var raises KeyError (fail-fast)."""
        with patch.dict("os.environ", {}, clear=True):
            # Ensure ENVIRONMENT is not set
            import os
            os.environ.pop("ENVIRONMENT", None)
            with pytest.raises(KeyError, match="ENVIRONMENT"):
                verify_internal_auth(None)
```

Note: The `test_missing_environment_raises` test addresses AR2-FINDING-02 (missing edge case).

### T5: Run Tests and Verify

**Commands**:
```bash
# Run affected tests
cd /home/zeebo/projects/sentiment-analyzer-gsk
python -m pytest tests/unit/notification/test_alert_evaluator.py -v

# Verify no INTERNAL_API_KEY references remain
grep -r "INTERNAL_API_KEY" src/lambdas/notification/alert_evaluator.py
# Expected: no output

grep -r "INTERNAL_API_KEY" tests/unit/notification/test_alert_evaluator.py
# Expected: no output
```

**Traces**: AC1-AC7

## Acceptance Criteria Traceability

| AC | Verified By |
|----|-------------|
| AC1: INTERNAL_API_KEY removed | T2, T5 (grep verification) |
| AC2: Returns True only for dev/test | T3, T4 (test_allows_dev, test_allows_test, test_rejects_preprod, test_rejects_prod) |
| AC3: Ignores auth_header | T3, T4 (test_ignores_auth_header, test_rejects_prod_even_with_header) |
| AC4: Signature unchanged | T3 (function signature preserved) |
| AC5: Existing callers work | T3 (no callers exist -- AR1-01 confirmed -- but interface stable) |
| AC6: No INTERNAL_API_KEY in tests | T4, T5 (grep verification) |
| AC7: No Terraform changes | N/A (no Terraform tasks) |

---

## Adversarial Review #3: Final Cross-Artifact Review

### AR3-CHECK-01: Spec-Plan-Task Alignment

All 3 functional requirements (FR-001, FR-002, FR-003) map to tasks (T2, T3, T4). Both non-functional requirements are addressed (NFR-001 by absence of Terraform tasks, NFR-002 by T3's signature preservation). The AR1 module docstring finding is captured in T1. The AR2 KeyError test finding is captured in T4. **PASS**.

### AR3-CHECK-02: Acceptance Criteria Coverage

All 7 acceptance criteria (AC1-AC7) are traced to specific tasks and verification steps. **PASS**.

### AR3-CHECK-03: Edge Case Coverage

6/6 spec edge cases are covered by test methods in T4:
- Dev/no header -> test_allows_dev
- Dev/any header -> test_ignores_auth_header
- Test/no header -> test_allows_test
- Preprod/any header -> test_rejects_preprod
- Prod/any header -> test_rejects_prod + test_rejects_prod_even_with_header
- ENVIRONMENT missing -> test_missing_environment_raises
**PASS**.

### AR3-CHECK-04: Task Dependency Order Is Correct

T1 and T2 are independent (different lines in same file). T3 depends on T2 (references INTERNAL_API_KEY removed). T4 depends on T2+T3 (tests match new behavior). T5 depends on all. **PASS**.

### AR3-FINDING-01: T4 test_missing_environment_raises Has a Subtlety

**Issue**: The test uses `patch.dict("os.environ", {}, clear=True)` which clears ALL env vars, then also does `os.environ.pop("ENVIRONMENT", None)`. The `clear=True` already removes ENVIRONMENT, making the `pop` redundant. However, this is defensive coding and harmless.

More importantly: other tests in the same file may set ENVIRONMENT via class-level fixtures or conftest. The `clear=True` could interfere with pytest internals. A safer approach would be:

```python
def test_missing_environment_raises(self):
    """Missing ENVIRONMENT var raises KeyError (fail-fast)."""
    env_copy = os.environ.copy()
    env_copy.pop("ENVIRONMENT", None)
    with patch.dict("os.environ", env_copy, clear=True):
        with pytest.raises(KeyError, match="ENVIRONMENT"):
            verify_internal_auth(None)
```

**Decision**: AMEND T4 to use the safer pattern. The redundant `os.environ.pop` and the `import os` inside the test method are both code smells.

### AR3-FINDING-02: Risk of Test Pollution from clear=True

**Issue**: `patch.dict("os.environ", {}, clear=True)` removes DATABASE_TABLE, which is read at module level. But since the module is already imported (module-level variables already captured), this won't cause an ImportError. The function only reads ENVIRONMENT at call time. **No risk**.

### Summary

| Check/Finding | Status |
|---------------|--------|
| Spec-Plan-Task alignment | PASS |
| AC coverage | PASS |
| Edge case coverage | PASS |
| Dependency order | PASS |
| AR3-01: KeyError test pattern | AMEND (minor cleanup) |
| AR3-02: Test pollution risk | NO RISK |

**Final assessment**: All artifacts are consistent, complete, and ready for implementation. One minor test pattern improvement noted in AR3-01 -- implementer should use the safer env-copy approach for the KeyError test.
