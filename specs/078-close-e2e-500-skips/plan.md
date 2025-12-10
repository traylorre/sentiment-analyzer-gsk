# Implementation Plan: Close Config Creation 500 E2E Test Skips

**Branch**: `078-close-e2e-500-skips` | **Date**: 2025-12-10 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `/specs/078-close-e2e-500-skips/spec.md`

## Summary

Remove ~18 defensive `pytest.skip()` calls from E2E tests that were added as workarounds for the config creation 500 error (now fixed by Feature 077). This is a test maintenance task - no new code, no architecture changes, just removing workarounds now that the root cause is fixed.

## Technical Context

**Language/Version**: Python 3.13
**Primary Dependencies**: pytest 8.0+
**Storage**: N/A (test files only)
**Testing**: pytest (modifying E2E tests in `tests/e2e/`)
**Target Platform**: Linux server (CI/preprod)
**Project Type**: single (existing project structure)
**Performance Goals**: N/A (test modification)
**Constraints**: Tests must pass against preprod with Feature 077 deployed
**Scale/Scope**: ~6 test files, ~18 skip patterns to remove

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Constitution Section | Applicable? | Status | Notes |
|---------------------|-------------|--------|-------|
| 7) Testing & Validation | YES | PASS | Removing defensive skips to restore test coverage |
| Implementation Accompaniment Rule | NO | N/A | Not adding implementation code |
| Functional Integrity Principle | YES | PASS | Restoring previously-disabled test assertions |
| 8) Git Workflow & CI/CD | YES | PASS | Standard feature branch workflow |
| Pipeline Check Bypass | YES | PASS | Tests must pass, no bypass |

**Gate Status**: PASS - No violations. This is test maintenance aligned with Constitution Section 7.

## Project Structure

### Documentation (this feature)

```text
specs/078-close-e2e-500-skips/
├── spec.md              # Feature specification
├── plan.md              # This file
├── research.md          # Skip pattern inventory (Phase 0)
├── checklists/
│   └── requirements.md  # Requirements checklist
└── tasks.md             # Implementation tasks (Phase 2)
```

### Source Code (files to modify)

```text
tests/e2e/
├── test_config_crud.py            # ~8 skip patterns
├── test_alerts.py                 # ~2 skip patterns
├── test_anonymous_restrictions.py # ~5 skip patterns
├── test_auth_anonymous.py         # ~2 skip patterns
├── test_failure_injection.py      # ~1 skip pattern
└── test_sentiment.py              # ~1 skip pattern (verify)

RESULT2-tech-debt.md               # Update closure summary
```

**Structure Decision**: No new files created. Modifying existing E2E test files to remove defensive skip patterns.

## Complexity Tracking

> **No violations - section not applicable**

This is a straightforward test maintenance task with no architectural decisions required.

## Phase 0: Research - Skip Pattern Inventory

### Research Task 1: Exact Skip Pattern Discovery

**Question**: What is the exact skip pattern used across E2E tests?

**Method**: Grep for skip patterns in `tests/e2e/`

**Expected Patterns**:
```python
# Pattern 1: Direct skip call
pytest.skip("Config creation endpoint returning 500 - API issue")

# Pattern 2: Conditional skip
if response.status_code == 500:
    pytest.skip("Config creation endpoint returning 500")
```

### Research Task 2: Compound Skip Conditions

**Question**: Are there tests with BOTH 500-related AND other skip conditions?

**Method**: Identify tests that have multiple skip reasons

**Decision Required**: For compound skips, remove only the 500-related condition, preserve other conditions (e.g., "endpoint not implemented")

### Research Task 3: Feature 077 Deployment Verification

**Question**: How to verify Feature 077 is deployed to preprod?

**Method**: Check if config creation endpoint returns 422 (validation error) instead of 500 for invalid input

**Verification Command**:
```bash
curl -X POST https://preprod.example.com/api/v2/config \
  -H "Content-Type: application/json" \
  -d '{"invalid": "data"}' \
  -w "%{http_code}"
# Expected: 422 (not 500)
```

## Phase 1: Design - No New Design Required

This feature does not require:
- **data-model.md**: No new data entities
- **contracts/**: No new API contracts
- **quickstart.md**: No new components to document

### Decision Record

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Skip removal approach | Remove entire conditional block | Clean removal, not leaving dead code |
| Test execution | Run against preprod | Validates Feature 077 fix is deployed |
| Documentation update | Update RESULT2-tech-debt.md | Track closure of this tech debt category |

## Implementation Approach

### Step 1: Inventory Skip Patterns
1. Search all E2E test files for "500" and "skip" patterns
2. Document exact line numbers and test functions
3. Identify compound skip conditions

### Step 2: Remove Skip Patterns
For each identified skip pattern:
1. Remove the `if response.status_code == 500: pytest.skip(...)` block
2. Let the test run through to its natural assertion
3. Preserve any other skip conditions (e.g., "endpoint not implemented")

### Step 3: Verify Tests Pass
1. Run E2E tests against preprod: `pytest tests/e2e/ -k "config" -v`
2. Confirm 0 tests skip with "500" message
3. Confirm all unskipped tests pass

### Step 4: Update Documentation
1. Update RESULT2-tech-debt.md with closure summary
2. Include PR number and closure date

## Risk Assessment

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| Feature 077 not deployed | Low | High | Verify endpoint returns 422 before implementation |
| Tests fail after unskip | Medium | Low | Tests failing = expected behavior, means fix isn't complete |
| Compound skip removal breaks tests | Low | Medium | Only remove 500-related conditions |

## Success Criteria Verification

| SC | Criterion | Verification Method |
|----|-----------|---------------------|
| SC-001 | Zero "500" skip messages | `grep -r "500" tests/e2e/ \| grep -i skip` returns empty |
| SC-002 | 100% unskipped tests pass | `pytest tests/e2e/ -k "config"` all pass |
| SC-003 | RESULT2 updated | `grep "CLOSED" RESULT2-tech-debt.md` shows closure |
| SC-004 | No skip count regression | Total skips ≤ before minus removed |

---

**Next Step**: Run `/speckit.tasks` to generate implementation task list
