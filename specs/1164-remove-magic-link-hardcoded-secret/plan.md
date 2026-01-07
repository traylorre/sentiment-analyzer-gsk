# Implementation Plan: Remove Hardcoded MAGIC_LINK_SECRET

**Branch**: `1164-remove-magic-link-hardcoded-secret` | **Date**: 2026-01-06 | **Spec**: [spec.md](./spec.md)
**Input**: Phase 0 C1 Security Fix - Remove hardcoded secret fallback

## Summary

Remove the hardcoded MAGIC_LINK_SECRET fallback value from auth.py, add fail-fast validation at module load, and remove the orphaned `_verify_magic_link_signature()` function that is never called.

## Technical Context

**Language/Version**: Python 3.13
**Primary Dependencies**: os (stdlib), hmac (stdlib)
**Storage**: DynamoDB (no changes - tokens still stored with signatures)
**Testing**: pytest with environment variable fixtures
**Target Platform**: AWS Lambda
**Project Type**: Web application (backend Lambda)
**Performance Goals**: N/A (startup validation only)
**Constraints**: Must not break existing magic link flows
**Scale/Scope**: 2 file changes + test updates

## Constitution Check

| Gate | Status | Notes |
|------|--------|-------|
| No hardcoded secrets | FIXING | This feature addresses the violation |
| Fail-fast validation | ADDING | Required secrets checked at load time |
| Dead code removal | PASS | Removing orphaned verification function |

## Project Structure

### Documentation (this feature)

```text
specs/1164-remove-magic-link-hardcoded-secret/
├── spec.md              # Feature specification (DONE)
├── plan.md              # This file
├── tasks.md             # Task breakdown (next: /speckit.tasks)
└── checklists/
    └── requirements.md  # Specification quality checklist (DONE)
```

### Source Code (repository root)

```text
src/lambdas/dashboard/
└── auth.py              # Remove hardcoded fallback, add validation, remove dead code

tests/
├── unit/lambdas/dashboard/
│   └── test_auth_us2.py # Update to use fixtures for MAGIC_LINK_SECRET
└── integration/
    └── test_us2_magic_link.py  # Already sets env var properly
```

**Structure Decision**: Minimal changes to existing files. No new files required.

## Implementation Approach

### Phase 1: Remove Hardcoded Fallback

**File**: `src/lambdas/dashboard/auth.py`

**Current code (lines 1101-1103)**:
```python
MAGIC_LINK_SECRET = os.environ.get(
    "MAGIC_LINK_SECRET", "default-dev-secret-change-in-prod"
)
```

**New code**:
```python
MAGIC_LINK_SECRET = os.environ.get("MAGIC_LINK_SECRET", "")
if not MAGIC_LINK_SECRET:
    raise RuntimeError(
        "MAGIC_LINK_SECRET environment variable is required but not set. "
        "Set it to a secure random value (minimum 32 characters)."
    )
```

### Phase 2: Remove Dead Code

**File**: `src/lambdas/dashboard/auth.py`

Remove the orphaned function (lines 1117-1120):
```python
def _verify_magic_link_signature(token_id: str, email: str, signature: str) -> bool:
    """Verify magic link signature."""
    expected = _generate_magic_link_signature(token_id, email)
    return hmac.compare_digest(expected, signature)
```

This function is never called - verification uses atomic DynamoDB consumption instead.

### Phase 3: Update Unit Tests

**File**: `tests/unit/lambdas/dashboard/test_auth_us2.py`

The tests that test signature functions need a proper env var fixture:

```python
@pytest.fixture(autouse=True)
def set_magic_link_secret(monkeypatch):
    """Set MAGIC_LINK_SECRET for all tests in this module."""
    monkeypatch.setenv("MAGIC_LINK_SECRET", "test-secret-for-unit-tests-minimum-32-chars")
```

Tests to update:
- `test_generate_signature()` - Keep, validates HMAC generation
- `test_different_inputs_different_signature()` - Keep
- `test_verify_valid_signature()` - Remove (function deleted)
- `test_verify_invalid_signature()` - Remove (function deleted)

### Phase 4: Verify Integration Tests

**File**: `tests/integration/test_us2_magic_link.py`

Already properly sets env var at line 45:
```python
os.environ["MAGIC_LINK_SECRET"] = "test-secret-key-for-signing"
```

No changes needed, but verify tests pass.

## Dependencies

| Dependency | Status | Impact |
|------------|--------|--------|
| pytest monkeypatch | Available | For env var fixtures in tests |
| DynamoDB atomic ops | Working | Not affected - verification mechanism unchanged |

## Complexity Tracking

No constitution violations. Minimal scope:
- 1 validation block added (~5 lines)
- 1 function removed (~4 lines)
- Test fixture added (~3 lines)
- 2 test functions removed

## Risks and Mitigations

| Risk | Probability | Impact | Mitigation |
|------|-------------|--------|------------|
| Tests fail without env var | Medium | Low | Add pytest fixture |
| Lambda fails at cold start | Low | High | Ensure Terraform sets env var |
| Existing tokens break | Very Low | Low | Verification doesn't use signature |

## Definition of Done

- [ ] Hardcoded fallback removed from auth.py
- [ ] Fail-fast validation added at module load
- [ ] `_verify_magic_link_signature()` function removed
- [ ] Unit tests updated with env var fixture
- [ ] Tests for removed function deleted
- [ ] All tests pass
- [ ] PR created and merged
