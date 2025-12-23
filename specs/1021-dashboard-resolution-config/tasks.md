# Implementation Tasks

Feature-1021 | Dashboard Resolution Config

## Phase 1: Configuration (US1, US2, US3)

- [x] [T001] Add RESOLUTIONS object to `src/dashboard/config.js` with all 8 resolution levels
- [x] [T002] Add each resolution with: key, displayName, durationSeconds, ttlSeconds
- [x] [T003] Add RESOLUTION_ORDER array: ["1m", "5m", "10m", "1h", "3h", "6h", "12h", "24h"]
- [x] [T004] Add DEFAULT_RESOLUTION constant: "5m"
- [x] [T005] Add TIMESERIES endpoint to ENDPOINTS: "/api/v2/timeseries"
- [x] [T006] Add Object.freeze(CONFIG.RESOLUTIONS) after declaration
- [x] [T007] Add Object.freeze(CONFIG.RESOLUTION_ORDER) after declaration

## Phase 2: Testing (SC-002, SC-005)

- [x] [T008] Create `tests/unit/dashboard/test_config_resolution.py` with TestResolutionConfig class
- [x] [T009] Add test_all_resolutions_defined: verify 8 resolutions exist
- [x] [T010] [P] Add test_ttl_matches_python_model: compare TTLs with Resolution.ttl_seconds
- [x] [T011] [P] Add test_duration_matches_python_model: compare durations with Resolution.duration_seconds
- [x] [T012] Add test_default_resolution_is_5m: verify DEFAULT_RESOLUTION = "5m"
- [x] [T013] Add test_timeseries_endpoint_exists: verify ENDPOINTS.TIMESERIES defined

## Phase 3: Validation (SC-001, SC-004)

- [x] [T014] Run existing dashboard tests to verify no regressions
- [x] [T015] Verify CONFIG.ENDPOINTS unchanged (existing endpoints still present)

## Summary

| Metric | Count |
|--------|-------|
| Total Tasks | 15 |
| Phase 1 (Config) | 7 |
| Phase 2 (Testing) | 6 |
| Phase 3 (Validation) | 2 |
| Parallel Opportunities | 2 tasks marked [P] |

## MVP Scope

All 15 tasks COMPLETE.
