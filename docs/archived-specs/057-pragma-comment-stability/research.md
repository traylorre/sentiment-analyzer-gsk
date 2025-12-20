# Research: Formatter Pragma Comment Stability

**Feature**: 057-pragma-comment-stability
**Date**: 2025-12-09
**Status**: Complete

## Executive Summary

Research confirms a clear solution: **migrate from Black to Ruff formatter**. Ruff formatter explicitly excludes pragma comments from line length calculations, preventing the drift problem entirely. Additionally, Ruff's RUF100 rule detects unused `# noqa` directives, providing automatic validation.

## Research Findings

### 1. Formatter Behavior Analysis

#### Black Formatter
- **Behavior**: Black counts pragma comments toward line length
- **Problem**: When a line with `# noqa` or `# type:` exceeds 88 characters, Black may reflow the line, moving the pragma comment to an unintended position
- **Mitigation**: Black offers `# fmt: skip` or `# fmt: off/on` blocks to prevent reformatting, but this requires additional markers
- **Verdict**: Black is the cause of pragma comment drift

**Sources**:
- [Black Issue #195 - noqa comments get moved](https://github.com/psf/black/issues/195)
- [Black Issue #1713 - Line too long: Comments](https://github.com/psf/black/issues/1713)
- [Black Code Style Documentation](https://black.readthedocs.io/en/stable/the_black_code_style/current_style.html)

#### Ruff Formatter
- **Behavior**: Pragma comments (`# type`, `# noqa`, `# pyright`, `# pylint`, etc.) are **ignored** when computing line width
- **Result**: Lines can exceed the line length limit if the overage is due to pragma comments
- **Advantage**: Prevents Ruff from moving pragma comments, preserving their meaning and behavior
- **Deviation from Black**: This is intentional - Ruff aligns with Pyink rather than Black on this behavior

**Key Quote from Ruff Documentation**:
> "Pragma comments (`# type`, `# noqa`, `# pyright`, `# pylint`, etc.) are ignored when computing the width of a line. This prevents Ruff from moving pragma comments around, thereby modifying their meaning and behavior."

**Sources**:
- [Ruff Known Deviations from Black](https://docs.astral.sh/ruff/formatter/black/)
- [Ruff PR #7692 - Ignore overlong pragma comments](https://github.com/astral-sh/ruff/pull/7692)
- [Ruff Discussion #6670 - Pragma comment handling](https://github.com/astral-sh/ruff/discussions/6670)

#### Limitation: `# nosec` Support
- Ruff's pragma list is hardcoded and may not include `# nosec` (Bandit-specific)
- Users have requested custom pragma support: [Issue #11941](https://github.com/astral-sh/ruff/issues/11941)
- **Mitigation**: Test Ruff formatter behavior with `# nosec` comments specifically

### 2. Unused Pragma Detection

#### Ruff RUF100 Rule
- **Function**: Detects `# noqa` directives that don't suppress any active violation
- **Auto-fix**: Can automatically remove unused `# noqa` comments
- **Configuration**: `lint.external` setting for external rule codes (e.g., Flake8 rules not in Ruff)
- **Usage**: `ruff check --extend-select RUF100` flags unused directives

**Sources**:
- [Ruff RUF100 Documentation](https://docs.astral.sh/ruff/rules/unused-noqa/)
- [Ruff Issue #6122 - RUF100 edge cases](https://github.com/astral-sh/ruff/issues/6122)

#### Bandit `# nosec` Validation
- **Current State**: Bandit does NOT have built-in detection for unused `# nosec` comments
- **Audit Mode**: `--ignore-nosec` flag shows what would be flagged without suppressions
- **Feature Request**: [Issue #888](https://github.com/PyCQA/bandit/issues/888) proposes detecting `# nosec` without specific codes
- **Best Practice**: Always specify rule codes (`# nosec B324` not just `# nosec`)

**Sources**:
- [Bandit Configuration Documentation](https://bandit.readthedocs.io/en/latest/config.html)
- [Bandit nosec examples](https://github.com/PyCQA/bandit/blob/main/examples/nosec.py)

### 3. Industry Best Practices

| Practice | Description |
|----------|-------------|
| **Specific Rule Codes** | Always use `# noqa: E501` not blanket `# noqa` |
| **Justification Comments** | Add explanation: `# nosec B324 - MD5 for cache key, not security` |
| **Periodic Audit** | Run with `--ignore-nosec` / `RUF100` to find obsolete suppressions |
| **Formatter Selection** | Prefer formatters that preserve pragma comments (Ruff > Black) |
| **Version Pinning** | Pin formatter version to prevent behavior changes |

### 4. Migration Cost Assessment

#### Current State
- **Formatters**: Black 25.11.0 + ruff-format (both in pre-commit)
- **Observation**: Having both formatters is redundant and may cause conflicts

#### Migration Approach
1. Remove Black from pre-commit, keep only ruff-format
2. Run `ruff format --check` to preview changes
3. Run `ruff format` to apply (one-time bulk format)
4. Expected: Minimal changes since both formatters produce similar output

#### Blast Radius Estimation
- Python files: ~50 in src/, ~100 in tests/
- Expected changes: Mostly whitespace, some line wrapping differences
- Risk: Low - Ruff formatter is designed for Black compatibility

### 5. Pre-processing vs Native Support

| Approach | Pros | Cons |
|----------|------|------|
| **Native (Ruff)** | Built-in support, no extra tooling, maintained | Limited pragma list |
| **Pre-processing** | Custom pragma support | Additional complexity, maintenance burden |
| **`# fmt: skip`** | Works with Black | Requires modifying every pragma line |

**Recommendation**: Native Ruff support is preferred. For `# nosec` comments, test if Ruff formatter treats them as pragma comments. If not, use `# fmt: skip` selectively or request feature enhancement.

## Decisions

### Decision 1: Formatter Strategy
**Decision**: Migrate from Black to Ruff formatter exclusively
**Rationale**: Ruff formatter excludes pragma comments from line length, solving the root cause
**Alternatives Rejected**:
- Keep Black + add `# fmt: skip` everywhere (too invasive, requires code changes)
- Pre/post-processing scripts (maintenance burden, fragile)

### Decision 2: Pragma Validation Strategy
**Decision**: Enable RUF100 in Ruff config and run periodic Bandit audits
**Rationale**: RUF100 auto-detects unused `# noqa`; Bandit `--ignore-nosec` audits `# nosec`
**Implementation**:
- Add `RUF100` to Ruff's enabled rules
- Add `make audit-pragma` target for periodic `# nosec` validation

### Decision 3: Existing Comment Validation
**Decision**: Validate all 31 existing pragma comments before migration
**Rationale**: Must confirm existing comments are correctly placed before declaring success
**Implementation**:
- Run linters without suppressions to identify what each pragma suppresses
- Document each pragma's purpose and verify alignment

## Technical Recommendations

### pyproject.toml Changes
```toml
[tool.ruff]
line-length = 88
target-version = "py313"  # Upgrade from py312
select = [
    # ... existing rules ...
    "RUF100",  # Detect unused noqa directives
]

[tool.ruff.lint]
# Tell Ruff about external rule codes used by Bandit
external = ["B108", "B202", "B324"]
```

### pre-commit-config.yaml Changes
```yaml
# REMOVE Black formatter
# - repo: https://github.com/psf/black
#   rev: 25.11.0
#   hooks:
#     - id: black

# KEEP Ruff (already present)
- repo: https://github.com/astral-sh/ruff-pre-commit
  rev: v0.8.2  # Update to latest
  hooks:
    - id: ruff
      args: [--fix]
    - id: ruff-format
```

### New Make Targets
```makefile
audit-pragma:
	@echo "=== Checking for unused # noqa comments ==="
	ruff check --select RUF100 src/ tests/
	@echo "=== Checking # nosec usage (audit mode) ==="
	bandit -r src/ --ignore-nosec 2>/dev/null | grep -E "^(>>|Issue)" || true
```

## Risk Assessment

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| Ruff doesn't treat `# nosec` as pragma | Medium | Low | Test explicitly; use `# fmt: skip` if needed |
| Migration changes code semantics | Very Low | High | Diff review before commit |
| RUF100 false positives | Low | Low | Use `external` setting for Bandit codes |
| Team unfamiliarity with Ruff format | Low | Low | Same output as Black in 99% of cases |

## Next Steps

1. **Test Ruff formatter with `# nosec`**: Verify it's treated as pragma
2. **Run Ruff format preview**: `ruff format --check --diff src/`
3. **Validate existing pragmas**: Document each one's purpose
4. **Update pre-commit config**: Remove Black, update Ruff version
5. **Enable RUF100**: Add to pyproject.toml
6. **Create audit target**: Add `make audit-pragma`
