# Chaos Testing Operator Guide

**Version**: 1.0
**Last Updated**: 2025-11-24
**Target Audience**: On-Call Engineers, SREs, DevOps

---

## Table of Contents

- [Overview](#overview)
- [Prerequisites](#prerequisites)
- [Quick Reference Table](#quick-reference-table)
- [Scenario Playbooks](#scenario-playbooks)
  - [Phase 2: DynamoDB Throttling](#phase-2-dynamodb-throttling)
  - [Phase 3: NewsAPI Failure](#phase-3-newsapi-failure)
  - [Phase 4: Lambda Cold Start Delay](#phase-4-lambda-cold-start-delay)
- [Common Operations](#common-operations)
- [Troubleshooting](#troubleshooting)
- [Safety Guidelines](#safety-guidelines)

---

## Overview

This guide provides comprehensive playbooks for executing chaos experiments in the Sentiment Analyzer system. Each scenario includes:

- What the experiment tests
- Normal baseline behavior
- Expected behavior during the experiment
- How to verify system recovery
- Acceptable thresholds and SLOs

**Environments**:
- Chaos testing is **ONLY** enabled in: preprod, dev, test
- Production environment **NEVER** executes chaos experiments (fail-safe)

**Access**:
- Chaos experiments are managed through the Dashboard API at `/api/chaos/experiments`
- AWS FIS experiments require `fis:StartExperiment` IAM permission
- DynamoDB-based experiments require dashboard API key

---

## Prerequisites

### Required Tools

```bash
# AWS CLI
aws --version  # Required: v2.x

# Dashboard API access
export DASHBOARD_API_KEY="your-api-key-here"
export DASHBOARD_URL="https://your-dashboard-url.com"

# CloudWatch Logs access
aws logs tail --help

# Optional: jq for JSON parsing
jq --version
```

### IAM Permissions

Minimum permissions required:

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "fis:StartExperiment",
        "fis:StopExperiment",
        "fis:GetExperiment",
        "dynamodb:PutItem",
        "dynamodb:GetItem",
        "dynamodb:Query",
        "cloudwatch:GetMetricStatistics",
        "logs:FilterLogEvents",
        "logs:TailLogs"
      ],
      "Resource": "*"
    }
  ]
}
```

---

## Quick Reference Table

| Scenario | What It Tests | Normal Behavior | Chaos Behavior | Recovery Time | Acceptable Thresholds |
|----------|---------------|------------------|----------------|---------------|----------------------|
| **DynamoDB Throttling** | System resilience to database capacity limits | All writes succeed, latency <100ms | 50% writes throttled, DLQ accumulates | Immediate on stop | Error rate <10%, no data loss |
| **NewsAPI Failure** | Graceful degradation when external API unavailable | 10-100 articles fetched every 5min | 0 articles fetched, no errors | 5 minutes (next poll) | Ingestion stops, analysis continues processing backlog |
| **Lambda Cold Start** | Performance under high latency conditions | P95 latency 200-500ms | P95 latency +2000ms (configurable) | Immediate on stop | No timeouts, no 5xx errors |

---

## Scenario Playbooks

### Phase 2: DynamoDB Throttling

#### What It Tests

- System resilience to DynamoDB write capacity exhaustion
- Dead Letter Queue (DLQ) behavior under sustained failures
- Lambda retry logic and exponential backoff
- CloudWatch alarm triggering

#### Normal Baseline Behavior

```bash
# Metric: ConsumedWriteCapacityUnits (baseline)
aws cloudwatch get-metric-statistics \
  --namespace AWS/DynamoDB \
  --metric-name ConsumedWriteCapacityUnits \
  --dimensions Name=TableName,Value=preprod-sentiment-items \
  --start-time $(date -u -d '10 minutes ago' +%Y-%m-%dT%H:%M:%S) \
  --end-time $(date -u +%Y-%m-%dT%H:%M:%S) \
  --period 300 \
  --statistics Average,Maximum

# Expected: Average 10-50 WCU, Maximum <100 WCU
```

**Baseline SLOs**:
- Write success rate: >99.9%
- P95 write latency: <100ms
- DLQ depth: 0 messages

#### Starting the Experiment

```bash
# Via Dashboard API
curl -X POST "$DASHBOARD_URL/api/chaos/experiments" \
  -H "Authorization: Bearer $DASHBOARD_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "scenario_type": "dynamodb_throttle",
    "duration_seconds": 300,
    "blast_radius": 50
  }'

# Save experiment ID from response
export EXPERIMENT_ID="<experiment_id>"
```

#### Expected Behavior During Chaos

**Immediate (0-30 seconds)**:
1. DynamoDB returns `ProvisionedThroughputExceededException` for ~50% of writes
2. Analysis Lambda retries with exponential backoff (3 attempts)
3. Failed messages route to DLQ after max retries

**Sustained (30-300 seconds)**:
4. DLQ accumulates messages (alarm triggers at depth >10)
5. CloudWatch alarm: `preprod-dynamodb-write-throttles` fires
6. Dashboard UI shows degraded state
7. Ingestion continues (unaffected)

**Observable Metrics**:
```bash
# Check throttle rate
aws cloudwatch get-metric-statistics \
  --namespace AWS/DynamoDB \
  --metric-name UserErrors \
  --dimensions Name=TableName,Value=preprod-sentiment-items \
  --start-time $(date -u -d '5 minutes ago' +%Y-%m-%dT%H:%M:%S) \
  --end-time $(date -u +%Y-%m-%dT%H:%M:%S) \
  --period 60 \
  --statistics Sum

# Expected during chaos: Sum >10 per minute
```

#### Verifying System Recovery

**1. Stop Experiment**:
```bash
curl -X POST "$DASHBOARD_URL/api/chaos/experiments/$EXPERIMENT_ID/stop" \
  -H "Authorization: Bearer $DASHBOARD_API_KEY"
```

**2. Verify Throttling Stopped** (within 1-2 seconds):
```bash
aws cloudwatch get-metric-statistics \
  --namespace AWS/DynamoDB \
  --metric-name UserErrors \
  --dimensions Name=TableName,Value=preprod-sentiment-items \
  --start-time $(date -u -d '2 minutes ago' +%Y-%m-%dT%H:%M:%S) \
  --end-time $(date -u +%Y-%m-%dT%H:%M:%S) \
  --period 60 \
  --statistics Sum

# Expected: Sum returns to 0
```

**3. Verify DLQ Drains** (within 5-10 minutes):
```bash
aws sqs get-queue-attributes \
  --queue-url https://sqs.us-west-2.amazonaws.com/.../preprod-sentiment-analysis-dlq \
  --attribute-names ApproximateNumberOfMessages

# Expected: Messages reprocessed by DLQ processor Lambda
```

**4. Verify No Data Loss**:
```bash
# Check analysis completion rate
aws cloudwatch get-metric-statistics \
  --namespace SentimentAnalyzer \
  --metric-name AnalysisCompleted \
  --start-time $(date -u -d '15 minutes ago' +%Y-%m-%dT%H:%M:%S) \
  --end-time $(date -u +%Y-%m-%dT%H:%M:%S) \
  --period 300 \
  --statistics Sum

# Expected: Sum matches pre-chaos baseline after recovery
```

#### Acceptable Thresholds

| Metric | Normal | During Chaos | Post-Recovery | Alert If |
|--------|--------|--------------|---------------|----------|
| Write Success Rate | >99.9% | >50% (blast_radius) | >99.9% within 2min | <90% |
| DLQ Depth | 0 | <100 | 0 within 10min | >100 |
| P95 Latency | <100ms | <500ms (retries) | <100ms within 2min | >1000ms |
| Data Loss | 0 | 0 (DLQ captures) | 0 | Any data loss |

---

### Phase 3: NewsAPI Failure

#### What It Tests

- Graceful degradation when external API (NewsAPI) is unavailable
- System continues processing existing data
- No cascading failures to downstream components
- Monitoring detects missing ingestion

#### Normal Baseline Behavior

```bash
# Metric: ArticlesFetched (baseline)
aws cloudwatch get-metric-statistics \
  --namespace SentimentAnalyzer \
  --metric-name ArticlesFetched \
  --start-time $(date -u -d '30 minutes ago' +%Y-%m-%dT%H:%M:%S) \
  --end-time $(date -u +%Y-%m-%dT%H:%M:%S) \
  --period 300 \
  --statistics Sum

# Expected: Sum 10-100 per 5 minutes (depends on watch_tags)
```

**Baseline SLOs**:
- Articles fetched per poll: 10-100
- Ingestion error rate: <1%
- Analysis continues processing: 100%

#### Starting the Experiment

```bash
curl -X POST "$DASHBOARD_URL/api/chaos/experiments" \
  -H "Authorization: Bearer $DASHBOARD_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "scenario_type": "newsapi_failure",
    "duration_seconds": 600,
    "blast_radius": 100
  }'

export EXPERIMENT_ID="<experiment_id>"
```

#### Expected Behavior During Chaos

**Immediate (within 1 poll cycle = 5 minutes)**:
1. Ingestion Lambda detects active chaos experiment
2. Skips NewsAPI fetch for all tags
3. Logs warning: "Chaos experiment active: skipping NewsAPI fetch"
4. Returns successfully with 0 articles fetched (no errors)

**Sustained (5-600 seconds)**:
5. No new items added to DynamoDB
6. Analysis Lambda continues processing existing queue backlog
7. Dashboard shows stale data (last_updated timestamp doesn't advance)
8. CloudWatch alarm: `no-new-items-1h` may trigger after 60 minutes

**Observable Logs**:
```bash
aws logs filter-log-events \
  --log-group-name /aws/lambda/preprod-sentiment-ingestion \
  --filter-pattern "Chaos experiment active" \
  --start-time $(date -u -d '10 minutes ago' +%s)000

# Expected: WARNING logs for each tag skipped
```

#### Verifying System Recovery

**1. Stop Experiment**:
```bash
curl -X POST "$DASHBOARD_URL/api/chaos/experiments/$EXPERIMENT_ID/stop" \
  -H "Authorization: Bearer $DASHBOARD_API_KEY"
```

**2. Verify Ingestion Resumes** (within 5 minutes = next poll):
```bash
# Watch logs for successful fetch
aws logs tail /aws/lambda/preprod-sentiment-ingestion --since 5m --follow

# Look for: "Fetched X articles for tag Y"
# Expected: X > 0
```

**3. Verify New Items in DynamoDB**:
```bash
aws cloudwatch get-metric-statistics \
  --namespace SentimentAnalyzer \
  --metric-name NewItemsIngested \
  --start-time $(date -u -d '10 minutes ago' +%Y-%m-%dT%H:%M:%S) \
  --end-time $(date -u +%Y-%m-%dT%H:%M:%S) \
  --period 300 \
  --statistics Sum

# Expected: Sum >0 within 5-10 minutes of stopping
```

**4. Verify Analysis Pipeline Unaffected**:
```bash
aws cloudwatch get-metric-statistics \
  --namespace SentimentAnalyzer \
  --metric-name AnalysisCompleted \
  --start-time $(date -u -d '30 minutes ago' +%Y-%m-%dT%H:%M:%S) \
  --end-time $(date -u +%Y-%m-%dT%H:%M:%S) \
  --period 300 \
  --statistics Sum

# Expected: Analysis continues during chaos (processes existing queue)
```

#### Acceptable Thresholds

| Metric | Normal | During Chaos | Post-Recovery | Alert If |
|--------|--------|--------------|---------------|----------|
| Articles Fetched | 10-100/5min | 0 | 10-100/5min within 10min | 0 for >60min |
| Ingestion Errors | <1% | 0% (graceful skip) | <1% | Any errors |
| Analysis Throughput | Baseline | Baseline (processes queue) | Baseline | Drops >10% |
| Dashboard Availability | 100% | 100% (stale data) | 100% (fresh data) | <99% |

---

### Phase 4: Lambda Cold Start Delay

#### What It Tests

- System performance under high Lambda latency
- End-to-end latency impact (ingestion → analysis → dashboard)
- Timeout behavior (15min Lambda limit)
- Queue backpressure and throttling

#### Normal Baseline Behavior

```bash
# Metric: Lambda Duration P95 (baseline)
aws cloudwatch get-metric-statistics \
  --namespace AWS/Lambda \
  --metric-name Duration \
  --dimensions Name=FunctionName,Value=preprod-sentiment-analysis \
  --start-time $(date -u -d '30 minutes ago' +%Y-%m-%dT%H:%M:%S) \
  --end-time $(date -u +%Y-%m-%dT%H:%M:%S) \
  --period 300 \
  --statistics Average,Maximum \
  --extended-statistics p95

# Expected: Average 200-500ms, p95 <1000ms, Maximum <3000ms
```

**Baseline SLOs**:
- P50 latency: <500ms
- P95 latency: <1000ms
- Timeout rate: 0%

#### Starting the Experiment

```bash
# Start with 2-second delay
curl -X POST "$DASHBOARD_URL/api/chaos/experiments" \
  -H "Authorization: Bearer $DASHBOARD_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "scenario_type": "lambda_cold_start",
    "duration_seconds": 300,
    "blast_radius": 2000
  }'

export EXPERIMENT_ID="<experiment_id>"
```

**Blast Radius Values**:
- `500`: 500ms delay (mild degradation)
- `2000`: 2s delay (typical cold start)
- `5000`: 5s delay (extreme cold start)

#### Expected Behavior During Chaos

**Immediate (0-60 seconds)**:
1. Lambda injects `blast_radius` milliseconds delay at handler entry
2. Logs warning: "Chaos experiment active: injected Xms delay"
3. All invocations delayed (warm + cold start simulation)

**Sustained (60-300 seconds)**:
4. SNS/SQS queue accumulates (ingestion faster than delayed analysis)
5. Lambda concurrency may increase to compensate
6. End-to-end latency increases by delay amount
7. Dashboard API response times unaffected (separate Lambda)

**Observable Metrics**:
```bash
# Verify delay injection
aws cloudwatch get-metric-statistics \
  --namespace AWS/Lambda \
  --metric-name Duration \
  --dimensions Name=FunctionName,Value=preprod-sentiment-analysis \
  --start-time $(date -u -d '5 minutes ago' +%Y-%m-%dT%H:%M:%S) \
  --end-time $(date -u +%Y-%m-%dT%H:%M:%S) \
  --period 60 \
  --statistics Average,Maximum

# Expected during chaos:
#   Average: baseline + blast_radius (e.g., 400ms + 2000ms = 2400ms)
#   Maximum: May spike higher if model loading coincides
```

#### Verifying System Recovery

**1. Stop Experiment**:
```bash
curl -X POST "$DASHBOARD_URL/api/chaos/experiments/$EXPERIMENT_ID/stop" \
  -H "Authorization: Bearer $DASHBOARD_API_KEY"
```

**2. Verify Delay Removed** (within 1-2 invocations):
```bash
# Check logs for absence of chaos messages
aws logs filter-log-events \
  --log-group-name /aws/lambda/preprod-sentiment-analysis \
  --filter-pattern "Chaos experiment active" \
  --start-time $(date -u -d '5 minutes ago' +%s)000

# Expected: No new logs after stopping
```

**3. Verify Latency Returns to Baseline**:
```bash
aws cloudwatch get-metric-statistics \
  --namespace AWS/Lambda \
  --metric-name Duration \
  --dimensions Name=FunctionName,Value=preprod-sentiment-analysis \
  --start-time $(date -u -d '5 minutes ago' +%Y-%m-%dT%H:%M:%S) \
  --end-time $(date -u +%Y-%m-%dT%H:%M:%S) \
  --period 60 \
  --statistics Average

# Expected: Average returns to baseline (200-500ms) within 2-3 minutes
```

**4. Verify Queue Drains**:
```bash
aws sqs get-queue-attributes \
  --queue-url https://sqs.us-west-2.amazonaws.com/.../preprod-sentiment-analysis-queue \
  --attribute-names ApproximateNumberOfMessages

# Expected: Queue depth returns to 0-10 within 5-10 minutes
```

#### Acceptable Thresholds

| Metric | Normal | During Chaos | Post-Recovery | Alert If |
|--------|--------|--------------|---------------|----------|
| P95 Latency | <1000ms | <3000ms (for 2s delay) | <1000ms within 5min | >5000ms |
| Timeout Rate | 0% | 0% | 0% | >0.1% |
| Concurrent Executions | 5-20 | May increase 2-3x | Return to baseline within 10min | >100 |
| Queue Depth | 0-10 | <100 | 0-10 within 10min | >200 |

---

## Common Operations

### Listing Active Experiments

```bash
# Via Dashboard API
curl -X GET "$DASHBOARD_URL/api/chaos/experiments?status=running" \
  -H "Authorization: Bearer $DASHBOARD_API_KEY"
```

### Emergency Stop All Experiments

```bash
# Get all running experiments
curl -X GET "$DASHBOARD_URL/api/chaos/experiments?status=running" \
  -H "Authorization: Bearer $DASHBOARD_API_KEY" \
  | jq -r '.[] | .experiment_id' \
  | while read exp_id; do
      echo "Stopping $exp_id"
      curl -X POST "$DASHBOARD_URL/api/chaos/experiments/$exp_id/stop" \
        -H "Authorization: Bearer $DASHBOARD_API_KEY"
    done
```

### Monitoring During Experiments

**Real-time CloudWatch Dashboard**:
```bash
# Open preprod dashboard (replace ACCOUNT_ID)
aws cloudwatch get-dashboard \
  --dashboard-name preprod-sentiment-analyzer \
  | jq -r '.DashboardBody' > /tmp/dashboard.json

# View in AWS Console
open "https://console.aws.amazon.com/cloudwatch/home?region=us-west-2#dashboards:name=preprod-sentiment-analyzer"
```

**Tail Logs**:
```bash
# Monitor all Lambdas simultaneously (requires tmux/screen)
tmux new-session -d -s chaos
tmux split-window -h
tmux split-window -v
tmux select-pane -t 0
tmux send-keys "aws logs tail /aws/lambda/preprod-sentiment-ingestion --follow" Enter
tmux select-pane -t 1
tmux send-keys "aws logs tail /aws/lambda/preprod-sentiment-analysis --follow" Enter
tmux select-pane -t 2
tmux send-keys "aws logs tail /aws/lambda/preprod-sentiment-dashboard --follow" Enter
tmux attach-session -t chaos
```

---

## Troubleshooting

### Experiment Won't Start

**Symptoms**: API returns 400 or experiment status stuck in "pending"

**Debug Steps**:
1. Check FIS template exists (for dynamodb_throttle):
   ```bash
   aws fis get-experiment-template \
     --id $(terraform output -raw fis_dynamodb_throttle_template_id)
   ```

2. Verify IAM permissions:
   ```bash
   aws sts get-caller-identity
   # Ensure role has fis:StartExperiment
   ```

3. Check DynamoDB table exists (for newsapi_failure, lambda_cold_start):
   ```bash
   aws dynamodb describe-table --table-name preprod-chaos-experiments
   ```

### Experiment Won't Stop

**Symptoms**: System still exhibits chaos behavior after stop command

**Debug Steps**:
1. Verify experiment status changed to "stopped":
   ```bash
   curl -X GET "$DASHBOARD_URL/api/chaos/experiments/$EXPERIMENT_ID" \
     -H "Authorization: Bearer $DASHBOARD_API_KEY" \
     | jq '.status'
   ```

2. For FIS experiments, check AWS FIS console:
   ```bash
   aws fis get-experiment --id $FIS_EXPERIMENT_ID
   ```

3. Manual DynamoDB fix (last resort):
   ```bash
   aws dynamodb update-item \
     --table-name preprod-chaos-experiments \
     --key '{"experiment_id":{"S":"'$EXPERIMENT_ID'"}}' \
     --update-expression "SET #status = :stopped" \
     --expression-attribute-names '{"#status":"status"}' \
     --expression-attribute-values '{":stopped":{"S":"stopped"}}'
   ```

### System Not Recovering

**Symptoms**: Metrics remain degraded >15 minutes after stopping

**Possible Causes**:
1. DLQ not draining (reprocess manually)
2. Lambda container reusing cached chaos state (wait for cold start)
3. Experiment still running (verify status)
4. Unrelated production issue (check other metrics)

**Recovery Actions**:
```bash
# Force Lambda cold start (update env var)
aws lambda update-function-configuration \
  --function-name preprod-sentiment-analysis \
  --environment Variables={FORCE_COLD_START=true}

# Wait 30 seconds
sleep 30

# Remove env var
aws lambda update-function-configuration \
  --function-name preprod-sentiment-analysis \
  --environment Variables={FORCE_COLD_START=false}
```

---

## Safety Guidelines

### Pre-Flight Checklist

Before starting ANY chaos experiment:

- [ ] Verify environment is preprod/dev/test (NOT production)
- [ ] Confirm experiment duration is reasonable (<10 minutes for first run)
- [ ] Check current system health (all alarms green)
- [ ] Notify team in Slack (#chaos-testing channel)
- [ ] Have emergency stop command ready
- [ ] Monitor dashboard during experiment

### Abort Criteria

**Immediately stop experiment if**:
- Any Lambda timeout errors occur
- Error rate exceeds 25% (for blast_radius=50%)
- DLQ depth exceeds 200 messages
- Preprod budget alarm triggers
- Customer-facing production alerts fire (spillover)

### Post-Experiment Review

After EVERY experiment:

1. Document findings in experiment results (Dashboard UI)
2. Calculate blast radius accuracy (actual vs expected)
3. Verify full system recovery (all metrics baseline)
4. Update runbooks if new issues discovered
5. Share learnings in team retrospective

---

## References

- [Phase 2: DynamoDB Throttling Documentation](./chaos-testing/PHASE2_DYNAMODB_THROTTLE.md)
- [Phase 3: NewsAPI Failure Documentation](./chaos-testing/PHASE3_NEWSAPI_FAILURE.md)
- [Phase 4: Lambda Delay Documentation](./chaos-testing/PHASE4_LAMBDA_DELAY.md)
- [Chaos Engineering Principles](https://principlesofchaos.org/)
- [AWS FIS Best Practices](https://docs.aws.amazon.com/fis/latest/userguide/best-practices.html)

---

**Document Owner**: SRE Team
**Last Review**: 2025-11-24
**Next Review**: 2025-12-24 (monthly)
