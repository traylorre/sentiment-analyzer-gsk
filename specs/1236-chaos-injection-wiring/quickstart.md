# Quickstart: Chaos Injection End-to-End Wiring

**Feature Branch**: `1236-chaos-injection-wiring`

## What This Feature Does

Connects the existing chaos testing infrastructure to actual Lambda behavior. After this feature:
- Starting an `ingestion_failure` experiment causes the ingestion Lambda to skip article fetching
- Starting a `lambda_cold_start` experiment causes the analysis Lambda to experience artificial delay
- Both scenarios emit CloudWatch metrics for observability

## Files Changed

| File | What Changed |
|------|-------------|
| `src/lambdas/ingestion/handler.py` | Added chaos gate (check `is_chaos_active` before fetching) |
| `src/lambdas/dashboard/chaos.py` | Implemented `lambda_cold_start` start/stop (replaced NotImplementedError) |
| `src/lambdas/analysis/handler.py` | Added `ChaosInjectionActive` metric to existing delay path |
| `tests/unit/test_chaos_ingestion_wiring.py` | New tests for ingestion chaos gate |
| `tests/unit/test_chaos_fis.py` | Extended tests for lambda_cold_start start/stop |

## How to Test Locally

```bash
# Run all chaos-related tests
python -m pytest tests/unit/test_chaos_injection.py tests/unit/test_chaos_fis.py tests/unit/test_chaos_ingestion_wiring.py -v

# Run full test suite to check for regressions
make test-local
```

## How to Test in Preprod

### Scenario 1: Ingestion Failure

```bash
# Create experiment
curl -X POST https://$PREPROD_API/chaos/experiments \
  -H "Content-Type: application/json" \
  -d '{"scenario_type": "ingestion_failure", "blast_radius": 100, "duration_seconds": 60}'

# Start experiment (use experiment_id from response)
curl -X POST https://$PREPROD_API/chaos/experiments/$EXPERIMENT_ID/start

# Wait for next ingestion cycle (up to 5 minutes)
# Check CloudWatch Logs for "Chaos: skipping ingestion"
# Check CloudWatch Metrics for ChaosInjectionActive (Scenario=ingestion_failure)

# Stop experiment
curl -X POST https://$PREPROD_API/chaos/experiments/$EXPERIMENT_ID/stop

# Verify next ingestion cycle processes articles normally
```

### Scenario 2: Lambda Cold Start

```bash
# Create experiment with custom delay
curl -X POST https://$PREPROD_API/chaos/experiments \
  -H "Content-Type: application/json" \
  -d '{"scenario_type": "lambda_cold_start", "blast_radius": 100, "duration_seconds": 120, "parameters": {"delay_ms": 5000}}'

# Start experiment
curl -X POST https://$PREPROD_API/chaos/experiments/$EXPERIMENT_ID/start

# Trigger analysis (publish test message to SNS or wait for ingestion)
# Check CloudWatch Metrics for InferenceLatencyMs spike
# Check CloudWatch Metrics for ChaosInjectionActive (Scenario=lambda_cold_start)

# Stop experiment
curl -X POST https://$PREPROD_API/chaos/experiments/$EXPERIMENT_ID/stop
```

## Key Design Decisions

1. **App-level injection**: Uses DynamoDB flags + application code checks (not AWS FIS)
2. **Fail-safe**: All chaos detection returns safe defaults on any error (False/0)
3. **Production safety**: Chaos detection is double-gated (API blocks creation in prod + detection returns False in prod)
4. **dynamodb_throttle deferred**: Blocked by Terraform provider bug with FIS
