# Implementation Plan: Email-to-OAuth Link (Flow 4)

**Branch**: `1182-email-to-oauth-link` | **Date**: 2026-01-09 | **Spec**: [spec.md](spec.md)
**Input**: Feature specification from `/specs/1182-email-to-oauth-link/spec.md`

## Summary

Implement Federation Flow 4 allowing OAuth-authenticated users to add email as an additional authentication method via magic link verification. This requires two new functions: `link_email_to_oauth_user()` to initiate email linking and store pending state, and `complete_email_link()` to verify the magic link and add email to linked_providers.

## Technical Context

**Language/Version**: Python 3.13
**Primary Dependencies**: FastAPI 0.127.0, boto3 1.42.17, pydantic 2.12.5, PyJWT 2.10.1, aws-xray-sdk 2.15.0
**Storage**: DynamoDB with composite keys (PK/SK pattern), GSI by_email for O(1) lookups
**Testing**: pytest 7.4.3+ with moto for AWS mocking, 80% coverage requirement
**Target Platform**: AWS Lambda with Mangum ASGI adapter
**Project Type**: Web application (backend Lambda + frontend Next.js)
**Performance Goals**: P90 ≤ 500ms for API endpoints
**Constraints**: Atomic DynamoDB operations for race condition prevention, magic link tokens with TTL
**Scale/Scope**: Existing user base with federation fields, adding new auth flow direction

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Gate | Status | Notes |
|------|--------|-------|
| Parameterized queries | ✅ PASS | DynamoDB uses ExpressionAttributeValues |
| Secrets management | ✅ PASS | Magic link secrets in Secrets Manager |
| TLS in transit | ✅ PASS | HTTPS enforced via API Gateway |
| Unit tests required | ✅ PASS | Will add tests for new functions |
| Deterministic time in tests | ✅ PASS | Will use freezegun for expiry tests |
| No pipeline bypass | ✅ PASS | Standard PR workflow |
| GPG signed commits | ✅ PASS | Required by pre-commit |

## Project Structure

### Documentation (this feature)

```text
specs/1182-email-to-oauth-link/
├── spec.md              # Feature specification
├── plan.md              # This file
├── research.md          # Phase 0 output
├── data-model.md        # Phase 1 output
├── quickstart.md        # Phase 1 output
├── contracts/           # Phase 1 output
│   └── email-link-api.yaml
├── checklists/
│   └── requirements.md  # Specification checklist
└── tasks.md             # Phase 2 output (created by /speckit.tasks)
```

### Source Code (repository root)

```text
src/lambdas/
├── dashboard/
│   └── auth.py          # Add link_email_to_oauth_user(), complete_email_link()
└── shared/
    └── models/
        └── user.py      # User model (already has pending_email, linked_providers)

tests/
├── unit/
│   └── dashboard/
│       └── test_email_to_oauth_link.py  # New test file for Flow 4
└── integration/
    └── test_email_linking.py            # Optional LocalStack integration
```

**Structure Decision**: Backend-only change. New functions added to existing auth.py module following established patterns. Frontend UI for "Add Email" button is out of scope (separate feature).

## Complexity Tracking

No constitution violations requiring justification. Implementation follows existing patterns in auth.py.
