# Implementation Plan: OAuth Auto-Link for Email-Verified Users

**Branch**: `1181-oauth-auto-link` | **Date**: 2026-01-09 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `/specs/1181-oauth-auto-link/spec.md`

## Summary

Implement Federation Flow 3: when an email-verified user (free:email) authenticates via OAuth, automatically link accounts if the OAuth provider is authoritative for their email domain (@gmail.com + Google), otherwise prompt for manual linking confirmation. This builds on Feature 1180's `get_user_by_provider_sub()` helper.

## Technical Context

**Language/Version**: Python 3.13
**Primary Dependencies**: FastAPI, pydantic, boto3 (DynamoDB)
**Storage**: DynamoDB (existing users table with `by_provider_sub` GSI from Feature 1180)
**Testing**: pytest with moto (unit), LocalStack (integration)
**Target Platform**: AWS Lambda
**Project Type**: Web application (Lambda backend + Next.js frontend)
**Performance Goals**: Auto-link completion <3 seconds, prompt display <500ms
**Constraints**: Must not change user role during linking
**Scale/Scope**: Supports existing user base with email verification

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Gate | Status | Notes |
|------|--------|-------|
| SQL injection prevention | PASS | Uses DynamoDB with ExpressionAttributeValues |
| Authentication required | PASS | OAuth callback requires valid session |
| TLS enforced | PASS | All API calls via HTTPS |
| Secrets management | PASS | OAuth secrets in Secrets Manager |
| Unit test accompaniment | REQUIRED | All new functions need tests |
| Deterministic time handling | REQUIRED | Use fixed dates in tests |

## Project Structure

### Documentation (this feature)

```text
specs/1181-oauth-auto-link/
├── plan.md              # This file
├── research.md          # Phase 0 output
├── data-model.md        # Phase 1 output
├── quickstart.md        # Phase 1 output
├── contracts/           # Phase 1 output
└── tasks.md             # Phase 2 output
```

### Source Code (repository root)

```text
src/lambdas/dashboard/
├── auth.py              # Add can_auto_link_oauth(), link_oauth_to_existing()
└── oauth_callback.py    # Update to use Flow 3 logic

frontend/src/
├── components/auth/
│   └── LinkAccountPrompt.tsx  # Manual linking confirmation dialog
└── lib/api/
    └── auth.ts          # API client for linking endpoints

tests/
├── unit/dashboard/
│   └── test_oauth_auto_link.py  # Unit tests for new functions
└── integration/
    └── test_flow3_oauth_link.py # Integration tests
```

**Structure Decision**: Backend-only changes in `src/lambdas/dashboard/auth.py` with frontend prompt component. Follows existing patterns from Feature 1180.

## Complexity Tracking

No constitution violations requiring justification. Feature adds two functions to existing auth.py and one frontend component.
