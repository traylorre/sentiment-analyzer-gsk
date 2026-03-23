# Feature 1239: Quickstart Guide

## Prerequisites

- AWS credentials configured (same as for `scripts/chaos/inject.sh`)
- Python 3.13 with boto3, pyyaml, pydantic installed
- Chaos experiments table exists in DynamoDB (`{env}-chaos-experiments`)
- CloudWatch alarms deployed (via Terraform)

## Quick Usage

### 1. Validate a plan (dry-run)

```bash
python scripts/chaos/run-plan.py scripts/chaos/plans/ingestion-resilience.yaml --dry-run
```

Output:
```
[INFO] Loading plan: Ingestion Pipeline Resilience (v1)
[INFO] Validating plan...
[INFO] Plan valid: 2 scenarios, 4 assertions
[INFO] DRY-RUN: Skipping execution
[INFO] Scenario 1: ingestion_failure (60s)
[INFO]   Would assert: metric_equals_zero(NewItemsIngested) within 30s
[INFO]   Would assert: alarm_fires(ingestion-lambda-throttles) within 30s
[INFO] Scenario 2: dynamodb_throttle (60s)
[INFO]   Would assert: metric_increases(DynamoDBWriteThrottles) within 60s
```

### 2. Execute a plan

```bash
python scripts/chaos/run-plan.py scripts/chaos/plans/ingestion-resilience.yaml
```

Output:
```
[INFO] Loading plan: Ingestion Pipeline Resilience (v1)
[INFO] Validating plan...
[INFO] Checking for running experiments...
[INFO] Scenario 1/2: ingestion_failure
[INFO]   Created experiment: abc-123-def
[INFO]   Started experiment (gate=armed)
[INFO]   Waiting 60s for chaos effects...
[INFO]   Checking assertions...
[INFO]   PASS: metric_equals_zero(NewItemsIngested) - Sum=0 within 25s
[INFO]   PASS: alarm_fires(ingestion-lambda-throttles) - ALARM within 18s
[INFO]   Stopping experiment...
[INFO]   Scenario verdict: PASS
[INFO] Scenario 2/2: dynamodb_throttle
[INFO]   ...
[INFO] Plan complete: 2/2 scenarios PASS
[INFO] Report saved: chaos-reports/ingestion-pipeline-resilience-20240115T100000.json
```

### 3. View the report

```bash
cat chaos-reports/ingestion-pipeline-resilience-20240115T100000.json | python -m json.tool
```

### 4. Write a custom plan

Create `scripts/chaos/plans/my-plan.yaml`:

```yaml
name: My Resilience Test
version: 1
environment: preprod
scenarios:
  - scenario: ingestion_failure
    duration_seconds: 60
    assertions:
      - type: alarm_fires
        alarm: ingestion-lambda-throttles
        within_seconds: 60
      - type: metric_equals_zero
        metric: NewItemsIngested
        within_seconds: 120

  - scenario: trigger_failure
    duration_seconds: 120
    assertions:
      - type: metric_equals_zero
        metric: NewItemsIngested
        within_seconds: 180
```

Then run:
```bash
python scripts/chaos/run-plan.py scripts/chaos/plans/my-plan.yaml --dry-run
python scripts/chaos/run-plan.py scripts/chaos/plans/my-plan.yaml
```

## CLI Reference

```
usage: run-plan.py [-h] [--dry-run] [--report-dir DIR] [--poll-interval SEC] [--verbose] plan_file

Execute a chaos execution plan.

positional arguments:
  plan_file             Path to YAML plan file

options:
  --dry-run             Validate and preview without executing
  --report-dir DIR      Directory for JSON reports (default: ./chaos-reports/)
  --poll-interval SEC   Assertion polling interval in seconds (default: 10)
  --verbose             Enable debug logging
```

## Safety Notes

- Plans cannot target `prod` environment (blocked by chaos.py validation)
- Kill switch is checked before each scenario
- If anything goes wrong, pull the andon cord: `scripts/chaos/andon-cord.sh <env>`
- Reports are saved even on failure for post-mortem analysis

## Example Plans

| Plan File | Scenarios | Purpose |
|---|---|---|
| `ingestion-resilience.yaml` | ingestion_failure, trigger_failure | Verify ingestion pipeline handles throttling and schedule disruption |
| `data-layer-resilience.yaml` | dynamodb_throttle | Verify DynamoDB write denial propagates as expected |
| `full-stack-resilience.yaml` | All 5 scenarios | Complete resilience regression suite |

## Troubleshooting

| Issue | Fix |
|---|---|
| "Running experiment detected" | Wait for it to finish or run `scripts/chaos/andon-cord.sh <env>` |
| Assertion TIMEOUT on metrics | Increase `within_seconds` (CloudWatch has 1-2 min lag) |
| "Kill switch triggered" | Run `scripts/chaos/restore.sh <env>` first |
| Import error for chaos.py | Run from project root: `PYTHONPATH=. python scripts/chaos/run-plan.py ...` |
| Alarm not found | Check alarm name with `aws cloudwatch describe-alarms --alarm-names {env}-{suffix}` |
