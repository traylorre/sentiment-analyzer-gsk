# Quickstart: Auth Security Hardening (1222)

## Overview

This feature hardens 4 authentication vulnerabilities. All changes are in existing files — no new modules, infrastructure, or API endpoints.

## File Change Map

| File | Change | FR |
|------|--------|----|
| `src/lambdas/dashboard/auth.py` | Add GSI uniqueness check to `_link_provider()` | FR-001, FR-002 |
| `src/lambdas/dashboard/auth.py` | Add JWT sub verification to `link_accounts()` | FR-003, FR-004 |
| `src/lambdas/dashboard/auth.py` | Add ConditionExpression to `_mark_email_verified()` | FR-005, FR-006 |
| `src/lambdas/dashboard/auth.py` | Add ConditionExpression to `complete_email_link()` | FR-005, FR-006 |
| `src/lambdas/shared/auth/cognito.py` | Add `code_challenge` to `get_authorize_url()` | FR-007 |
| `src/lambdas/shared/auth/cognito.py` | Add `code_verifier` to `exchange_code_for_tokens()` | FR-009 |
| `src/lambdas/shared/auth/oauth_state.py` | Add `code_verifier` field to state storage/retrieval | FR-008 |
| `src/lambdas/dashboard/auth.py` | Pass `code_verifier` through `handle_oauth_callback()` | FR-008, FR-009 |
| `scripts/audit_duplicate_provider_subs.py` | NEW: Audit script for existing duplicate detection | FR-012 |

## Implementation Order

1. **Provider uniqueness** (FR-001, FR-002, FR-012) — highest risk, most impactful
2. **Account merge auth** (FR-003, FR-004) — simple check, high impact
3. **Verification state machine** (FR-005, FR-006) — conditional write additions
4. **PKCE** (FR-007, FR-008, FR-009) — touches multiple files but well-scoped

## Test Strategy

Each vulnerability class gets its own test file with both positive and negative cases:

- `test_provider_uniqueness.py`: Link success, duplicate rejection, race condition simulation
- `test_account_link_auth.py`: Valid merge, unauthorized merge rejection, unauthenticated rejection
- `test_verification_state.py`: Valid transition, bypass attempt, downgrade prevention
- `test_pkce.py`: URL contains challenge, exchange includes verifier, wrong verifier fails

All tests use moto for DynamoDB mocking (unit tests, per constitution).

## Risks

- **GSI eventual consistency**: The `by_provider_sub` GSI has a ~100ms consistency window. Two users linking the same provider sub within 100ms could both succeed. Mitigation: acceptable for this write pattern (extremely low probability). If needed, a TransactWriteItems approach can be added later.
- **Cognito PKCE support**: AWS Cognito supports PKCE natively. The `code_challenge_method=S256` is the only supported method. Plain method is not supported.
- **Backward compatibility**: Existing OAuth state records (without `code_verifier`) will be processed normally — the code_verifier field is optional during a transition period. New states always include it.
