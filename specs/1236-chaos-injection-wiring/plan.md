# Implementation Plan: Chaos Injection End-to-End Wiring

**Feature Branch**: `1236-chaos-injection-wiring`
**Created**: 2026-03-21
**Estimated Effort**: Small (~80 lines of production code + ~150 lines of tests)

## Files to Modify

### Production Code

| File | Change | Lines Added | Risk |
|------|--------|-------------|------|
| `src/lambdas/ingestion/handler.py` | Add `is_chaos_active` import + chaos gate before fetching | ~15 | Low -- early return, no existing logic modified |
| `src/lambdas/dashboard/chaos.py` | Implement `lambda_cold_start` start/stop in `start_experiment()` and `stop_experiment()` | ~25 | Low -- replacing `NotImplementedError` stubs |
| `src/lambdas/analysis/handler.py` | Add `ChaosInjectionActive` metric emission (1 line) | ~5 | Low -- adding metric to existing chaos code path |

### Test Code

| File | Change | Lines Added |
|------|--------|-------------|
| `tests/unit/test_chaos_ingestion_wiring.py` (new) | Tests for ingestion handler chaos gate | ~80 |
| `tests/unit/test_chaos_fis.py` | Add tests for `lambda_cold_start` start/stop | ~60 |
| `tests/unit/test_chaos_injection.py` | No changes needed (existing tests cover detection) | 0 |

### Total Impact

- **3 files modified** (production)
- **1 new test file** + **1 test file extended**
- **~45 lines** production code added
- **~140 lines** test code added
- **0 files deleted**

## Change Details

### 1. Ingestion Handler Chaos Gate (handler.py)

Insert after the warmup check (line 186) and before config loading (line 214):

```python
from src.lambdas.shared.chaos_injection import is_chaos_active

# After warmup check, before config loading:
if is_chaos_active("ingestion_failure"):
    logger.warning(
        "Chaos: skipping ingestion",
        extra={
            "scenario": "ingestion_failure",
            "experiment_active": True,
            "lambda_function": "ingestion",
        },
    )
    emit_metric(
        "ChaosInjectionActive",
        1,
        dimensions={"Scenario": "ingestion_failure"},
    )
    return {
        "statusCode": 200,
        "body": {
            "status": "chaos_active",
            "scenario": "ingestion_failure",
            "message": "Ingestion skipped due to active chaos experiment",
        },
    }
```

**Why after warmup**: Warmup invocations should always succeed regardless of chaos state.
**Why before config**: Avoid hitting Secrets Manager and DynamoDB config scans when we know we're going to skip.
**Why statusCode 200**: The Lambda executed successfully -- it intentionally skipped. A non-200 would trigger alarms.

### 2. Chaos Module lambda_cold_start Implementation (chaos.py)

Replace `NotImplementedError` blocks:

**start_experiment (line 605-607)**:
```python
elif scenario_type == "lambda_cold_start":
    # Phase 4: Lambda delay injection via DynamoDB flag
    delay_ms = (parameters or {}).get("delay_ms", 3000)
    results = {
        "started_at": datetime.now(UTC).isoformat() + "Z",
        "injection_method": "dynamodb_flag",
        "delay_ms": delay_ms,
        "note": "Analysis Lambda will inject artificial delay while experiment is running",
    }
    update_experiment_status(experiment_id, "running", results)
```

**stop_experiment (line 674-676)**:
```python
elif scenario_type == "lambda_cold_start":
    # Phase 4: Stop Lambda delay injection
    results = experiment.get("results", {})
    results["stopped_at"] = datetime.now(UTC).isoformat() + "Z"
    update_experiment_status(experiment_id, "stopped", results)
```

**Why `parameters.delay_ms`**: Allows operators to configure different delay values per experiment (e.g., 1000ms for mild, 5000ms for severe). Falls back to 3000ms.
**Why mirror ingestion_failure pattern**: The `stop_experiment` for `ingestion_failure` (lines 667-672) follows this exact pattern. Consistency reduces cognitive load.

### 3. Analysis Handler Metric Addition (analysis/handler.py)

Add metric emission after the existing delay injection (line 119):

```python
if delay_ms > 0:
    emit_metric(
        "ChaosInjectionActive",
        1,
        dimensions={"Scenario": "lambda_cold_start"},
    )
    time.sleep(delay_ms / 1000.0)
    # existing log_structured call remains
```

**Why before sleep**: Emit metric before the delay so it is captured even if the Lambda times out during the sleep.

## Constitution Checklist

- [ ] No secrets hardcoded
- [ ] No `prevent_destroy` changes needed (no new stateful resources)
- [ ] Cost impact: Zero (CloudWatch metrics already emitted, no new resources)
- [ ] GPG signing: All commits signed with `git commit -S`
- [ ] Tests: Unit tests for all new code paths
- [ ] No new dependencies introduced
- [ ] Fail-safe design: `is_chaos_active()` returns False on any error

## Risk Assessment

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| `is_chaos_active()` adds latency to every ingestion invocation | Low | Low | DynamoDB query is <10ms; function is fail-safe with 0ms overhead if table not configured |
| `CHAOS_EXPERIMENTS_TABLE` not configured in ingestion Lambda env | Medium | Low | `is_chaos_active()` returns False if env var empty -- zero impact |
| Operator forgets to stop experiment | Medium | Medium | Duration field is informational; auto-stop is future work. Dashboard shows running experiments prominently |
| Concurrent same-type experiments cause confusion | Low | Low | `is_chaos_active()` returns True if ANY matching experiment is running. Multiple experiments just mean chaos is active |

## Rollback Plan

All changes are additive. If issues arise:
1. Stop all running chaos experiments via the dashboard
2. The system immediately returns to normal behavior (next invocation)
3. If code needs to be reverted, the only production-affecting change is the `is_chaos_active()` gate in ingestion -- removing that import and if-block restores original behavior
