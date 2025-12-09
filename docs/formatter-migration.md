# Formatter Migration: Black to Ruff

**Feature**: 057-pragma-comment-stability
**Date**: 2025-12-09
**Status**: Complete

## Summary

This project migrated from Black formatter to Ruff formatter to solve pragma comment drift issues. Ruff formatter excludes pragma comments from line length calculations, preventing security suppressions from becoming misaligned.

## Why We Migrated

### The Problem

Black formatter counts pragma comments toward line length. When a line with `# noqa` or `# nosec` exceeds 88 characters, Black may reflow the line, causing the pragma to drift away from its target:

```python
# Before Black:
x = some_long_function_call(arg1, arg2)  # nosec B324 - MD5 for cache

# After Black (potential drift):
x = some_long_function_call(
    arg1, arg2
)  # nosec B324 - MD5 for cache  <- Now on wrong line!
```

### The Solution

Ruff formatter explicitly excludes pragma comments from line length calculations:

> "Pragma comments (`# type`, `# noqa`, `# pyright`, `# pylint`, etc.) are ignored when computing the width of a line."
> — [Ruff Documentation](https://docs.astral.sh/ruff/formatter/black/)

## What Changed

### Configuration Files

| File | Change |
|------|--------|
| `pyproject.toml` | Removed `[tool.black]` section, updated `[tool.ruff]` to use `[tool.ruff.lint]` sections |
| `.pre-commit-config.yaml` | Removed Black hook, updated Ruff from v0.1.6 to v0.8.4 |
| `Makefile` | Updated `fmt` and `fmt-check` targets to use Ruff only |

### New Features

- **RUF100 rule**: Automatically detects unused `# noqa` directives
- **`make audit-pragma`**: New Makefile target to audit all pragma comments
- **`external` setting**: Tells Ruff about Bandit-specific codes (B108, B202, B324)

### Formatting Differences

Ruff and Black produce nearly identical output with one notable difference:

```python
# Black style:
assert (
    condition
), "message"

# Ruff style:
assert condition, (
    "message"
)
```

This is purely cosmetic and has no semantic impact.

## Commands

### Format Code

```bash
# Format all Python files
ruff format src/ tests/

# Check without modifying
ruff format --check src/ tests/
```

### Audit Pragma Comments

```bash
# Run full pragma audit
make audit-pragma

# Check only for unused noqa
ruff check --select RUF100 src/ tests/
```

## For Developers

1. **No action required** - The migration is complete
2. **New pragma comments** will be preserved on long lines automatically
3. **Run `make fmt`** before committing (same as before)
4. **RUF100** will warn if you add an unnecessary `# noqa`

## Research Sources

- [Ruff Known Deviations from Black](https://docs.astral.sh/ruff/formatter/black/)
- [Black Issue #195 - noqa comments get moved](https://github.com/psf/black/issues/195)
- [Ruff PR #7692 - Ignore overlong pragma comments](https://github.com/astral-sh/ruff/pull/7692)
