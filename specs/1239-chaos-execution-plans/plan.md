# Feature 1239: Implementation Plan

## Architecture

```
scripts/chaos/run-plan.py          # CLI entry point
scripts/chaos/plan_schema.py       # YAML schema validation (pydantic models)
scripts/chaos/plan_executor.py     # Orchestration engine
scripts/chaos/assertion_engine.py  # CloudWatch assertion checks
scripts/chaos/plans/               # Example plan YAML files
chaos-reports/                     # Generated JSON reports (gitignored)
tests/unit/test_plan_schema.py     # Schema validation tests
tests/unit/test_plan_executor.py   # Executor logic tests
tests/unit/test_assertion_engine.py # Assertion engine tests
```

## Phases

### Phase 1: Schema & Validation (US1)
**Effort**: ~2 hours
**Files**: `plan_schema.py`, `test_plan_schema.py`

1. Define pydantic models for plan schema (ChaosPlan, ChaosScenario, ChaosAssertion)
2. Implement YAML loading and validation
3. Validate scenario types against chaos.py valid_scenarios
4. Validate assertion types and required fields per type
5. Warn on metric assertions with within_seconds < 60
6. Unit tests: valid plans, each invalid case, edge cases

### Phase 2: Assertion Engine (US3)
**Effort**: ~3 hours
**Files**: `assertion_engine.py`, `test_assertion_engine.py`

1. Implement CloudWatch client wrapper (get_metric_statistics, describe_alarms)
2. Implement metric namespace auto-detection
3. Implement `check_metric_equals_zero(metric, namespace, within_seconds, poll_interval)`
4. Implement `check_metric_increases(metric, namespace, baseline, within_seconds, threshold, poll_interval)`
5. Implement `check_alarm_fires(alarm_name, within_seconds, poll_interval)`
6. Implement `check_alarm_ok(alarm_name, within_seconds, poll_interval)`
7. Unit tests with moto mocks for CloudWatch

### Phase 3: Plan Executor (US2)
**Effort**: ~3 hours
**Files**: `plan_executor.py`, `test_plan_executor.py`

1. Implement concurrent execution guard (query DynamoDB for running experiments)
2. Implement sequential scenario execution loop
3. Integrate assertion engine after each scenario's duration
4. Implement mid-plan failure handling (stop current, skip remaining)
5. Implement kill switch monitoring during execution
6. Implement dry-run mode
7. Generate consolidated JSON report
8. Unit tests with mocked chaos.py functions

### Phase 4: CLI & Examples (US2)
**Effort**: ~1 hour
**Files**: `run-plan.py`, `plans/*.yaml`

1. Implement argparse CLI (plan file, --dry-run, --report-dir, --poll-interval, --verbose)
2. Wire CLI to plan_executor
3. Create example plan files:
   - `ingestion-resilience.yaml` (ingestion_failure + trigger_failure)
   - `data-layer-resilience.yaml` (dynamodb_throttle)
   - `full-stack-resilience.yaml` (all 5 scenarios)
4. Add chaos-reports/ to .gitignore

### Phase 5: Integration Testing
**Effort**: ~1 hour
**Files**: `test_plan_executor.py` (extended)

1. End-to-end dry-run test with example plan
2. Test plan loading from YAML file
3. Test report generation format
4. Test concurrent execution guard

## Dependency Graph

```
Phase 1 (Schema) ──┐
                    ├── Phase 3 (Executor) ── Phase 4 (CLI)
Phase 2 (Assertions)┘                           │
                                                 └── Phase 5 (Integration)
```

Phases 1 and 2 can be developed in parallel. Phase 3 depends on both. Phase 4 depends on Phase 3.

## Risk Mitigation

| Risk | Mitigation |
|---|---|
| CloudWatch metric lag causes false TIMEOUT | Use within_seconds >= 120 for metric assertions; warn on < 60 |
| chaos.py import path issues from scripts/ | Use sys.path manipulation or package import; test in CI |
| Concurrent plan execution race condition | Use DynamoDB consistent read for running experiments check |
| Plan executor crashes mid-scenario | Wrap in try/finally to always attempt stop_experiment |
| Alarm name mismatch between plan and Terraform | Validate alarm existence before starting scenarios (pre-flight) |

## Cost Impact

No new AWS resources. CloudWatch API calls during assertion checking:
- `GetMetricStatistics`: ~$0.01 per 1000 requests
- `DescribeAlarms`: ~$0.01 per 1000 requests
- Typical plan run: ~50-100 API calls = negligible cost
