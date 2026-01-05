# Implementation Plan: Guard Mock Token Generation

**Branch**: `1128-guard-mock-tokens` | **Date**: 2026-01-05 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `/specs/1128-guard-mock-tokens/spec.md`

## Summary

Add environment guard to `_generate_tokens()` function in auth.py to prevent mock token generation in AWS Lambda environment. This is a critical security fix that blocks fake/predictable tokens from being issued in production while maintaining local development workflow.

## Technical Context

**Language/Version**: Python 3.13 (existing project standard)
**Primary Dependencies**: None new - uses stdlib `os` module (already imported)
**Storage**: N/A
**Testing**: pytest with moto mocks (unit), LocalStack (integration)
**Target Platform**: AWS Lambda (serverless)
**Project Type**: Web application (Lambda backend)
**Performance Goals**: Negligible latency impact (single env var lookup)
**Constraints**: Must not break local development workflow
**Scale/Scope**: Single function modification (~5 lines of code)

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Gate | Status | Notes |
|------|--------|-------|
| Security & Access Control (3) | PASS | Prevents authentication bypass in production |
| Preventing SQL injection | N/A | No DB changes |
| Testing & Validation (7) | PASS | Unit tests required per Implementation Accompaniment Rule |
| Git Workflow (8) | PASS | Feature branch, GPG-signed commits |
| Local SAST (10) | PASS | Will run `make validate` before push |

**No violations requiring justification.**

## Project Structure

### Documentation (this feature)

```text
specs/1128-guard-mock-tokens/
├── plan.md              # This file
├── research.md          # Phase 0 output (minimal - well-understood pattern)
├── checklists/
│   └── requirements.md  # Quality checklist
└── tasks.md             # Phase 2 output
```

### Source Code (repository root)

```text
src/lambdas/dashboard/
└── auth.py              # _generate_tokens() function at lines 1510-1529

tests/unit/lambdas/dashboard/
└── test_auth_guard.py   # New unit tests for environment guard
```

**Structure Decision**: Single file modification in existing backend Lambda module. No new directories or architectural changes needed.

## Complexity Tracking

> No violations requiring justification. This is a minimal, targeted security fix.

---

## Phase 0: Research

**Status**: Complete (pattern is well-understood)

The environment detection pattern using `AWS_LAMBDA_FUNCTION_NAME` is a canonical AWS best practice:
- AWS sets this variable automatically in all Lambda environments
- It contains the function name (e.g., `sentiment-analyzer-dashboard`)
- Absent in local development, present in Lambda (including LocalStack)

No additional research needed - this is a standard pattern documented in AWS Lambda environment variables documentation.

---

## Phase 1: Design

### Implementation Approach

1. Add guard check at the start of `_generate_tokens()` function
2. Check if `AWS_LAMBDA_FUNCTION_NAME` is set and non-empty
3. If true, raise `RuntimeError` with descriptive message
4. Log the blocked attempt at ERROR level
5. Existing mock token generation logic remains unchanged for local development

### Code Change (Pseudo-code)

```python
def _generate_tokens(user: User) -> tuple[dict, str]:
    """Generate mock tokens for testing.

    In production, tokens come from Cognito.
    SECURITY: Blocked in Lambda environment.
    """
    # SECURITY GUARD: Block mock tokens in Lambda environment
    if os.environ.get("AWS_LAMBDA_FUNCTION_NAME"):
        logger.error(
            "SECURITY: Mock token generation blocked in Lambda environment. "
            "Production must use Cognito tokens."
        )
        raise RuntimeError(
            "Mock token generation is disabled in Lambda environment. "
            "Use real Cognito tokens in production."
        )

    # Existing mock token generation (unchanged)
    refresh_token = f"mock_refresh_token_{user.user_id[:8]}"
    body_tokens = {
        "id_token": f"mock_id_token_{user.user_id[:8]}",
        "access_token": f"mock_access_token_{user.user_id[:8]}",
        "expires_in": 3600,
    }
    return body_tokens, refresh_token
```

### Test Strategy

Unit tests will cover:
1. **Lambda environment (blocked)**: Set `AWS_LAMBDA_FUNCTION_NAME`, verify RuntimeError
2. **Local environment (allowed)**: Unset variable, verify tokens generated
3. **Empty string (allowed)**: Set to empty string, verify tokens generated
4. **Error message content**: Verify message contains actionable guidance

### No API Contracts Needed

This feature does not introduce new APIs or change existing contracts. It only adds an internal guard to an existing function.

### No Data Model Changes

No new entities or data model modifications required.
