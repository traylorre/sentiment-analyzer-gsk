# Feature 1005: E2E Skip Rate Validator

## Problem Statement

The E2E test suite currently has a 24.7% skip rate (61 skipped out of 247 tests). This indicates TDD gone stale - tests were written for features that were never implemented. Without automated enforcement, skip rates can grow unchecked, hiding test debt.

## Root Cause Analysis

From Feature 1001 investigation:
- 70 NOT_IMPLEMENTED: Tests for endpoints that don't exist
- 19 CONFIG_UNAVAILABLE: Fixed in PR #435 (payload format bug)
- 4 RATE_LIMIT: Documented in PR #437
- 13 ENVIRONMENT: Legitimate constraints

## Solution

Create a methodology validator that:
1. Parses pytest output to extract pass/skip/fail counts
2. Calculates skip rate = skipped / (passed + skipped + failed)
3. Fails CI if skip rate exceeds configurable threshold (default 15%)
4. Integrates with existing validate-runner.py orchestrator

## Functional Requirements

### FR-001: Skip Rate Calculation
Validator parses pytest JSON output to extract test counts and calculates:
- `skip_rate = skipped / total_tests`
- Where `total_tests = passed + skipped + failed`

### FR-002: Threshold Enforcement
Default threshold: 15% (0.15)
- PASS: skip_rate <= threshold
- FAIL: skip_rate > threshold

### FR-003: CLI Interface
```bash
python -m src.validators.skip_rate --path /path/to/repo [--threshold 0.15]
```

### FR-004: Integration with Methodology Index
Add entry to `.specify/methodologies/index.yaml` with:
- verification_gate: pytest marker check
- validation_gate: skip rate threshold

### FR-005: Finding Details
On failure, emit finding with:
- Current skip rate (percentage)
- Threshold exceeded
- Top 5 files by skip count
- Remediation: "Reduce skip rate by implementing features or removing stale tests"

## Technical Design

### Validator Location
`src/validators/skip_rate.py` in terraform-gsk-template

### Finding IDs
- SKIP-001: Skip rate exceeds threshold (HIGH severity)
- SKIP-002: Cannot parse pytest output (ERROR)

### Dependencies
- Requires pytest JSON output (`pytest --json-report`)
- OR parses output from `scripts/audit-e2e-skips.py`

## Acceptance Criteria

1. Validator detects skip rate from pytest run
2. Fails when skip rate > 15%
3. Produces YAML output matching methodology schema
4. Slash command `/skip-rate-validate` works
5. Makefile target `make validate-skip-rate` works

## Out of Scope

- Automatic test removal (requires human review)
- Integration with pytest hooks (future enhancement)
- Per-file skip thresholds
