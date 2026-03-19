# Tasks: Frontend Error Visibility

**Input**: Design documents from `/specs/1226-frontend-error-visibility/`
**Prerequisites**: plan.md, spec.md, research.md, data-model.md, quickstart.md

**Tests**: Unit tests included per constitution (Implementation Accompaniment Rule). Playwright E2E tests included for each user story's independent test criteria.

**Organization**: Tasks grouped by user story (US1, US2, US3) for independent implementation and testing.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (e.g., US1, US2, US3)
- Include exact file paths in descriptions

---

## Phase 1: Setup

**Purpose**: Shared infrastructure that all user stories depend on

- [x] T001 Create API health Zustand store with failure window tracking in `frontend/src/stores/api-health-store.ts` — State: `failures[]`, `isUnreachable`, `bannerDismissed`. Actions: `recordFailure()`, `recordSuccess()`, `dismissBanner()`. Sliding window: prune entries >60s old, threshold 3+ failures = unreachable. See data-model.md for state transitions.
- [x] T002 Create `useApiHealth` hook in `frontend/src/hooks/use-api-health.ts` — Wire `api-health-store` to React Query's `QueryCache` via `onError` and `onSuccess` callbacks. Import and call `recordFailure()`/`recordSuccess()` on every query result. Must not fire on cancelled queries.
- [x] T003 Wire `useApiHealth` hook into app providers in `frontend/src/app/providers.tsx` — Initialize the hook inside the `QueryClientProvider` so it runs on every page. Configure `QueryClient` with `queryCache: new QueryCache({ onError, onSuccess })` callbacks.

**Checkpoint**: Health state tracking is active. No UI yet, but the store correctly tracks failures and transitions between healthy/unreachable.

---

## Phase 2: Foundational — Structured Console Events

**Purpose**: Console event infrastructure that all user stories emit through

- [x] T004 Add `emitErrorEvent()` utility function in `frontend/src/lib/api/client.ts` — Function signature: `emitErrorEvent(event: string, details: Record<string, unknown>)`. Emits `console.warn({ event, timestamp: new Date().toISOString(), details })`. Used by all error state transitions (banner, search, auth).
- [x] T005 [P] Write unit test for `api-health-store` in `frontend/tests/unit/stores/api-health-store.test.ts` — Use `jest.useFakeTimers()` for sliding window assertions. Test: `recordFailure()` accumulates within window, prunes >60s entries, transitions to unreachable at threshold 3, `recordSuccess()` clears and recovers, `dismissBanner()` hides but doesn't recover, re-failure after recovery resets dismissed. Also verify stale errors clear on recovery (FR-007).
- [x] T005b [P] Write unit test for `useApiHealth` hook in `frontend/tests/unit/hooks/use-api-health.test.ts` — Test: hook calls `recordFailure()` when QueryCache fires onError, calls `recordSuccess()` when QueryCache fires onSuccess, does not fire on cancelled queries.
- [x] T006 [P] Write unit test for `emitErrorEvent` in `frontend/tests/unit/lib/emit-error-event.test.ts` — Test: emits console.warn with correct structure, includes ISO timestamp, includes event name and details.

**Checkpoint**: Foundation ready — health tracking works, console events emit, unit tests pass. User story implementation can begin.

---

## Phase 3: User Story 1 — Ticker Search Error States (Priority: P1) MVP

**Goal**: Ticker search dropdown shows distinct error state (warning + retry) vs empty results ("No tickers found")

**Independent Test**: Simulate API error on search endpoint → dropdown shows error message with retry. Simulate empty results → dropdown shows "No tickers found." Both visually distinct.

### Implementation for User Story 1

- [x] T007 [US1] Modify ticker search dropdown in `frontend/src/components/dashboard/ticker-input.tsx` — Add `isError` and `error` handling from the `useQuery` result. When `isError` is true: render warning icon + error message + retry button in the dropdown area. When `isError` is false and results are empty: render existing "No tickers found" message. When `isError` is false and results exist: render results (unchanged). For 429 status: show "Too many requests. Please wait a moment." Emit `emitErrorEvent('search_error_displayed', { errorCode, endpoint })` when error state renders.
- [x] T008 [US1] Write unit test for ticker search error states in `frontend/tests/unit/components/ticker-input-error.test.ts` — Test: renders error state when `useQuery` returns `isError: true`, renders "No tickers found" when results are empty, renders results when results exist, error clears on successful retry, 429 shows rate limit message.
- [x] T009 [US1] Write Playwright E2E test for search error visibility in `frontend/tests/e2e/error-visibility-search.spec.ts` — Use `page.route()` to intercept search API and return 500. Verify dropdown shows error message (not "No tickers found"). Verify console warning emitted. Remove route interception, type new query, verify results appear normally. Also test: intercept with HTML response (content-type text/html) and verify error state (not crash/parse error).

**Checkpoint**: US1 complete. Ticker search distinguishes errors from empty results. Unit and E2E tests pass.

---

## Phase 4: User Story 2 — Global API Health Banner (Priority: P1)

**Goal**: Persistent banner appears at top of dashboard after 3+ request failures in 60 seconds, auto-dismisses on recovery

**Independent Test**: Block API via Playwright route interception → trigger 3+ interactions → banner appears. Unblock → next successful request → banner dismisses.

### Implementation for User Story 2

- [x] T010 [US2] Create health banner component in `frontend/src/components/ui/api-health-banner.tsx` — Reads `isUnreachable` and `bannerDismissed` from `api-health-store`. When unreachable and not dismissed: renders fixed-position amber banner at top of page with message "We're having trouble connecting to the server. Some features may be unavailable." and dismiss (X) button. Emit `emitErrorEvent('api_health_banner_shown', { failureCount })` on mount. Emit `emitErrorEvent('api_health_banner_dismissed', {})` on dismiss click. Emit `emitErrorEvent('api_health_recovered', {})` when transitioning from unreachable to healthy.
- [x] T011 [US2] Mount health banner in root layout in `frontend/src/app/providers.tsx` — Add `<ApiHealthBanner />` above the main content area, inside the providers wrapper. Must render on all pages/routes.
- [x] T012 [US2] Ensure banner and chart error overlay don't duplicate (FR-008) — In `frontend/src/components/charts/price-sentiment-chart.tsx`, when the health banner is showing (`isUnreachable` from store), suppress the generic "connection" portion of chart error messages. Chart-specific errors (e.g., "No price data for LCID") still show.
- [x] T013 [P] [US2] Write unit test for health banner in `frontend/tests/unit/components/api-health-banner.test.ts` — Test: renders when isUnreachable=true, hidden when isUnreachable=false, hidden when bannerDismissed=true, dismiss button sets bannerDismissed, emits console events on show/dismiss/recover.
- [x] T014 [US2] Write Playwright E2E test for health banner in `frontend/tests/e2e/error-visibility-banner.spec.ts` — Use `page.route()` to block all API requests. Perform 3+ interactions (search, navigate). Verify banner appears. Capture console events and assert `api_health_banner_shown` emitted. Remove route block, perform action, verify banner dismisses, assert `api_health_recovered` emitted.

**Checkpoint**: US2 complete. Health banner appears on sustained failures, auto-recovers. No duplicate messaging with chart errors. Unit and E2E tests pass.

---

## Phase 5: User Story 3 — Auth Degradation Notifications (Priority: P2)

**Goal**: Non-blocking toast notification after 2+ consecutive session refresh failures, with "Sign in again" action

**Independent Test**: Simulate refresh failure twice → toast appears with message and action. Simulate successful refresh → counter resets.

### Implementation for User Story 3

- [x] T015 [US3] Add refresh failure tracking to auth store in `frontend/src/stores/auth-store.ts` — Add `refreshFailureCount: number` and `sessionDegraded: boolean` to state. In `refreshSession()`: on catch, increment `refreshFailureCount`; if count >= 2, set `sessionDegraded: true` and emit `emitErrorEvent('auth_degradation_warning', { failureCount })`. On success: reset count to 0 and `sessionDegraded: false`.
- [x] T016 [US3] Create auth degradation toast component in `frontend/src/components/ui/auth-degradation-toast.tsx` — Subscribe to `sessionDegraded` from auth store. On transition to `true`: show sonner toast with message "Your session may expire soon. Please save your work." and "Sign in again" action button. Action navigates to sign-in flow preserving current page for return. Only renders for authenticated users (not anonymous).
- [x] T017 [US3] Mount auth degradation toast in providers in `frontend/src/app/providers.tsx` — Add `<AuthDegradationToast />` inside providers wrapper.
- [x] T017b [US3] Add profile refresh failure logging to auth store in `frontend/src/stores/auth-store.ts` — In `refreshUserProfile()` catch block: log error via existing logger (FR-006). Do NOT surface to customer for single transient failures (preserve current behavior). Only log for observability.
- [x] T018 [P] [US3] Write unit test for auth refresh tracking in `frontend/tests/unit/stores/auth-store-degradation.test.ts` — Test: refreshFailureCount increments on failure, sessionDegraded=true at count 2, resets on success, does not fire for anonymous sessions, emits console event. Also verify profile refresh failures are logged but not surfaced (FR-006).
- [x] T018b [P] [US3] Write unit test for auth degradation toast in `frontend/tests/unit/components/auth-degradation-toast.test.ts` — Test: renders toast when sessionDegraded=true, hidden when sessionDegraded=false, hidden for anonymous users, "Sign in again" action present, emits console event.
- [x] T019 [US3] Write Playwright E2E test for auth degradation in `frontend/tests/e2e/error-visibility-auth.spec.ts` — Use `page.route()` to intercept refresh endpoint and return 401 twice. Verify toast appears. Verify "Sign in again" action is present. Capture console event `auth_degradation_warning`.

**Checkpoint**: US3 complete. Auth degradation surfaces proactively. Unit and E2E tests pass.

---

## Phase 6: Polish & Cross-Cutting Concerns

**Purpose**: Consistency, cleanup, and final validation

- [x] T020 Verify FR-007 (stale error clearing) across all components — Manual check: trigger search error, then successful search → error clears. Trigger banner, then recovery → banner clears. Trigger auth toast, then successful refresh → no re-trigger.
- [x] T021 Verify FR-009 (visual consistency) — Review all new UI elements against dark theme. Banner amber matches existing color palette. Error state in search uses warning styling consistent with chart error overlay.
- [x] T022 Run full Playwright suite against preprod to validate all 3 user stories end-to-end in `frontend/tests/e2e/error-visibility-*.spec.ts`
- [x] T023 Run quickstart.md validation — Follow quickstart.md steps exactly to verify setup, test commands, and architecture description are accurate.

---

## Dependencies & Execution Order

### Phase Dependencies

- **Phase 1 (Setup)**: No dependencies — start immediately
- **Phase 2 (Foundational)**: Depends on Phase 1 (T001-T003 complete)
- **Phase 3 (US1)**: Depends on Phase 2 (T004-T006 complete)
- **Phase 4 (US2)**: Depends on Phase 2 (T004-T006 complete) — can run in parallel with US1
- **Phase 5 (US3)**: Depends on Phase 2 (T004-T006 complete) — can run in parallel with US1/US2
- **Phase 6 (Polish)**: Depends on all user stories complete

### User Story Dependencies

- **US1 (Ticker Search)**: Independent — only needs api-health-store and emitErrorEvent
- **US2 (Health Banner)**: Independent — only needs api-health-store and emitErrorEvent
- **US3 (Auth Degradation)**: Independent — only needs emitErrorEvent (uses existing auth-store)

All three user stories can proceed in parallel after Phase 2.

### Within Each User Story

- Implementation tasks before tests (tests validate implementation)
- Store/hook changes before component changes
- Component creation before provider wiring

### Parallel Opportunities

- T005 and T006 can run in parallel (different test files)
- US1, US2, US3 can all start after Phase 2 (different files, no shared state mutations)
- T013 can run in parallel with T010-T012 (test file independent of implementation)
- T018 can run in parallel with T015-T017 (test file independent of implementation)

---

## Parallel Example: After Phase 2

```
# All three user stories can launch simultaneously:
Agent 1: T007 → T008 → T009  (US1: Ticker search errors)
Agent 2: T010 → T011 → T012 → T013 → T014  (US2: Health banner)
Agent 3: T015 → T016 → T017 → T018 → T019  (US3: Auth degradation)
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 1: Setup (T001-T003)
2. Complete Phase 2: Foundational (T004-T006)
3. Complete Phase 3: US1 — Ticker Search (T007-T009)
4. **STOP and VALIDATE**: Playwright test passes, search error distinct from empty
5. Deploy — this alone would have prevented Layer 13's 3-day silent outage

### Incremental Delivery

1. Setup + Foundational → Foundation ready
2. Add US1 (ticker search) → Deploy (MVP — catches the Layer 13 class of failures)
3. Add US2 (health banner) → Deploy (systemic outage visibility)
4. Add US3 (auth degradation) → Deploy (proactive session management)
5. Polish → Final validation

---

## Notes

- Total tasks: **27**
- Setup: 3 tasks (T001-T003)
- Foundation: 4 tasks (T004-T006, T005b)
- US1: 3 tasks (T007-T009)
- US2: 5 tasks (T010-T014)
- US3: 7 tasks (T015-T019, T017b, T018b)
- Polish: 4 tasks (T020-T023)
- Parallel opportunities: US1/US2/US3 all independent after Phase 2
- MVP scope: Phase 1 + 2 + 3 (10 tasks, delivers the Layer 13 prevention)
- Analysis remediations: +4 tasks (C1: FR-006 profile logging, C4: hook unit test, C5: toast unit test, C6: HTML edge case in E2E)
