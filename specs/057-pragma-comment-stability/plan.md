# Implementation Plan: Formatter Pragma Comment Stability

**Branch**: `057-pragma-comment-stability` | **Date**: 2025-12-09 | **Spec**: [spec.md](spec.md)
**Input**: Feature specification from `/specs/057-pragma-comment-stability/spec.md`

## Summary

Ensure code formatters never break security and linting suppression comments (`# noqa`, `# nosec`, `# type:`). Research confirms that **Ruff formatter excludes pragma comments from line length calculations**, preventing drift. The solution is to migrate from Black to Ruff formatter exclusively and enable RUF100 for unused pragma detection.

## Technical Context

**Language/Version**: Python 3.13 (per pyproject.toml)
**Primary Dependencies**: Ruff ≥0.8.0 (formatter + linter), Bandit 1.7.10 (security)
**Storage**: N/A (configuration-only feature)
**Testing**: pytest (existing), manual validation of pragma placement
**Target Platform**: Linux (CI), macOS/Linux (developer machines)
**Project Type**: Configuration/tooling update
**Performance Goals**: Audit completes in <10 seconds for full codebase
**Constraints**: Zero functional code changes, backward compatible formatting
**Scale/Scope**: ~50 Python files in src/, ~100 in tests/, 31 pragma comments

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Requirement | Status | Notes |
|-------------|--------|-------|
| Local SAST (Amendment 1.6) | PASS | Feature adds RUF100 for unused pragma detection |
| Pre-push requirements (§8) | PASS | Uses existing pre-commit infrastructure |
| Testing accompaniment (§7) | PASS | Manual validation + RUF100 automated checks |
| No pipeline bypass (§8) | PASS | All changes go through normal PR process |
| GPG signing (§8) | PASS | Standard commit workflow |

**Post-Design Re-check**: All gates still pass. No constitution violations.

## Project Structure

### Documentation (this feature)

```text
specs/057-pragma-comment-stability/
├── plan.md              # This file
├── research.md          # Phase 0 research (complete)
├── checklists/
│   └── requirements.md  # Spec validation checklist
└── tasks.md             # Phase 2 output (next step)
```

### Files Modified (repository root)

```text
# Configuration files to update
pyproject.toml           # Update Ruff config, add RUF100
.pre-commit-config.yaml  # Remove Black, update Ruff version
Makefile                 # Add audit-pragma target

# No source code changes required
# Pragma comments remain unchanged - formatter behavior changes
```

**Structure Decision**: Configuration-only update. No new source directories. Existing project structure preserved.

## Implementation Strategy

### Phase 1: Validation & Preparation

1. **Test Ruff formatter with `# nosec`**
   - Create test file with `# nosec` on long line
   - Run `ruff format` and verify comment placement preserved
   - Document behavior (may need `# fmt: skip` for nosec)

2. **Audit existing pragma comments**
   - Run `ruff check --select RUF100` to find unused `# noqa`
   - Run `bandit -r src/ --ignore-nosec` to audit `# nosec`
   - Document each pragma's purpose and verify alignment

3. **Preview formatting changes**
   - Run `ruff format --check --diff src/ tests/`
   - Review any differences (should be minimal)

### Phase 2: Configuration Updates

1. **Update pyproject.toml**
   ```toml
   [tool.ruff]
   target-version = "py313"  # Update from py312

   [tool.ruff.lint]
   select = [
       # ... existing ...
       "RUF100",  # Unused noqa directive
   ]
   external = ["B108", "B202", "B324"]  # Bandit codes
   ```

2. **Update .pre-commit-config.yaml**
   - Remove Black formatter hook
   - Update Ruff to latest version (≥0.8.0)
   - Keep ruff-format hook

3. **Add Makefile target**
   ```makefile
   audit-pragma:
   	@echo "=== Unused noqa check ==="
   	ruff check --select RUF100 src/ tests/
   	@echo "=== nosec audit ==="
   	bandit -r src/ --ignore-nosec 2>/dev/null | grep -E "^(>>|Issue)" || true
   ```

### Phase 3: Migration & Verification

1. **Run formatter migration**
   - `ruff format src/ tests/`
   - Review changes (git diff)
   - Verify no semantic code changes

2. **Verify success criteria**
   - SC-001: Run formatter, verify pragma comments unchanged
   - SC-002: Run RUF100, verify all pragmas still needed
   - SC-003: Intentionally break pragma, verify detection
   - SC-004: Time audit target (<10 seconds)
   - SC-005: Document decision in this plan

3. **Update CI if needed**
   - Ensure CI uses same Ruff version as pre-commit
   - Remove any Black references in workflows

## Decision Record

### Decision: Migrate from Black to Ruff Formatter

**Context**: Black counts pragma comments toward line length, causing potential drift when lines are reformatted.

**Decision**: Remove Black, use Ruff formatter exclusively.

**Rationale**:
- Ruff explicitly excludes pragma comments from line length calculation
- Ruff is already installed (linter), reducing dependencies
- Black and Ruff produce nearly identical output (Ruff designed for compatibility)
- No functional code changes required

**Alternatives Considered**:
| Alternative | Rejected Because |
|-------------|------------------|
| Keep Black + `# fmt: skip` everywhere | Requires modifying every pragma line |
| Pre/post-processing scripts | Maintenance burden, fragile |
| Accept drift and fix manually | Doesn't meet SC-001 (zero drift) |

**Consequences**:
- Positive: Pragma comments automatically protected
- Positive: Reduces dependencies (one less formatter)
- Negative: Minor formatting differences possible (reviewed in migration)
- Negative: `# nosec` may not be recognized (test and document)

## Risk Register

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| Ruff doesn't treat `# nosec` as pragma | Medium | Low | Test explicitly; use `# fmt: skip` if needed |
| Migration introduces formatting diffs | Low | Low | Review diff, one-time bulk commit |
| Team unfamiliar with Ruff format | Low | Low | Output nearly identical to Black |
| RUF100 false positives | Low | Low | Use `external` setting for Bandit codes |

## Success Criteria Verification Plan

| Criterion | Verification Method |
|-----------|---------------------|
| SC-001: Zero drift | Add pragma to long line, format, verify placement |
| SC-002: 31 pragmas validated | Run RUF100 + bandit audit, document results |
| SC-003: 100% detection | Break 5 pragmas intentionally, verify CI fails |
| SC-004: <10s audit | Time `make audit-pragma` |
| SC-005: Decision documented | This plan (complete) |

## Complexity Tracking

> No constitution violations requiring justification.

| Item | Complexity | Notes |
|------|------------|-------|
| Configuration changes | Low | 3 files, ~20 lines changed |
| Migration risk | Low | Ruff designed for Black compatibility |
| Testing effort | Low | Manual verification + automated RUF100 |

## Next Steps

Run `/speckit.tasks` to generate the implementation task list.
