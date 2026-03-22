# Feature 1239: Research Notes

## Existing Chaos Infrastructure Analysis

### chaos.py API Surface (Feature 1237)

The plan executor reuses these functions from `src/lambdas/dashboard/chaos.py`:

| Function | Signature | Purpose |
|---|---|---|
| `create_experiment` | `(scenario_type, blast_radius, duration_seconds, parameters) -> dict` | Creates DynamoDB record, validates inputs |
| `start_experiment` | `(experiment_id) -> dict` | Checks gate, captures baseline, injects fault |
| `stop_experiment` | `(experiment_id) -> dict` | Restores from SSM snapshot, captures post-chaos health |
| `get_experiment_report` | `(experiment_id) -> dict` | Generates verdict: CLEAN/COMPROMISED/INCONCLUSIVE |
| `get_experiment` | `(experiment_id) -> dict | None` | Reads experiment from DynamoDB |
| `list_experiments` | `(status, limit) -> list[dict]` | Lists experiments, supports status GSI |
| `check_environment_allowed` | `() -> None` | Raises if environment is prod |

**Key constraints from chaos.py:**
- `duration_seconds` must be 5-300
- `blast_radius` must be 10-100
- Valid scenarios: `dynamodb_throttle`, `ingestion_failure`, `lambda_cold_start`, `trigger_failure`, `api_timeout`
- Valid statuses: `pending`, `running`, `completed`, `failed`, `stopped`

### Gate/Kill Switch (Feature 1238)

The plan executor inherits all safety mechanisms:
- `_check_gate()` returns "armed", "disarmed", or raises ChaosError for "triggered"
- Gate state "disarmed" = dry-run (no infra changes, signals recorded)
- Kill switch "triggered" = all operations blocked
- Fail-closed: SSM unreachable = blocked

### Shell Scripts

The bash scripts (`inject.sh`, `restore.sh`, `status.sh`, `andon-cord.sh`) are independent of the Python API. The plan executor uses the Python API (chaos.py) directly, not the shell scripts.

### CloudWatch Assertions Data Sources

**Alarm state checking** requires `cloudwatch:DescribeAlarms`:
- Already used in `_capture_baseline()` for health checks
- Alarm names follow pattern: `{env}-{suffix}` (verified from Terraform)

**Metric statistics** requires `cloudwatch:GetMetricStatistics`:
- Not currently used in chaos.py but available via boto3
- Custom metrics in namespaces: SentimentAnalyzer, SentimentAnalyzer/Reliability, SentimentAnalyzer/Ingestion, SentimentAnalyzer/SSE, SentimentAnalyzer/Canary
- AWS metrics in namespaces: AWS/Lambda, AWS/DynamoDB, AWS/SQS, AWS/SNS

### IAM Permissions

The chaos dashboard Lambda already has:
- `cloudwatch:DescribeAlarms` (used in `_capture_baseline`)
- `dynamodb:*` on chaos-experiments table
- `ssm:GetParameter`, `ssm:PutParameter`, `ssm:DeleteParameter` for kill switch/snapshots
- `lambda:GetFunctionConfiguration`, `lambda:PutFunctionConcurrency`, etc.

The `run-plan.py` script runs locally (not in Lambda), so it needs:
- AWS credentials with `cloudwatch:GetMetricStatistics` and `cloudwatch:DescribeAlarms`
- Same permissions as inject.sh/restore.sh for chaos operations
- OR: call the chaos API via HTTP (dashboard Lambda endpoints)

**Decision**: run-plan.py will import and call chaos.py functions directly (same as how tests do it), requiring the operator to have appropriate AWS credentials.

### Existing Test Patterns

`tests/unit/test_chaos_fis.py` and `tests/unit/test_chaos_gate.py` use moto for AWS service mocking:
- `@mock_aws` decorator for DynamoDB, Lambda, SSM, IAM, CloudWatch
- Test fixtures create chaos experiments table, Lambda functions
- Tests verify experiment lifecycle, gate behavior, kill switch

The plan executor tests should follow the same pattern.

## CloudWatch API Considerations

### GetMetricStatistics Latency

CloudWatch metrics have inherent lag:
- Standard resolution: 1-2 minutes before data appears
- High-resolution (1-second): available within 1 minute
- Custom metrics from Lambda: emitted at function completion, then 1-2 min delay

**Implication**: `within_seconds` values under 60 for metric-based assertions may be unreliable. The plan validator should warn about this.

### DescribeAlarms Response

```python
response = cloudwatch.describe_alarms(AlarmNames=[alarm_name])
alarm = response['MetricAlarms'][0]
# alarm['StateValue'] is one of: 'OK', 'ALARM', 'INSUFFICIENT_DATA'
```

Alarm state transitions happen within seconds of threshold breach, but depend on evaluation periods. Most chaos alarms use 1-2 evaluation periods of 60-300 seconds.

### Metric Namespace Auto-Detection

To reduce plan verbosity, the executor auto-detects namespace:

| Metric Pattern | Namespace |
|---|---|
| `NewItemsIngested` | `SentimentAnalyzer` |
| `Errors`, `Throttles`, `Duration`, `Invocations` | `AWS/Lambda` |
| `SilentFailure/*` | `SentimentAnalyzer/Reliability` |
| `ConnectionCount` | `SentimentAnalyzer/SSE` |
| `CollisionRate`, `*ApiErrors`, `*ApiCalls`, `CircuitBreakerOpen` | `SentimentAnalyzer/Ingestion` |
| `EmailsSent`, `EmailsAttempted`, `EmailQuotaUsed` | `SentimentAnalyzer/Notifications` |
| `CanaryHealth`, `completeness_ratio` | `SentimentAnalyzer/Canary` |

Explicit `namespace` in the plan overrides auto-detection.

## Scenario-Assertion Mapping

Which assertions are meaningful for each scenario:

| Scenario | Meaningful Assertions |
|---|---|
| `ingestion_failure` | `metric_equals_zero` on NewItemsIngested, `alarm_fires` on ingestion-lambda-throttles |
| `dynamodb_throttle` | `alarm_fires` on ingestion-lambda-errors or analysis-lambda-errors |
| `lambda_cold_start` | `metric_increases` on Duration (AWS/Lambda) |
| `trigger_failure` | `metric_equals_zero` on NewItemsIngested (after 1 schedule cycle) |
| `api_timeout` | `alarm_fires` on {service}-lambda-errors |

## Design Decisions

1. **Sequential execution only**: Parallel scenarios would create overlapping chaos states, making assertions unreliable and recovery complex.

2. **Python script, not shell**: The assertion engine needs boto3 CloudWatch API calls and JSON report generation. Python is the natural choice given the existing chaos.py codebase.

3. **Import chaos.py directly**: Rather than HTTP calls to the dashboard Lambda, the script imports chaos.py functions. This requires local AWS credentials but avoids network dependencies during chaos testing.

4. **Assertion polling with backoff**: Linear polling (every N seconds) up to timeout. No exponential backoff -- we want consistent observation windows.

5. **TIMEOUT != FAIL**: CloudWatch lag means assertions may not resolve in time even when the effect occurred. TIMEOUT is reported separately from FAIL for honest reporting.
