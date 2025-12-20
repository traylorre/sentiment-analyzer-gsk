# Implementation Plan: Validation Blind Spot Audit

**Branch**: `070-validation-blindspot-audit` | **Date**: 2025-12-08 | **Spec**: [spec.md](spec.md)
**Input**: Feature specification from `/specs/070-validation-blindspot-audit/spec.md`

## Summary

Add local SAST (Static Application Security Testing) to detect OWASP vulnerability patterns before code leaves the developer's machine. Current blind spot: 3 HIGH-severity vulnerabilities (log injection, clear-text logging) were caught by remote CI (CodeQL) but passed all local validation. Fix involves adding Semgrep/Bandit to local validation, remediating existing vulnerabilities, and updating documentation.

## Technical Context

**Language/Version**: Python 3.13 (existing project standard)
**Primary Dependencies**: Semgrep (SAST), Bandit (Python security linter), pre-commit, Make
**Storage**: N/A (tooling configuration only)
**Testing**: pytest (existing), manual verification of SAST detection
**Target Platform**: Linux/macOS developer machines, GitHub Actions CI
**Project Type**: Single Python project with Terraform infrastructure
**Performance Goals**: Local SAST completes in <60 seconds
**Constraints**: Must detect patterns equivalent to CodeQL py/log-injection and py/clear-text-logging-sensitive-data
**Scale/Scope**: ~15k LOC Python codebase, 3 existing vulnerabilities to remediate

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

### Pre-Phase 0 Evaluation

| Gate | Constitution Section | Status | Notes |
|------|---------------------|--------|-------|
| Security scanning in CI | §3, §7 | ✅ PASS | Adding local SAST aligns with "SAST/secret scanning in CI" requirement |
| No bypass of validation | §8 Pipeline Bypass | ✅ PASS | Feature enforces validation, does not bypass |
| Implementation accompaniment | §7 | ✅ PASS | Tests will verify SAST detection works |
| GPG-signed commits | §8 | ✅ PASS | Standard practice |
| Feature branch workflow | §8 | ✅ PASS | Using 070-validation-blindspot-audit branch |

**GATE RESULT**: ✅ PASS - Proceed to Phase 0

## Project Structure

### Documentation (this feature)

```text
specs/070-validation-blindspot-audit/
├── plan.md              # This file
├── spec.md              # Feature specification
├── research.md          # Phase 0 output - SAST tool research
├── quickstart.md        # Phase 1 output - Getting started guide
├── methodology-violation-001.md  # Artifact for template repo overhaul
└── checklists/
    └── requirements.md  # Specification quality checklist
```

### Modified Files (repository root)

```text
# Configuration files to modify
.pre-commit-config.yaml      # Add Bandit + Semgrep hooks
Makefile                     # Add `make sast` target
pyproject.toml               # Add semgrep, bandit to dev dependencies

# Source files to remediate (3 vulnerabilities)
src/lambdas/shared/secrets.py     # Clear-text logging vulnerability
src/lambdas/dashboard/ohlc.py     # Log injection vulnerability (2 instances)

# Documentation to update
.specify/memory/constitution.md   # Add local SAST requirement
CLAUDE.md                         # Document SAST tooling
```

**Structure Decision**: Tooling/configuration feature - no new source directories. Modifies existing configs and remediates existing vulnerabilities.

## Complexity Tracking

> **No constitution violations. Feature is purely additive tooling.**

N/A - All gates passed. No complexity justification needed.

## Technical Approach

### Tool Selection Decision

Based on research (see research.md), the recommended approach is:

| Layer | Tool | Coverage | Execution Time |
|-------|------|----------|----------------|
| Pre-commit | Bandit | 30-40% CodeQL | 5-15s |
| Make validate | Semgrep | 70-85% CodeQL | 15-45s |
| CI (existing) | CodeQL | 100% | 120-300s |

**Rationale**: Two-tier local approach provides fast feedback (Bandit) with comprehensive coverage (Semgrep), while leaving heavy-weight analysis (CodeQL) to CI where it already runs.

### Integration Points

1. **Pre-commit hook**: Bandit for fast feedback on every commit
2. **Make target**: `make sast` runs Semgrep for comprehensive local scan
3. **Make validate**: Include `make sast` in standard validation
4. **Severity blocking**: HIGH/MEDIUM block commits; LOW reports only

### Vulnerability Remediation Strategy

The 3 existing vulnerabilities require code fixes:

1. **Clear-text logging**: Redact sensitive data before logging
2. **Log injection (2x)**: Sanitize user-controlled data before logging

Fixes must:
- Pass local SAST validation
- Pass CodeQL in CI (dismiss alerts as "fixed")
- Not break existing tests

## Post-Phase 1 Constitution Re-Check

| Gate | Constitution Section | Status | Notes |
|------|---------------------|--------|-------|
| Security scanning enhanced | §3, §7 | ✅ PASS | Design adds local SAST layer |
| Testing requirements | §7 | ✅ PASS | Manual verification + SAST self-test in quickstart |
| No new complexity | General | ✅ PASS | Adds tooling, no new abstractions |
| Documentation updated | §6, CLAUDE.md | ✅ PASS | Agent context script updated |

**GATE RESULT**: ✅ PASS - Ready for `/speckit.tasks`

## Artifacts Generated

| Artifact | Status | Purpose |
|----------|--------|---------|
| plan.md | ✅ Complete | Implementation design |
| research.md | ✅ Complete | Tool selection rationale |
| quickstart.md | ✅ Complete | Developer setup guide |
| methodology-violation-001.md | ✅ Complete | Template overhaul artifacts |
| CLAUDE.md | ✅ Updated | Agent context |

## Next Steps

1. Run `/speckit.tasks` to generate implementation tasks
2. Create feature branch `070-validation-blindspot-audit`
3. Implement tasks in order
4. Port methodology-violation-001.md findings to template repo
