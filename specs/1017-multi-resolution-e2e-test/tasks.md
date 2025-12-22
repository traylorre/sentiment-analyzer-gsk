# Tasks: Multi-Resolution Dashboard E2E Test Suite

## Phase 1: Setup

- [x] [T001] Create test file `tests/e2e/test_multi_resolution_dashboard.py`
- [x] [T002] Add imports, pytestmark, and fixtures

## Phase 2: US1 - Dashboard Load Tests

- [x] [T003] [US1] Implement `test_initial_load_within_500ms`
- [x] [T004] [US1] Implement `test_skeleton_ui_shown_not_spinner`
- [x] [T005] [US1] Implement `test_default_resolution_is_5m`

## Phase 3: US2 - Resolution Switching Tests

- [x] [T006] [US2] Implement `test_switch_completes_within_100ms`
- [x] [T007] [US2] Implement `test_all_8_resolutions_available`
- [x] [T008] [US2] Implement `test_cached_resolution_loads_instantly`

## Phase 4: US3 - Live Updates Tests

- [x] [T009] [US3] Implement `test_sse_connection_established`
- [x] [T010] [US3] Implement `test_partial_bucket_indicator_visible`
- [x] [T011] [US3] Implement `test_heartbeat_received_within_3s`

## Phase 5: US4 - Historical Scrolling Tests

- [x] [T012] [US4] Implement `test_scroll_left_loads_previous_range`
- [x] [T013] [US4] Implement `test_cached_range_loads_instantly`
- [x] [T014] [US4] Implement `test_live_data_appends_at_edge`

## Phase 6: US5 - Multi-Ticker & Connectivity Tests

- [x] [T015] [US5] Implement `test_10_tickers_load_within_1_second`
- [x] [T016] [US5] Implement `test_auto_reconnection_indicator`
- [x] [T017] [US5] Implement `test_fallback_polling_mode_indicator`

## Phase 7: Validation

- [x] [T018] Run `pytest --collect-only tests/e2e/test_multi_resolution_dashboard.py` - 15 tests collected
- [x] [T019] Run `ruff check tests/e2e/test_multi_resolution_dashboard.py` - All checks passed
- [x] [T020] Verify all 15 tests are collected - PASS

## Summary

| Phase | Tasks | Description |
|-------|-------|-------------|
| 1 | T001-T002 | Setup |
| 2 | T003-T005 | US1: Dashboard Load |
| 3 | T006-T008 | US2: Resolution Switching |
| 4 | T009-T011 | US3: Live Updates |
| 5 | T012-T014 | US4: Historical Scrolling |
| 6 | T015-T017 | US5: Multi-Ticker & Connectivity |
| 7 | T018-T020 | Validation |

**Total**: 20 tasks
**Complete**: 20/20 (100%)
