# Feature 1310: Implementation Plan

## Overview

Remove the dead `INTERNAL_API_KEY` empty-string fallback pattern from `alert_evaluator.py` and simplify `verify_internal_auth()` to an explicit environment gate. Two files modified, zero infrastructure changes.

## Changes

### Change 1: Remove INTERNAL_API_KEY and Simplify verify_internal_auth

**File**: `src/lambdas/notification/alert_evaluator.py`

#### 1a: Update Module Docstring (line 14)

```python
# BEFORE (line 14):
    - Internal endpoints require X-Internal-Auth header

# AFTER:
    - Internal endpoints are restricted to dev/test environments
```

**Rationale**: AR1-FINDING-02. The X-Internal-Auth header is no longer checked. Docstring must reflect the actual security model.

#### 1b: Remove INTERNAL_API_KEY Variable (line 38)

```python
# BEFORE (line 38):
INTERNAL_API_KEY = os.environ.get("INTERNAL_API_KEY", "")

# AFTER:
# (line removed entirely)
```

**Rationale**: FR-001. Variable is never set by Terraform. Dead infrastructure.

#### 1c: Simplify verify_internal_auth (lines 288-301)

```python
# BEFORE (lines 288-301):
def verify_internal_auth(auth_header: str | None) -> bool:
    """Verify internal API authentication.

    Args:
        auth_header: X-Internal-Auth header value

    Returns:
        True if authenticated, False otherwise
    """
    if not INTERNAL_API_KEY:
        # Allow in dev/test if not configured
        return os.environ["ENVIRONMENT"] in ("dev", "test")

    return auth_header == INTERNAL_API_KEY

# AFTER:
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

**Rationale**: FR-002. Removes dead INTERNAL_API_KEY branch. Makes security model explicit.

### Change 2: Update Tests

**File**: `tests/unit/notification/test_alert_evaluator.py`

#### 2a: Remove verify_internal_auth from Import (line 26)

No change needed -- keep the import. The function still exists, only its behavior changed.

#### 2b: Rewrite TestVerifyInternalAuth Class (lines 408-431)

```python
# BEFORE (lines 408-431):
class TestVerifyInternalAuth:
    """Tests for verify_internal_auth function."""

    @patch("src.lambdas.notification.alert_evaluator.INTERNAL_API_KEY", "secret123")
    def test_valid_auth(self):
        """Returns True for valid auth."""
        assert verify_internal_auth("secret123") is True

    @patch("src.lambdas.notification.alert_evaluator.INTERNAL_API_KEY", "secret123")
    def test_invalid_auth(self):
        """Returns False for invalid auth."""
        assert verify_internal_auth("wrong") is False

    @patch("src.lambdas.notification.alert_evaluator.INTERNAL_API_KEY", "")
    @patch.dict("os.environ", {"ENVIRONMENT": "dev"})
    def test_allows_dev_without_key(self):
        """Allows dev environment without key."""
        assert verify_internal_auth(None) is True

    @patch("src.lambdas.notification.alert_evaluator.INTERNAL_API_KEY", "")
    @patch.dict("os.environ", {"ENVIRONMENT": "prod"})
    def test_rejects_prod_without_key(self):
        """Rejects prod environment without key."""
        assert verify_internal_auth(None) is False

# AFTER:
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
```

**Rationale**: FR-003. Tests now reflect the actual behavior: pure environment gating. No more INTERNAL_API_KEY patches. Added tests for all four environments plus header-ignored verification.

## Dependency Order

1. Change 1 (alert_evaluator.py) -- no dependencies
2. Change 2 (test_alert_evaluator.py) -- depends on Change 1 (tests must match new behavior)

Both can be in a single commit.

## Verification

```bash
# Run affected tests
python -m pytest tests/unit/notification/test_alert_evaluator.py -v

# Run full notification test suite
python -m pytest tests/unit/notification/ -v

# Verify no other references remain
grep -r "INTERNAL_API_KEY" src/ tests/
# Should only show: (nothing in src/, only the test import of verify_internal_auth)
```

## Rollback Plan

Revert the single commit. No infrastructure changes means no Terraform state to reconcile.

## What This Does NOT Change

- No Terraform modifications (INTERNAL_API_KEY was never in infra)
- No changes to notification handler.py
- No changes to any other Lambda
- Function signature preserved for any future callers
- No changes to the `/api/internal/alerts/evaluate` routing (wherever it's routed)

---

## Adversarial Review #2: Cross-Artifact Consistency

### Spec-to-Plan Traceability

| Spec Requirement | Plan Coverage | Status |
|-----------------|---------------|--------|
| FR-001: Remove INTERNAL_API_KEY variable | Change 1b | COVERED |
| FR-002: Simplify verify_internal_auth | Change 1c | COVERED |
| FR-003: Update tests | Change 2b | COVERED |
| NFR-001: No Terraform changes | Explicitly stated in "What This Does NOT Change" | COVERED |
| NFR-002: Interface stability | Function signature preserved in Change 1c | COVERED |
| AR1-02: Module docstring update | Change 1a | COVERED |

### AR2-FINDING-01: Plan Verification Command Has Minor Inaccuracy

**Issue**: The verification section says `grep -r "INTERNAL_API_KEY" src/ tests/` should show nothing in src/. This is correct. But the comment says "only the test import of verify_internal_auth" -- this is misleading because the grep is for INTERNAL_API_KEY, not verify_internal_auth. After the change, the grep should return zero results in both src/ and tests/.

**Impact**: Cosmetic. The verification logic is sound, the comment is imprecise.

**Decision**: ACCEPT. No plan change needed -- the command itself is correct.

### AR2-FINDING-02: Edge Case Coverage in Tests

**Check**: Spec lists 6 edge cases. Plan's test rewrite covers:
- Dev allows: YES (test_allows_dev)
- Dev ignores header: YES (test_ignores_auth_header)
- Test allows: YES (test_allows_test)
- Preprod denies: YES (test_rejects_preprod)
- Prod denies: YES (test_rejects_prod, test_rejects_prod_even_with_header)
- ENVIRONMENT missing raises KeyError: NOT EXPLICITLY TESTED

**Recommendation**: Add a test for missing ENVIRONMENT raising KeyError. This is an important edge case from the spec.

**Decision**: AMEND plan. Add test to Change 2b.

### AR2-FINDING-03: AC6 Validation

**Check**: AC6 says "no references to INTERNAL_API_KEY in test file". After Change 2b, all @patch decorators referencing INTERNAL_API_KEY are removed. The string "INTERNAL_API_KEY" will not appear in the test file. CONFIRMED.

### AR2-FINDING-04: Blank Line After Removed Variable

**Check**: Line 38 is `INTERNAL_API_KEY = os.environ.get(...)` followed by line 39 (blank) and line 40 (blank). After removing line 38, the two consecutive blank lines around the comment block should be reduced to one for PEP 8 compliance.

**Decision**: AMEND plan. Note that removing line 38 should also clean up the resulting double-blank-line.

### Summary

| Finding | Action |
|---------|--------|
| AR2-01: Verification comment imprecise | ACCEPT (cosmetic) |
| AR2-02: Missing KeyError test | AMEND - add test |
| AR2-03: AC6 satisfied | CONFIRMED |
| AR2-04: Double blank line after removal | AMEND - note cleanup |

**Net assessment**: Two minor amendments to plan. No structural drift between spec and plan.
