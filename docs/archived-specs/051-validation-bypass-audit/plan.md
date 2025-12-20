# Implementation Plan: Validation Bypass Audit

**Branch**: `051-validation-bypass-audit` | **Date**: 2025-12-06 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `/specs/051-validation-bypass-audit/spec.md`

## Summary

Comprehensive audit of all validation bypasses (SKIP=, pragma allowlist, noqa, type:ignore, datetime.utcnow) in the target repository, followed by classification and remediation. This is a code quality/maintenance feature that produces an audit report and fixes technical debt.

## Technical Context

**Language/Version**: Python 3.13, Bash (for grep/scanning scripts)
**Primary Dependencies**: grep, ruff (for lint analysis), pytest (for validation)
**Storage**: N/A (audit report is markdown output)
**Testing**: pytest (verify remediation doesn't break tests)
**Target Platform**: Local development, CI/CD hooks
**Project Type**: Code maintenance/audit tooling
**Performance Goals**: Audit completes in < 30 seconds
**Constraints**: Must not break existing tests or functionality
**Scale/Scope**: Single repository (~1600 unit tests, ~50k LOC Python)

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Gate | Status | Notes |
|------|--------|-------|
| Tech Debt Tracking (9) | PASS | This feature IS tech debt remediation |
| Testing Requirements (7) | PASS | All changes must pass existing tests |
| Pre-Push Requirements (8) | PASS | Goal is to eliminate SKIP= bypasses |
| Pipeline Bypass Prohibition | PASS | Feature eliminates bypass need |
| Deterministic Time Handling | APPLICABLE | datetime.utcnow() remediation is core scope |

**All gates passed. Proceeding to Phase 0.**

## Project Structure

### Documentation (this feature)

```text
specs/051-validation-bypass-audit/
├── plan.md              # This file
├── research.md          # Phase 0 output
├── quickstart.md        # Phase 1 output
└── tasks.md             # Phase 2 output (via /speckit.tasks)
```

### Source Code (repository root)

```text
# Audit tooling (optional - can be manual grep commands)
scripts/
└── audit-bypasses.sh    # Optional: Automated bypass detection

# Files to remediate
src/lambdas/dashboard/chaos.py  # datetime.utcnow() usages
src/lambdas/*/handler.py        # Any datetime.utcnow() usages
.github/workflows/deploy.yml     # pragma: allowlist (already fixed)
.pre-commit-config.yaml          # pytest hook configuration

# Documentation output
docs/
└── TECH_DEBT_REGISTRY.md       # Updated with bypass audit results
```

**Structure Decision**: No new source directories needed. This is primarily an audit + targeted edits to existing files.

## Complexity Tracking

No violations detected. This is standard code maintenance.

## Bypass Categories & Detection

### Category 1: SKIP= Environment Variables (HIGH priority)

**Detection**: `grep -r "SKIP=" .git/hooks/ .github/`
**Issue**: Bypasses pre-commit hooks during commit/push
**Remediation**: Fix underlying hook issues so SKIP= is unnecessary

### Category 2: pragma: allowlist secret (MEDIUM priority)

**Detection**: `grep -rn "pragma: allowlist" --include="*.py" --include="*.yml"`
**Issue**: Bypasses detect-secrets scanning
**Classification**: LEGITIMATE if for known false positives (moto mock creds)

### Category 3: # noqa Comments (LOW priority)

**Detection**: `grep -rn "# noqa" --include="*.py" src/`
**Issue**: Bypasses ruff/flake8 linting
**Classification**: Review each - some are legitimate, others are tech debt

### Category 4: # type: ignore Comments (LOW priority)

**Detection**: `grep -rn "# type: ignore" --include="*.py" src/`
**Issue**: Bypasses mypy type checking
**Classification**: Review each for validity

### Category 5: datetime.utcnow() (HIGH priority)

**Detection**: `grep -rn "datetime.utcnow" --include="*.py" src/`
**Issue**: Deprecated in Python 3.12+, causes 365+ warnings
**Remediation**: Replace with `datetime.now(datetime.UTC)`

### Category 6: Pre-commit Hook Issues (HIGH priority)

**Detection**: Run `pre-commit run --all-files` and analyze failures
**Issue**: pytest hook fails with "Executable python not found"
**Remediation**: Fix .pre-commit-config.yaml to use correct python path

## Remediation Strategy

1. **Phase 1**: Audit and document all bypasses in structured report
2. **Phase 2**: Classify each as LEGITIMATE or TECH_DEBT
3. **Phase 3**: Remediate TECH_DEBT items in priority order:
   - HIGH: datetime.utcnow(), pre-commit config, SKIP= eliminations
   - MEDIUM: pragma allowlist review
   - LOW: noqa/type:ignore review
4. **Phase 4**: Document remaining LEGITIMATE bypasses with justification
5. **Phase 5**: Verify all tests pass, push succeeds without SKIP=
