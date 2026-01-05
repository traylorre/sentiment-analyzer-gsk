# Implementation Plan: Atomic Magic Link Token Consumption

**Branch**: `1129-atomic-magic-link` | **Date**: 2026-01-05 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `/specs/1129-atomic-magic-link/spec.md`

## Summary

Update router endpoint to use the existing atomic `verify_and_consume_token()` function instead of the vulnerable non-atomic `verify_magic_link()` function. This prevents race condition token reuse attacks by using DynamoDB conditional updates.

## Technical Context

**Language/Version**: Python 3.13 (existing project standard)
**Primary Dependencies**: boto3 (existing), DynamoDB conditional expressions
**Storage**: DynamoDB - magic_link_tokens table
**Testing**: pytest with moto mocks (unit), LocalStack (integration)
**Target Platform**: AWS Lambda (serverless)
**Project Type**: Web application (Lambda backend)
**Performance Goals**: Same latency as current (single DB roundtrip)
**Constraints**: Must use existing atomic function, minimal code change
**Scale/Scope**: Single router endpoint change + test updates

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Gate | Status | Notes |
|------|--------|-------|
| Security & Access Control (3) | PASS | Prevents race condition token replay attacks |
| Preventing SQL injection | N/A | Uses DynamoDB with parameterized expressions |
| Testing & Validation (7) | PASS | Unit tests required per Implementation Accompaniment Rule |
| Git Workflow (8) | PASS | Feature branch, GPG-signed commits |
| Local SAST (10) | PASS | Will run `make validate` before push |

**No violations requiring justification.**

## Project Structure

### Documentation (this feature)

```text
specs/1129-atomic-magic-link/
├── plan.md              # This file
├── research.md          # Phase 0 output
├── checklists/
│   └── requirements.md  # Quality checklist
└── tasks.md             # Phase 2 output
```

### Source Code (repository root)

```text
src/lambdas/dashboard/
├── auth.py              # verify_and_consume_token() at lines 1236-1360 (existing)
│                        # verify_magic_link() at lines 1364-1476 (deprecated)
└── router_v2.py         # Line 348 - needs to call atomic function

tests/unit/lambdas/dashboard/
└── test_atomic_magic_link_router.py   # New tests for router integration
```

**Structure Decision**: Single router file modification. The atomic function already exists and is tested.

## Complexity Tracking

> No violations requiring justification. This is a routing change to use existing safe code.

---

## Phase 0: Research

**Status**: Complete (existing code analysis)

### Key Findings

1. **Atomic function exists**: `verify_and_consume_token()` at auth.py:1236-1360
   - Uses `ConditionExpression="used = :false"`
   - Records `used_at` and `used_by_ip` audit fields
   - Raises `TokenAlreadyUsedError` on race condition
   - Raises `TokenExpiredError` on expired tokens

2. **Non-atomic function**: `verify_magic_link()` at auth.py:1364-1476
   - Uses separate get then update (vulnerable)
   - Router currently calls this at router_v2.py:348

3. **Error handling exists**:
   - `TokenAlreadyUsedError` → 409 Conflict
   - `TokenExpiredError` → 410 Gone

### Decision

Replace the router call from `verify_magic_link()` to `verify_and_consume_token()` with appropriate parameter mapping.

---

## Phase 1: Design

### Implementation Approach

1. Update router_v2.py:348 to call `verify_and_consume_token()` instead of `verify_magic_link()`
2. Ensure correct parameters are passed (token, client IP for audit)
3. Verify error handling maps correctly (409, 410 responses already exist)
4. Add integration test verifying atomic behavior

### Code Change (Pseudo-code)

```python
# router_v2.py line 348 - BEFORE
result = auth_service.verify_magic_link(token)

# router_v2.py line 348 - AFTER
result = auth_service.verify_and_consume_token(
    token=token,
    client_ip=request.client.host  # For audit trail
)
```

### Test Strategy

Unit tests will cover:
1. **Router calls atomic function**: Verify `verify_and_consume_token` is called
2. **409 response on race condition**: Mock `TokenAlreadyUsedError`, verify 409
3. **410 response on expiry**: Mock `TokenExpiredError`, verify 410
4. **Audit fields passed**: Verify client IP is passed for audit

### No New API Contracts

This feature does not change the API contract - same endpoints, same request/response format. Only the internal implementation changes to be atomic.

### No Data Model Changes

The `MagicLinkToken` model already has the required audit fields (`used_at`, `used_by_ip`).
