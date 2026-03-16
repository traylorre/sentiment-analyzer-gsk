# Implementation Plan: Auth Security Hardening

**Branch**: `1222-auth-security-hardening` | **Date**: 2026-03-16 | **Spec**: [spec.md](spec.md)
**Input**: Feature specification from `/specs/1222-auth-security-hardening/spec.md`

## Summary

Fix 4 critical authentication vulnerabilities: (1) add provider_sub uniqueness enforcement to prevent account takeover via duplicate OAuth linking, (2) add authorization checks to account merge endpoint, (3) enforce role-verification state machine at DynamoDB conditional write layer, (4) add PKCE to OAuth authorization flow for public Cognito client.

## Technical Context

**Language/Version**: Python 3.13 (existing project standard)
**Primary Dependencies**: boto3 (DynamoDB), pydantic (models), aws-lambda-powertools (routing/tracing), joserfc (JWT)
**Storage**: DynamoDB (`{env}-sentiment-users` table with `by_provider_sub`, `by_email`, `by_cognito_sub` GSIs)
**Testing**: pytest + moto (unit), Playwright (E2E - separate feature 1223)
**Target Platform**: AWS Lambda (serverless)
**Project Type**: Web application (Lambda backend + Amplify frontend)
**Performance Goals**: Negligible impact — adds 1 DynamoDB read per provider link operation (GSI query)
**Constraints**: All changes must be backward-compatible with existing sessions and linked accounts
**Scale/Scope**: ~4 files modified, ~200 lines changed, ~300 lines of new tests

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Gate | Status | Notes |
|------|--------|-------|
| Security: parameterized queries | PASS | All DynamoDB operations use ExpressionAttributeNames/Values |
| Security: secrets not in source | PASS | No secrets introduced |
| Testing: unit tests accompany code | PASS | New tests for all 4 vulnerability classes planned |
| Testing: deterministic dates | PASS | No date-dependent logic |
| Observability: structured logging | PASS | FR-011 requires audit logging with correlation IDs |
| Git: GPG-signed commits | PASS | Standard workflow |
| Pipeline: no bypass | PASS | Standard PR flow |

## Project Structure

### Documentation (this feature)

```text
specs/1222-auth-security-hardening/
├── spec.md              # Feature specification
├── plan.md              # This file
├── research.md          # Phase 0: code analysis findings
├── data-model.md        # Phase 1: entity changes
├── quickstart.md        # Phase 1: implementation guide
├── contracts/           # Phase 1: no new API endpoints (hardening existing)
└── tasks.md             # Phase 2 output (/speckit.tasks)
```

### Source Code (repository root)

```text
src/
├── lambdas/
│   ├── dashboard/
│   │   └── auth.py              # _link_provider(), link_accounts(), handle_oauth_callback()
│   └── shared/
│       ├── auth/
│       │   ├── cognito.py       # get_authorize_url(), exchange_code_for_tokens()
│       │   └── oauth_state.py   # store_oauth_state() — add code_verifier field
│       └── models/
│           └── user.py          # validate_role_verification_state()

tests/
├── unit/
│   ├── auth/
│   │   ├── test_provider_uniqueness.py    # NEW: FR-001, FR-002
│   │   ├── test_account_link_auth.py      # NEW: FR-003, FR-004
│   │   ├── test_verification_state.py     # NEW: FR-005, FR-006
│   │   └── test_pkce.py                   # NEW: FR-007, FR-008, FR-009
│   └── dashboard/
│       └── test_auth.py                   # EXISTING: extend with negative cases

scripts/
└── audit_duplicate_provider_subs.py       # NEW: FR-012 one-time audit script
```

**Structure Decision**: All changes modify existing files in the established Lambda handler architecture. No new modules or architectural changes. One new audit script added to `scripts/`.
