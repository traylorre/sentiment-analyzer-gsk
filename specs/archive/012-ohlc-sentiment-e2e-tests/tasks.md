# Tasks: OHLC & Sentiment History E2E Test Suite

**Input**: Design documents from `/specs/012-ohlc-sentiment-e2e-tests/`
**Prerequisites**: plan.md (required), spec.md (required), research.md, data-model.md, contracts/

**Tests**: This feature IS a test suite, so all tasks are test implementation tasks.

**Organization**: Tasks grouped by user story to enable independent implementation and testing.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (e.g., US1, US2, US3)
- Include exact file paths in descriptions

## Path Conventions

- **Test infrastructure**: `tests/fixtures/mocks/`, `tests/fixtures/synthetic/`
- **Integration tests**: `tests/integration/ohlc/`, `tests/integration/sentiment_history/`
- **E2E tests**: `tests/e2e/`
- **Configuration**: `tests/conftest.py`, `pytest.ini`

---

## Phase 1: Setup (Test Infrastructure)

**Purpose**: Create test infrastructure components needed by all user stories

- [X] T001 Create FailureInjector class in tests/fixtures/mocks/failure_injector.py
- [X] T002 [P] Extend MockTiingoAdapter with failure injection support in tests/fixtures/mocks/mock_tiingo.py
- [X] T003 [P] Extend MockFinnhubAdapter with failure injection support in tests/fixtures/mocks/mock_finnhub.py
- [X] T004 Create OHLCValidator class in tests/fixtures/validators/ohlc_validator.py
- [X] T005 [P] Create SentimentValidator class in tests/fixtures/validators/sentiment_validator.py
- [X] T006 Create TestOracle class in tests/fixtures/oracles/test_oracle.py
- [X] T007 [P] Create EdgeCaseGenerator in tests/fixtures/synthetic/edge_case_generator.py
- [X] T008 Add pytest markers to pytest.ini (ohlc, sentiment_history, error_resilience, boundary, auth, preprod)

---

## Phase 2: Foundational (Shared Fixtures)

**Purpose**: Create shared pytest fixtures that all user stories depend on

**⚠️ CRITICAL**: No user story work can begin until this phase is complete

- [X] T009 Add failure_injector fixtures to tests/conftest.py (default, tiingo_500_error, tiingo_timeout, etc.)
- [X] T010 [P] Add mock adapter fixtures to tests/conftest.py (mock_tiingo, mock_finnhub with injection)
- [X] T011 [P] Add validator fixtures to tests/conftest.py (ohlc_validator, sentiment_validator)
- [X] T012 Add test_oracle fixture to tests/conftest.py
- [X] T013 Add test_client fixture with dependency override for mock adapters in tests/conftest.py
- [X] T014 Create tests/integration/ohlc/__init__.py directory structure
- [X] T015 [P] Create tests/integration/sentiment_history/__init__.py directory structure

**Checkpoint**: Foundation ready - user story test implementation can now begin

---

## Phase 3: User Story 1 - OHLC Happy Path Validation (Priority: P1) 🎯 MVP

**Goal**: Verify OHLC endpoint returns correct, well-formed data for all valid parameter combinations

**Independent Test**: `pytest tests/integration/ohlc/test_happy_path.py -v`

### Implementation for User Story 1

- [X] T016 [US1] Implement test_ohlc_valid_ticker_default_params in tests/integration/ohlc/test_happy_path.py
- [X] T017 [P] [US1] Implement test_ohlc_time_ranges parameterized test (1W, 1M, 3M, 6M, 1Y) in tests/integration/ohlc/test_happy_path.py
- [X] T018 [P] [US1] Implement test_ohlc_custom_date_range in tests/integration/ohlc/test_happy_path.py
- [X] T019 [P] [US1] Implement test_ohlc_lowercase_ticker_normalization in tests/integration/ohlc/test_happy_path.py
- [X] T020 [P] [US1] Implement test_ohlc_cache_expires_at_field in tests/integration/ohlc/test_happy_path.py
- [X] T021 [US1] Implement test_ohlc_source_field_tiingo in tests/integration/ohlc/test_happy_path.py
- [X] T022 [US1] Implement test_ohlc_source_field_finnhub_fallback in tests/integration/ohlc/test_happy_path.py
- [X] T023 [P] [US1] Implement test_ohlc_count_matches_candles_length in tests/integration/ohlc/test_happy_path.py
- [X] T024 [P] [US1] Implement test_ohlc_start_date_matches_first_candle in tests/integration/ohlc/test_happy_path.py
- [X] T025 [P] [US1] Implement test_ohlc_end_date_matches_last_candle in tests/integration/ohlc/test_happy_path.py

**Checkpoint**: OHLC happy path tests complete and passing

---

## Phase 4: User Story 2 - Sentiment History Happy Path Validation (Priority: P1)

**Goal**: Verify sentiment history endpoint returns correct, well-formed data for all valid parameter combinations

**Independent Test**: `pytest tests/integration/sentiment_history/test_happy_path.py -v`

### Implementation for User Story 2

- [X] T026 [US2] Implement test_sentiment_valid_ticker_default_params in tests/integration/sentiment_history/test_happy_path.py
- [X] T027 [P] [US2] Implement test_sentiment_source_filter parameterized test (tiingo, finnhub, our_model, aggregated) in tests/integration/sentiment_history/test_happy_path.py
- [X] T028 [P] [US2] Implement test_sentiment_time_ranges parameterized test (1W, 1M, 3M, 6M, 1Y) in tests/integration/sentiment_history/test_happy_path.py
- [X] T029 [P] [US2] Implement test_sentiment_custom_date_range in tests/integration/sentiment_history/test_happy_path.py
- [X] T030 [P] [US2] Implement test_sentiment_lowercase_ticker_normalization in tests/integration/sentiment_history/test_happy_path.py
- [X] T031 [US2] Implement test_sentiment_score_bounds_validation in tests/integration/sentiment_history/test_happy_path.py
- [X] T032 [US2] Implement test_sentiment_confidence_bounds_validation in tests/integration/sentiment_history/test_happy_path.py
- [X] T033 [US2] Implement test_sentiment_label_consistency parameterized test (positive, neutral, negative thresholds) in tests/integration/sentiment_history/test_happy_path.py
- [X] T034 [P] [US2] Implement test_sentiment_count_matches_history_length in tests/integration/sentiment_history/test_happy_path.py

**Checkpoint**: Sentiment history happy path tests complete and passing

---

## Phase 5: User Story 3 - Data Source Error Resilience (Priority: P1)

**Goal**: Verify endpoints gracefully handle network failures, malformed responses, rate limiting

**Independent Test**: `pytest tests/integration/ohlc/test_error_resilience.py -v`

### Implementation for User Story 3

- [X] T035 [US3] Implement test_tiingo_http_500_fallback_to_finnhub in tests/integration/ohlc/test_error_resilience.py
- [X] T036 [P] [US3] Implement test_tiingo_http_502_fallback in tests/integration/ohlc/test_error_resilience.py
- [X] T037 [P] [US3] Implement test_tiingo_http_503_fallback in tests/integration/ohlc/test_error_resilience.py
- [X] T038 [P] [US3] Implement test_tiingo_http_504_fallback in tests/integration/ohlc/test_error_resilience.py
- [X] T039 [US3] Implement test_tiingo_timeout_fallback in tests/integration/ohlc/test_error_resilience.py
- [X] T040 [US3] Implement test_tiingo_connection_refused_fallback in tests/integration/ohlc/test_error_resilience.py
- [X] T041 [US3] Implement test_tiingo_dns_failure_fallback in tests/integration/ohlc/test_error_resilience.py
- [X] T042 [US3] Implement test_both_sources_500_returns_404 in tests/integration/ohlc/test_error_resilience.py
- [X] T043 [US3] Implement test_tiingo_429_rate_limit_fallback in tests/integration/ohlc/test_error_resilience.py
- [X] T044 [US3] Implement test_both_429_returns_404 in tests/integration/ohlc/test_error_resilience.py
- [X] T045 [P] [US3] Implement test_tiingo_invalid_json_fallback in tests/integration/ohlc/test_error_resilience.py
- [X] T046 [P] [US3] Implement test_tiingo_empty_json_object_fallback in tests/integration/ohlc/test_error_resilience.py
- [X] T047 [P] [US3] Implement test_tiingo_empty_array_fallback in tests/integration/ohlc/test_error_resilience.py
- [X] T048 [P] [US3] Implement test_tiingo_html_error_page_fallback in tests/integration/ohlc/test_error_resilience.py
- [X] T049 [P] [US3] Implement test_tiingo_truncated_json_fallback in tests/integration/ohlc/test_error_resilience.py
- [X] T050 [US3] Implement test_tiingo_missing_required_fields parameterized test (open, close, high, low, date) in tests/integration/ohlc/test_error_resilience.py
- [X] T051 [US3] Implement test_tiingo_null_price_values_fallback in tests/integration/ohlc/test_error_resilience.py
- [X] T052 [US3] Implement test_tiingo_negative_prices_fallback in tests/integration/ohlc/test_error_resilience.py
- [X] T053 [P] [US3] Implement test_tiingo_nan_prices_fallback in tests/integration/ohlc/test_error_resilience.py
- [X] T054 [P] [US3] Implement test_tiingo_infinity_prices_fallback in tests/integration/ohlc/test_error_resilience.py
- [X] T055 [US3] Implement test_tiingo_extra_fields_ignored in tests/integration/ohlc/test_error_resilience.py

**Checkpoint**: Error resilience tests complete and passing

---

## Phase 6: User Story 4 - Edge Case Boundary Testing (Priority: P1)

**Goal**: Verify system behavior at boundary conditions for dates, tickers, prices, and scores

**Independent Test**: `pytest -m boundary -v`

### Implementation for User Story 4

#### Date Range Boundaries
- [X] T056 [US4] Implement test_ohlc_single_day_range in tests/integration/ohlc/test_boundary.py
- [X] T057 [P] [US4] Implement test_ohlc_adjacent_days_range in tests/integration/ohlc/test_boundary.py
- [X] T058 [P] [US4] Implement test_ohlc_market_not_closed_today in tests/integration/ohlc/test_boundary.py
- [X] T059 [P] [US4] Implement test_ohlc_future_end_date in tests/integration/ohlc/test_boundary.py
- [X] T060 [P] [US4] Implement test_ohlc_before_ticker_ipo in tests/integration/ohlc/test_boundary.py
- [X] T061 [US4] Implement test_ohlc_start_after_end_returns_400 in tests/integration/ohlc/test_boundary.py
- [X] T062 [P] [US4] Implement test_sentiment_single_day_range in tests/integration/sentiment_history/test_boundary.py

#### Ticker Symbol Boundaries
- [X] T063 [US4] Implement test_ticker_1_char_valid in tests/integration/ohlc/test_boundary.py
- [X] T064 [P] [US4] Implement test_ticker_5_chars_valid in tests/integration/ohlc/test_boundary.py
- [X] T065 [P] [US4] Implement test_ticker_6_chars_invalid in tests/integration/ohlc/test_boundary.py
- [X] T066 [P] [US4] Implement test_ticker_empty_invalid in tests/integration/ohlc/test_boundary.py
- [X] T067 [US4] Implement test_ticker_with_digits_invalid in tests/integration/ohlc/test_boundary.py
- [X] T068 [P] [US4] Implement test_ticker_with_symbols_invalid parameterized test (-, ., _, space) in tests/integration/ohlc/test_boundary.py
- [X] T069 [P] [US4] Implement test_ticker_whitespace_trimmed in tests/integration/ohlc/test_boundary.py
- [X] T070 [P] [US4] Implement test_ticker_mixed_case_normalized in tests/integration/ohlc/test_boundary.py
- [X] T071 [US4] Implement test_ticker_unknown_returns_404 in tests/integration/ohlc/test_boundary.py
- [X] T072 [P] [US4] Implement test_ticker_unicode_invalid in tests/integration/ohlc/test_boundary.py

#### Price Data Boundaries (via validator)
- [X] T073 [US4] Implement test_candle_high_less_than_low_rejected in tests/integration/ohlc/test_boundary.py
- [X] T074 [P] [US4] Implement test_candle_close_outside_range_rejected in tests/integration/ohlc/test_boundary.py
- [X] T075 [P] [US4] Implement test_candle_open_outside_range_rejected in tests/integration/ohlc/test_boundary.py
- [X] T076 [US4] Implement test_candle_doji_accepted in tests/integration/ohlc/test_boundary.py
- [X] T077 [P] [US4] Implement test_candle_large_cap_price_accepted in tests/integration/ohlc/test_boundary.py
- [X] T078 [P] [US4] Implement test_candle_penny_stock_price_accepted in tests/integration/ohlc/test_boundary.py
- [X] T079 [P] [US4] Implement test_candle_zero_price_rejected in tests/integration/ohlc/test_boundary.py
- [X] T080 [P] [US4] Implement test_candle_zero_volume_accepted in tests/integration/ohlc/test_boundary.py
- [X] T081 [P] [US4] Implement test_candle_negative_volume_rejected in tests/integration/ohlc/test_boundary.py

#### Sentiment Score Boundaries
- [X] T082 [US4] Implement test_sentiment_score_exactly_minus_1_valid in tests/integration/sentiment_history/test_boundary.py
- [X] T083 [P] [US4] Implement test_sentiment_score_exactly_1_valid in tests/integration/sentiment_history/test_boundary.py
- [X] T084 [P] [US4] Implement test_sentiment_score_exactly_0_valid in tests/integration/sentiment_history/test_boundary.py
- [X] T085 [P] [US4] Implement test_sentiment_score_below_minus_1_rejected in tests/integration/sentiment_history/test_boundary.py
- [X] T086 [P] [US4] Implement test_sentiment_score_above_1_rejected in tests/integration/sentiment_history/test_boundary.py
- [X] T087 [US4] Implement test_sentiment_label_at_positive_threshold in tests/integration/sentiment_history/test_boundary.py
- [X] T088 [P] [US4] Implement test_sentiment_label_at_negative_threshold in tests/integration/sentiment_history/test_boundary.py
- [X] T089 [P] [US4] Implement test_sentiment_label_just_below_positive_threshold in tests/integration/sentiment_history/test_boundary.py
- [X] T090 [P] [US4] Implement test_sentiment_label_just_above_negative_threshold in tests/integration/sentiment_history/test_boundary.py
- [X] T091 [P] [US4] Implement test_sentiment_confidence_exactly_0_valid in tests/integration/sentiment_history/test_boundary.py
- [X] T092 [P] [US4] Implement test_sentiment_confidence_exactly_1_valid in tests/integration/sentiment_history/test_boundary.py
- [X] T093 [P] [US4] Implement test_sentiment_confidence_below_0_rejected in tests/integration/sentiment_history/test_boundary.py
- [X] T094 [P] [US4] Implement test_sentiment_confidence_above_1_rejected in tests/integration/sentiment_history/test_boundary.py

**Checkpoint**: Boundary testing complete and passing

---

## Phase 7: User Story 5 - Data Consistency and Ordering (Priority: P1)

**Goal**: Verify data is returned in correct order and maintains internal consistency

**Independent Test**: `pytest tests/integration/ohlc/test_data_consistency.py -v`

### Implementation for User Story 5

- [ ] T095 [US5] Implement test_ohlc_candles_sorted_ascending in tests/integration/ohlc/test_data_consistency.py
- [ ] T096 [P] [US5] Implement test_ohlc_random_order_input_sorted_output in tests/integration/ohlc/test_data_consistency.py
- [ ] T097 [P] [US5] Implement test_ohlc_descending_input_sorted_ascending in tests/integration/ohlc/test_data_consistency.py
- [ ] T098 [US5] Implement test_ohlc_duplicate_dates_deduplicated in tests/integration/ohlc/test_data_consistency.py
- [ ] T099 [US5] Implement test_sentiment_history_sorted_ascending in tests/integration/sentiment_history/test_data_consistency.py
- [ ] T100 [US5] Implement test_ohlc_data_gaps_preserved in tests/integration/ohlc/test_data_consistency.py
- [ ] T101 [P] [US5] Implement test_ohlc_no_weekend_candles in tests/integration/ohlc/test_data_consistency.py
- [ ] T102 [P] [US5] Implement test_sentiment_includes_weekends in tests/integration/sentiment_history/test_data_consistency.py
- [ ] T103 [US5] Implement test_ohlc_start_date_equals_first_candle in tests/integration/ohlc/test_data_consistency.py
- [ ] T104 [P] [US5] Implement test_ohlc_end_date_equals_last_candle in tests/integration/ohlc/test_data_consistency.py
- [ ] T105 [US5] Implement test_ohlc_count_exact_match in tests/integration/ohlc/test_data_consistency.py
- [ ] T106 [P] [US5] Implement test_sentiment_count_exact_match in tests/integration/sentiment_history/test_data_consistency.py
- [ ] T107 [US5] Implement test_ohlc_empty_returns_404 in tests/integration/ohlc/test_data_consistency.py
- [ ] T108 [P] [US5] Implement test_sentiment_empty_returns_404 in tests/integration/sentiment_history/test_data_consistency.py

**Checkpoint**: Data consistency tests complete and passing

---

## Phase 8: User Story 6 - Authentication and Security (Priority: P1)

**Goal**: Verify endpoints enforce authentication requirements and handle security edge cases

**Independent Test**: `pytest -m auth -v`

### Implementation for User Story 6

- [ ] T109 [US6] Implement test_ohlc_missing_user_id_returns_401 in tests/integration/ohlc/test_authentication.py
- [ ] T110 [P] [US6] Implement test_sentiment_missing_user_id_returns_401 in tests/integration/sentiment_history/test_authentication.py
- [ ] T111 [P] [US6] Implement test_ohlc_empty_user_id_returns_401 in tests/integration/ohlc/test_authentication.py
- [ ] T112 [P] [US6] Implement test_ohlc_whitespace_user_id_returns_401 in tests/integration/ohlc/test_authentication.py
- [ ] T113 [US6] Implement test_ohlc_valid_uuid_user_id_succeeds in tests/integration/ohlc/test_authentication.py
- [ ] T114 [P] [US6] Implement test_ohlc_valid_string_user_id_succeeds in tests/integration/ohlc/test_authentication.py
- [ ] T115 [US6] Implement test_ohlc_long_user_id_handled_gracefully in tests/integration/ohlc/test_authentication.py
- [ ] T116 [P] [US6] Implement test_ohlc_special_chars_user_id_no_injection in tests/integration/ohlc/test_authentication.py
- [ ] T117 [P] [US6] Implement test_ohlc_sql_injection_user_id_safe in tests/integration/ohlc/test_authentication.py
- [ ] T118 [P] [US6] Implement test_ohlc_xss_user_id_safe in tests/integration/ohlc/test_authentication.py
- [ ] T119 [P] [US6] Implement test_ohlc_null_byte_user_id_safe in tests/integration/ohlc/test_authentication.py
- [ ] T120 [US6] Implement test_ohlc_newline_user_id_no_log_injection in tests/integration/ohlc/test_authentication.py

**Checkpoint**: Authentication tests complete and passing

---

## Phase 9: User Story 7 - E2E Preprod Validation (Priority: P2)

**Goal**: Verify endpoints work correctly against real preprod infrastructure

**Independent Test**: `PREPROD_API_URL=... pytest -m preprod -v`

### Implementation for User Story 7

- [ ] T121 [US7] Create preprod test configuration and skip conditions in tests/e2e/test_ohlc_sentiment_preprod.py
- [ ] T122 [US7] Implement test_ohlc_real_data_within_5_seconds in tests/e2e/test_ohlc_sentiment_preprod.py
- [ ] T123 [P] [US7] Implement test_ohlc_msft_real_data in tests/e2e/test_ohlc_sentiment_preprod.py
- [ ] T124 [P] [US7] Implement test_sentiment_real_data_within_3_seconds in tests/e2e/test_ohlc_sentiment_preprod.py
- [ ] T125 [P] [US7] Implement test_sentiment_googl_real_data in tests/e2e/test_ohlc_sentiment_preprod.py
- [ ] T126 [US7] Implement test_real_ohlc_prices_positive in tests/e2e/test_ohlc_sentiment_preprod.py
- [ ] T127 [P] [US7] Implement test_real_ohlc_high_gte_low in tests/e2e/test_ohlc_sentiment_preprod.py
- [ ] T128 [P] [US7] Implement test_real_ohlc_open_close_in_range in tests/e2e/test_ohlc_sentiment_preprod.py
- [ ] T129 [US7] Implement test_real_ohlc_recent_data in tests/e2e/test_ohlc_sentiment_preprod.py
- [ ] T130 [P] [US7] Implement test_real_sentiment_scores_in_range in tests/e2e/test_ohlc_sentiment_preprod.py
- [ ] T131 [US7] Implement test_concurrent_requests_complete_within_15_seconds in tests/e2e/test_ohlc_sentiment_preprod.py
- [ ] T132 [P] [US7] Implement test_cache_hit_faster_response in tests/e2e/test_ohlc_sentiment_preprod.py
- [ ] T133 [US7] Implement test_p95_latency_under_2_seconds in tests/e2e/test_ohlc_sentiment_preprod.py
- [ ] T134 [US7] Implement test_real_source_is_tiingo in tests/e2e/test_ohlc_sentiment_preprod.py

**Checkpoint**: E2E preprod tests complete and passing

---

## Phase 10: Polish & Cross-Cutting Concerns

**Purpose**: Final improvements and documentation

- [ ] T135 [P] Run all integration tests and verify < 5 minute completion time
- [ ] T136 Run all E2E tests and verify < 10 minute completion time
- [ ] T137 [P] Verify all pytest markers work correctly
- [ ] T138 Update quickstart.md with final test counts and any adjustments in specs/012-ohlc-sentiment-e2e-tests/quickstart.md
- [ ] T139 Run ruff check and black formatting on all test files
- [ ] T140 Final review of test coverage against spec.md acceptance scenarios

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies - can start immediately
- **Foundational (Phase 2)**: Depends on Setup completion - BLOCKS all user stories
- **User Stories (Phase 3-9)**: All depend on Foundational phase completion
  - US1-US6 are all P1 priority and can run in parallel
  - US7 is P2 priority and depends on US1-US6 being stable
- **Polish (Phase 10)**: Depends on all user stories being complete

### User Story Dependencies

- **US1 (OHLC Happy Path)**: Can start after Foundational - No cross-story dependencies
- **US2 (Sentiment Happy Path)**: Can start after Foundational - No cross-story dependencies
- **US3 (Error Resilience)**: Can start after Foundational - Uses FailureInjector from Setup
- **US4 (Boundary Testing)**: Can start after Foundational - Uses EdgeCaseGenerator from Setup
- **US5 (Data Consistency)**: Can start after Foundational - Uses validators from Setup
- **US6 (Authentication)**: Can start after Foundational - No special dependencies
- **US7 (E2E Preprod)**: Should be last - validates full integration

### Within Each User Story

- Tests organized by file for clear structure
- Parameterized tests used for repetitive scenarios
- Each test should be independently runnable

### Parallel Opportunities

- All Setup tasks marked [P] can run in parallel
- All Foundational tasks marked [P] can run in parallel
- US1-US6 can all start in parallel after Foundational phase
- Within each user story, tasks marked [P] can run in parallel

---

## Parallel Example: User Story 3 (Error Resilience)

```bash
# Launch HTTP error fallback tests together (all [P]):
Task: "T036 [P] [US3] Implement test_tiingo_http_502_fallback"
Task: "T037 [P] [US3] Implement test_tiingo_http_503_fallback"
Task: "T038 [P] [US3] Implement test_tiingo_http_504_fallback"

# Launch malformed response tests together (all [P]):
Task: "T045 [P] [US3] Implement test_tiingo_invalid_json_fallback"
Task: "T046 [P] [US3] Implement test_tiingo_empty_json_object_fallback"
Task: "T047 [P] [US3] Implement test_tiingo_empty_array_fallback"
```

---

## Implementation Strategy

### MVP First (User Stories 1 & 2)

1. Complete Phase 1: Setup (test infrastructure)
2. Complete Phase 2: Foundational (shared fixtures)
3. Complete Phase 3: User Story 1 (OHLC Happy Path)
4. Complete Phase 4: User Story 2 (Sentiment Happy Path)
5. **STOP and VALIDATE**: Run `pytest tests/integration/ -v`
6. Tests should pass, endpoints verified

### Full Implementation

1. Complete Setup + Foundational → Infrastructure ready
2. Add US1 + US2 → Happy path coverage (MVP!)
3. Add US3 → Error resilience coverage
4. Add US4 → Boundary testing coverage
5. Add US5 → Data consistency coverage
6. Add US6 → Authentication coverage
7. Add US7 → E2E preprod validation
8. Polish → Final verification

### Parallel Team Strategy

With multiple developers:

1. Team completes Setup + Foundational together
2. Once Foundational is done:
   - Developer A: US1 (OHLC Happy Path) + US3 (Error Resilience)
   - Developer B: US2 (Sentiment Happy Path) + US4 (Boundary Testing)
   - Developer C: US5 (Data Consistency) + US6 (Authentication)
3. All complete: Developer D runs US7 (E2E Preprod)

---

## Notes

- [P] tasks = different files, no dependencies
- [Story] label maps task to specific user story for traceability
- Each user story should be independently completable and testable
- Commit after each task or logical group
- Stop at any checkpoint to validate story independently
- Total tasks: 140
- Task count per user story:
  - Setup (Phase 1): 8 tasks
  - Foundational (Phase 2): 7 tasks
  - US1 (OHLC Happy Path): 10 tasks
  - US2 (Sentiment Happy Path): 9 tasks
  - US3 (Error Resilience): 21 tasks
  - US4 (Boundary Testing): 39 tasks
  - US5 (Data Consistency): 14 tasks
  - US6 (Authentication): 12 tasks
  - US7 (E2E Preprod): 14 tasks
  - Polish: 6 tasks
