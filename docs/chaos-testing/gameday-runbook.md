# Chaos GameDay Runbook

**Purpose**: Step-by-step operator guide for executing a chaos plan against preprod.
**Estimated Duration**: 60 minutes (including pre-flight and post-mortem)
**Roles Required**: Operator (primary) + Buddy (secondary)

---

## Table of Contents

1. [Overview](#overview)
2. [Pre-Flight](#pre-flight)
3. [Execution: Ingestion Resilience Plan](#execution-ingestion-resilience-plan)
4. [Execution: Cold Start Resilience Plan](#execution-cold-start-resilience-plan)
5. [Post-Mortem](#post-mortem)
6. [Baseline Storage](#baseline-storage)
7. [Emergency Procedures](#emergency-procedures)
8. [Fallback: Direct Script Execution](#fallback-direct-script-execution)

---

## Overview

A Chaos GameDay is a controlled exercise where we intentionally inject faults into the preprod environment to validate system resilience. Each GameDay executes one or more chaos plans, observes system behavior, and produces a baseline report.

**What you will do**:
1. Verify the environment is healthy (pre-flight)
2. Arm the chaos gate
3. Execute each scenario in the plan sequentially
4. Observe metrics and verify assertions
5. Stop each scenario and verify recovery
6. Generate and store the baseline report
7. Disarm the gate and write up findings

**Key safety mechanisms**:
- SSM kill switch prevents accidental injection
- SSM snapshots preserve pre-chaos config for restoration
- Andon cord script for emergency recovery
- Buddy operator for redundant safety

---

## Pre-Flight

**Time estimate**: 10 minutes

### Step 1: Complete the pre-flight checklist

Open and complete every item in `docs/chaos-testing/preflight-checklist.md`.

```bash
# Quick health check
scripts/chaos/status.sh preprod
```

If ANY No-Go condition is triggered, **ABORT** and investigate.

### Step 2: Arm the chaos gate

The gate defaults to `disarmed` (dry-run mode). To execute real chaos:

```bash
aws ssm put-parameter \
  --name "/chaos/preprod/kill-switch" \
  --value "armed" \
  --type String \
  --overwrite
```

Verify:

```bash
aws ssm get-parameter \
  --name "/chaos/preprod/kill-switch" \
  --query "Parameter.Value" \
  --output text
# Expected: armed
```

### Step 3: Record start time

```bash
echo "GameDay started at: $(date -u +%Y-%m-%dT%H:%M:%SZ)"
```

---

## Execution: Ingestion Resilience Plan

**Plan file**: `chaos-plans/ingestion-resilience.yaml`
**Total time**: ~30 minutes (2 scenarios x 2 min injection + 5 min observation each, plus transitions)

### Scenario 1: ingestion_failure (Concurrency Zero)

**What it does**: Sets the ingestion Lambda's reserved concurrency to 0. All invocations are throttled by the Lambda runtime before execution begins.

#### 1.1 Create and start the experiment

**Option A: Via Dashboard API**

```bash
# Create experiment
EXPERIMENT=$(curl -s -X POST https://<DASHBOARD_FUNCTION_URL>/api/chaos/experiments \
  -H "Content-Type: application/json" \
  -d '{
    "scenario_type": "ingestion_failure",
    "duration_seconds": 120,
    "blast_radius": 100
  }')

EXPERIMENT_ID=$(echo "$EXPERIMENT" | python3 -c "import sys, json; print(json.load(sys.stdin)['experiment_id'])")
echo "Experiment ID: $EXPERIMENT_ID"

# Start experiment
curl -s -X POST "https://<DASHBOARD_FUNCTION_URL>/api/chaos/experiments/${EXPERIMENT_ID}/start" | python3 -m json.tool
```

**Option B: Via inject script**

```bash
scripts/chaos/inject.sh ingestion-failure preprod --duration 120
```

#### 1.2 Start timer

```bash
echo "Scenario 1 started at: $(date -u +%Y-%m-%dT%H:%M:%SZ)"
echo "Stop after 120 seconds ($(date -u -d '+2 minutes' +%H:%M:%S) UTC)"
```

#### 1.3 Observe (2 minutes)

Open CloudWatch console and watch these metrics:

| Metric | Namespace | Expected |
|--------|-----------|----------|
| Throttles | AWS/Lambda (ingestion) | Increases to match invocation rate |
| Errors | AWS/Lambda (ingestion) | Increases |
| Invocations | AWS/Lambda (ingestion) | Drops to 0 |
| ArticlesFetched | SentimentAnalyzer | Drops to 0 |

CloudWatch Logs Insights query:

```
fields @timestamp, @message
| filter @logStream like /sentiment-ingestion/
| sort @timestamp desc
| limit 20
```

**What to look for**: Throttle errors in logs, no successful invocations.

#### 1.4 Stop the experiment

**Option A: Via Dashboard API**

```bash
curl -s -X POST "https://<DASHBOARD_FUNCTION_URL>/api/chaos/experiments/${EXPERIMENT_ID}/stop" | python3 -m json.tool
```

**Option B: Via restore script**

```bash
scripts/chaos/restore.sh preprod
```

#### 1.5 Observe recovery (5 minutes)

Wait for the next EventBridge-triggered invocation (every 5 minutes).

| Metric | Expected |
|--------|----------|
| Invocations | Returns to normal rate |
| ArticlesFetched | Returns to non-zero |
| Errors | Returns to 0 |
| Alarm State | Transitions from ALARM back to OK |

```bash
# Check alarm state
aws cloudwatch describe-alarms \
  --alarm-names "preprod-ingestion-lambda-errors" \
  --query "MetricAlarms[].StateValue" \
  --output text
# Expected after recovery: OK
```

#### 1.6 Generate report

```bash
# Via Dashboard API
REPORT=$(curl -s "https://<DASHBOARD_FUNCTION_URL>/api/chaos/experiments/${EXPERIMENT_ID}/report")
echo "$REPORT" | python3 -m json.tool

# Save report
echo "$REPORT" | python3 -m json.tool > "/tmp/report-ingestion-failure-$(date +%Y-%m-%d).json"
```

Record the verdict: ________ (expected: CLEAN)

---

### Scenario 2: dynamodb_throttle (Deny-Write Policy)

**What it does**: Attaches an IAM deny-write policy to the ingestion and analysis Lambda execution roles. DynamoDB write operations fail with AccessDeniedException.

**Important**: Wait at least 2 minutes after Scenario 1 recovery before starting Scenario 2. This prevents overlapping effects.

#### 2.1 Create and start the experiment

```bash
# Create experiment
EXPERIMENT2=$(curl -s -X POST https://<DASHBOARD_FUNCTION_URL>/api/chaos/experiments \
  -H "Content-Type: application/json" \
  -d '{
    "scenario_type": "dynamodb_throttle",
    "duration_seconds": 120,
    "blast_radius": 100
  }')

EXPERIMENT2_ID=$(echo "$EXPERIMENT2" | python3 -c "import sys, json; print(json.load(sys.stdin)['experiment_id'])")
echo "Experiment ID: $EXPERIMENT2_ID"

# Start experiment
curl -s -X POST "https://<DASHBOARD_FUNCTION_URL>/api/chaos/experiments/${EXPERIMENT2_ID}/start" | python3 -m json.tool
```

**Note**: IAM policy propagation takes up to 60 seconds. The inject script sleeps 5 seconds, but full propagation may take longer. Effects may be delayed.

#### 2.2 Start timer

```bash
echo "Scenario 2 started at: $(date -u +%Y-%m-%dT%H:%M:%SZ)"
echo "Stop after 120 seconds ($(date -u -d '+2 minutes' +%H:%M:%S) UTC)"
```

#### 2.3 Observe (2 minutes)

| Metric | Namespace | Expected |
|--------|-----------|----------|
| Errors | AWS/Lambda (ingestion) | Increases (AccessDenied on writes) |
| Errors | AWS/Lambda (analysis) | Increases (AccessDenied on writes) |
| SystemErrors | AWS/DynamoDB (items table) | May increase |

CloudWatch Logs Insights query:

```
fields @timestamp, @message
| filter @message like /AccessDenied/
| sort @timestamp desc
| limit 20
```

**What to look for**: AccessDeniedException in Lambda logs, error count increasing.

#### 2.4 Stop the experiment

```bash
curl -s -X POST "https://<DASHBOARD_FUNCTION_URL>/api/chaos/experiments/${EXPERIMENT2_ID}/stop" | python3 -m json.tool
```

#### 2.5 Observe recovery (5 minutes)

| Metric | Expected |
|--------|----------|
| Errors (ingestion) | Returns to 0 |
| Errors (analysis) | Returns to 0 |
| Successful writes | Resume on next invocation |

**DLQ check** (manual assertion):

```bash
# Check SQS DLQ depth (if DLQ is configured)
aws sqs get-queue-attributes \
  --queue-url "https://sqs.us-east-1.amazonaws.com/<ACCOUNT_ID>/preprod-sentiment-dlq" \
  --attribute-names ApproximateNumberOfMessages \
  --query "Attributes.ApproximateNumberOfMessages" \
  --output text
# If > 0, note for post-mortem but do not block GameDay
```

#### 2.6 Generate report

```bash
REPORT2=$(curl -s "https://<DASHBOARD_FUNCTION_URL>/api/chaos/experiments/${EXPERIMENT2_ID}/report")
echo "$REPORT2" | python3 -m json.tool > "/tmp/report-dynamodb-throttle-$(date +%Y-%m-%d).json"
```

Record the verdict: ________ (expected: CLEAN)

---

## Execution: Cold Start Resilience Plan

**Plan file**: `chaos-plans/cold-start-resilience.yaml`
**Prerequisite**: Ingestion resilience plan completed first.

Follow the same pattern as above. Refer to the plan file for scenario-specific parameters and observation metrics. Key differences:

- **Scenario 1 (lambda_cold_start)**: Reduces analysis Lambda memory to 128MB. Observe `Duration` metric increase.
- **Scenario 2 (api_timeout)**: Sets ingestion Lambda timeout to 1s. Observe all invocations failing.

---

## Post-Mortem

**Time estimate**: 15 minutes

### Step 1: Disarm the gate

```bash
aws ssm put-parameter \
  --name "/chaos/preprod/kill-switch" \
  --value "disarmed" \
  --type String \
  --overwrite
```

### Step 2: Review reports

For each scenario, review the report and document:

| Question | Scenario 1 | Scenario 2 |
|----------|-----------|-----------|
| Verdict | | |
| Actual recovery time | | |
| Expected recovery time | 5 min | 5 min |
| Unexpected behaviors | | |
| Alarms fired as expected? | | |
| Manual intervention needed? | | |

### Step 3: Verify assertions

Review each assertion from the chaos plan:

| Assertion ID | Description | Result (PASS/FAIL) | Notes |
|-------------|-------------|-------------------|-------|
| assert-1 | Throttle detected | | |
| assert-2 | Alarm fires | | |
| assert-3 | Recovery within 5 min | | |
| assert-4 | Write errors | | |
| assert-5 | Write recovery | | |
| assert-6 | No data loss | | |

### Step 4: Document findings

Write a brief summary:

```
GameDay Date: YYYY-MM-DD
Plan: ingestion-resilience v1.0
Overall Verdict: CLEAN / RECOVERY_INCOMPLETE / COMPROMISED
Key Findings:
  1. [finding]
  2. [finding]
Follow-up Actions:
  1. [action]
  2. [action]
```

### Step 5: Notify team

Post in Slack: "Chaos GameDay complete. Overall verdict: [verdict]. Report stored at reports/chaos/baseline-ingestion-resilience-YYYY-MM-DD.json"

---

## Baseline Storage

### Step 1: Create reports directory

```bash
mkdir -p reports/chaos
```

### Step 2: Store baseline reports

```bash
# Copy from /tmp to repo
cp /tmp/report-ingestion-failure-$(date +%Y-%m-%d).json \
   reports/chaos/baseline-ingestion-resilience-$(date +%Y-%m-%d).json

cp /tmp/report-dynamodb-throttle-$(date +%Y-%m-%d).json \
   reports/chaos/baseline-dynamodb-throttle-$(date +%Y-%m-%d).json
```

### Step 3: Commit to repo

```bash
git add chaos-plans/ reports/chaos/ docs/chaos-testing/
git commit -S -m "feat(chaos): First GameDay baseline - ingestion resilience

Executed ingestion-resilience chaos plan against preprod.
Scenarios: ingestion_failure, dynamodb_throttle
Overall verdict: [CLEAN/RECOVERY_INCOMPLETE]

Reports stored as baseline for future diff."
```

---

## Emergency Procedures

### Pull the Andon Cord

If anything goes wrong during the GameDay, immediately:

```bash
scripts/chaos/andon-cord.sh preprod
```

This will:
1. Set the kill switch to `triggered`
2. Read all SSM snapshots
3. Restore all Lambda configurations to pre-chaos state
4. Detach any deny policies

### Manual Restore (if andon cord fails)

If the andon cord script itself fails:

```bash
# Restore ingestion Lambda concurrency
aws lambda delete-function-concurrency \
  --function-name preprod-sentiment-ingestion

# Detach deny-write policy (if attached)
ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
aws iam detach-role-policy \
  --role-name preprod-ingestion-lambda-role \
  --policy-arn "arn:aws:iam::${ACCOUNT_ID}:policy/preprod-chaos-deny-dynamodb-write" 2>/dev/null || true
aws iam detach-role-policy \
  --role-name preprod-analysis-lambda-role \
  --policy-arn "arn:aws:iam::${ACCOUNT_ID}:policy/preprod-chaos-deny-dynamodb-write" 2>/dev/null || true

# Restore memory (if changed)
aws lambda update-function-configuration \
  --function-name preprod-sentiment-analysis \
  --memory-size 512

# Restore timeout (if changed)
aws lambda update-function-configuration \
  --function-name preprod-sentiment-ingestion \
  --timeout 30

# Re-enable EventBridge rule (if disabled)
aws events enable-rule \
  --name preprod-sentiment-ingestion-schedule

# Reset kill switch
aws ssm put-parameter \
  --name "/chaos/preprod/kill-switch" \
  --value "disarmed" \
  --type String \
  --overwrite
```

### Escalation Path

1. **Buddy operator** pulls andon cord
2. If unresolved in 5 minutes: **on-call engineer** via PagerDuty
3. If on-call unavailable: **engineering lead** via direct message

---

## Fallback: Direct Script Execution

If the dashboard Lambda Function URL is unreachable, use the chaos scripts directly. They bypass the dashboard API but still log to the chaos-experiments DynamoDB table.

### Inject

```bash
# Ingestion failure
scripts/chaos/inject.sh ingestion-failure preprod --duration 120

# DynamoDB throttle
scripts/chaos/inject.sh dynamodb-throttle preprod --duration 120

# Dry run (verify commands without executing)
scripts/chaos/inject.sh ingestion-failure preprod --dry-run
```

### Restore

```bash
scripts/chaos/restore.sh preprod
```

### Status

```bash
scripts/chaos/status.sh preprod
```

### Limitations of fallback path

- No experiment reports via API (must query DynamoDB directly)
- No real-time metrics in the chaos dashboard UI
- Audit trail still written to DynamoDB
- All safety mechanisms (kill switch, snapshots, andon cord) still work
