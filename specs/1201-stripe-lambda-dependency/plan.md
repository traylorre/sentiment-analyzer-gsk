# Implementation Plan: Add Stripe Dependency to Dashboard Lambda

**Branch**: `1201-stripe-lambda-dependency` | **Date**: 2026-01-12 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `/specs/1201-stripe-lambda-dependency/spec.md`

## Summary

Add the `stripe` Python package to the Dashboard Lambda's requirements.txt to resolve the ModuleNotFoundError blocking production deployments.

## Technical Context

**Language/Version**: Python 3.13 (existing Lambda runtime)
**Primary Dependencies**: stripe>=11.4.1,<12.0.0 (matches root requirements.txt)
**Testing**: CI/CD smoke test (import verification)
**Constraints**: Must not conflict with existing Lambda dependencies
**Scale/Scope**: Single file change (1 line)

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Gate | Status | Notes |
|------|--------|-------|
| Secrets stored in managed service | N/A | No secrets involved - dependency only |
| No secrets in source control | N/A | No secrets involved |
| TLS in transit | N/A | No network changes |
| Auth required for management | N/A | No auth changes |
| Implementation accompaniment (tests) | PASS | CI smoke test verifies imports |
| Pre-push requirements | PASS | Normal PR workflow |
| No pipeline bypass | PASS | Normal PR workflow |

**Post-Design Re-check**: All gates pass. No violations.

## Project Structure

```text
src/lambdas/dashboard/
├── requirements.txt          # UPDATE: Add stripe>=11.4.1,<12.0.0
├── Dockerfile               # No change - already installs from requirements.txt
└── ...

specs/1201-stripe-lambda-dependency/
├── spec.md                  # Feature specification
├── plan.md                  # This file
└── tasks.md                 # To be generated
```

## Implementation Phases

### Phase 1: Add Dependency

1. Update `src/lambdas/dashboard/requirements.txt`:
   - Add `stripe>=11.4.1,<12.0.0` with comment referencing the issue

**That's it.** No other changes required.

## Risk Assessment

| Risk | Mitigation |
|------|------------|
| Version conflict with other deps | Using same version as root requirements.txt (11.4.1) |
| Lambda package size increase | Stripe SDK is ~1MB - well within Lambda limits |
| CI smoke test format change | No change to smoke test - it already tests imports |

## Deliverables

1. Updated `src/lambdas/dashboard/requirements.txt` with stripe dependency
