# Tasks: E2E Endpoint Implementation Roadmap

**Input**: Design documents from `/specs/079-e2e-endpoint-roadmap/`
**Prerequisites**: plan.md (required), spec.md (required), data-model.md

**Tests**: TDD approach is REQUIRED per spec.md. Existing E2E tests serve as blackbox specifications. Implementation follows RED-GREEN-REFACTOR: remove pytest.skip() → tests fail → implement → tests pass.

**Organization**: Tasks are grouped by user story (endpoint category) to enable independent implementation.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (US1=Alerts, US2=Market, US3=Tickers, US4=Notifications, US5=Preferences, US6=Quota, US7=MagicLink, US8=RateLimiting)
- Include exact file paths in descriptions

## Path Conventions

- **Single project**: `src/`, `tests/` at repository root
- E2E tests already exist in `tests/e2e/test_*.py` - use as blackbox specs

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Project structure for new endpoints - no new files needed, existing structure is sufficient

- [ ] T001 Verify existing src/models/ and src/routers/ structure supports new endpoints
- [ ] T002 [P] Review existing DynamoDB table schema for new entity access patterns in terraform/modules/dynamodb/

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Core infrastructure that MUST be complete before ANY user story can be implemented

**⚠️ CRITICAL**: No user story work can begin until this phase is complete

- [ ] T003 Add DynamoDB GSI for user alerts query pattern in terraform/modules/dynamodb/main.tf
- [ ] T004 [P] Add exchange_calendars to dependencies in pyproject.toml (for market status)
- [ ] T005 [P] Create base alert model skeleton in src/models/alert.py (empty classes from data-model.md)
- [ ] T006 [P] Create base market_status model skeleton in src/models/market_status.py
- [ ] T007 [P] Create base ticker model skeleton in src/models/ticker.py
- [ ] T008 [P] Create base notification model skeleton in src/models/notification.py
- [ ] T009 [P] Create base preferences model skeleton in src/models/preferences.py
- [ ] T010 [P] Create base quota model skeleton in src/models/quota.py
- [ ] T011 [P] Create base magic_link model skeleton in src/models/magic_link.py

**Checkpoint**: Foundation ready - user story implementation can now begin in parallel

---

## Phase 3: User Story 1 - Alerts Management (Priority: P1) 🎯 MVP

**Goal**: Users can create and manage sentiment/volatility alerts for their configurations

**Independent Test**: `pytest tests/e2e/test_alerts.py -v` - all 10 tests pass without skips

**Source Tests**: T068-T074 + 3 additional in `tests/e2e/test_alerts.py`

### TDD Step 1: RED - Remove Skips

- [ ] T012 [US1] Remove pytest.skip() from test_alert_create_sentiment_threshold in tests/e2e/test_alerts.py
- [ ] T013 [P] [US1] Remove pytest.skip() from test_alert_create_volatility_threshold in tests/e2e/test_alerts.py
- [ ] T014 [P] [US1] Remove pytest.skip() from test_alert_toggle_off in tests/e2e/test_alerts.py
- [ ] T015 [P] [US1] Remove pytest.skip() from test_alert_update_threshold in tests/e2e/test_alerts.py
- [ ] T016 [P] [US1] Remove pytest.skip() from test_alert_delete in tests/e2e/test_alerts.py
- [ ] T017 [P] [US1] Remove pytest.skip() from test_alert_max_limit_enforced in tests/e2e/test_alerts.py
- [ ] T018 [P] [US1] Remove pytest.skip() from test_alert_anonymous_forbidden in tests/e2e/test_alerts.py
- [ ] T019 [P] [US1] Remove pytest.skip() from test_alert_list in tests/e2e/test_alerts.py
- [ ] T020 [P] [US1] Remove pytest.skip() from test_alert_invalid_threshold in tests/e2e/test_alerts.py

### TDD Step 2: GREEN - Implement

- [ ] T021 [US1] Implement AlertCreate and Alert pydantic models in src/models/alert.py
- [ ] T022 [US1] Implement AlertService with DynamoDB CRUD in src/services/alert_service.py
- [ ] T023 [US1] Implement POST /api/v2/configurations/{id}/alerts endpoint in src/routers/alerts.py
- [ ] T024 [US1] Implement GET /api/v2/configurations/{id}/alerts endpoint in src/routers/alerts.py
- [ ] T025 [US1] Implement GET /api/v2/alerts/{id} endpoint in src/routers/alerts.py
- [ ] T026 [US1] Implement PATCH /api/v2/alerts/{id} endpoint in src/routers/alerts.py
- [ ] T027 [US1] Implement DELETE /api/v2/alerts/{id} endpoint in src/routers/alerts.py
- [ ] T028 [US1] Add alert limit validation (max alerts per config) in src/services/alert_service.py
- [ ] T029 [US1] Add threshold validation (sentiment: -1 to 1, volatility: positive) in src/models/alert.py
- [ ] T030 [US1] Register alerts router in main FastAPI app in src/main.py

**Checkpoint**: `pytest tests/e2e/test_alerts.py -v` - all tests pass

---

## Phase 4: User Story 2 - Market Status (Priority: P1)

**Goal**: Users can check market open/closed status and trading schedule

**Independent Test**: `pytest tests/e2e/test_market_status.py -v` - all 7 tests pass without skips

**Source Tests**: T105-T109 + 2 additional in `tests/e2e/test_market_status.py`

### TDD Step 1: RED - Remove Skips

- [ ] T031 [US2] Remove pytest.skip() from test_market_status_open in tests/e2e/test_market_status.py
- [ ] T032 [P] [US2] Remove pytest.skip() from test_market_status_closed in tests/e2e/test_market_status.py
- [ ] T033 [P] [US2] Remove pytest.skip() from test_market_status_holiday in tests/e2e/test_market_status.py
- [ ] T034 [P] [US2] Remove pytest.skip() from test_premarket_estimates_returned in tests/e2e/test_market_status.py
- [ ] T035 [P] [US2] Remove pytest.skip() from test_premarket_redirect_when_open in tests/e2e/test_market_status.py
- [ ] T036 [P] [US2] Remove pytest.skip() from test_market_schedule_endpoint in tests/e2e/test_market_status.py
- [ ] T037 [P] [US2] Remove pytest.skip() from test_market_status_includes_timestamp in tests/e2e/test_market_status.py

### TDD Step 2: GREEN - Implement

- [ ] T038 [US2] Implement MarketStatus and MarketSchedule pydantic models in src/models/market_status.py
- [ ] T039 [US2] Implement MarketService using exchange_calendars in src/services/market_service.py
- [ ] T040 [US2] Implement GET /api/v2/market/status endpoint in src/routers/market.py
- [ ] T041 [US2] Implement GET /api/v2/market/schedule endpoint in src/routers/market.py
- [ ] T042 [US2] Implement GET /api/v2/market/holidays endpoint in src/routers/market.py
- [ ] T043 [US2] Implement GET /api/v2/market/premarket endpoint in src/routers/market.py
- [ ] T044 [US2] Add caching for market status (TTL 60s) in src/services/market_service.py
- [ ] T045 [US2] Register market router in main FastAPI app in src/main.py

**Checkpoint**: `pytest tests/e2e/test_market_status.py -v` - all tests pass

---

## Phase 5: User Story 3 - Ticker Validation (Priority: P1)

**Goal**: Users can search and validate ticker symbols before adding to configurations

**Independent Test**: `pytest tests/e2e/test_ticker_validation.py -v` - all 8 tests pass without skips

**Source Tests**: T090-T094 + 3 additional in `tests/e2e/test_ticker_validation.py`

### TDD Step 1: RED - Remove Skips

- [ ] T046 [US3] Remove pytest.skip() from test_valid_ticker_returns_metadata in tests/e2e/test_ticker_validation.py
- [ ] T047 [P] [US3] Remove pytest.skip() from test_delisted_ticker_returns_successor in tests/e2e/test_ticker_validation.py
- [ ] T048 [P] [US3] Remove pytest.skip() from test_invalid_ticker_returns_invalid in tests/e2e/test_ticker_validation.py
- [ ] T049 [P] [US3] Remove pytest.skip() from test_ticker_search_returns_matches in tests/e2e/test_ticker_validation.py
- [ ] T050 [P] [US3] Remove pytest.skip() from test_ticker_search_empty_query in tests/e2e/test_ticker_validation.py
- [ ] T051 [P] [US3] Remove pytest.skip() from test_ticker_search_partial_match in tests/e2e/test_ticker_validation.py
- [ ] T052 [P] [US3] Remove pytest.skip() from test_ticker_validation_case_insensitive in tests/e2e/test_ticker_validation.py
- [ ] T053 [P] [US3] Remove pytest.skip() from test_ticker_batch_validation in tests/e2e/test_ticker_validation.py

### TDD Step 2: GREEN - Implement

- [ ] T054 [US3] Implement TickerInfo pydantic model in src/models/ticker.py
- [ ] T055 [US3] Implement TickerService using Tiingo API in src/services/ticker_service.py
- [ ] T056 [US3] Implement GET /api/v2/tickers/{symbol} endpoint in src/routers/tickers.py
- [ ] T057 [US3] Implement GET /api/v2/tickers/validate endpoint in src/routers/tickers.py
- [ ] T058 [US3] Implement POST /api/v2/tickers/validate (batch) endpoint in src/routers/tickers.py
- [ ] T059 [US3] Implement GET /api/v2/tickers/search endpoint in src/routers/tickers.py
- [ ] T060 [US3] Add ticker cache in DynamoDB (TTL 24h) in src/services/ticker_service.py
- [ ] T061 [US3] Add delisted ticker mapping (FB→META, TWTR→X) in src/services/ticker_service.py
- [ ] T062 [US3] Register tickers router in main FastAPI app in src/main.py

**Checkpoint**: `pytest tests/e2e/test_ticker_validation.py -v` - all tests pass

---

## Phase 6: User Story 4 - Notifications (Priority: P2)

**Goal**: Users can view and manage their notifications from alert triggers

**Independent Test**: `pytest tests/e2e/test_notifications.py -v` - all 8 tests pass without skips

**Source Tests**: T075-T079 + 3 additional in `tests/e2e/test_notifications.py`

### TDD Step 1: RED - Remove Skips

- [ ] T063 [US4] Remove pytest.skip() from test_alert_trigger_creates_notification in tests/e2e/test_notifications.py
- [ ] T064 [P] [US4] Remove pytest.skip() from test_notification_status_sent in tests/e2e/test_notifications.py
- [ ] T065 [P] [US4] Remove pytest.skip() from test_notification_list in tests/e2e/test_notifications.py
- [ ] T066 [P] [US4] Remove pytest.skip() from test_notification_detail_with_tracking in tests/e2e/test_notifications.py
- [ ] T067 [P] [US4] Remove pytest.skip() from test_notification_quota_exceeded in tests/e2e/test_notifications.py
- [ ] T068 [P] [US4] Remove pytest.skip() from test_notification_mark_read in tests/e2e/test_notifications.py
- [ ] T069 [P] [US4] Remove pytest.skip() from test_notification_unauthorized in tests/e2e/test_notifications.py

### TDD Step 2: GREEN - Implement

- [ ] T070 [US4] Implement Notification pydantic model in src/models/notification.py
- [ ] T071 [US4] Implement NotificationService with DynamoDB CRUD in src/services/notification_service.py
- [ ] T072 [US4] Implement GET /api/v2/notifications endpoint with pagination in src/routers/notifications.py
- [ ] T073 [US4] Implement GET /api/v2/notifications/{id} endpoint in src/routers/notifications.py
- [ ] T074 [US4] Implement PATCH /api/v2/notifications/{id} (mark read) in src/routers/notifications.py
- [ ] T075 [US4] Implement GET /api/v2/notifications/quota endpoint in src/routers/notifications.py
- [ ] T076 [US4] Add auth requirement (401 without token) in src/routers/notifications.py
- [ ] T077 [US4] Register notifications router in main FastAPI app in src/main.py

**Checkpoint**: `pytest tests/e2e/test_notifications.py -v` - all tests pass

---

## Phase 7: User Story 5 - Notification Preferences (Priority: P2)

**Goal**: Users can control how and when they receive notifications

**Independent Test**: `pytest tests/e2e/test_notification_preferences.py -v` - all 13 tests pass without skips

**Source Tests**: T139-T144 + 7 additional in `tests/e2e/test_notification_preferences.py`

### TDD Step 1: RED - Remove Skips

- [ ] T078 [US5] Remove pytest.skip() from test_get_preferences_returns_structure in tests/e2e/test_notification_preferences.py
- [ ] T079 [P] [US5] Remove pytest.skip() from test_get_preferences_unauthorized in tests/e2e/test_notification_preferences.py
- [ ] T080 [P] [US5] Remove pytest.skip() from test_update_preferences_email_enabled in tests/e2e/test_notification_preferences.py
- [ ] T081 [P] [US5] Remove pytest.skip() from test_update_preferences_persists in tests/e2e/test_notification_preferences.py
- [ ] T082 [P] [US5] Remove pytest.skip() from test_update_preferences_unauthorized in tests/e2e/test_notification_preferences.py
- [ ] T083 [P] [US5] Remove pytest.skip() from test_disable_all_notifications in tests/e2e/test_notification_preferences.py
- [ ] T084 [P] [US5] Remove pytest.skip() from test_disable_all_unauthorized in tests/e2e/test_notification_preferences.py
- [ ] T085 [P] [US5] Remove pytest.skip() from test_resubscribe_notifications in tests/e2e/test_notification_preferences.py
- [ ] T086 [P] [US5] Remove pytest.skip() from test_get_digest_settings in tests/e2e/test_notification_preferences.py
- [ ] T087 [P] [US5] Remove pytest.skip() from test_get_digest_settings_unauthorized in tests/e2e/test_notification_preferences.py
- [ ] T088 [P] [US5] Remove pytest.skip() from test_update_digest_settings in tests/e2e/test_notification_preferences.py
- [ ] T089 [P] [US5] Remove pytest.skip() from test_update_digest_settings_invalid_time in tests/e2e/test_notification_preferences.py
- [ ] T090 [P] [US5] Remove pytest.skip() from test_trigger_test_digest in tests/e2e/test_notification_preferences.py

### TDD Step 2: GREEN - Implement

- [ ] T091 [US5] Implement NotificationPreference and DigestSettings models in src/models/preferences.py
- [ ] T092 [US5] Implement PreferencesService with DynamoDB CRUD in src/services/preferences_service.py
- [ ] T093 [US5] Implement GET /api/v2/notifications/preferences endpoint in src/routers/notifications.py
- [ ] T094 [US5] Implement PATCH /api/v2/notifications/preferences endpoint in src/routers/notifications.py
- [ ] T095 [US5] Implement POST /api/v2/notifications/disable-all endpoint in src/routers/notifications.py
- [ ] T096 [US5] Implement POST /api/v2/notifications/resubscribe endpoint in src/routers/notifications.py
- [ ] T097 [US5] Implement GET /api/v2/notifications/digest endpoint in src/routers/notifications.py
- [ ] T098 [US5] Implement PATCH /api/v2/notifications/digest endpoint in src/routers/notifications.py
- [ ] T099 [US5] Implement POST /api/v2/notifications/digest/test endpoint in src/routers/notifications.py
- [ ] T100 [US5] Add time format validation (HH:MM) in src/models/preferences.py

**Checkpoint**: `pytest tests/e2e/test_notification_preferences.py -v` - all tests pass

---

## Phase 8: User Story 6 - Quota Management (Priority: P2)

**Goal**: Users can see their usage quotas for alerts

**Independent Test**: `pytest tests/e2e/test_quota.py -v` - all 8 tests pass without skips

**Source Tests**: T145 + 7 additional in `tests/e2e/test_quota.py`

### TDD Step 1: RED - Remove Skips

- [ ] T101 [US6] Remove pytest.skip() from test_quota_endpoint_returns_status in tests/e2e/test_quota.py
- [ ] T102 [P] [US6] Remove pytest.skip() from test_quota_values_are_consistent in tests/e2e/test_quota.py
- [ ] T103 [P] [US6] Remove pytest.skip() from test_quota_resets_at_is_valid_iso_datetime in tests/e2e/test_quota.py
- [ ] T104 [P] [US6] Remove pytest.skip() from test_quota_is_consistent_across_requests in tests/e2e/test_quota.py
- [ ] T105 [P] [US6] Remove pytest.skip() from test_quota_unauthorized_without_token in tests/e2e/test_quota.py
- [ ] T106 [P] [US6] Remove pytest.skip() from test_quota_fresh_user_has_zero_used in tests/e2e/test_quota.py
- [ ] T107 [P] [US6] Remove pytest.skip() from test_quota_limit_is_reasonable in tests/e2e/test_quota.py

### TDD Step 2: GREEN - Implement

- [ ] T108 [US6] Implement AlertQuota pydantic model with computed fields in src/models/quota.py
- [ ] T109 [US6] Implement QuotaService with DynamoDB tracking in src/services/quota_service.py
- [ ] T110 [US6] Implement GET /api/v2/alerts/quota endpoint in src/routers/alerts.py
- [ ] T111 [US6] Add quota reset logic (daily reset at midnight UTC) in src/services/quota_service.py
- [ ] T112 [US6] Integrate quota check with alert email sending in src/services/alert_service.py

**Checkpoint**: `pytest tests/e2e/test_quota.py -v` - all tests pass

---

## Phase 9: User Story 7 - Magic Link Authentication (Priority: P3)

**Goal**: Users can authenticate via email magic links

**Independent Test**: `pytest tests/e2e/test_auth_magic_link.py -v` - all 6 tests pass without skips

**Source Tests**: T044-T047 + 2 additional in `tests/e2e/test_auth_magic_link.py`

### TDD Step 1: RED - Remove Skips

- [ ] T113 [US7] Remove pytest.skip() from test_magic_link_request in tests/e2e/test_auth_magic_link.py
- [ ] T114 [P] [US7] Remove pytest.skip() from test_magic_link_request_rate_limited in tests/e2e/test_auth_magic_link.py
- [ ] T115 [P] [US7] Remove pytest.skip() from test_magic_link_verification in tests/e2e/test_auth_magic_link.py
- [ ] T116 [P] [US7] Remove pytest.skip() from test_magic_link_invalid_token in tests/e2e/test_auth_magic_link.py
- [ ] T117 [P] [US7] Remove pytest.skip() from test_anonymous_data_merge in tests/e2e/test_auth_magic_link.py
- [ ] T118 [P] [US7] Remove pytest.skip() from test_full_anonymous_to_authenticated_journey in tests/e2e/test_auth_magic_link.py

### TDD Step 2: GREEN - Implement

- [ ] T119 [US7] Implement MagicLinkToken pydantic model in src/models/magic_link.py
- [ ] T120 [US7] Implement MagicLinkService with DynamoDB storage in src/services/magic_link_service.py
- [ ] T121 [US7] Implement POST /api/v2/auth/magic-link endpoint in src/routers/auth_magic.py
- [ ] T122 [US7] Implement POST /api/v2/auth/verify endpoint in src/routers/auth_magic.py
- [ ] T123 [US7] Add SendGrid integration for email delivery in src/services/magic_link_service.py
- [ ] T124 [US7] Add anonymous session merge logic in src/services/magic_link_service.py
- [ ] T125 [US7] Add rate limiting (1 per email per minute) in src/routers/auth_magic.py
- [ ] T126 [US7] Add token expiry (15 min) and single-use validation in src/services/magic_link_service.py
- [ ] T127 [US7] Register auth_magic router in main FastAPI app in src/main.py

**Checkpoint**: `pytest tests/e2e/test_auth_magic_link.py -v` - all tests pass

---

## Phase 10: User Story 8 - Rate Limiting Feedback (Priority: P3)

**Goal**: Users receive clear feedback when rate limited with retry timing

**Independent Test**: `pytest tests/e2e/test_rate_limiting.py -v` - all 8 tests pass without skips

**Source Tests**: T080-T084 + 3 additional in `tests/e2e/test_rate_limiting.py`

### TDD Step 1: RED - Remove Skips

- [ ] T128 [US8] Remove pytest.skip() from test_requests_within_limit_succeed in tests/e2e/test_rate_limiting.py
- [ ] T129 [P] [US8] Remove pytest.skip() from test_rate_limit_headers_on_normal_response in tests/e2e/test_rate_limiting.py
- [ ] T130 [P] [US8] Remove pytest.skip() from test_rate_limit_triggers_429 in tests/e2e/test_rate_limiting.py
- [ ] T131 [P] [US8] Remove pytest.skip() from test_retry_after_header_present in tests/e2e/test_rate_limiting.py
- [ ] T132 [P] [US8] Remove pytest.skip() from test_rate_limit_recovery in tests/e2e/test_rate_limiting.py
- [ ] T133 [P] [US8] Remove pytest.skip() from test_magic_link_rate_limit in tests/e2e/test_rate_limiting.py
- [ ] T134 [P] [US8] Remove pytest.skip() from test_rate_limit_per_endpoint in tests/e2e/test_rate_limiting.py

### TDD Step 2: GREEN - Implement

- [ ] T135 [US8] Add RateLimitMiddleware with X-RateLimit-* headers in src/middleware/rate_limit.py
- [ ] T136 [US8] Add Retry-After header to 429 responses in src/middleware/rate_limit.py
- [ ] T137 [US8] Configure per-endpoint rate limits in src/middleware/rate_limit.py
- [ ] T138 [US8] Add rate limit state storage (DynamoDB or Redis) in src/middleware/rate_limit.py
- [ ] T139 [US8] Register rate limit middleware in main FastAPI app in src/main.py

**Checkpoint**: `pytest tests/e2e/test_rate_limiting.py -v` - all tests pass

---

## Phase 11: Polish & Cross-Cutting Concerns

**Purpose**: Improvements that affect multiple user stories

- [ ] T140 [P] Add unit tests for alert_service in tests/unit/services/test_alert_service.py
- [ ] T141 [P] Add unit tests for market_service in tests/unit/services/test_market_service.py
- [ ] T142 [P] Add unit tests for ticker_service in tests/unit/services/test_ticker_service.py
- [ ] T143 [P] Add unit tests for notification_service in tests/unit/services/test_notification_service.py
- [ ] T144 [P] Add unit tests for quota_service in tests/unit/services/test_quota_service.py
- [ ] T145 [P] Add unit tests for magic_link_service in tests/unit/services/test_magic_link_service.py
- [ ] T146 Update CLAUDE.md with new endpoint documentation
- [ ] T147 Run full E2E test suite to verify no regressions: `pytest tests/e2e/ -v`
- [ ] T148 Verify E2E skip count reduced by ~67 tests

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies - can start immediately
- **Foundational (Phase 2)**: Depends on Setup completion - BLOCKS all user stories
- **User Stories (Phase 3-10)**: All depend on Foundational phase completion
  - User stories can proceed in parallel (if staffed)
  - Or sequentially in priority order (P1 → P2 → P3)
- **Polish (Phase 11)**: Depends on all user stories being complete

### User Story Dependencies

- **US1 Alerts (P1)**: Can start after Foundational - No dependencies on other stories
- **US2 Market (P1)**: Can start after Foundational - No dependencies on other stories
- **US3 Tickers (P1)**: Can start after Foundational - No dependencies on other stories
- **US4 Notifications (P2)**: Can start after Foundational - May reference alerts but independently testable
- **US5 Preferences (P2)**: Can start after Foundational - No dependencies on other stories
- **US6 Quota (P2)**: Can start after Foundational - May integrate with alerts but independently testable
- **US7 Magic Link (P3)**: Can start after Foundational - No dependencies on other stories
- **US8 Rate Limiting (P3)**: Can start after Foundational - Cross-cutting middleware

### Within Each User Story (TDD Flow)

1. Remove pytest.skip() → tests FAIL with 404
2. Implement models
3. Implement services
4. Implement endpoints
5. Tests pass (GREEN)

### Parallel Opportunities

- All Phase 2 model skeletons (T005-T011) can run in parallel
- Within each user story, skip removals can run in parallel
- P1 stories (US1, US2, US3) can run in parallel after Phase 2
- P2 stories (US4, US5, US6) can run in parallel after Phase 2
- P3 stories (US7, US8) can run in parallel after Phase 2

---

## Parallel Example: User Story 1 (Alerts)

```bash
# Step 1: Remove all skips in parallel
Task: T012-T020 (9 skip removals in test_alerts.py)

# Step 2: Implement in sequence
Task: T021 (models) → T022 (service) → T023-T027 (endpoints) → T028-T030 (validation + registration)

# Step 3: Verify
pytest tests/e2e/test_alerts.py -v  # All 10 tests pass
```

---

## Implementation Strategy

### MVP First (Phase 1 Stories Only)

1. Complete Phase 1: Setup
2. Complete Phase 2: Foundational (CRITICAL - blocks all stories)
3. Complete Phase 3: Alerts (US1) - ~10 E2E tests
4. Complete Phase 4: Market Status (US2) - ~7 E2E tests
5. Complete Phase 5: Ticker Validation (US3) - ~8 E2E tests
6. **STOP and VALIDATE**: Test all P1 stories independently
7. Verify: ~25 E2E tests now pass (SC-001 met)

### Incremental Delivery

1. Complete Setup + Foundational → Foundation ready
2. Add US1 Alerts → Test → Verify ~10 tests pass
3. Add US2 Market → Test → Verify ~17 tests pass
4. Add US3 Tickers → Test → Verify ~25 tests pass (P1 complete)
5. Add US4-US6 → Test → Verify ~54 tests pass (P2 complete)
6. Add US7-US8 → Test → Verify ~67 tests pass (P3 complete)

### Parallel Team Strategy

With multiple developers:

1. Team completes Setup + Foundational together
2. Once Foundational is done:
   - Developer A: US1 Alerts
   - Developer B: US2 Market
   - Developer C: US3 Tickers
3. P1 stories complete, then:
   - Developer A: US4 Notifications
   - Developer B: US5 Preferences
   - Developer C: US6 Quota
4. P2 stories complete, then:
   - Developer A: US7 Magic Link
   - Developer B: US8 Rate Limiting

---

## Notes

- [P] tasks = different files, no dependencies
- [Story] label maps task to specific user story for traceability
- Each user story should be independently completable and testable
- TDD: Remove skip → tests fail → implement → tests pass
- Commit after each task or logical group
- Stop at any checkpoint to validate story independently
- E2E tests are the blackbox specification - implement to match test assertions
