# Implementation Plan: OAuth-to-OAuth Link (Flow 5)

**Branch**: `1183-oauth-to-oauth-link` | **Date**: 2026-01-09 | **Spec**: [spec.md](spec.md)
**Input**: Feature specification from `/specs/1183-oauth-to-oauth-link/spec.md`

## Summary

Implement Federation Flow 5: when an existing OAuth user authenticates with a different OAuth provider, auto-link both accounts. This extends the existing `handle_oauth_callback()` to detect existing OAuth users and link new providers automatically.

## Technical Context

**Language/Version**: Python 3.13
**Primary Dependencies**: FastAPI 0.127.0, boto3 1.42.17, pydantic 2.12.5
**Storage**: DynamoDB with provider_sub GSI for collision detection
**Testing**: pytest 7.4.3+ with moto, 80% coverage requirement
**Target Platform**: AWS Lambda with Mangum ASGI adapter
**Project Type**: Web application (backend Lambda)
**Performance Goals**: P90 ≤ 500ms for OAuth callback handling
**Constraints**: Atomic operations for race condition prevention, GSI for O(1) lookups

## Constitution Check

| Gate | Status | Notes |
|------|--------|-------|
| Parameterized queries | ✅ PASS | DynamoDB uses ExpressionAttributeValues |
| Secrets management | ✅ PASS | OAuth secrets in Secrets Manager |
| TLS in transit | ✅ PASS | HTTPS enforced |
| Unit tests required | ✅ PASS | Will add tests for auto-link logic |
| No pipeline bypass | ✅ PASS | Standard PR workflow |

## Project Structure

### Source Code Changes

```text
src/lambdas/
├── dashboard/
│   └── auth.py          # Extend handle_oauth_callback() for Flow 5

tests/
├── unit/
│   └── dashboard/
│       └── test_oauth_to_oauth_link.py  # New test file for Flow 5
```

**Structure Decision**: Minimal change - extend existing handle_oauth_callback() function with Flow 5 detection logic.
