# Tasks: Chaos Injection End-to-End Wiring

**Feature Branch**: `1236-chaos-injection-wiring`
**Created**: 2026-03-21

## Phase 1: Wire ingestion_failure Scenario

### T-001: Add chaos import to ingestion handler
- [ ] Add `from src.lambdas.shared.chaos_injection import is_chaos_active` to imports in `src/lambdas/ingestion/handler.py`
- File: `src/lambdas/ingestion/handler.py` (line ~112, after existing shared imports)
- Acceptance: Import succeeds, no circular dependency

### T-002: Add chaos gate to ingestion handler
- [ ] Insert `is_chaos_active("ingestion_failure")` check in `lambda_handler()` after warmup check (line ~188) and before config loading
- [ ] When chaos active: log structured warning, emit `ChaosInjectionActive` metric with `Scenario=ingestion_failure` dimension, return early with `{"status": "chaos_active", "scenario": "ingestion_failure"}`
- File: `src/lambdas/ingestion/handler.py`
- Acceptance: FR-001, FR-002, FR-003, FR-008, FR-009 satisfied

### T-003: Write tests for ingestion chaos gate
- [ ] Create `tests/unit/test_chaos_ingestion_wiring.py`
- [ ] Test: chaos active -> handler returns early with `status=chaos_active` and zero articles
- [ ] Test: chaos inactive -> handler proceeds normally (mock remaining dependencies)
- [ ] Test: production environment -> `is_chaos_active` returns False, handler proceeds normally
- [ ] Test: no chaos table configured -> `is_chaos_active` returns False, handler proceeds normally
- [ ] Test: `ChaosInjectionActive` metric emitted when chaos active
- [ ] Test: structured log warning emitted when chaos active
- File: `tests/unit/test_chaos_ingestion_wiring.py` (new)
- Acceptance: SC-001, SC-002 verified

## Phase 2: Implement lambda_cold_start in chaos.py

### T-004: Implement lambda_cold_start start in chaos.py
- [ ] Replace `NotImplementedError` at line 605-607 with actual implementation
- [ ] Extract `delay_ms` from `experiment["parameters"]` with default of 3000
- [ ] Store `delay_ms` in experiment results alongside `started_at` and `injection_method`
- [ ] Set experiment status to "running" via `update_experiment_status()`
- File: `src/lambdas/dashboard/chaos.py` (lines 605-607)
- Acceptance: FR-004, FR-005 satisfied

### T-005: Implement lambda_cold_start stop in chaos.py
- [ ] Replace `NotImplementedError` at line 674-676 with actual implementation
- [ ] Preserve existing results, add `stopped_at` timestamp
- [ ] Set experiment status to "stopped" via `update_experiment_status()`
- File: `src/lambdas/dashboard/chaos.py` (lines 674-676)
- Acceptance: FR-006 satisfied

### T-006: Write tests for lambda_cold_start start/stop
- [ ] Add test class `TestStartExperimentLambdaColdStart` to `tests/unit/test_chaos_fis.py`
- [ ] Test: start lambda_cold_start with default delay -> status "running", results.delay_ms=3000
- [ ] Test: start lambda_cold_start with custom delay_ms=5000 -> results.delay_ms=5000
- [ ] Test: stop lambda_cold_start -> status "stopped", results.stopped_at present
- [ ] Test: start lambda_cold_start preserves injection_method in results
- [ ] Test: stop lambda_cold_start preserves started_at and delay_ms in results
- File: `tests/unit/test_chaos_fis.py`
- Acceptance: SC-003, SC-005 verified

## Phase 3: Add CloudWatch Metrics for Chaos Events

### T-007: Add ChaosInjectionActive metric to analysis handler
- [ ] In the existing chaos delay path (lines 118-126), add `emit_metric("ChaosInjectionActive", 1, dimensions={"Scenario": "lambda_cold_start"})` before the `time.sleep` call
- File: `src/lambdas/analysis/handler.py` (line ~119)
- Acceptance: FR-007 satisfied

### T-008: Verify emit_metric supports dimensions parameter
- [ ] Check `src/lib/metrics.py` `emit_metric()` signature confirms `dimensions` kwarg is supported
- [ ] If not supported, add dimensions support (should already be there based on existing usage in ingestion handler)
- File: `src/lib/metrics.py` (read-only verification)
- Acceptance: Dimensions kwarg works correctly

## Phase 4: Auto-Stop Expired Experiments

### T-013: Add auto-stop helper to chaos_injection.py
- [ ] Add `auto_stop_expired(scenario_type)` function to `src/lambdas/shared/chaos_injection.py` — query running experiments for the scenario, check if `started_at + duration_seconds < now`, if expired call `update_experiment_status(id, "completed", {stopped_at, auto_stopped: true})` via DynamoDB update
- File: `src/lambdas/shared/chaos_injection.py`
- Acceptance: FR-011 satisfied

### T-014: Wire auto-stop into chaos checks
- [ ] In ingestion handler: after `is_chaos_active()` check, call `auto_stop_expired("ingestion_failure")` (best-effort, wrapped in try/except)
- [ ] In analysis handler: after `get_chaos_delay_ms()` check, call `auto_stop_expired("lambda_cold_start")` (best-effort)
- Files: `src/lambdas/ingestion/handler.py`, `src/lambdas/analysis/handler.py`

### T-015: Write auto-stop tests
- [ ] Create tests in `tests/unit/test_chaos_auto_stop.py`: (1) expired experiment gets auto-stopped, (2) non-expired experiment stays running, (3) auto-stop failure doesn't crash Lambda, (4) auto-stopped experiment has `auto_stopped: true` in results
- File: `tests/unit/test_chaos_auto_stop.py` (new)

## Phase 5: DynamoDB Throttle Workaround (App-Level)

### T-016: Implement dynamodb_throttle start/stop in chaos.py
- [ ] The `dynamodb_throttle` scenario in `start_experiment()` currently tries AWS FIS. Replace with DynamoDB-flag pattern (same as ingestion_failure): set status to "running" with `injection_method: "dynamodb_flag"`, store `delay_ms` from parameters (default 500)
- [ ] Update `stop_experiment()` similarly — set status to "stopped"
- File: `src/lambdas/dashboard/chaos.py`
- Acceptance: FR-013 satisfied

### T-017: Wire DynamoDB throttle into ingestion and analysis
- [ ] In ingestion handler: check `is_chaos_active("dynamodb_throttle")`, if active call `get_chaos_delay_ms("dynamodb_throttle")` and sleep before DynamoDB writes. Emit `ChaosInjectionActive` metric with `Scenario=dynamodb_throttle`
- [ ] In analysis handler: same pattern before DynamoDB write operations
- Files: `src/lambdas/ingestion/handler.py`, `src/lambdas/analysis/handler.py`
- Acceptance: FR-012 satisfied

### T-018: Write DynamoDB throttle tests
- [ ] Add tests: (1) dynamodb_throttle start succeeds with default delay 500ms, (2) stop succeeds, (3) ingestion handler adds delay when active, (4) analysis handler adds delay when active
- File: `tests/unit/test_chaos_dynamodb_throttle.py` (new)

## Phase 6: Validation and Regression Testing

### T-019: Run existing chaos test suite
- [ ] Run `python -m pytest tests/unit/test_chaos_fis.py -v` -- all existing tests pass
- [ ] Run `python -m pytest tests/unit/test_chaos_injection.py -v` -- all existing tests pass
- [ ] No regressions from changes
- Acceptance: SC-007 verified

### T-020: Run full test suite
- [ ] Run `make test-local` -- all tests pass
- [ ] No regressions in any module
- Acceptance: SC-007 verified

### T-021: Verify production safety
- [ ] Confirm `is_chaos_active()` returns False in production environment (covered by existing test `test_production_environment_returns_false`)
- [ ] Confirm `get_chaos_delay_ms()` returns 0 in production environment (covered by existing test `test_production_environment_returns_zero`)
- [ ] Confirm `check_environment_allowed()` raises `EnvironmentNotAllowedError` in production (covered by existing test)
- Acceptance: SC-008, FR-010 verified

### T-022: Adversarial review of implementation
- [ ] Verify ingestion handler chaos check does NOT run before warmup check
- [ ] Verify ingestion handler chaos check does NOT affect event parsing or SNS publishing
- [ ] Verify chaos.py lambda_cold_start implementation stores delay_ms in the exact field path that `get_chaos_delay_ms()` reads (`results.delay_ms`)
- [ ] Verify no new environment variables are required beyond existing `CHAOS_EXPERIMENTS_TABLE`
- [ ] Check for any hardcoded delay values that should be configurable

## Dependency Graph

```
T-001 --> T-002 --> T-003
T-004 --> T-006
T-005 --> T-006
T-007 --> T-008
T-003, T-006, T-008 --> T-009 --> T-010 --> T-011 --> T-012
```

## Estimated Effort Per Phase

| Phase | Tasks | Lines (prod) | Lines (test) | Time |
|-------|-------|-------------|-------------|------|
| Phase 1 | T-001, T-002, T-003 | ~15 | ~80 | 30 min |
| Phase 2 | T-004, T-005, T-006 | ~20 | ~60 | 20 min |
| Phase 3 | T-007, T-008 | ~5 | ~10 | 10 min |
| Phase 4 | T-009, T-010, T-011, T-012 | 0 | 0 | 15 min |
| **Total** | **12 tasks** | **~40** | **~150** | **~75 min** |
