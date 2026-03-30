# Plan: 1278-pydantic-dev-pin

## Implementation Strategy

Single-file edit. Add 2 lines to `requirements-dev.txt`.

## Change Detail

### File: `requirements-dev.txt`

**Location**: After line 17 (`-r requirements.txt`), before line 19 (`# Testing Framework`)

**Add**:
```
# Override pydantic version from requirements.txt for moto compatibility
pydantic==2.12.4  # pinned: moto[all]==5.1.22 requires pydantic<=2.12.4
```

### Resulting structure (lines 16-22):
```
# Include production dependencies
-r requirements.txt

# Override pydantic version from requirements.txt for moto compatibility
pydantic==2.12.4  # pinned: moto[all]==5.1.22 requires pydantic<=2.12.4

# Testing Framework
pytest==9.0.2           # Compatible with pytest-asyncio 1.3.0
```

## Verification Plan

1. `pip install --dry-run -r requirements-dev.txt` — must resolve without conflict
2. `pip install --dry-run -r requirements-ci.txt` — must still resolve
3. `pip install --dry-run -r requirements.txt` — must still install pydantic 2.12.5
4. Visual diff review — only 2 lines added

## Dependencies
- None. Zero code changes.

## Estimated Effort
- Implementation: < 1 minute
- Verification: < 5 minutes
