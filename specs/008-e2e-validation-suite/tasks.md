# Tasks: E2E Validation Suite

**Input**: Design documents from `/specs/008-e2e-validation-suite/`
**Prerequisites**: plan.md (required), spec.md (required), research.md, data-model.md, contracts/

**Tests**: This feature IS the test suite itself. All tasks create E2E tests.

**Organization**: Tasks are grouped by user story to enable independent implementation and testing of each story.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (e.g., US1, US2, US3)
- Include exact file paths in descriptions

## Path Conventions

- **Test suite**: `tests/e2e/` at repository root
- **Fixtures**: `tests/e2e/fixtures/`
- **Helpers**: `tests/e2e/helpers/`
- **CI workflow**: `.github/workflows/`

---

## Phase 1: Setup (Test Infrastructure)

**Purpose**: Create test directory structure and shared infrastructure

- [ ] T001 Create tests/e2e/ directory structure per plan.md
- [ ] T002 Create tests/e2e/__init__.py with e2e marker registration
- [ ] T003 [P] Create tests/e2e/fixtures/__init__.py package
- [ ] T004 [P] Create tests/e2e/helpers/__init__.py package
- [ ] T005 Add pytest-asyncio, httpx, httpx-sse, boto3 to pyproject.toml [dev] dependencies
- [ ] T006 Create pytest.ini or pyproject.toml [tool.pytest] section with e2e markers and asyncio mode

---

## Phase 2: Foundational (Shared Test Components)

**Purpose**: Core fixtures and helpers that ALL user stories depend on

**⚠️ CRITICAL**: No user story tests can be written until this phase is complete

### Synthetic Data Generators

- [ ] T007 [P] Create SyntheticTicker dataclass in tests/e2e/fixtures/models.py
- [ ] T008 [P] Create SyntheticSentiment dataclass in tests/e2e/fixtures/models.py
- [ ] T009 [P] Create SyntheticUser dataclass in tests/e2e/fixtures/models.py
- [ ] T010 [P] Create SyntheticNewsArticle dataclass in tests/e2e/fixtures/models.py
- [ ] T011 [P] Create SyntheticOHLC dataclass in tests/e2e/fixtures/models.py
- [ ] T012 [P] Create SyntheticEmailEvent dataclass in tests/e2e/fixtures/models.py
- [ ] T013 Implement generate_tiingo_news() in tests/e2e/fixtures/tiingo.py per contracts/synthetic-tiingo.md
- [ ] T014 Implement generate_tiingo_ohlc() in tests/e2e/fixtures/tiingo.py
- [ ] T015 Implement SyntheticTiingoHandler class in tests/e2e/fixtures/tiingo.py
- [ ] T016 Implement generate_finnhub_sentiment() in tests/e2e/fixtures/finnhub.py per contracts/synthetic-finnhub.md
- [ ] T017 Implement SyntheticFinnhubHandler class in tests/e2e/fixtures/finnhub.py
- [ ] T018 Implement SyntheticSendGridHandler class in tests/e2e/fixtures/sendgrid.py per contracts/synthetic-sendgrid.md
- [ ] T019 Implement generate_ohlc_data() in tests/e2e/fixtures/ohlc.py for ATR testing

### Core Test Helpers

- [ ] T020 [P] Implement PreprodAPIClient class in tests/e2e/helpers/api_client.py with httpx async client
- [ ] T021 [P] Implement create_anonymous_session() in tests/e2e/helpers/auth.py
- [ ] T022 [P] Implement request_magic_link() in tests/e2e/helpers/auth.py
- [ ] T023 [P] Implement verify_magic_link() in tests/e2e/helpers/auth.py
- [ ] T024 [P] Implement get_oauth_urls() in tests/e2e/helpers/auth.py
- [ ] T025 [P] Implement refresh_tokens() in tests/e2e/helpers/auth.py
- [ ] T026 Implement query_cloudwatch_logs() in tests/e2e/helpers/cloudwatch.py per research.md section 4
- [ ] T027 Implement get_cloudwatch_metrics() in tests/e2e/helpers/cloudwatch.py
- [ ] T028 Implement get_xray_trace() in tests/e2e/helpers/xray.py per research.md section 5
- [ ] T029 Implement validate_trace_segments() in tests/e2e/helpers/xray.py
- [ ] T030 Implement cleanup_by_prefix() in tests/e2e/helpers/cleanup.py
- [ ] T031 Implement find_orphaned_test_data() in tests/e2e/helpers/cleanup.py

### Shared Fixtures (conftest.py)

- [ ] T032 Create test_run_id fixture (session scope) in tests/e2e/conftest.py
- [ ] T033 Create test_email_domain fixture (session scope) in tests/e2e/conftest.py
- [ ] T034 Create api_client fixture (session scope) in tests/e2e/conftest.py
- [ ] T035 Create synthetic_data fixture (session scope) in tests/e2e/conftest.py
- [ ] T036 Create tiingo_handler fixture in tests/e2e/conftest.py
- [ ] T037 Create finnhub_handler fixture in tests/e2e/conftest.py
- [ ] T038 Create sendgrid_handler fixture in tests/e2e/conftest.py
- [ ] T039 Create cleanup_test_data fixture (session scope, autouse) in tests/e2e/conftest.py
- [ ] T040 Create dynamodb_table fixture for direct DynamoDB access in tests/e2e/conftest.py

**Checkpoint**: Foundation ready - user story test implementation can now begin

---

## Phase 3: User Story 1 - Unknown to Known User Journey (Priority: P1) 🎯 MVP

**Goal**: Validate anonymous→authenticated flow with data persistence

**Independent Test**: Execute full anonymous→magic link→authenticated flow, verify configs persist

### Implementation for User Story 1

- [ ] T041 [P] [US1] Create test_anonymous_session_creation() in tests/e2e/test_auth_anonymous.py
- [ ] T042 [P] [US1] Create test_anonymous_session_validation() in tests/e2e/test_auth_anonymous.py
- [ ] T043 [P] [US1] Create test_anonymous_config_creation() in tests/e2e/test_auth_anonymous.py
- [ ] T044 [US1] Create test_magic_link_request() in tests/e2e/test_auth_magic_link.py
- [ ] T045 [US1] Create test_magic_link_verification() in tests/e2e/test_auth_magic_link.py
- [ ] T046 [US1] Create test_anonymous_data_merge() in tests/e2e/test_auth_magic_link.py
- [ ] T047 [US1] Create test_full_anonymous_to_authenticated_journey() in tests/e2e/test_auth_magic_link.py (integration test)

**Checkpoint**: US1 complete - Anonymous→Authenticated flow validated

---

## Phase 4: User Story 2 - OAuth Authentication Flows (Priority: P2)

**Goal**: Validate OAuth URL generation, callback, token management

**Independent Test**: Validate OAuth URLs, simulate callback, verify session creation

### Implementation for User Story 2

- [ ] T048 [P] [US2] Create test_oauth_urls_returned() in tests/e2e/test_auth_oauth.py
- [ ] T049 [P] [US2] Create test_oauth_url_structure_google() in tests/e2e/test_auth_oauth.py
- [ ] T050 [P] [US2] Create test_oauth_url_structure_github() in tests/e2e/test_auth_oauth.py
- [ ] T051 [US2] Create test_oauth_callback_tokens_returned() in tests/e2e/test_auth_oauth.py
- [ ] T052 [US2] Create test_session_validation() in tests/e2e/test_auth_oauth.py
- [ ] T053 [US2] Create test_signout_invalidates_session() in tests/e2e/test_auth_oauth.py
- [ ] T054 [US2] Create test_token_refresh() in tests/e2e/test_auth_oauth.py

**Checkpoint**: US2 complete - OAuth flows validated

---

## Phase 5: User Story 3 - Configuration CRUD Operations (Priority: P3)

**Goal**: Validate full CRUD lifecycle with validation rules

**Independent Test**: Perform create, read, update, delete on config, verify each operation

### Implementation for User Story 3

- [ ] T055 [P] [US3] Create test_config_create_success() in tests/e2e/test_config_crud.py
- [ ] T056 [P] [US3] Create test_config_create_with_ticker_metadata() in tests/e2e/test_config_crud.py
- [ ] T057 [US3] Create test_config_read_by_id() in tests/e2e/test_config_crud.py
- [ ] T058 [US3] Create test_config_update_name_and_tickers() in tests/e2e/test_config_crud.py
- [ ] T059 [US3] Create test_config_delete() in tests/e2e/test_config_crud.py
- [ ] T060 [US3] Create test_config_max_limit_enforced() in tests/e2e/test_config_crud.py
- [ ] T061 [US3] Create test_config_invalid_ticker_rejected() in tests/e2e/test_config_crud.py

**Checkpoint**: US3 complete - Config CRUD validated

---

## Phase 6: User Story 4 - Sentiment and Volatility Data (Priority: P4)

**Goal**: Validate sentiment/volatility endpoints return correct structure

**Independent Test**: Create config, request sentiment data, verify response matches contract

### Implementation for User Story 4

- [ ] T062 [P] [US4] Create test_sentiment_data_all_sources() in tests/e2e/test_sentiment.py
- [ ] T063 [P] [US4] Create test_heatmap_sources_view() in tests/e2e/test_sentiment.py
- [ ] T064 [P] [US4] Create test_heatmap_timeperiods_view() in tests/e2e/test_sentiment.py
- [ ] T065 [US4] Create test_volatility_atr_data() in tests/e2e/test_sentiment.py
- [ ] T066 [US4] Create test_correlation_data() in tests/e2e/test_sentiment.py
- [ ] T067 [US4] Create test_sentiment_with_synthetic_oracle() in tests/e2e/test_sentiment.py (verify expected values)

**Checkpoint**: US4 complete - Sentiment/volatility data validated

---

## Phase 7: User Story 5 - Alert Rule Lifecycle (Priority: P5)

**Goal**: Validate alert CRUD, threshold configuration, enable/disable

**Independent Test**: Create alert, toggle, update threshold, delete, verify each state

### Implementation for User Story 5

- [ ] T068 [P] [US5] Create test_alert_create_sentiment_threshold() in tests/e2e/test_alerts.py
- [ ] T069 [P] [US5] Create test_alert_create_volatility_threshold() in tests/e2e/test_alerts.py
- [ ] T070 [US5] Create test_alert_toggle_off() in tests/e2e/test_alerts.py
- [ ] T071 [US5] Create test_alert_update_threshold() in tests/e2e/test_alerts.py
- [ ] T072 [US5] Create test_alert_delete() in tests/e2e/test_alerts.py
- [ ] T073 [US5] Create test_alert_max_limit_enforced() in tests/e2e/test_alerts.py
- [ ] T074 [US5] Create test_alert_anonymous_forbidden() in tests/e2e/test_alerts.py

**Checkpoint**: US5 complete - Alert lifecycle validated

---

## Phase 8: User Story 6 - Notification Delivery Pipeline (Priority: P6)

**Goal**: Validate alert evaluation, notification creation, delivery tracking

**Independent Test**: Trigger alert condition, verify notification created and tracked

### Implementation for User Story 6

- [ ] T075 [P] [US6] Create test_alert_trigger_creates_notification() in tests/e2e/test_notifications.py
- [ ] T076 [P] [US6] Create test_notification_status_sent() in tests/e2e/test_notifications.py
- [ ] T077 [US6] Create test_notification_list() in tests/e2e/test_notifications.py
- [ ] T078 [US6] Create test_notification_detail_with_tracking() in tests/e2e/test_notifications.py
- [ ] T079 [US6] Create test_notification_quota_exceeded() in tests/e2e/test_notifications.py

**Checkpoint**: US6 complete - Notification pipeline validated

---

## Phase 9: User Story 7 - Rate Limiting Enforcement (Priority: P7)

**Goal**: Validate rate limits trigger 429 with retry_after

**Independent Test**: Burst requests until 429, verify retry_after header

### Implementation for User Story 7

- [ ] T080 [P] [US7] Create test_requests_within_limit_succeed() in tests/e2e/test_rate_limiting.py
- [ ] T081 [US7] Create test_rate_limit_triggers_429() in tests/e2e/test_rate_limiting.py
- [ ] T082 [US7] Create test_retry_after_header_present() in tests/e2e/test_rate_limiting.py
- [ ] T083 [US7] Create test_rate_limit_recovery() in tests/e2e/test_rate_limiting.py
- [ ] T084 [US7] Create test_magic_link_rate_limit() in tests/e2e/test_rate_limiting.py

**Checkpoint**: US7 complete - Rate limiting validated

---

## Phase 10: User Story 8 - Circuit Breaker Behavior (Priority: P8)

**Goal**: Validate circuit breaker opens on failures, serves cached data

**Independent Test**: Inject failures, verify circuit opens, verify cached data returned

### Implementation for User Story 8

- [ ] T085 [P] [US8] Create test_healthy_api_returns_fresh_data() in tests/e2e/test_circuit_breaker.py
- [ ] T086 [US8] Create test_circuit_opens_after_failures() in tests/e2e/test_circuit_breaker.py
- [ ] T087 [US8] Create test_circuit_open_returns_cached_data() in tests/e2e/test_circuit_breaker.py
- [ ] T088 [US8] Create test_circuit_half_open_after_timeout() in tests/e2e/test_circuit_breaker.py
- [ ] T089 [US8] Create test_circuit_closes_on_success() in tests/e2e/test_circuit_breaker.py

**Checkpoint**: US8 complete - Circuit breaker validated

---

## Phase 11: User Story 9 - Ticker Validation (Priority: P9)

**Goal**: Validate ticker validation and autocomplete endpoints

**Independent Test**: Validate known-good, known-bad, delisted tickers; test autocomplete

### Implementation for User Story 9

- [ ] T090 [P] [US9] Create test_valid_ticker_returns_metadata() in tests/e2e/test_ticker_validation.py
- [ ] T091 [P] [US9] Create test_delisted_ticker_returns_successor() in tests/e2e/test_ticker_validation.py
- [ ] T092 [P] [US9] Create test_invalid_ticker_returns_invalid() in tests/e2e/test_ticker_validation.py
- [ ] T093 [US9] Create test_ticker_search_returns_matches() in tests/e2e/test_ticker_validation.py
- [ ] T094 [US9] Create test_ticker_search_empty_query() in tests/e2e/test_ticker_validation.py

**Checkpoint**: US9 complete - Ticker validation validated

---

## Phase 12: User Story 10 - Real-Time SSE Updates (Priority: P10)

**Goal**: Validate SSE connection, event streaming, reconnection

**Independent Test**: Connect SSE, trigger update, verify event received

### Implementation for User Story 10

- [ ] T095 [P] [US10] Create test_sse_connection_established() in tests/e2e/test_sse.py
- [ ] T096 [US10] Create test_sse_receives_sentiment_update() in tests/e2e/test_sse.py
- [ ] T097 [US10] Create test_sse_receives_refresh_event() in tests/e2e/test_sse.py
- [ ] T098 [US10] Create test_sse_reconnection_with_last_event_id() in tests/e2e/test_sse.py
- [ ] T099 [US10] Create test_sse_unauthenticated_rejected() in tests/e2e/test_sse.py

**Checkpoint**: US10 complete - SSE streaming validated

---

## Phase 13: User Story 11 - CloudWatch Observability (Priority: P11)

**Goal**: Validate CloudWatch logs, metrics, X-Ray traces emitted correctly

**Independent Test**: Make API request, query CloudWatch, verify entries exist

### Implementation for User Story 11

- [ ] T100 [P] [US11] Create test_cloudwatch_logs_created() in tests/e2e/test_observability.py
- [ ] T101 [P] [US11] Create test_cloudwatch_metrics_incremented() in tests/e2e/test_observability.py
- [ ] T102 [US11] Create test_xray_trace_exists() in tests/e2e/test_observability.py
- [ ] T103 [US11] Create test_xray_cross_lambda_trace() in tests/e2e/test_observability.py
- [ ] T104 [US11] Create test_cloudwatch_alarm_triggers() in tests/e2e/test_observability.py

**Checkpoint**: US11 complete - Observability validated

---

## Phase 14: User Story 12 - Market Status (Priority: P12)

**Goal**: Validate market status detection and pre-market estimates

**Independent Test**: Query market status, verify response matches market hours

### Implementation for User Story 12

- [ ] T105 [P] [US12] Create test_market_status_open() in tests/e2e/test_market_status.py
- [ ] T106 [P] [US12] Create test_market_status_closed() in tests/e2e/test_market_status.py
- [ ] T107 [P] [US12] Create test_market_status_holiday() in tests/e2e/test_market_status.py
- [ ] T108 [US12] Create test_premarket_estimates_returned() in tests/e2e/test_market_status.py
- [ ] T109 [US12] Create test_premarket_redirect_when_open() in tests/e2e/test_market_status.py

**Checkpoint**: US12 complete - Market status validated

---

## Phase 15: CI Integration & Polish

**Purpose**: GitHub Actions workflow and cross-cutting concerns

- [ ] T110 Create .github/workflows/e2e-preprod.yml per research.md section 10
- [ ] T111 Add AWS credentials configuration via OIDC in e2e-preprod.yml
- [ ] T112 Add JUnit XML report generation (--junitxml) in e2e-preprod.yml
- [ ] T113 Add artifact upload for test results in e2e-preprod.yml
- [ ] T114 [P] Create tests/e2e/test_cleanup.py with manual cleanup utilities
- [ ] T115 [P] Add pytest markers for test categorization (@pytest.mark.auth, @pytest.mark.slow, etc.)
- [ ] T116 Update specs/008-e2e-validation-suite/quickstart.md with final instructions
- [ ] T117 Run full E2E suite in preprod and verify all tests pass

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies - can start immediately
- **Foundational (Phase 2)**: Depends on Setup completion - BLOCKS all user stories
- **User Stories (Phase 3-14)**: All depend on Foundational phase completion
  - User stories can proceed in parallel (if staffed)
  - Or sequentially in priority order (P1 → P2 → ... → P12)
- **CI Integration (Phase 15)**: Depends on at least US1 being complete for validation

### User Story Dependencies

- **US1 (P1)**: Can start after Phase 2 - No dependencies on other stories
- **US2 (P2)**: Can start after Phase 2 - No dependencies on other stories
- **US3 (P3)**: Can start after Phase 2 - No dependencies on other stories
- **US4-US12**: Can start after Phase 2 - No dependencies on other stories

All user stories are independently testable and can be parallelized.

### Within Each User Story

- Tests create fixtures and helpers first (via conftest)
- Test files within a story marked [P] can be written in parallel
- Story complete when all acceptance scenarios covered

### Parallel Opportunities

- All foundational fixtures (T007-T019) can run in parallel
- All foundational helpers (T020-T031) can run in parallel
- All user stories can be implemented in parallel after Phase 2
- Tests marked [P] within each story can be written in parallel

---

## Parallel Example: User Story 1

```bash
# Launch all US1 tests in parallel:
Task: "T041 [P] [US1] Create test_anonymous_session_creation() in tests/e2e/test_auth_anonymous.py"
Task: "T042 [P] [US1] Create test_anonymous_session_validation() in tests/e2e/test_auth_anonymous.py"
Task: "T043 [P] [US1] Create test_anonymous_config_creation() in tests/e2e/test_auth_anonymous.py"

# Then sequential (depend on anonymous session):
Task: "T044 [US1] Create test_magic_link_request() in tests/e2e/test_auth_magic_link.py"
Task: "T045 [US1] Create test_magic_link_verification() in tests/e2e/test_auth_magic_link.py"
Task: "T046 [US1] Create test_anonymous_data_merge() in tests/e2e/test_auth_magic_link.py"
Task: "T047 [US1] Create test_full_anonymous_to_authenticated_journey() in tests/e2e/test_auth_magic_link.py"
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 1: Setup
2. Complete Phase 2: Foundational (CRITICAL - blocks all stories)
3. Complete Phase 3: User Story 1
4. **STOP and VALIDATE**: Run US1 tests in preprod
5. Deploy CI workflow if ready

### Incremental Delivery

1. Complete Setup + Foundational → Foundation ready
2. Add US1 → Run tests → Validate MVP
3. Add US2-US3 → Run tests → Core auth/config covered
4. Add US4-US6 → Run tests → Data and notifications covered
5. Add US7-US9 → Run tests → Error handling covered
6. Add US10-US12 → Run tests → Advanced features covered
7. Complete CI Integration → Full pipeline ready

### Parallel Team Strategy

With multiple developers after Phase 2 complete:
- Developer A: US1, US2 (Auth flows)
- Developer B: US3, US4 (Config/Data)
- Developer C: US5, US6 (Alerts/Notifications)
- Developer D: US7, US8, US9 (Error handling)
- Developer E: US10, US11, US12 (Advanced)

---

## Summary

| Phase | Tasks | Stories |
|-------|-------|---------|
| Setup | 6 | - |
| Foundational | 34 | - |
| US1 (P1) | 7 | Anonymous→Auth |
| US2 (P2) | 7 | OAuth |
| US3 (P3) | 7 | Config CRUD |
| US4 (P4) | 6 | Sentiment/Volatility |
| US5 (P5) | 7 | Alerts |
| US6 (P6) | 5 | Notifications |
| US7 (P7) | 5 | Rate Limiting |
| US8 (P8) | 5 | Circuit Breaker |
| US9 (P9) | 5 | Ticker Validation |
| US10 (P10) | 5 | SSE |
| US11 (P11) | 5 | Observability |
| US12 (P12) | 5 | Market Status |
| CI/Polish | 8 | - |
| **Total** | **117** | **12 stories** |

---

## Notes

- [P] tasks = different files, no dependencies
- [Story] label maps task to specific user story for traceability
- Each user story is independently completable and testable
- Commit after each task or logical group
- Run `pytest tests/e2e/ -m "us1"` to validate individual stories
- All tests use preprod environment (no local execution)
