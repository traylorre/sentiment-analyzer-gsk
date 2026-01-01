# Tasks: Session Initialization Timeout

**Feature**: 1112-session-init-timeout
**Date**: 2025-12-31
**Spec**: [spec.md](./spec.md) | **Plan**: [plan.md](./plan.md)

## Summary

| Metric | Value |
|--------|-------|
| Total Tasks | 12 |
| User Stories | 3 |
| Parallel Opportunities | 4 tasks |
| MVP Scope | Phase 1-3 (US1: Dashboard Loads) |

## Phase 1: Setup

**Goal**: Initialize constants and prepare foundation

- [x] T001 Add SESSION_INIT_TIMEOUT_MS constant (10000) in `frontend/src/lib/constants.ts`
- [x] T002 Add MAX_INIT_TIME_MS constant (15000) for documentation in `frontend/src/lib/constants.ts`

## Phase 2: Foundational (Blocking)

**Goal**: Extend API client with timeout support - required by all user stories

- [x] T003 Add `timeout?: number` to RequestOptions interface in `frontend/src/lib/api/client.ts`
- [x] T004 Add 'TIMEOUT' to ErrorCode union type in `frontend/src/lib/api/client.ts`
- [x] T005 Create AbortController and set AbortSignal.timeout() in apiClient function in `frontend/src/lib/api/client.ts`
- [x] T006 Handle AbortError and convert to ApiClientError with 'TIMEOUT' code in `frontend/src/lib/api/client.ts`

**Dependency**: T003 → T005 → T006 (sequential within file)

## Phase 3: User Story 1 - Dashboard Loads Within Reasonable Time (P1)

**Goal**: Users see meaningful content within 15 seconds, even if backend is slow/unreachable

**Independent Test Criteria**:
- Network offline → error state appears within 15 seconds
- Slow network (8s response) → session completes successfully
- Working network → dashboard content within 10 seconds

- [x] T007 [US1] Add timeout parameter to createAnonymousSession (default: SESSION_INIT_TIMEOUT_MS) in `frontend/src/lib/api/auth.ts`
- [x] T008 [US1] Verify AbortController properly cancels fetch request on timeout in `frontend/src/lib/api/client.ts`

**Requirements Covered**: FR-001, FR-004, FR-006
**Success Metrics**: SC-001, SC-002, SC-004

## Phase 4: User Story 2 - Graceful Error Recovery (P2)

**Goal**: Users see helpful error message with retry action instead of stuck loading screen

**Independent Test Criteria**:
- Session init fails → clear error message appears (no technical jargon)
- Error state shown → retry button visible and functional
- Network recovers → retry succeeds immediately

- [x] T009 [US2] Define user-friendly timeout error message constant in `frontend/src/lib/constants.ts`
- [x] T010 [US2] Verify error message propagates correctly through auth-store to UI in `frontend/src/stores/auth-store.ts`

**Requirements Covered**: FR-002, FR-003, FR-007
**Success Metrics**: SC-003, SC-005

**Note**: Retry mechanism already exists in use-session-init.ts - verify it works with timeout errors.

## Phase 5: User Story 3 - Session State Visibility (P3)

**Goal**: Users understand what app is doing during initialization

**Independent Test Criteria**:
- Init in progress > 5 seconds → loading indicator remains visible
- User sees clear feedback during wait

- [x] T011 [US3] Verify loading state remains visible during timeout wait in `frontend/src/hooks/use-session-init.ts`

**Note**: Existing isLoading/isInitializing flags should handle this - verify only.

## Phase 6: Polish & Verification

**Goal**: Ensure quality and backwards compatibility

- [ ] T012 Verify localStorage session restoration still works (FR-005) - manual test
- [ ] T013 Run existing frontend tests to confirm no regressions via `npm test` in `frontend/`

## Dependencies

```
Phase 1 (Setup)
    │
    ▼
Phase 2 (Foundational) ─── BLOCKS ALL USER STORIES
    │
    ├───► Phase 3 (US1: Dashboard Loads) ─── MVP COMPLETE
    │         │
    │         ▼
    ├───► Phase 4 (US2: Error Recovery)
    │         │
    │         ▼
    └───► Phase 5 (US3: State Visibility)
              │
              ▼
         Phase 6 (Polish)
```

## Parallel Execution

**Within Phase 1**: T001 and T002 can run in parallel [P]

**Within Phase 2**: T003 and T004 can run in parallel [P], then T005 → T006 sequential

**User Story Independence**: After Phase 2, US1/US2/US3 can theoretically run in parallel, but priority order (P1→P2→P3) is recommended for incremental value delivery.

## Implementation Strategy

### MVP (Recommended First Delivery)
- Phase 1 + Phase 2 + Phase 3 (US1)
- Delivers core timeout functionality
- Dashboard loads within 15 seconds guaranteed
- 8 tasks total

### Full Feature
- All phases including US2 (error recovery) and US3 (visibility)
- Complete error handling UX
- 13 tasks total

## Manual Testing Checklist

After implementation, verify:

- [ ] Network offline → error + retry within 15s
- [ ] Slow network (3G throttle) → success or timeout + retry
- [ ] Backend down → error + retry within 15s
- [ ] Valid localStorage session → instant dashboard (no API call)
- [ ] Expired localStorage session → API call with timeout
- [ ] Error message is user-friendly (no stack traces, error codes)
- [ ] Retry button works after timeout
- [ ] No orphaned connections after timeout (check DevTools Network tab)
