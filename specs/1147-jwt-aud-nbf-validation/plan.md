# Implementation Plan: JWT Audience and Not-Before Claim Validation

**Branch**: `1147-jwt-aud-nbf-validation` | **Date**: 2026-01-05 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `/specs/1147-jwt-aud-nbf-validation/spec.md`

## Summary

Add `aud` (audience) and `nbf` (not-before) JWT claim validation to `auth_middleware.py` to close CVSS 7.8 security vulnerabilities. Cross-service token replay and pre-generated token attacks are currently possible because only `exp`, `iss`, `sub`, and `iat` are validated. This feature extends the existing PyJWT validation with audience and not-before checks using the existing 60-second leeway pattern.

## Technical Context

**Language/Version**: Python 3.13
**Primary Dependencies**: PyJWT (existing), AWS Lambda, boto3
**Storage**: N/A (stateless validation)
**Testing**: pytest with moto for AWS mocking
**Target Platform**: AWS Lambda (Python 3.13 runtime)
**Project Type**: Web application (backend Lambda + frontend Next.js)
**Performance Goals**: <10ms validation overhead (current baseline)
**Constraints**: Must not break existing authenticated flows; 60-second clock skew tolerance
**Scale/Scope**: Backend-only change, security-critical path

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Gate | Status | Notes |
|------|--------|-------|
| Security & Access Control (§3) | ✅ PASS | Enhances security by adding claim validation |
| Testing (§7) | ✅ PASS | Unit tests required for all new validation logic |
| Git Workflow (§8) | ✅ PASS | Feature branch, GPG-signed commits |
| Implementation Accompaniment | ✅ PASS | Tests accompany implementation |
| No Pipeline Bypass | ✅ PASS | All changes go through normal PR flow |

**No Constitution violations.** This is a pure security enhancement.

## Project Structure

### Documentation (this feature)

```text
specs/1147-jwt-aud-nbf-validation/
├── plan.md              # This file
├── research.md          # Phase 0: PyJWT best practices research
├── data-model.md        # Phase 1: JWTConfig changes
├── quickstart.md        # Phase 1: Implementation guide
├── contracts/           # Phase 1: N/A (no API contract changes)
└── tasks.md             # Phase 2: Implementation tasks
```

### Source Code (repository root)

```text
src/lambdas/shared/middleware/
└── auth_middleware.py       # Primary change: validate_jwt() + JWTConfig

tests/unit/middleware/
└── test_jwt_validation.py   # Unit tests for aud/nbf validation

tests/e2e/
└── conftest.py              # Update create_test_jwt() to include aud/nbf
```

**Structure Decision**: Backend-only change in existing middleware. No new files needed.

## Complexity Tracking

> No Constitution violations - table not required.
