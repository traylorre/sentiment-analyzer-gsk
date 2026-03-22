# Feature 1239: Tasks

## Phase 1: Schema & Validation

- [ ] T1.1: Create `scripts/chaos/plan_schema.py` with pydantic models (ChaosPlan, ChaosScenario, ChaosAssertion)
- [ ] T1.2: Implement `load_plan(path: Path) -> ChaosPlan` YAML loading with validation
- [ ] T1.3: Validate scenario types against `chaos.py` valid_scenarios list
- [ ] T1.4: Validate assertion type/field combinations (metric_* needs `metric`, alarm_* needs `alarm`)
- [ ] T1.5: Add warning for metric assertions with `within_seconds < 60` (CloudWatch lag)
- [ ] T1.6: Create `tests/unit/test_plan_schema.py` with valid plan, each invalid case, edge cases
- [ ] T1.7: Test error messages are human-readable and actionable

## Phase 2: Assertion Engine

- [ ] T2.1: Create `scripts/chaos/assertion_engine.py` with AssertionResult dataclass (PASS/FAIL/TIMEOUT)
- [ ] T2.2: Implement metric namespace auto-detection mapping
- [ ] T2.3: Implement `check_metric_equals_zero()` with polling loop
- [ ] T2.4: Implement `check_metric_increases()` with baseline capture and delta check
- [ ] T2.5: Implement `check_alarm_fires()` with polling loop
- [ ] T2.6: Implement `check_alarm_ok()` with polling loop
- [ ] T2.7: Create `tests/unit/test_assertion_engine.py` with moto CloudWatch mocks
- [ ] T2.8: Test TIMEOUT behavior when assertion never resolves

## Phase 3: Plan Executor

- [ ] T3.1: Create `scripts/chaos/plan_executor.py` with PlanExecutor class
- [ ] T3.2: Implement concurrent execution guard (DynamoDB query for running experiments)
- [ ] T3.3: Implement sequential scenario execution loop with chaos.py integration
- [ ] T3.4: Implement mid-plan failure handling (stop current, skip remaining)
- [ ] T3.5: Implement kill switch check between scenarios
- [ ] T3.6: Implement dry-run mode (validate + preview)
- [ ] T3.7: Implement consolidated JSON report generation
- [ ] T3.8: Write report to file with timestamp-based filename
- [ ] T3.9: Create `tests/unit/test_plan_executor.py` with mocked chaos.py and assertion engine
- [ ] T3.10: Test mid-plan failure produces correct partial report
- [ ] T3.11: Test concurrent execution guard blocks when running experiment exists

## Phase 4: API Endpoint & Dashboard UI

- [ ] T4.1: Add `POST /chaos/plans/{name}/execute` to dashboard handler.py (resolves plan name to YAML file, calls PlanExecutor, returns report)
- [ ] T4.2: Add plan execution UI to chaos.html (plan selector dropdown + "Run Plan" button + live status display)
- [ ] T4.3: Create `scripts/chaos/run-plan.py` as thin CLI wrapper that calls the API endpoint (with fallback to direct PlanExecutor for offline use)
- [ ] T4.4: Wire CLI to PlanExecutor with proper error handling and exit codes
- [ ] T4.5: Create `scripts/chaos/plans/ingestion-resilience.yaml` example plan
- [ ] T4.6: Create `scripts/chaos/plans/data-layer-resilience.yaml` example plan
- [ ] T4.7: Create `scripts/chaos/plans/full-stack-resilience.yaml` example plan
- [ ] T4.8: Add `chaos-reports/` to `.gitignore`
- [ ] T4.9: Make `run-plan.py` executable (`chmod +x`)

## Phase 5: Integration Testing

- [ ] T5.1: End-to-end dry-run test with example plan YAML file
- [ ] T5.2: Test full plan loading -> validation -> (mocked) execution -> report generation
- [ ] T5.3: Verify report JSON schema matches FR-009
- [ ] T5.4: Test with all 3 example plans to verify they parse and validate

## Summary

| Phase | Tasks | Estimated Effort |
|---|---|---|
| Phase 1: Schema | 7 tasks | ~2 hours |
| Phase 2: Assertions | 8 tasks | ~3 hours |
| Phase 3: Executor | 11 tasks | ~3 hours |
| Phase 4: API & UI | 9 tasks | ~2 hours |
| Phase 5: Integration | 4 tasks | ~1 hour |
| **Total** | **39 tasks** | **~11 hours** |
