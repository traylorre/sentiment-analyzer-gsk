# Chaos Testing System - Full Design Specification

**Status:** DRAFT
**Created:** 2025-11-22
**Owner:** Engineering
**Purpose:** Enable controlled failure injection and resilience validation for sentiment-analyzer-gsk

---

## Executive Summary

This specification defines a **simple, serverless-native chaos testing system** for the sentiment analyzer. It enables engineers to inject controlled failures into production-like environments and observe system behavior through real-time visualizations.

**Key Design Principles:**
1. **Separate View** - New `/chaos` endpoint in dashboard Lambda (not mixed with sentiment data)
2. **AWS-Native** - Leverage AWS FIS (Fault Injection Simulator) for fault injection
3. **Observable** - CloudWatch metrics + real-time polling for experiment status
4. **Safe** - Automatic rollback, time limits, blast radius controls
5. **Simple** - No new infrastructure, reuse existing dashboard Lambda + DynamoDB

---

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────┐
│                     CHAOS TESTING SYSTEM                     │
└─────────────────────────────────────────────────────────────┘

┌──────────────┐         ┌──────────────┐         ┌──────────────┐
│  User opens  │────────▶│  Dashboard   │────────▶│  AWS FIS     │
│  /chaos UI   │  HTTP   │  Lambda      │   API   │  Service     │
│              │◀────────│  (enhanced)  │◀────────│              │
└──────────────┘   JSON  └──────────────┘   JSON  └──────────────┘
                              │      ▲
                              │      │
                              ▼      │
                         ┌──────────────┐
                         │  DynamoDB    │
                         │  chaos-      │
                         │  experiments │
                         └──────────────┘
                              │
                              │ monitors
                              ▼
     ┌──────────────────────────────────────────────────────────┐
     │             TARGET SYSTEM (Sentiment Analyzer)           │
     ├──────────────┬──────────────┬──────────────┬─────────────┤
     │  Ingestion   │  Analysis    │  DynamoDB    │   SNS/SQS   │
     │  Lambda      │  Lambda      │  Tables      │   Queues    │
     └──────────────┴──────────────┴──────────────┴─────────────┘
```

---

## System Components

### 1. Chaos Dashboard UI (`/chaos` endpoint)

**Purpose:** Web interface for engineers to trigger and monitor chaos experiments.

**Technology:**
- **Location:** Enhanced dashboard Lambda (existing Lambda, new `/chaos` route)
- **Frontend:** Static HTML + vanilla JavaScript (no React/Vue complexity)
- **Styling:** Tailwind CSS via CDN (consistent with dashboard)
- **Real-time:** Polling API every 2 seconds during active experiments

**UI Layout:**

```
┌─────────────────────────────────────────────────────────────┐
│  Chaos Engineering Dashboard                    🔥 [LIVE]   │
├─────────────────────────────────────────────────────────────┤
│                                                               │
│  ┌───────────────────────────────────────────────────────┐  │
│  │  SCENARIO LIBRARY                                      │  │
│  │                                                         │  │
│  │  [▶️ DynamoDB Throttling → DLQ Fill]      Priority: 1  │  │
│  │  [▶️ NewsAPI Unavailable → Alarm Trigger] Priority: 2  │  │
│  │  [▶️ Lambda Cold Start Delay]             Priority: 3  │  │
│  │  [⏸️ Secrets Manager Throttling]         Priority: 4  │  │
│  │  [⏸️ SQS Message Delay]                  Priority: 5  │  │
│  └───────────────────────────────────────────────────────┘  │
│                                                               │
│  ┌───────────────────────────────────────────────────────┐  │
│  │  ACTIVE EXPERIMENT: DynamoDB Throttling                │  │
│  │  Status: 🟡 RUNNING (45s / 300s)                       │  │
│  │  Blast Radius: 25% of requests                         │  │
│  │                                                         │  │
│  │  📊 LIVE METRICS                                       │  │
│  │  ┌─────────────────────────────────────────────────┐  │  │
│  │  │  DLQ Messages: 12 ████████░░░░░░░░░  (60% full) │  │  │
│  │  │  Error Rate:    8% ████░░░░░░░░░░░░  (target 10%)│  │  │
│  │  │  Latency p99:  450ms ███████░░░░░░░  (threshold) │  │  │
│  │  └─────────────────────────────────────────────────┘  │  │
│  │                                                         │  │
│  │  [⏹️ STOP EXPERIMENT]    [📈 View Full Metrics]       │  │
│  └───────────────────────────────────────────────────────┘  │
│                                                               │
│  ┌───────────────────────────────────────────────────────┐  │
│  │  EXPERIMENT HISTORY                                    │  │
│  │  2025-11-22 14:30 | DynamoDB Throttling    | ✅ PASS   │  │
│  │  2025-11-22 13:15 | NewsAPI Unavailable    | ⚠️ WARN   │  │
│  │  2025-11-22 12:00 | Lambda Cold Start      | ✅ PASS   │  │
│  └───────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────┘
```

### 2. Dashboard Lambda Enhancements

**New Routes:**

```python
# Existing: GET /health
# Existing: GET /metrics
# NEW: GET /chaos                    → Render chaos UI HTML
# NEW: GET /api/chaos/scenarios      → List available scenarios
# NEW: POST /api/chaos/start         → Start experiment
# NEW: POST /api/chaos/stop          → Stop experiment
# NEW: GET /api/chaos/status         → Get experiment status + metrics
```

**Handler Structure:**

```python
# src/lambdas/dashboard/handler.py

def lambda_handler(event, context):
    path = event['path']
    method = event['httpMethod']

    # Existing routes
    if path == '/health':
        return health_check()
    if path == '/metrics':
        return get_metrics()

    # NEW chaos routes
    if path == '/chaos':
        return render_chaos_ui()
    if path == '/api/chaos/scenarios':
        return list_scenarios()
    if path.startswith('/api/chaos/'):
        return handle_chaos_api(path, method, event)
```

### 3. AWS FIS Integration

**Purpose:** Execute actual fault injection using AWS-managed service.

**Why AWS FIS vs. Custom:**
- ✅ Native integration with Lambda, DynamoDB, SNS/SQS
- ✅ Built-in safety (stop conditions, time limits)
- ✅ IAM-based access control
- ✅ CloudWatch integration
- ✅ No infrastructure to maintain
- ❌ Limited to AWS services (can't inject NewsAPI failures)

**FIS Experiment Templates** (Terraform-managed):

```hcl
# infrastructure/terraform/modules/chaos/fis-templates.tf

resource "aws_fis_experiment_template" "dynamodb_throttle" {
  description = "[Chaos] Inject DynamoDB throttling exceptions"
  role_arn    = aws_iam_role.fis.arn

  action {
    name      = "inject-throttling"
    action_id = "aws:dynamodb:global-table-pause-replication"  # Or custom SSM doc

    parameter {
      key   = "duration"
      value = "PT5M"  # ISO 8601: 5 minutes
    }

    parameter {
      key   = "percentage"
      value = "25"
    }

    target {
      key   = "Tables"
      value = "dynamodb-tables"
    }
  }

  stop_condition {
    source = "aws:cloudwatch:alarm"
    value  = aws_cloudwatch_metric_alarm.chaos_critical_error_rate.arn
  }

  target {
    name           = "dynamodb-tables"
    resource_type  = "aws:dynamodb:table"
    selection_mode = "ALL"

    resource_arns = [
      aws_dynamodb_table.sentiment_items.arn
    ]
  }

  tags = {
    chaos_scenario = "dynamodb-throttle"
  }
}
```

### 4. DynamoDB Experiment Tracking

**Purpose:** Store experiment state, history, and results.

**Table Schema:**

```
Table: chaos-experiments
PK: experiment_id (String)  # UUID v4
SK: started_at (Number)     # Unix timestamp

Attributes:
- scenario_id (String)       # "dynamodb-throttle"
- status (String)            # "pending", "running", "stopping", "completed", "failed"
- fis_experiment_id (String) # AWS FIS experiment ID
- started_at (Number)
- stopped_at (Number)
- duration_seconds (Number)
- blast_radius_pct (Number)
- result (String)            # "pass", "warn", "fail"
- metrics_snapshot (Map)     # Final metrics
- error_message (String)     # If failed
- stopped_by (String)        # "auto", "manual", "alarm"

GSI: status-index
PK: status
SK: started_at
```

### 5. Custom Fault Injectors (For Non-AWS Resources)

**Purpose:** Inject failures into external dependencies (NewsAPI, RSS feeds).

**Implementation:** Lambda Layer + Feature Flag

```python
# src/layers/chaos_injector/chaos.py

import os
import random
import json
from datetime import datetime

class ChaosInjector:
    """
    Injects controlled failures into Lambda functions.
    Activated via environment variable: CHAOS_CONFIG
    """

    def __init__(self):
        self.enabled = os.getenv('CHAOS_ENABLED', 'false') == 'true'
        self.config = self._load_config()

    def _load_config(self):
        if not self.enabled:
            return {}

        config_str = os.getenv('CHAOS_CONFIG', '{}')
        return json.loads(config_str)

    def should_inject_failure(self, fault_type):
        """Check if we should inject this fault based on probability"""
        if not self.enabled:
            return False

        fault_config = self.config.get(fault_type, {})
        probability = fault_config.get('probability', 0)

        return random.random() < probability

    def inject_api_failure(self, api_name):
        """
        Inject API call failure (for NewsAPI, RSS feeds)

        Returns:
            Exception to raise, or None if no injection
        """
        fault_type = f'api.{api_name}.failure'

        if not self.should_inject_failure(fault_type):
            return None

        # Return exception to raise
        from requests.exceptions import Timeout, ConnectionError

        fault_config = self.config.get(fault_type, {})
        error_type = fault_config.get('error_type', 'timeout')

        if error_type == 'timeout':
            return Timeout(f"[CHAOS] Simulated timeout for {api_name}")
        elif error_type == '500':
            return ConnectionError(f"[CHAOS] Simulated 500 error for {api_name}")
        elif error_type == 'unreachable':
            return ConnectionError(f"[CHAOS] Simulated network unreachable for {api_name}")

        return None

    def inject_delay(self, operation):
        """Inject artificial delay"""
        import time

        fault_type = f'latency.{operation}'

        if not self.should_inject_failure(fault_type):
            return 0

        fault_config = self.config.get(fault_type, {})
        delay_ms = fault_config.get('delay_ms', 0)

        if delay_ms > 0:
            time.sleep(delay_ms / 1000.0)

        return delay_ms

# Usage in ingestion Lambda:
# src/lambdas/ingestion/handler.py

from chaos import ChaosInjector

chaos = ChaosInjector()

def fetch_newsapi_articles(source_id, api_key):
    # Check for chaos injection
    fault = chaos.inject_api_failure('newsapi')
    if fault:
        raise fault

    # Normal API call
    response = requests.get(...)
    return response.json()
```

---

## Priority 1-3 Chaos Scenarios

Based on research and system architecture, here are the **Top 3** scenarios to implement first:

### Scenario 1: DynamoDB Throttling → DLQ Observation ⭐⭐⭐

**Goal:** Validate that when DynamoDB throttles writes, messages correctly route to DLQ and processing resumes when throttling stops.

**Failure Injection:**
- **Method:** AWS FIS action `aws:dynamodb:api-throttle` OR SSM custom document
- **Target:** `sentiment-items` DynamoDB table
- **Parameters:**
  - Throttle 25% of `PutItem` operations
  - Duration: 5 minutes
  - Operations: `PutItem,BatchWriteItem`

**Expected Behavior:**
1. ✅ Inference Lambda retries 3x with exponential backoff
2. ✅ After retries exhausted, message moves to DLQ
3. ✅ DLQ depth CloudWatch metric increases
4. ✅ Error rate alarm triggers (threshold: 10%)
5. ✅ When throttling stops, DLQ redrives automatically
6. ✅ All messages eventually processed (0 data loss)

**Metrics to Monitor:**
```
- DynamoDB ConsumedWriteCapacity (should show throttling)
- DynamoDB ThrottledRequests (should spike)
- SQS ApproximateNumberOfMessagesVisible (DLQ depth)
- Lambda Errors (should increase then recover)
- Custom metric: sentiment.items_written_success (should dip then recover)
```

**Success Criteria:**
- ✅ No messages lost
- ✅ DLQ depth returns to 0 within 10 minutes after fault cleared
- ✅ P99 latency returns to baseline within 5 minutes

**Implementation Complexity:** MEDIUM (FIS template + CloudWatch metrics)

---

### Scenario 2: NewsAPI Unavailable → Alarm Trigger ⭐⭐⭐

**Goal:** Validate that when NewsAPI is unreachable, ingestion gracefully fails, CloudWatch alarm triggers, and system auto-recovers.

**Failure Injection:**
- **Method:** Custom Lambda Layer chaos injector (FIS can't inject external API failures)
- **Target:** Ingestion Lambda (Twitter/NewsAPI variant)
- **Parameters:**
  - Inject `Timeout` or `ConnectionError` exceptions
  - Probability: 100% (all requests fail)
  - Duration: 2 minutes

**Expected Behavior:**
1. ✅ Ingestion Lambda catches exception
2. ✅ Lambda returns failure status to scheduler
3. ✅ CloudWatch metric `newsapi.fetch_errors` increases
4. ✅ CloudWatch alarm "NewsAPI Unavailable" triggers after 2 datapoints
5. ✅ SNS notification sent to on-call engineer
6. ✅ When fault cleared, next scheduled poll succeeds
7. ✅ Alarm auto-resolves

**Metrics to Monitor:**
```
- Custom metric: newsapi.fetch_errors (should spike)
- Custom metric: newsapi.fetch_success (should drop to 0)
- Lambda Duration (should be shorter due to fast-fail)
- CloudWatch Alarm state (should transition: OK → ALARM → OK)
```

**Success Criteria:**
- ✅ Alarm triggers within 2 minutes of fault injection
- ✅ No Lambda crashes (graceful exception handling)
- ✅ Alarm auto-resolves within 5 minutes after fault cleared
- ✅ Next successful poll resumes normal operation

**Implementation Complexity:** LOW (Lambda layer + env var feature flag)

---

### Scenario 3: Lambda Cold Start Delay → Timeout Observation ⭐⭐

**Goal:** Validate Lambda timeout handling when artificial delay simulates extreme cold starts.

**Failure Injection:**
- **Method:** AWS FIS action `aws:lambda:invocation-add-delay`
- **Target:** Inference Lambda
- **Parameters:**
  - Add 25,000ms (25 seconds) delay
  - Percentage: 50% of invocations
  - Duration: 3 minutes

**Expected Behavior:**
1. ✅ 50% of Lambda invocations timeout (30s limit)
2. ✅ Timed-out invocations return to SQS queue
3. ✅ SQS redelivers messages after visibility timeout
4. ✅ Retried invocations succeed (if delay cleared)
5. ✅ Lambda timeout CloudWatch metric increases
6. ✅ Messages processed eventually (eventual consistency)

**Metrics to Monitor:**
```
- Lambda Duration (should show bimodal distribution)
- Lambda Errors (timeout errors)
- SQS ApproximateAgeOfOldestMessage (should increase)
- SQS NumberOfMessagesReceived (redelivery count)
```

**Success Criteria:**
- ✅ No messages lost despite timeouts
- ✅ All messages processed within 15 minutes
- ✅ System auto-recovers when delay removed

**Implementation Complexity:** LOW (FIS template only)

---

## Backlog Scenarios (Priority 4-5)

### Scenario 4: Secrets Manager Throttling → Token Cache Validation

**Goal:** Validate that Lambda's `/tmp` token cache prevents catastrophic failure when Secrets Manager throttles.

**Injection:** AWS FIS `aws:secretsmanager:throttle`
**Expected:** Lambda serves from cache, gracefully degrades

### Scenario 5: SQS Message Delay → Latency SLA Impact

**Goal:** Validate end-to-end latency impact when SQS messages delayed.

**Injection:** AWS FIS `aws:sqs:delay-messages`
**Expected:** P99 latency increases but stays under SLA

### Scenario 6: SNS Topic Unavailable → Multi-AZ Failover

**Goal:** Validate SNS redundancy and message delivery guarantees.

**Injection:** AWS FIS `aws:sns:topic-unavailable`
**Expected:** Message delivery via backup path

---

## Dashboard vs. Separate View Decision

### Option A: Extend Existing Dashboard ✅ **RECOMMENDED**

**Pros:**
- ✅ Reuse existing Lambda infrastructure
- ✅ Single API key authentication (already implemented)
- ✅ Consistent UI styling (Tailwind CSS)
- ✅ No new deployment pipeline
- ✅ Lower operational overhead

**Cons:**
- ⚠️ Mixing chaos controls with production metrics (mitigated by separate `/chaos` route)
- ⚠️ Slightly larger Lambda package size (~50 KB for chaos code)

**Implementation:**
```
dashboard-lambda/
├── src/
│   ├── routes/
│   │   ├── health.py       # Existing
│   │   ├── metrics.py      # Existing
│   │   ├── chaos.py        # NEW
│   └── templates/
│       ├── dashboard.html  # Existing
│       ├── chaos.html      # NEW
```

### Option B: Separate Chaos Service ❌ **NOT RECOMMENDED**

**Pros:**
- ✅ Complete isolation from production dashboard
- ✅ Independent scaling

**Cons:**
- ❌ New Lambda function to deploy/maintain
- ❌ New API Gateway endpoint
- ❌ Duplicate authentication logic
- ❌ More complex Terraform
- ❌ Higher operational overhead

**Verdict:** Extend existing dashboard. Chaos testing is an **engineering tool**, not a user-facing feature. Keeping it in the same Lambda simplifies operations without compromising production.

---

## Safety Mechanisms

### 1. Automatic Stop Conditions

**CloudWatch Alarms as Kill Switches:**

```hcl
resource "aws_cloudwatch_metric_alarm" "chaos_critical_error_rate" {
  alarm_name          = "chaos-critical-error-rate"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 2
  metric_name         = "Errors"
  namespace           = "AWS/Lambda"
  period              = 60
  statistic           = "Sum"
  threshold           = 50  # Stop experiment if >50 errors/min

  dimensions = {
    FunctionName = aws_lambda_function.inference.function_name
  }
}
```

**FIS Experiment Links Alarm:**
```hcl
stop_condition {
  source = "aws:cloudwatch:alarm"
  value  = aws_cloudwatch_metric_alarm.chaos_critical_error_rate.arn
}
```

**Result:** Experiment automatically stops if error rate exceeds threshold.

### 2. Time Limits

**All FIS experiments have hard duration limits:**
- Minimum: 1 minute
- Maximum: 12 hours
- Recommended: 5 minutes for automated tests

**Dashboard enforces UI limits:**
```javascript
const MAX_EXPERIMENT_DURATION_SECONDS = 300; // 5 minutes

function validateExperimentDuration(duration) {
  if (duration > MAX_EXPERIMENT_DURATION_SECONDS) {
    throw new Error(`Experiment duration cannot exceed ${MAX_EXPERIMENT_DURATION_SECONDS}s`);
  }
}
```

### 3. Blast Radius Control

**Percentage-Based Fault Injection:**
```
┌────────────────────────────────────────────────────────┐
│  Blast Radius Slider                                   │
│                                                         │
│  Impact: [======░░░░░░░░░░░░░░░░] 25% of requests     │
│           ◀───────────────────────▶                    │
│           0%         50%         100%                  │
│                                                         │
│  Recommended: Start with 10%, increase gradually       │
└────────────────────────────────────────────────────────┘
```

**Progressive Experiment Strategy:**
1. First run: 10% blast radius, 2 minutes
2. If successful: 25% blast radius, 5 minutes
3. If successful: 50% blast radius, 5 minutes
4. Production validation: 100% blast radius, 1 minute

### 4. Environment Gating

**Chaos experiments ONLY in preprod:**

```python
# src/lambdas/dashboard/chaos.py

ALLOWED_ENVIRONMENTS = ['preprod', 'dev']

def start_experiment(scenario_id):
    env = os.getenv('ENVIRONMENT')

    if env not in ALLOWED_ENVIRONMENTS:
        raise ValueError(
            f"Chaos experiments not allowed in {env}. "
            f"Allowed: {ALLOWED_ENVIRONMENTS}"
        )

    # Proceed with experiment
```

**Terraform enforces:**
```hcl
resource "aws_fis_experiment_template" "dynamodb_throttle" {
  count = var.environment == "prod" ? 0 : 1  # No FIS templates in prod
  # ...
}
```

### 5. Manual Kill Switch

**UI Provides Immediate Stop:**
```html
<button
  class="bg-red-600 text-white px-6 py-3 rounded-lg"
  onclick="stopExperiment()"
>
  ⏹️ EMERGENCY STOP
</button>
```

**API Implementation:**
```python
def stop_experiment(experiment_id):
    """Stop FIS experiment immediately"""

    # Get FIS experiment ID from DynamoDB
    item = table.get_item(Key={'experiment_id': experiment_id})
    fis_id = item['Item']['fis_experiment_id']

    # Stop FIS experiment
    fis_client.stop_experiment(id=fis_id)

    # Update DynamoDB
    table.update_item(
        Key={'experiment_id': experiment_id},
        UpdateExpression='SET #status = :stopped, stopped_at = :now, stopped_by = :manual',
        ExpressionAttributeNames={'#status': 'status'},
        ExpressionAttributeValues={
            ':stopped': 'stopped',
            ':now': int(time.time()),
            ':manual': 'manual'
        }
    )
```

---

## Implementation Plan

### Phase 1: Foundation (Week 1)

**Goal:** Set up basic chaos infrastructure

**Tasks:**
1. ✅ Create DynamoDB table `chaos-experiments`
2. ✅ Add FIS IAM role with permissions
3. ✅ Create CloudWatch stop-condition alarms
4. ✅ Add `/chaos` route to dashboard Lambda
5. ✅ Implement static HTML UI (scenario list only)

**Acceptance:**
- [ ] `/chaos` endpoint returns HTML
- [ ] DynamoDB table created
- [ ] IAM roles verified

### Phase 2: Scenario 1 - DynamoDB Throttling (Week 2)

**Goal:** Implement first complete chaos scenario

**Tasks:**
1. ✅ Create FIS experiment template (Terraform)
2. ✅ Implement `POST /api/chaos/start` API
3. ✅ Implement `GET /api/chaos/status` API
4. ✅ Add DLQ depth metric visualization
5. ✅ Create experiment history table

**Acceptance:**
- [ ] Can start DynamoDB throttling experiment from UI
- [ ] See DLQ messages increase in real-time
- [ ] Experiment auto-stops after 5 minutes
- [ ] Results saved to DynamoDB

### Phase 3: Scenario 2 - NewsAPI Failure (Week 3)

**Goal:** Add custom fault injector for external APIs

**Tasks:**
1. ✅ Create Lambda Layer for `ChaosInjector` class
2. ✅ Update ingestion Lambda to use layer
3. ✅ Add env var `CHAOS_CONFIG` to Lambda
4. ✅ Implement CloudWatch alarm for NewsAPI errors
5. ✅ Add alarm status to UI

**Acceptance:**
- [ ] Can inject NewsAPI failures via env var
- [ ] CloudWatch alarm triggers
- [ ] Alarm appears in UI
- [ ] Alarm auto-resolves

### Phase 4: Scenario 3 - Lambda Delay (Week 4)

**Goal:** Add AWS FIS Lambda delay action

**Tasks:**
1. ✅ Create FIS experiment template for Lambda delay
2. ✅ Add timeout metrics to UI
3. ✅ Verify SQS redelivery behavior
4. ✅ Document results in experiment history

**Acceptance:**
- [ ] Can inject Lambda delays from UI
- [ ] See timeout metrics spike
- [ ] Messages eventually processed
- [ ] No data loss

### Phase 5: Polish & Backlog (Week 5+)

**Goal:** Production-ready + additional scenarios

**Tasks:**
1. ✅ Add Scenarios 4-6 to backlog
2. ✅ Implement experiment templates system
3. ✅ Add export experiment results to JSON
4. ✅ Write runbook for chaos testing
5. ✅ Team training session

---

## Success Metrics

**Engineering Goals:**
- [ ] Run at least 1 chaos experiment per week
- [ ] Identify and fix 3+ resilience gaps in first month
- [ ] Reduce MTTR (Mean Time To Recovery) by 30%

**System Resilience KPIs:**
- [ ] 99.9% message delivery despite failures
- [ ] All experiments complete successfully (pass criteria met)
- [ ] Zero production incidents caused by chaos testing

---

## API Reference

### GET /api/chaos/scenarios

**Response:**
```json
{
  "scenarios": [
    {
      "id": "dynamodb-throttle",
      "name": "DynamoDB Throttling → DLQ Fill",
      "description": "Inject ProvisionedThroughputExceededException and observe DLQ behavior",
      "priority": 1,
      "duration_seconds": 300,
      "blast_radius_pct": 25,
      "status": "ready"
    },
    {
      "id": "newsapi-unavailable",
      "name": "NewsAPI Unavailable → Alarm Trigger",
      "description": "Simulate NewsAPI timeout and verify CloudWatch alarm",
      "priority": 2,
      "duration_seconds": 120,
      "blast_radius_pct": 100,
      "status": "ready"
    }
  ]
}
```

### POST /api/chaos/start

**Request:**
```json
{
  "scenario_id": "dynamodb-throttle",
  "duration_seconds": 300,
  "blast_radius_pct": 25
}
```

**Response:**
```json
{
  "experiment_id": "exp-123e4567-e89b-12d3-a456-426614174000",
  "fis_experiment_id": "EXTfEdBu7qhMCnxxx",
  "status": "running",
  "started_at": 1700000000,
  "estimated_completion": 1700000300
}
```

### GET /api/chaos/status?experiment_id=exp-123

**Response:**
```json
{
  "experiment_id": "exp-123e4567-e89b-12d3-a456-426614174000",
  "scenario_id": "dynamodb-throttle",
  "status": "running",
  "started_at": 1700000000,
  "elapsed_seconds": 45,
  "duration_seconds": 300,
  "metrics": {
    "dlq_depth": 12,
    "error_rate_pct": 8.5,
    "p99_latency_ms": 450
  },
  "stop_conditions": {
    "alarm_triggered": false,
    "alarm_name": null
  }
}
```

### POST /api/chaos/stop

**Request:**
```json
{
  "experiment_id": "exp-123e4567-e89b-12d3-a456-426614174000"
}
```

**Response:**
```json
{
  "experiment_id": "exp-123e4567-e89b-12d3-a456-426614174000",
  "status": "stopped",
  "stopped_by": "manual",
  "stopped_at": 1700000090
}
```

---

## Terraform Module Structure

```
infrastructure/terraform/modules/chaos/
├── main.tf                    # Module entry point
├── fis-templates.tf           # FIS experiment templates
├── dynamodb.tf                # chaos-experiments table
├── iam.tf                     # FIS service role
├── cloudwatch.tf              # Stop-condition alarms
├── variables.tf
└── outputs.tf

infrastructure/terraform/environments/preprod/
└── main.tf
    └── module "chaos" { ... }  # Only in preprod, not prod
```

---

## Open Questions & Decisions

1. **Should chaos UI require separate authentication?**
   - **Decision:** No. Reuse dashboard API key. Chaos is admin-only operation.

2. **How to handle ongoing experiments during dashboard Lambda redeploy?**
   - **Decision:** FIS experiments run independently. Store state in DynamoDB. Redeployed Lambda can query FIS API to resume monitoring.

3. **What if multiple engineers trigger experiments simultaneously?**
   - **Decision:** UI shows "Experiment already running" error. Only 1 active experiment at a time.

4. **Should we support scheduling chaos experiments (GameDays)?**
   - **Decision:** Not in MVP. Add to Phase 5 backlog.

---

## References

- AWS FIS Actions: https://docs.aws.amazon.com/fis/latest/userguide/fis-actions-reference.html
- Chaos Engineering Principles: https://principlesofchaos.org/
- LocalStack Chaos API: https://docs.localstack.cloud/user-guide/chaos-engineering/
- Chaos Mesh Dashboard: https://github.com/chaos-mesh/chaos-mesh

---

**Next Steps:**
1. Review this spec with team
2. Create GitHub issue for Phase 1 implementation
3. Add Terraform module skeleton
4. Schedule kickoff meeting
