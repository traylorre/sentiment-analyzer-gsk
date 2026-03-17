# Implementation Plan: E2E Test Coverage Expansion

**Branch**: `1223-e2e-test-coverage` | **Date**: 2026-03-16 | **Spec**: [spec.md](spec.md)
**Input**: Feature specification from `/specs/1223-e2e-test-coverage/spec.md`

## Summary

Expand E2E test coverage from basic dashboard interactions to full authentication flows (OAuth, magic link), alert CRUD, session lifecycle, account linking, and cross-browser compatibility. Uses Playwright route interception for OAuth mocking and DynamoDB direct query for magic link token extraction.

## Technical Context

**Language/Version**: TypeScript (Playwright tests), Python 3.13 (backend test utilities)
**Primary Dependencies**: Playwright 1.58+, pytest-playwright, boto3 (DynamoDB token query)
**Storage**: DynamoDB (read-only for token extraction in tests)
**Testing**: Playwright (frontend E2E), pytest (backend E2E harness)
**Target Platform**: GitHub Actions CI (ubuntu-latest)
**Project Type**: Web application (Amplify frontend + Lambda backend)
**Performance Goals**: All new tests complete within existing CI timeout budget (~10 min for E2E)
**Constraints**: Zero additional infrastructure cost; DynamoDB reads for token extraction only
**Scale/Scope**: ~6 new test files, ~40 new test cases, 3 browser engines

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Gate | Status | Notes |
|------|--------|-------|
| Testing: E2E uses real preprod AWS | PASS | Tests hit real Lambda Function URLs |
| Testing: mock external dependencies | PASS | OAuth providers mocked via route interception |
| Testing: synthetic test data | PASS | Unique prefixed identifiers per run |
| Testing: deterministic dates | PASS | Fixed dates in test fixtures |
| Security: no secrets in source | PASS | DynamoDB access via CI AWS credentials |
| Git: GPG-signed commits | PASS | Standard workflow |
| Pipeline: no bypass | PASS | Tests run within existing CI pipeline |

## Project Structure

### Documentation (this feature)

```text
specs/1223-e2e-test-coverage/
├── spec.md              # Feature specification
├── plan.md              # This file
├── research.md          # Phase 0: Playwright patterns research
├── data-model.md        # Phase 1: Test data model
├── quickstart.md        # Phase 1: Test execution guide
├── contracts/           # Phase 1: Test coverage matrix
└── tasks.md             # Phase 2 output (/speckit.tasks)
```

### Source Code (repository root)

```text
frontend/
├── playwright.config.ts         # MODIFY: Add Firefox + WebKit projects
├── tests/
│   ├── auth/
│   │   ├── oauth-flow.spec.ts   # NEW: US1 — OAuth login via route interception
│   │   └── magic-link.spec.ts   # NEW: US2 — Magic link with DynamoDB token query
│   ├── alerts/
│   │   └── crud.spec.ts         # NEW: US3 — Alert lifecycle
│   ├── session/
│   │   └── lifecycle.spec.ts    # NEW: US4 — Refresh, sign-out, eviction, expiry
│   ├── account/
│   │   └── linking.spec.ts      # NEW: US5 — Anonymous migration, multi-provider
│   └── helpers/
│       ├── auth-helper.ts       # NEW: Shared auth utilities (create session, mock OAuth)
│       └── dynamo-helper.ts     # NEW: DynamoDB token query for magic link extraction

tests/e2e/
├── conftest.py                  # MODIFY: Add DynamoDB token extraction fixture
└── test_session_consistency_preprod.py  # EXISTING: reference for session patterns
```

**Structure Decision**: New Playwright tests go in `frontend/tests/` organized by feature area. Python-side DynamoDB utilities go in `tests/e2e/conftest.py`. Cross-browser config added to existing `playwright.config.ts`.
