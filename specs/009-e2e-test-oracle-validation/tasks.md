# Tasks: E2E Test Oracle Validation

**Feature**: 009-e2e-test-oracle-validation
**Generated**: 2025-11-29
**Input**: Design documents from `/specs/009-e2e-test-oracle-validation/`

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (e.g., US1, US2)
- All paths relative to repository root

---

## Phase 1: Setup

**Purpose**: Verify existing infrastructure and prepare for oracle enhancements

- [ ] T001 Verify test fixtures exist: `tests/fixtures/synthetic/test_oracle.py`, `tests/e2e/conftest.py`
- [ ] T002 [P] Add OracleExpectation and ValidationResult dataclasses to `tests/fixtures/synthetic/test_oracle.py`
- [ ] T003 [P] Add SkipInfo dataclass to `tests/e2e/conftest.py` for standardized skip messages

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Core infrastructure that MUST be complete before user story work

**⚠️ CRITICAL**: US1, US3, US4, US5 depend on these foundational pieces

- [ ] T004 Create ConfigGenerator in `tests/fixtures/synthetic/config_generator.py` with SyntheticConfiguration and SyntheticTicker dataclasses
- [ ] T005 Add factory function `create_config_generator(seed)` to `tests/fixtures/synthetic/__init__.py`
- [ ] T006 Add `config_generator` and `synthetic_config` fixtures to `tests/e2e/conftest.py`
- [ ] T007 [P] Add unit tests for ConfigGenerator determinism in `tests/unit/fixtures/test_config_generator.py`

**Checkpoint**: Foundation ready - ConfigGenerator and core fixtures available

---

## Phase 3: User Story 1 - Fix Sentiment Oracle Validation (Priority: P1) 🎯

**Goal**: Sentiment tests compare actual API responses against oracle-computed values

**Independent Test**: Run `pytest tests/e2e/test_sentiment.py -v -m preprod` and verify numeric comparisons within ±0.01 tolerance

### Implementation for User Story 1

- [ ] T008 [US1] Extend SyntheticTestOracle with `compute_expected_api_sentiment(config, news_articles)` method in `tests/fixtures/synthetic/test_oracle.py`
- [ ] T009 [US1] Implement `validate_api_response(response, expected, tolerance)` returning ValidationResult in `tests/fixtures/synthetic/test_oracle.py`
- [ ] T010 [US1] Add `test_oracle` fixture to `tests/e2e/conftest.py` using `synthetic_seed`
- [ ] T011 [US1] Refactor `test_sentiment_with_synthetic_oracle` in `tests/e2e/test_sentiment.py` to use oracle comparison pattern
- [ ] T012 [US1] Add tolerance-based assertions (±0.01) for sentiment score comparisons in `tests/e2e/test_sentiment.py`
- [ ] T013 [US1] Add unit tests for oracle computation in `tests/unit/fixtures/test_oracle_unit.py`

**Checkpoint**: Sentiment tests now validate oracle values, not just structure

---

## Phase 4: User Story 2 - Eliminate Dual-Outcome Assertions (Priority: P1) 🎯

**Goal**: Replace `assert A or B` patterns with specific single-outcome tests

**Independent Test**: Run `grep -rn "assert.*or.*==" tests/e2e/` and verify zero matches

### Implementation for User Story 2

- [ ] T014 [P] [US2] Audit and list all dual-outcome assertions in `tests/e2e/test_rate_limiting.py`
- [ ] T015 [P] [US2] Audit and list all dual-outcome assertions in `tests/e2e/test_auth_magic_link.py`, `tests/e2e/test_auth_anonymous.py`, `tests/e2e/test_auth_oauth.py`
- [ ] T016 [US2] Split rate limiting tests: `test_rate_limit_triggers_after_threshold()` and `test_requests_succeed_under_threshold()` in `tests/e2e/test_rate_limiting.py`
- [ ] T017 [US2] Refactor auth status tests to assert specific HTTP codes (200 vs 201) in `tests/e2e/test_auth_*.py`
- [ ] T018 [US2] Add explicit `pytest.skip()` with SkipInfo messages for tests that cannot trigger target condition in preprod
- [ ] T019 [US2] Refactor quota tracking assertions in `tests/e2e/test_quota.py` to be single-outcome

**Checkpoint**: Zero `assert A or B` patterns remain in E2E tests

---

## Phase 5: User Story 3 - Extend Synthetic Data to Preprod Tests (Priority: P2)

**Goal**: All preprod tests use seeded synthetic data instead of hardcoded values

**Independent Test**: Run E2E suite twice with different `E2E_TEST_SEED` values and verify different data is used

### Implementation for User Story 3

- [ ] T020 [P] [US3] Migrate `tests/e2e/test_config_crud.py` to use ConfigGenerator for config names and tickers
- [ ] T021 [P] [US3] Migrate `tests/e2e/test_alerts.py` to use synthetic data generators
- [ ] T022 [P] [US3] Migrate `tests/e2e/test_notifications.py` to use synthetic data generators
- [ ] T023 [P] [US3] Migrate `tests/e2e/test_notification_preferences.py` to use synthetic data generators
- [ ] T024 [P] [US3] Migrate `tests/e2e/test_ticker_validation.py` to use TickerGenerator
- [ ] T025 [P] [US3] Migrate `tests/e2e/test_market_status.py` to use synthetic data generators
- [ ] T026 [P] [US3] Migrate `tests/e2e/test_observability.py` to use synthetic data generators
- [ ] T027 [P] [US3] Migrate `tests/e2e/test_sse.py` to use synthetic data generators
- [ ] T028 [US3] Verify determinism: same seed produces identical synthetic data across runs

**Checkpoint**: All 20 E2E test files use synthetic data generators

---

## Phase 6: User Story 4 - Add Processing Layer Failure Mode Tests (Priority: P2)

**Goal**: Test error handling paths through failure injection

**Independent Test**: Run failure injection tests and verify appropriate error responses or fallback behaviors

### Implementation for User Story 4

- [ ] T029 [US4] Add FailureInjectionConfig dataclass to `tests/e2e/conftest.py`
- [ ] T030 [P] [US4] Create `tests/e2e/test_failure_injection.py` with test class structure
- [ ] T031 [US4] Implement `test_tiingo_failure_graceful_degradation` using `fail_mode_tiingo` context manager
- [ ] T032 [US4] Implement `test_finnhub_failure_fallback` using `fail_mode_finnhub` context manager
- [ ] T033 [US4] Implement `test_circuit_breaker_opens_on_failures` verifying state transitions in DynamoDB
- [ ] T034 [US4] Implement `test_malformed_response_handling` for invalid JSON from external APIs
- [ ] T035 [US4] Implement `test_timeout_retry_behavior` for external API timeouts
- [ ] T036 [US4] Add at least 5 failure injection tests total (FR-005 requirement)

**Checkpoint**: At least 5 new failure injection tests covering error handling paths

---

## Phase 7: User Story 5 - Reduce Test Skip Rate (Priority: P3)

**Goal**: E2E skip rate below 15% with actionable skip messages

**Independent Test**: Run `pytest tests/e2e/ -v --tb=no | grep -c SKIPPED` and verify <15% of total

### Implementation for User Story 5

- [ ] T037 [US5] Audit all skipped tests and categorize by skip reason
- [ ] T038 [US5] Convert CloudWatch/observability tests to unit tests with mocks in `tests/unit/`
- [ ] T039 [US5] Add `integration-optional` pytest marker for tests requiring specific preprod resources
- [ ] T040 [US5] Update all skip messages to use SkipInfo format with condition, reason, and remediation
- [ ] T041 [US5] Add TestMetrics tracking to `tests/e2e/conftest.py` for skip rate reporting
- [ ] T042 [US5] Verify skip rate is below 15% threshold (SC-003)

**Checkpoint**: Skip rate below 15% with all skips having actionable messages

---

## Phase 8: Polish & Cross-Cutting Concerns

**Purpose**: Final validation and cleanup

- [ ] T043 Run full E2E suite and verify all success criteria (SC-001 through SC-007)
- [ ] T044 [P] Verify zero dual-outcome assertions remain: `grep -rn "assert.*or.*==" tests/e2e/`
- [ ] T045 [P] Verify all sentiment tests use oracle comparison pattern
- [ ] T046 Run quickstart.md examples to validate documentation accuracy
- [ ] T047 Update `tests/fixtures/synthetic/__init__.py` exports for new components

---

## Dependencies & Execution Order

### Phase Dependencies

- **Phase 1 (Setup)**: No dependencies - can start immediately
- **Phase 2 (Foundational)**: Depends on Phase 1 - BLOCKS all user stories
- **Phase 3 (US1)**: Depends on Phase 2 (ConfigGenerator, fixtures)
- **Phase 4 (US2)**: Can start after Phase 2, independent of US1
- **Phase 5 (US3)**: Depends on Phase 2 (ConfigGenerator)
- **Phase 6 (US4)**: Depends on Phase 2 (fixtures), independent of US1-US3
- **Phase 7 (US5)**: Can start after Phase 2, may reference fixes from US2
- **Phase 8 (Polish)**: Depends on all previous phases

### User Story Dependencies

- **US1 (P1)**: Requires ConfigGenerator → then independent
- **US2 (P1)**: Independent after Foundational
- **US3 (P2)**: Requires ConfigGenerator → migration can proceed in parallel
- **US4 (P2)**: Independent after Foundational
- **US5 (P3)**: May benefit from US2 skip message patterns

### Parallel Opportunities

```
Phase 2: T004 → T005, T006, T007 (T007 parallel after T004)

Phase 3: T008 → T009 → T010 → T011, T012 (sequential)
         T013 can run parallel after T009

Phase 4: T014, T015 (parallel audit)
         T016 → T17, T18, T19 (sequential refactors)

Phase 5: T020-T027 all parallel (different files)
         T028 after all migrations

Phase 6: T029 → T030 → T031-T036 (T031-T036 parallel after T030)

Phase 7: T037 → T038, T039, T040 (parallel after audit)
         T041 → T042 (sequential)
```

---

## Implementation Strategy

### MVP First (P1 Stories)

1. Complete Phase 1: Setup
2. Complete Phase 2: Foundational (ConfigGenerator, fixtures)
3. Complete Phase 3: US1 - Fix Sentiment Oracle Validation
4. Complete Phase 4: US2 - Eliminate Dual-Outcome Assertions
5. **STOP and VALIDATE**: Core test quality issues fixed

### Incremental Delivery

1. Setup + Foundational → Foundation ready
2. Add US1 → Sentiment tests have oracle validation
3. Add US2 → No more false-positive dual-outcome tests
4. Add US3 → All tests use synthetic data
5. Add US4 → Error handling paths tested
6. Add US5 → Skip rate optimized
7. Polish → All success criteria verified

---

## Notes

- All changes are test infrastructure only (no production code changes)
- Tests use `@pytest.mark.preprod` for real AWS E2E tests
- Synthetic seed from `E2E_TEST_SEED` environment variable
- Oracle tolerance is ±0.01 for floating point comparison
- SkipInfo format: `SKIPPED: {condition}\nReason: {reason}\nTo run: {remediation}`
