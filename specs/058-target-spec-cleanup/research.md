# Research: Target Repo Spec Cleanup

**Feature**: 058-target-spec-cleanup
**Date**: 2025-12-07

## Executive Summary

This research documents the current validation state of the target repo (sentiment-analyzer-gsk) and identifies root causes for each failing validator. All 5 failing validators are now understood with clear remediation paths.

## 1. Current Validation State

### Validation Run Results

| Validator          | ID        | Severity | Status | Root Cause                                         |
| ------------------ | --------- | -------- | ------ | -------------------------------------------------- |
| canonical-validate | CAN-002   | HIGH     | FAIL   | IAM files lack canonical source citations          |
| property           | PROP-001  | HIGH     | FAIL   | Validator subprocess fails (not test failures)     |
| spec-coherence     | SPEC-001  | MEDIUM   | FAIL   | Make target unavailable, fallback fails            |
| bidirectional      | BIDIR-001 | MEDIUM   | FAIL   | Make target unavailable, intrinsic detection fails |
| mutation           | MUT-001   | MEDIUM   | FAIL   | No mutation test infrastructure                    |

### Suppressed Findings (8 total)

All suppressed via `iam-allowlist.yaml` with entry `lambda-cicd-deployment`:

- SQS-009: sqs:DeleteQueue (CI queue management)
- LAMBDA-007 x4: Lambda privilege escalation (CI/CD deployment requirement)
- LAMBDA-011 x3: Function URL auth (intentional public access)

**Decision**: These suppressions are legitimate and require no action.

## 2. Root Cause Analysis

### CAN-002: Missing Canonical Source Citations

**Problem**: The canonical-validate validator checks for a `## Canonical Sources Cited` section in PR descriptions when IAM files are modified. Since we're not running in a PR context, it detects 4 IAM files without citations.

**Files Affected**:

- `infrastructure/iam-policies/prod-deployer-policy.json`
- `infrastructure/iam-policies/preprod-deployer-policy.json`
- `infrastructure/terraform/ci-user-policy.tf`
- `docs/iam-policies/dev-deployer-policy.json`

**Resolution Strategy**:

1. Add inline `// Canonical: <url>` comments to each permission block
2. Update IAM policies with AWS IAM Actions Reference links
3. The validator should PASS once canonical sources are embedded in files

**Canonical Source Format**:

```json
{
  "Effect": "Allow",
  "Action": ["s3:GetObject", "s3:PutObject"],
  "Resource": "arn:aws:s3:::bucket/*"
  // Canonical: https://docs.aws.amazon.com/service-authorization/latest/reference/list_amazons3.html
}
```

**Decision**: Add canonical source citations to all IAM policy statements
**Rationale**: Enables auditability and verifies permissions against AWS documentation
**Alternatives Rejected**: Suppressing CAN-002 (loses audit value)

### PROP-001: Property Tests Failing in Validator

**Problem**: Property tests pass when run directly (`pytest tests/property/` = 33 passed) but validator reports FAIL.

**Root Cause Investigation**:

1. Target repo lacks `make test-property` target
2. Validator falls back to intrinsic detection (direct pytest)
3. The subprocess call fails for unknown reason (exit code != 0)

**Verification**:

```bash
# Local run succeeds
python3 -m pytest tests/property/ -v  # 33 passed in 2.79s

# Validator runs subprocess that fails
# Need to debug subprocess environment differences
```

**Resolution Strategy**:

1. Add `make test-property` target to target repo Makefile
2. OR: Debug why subprocess pytest fails when direct pytest succeeds
3. May be Python path or virtual environment issue

**Decision**: Add `test-property` Makefile target to target repo
**Rationale**: Consistent with template pattern, avoids subprocess debugging
**Alternatives Rejected**: Modifying template validator (changes template, not target)

### SPEC-001: Spec Coherence Check Failing

**Problem**: SpecCoherenceValidator fails because target repo lacks `make test-spec` target.

**Current Behavior**:

- Validator checks for `make test-spec` target
- Target repo doesn't have it
- Validator falls back to FAIL (not SKIP per Amendment 1.7)

**Resolution Strategy**:

1. Verify Amendment 1.7 is correctly implemented in validator
2. If validator should SKIP, fix the template validator
3. If target repo should have test-spec, add the Makefile target

**Decision**: Target repo should implement `make test-spec` OR validator should SKIP
**Rationale**: Per Amendment 1.7, target repos without template targets should SKIP
**Further Investigation**: Check if validator implementation matches Amendment 1.7

### BIDIR-001: Bidirectional Verification Failing

**Problem**: BidirectionalValidator fails because target repo lacks the infrastructure.

**Current Behavior**:

- Validator checks for `make test-bidirectional`
- Falls back to intrinsic detection
- Intrinsic detection fails (no `.specify/verification/` structure)

**Resolution Strategy**:

1. Same as SPEC-001 - verify Amendment 1.7 compliance
2. Target repo should either implement bidirectional or validator should SKIP

**Decision**: Validator should SKIP for target repos per Amendment 1.7
**Rationale**: Target repo independence - shouldn't require template infrastructure

### MUT-001: Mutation Testing Failing

**Problem**: MutationValidator fails because target repo has no mutation testing setup.

**Current Behavior**:

- Validator checks for `make test-mutation`
- Falls back to FAIL status

**Resolution Strategy**:

1. Add mutmut to dev dependencies
2. Add `make test-mutation` target
3. OR: Verify validator properly SKIPs per Amendment 1.7

**Decision**: Verify Amendment 1.7 compliance first, then add infrastructure if needed
**Rationale**: Don't add infrastructure that should be optional per constitution

## 3. Amendment 1.7 Compliance Review

**Amendment 1.7 - Target Repo Independence** states:

> Validators MUST gracefully SKIP (not FAIL) when target repos lack template-specific infrastructure

### ROOT CAUSE: Misclassified Repo Type

**Critical Finding**: The target repo is misclassified as "template" instead of "dependent".

```
$ python3 -c "from src.validators.utils import detect_repo_type; ..."
Repo type: template  ← WRONG, should be "dependent"
```

**Location**: `src/validators/utils.py:detect_repo_type()` lines 76-79

**Bug**: The function has a fallback that checks for `constitution.md`:

```python
# Fallback: Check for constitution.md (for test environments without git remote)
constitution = repo_path / CONSTITUTION_PATH
if constitution.exists():
    return "template"  # ← Too aggressive
```

**Why It's Wrong**: Target repos that adopt the speckit methodology have their own `constitution.md`. This fallback was designed for test environments but incorrectly classifies ANY repo with a constitution as "template".

**Impact**: Since the repo is classified as "template":

- Amendment 1.7 checks are bypassed (they only apply to "dependent" repos)
- Validators run as if they're in the template repo
- All SKIP logic for missing make targets is never triggered

### Validator Behavior Analysis (Post Root Cause)

| Validator      | Expected (if "dependent")    | Actual (misclassified as "template") |
| -------------- | ---------------------------- | ------------------------------------ |
| spec-coherence | SKIP (no make test-spec)     | FAIL (runs make, fails)              |
| bidirectional  | Intrinsic detection          | Intrinsic detection (same)           |
| property       | Intrinsic detection          | FAIL (subprocess issue)              |
| mutation       | SKIP (no make test-mutation) | FAIL (runs make, fails)              |

### Future Work Required (Separate Spec)

This is a design issue requiring careful thought. Do NOT rush to fix.

**Issue**: How to distinguish between:

1. Template repo (terraform-gsk-template) - should run full validation
2. Target repos that adopted speckit (have constitution.md) - should use Amendment 1.7
3. Target repos without speckit (no constitution.md) - should use Amendment 1.7

**Possible Solutions** (each has tradeoffs):

1. Remove constitution fallback entirely (breaks tests)
2. Add explicit marker file (e.g., `.specify/TEMPLATE_REPO`)
3. Check git remote URL more strictly
4. Check constitution content for template vs target patterns

**Decision**: Defer to separate `/speckit.specify` work item
**Rationale**: This affects template-target boundary design, needs architectural review

## 4. Bidirectional Coverage Analysis

Target repo has 22 spec directories. Coverage audit needed:

| Spec                        | Status         | Action Needed              |
| --------------------------- | -------------- | -------------------------- |
| 001-019                     | Original specs | Audit for coherence        |
| 038-ecr-docker-build        | Recent         | Should be current          |
| 041-pipeline-blockers       | Recent         | Should be current          |
| 051-validation-bypass-audit | Recent         | Should be current          |
| chaos-testing-\*.md         | Loose files    | Archive or convert to spec |

**Decision**: Audit all specs for bidirectional coverage
**Rationale**: 100% coverage required per clarification

## 5. Technology Decisions

### Mutation Testing Tool

**Decision**: mutmut
**Rationale**: Already in template requirements, Python-native, integrates with pytest
**Alternatives Rejected**:

- cosmic-ray (less maintained)
- mutpy (deprecated)

### Canonical Source Format

**Decision**: Inline comments in JSON/HCL files
**Rationale**: Co-located with permissions, no separate file to maintain
**Alternatives Rejected**:

- Separate CANONICAL_SOURCES.md (divorced from code)
- PR description only (not persistent)

## 6. Implementation Priority

Based on severity and dependencies:

1. **P1**: Fix PROP-001 - Add `make test-property` or debug subprocess
2. **P1**: Fix CAN-002 - Add canonical citations to IAM files
3. **P2**: Fix SPEC-001 - Add `make test-spec` or verify Amendment 1.7
4. **P2**: Fix BIDIR-001 - Add `make test-bidirectional` or verify Amendment 1.7
5. **P3**: Fix MUT-001 - Add mutation testing or verify Amendment 1.7

## 7. Open Questions

1. Why does subprocess pytest fail when direct pytest succeeds?

   - Needs environment comparison (PATH, PYTHONPATH, venv)

2. ~~Are validators correctly implementing Amendment 1.7?~~

   - **ANSWERED**: Validators ARE correctly implemented, but `detect_repo_type` misclassifies repos

3. Should target repo adopt template make targets?
   - Pro: Consistency, passes validators
   - Con: Coupling to template (tension with Amendment 1.7)

## 8. Included Fixes (Previously Deferred)

### FIX-001: `detect_repo_type` Constitution Fallback (IN SCOPE)

**Location**: `src/validators/utils.py:76-79`
**Severity**: HIGH (blocks Amendment 1.7 for all speckit-adopting repos)
**Current Behavior**: Repos with `constitution.md` are classified as "template"
**Expected Behavior**: Only `traylorre/terraform-gsk-template` should be "template"

**Solution**: Remove the constitution fallback entirely. The rule is unambiguous:

- `terraform-gsk-template` is the ONLY template repo in existence, ever
- All other repos are target/dependent repos
- If git remote check fails, default to "dependent" (not "template")

**Implementation**:

```python
# BEFORE (buggy):
# Fallback: Check for constitution.md (for test environments without git remote)
constitution = repo_path / CONSTITUTION_PATH
if constitution.exists():
    return "template"

# AFTER (fixed):
# No fallback needed - if remote check fails, repo is dependent
# Only terraform-gsk-template is ever the template
```

**Test Impact**: Template unit tests that rely on constitution fallback will need to mock git remote or use fixtures.

---

## 9. Deferred Work (Future Specs)

### DEFERRED-002: Property Test Subprocess Environment

**Location**: PropertyValidator intrinsic detection path
**Severity**: MEDIUM (workaround: add make target)
**Current Behavior**: `python3 -m pytest` subprocess fails, direct pytest succeeds
**Why Deferred**:

1. Adding `make test-property` target bypasses intrinsic detection path
2. If make target works, subprocess issue becomes moot
3. If still fails after make target, investigate then

### DEFERRED-003: Canonical Source Detection Outside PR Context

**Location**: CanonicalSourceValidator
**Severity**: LOW (only affects non-PR validation runs)
**Current Behavior**: Checks for PR description section even when not in PR
**Why Deferred**: Will be addressed opportunistically when code is touched during future target repo work

### Summary Table

| ID               | Issue                     | Severity | Status                       |
| ---------------- | ------------------------- | -------- | ---------------------------- |
| ~~DEFERRED-001~~ | detect_repo_type fallback | HIGH     | **IN SCOPE** (FIX-001)       |
| DEFERRED-002     | Subprocess pytest env     | MEDIUM   | Deferred (workaround exists) |
| DEFERRED-003     | Canonical outside PR      | LOW      | Deferred (opportunistic fix) |
