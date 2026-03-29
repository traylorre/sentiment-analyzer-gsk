# Quickstart: Bidirectional Validation for Target Repos

**Feature**: 055-target-bidirectional
**Date**: 2025-12-06

## Overview

This feature enables the BidirectionalValidator to validate spec-code alignment in target repositories (like sentiment-analyzer-gsk) that have specification files but no `make test-bidirectional` target.

## Usage

### Basic Usage

```bash
# From template repo, validate a target repo
/validate --validator bidirectional --repo /path/to/target-repo

# Or run all validators on target repo
/validate --repo /path/to/target-repo
```

### Expected Output

```yaml
validation:
  command: bidirectional
  repo: /path/to/target-repo
  repo_type: dependent
  status: PASS # or FAIL/WARN

findings:
  - id: BIDIR-001
    severity: HIGH
    file: specs/001-auth/spec.md
    message: "FR-003: System MUST encrypt passwords - no implementation found"
    remediation: "Add password encryption in src/auth/"
```

## How It Works

### 1. Intrinsic Detection

When a target repo lacks `make test-bidirectional`, the validator:

1. **Discovers specs**: Finds all `specs/*/spec.md` files
2. **Parses requirements**: Extracts FR-NNN requirements and acceptance scenarios
3. **Maps to code**: Matches feature names to source files in `src/`
4. **Compares semantically**: Uses Claude API for semantic comparison

### 2. Semantic Comparison

The validator uses semantic comparison, not string matching:

| Spec Says                | Code Has          | Result       |
| ------------------------ | ----------------- | ------------ |
| "users can authenticate" | `def login()`     | ✅ MATCH     |
| "data at rest encrypted" | `encrypted=true`  | ✅ MATCH     |
| "return 404 for missing" | No error handling | ❌ BIDIR-001 |

### 3. Graceful Degradation

If Claude API is unavailable:

| Tier       | Capability                                    |
| ---------- | --------------------------------------------- |
| Full (API) | Semantic comparison, gap classification       |
| Cached     | Uses previous API responses                   |
| Offline    | Testability checks, reference validation only |

## Target Repo Requirements

### Minimum (Intrinsic Detection)

No changes needed. Just have specs:

```
target-repo/
├── specs/
│   ├── 001-feature/
│   │   └── spec.md      # FR-NNN requirements
│   └── 002-another/
│       └── spec.md
└── src/
    └── ...              # Implementation code
```

### Optional (Thin Make Target - US2)

If you want custom validation behavior, add a thin make target (< 10 lines per SC-004):

```makefile
# In target repo Makefile
# Option 1: Custom threshold
test-bidirectional:
	python3 -c "from src.validators.bidirectional import *; print('Bidirectional OK')"

# Option 2: Delegate to template validator with custom args
test-bidirectional:
	cd /path/to/template && python3 -m src.validators.runner bidirectional $(PWD)

# Option 3: Simple pass-through (marks as validated)
test-bidirectional:
	@echo "Bidirectional validation handled by template"
```

When a thin make target exists:

1. The validator detects it via `make -n test-bidirectional`
2. Runs `make test-bidirectional` instead of intrinsic detection
3. Reports PASS/FAIL based on exit code

**Important**: The thin make target takes precedence over intrinsic detection. Remove it to use automatic spec-code comparison.

## Finding Types

| ID        | Severity | Meaning                                       |
| --------- | -------- | --------------------------------------------- |
| BIDIR-001 | HIGH     | Spec requirement without code implementation  |
| BIDIR-002 | MEDIUM   | Code functionality without spec documentation |
| BIDIR-003 | LOW      | Semantic drift (partial mismatch)             |
| BIDIR-004 | INFO     | Spec lacks testable acceptance criteria       |
| BIDIR-005 | HIGH     | Contradiction between spec sections           |

## Integration with /validate

The BidirectionalValidator is included in the default `/validate` run:

```bash
/validate --repo /path/to/target-repo
```

All 9 methodology validators run, including bidirectional.

## Troubleshooting

### "SKIP: no specs/\*/spec.md files found"

The target repo has no specification files. Create specs following the convention:

```bash
mkdir -p specs/001-feature
touch specs/001-feature/spec.md
```

### "SKIP: make test-bidirectional not available"

This is expected for target repos. The validator falls back to intrinsic detection. If you see this and the validator still SKIPs, check that specs exist.

### Low confidence matches

If requirements show < 70% confidence, the spec and code may use different terminology. Consider:

1. Updating spec to match code terminology
2. Adding explicit mapping comments in code
3. Adjusting threshold via make target

## Development

### Running Tests

```bash
# Unit tests
pytest tests/unit/test_bidirectional_*.py -v

# With fixtures
pytest tests/unit/test_bidirectional_*.py -v --fixtures tests/fixtures/bidirectional/
```

### Adding Test Fixtures

```bash
# Aligned spec-code pair
tests/fixtures/bidirectional/aligned/
├── spec.md       # Has FR-001: System MUST do X
└── module.py     # Has def do_x()

# Misaligned pair
tests/fixtures/bidirectional/misaligned/
├── spec.md       # Has FR-001: System MUST do Y
└── module.py     # Has def do_z()  (drift)
```
