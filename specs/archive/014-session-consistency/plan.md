# Implementation Plan: Multi-User Session Consistency

**Branch**: `014-session-consistency` | **Date**: 2025-12-01 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `/specs/014-session-consistency/spec.md`

## Summary

Fix critical authentication race conditions and session consistency issues that prevent reliable multi-user operation. The dashboard frontend cannot display data because it lacks automatic anonymous session creation, magic link tokens can be verified concurrently causing duplicate accounts, and user creation has race conditions. This implementation adds: (1) hybrid auth headers accepting both `X-User-ID` and `Authorization: Bearer`, (2) automatic anonymous session on app load, (3) atomic token verification with DynamoDB conditional writes, (4) email uniqueness via GSI with conditional writes, (5) tombstone-based idempotent account merge, and (6) server-side session revocation integrated with andon cord system.

## Technical Context

**Language/Version**: Python 3.13 (backend), TypeScript 5 (frontend)
**Primary Dependencies**: FastAPI 0.121.3, boto3, pydantic, aws-lambda-powertools (backend); React 18, Next.js 14.2.21, Zustand 5.0.8, React Query 5.90.11 (frontend)
**Storage**: DynamoDB (single-table design with GSIs for email lookup)
**Testing**: pytest + pytest-asyncio + moto + responses (backend unit); vitest (frontend); pytest + httpx (E2E against preprod AWS)
**Target Platform**: AWS Lambda (backend), Browser (frontend)
**Project Type**: Web application (backend + frontend)
**Performance Goals**: Session creation <500ms p90, email lookup <100ms (via GSI), 100 concurrent auth requests without race failures
**Constraints**: 30-day anonymous session TTL, 1-hour magic link expiry, 80% test coverage minimum
**Scale/Scope**: 10,000+ users, 100 concurrent auth operations, 5 concurrent tabs per user

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Gate | Status | Evidence |
|------|--------|----------|
| **Security & Access Control (§3)** | ✅ PASS | All auth endpoints require authentication. Token validation uses HMAC-SHA256. No secrets in source control. |
| **SQL/NoSQL Injection Prevention (§3)** | ✅ PASS | All DynamoDB operations use ExpressionAttributeNames/Values. Conditional writes use parameterized expressions. |
| **Parameterized Queries (§3)** | ✅ PASS | DynamoDB conditional writes use `attribute_not_exists(email)` with parameter binding, not string interpolation. |
| **Deployment Requirements (§5)** | ✅ PASS | Serverless Lambda architecture via Terraform. Uses SNS/SQS for decoupling per constitution. |
| **Testing Environment Matrix (§7)** | ✅ PASS | Unit tests use moto for AWS mocking. E2E tests run against real preprod AWS. External APIs mocked. |
| **Implementation Accompaniment Rule (§7)** | ✅ PASS | All FRs mapped to specific test files. Race condition tests use pytest-asyncio. 80% coverage enforced. |
| **Pre-Push Requirements (§8)** | ✅ PASS | Code linted (ruff), formatted (black), GPG-signed commits, feature branch workflow. |
| **Pipeline Bypass Prohibition (§8)** | ✅ PASS | No bypass mechanisms. All PRs require passing CI checks before merge. |

**Pre-Design Validation**: All gates pass. Proceeding to Phase 0 research.

## Project Structure

### Documentation (this feature)

```text
specs/014-session-consistency/
├── spec.md              # Feature specification (completed)
├── plan.md              # This file (/speckit.plan command output)
├── research.md          # Phase 0 output (/speckit.plan command)
├── data-model.md        # Phase 1 output (/speckit.plan command)
├── quickstart.md        # Phase 1 output (/speckit.plan command)
├── contracts/           # Phase 1 output (/speckit.plan command)
│   └── session-api-v2.yaml  # OpenAPI schema for session endpoints
├── checklists/
│   └── requirements.md  # Quality checklist (completed)
└── tasks.md             # Phase 2 output (/speckit.tasks command)
```

### Source Code (repository root)

```text
# Backend (Python 3.13 + FastAPI)
src/lambdas/
├── dashboard/
│   ├── auth.py                    # Auth service (modify: atomic verification, hybrid headers)
│   ├── router_v2.py               # API router (modify: accept both header types)
│   └── quota.py                   # Quota service (reference: conditional write patterns)
├── shared/
│   ├── models/
│   │   ├── user.py                # User model (modify: add revoked field, email GSI)
│   │   └── magic_link_token.py    # Token model (modify: atomic verification fields)
│   ├── auth/
│   │   ├── cognito.py             # Cognito integration (reference only)
│   │   └── merge.py               # Account merge (modify: tombstone + idempotency)
│   └── middleware/
│       └── auth_middleware.py     # New: hybrid header extraction middleware

# Frontend (TypeScript 5 + React 18)
frontend/src/
├── stores/
│   └── auth-store.ts              # Auth state (modify: auto-create session on mount)
├── lib/api/
│   ├── client.ts                  # API client (modify: support both header formats)
│   └── auth.ts                    # Auth API (reference only)
├── hooks/
│   └── use-session-init.ts        # New: React hook for session initialization
└── components/
    └── providers/
        └── session-provider.tsx   # New: Provider wrapping app for session init

# Tests
tests/
├── unit/lambdas/shared/auth/
│   ├── test_session_consistency.py      # New: FR-001, FR-002, FR-003
│   ├── test_atomic_token_verification.py # New: FR-004, FR-005, FR-006
│   ├── test_email_uniqueness.py         # New: FR-007, FR-008, FR-009
│   └── test_merge_idempotency.py        # New: FR-013, FR-014, FR-015
├── integration/
│   └── test_session_race_conditions.py  # New: Concurrent operation tests
├── contract/
│   └── test_session_api_v2.py           # New: API schema validation
└── e2e/
    └── test_session_consistency_preprod.py # New: Real AWS validation

# Infrastructure (Terraform)
infrastructure/terraform/
├── modules/
│   ├── dynamodb/
│   │   └── main.tf                # Modify: add email GSI
│   └── lambda/
│       └── main.tf                # Reference only
└── main.tf                        # Root module
```

**Structure Decision**: Web application structure with Python backend in `src/lambdas/` and TypeScript frontend in `frontend/src/`. Tests follow pyramid structure in `tests/` with unit, integration, contract, and e2e directories.

## Complexity Tracking

> **Fill ONLY if Constitution Check has violations that must be justified**

No violations. All design decisions align with existing patterns:
- DynamoDB conditional writes already used in quota system
- Zustand persistence already implemented in auth store
- pytest-asyncio compatible with existing test infrastructure
- GSI pattern documented in constitution (§5 DynamoDB patterns)

## Constitution Check (Post-Design)

*Re-validation after Phase 1 design completion.*

| Gate | Status | Evidence |
|------|--------|----------|
| **Security & Access Control (§3)** | ✅ PASS | API contracts require auth. Session revocation adds security layer. |
| **SQL/NoSQL Injection Prevention (§3)** | ✅ PASS | All DynamoDB patterns in data-model.md use parameterized expressions. |
| **Conditional Writes (§5)** | ✅ PASS | Atomic token verification and email uniqueness use `ConditionExpression`. |
| **Testing Environment Matrix (§7)** | ✅ PASS | Test structure in quickstart.md follows pyramid. Race tests use asyncio. |
| **Implementation Accompaniment (§7)** | ✅ PASS | Every FR has mapped test file. 80% coverage required. |
| **Idempotency (§5)** | ✅ PASS | Merge operation uses tombstone markers for retry safety. |
| **Observability (§6)** | ✅ PASS | X-Ray tracing referenced. Error codes documented in contracts. |

**Post-Design Validation**: All gates pass. Ready for `/speckit.tasks`.

## Generated Artifacts

| Artifact | Path | Status |
|----------|------|--------|
| Research | `specs/014-session-consistency/research.md` | ✅ Complete |
| Data Model | `specs/014-session-consistency/data-model.md` | ✅ Complete |
| API Contracts | `specs/014-session-consistency/contracts/session-api-v2.yaml` | ✅ Complete |
| Quickstart | `specs/014-session-consistency/quickstart.md` | ✅ Complete |

## Next Steps

Run `/speckit.tasks` to generate implementation tasks from this plan.
