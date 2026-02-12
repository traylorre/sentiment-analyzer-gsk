# Tasks: Security Headers and Auth Error Codes

**Feature**: 1190-security-headers-error-codes
**Date**: 2026-01-10
**Spec**: [spec.md](spec.md) | **Plan**: [plan.md](plan.md)
**Completed**: 2026-01-10

## Task Summary

| Phase | Description | Task Count | Status |
|-------|-------------|------------|--------|
| Phase 1 | Setup | 0 | N/A |
| Phase 2 | Foundational - Error Code Infrastructure | 2 | Done |
| Phase 3 | US1/US2 - Validate Security Headers (A22) | 2 | Done |
| Phase 4 | US3 - Backend Error Codes (A23) | 3 | Done |
| Phase 5 | US4 - Frontend Error Handlers | 3 | Done |
| Phase 6 | Polish | 1 | Done |
| **Total** | | **11** | **All Complete** |

## Dependencies

```
Phase 2 (Foundational)
    ↓
Phase 3 (Security Headers) ──┐
Phase 4 (Backend Errors) ────┼──→ Phase 6 (Polish)
Phase 5 (Frontend Errors) ───┘
```

**Note**: Phases 3, 4, 5 can run in parallel after Phase 2 completes.

---

## Phase 2: Foundational - Error Code Infrastructure

- [x] T001 Add AuthErrorCode enum with AUTH_013-AUTH_018 in `src/lambdas/shared/errors/auth_errors.py`
- [x] T002 Add AUTH_ERROR_MESSAGES and AUTH_ERROR_STATUS dictionaries in `src/lambdas/shared/errors/auth_errors.py`

---

## Phase 3: US1/US2 - Validate Security Headers (A22)

- [x] T003 [P] [US1] Security headers verified via existing tests in `tests/unit/shared/middleware/test_security_headers.py`
- [x] T004 [P] [US2] CloudFront HSTS max-age = 31536000 verified in `infrastructure/terraform/modules/cloudfront/main.tf:110`

---

## Phase 4: US3 - Backend Error Codes (A23)

- [x] T005 [US3] Create helper function `raise_auth_error(code: AuthErrorCode)` in `src/lambdas/shared/errors/auth_errors.py`
- [x] T006 [P] [US3] Add unit tests for all 6 error codes in `tests/unit/errors/test_auth_error_codes.py` (35 tests pass)
- [x] T007 [US3] Integrate AUTH_015 validation into `src/lambdas/dashboard/auth.py:2036`

---

## Phase 5: US4 - Frontend Error Handlers

- [x] T008 [P] [US4] Add AUTH_ERROR_HANDLERS map in `frontend/src/lib/api/errors.ts`
- [x] T009 [P] [US4] Add handler functions (clearTokensAndRedirect, showPasswordRequirements, etc.) in `frontend/src/lib/api/errors.ts`
- [x] T010 [US4] Add unit tests for error handlers in `frontend/tests/unit/lib/api/errors.test.ts` (25 tests pass)

---

## Phase 6: Polish

- [x] T011 Update spec-v2.md A22/A23 checklist items to [x] in `specs/1126-auth-httponly-migration/spec-v2.md:6865-6866`

---

## Implementation Notes

### Security Headers (A22)
- Already implemented in `security_headers.py`
- Verified via existing test suite
- CloudFront HSTS configured with max-age=31536000, includeSubDomains, preload

### Error Codes (A23)
- AUTH_015 integrated into OAuth callback for unknown provider validation
- AUTH_013, AUTH_016, AUTH_017, AUTH_018 documented for future integration points
- AUTH_017 will be integrated with Feature 1192 (Password auth endpoint)

### Test Coverage
- Backend: 35 tests for error codes
- Frontend: 25 tests for error handlers
- All tests passing
