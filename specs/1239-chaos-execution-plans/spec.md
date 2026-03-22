# Feature 1239: Chaos Execution Plans

## Overview

A YAML-based plan format that defines repeatable chaos experiment sequences with assertions. Plans are executed via an **API-first** architecture: the primary interface is `POST /chaos/plans/{name}/execute` (called from the dashboard's "Run Plan" button), with `scripts/chaos/run-plan.py` as a thin CLI wrapper that calls the same API. The actual orchestration logic lives in an importable Python module (`scripts/chaos/plan_executor.py`) used by both the API handler and the CLI.

This feature builds on the existing chaos infrastructure (Feature 1237: external actor architecture, Feature 1238: gate/kill-switch) and adds structured, repeatable experiment orchestration with automated pass/fail verdicts.

## User Stories

### US1 (P1): Define and Validate YAML Plan Format

**As a** chaos engineer,
**I want** a well-defined YAML schema for chaos execution plans,
**So that** I can define repeatable experiment sequences with assertions that are validated before execution.

**Acceptance Criteria:**
- Plan schema supports: `name`, `version`, `environment`, `scenarios[]`
- Each scenario supports: `scenario` (type), `duration_seconds`, `parameters` (optional), `assertions[]`
- Each assertion supports: `type`, `metric`/`alarm`, `within_seconds`, optional `namespace`/`threshold`
- Schema validation runs before any scenario execution
- Meaningful error messages for invalid plans (missing fields, unknown scenario types, invalid assertion types)
- Plans are stored as YAML files in `scripts/chaos/plans/`

### US2 (P1): Execute Plan via Dashboard or CLI

**As a** chaos engineer,
**I want** to execute an entire plan from the dashboard ("Run Plan" button) or CLI,
**So that** I get consistent, reproducible experiment runs without manual orchestration.

**Acceptance Criteria:**
- Operator clicks "Run Plan" on dashboard -> plan executes sequentially -> results stream back
- `POST /chaos/plans/{name}/execute` endpoint accepts plan name and runs the sequence
- CLI (`scripts/chaos/run-plan.py`) is a thin wrapper that calls the API endpoint
- Orchestration logic lives in `scripts/chaos/plan_executor.py` (importable by both API handler and CLI)
- Executor runs scenarios sequentially (one at a time)
- Per scenario: create_experiment -> start_experiment -> sleep(duration) -> check assertions -> stop_experiment
- Reuses existing `chaos.py` API functions (create_experiment, start_experiment, stop_experiment, get_experiment_report)
- On mid-plan failure: stop current experiment, skip remaining scenarios, report partial results
- Respects kill switch and gate state (existing safety mechanisms)
- Dry-run mode skips infrastructure changes but validates plan and assertions
- Produces a consolidated JSON report at the end

### US3 (P2): Assertion Engine Checks CloudWatch Metrics and Alarms

**As a** chaos engineer,
**I want** automated assertions that check CloudWatch metrics and alarm states,
**So that** I can verify that chaos scenarios produce the expected observable effects.

**Acceptance Criteria:**
- Assertion type `metric_equals_zero`: verify a CloudWatch metric Sum equals 0 within a time window
- Assertion type `metric_increases`: verify a CloudWatch metric Sum is greater than a baseline within a time window
- Assertion type `alarm_fires`: verify a CloudWatch alarm transitions to ALARM state within a time window
- Assertion type `alarm_ok`: verify a CloudWatch alarm returns to OK state within a time window
- Assertions poll at configurable intervals (default: 10s) up to `within_seconds` timeout
- Each assertion reports: PASS, FAIL, or TIMEOUT with details

## Functional Requirements

### FR-001: YAML Plan Schema Definition

The plan schema SHALL conform to:

```yaml
name: <string, required>          # Human-readable plan name
version: <integer, required>      # Schema version (currently: 1)
environment: <string, required>   # Target environment (dev|preprod|test)
timeout_seconds: <int, optional>  # Global plan timeout (default: 1800)
scenarios:                        # Ordered list of scenarios
  - scenario: <string, required>  # One of: ingestion_failure, dynamodb_throttle,
                                  #   lambda_cold_start, trigger_failure, api_timeout
    duration_seconds: <int, req>  # How long to run (5-300)
    blast_radius: <int, optional> # Percentage (10-100, default: 100)
    parameters: <map, optional>   # Scenario-specific params (e.g., target, timeout, delay_ms)
    assertions:                   # Assertions to check after injection
      - type: <string, required>  # One of: metric_equals_zero, metric_increases,
                                  #   alarm_fires, alarm_ok
        metric: <str, conditional># CloudWatch metric name (required for metric_* types)
        alarm: <str, conditional> # CloudWatch alarm name suffix (required for alarm_* types)
        namespace: <str, optional># CloudWatch namespace (default: auto-detect)
        within_seconds: <int, req># Max seconds to wait for assertion
        threshold: <num, optional># For metric_increases: minimum delta
```

### FR-002: Plan Validation Before Execution

The executor SHALL validate the plan before executing any scenario:
- All required fields present and correctly typed
- `environment` is one of: dev, preprod, test (never prod)
- Each `scenario` type is a valid chaos scenario
- `duration_seconds` within range (5-300)
- Each assertion `type` is recognized
- Assertion fields match type requirements (metric-based types require `metric`, alarm-based types require `alarm`)
- `within_seconds` > 0 for all assertions

### FR-003: Sequential Scenario Execution

For each scenario in the plan, the executor SHALL:
1. Call `create_experiment(scenario_type, blast_radius, duration_seconds, parameters)`
2. Call `start_experiment(experiment_id)` (respects gate state)
3. Sleep for `duration_seconds`
4. Execute all assertions for this scenario
5. Call `stop_experiment(experiment_id)`
6. Call `get_experiment_report(experiment_id)` and attach assertion results

### FR-004: Mid-Plan Failure Handling

If any scenario fails during execution (ChaosError, AWS API error):
- Stop the current experiment immediately (best-effort)
- Mark remaining scenarios as SKIPPED
- Do NOT continue to the next scenario
- Generate a partial report with failure details
- Exit with non-zero status code

### FR-005: Assertion Type -- metric_equals_zero

Poll CloudWatch `GetMetricStatistics` for the specified metric. Assert that the Sum statistic equals 0 over the polling window. Auto-detect namespace from metric name when not specified:
- `NewItemsIngested` -> `SentimentAnalyzer`
- `Errors`, `Throttles`, `Duration` -> `AWS/Lambda`
- Explicit `namespace` overrides auto-detection

### FR-006: Assertion Type -- metric_increases

Poll CloudWatch `GetMetricStatistics` for the specified metric. Assert that the Sum statistic is greater than a baseline (captured before injection). Default threshold delta: > 0. Custom threshold via `threshold` field.

### FR-007: Assertion Type -- alarm_fires

Poll CloudWatch `DescribeAlarms` for the specified alarm. Assert that the alarm transitions to `ALARM` state within `within_seconds`. Alarm name is resolved as `{environment}-{alarm}` where `alarm` is the suffix provided in the plan.

### FR-008: Assertion Type -- alarm_ok

Poll CloudWatch `DescribeAlarms` for the specified alarm. Assert that the alarm is in `OK` state within `within_seconds`. Used to verify recovery after experiment stops.

### FR-009: Consolidated Plan Report

After all scenarios complete (or on failure), produce a JSON report:

```json
{
  "plan_name": "Ingestion Pipeline Resilience",
  "plan_version": 1,
  "environment": "preprod",
  "started_at": "2024-01-15T10:00:00Z",
  "completed_at": "2024-01-15T10:05:00Z",
  "overall_verdict": "PASS",
  "scenarios": [
    {
      "scenario": "ingestion_failure",
      "experiment_id": "uuid",
      "status": "completed",
      "verdict": "PASS",
      "assertions": [
        {"type": "metric_equals_zero", "metric": "NewItemsIngested", "result": "PASS", "details": "..."},
        {"type": "alarm_fires", "alarm": "ingestion-lambda-throttles", "result": "PASS", "details": "..."}
      ],
      "experiment_report": { /* from get_experiment_report */ }
    }
  ]
}
```

### FR-010: Dry-Run Mode

When `--dry-run` is passed or the gate is disarmed:
- Validate the plan (FR-002)
- Log what WOULD be executed per scenario
- Skip actual experiment creation and assertions
- Report plan as DRY_RUN with structure preview

### FR-011: HTTP API Endpoint

```
POST /chaos/plans/{name}/execute
```

Request body (optional):
```json
{
  "dry_run": false,
  "poll_interval": 10
}
```

Behavior:
- Resolves `{name}` to a plan file in `scripts/chaos/plans/{name}.yaml`
- Validates the plan (FR-002)
- Executes the plan using PlanExecutor from `scripts/chaos/plan_executor.py`
- Returns the consolidated JSON report (FR-009) on completion
- Returns 404 if plan file not found, 400 if plan invalid, 403 if environment not allowed
- Requires authenticated (non-anonymous) session (same auth as other chaos endpoints)

### FR-012: CLI Interface (Thin Wrapper)

```bash
python scripts/chaos/run-plan.py <plan-file> [options]
```

Options:
- `--dry-run`: Validate and preview without executing
- `--report-dir <path>`: Directory for JSON reports (default: `./chaos-reports/`)
- `--poll-interval <seconds>`: Assertion polling interval (default: 10)
- `--verbose`: Enable debug logging
- `--api-url <url>`: API base URL (default: reads from CHAOS_API_URL env or http://localhost:8000)

The CLI is a thin wrapper: it reads the plan file, calls `POST /chaos/plans/{name}/execute`, and writes the response to a report file. It can also call PlanExecutor directly for offline use.

### FR-013: Concurrent Plan Execution Guard

Before starting, check if another plan is currently running by:
- Querying DynamoDB for experiments with status=running
- If found, abort with error message identifying the running experiment
- This prevents conflicting chaos injections

## Edge Cases

### EC-001: Plan Validation Errors
Invalid plan YAML (syntax error, missing required fields, unknown scenario type) SHALL produce a clear error message and exit 1 without creating any experiments.

### EC-002: Mid-Plan Failure
If scenario N fails, scenarios N+1..M are marked SKIPPED. The current experiment is stopped (best-effort). Kill switch behavior is preserved.

### EC-003: Assertion Timeout
If an assertion does not become true within `within_seconds`, it is marked TIMEOUT (not FAIL). TIMEOUT assertions cause the scenario verdict to be INCONCLUSIVE, not FAIL.

### EC-004: Concurrent Plan Execution
If a running experiment is detected, the plan executor SHALL refuse to start and suggest waiting or pulling the andon cord.

### EC-005: Kill Switch Triggered Mid-Plan
If the kill switch transitions to "triggered" during plan execution, the executor SHALL abort immediately (no further scenarios) and report the interruption.

### EC-006: CloudWatch Data Lag
CloudWatch metrics have 1-2 minute lag. Assertions using `within_seconds < 60` may be unreliable for metric-based types. Validation SHALL warn (not block) when `within_seconds < 60` for metric_* assertions.

### EC-007: Alarm Name Resolution
Alarm names in plans use suffixes (e.g., `ingestion-lambda-throttles`). The executor prepends the environment prefix. If the alarm does not exist, the assertion fails with a descriptive error.

## Success Criteria

1. A valid YAML plan can define 1-5 scenarios with assertions and be validated without errors
2. `run-plan.py` executes all scenarios sequentially, reusing existing chaos.py API
3. Each supported assertion type correctly checks CloudWatch state
4. Mid-plan failures result in clean partial reports with remaining scenarios marked SKIPPED
5. Dry-run mode validates the plan and previews execution without infrastructure changes
6. The concurrent execution guard prevents overlapping chaos experiments
7. All 5 existing scenario types work in plans: ingestion_failure, dynamodb_throttle, lambda_cold_start, trigger_failure, api_timeout

## Data Sources for Assertions

### CloudWatch Alarm Names (from Terraform)

Pattern: `{environment}-{alarm-suffix}`

| Alarm Suffix | Module | Trigger Condition |
|---|---|---|
| `ingestion-lambda-errors` | cloudwatch-alarms | Lambda errors > threshold |
| `ingestion-lambda-throttles` | cloudwatch-alarms | Lambda throttles > 0 |
| `analysis-lambda-errors` | cloudwatch-alarms | Lambda errors > threshold |
| `analysis-lambda-throttles` | cloudwatch-alarms | Lambda throttles > 0 |
| `dashboard-lambda-errors` | cloudwatch-alarms | Lambda errors > threshold |
| `dashboard-lambda-throttles` | cloudwatch-alarms | Lambda throttles > 0 |
| `silent-failure-any` | cloudwatch-alarms | Silent failure count > 0 |
| `critical-composite` | cloudwatch-alarms | Any critical-tier alarm |
| `sentiment-lambda-ingestion-errors` | monitoring | Ingestion errors > 3 |
| `sentiment-no-new-items-1h` | monitoring | No items ingested for 1h |
| `sentiment-dlq-depth-exceeded` | monitoring | DLQ depth > 100 |
| `sentiment-tiingo-error-rate-high` | monitoring | Tiingo API errors > 5% |
| `sentiment-finnhub-error-rate-high` | monitoring | Finnhub API errors > 5% |
| `sentiment-circuit-breaker-open` | monitoring | Circuit breaker opened |

### CloudWatch Custom Metrics

| Metric | Namespace | Description |
|---|---|---|
| `NewItemsIngested` | `SentimentAnalyzer` | Items ingested after dedup |
| `Errors` | `AWS/Lambda` | Lambda invocation errors |
| `Throttles` | `AWS/Lambda` | Lambda throttle events |
| `Duration` | `AWS/Lambda` | Lambda execution duration |
| `SilentFailure/Count` | `SentimentAnalyzer/Reliability` | Silent failure path triggered |
| `ConnectionCount` | `SentimentAnalyzer/SSE` | SSE active connections |
| `CollisionRate` | `SentimentAnalyzer/Ingestion` | Cross-source collision rate |
| `CircuitBreakerOpen` | `SentimentAnalyzer/Ingestion` | Circuit breaker opened |

## Dependencies

- **chaos.py** (Feature 1237): create_experiment, start_experiment, stop_experiment, get_experiment_report
- **Kill switch/gate** (Feature 1238): SSM-based safety mechanisms
- **CloudWatch alarms** (Terraform): alarm names and custom metrics
- **DynamoDB**: chaos-experiments table for audit log and concurrent execution check

## Non-Goals

- Parallel scenario execution (sequential only for safety)
- Production environment support (prod is blocked at the environment validation layer)
- Custom assertion plugins (only the 4 built-in types for v1)
- Plan scheduling/cron (manual execution only)
