# Requirements Checklist: 1236-chaos-injection-wiring

## Functional Requirements

- [ ] **FR-001**: Ingestion Lambda checks `is_chaos_active("ingestion_failure")` before fetching
  - File: `src/lambdas/ingestion/handler.py` (insert after warmup check, ~line 188)
  - Test: `tests/unit/test_chaos_ingestion_wiring.py::TestIngestionChaosGate::test_chaos_active_skips_ingestion`
  - Verification: Mock `is_chaos_active` to return True, assert handler returns `{"status": "chaos_active"}` with zero articles

- [ ] **FR-002**: Ingestion Lambda emits `ChaosInjectionActive` metric with `Scenario=ingestion_failure` dimension
  - File: `src/lambdas/ingestion/handler.py` (within chaos gate block)
  - Test: `tests/unit/test_chaos_ingestion_wiring.py::TestIngestionChaosGate::test_chaos_metric_emitted`
  - Verification: Mock `emit_metric`, assert called with `"ChaosInjectionActive"` and dimensions `{"Scenario": "ingestion_failure"}`

- [ ] **FR-003**: Ingestion Lambda logs structured warning with chaos context
  - File: `src/lambdas/ingestion/handler.py` (within chaos gate block)
  - Test: `tests/unit/test_chaos_ingestion_wiring.py::TestIngestionChaosGate::test_chaos_log_emitted`
  - Verification: Capture log output, assert warning includes `scenario`, `experiment_active`, `lambda_function` fields

- [ ] **FR-004**: `chaos.py start_experiment()` supports `lambda_cold_start` scenario
  - File: `src/lambdas/dashboard/chaos.py` (replace NotImplementedError at lines 605-607)
  - Test: `tests/unit/test_chaos_fis.py::TestStartExperimentLambdaColdStart::test_start_lambda_cold_start_success`
  - Verification: Call `start_experiment()` with lambda_cold_start experiment, assert status "running" and results contain delay_ms

- [ ] **FR-005**: Default `delay_ms` of 3000 when `parameters.delay_ms` not provided
  - File: `src/lambdas/dashboard/chaos.py` (in lambda_cold_start start block)
  - Test: `tests/unit/test_chaos_fis.py::TestStartExperimentLambdaColdStart::test_start_lambda_cold_start_default_delay`
  - Verification: Create experiment with no parameters.delay_ms, start it, assert results.delay_ms == 3000

- [ ] **FR-006**: `chaos.py stop_experiment()` supports `lambda_cold_start` scenario
  - File: `src/lambdas/dashboard/chaos.py` (replace NotImplementedError at lines 674-676)
  - Test: `tests/unit/test_chaos_fis.py::TestStopExperimentLambdaColdStart::test_stop_lambda_cold_start_success`
  - Verification: Call `stop_experiment()` with running lambda_cold_start experiment, assert status "stopped" and results contain stopped_at

- [ ] **FR-007**: Analysis Lambda emits `ChaosInjectionActive` metric with `Scenario=lambda_cold_start`
  - File: `src/lambdas/analysis/handler.py` (add within existing delay_ms > 0 block, ~line 119)
  - Test: Existing test infrastructure or new test in test_chaos_ingestion_wiring.py
  - Verification: Mock `emit_metric`, assert called with `"ChaosInjectionActive"` and dimensions `{"Scenario": "lambda_cold_start"}`

- [ ] **FR-008**: Ingestion Lambda imports `is_chaos_active` from shared module
  - File: `src/lambdas/ingestion/handler.py` (import section, ~line 112)
  - Verification: No ImportError, no circular dependency

- [ ] **FR-009**: Chaos check occurs after warmup but before external API calls
  - File: `src/lambdas/ingestion/handler.py`
  - Verification: Code review -- chaos check is between lines 188-199 (after warmup return, before `_get_config()`)

- [ ] **FR-010**: Zero production impact -- all chaos paths return safe defaults
  - Files: `src/lambdas/shared/chaos_injection.py` (already implemented)
  - Tests: `tests/unit/test_chaos_injection.py::TestIsChaoActive::test_production_environment_returns_false`, `TestGetChaosDelayMs::test_production_environment_returns_zero`
  - Verification: Existing tests pass unchanged

## Implementation Tasks

- [ ] Add `is_chaos_active` import to ingestion handler
- [ ] Add chaos gate block to ingestion `lambda_handler()`
- [ ] Replace `NotImplementedError` in `start_experiment()` for `lambda_cold_start`
- [ ] Replace `NotImplementedError` in `stop_experiment()` for `lambda_cold_start`
- [ ] Add `ChaosInjectionActive` metric to analysis handler delay path
- [ ] Create `tests/unit/test_chaos_ingestion_wiring.py`
- [ ] Extend `tests/unit/test_chaos_fis.py` with lambda_cold_start tests
- [ ] Run full test suite to verify zero regressions

## Test Matrix

### Ingestion Chaos Gate

| Condition | `is_chaos_active` | Expected Behavior | Metric Emitted |
|-----------|-------------------|-------------------|----------------|
| Chaos active, preprod | True | Return early, skip fetching | ChaosInjectionActive |
| Chaos inactive, preprod | False | Proceed with normal ingestion | None |
| Production environment | False (hardcoded) | Proceed with normal ingestion | None |
| No chaos table configured | False (hardcoded) | Proceed with normal ingestion | None |
| DynamoDB error | False (fail-safe) | Proceed with normal ingestion | None |
| Warmup event + chaos active | N/A (warmup returns first) | Warmup returns before chaos check | None |

### Lambda Cold Start Start/Stop

| Action | Parameters | Expected Results |
|--------|-----------|-----------------|
| Start with default params | `{}` | `delay_ms=3000`, `injection_method="dynamodb_flag"` |
| Start with custom delay | `{"delay_ms": 5000}` | `delay_ms=5000` |
| Start with delay_ms=0 | `{"delay_ms": 0}` | `delay_ms=0` (no delay injected) |
| Stop running experiment | N/A | `stopped_at` added, `delay_ms` preserved |

### Analysis Chaos Metric

| Condition | `delay_ms` | Metric Emitted | Sleep Called |
|-----------|-----------|----------------|-------------|
| Chaos active, delay > 0 | 3000 | ChaosInjectionActive (Scenario=lambda_cold_start) | Yes |
| No chaos active | 0 | None | No |

## Acceptance Criteria Trace

| SC | Verified By | Status |
|----|------------|--------|
| SC-001 | `TestIngestionChaosGate::test_chaos_active_skips_ingestion` | Pending |
| SC-002 | `TestIngestionChaosGate::test_chaos_inactive_proceeds_normally` | Pending |
| SC-003 | `TestStartExperimentLambdaColdStart::test_start_lambda_cold_start_success` | Pending |
| SC-004 | Existing `test_chaos_injection.py::TestGetChaosDelayMs::test_returns_delay_when_experiment_active` | Pending |
| SC-005 | `TestStopExperimentLambdaColdStart::test_stop_lambda_cold_start_success` | Pending |
| SC-006 | `TestIngestionChaosGate::test_chaos_metric_emitted` + analysis metric test | Pending |
| SC-007 | `make test-local` (full suite) | Pending |
| SC-008 | Existing production safety tests (re-confirmed) | Pending |

## Spec-Plan-Tasks Drift Check

| Artifact | FR Count | Covered |
|----------|----------|---------|
| spec.md | FR-001 through FR-010 | All 10 FRs have tasks |
| plan.md | 3 changes detailed | Maps to T-001..T-007 |
| tasks.md | 12 tasks (T-001..T-012) | All FRs assigned to tasks |
| requirements.md | 10 FRs + test matrix | Traces to SC-001..SC-008 |

No drift detected. All requirements have:
1. A task assignment in tasks.md
2. A file location in plan.md
3. A test verification in the test matrix
4. A success criteria mapping
