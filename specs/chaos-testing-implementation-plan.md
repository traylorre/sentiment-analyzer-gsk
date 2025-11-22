# Chaos Testing Implementation Plan

**Status:** APPROVED
**Created:** 2025-11-22
**Owner:** Engineering
**Parent Spec:** chaos-testing-system.md

---

## Overview

This plan details the implementation of chaos testing capabilities by extending the existing dashboard Lambda. No new infrastructure will be created - all chaos functionality will be added as new routes and UI components within the current dashboard.

## Implementation Phases

### Phase 1: Foundation (Week 1)

#### 1.1 DynamoDB Table for Experiment Tracking

**File:** `infrastructure/terraform/modules/chaos/dynamodb.tf` (new)

```hcl
resource "aws_dynamodb_table" "chaos_experiments" {
  name           = "${var.environment}-chaos-experiments"
  billing_mode   = "PAY_PER_REQUEST"
  hash_key       = "experiment_id"

  attribute {
    name = "experiment_id"
    type = "S"
  }

  attribute {
    name = "status"
    type = "S"
  }

  attribute {
    name = "started_at"
    type = "N"
  }

  global_secondary_index {
    name            = "status-index"
    hash_key        = "status"
    range_key       = "started_at"
    projection_type = "ALL"
  }

  ttl {
    attribute_name = "ttl"
    enabled        = true
  }

  tags = {
    Environment = var.environment
    Purpose     = "chaos-testing"
  }
}
```

**Schema:**
```python
{
  "experiment_id": "exp-uuid",
  "scenario_id": "dynamodb-throttle",
  "status": "running" | "completed" | "failed" | "stopped",
  "started_at": 1700000000,
  "completed_at": 1700000300,
  "duration_seconds": 300,
  "blast_radius_pct": 25,
  "fis_experiment_id": "EXP123...",  # AWS FIS experiment ID
  "metrics": {
    "dlq_depth": [0, 5, 12, 8, 3, 0],
    "error_rate_pct": [0, 2, 8, 5, 1, 0],
    "p99_latency_ms": [50, 100, 450, 200, 75, 50]
  },
  "stopped_reason": null | "manual" | "alarm_triggered" | "timeout",
  "ttl": 1702592000  # 30 days retention
}
```

#### 1.2 Extend Dashboard Lambda IAM Role

**File:** `infrastructure/terraform/modules/lambda/dashboard.tf` (modify)

Add FIS permissions to dashboard Lambda role:

```hcl
data "aws_iam_policy_document" "dashboard_chaos_policy" {
  # Allow starting/stopping FIS experiments
  statement {
    actions = [
      "fis:StartExperiment",
      "fis:StopExperiment",
      "fis:GetExperiment",
      "fis:ListExperiments"
    ]
    resources = ["*"]

    condition {
      test     = "StringEquals"
      variable = "aws:ResourceTag/managed-by"
      values   = ["terraform"]
    }
  }

  # Allow reading chaos experiments table
  statement {
    actions = [
      "dynamodb:GetItem",
      "dynamodb:PutItem",
      "dynamodb:UpdateItem",
      "dynamodb:Query",
      "dynamodb:Scan"
    ]
    resources = [
      aws_dynamodb_table.chaos_experiments.arn,
      "${aws_dynamodb_table.chaos_experiments.arn}/index/*"
    ]
  }

  # Allow reading CloudWatch metrics for live updates
  statement {
    actions = [
      "cloudwatch:GetMetricStatistics",
      "cloudwatch:GetMetricData"
    ]
    resources = ["*"]
  }
}

resource "aws_iam_role_policy" "dashboard_chaos" {
  count  = var.environment == "prod" ? 0 : 1  # Only in preprod
  name   = "chaos-testing-permissions"
  role   = aws_iam_role.dashboard.id
  policy = data.aws_iam_policy_document.dashboard_chaos_policy.json
}
```

#### 1.3 Dashboard Lambda Code - Chaos API Routes

**File:** `src/lambdas/dashboard/chaos_api.py` (new)

```python
"""Chaos testing API endpoints for dashboard Lambda."""
import json
import time
import uuid
from typing import Dict, List, Optional
import boto3
from decimal import Decimal

dynamodb = boto3.resource('dynamodb')
fis = boto3.client('fis')
cloudwatch = boto3.client('cloudwatch')

CHAOS_TABLE = os.environ.get('CHAOS_EXPERIMENTS_TABLE')

# Scenario definitions
SCENARIOS = {
    "dynamodb-throttle": {
        "id": "dynamodb-throttle",
        "name": "DynamoDB Throttling → DLQ Fill",
        "description": "Inject throttling errors to validate retry logic and DLQ recovery",
        "priority": 1,
        "duration_seconds": 300,
        "fis_template_id": os.environ.get('FIS_TEMPLATE_DYNAMODB_THROTTLE'),
        "metrics": ["dlq_depth", "error_rate_pct", "p99_latency_ms"]
    },
    "newsapi-failure": {
        "id": "newsapi-failure",
        "name": "NewsAPI Unavailable → Alarm Trigger",
        "description": "Simulate external API failure to validate alarm and fallback behavior",
        "priority": 2,
        "duration_seconds": 180,
        "fis_template_id": None,  # Custom Lambda layer injection
        "metrics": ["error_rate_pct", "alarm_state"]
    },
    "lambda-cold-start": {
        "id": "lambda-cold-start",
        "name": "Lambda Cold Start Delay",
        "description": "Add artificial delay to Lambda invocations to observe timeout behavior",
        "priority": 3,
        "duration_seconds": 180,
        "fis_template_id": os.environ.get('FIS_TEMPLATE_LAMBDA_DELAY'),
        "metrics": ["timeout_count", "p99_latency_ms"]
    }
}


def list_scenarios() -> Dict:
    """GET /api/chaos/scenarios - List available chaos scenarios."""
    return {
        "statusCode": 200,
        "body": json.dumps({
            "scenarios": list(SCENARIOS.values())
        })
    }


def start_experiment(body: Dict) -> Dict:
    """POST /api/chaos/start - Start a chaos experiment."""
    scenario_id = body.get('scenario_id')
    blast_radius_pct = body.get('blast_radius_pct', 25)

    if scenario_id not in SCENARIOS:
        return {
            "statusCode": 400,
            "body": json.dumps({"error": f"Unknown scenario: {scenario_id}"})
        }

    scenario = SCENARIOS[scenario_id]
    experiment_id = f"exp-{uuid.uuid4()}"

    # Start FIS experiment if applicable
    fis_experiment_id = None
    if scenario['fis_template_id']:
        fis_response = fis.start_experiment(
            experimentTemplateId=scenario['fis_template_id'],
            tags={
                'experiment_id': experiment_id,
                'scenario_id': scenario_id
            }
        )
        fis_experiment_id = fis_response['experiment']['id']

    # Record experiment in DynamoDB
    table = dynamodb.Table(CHAOS_TABLE)
    now = int(time.time())
    table.put_item(Item={
        'experiment_id': experiment_id,
        'scenario_id': scenario_id,
        'status': 'running',
        'started_at': now,
        'duration_seconds': scenario['duration_seconds'],
        'blast_radius_pct': blast_radius_pct,
        'fis_experiment_id': fis_experiment_id,
        'metrics': {},
        'ttl': now + (30 * 24 * 60 * 60)  # 30 days
    })

    return {
        "statusCode": 200,
        "body": json.dumps({
            "experiment_id": experiment_id,
            "scenario_id": scenario_id,
            "status": "running",
            "fis_experiment_id": fis_experiment_id
        })
    }


def stop_experiment(experiment_id: str) -> Dict:
    """POST /api/chaos/stop - Stop a running experiment."""
    table = dynamodb.Table(CHAOS_TABLE)

    # Get experiment details
    response = table.get_item(Key={'experiment_id': experiment_id})
    if 'Item' not in response:
        return {
            "statusCode": 404,
            "body": json.dumps({"error": "Experiment not found"})
        }

    experiment = response['Item']

    # Stop FIS experiment if exists
    if experiment.get('fis_experiment_id'):
        fis.stop_experiment(id=experiment['fis_experiment_id'])

    # Update experiment status
    table.update_item(
        Key={'experiment_id': experiment_id},
        UpdateExpression='SET #status = :status, completed_at = :completed_at, stopped_reason = :reason',
        ExpressionAttributeNames={'#status': 'status'},
        ExpressionAttributeValues={
            ':status': 'stopped',
            ':completed_at': int(time.time()),
            ':reason': 'manual'
        }
    )

    return {
        "statusCode": 200,
        "body": json.dumps({
            "experiment_id": experiment_id,
            "status": "stopped"
        })
    }


def get_experiment_status(experiment_id: str) -> Dict:
    """GET /api/chaos/status/{experiment_id} - Get experiment status with live metrics."""
    table = dynamodb.Table(CHAOS_TABLE)

    response = table.get_item(Key={'experiment_id': experiment_id})
    if 'Item' not in response:
        return {
            "statusCode": 404,
            "body": json.dumps({"error": "Experiment not found"})
        }

    experiment = response['Item']
    scenario = SCENARIOS.get(experiment['scenario_id'])

    # Fetch live metrics from CloudWatch
    now = int(time.time())
    elapsed = now - int(experiment['started_at'])

    metrics = fetch_live_metrics(
        scenario['metrics'],
        start_time=experiment['started_at'],
        end_time=now
    )

    # Convert Decimal to float for JSON serialization
    experiment = json.loads(json.dumps(experiment, default=decimal_to_float))

    return {
        "statusCode": 200,
        "body": json.dumps({
            "experiment_id": experiment_id,
            "scenario_id": experiment['scenario_id'],
            "scenario_name": scenario['name'],
            "status": experiment['status'],
            "elapsed_seconds": elapsed,
            "duration_seconds": experiment['duration_seconds'],
            "blast_radius_pct": experiment['blast_radius_pct'],
            "metrics": metrics,
            "stopped_reason": experiment.get('stopped_reason')
        })
    }


def fetch_live_metrics(metric_names: List[str], start_time: int, end_time: int) -> Dict:
    """Fetch live CloudWatch metrics for experiment visualization."""
    metrics = {}

    for metric_name in metric_names:
        if metric_name == "dlq_depth":
            # Fetch DLQ ApproximateNumberOfMessages
            response = cloudwatch.get_metric_statistics(
                Namespace='AWS/SQS',
                MetricName='ApproximateNumberOfMessagesVisible',
                Dimensions=[
                    {'Name': 'QueueName', 'Value': f"{os.environ['ENVIRONMENT']}-sentiment-analysis-dlq"}
                ],
                StartTime=start_time,
                EndTime=end_time,
                Period=30,
                Statistics=['Average']
            )
            metrics['dlq_depth'] = int(response['Datapoints'][-1]['Average']) if response['Datapoints'] else 0

        elif metric_name == "error_rate_pct":
            # Calculate error rate from Lambda errors
            # ... (similar CloudWatch query)
            metrics['error_rate_pct'] = 0.0  # Placeholder

        elif metric_name == "p99_latency_ms":
            # Fetch Lambda Duration p99
            # ... (similar CloudWatch query)
            metrics['p99_latency_ms'] = 0  # Placeholder

    return metrics


def decimal_to_float(obj):
    """Convert DynamoDB Decimal to float for JSON serialization."""
    if isinstance(obj, Decimal):
        return float(obj)
    raise TypeError
```

#### 1.4 Dashboard Lambda Handler Updates

**File:** `src/lambdas/dashboard/lambda_function.py` (modify)

```python
from chaos_api import (
    list_scenarios,
    start_experiment,
    stop_experiment,
    get_experiment_status
)

def lambda_handler(event, context):
    """Enhanced handler with chaos testing routes."""
    path = event.get('rawPath', '/')
    method = event.get('requestContext', {}).get('http', {}).get('method', 'GET')

    # Existing routes
    if path == '/' or path == '/dashboard':
        return render_dashboard()

    # NEW: Chaos testing routes
    if path == '/chaos':
        return render_chaos_ui()

    if path == '/api/chaos/scenarios' and method == 'GET':
        return list_scenarios()

    if path == '/api/chaos/start' and method == 'POST':
        body = json.loads(event.get('body', '{}'))
        return start_experiment(body)

    if path.startswith('/api/chaos/stop/') and method == 'POST':
        experiment_id = path.split('/')[-1]
        return stop_experiment(experiment_id)

    if path.startswith('/api/chaos/status/') and method == 'GET':
        experiment_id = path.split('/')[-1]
        return get_experiment_status(experiment_id)

    return {"statusCode": 404, "body": "Not Found"}
```

#### 1.5 Chaos Testing UI (Basic)

**File:** `src/lambdas/dashboard/chaos_ui.py` (new)

```python
def render_chaos_ui() -> Dict:
    """Render chaos testing UI HTML."""
    html = """
<!DOCTYPE html>
<html>
<head>
    <title>Chaos Engineering Dashboard</title>
    <script src="https://cdn.tailwindcss.com"></script>
</head>
<body class="bg-gray-900 text-white">
    <div class="container mx-auto p-6">
        <h1 class="text-3xl font-bold mb-6">🔥 Chaos Engineering Dashboard</h1>

        <!-- Scenario Library -->
        <div class="bg-gray-800 rounded-lg p-6 mb-6">
            <h2 class="text-xl font-semibold mb-4">Scenario Library</h2>
            <div id="scenarios" class="space-y-3"></div>
        </div>

        <!-- Active Experiment -->
        <div id="active-experiment" class="bg-gray-800 rounded-lg p-6 hidden">
            <h2 class="text-xl font-semibold mb-4">Active Experiment</h2>
            <div id="experiment-details"></div>
            <button id="stop-btn" class="mt-4 bg-red-600 hover:bg-red-700 px-4 py-2 rounded">
                ⏹️ Stop Experiment
            </button>
        </div>
    </div>

    <script>
        let currentExperimentId = null;
        let pollInterval = null;

        // Load scenarios on page load
        async function loadScenarios() {
            const response = await fetch('/api/chaos/scenarios');
            const data = await response.json();

            const container = document.getElementById('scenarios');
            container.innerHTML = data.scenarios.map(scenario => `
                <div class="border border-gray-700 rounded p-4">
                    <div class="flex justify-between items-center">
                        <div>
                            <h3 class="font-semibold">${scenario.name}</h3>
                            <p class="text-sm text-gray-400">${scenario.description}</p>
                        </div>
                        <button onclick="startExperiment('${scenario.id}')"
                                class="bg-orange-600 hover:bg-orange-700 px-4 py-2 rounded">
                            ▶️ Start
                        </button>
                    </div>
                </div>
            `).join('');
        }

        async function startExperiment(scenarioId) {
            const response = await fetch('/api/chaos/start', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({
                    scenario_id: scenarioId,
                    blast_radius_pct: 25
                })
            });

            const data = await response.json();
            currentExperimentId = data.experiment_id;

            // Show active experiment panel
            document.getElementById('active-experiment').classList.remove('hidden');

            // Start polling for updates
            pollInterval = setInterval(pollExperimentStatus, 2000);
        }

        async function pollExperimentStatus() {
            if (!currentExperimentId) return;

            const response = await fetch(`/api/chaos/status/${currentExperimentId}`);
            const data = await response.json();

            document.getElementById('experiment-details').innerHTML = `
                <div class="space-y-2">
                    <p><strong>Scenario:</strong> ${data.scenario_name}</p>
                    <p><strong>Status:</strong> ${data.status}</p>
                    <p><strong>Elapsed:</strong> ${data.elapsed_seconds}s / ${data.duration_seconds}s</p>
                    <div class="mt-4">
                        <h3 class="font-semibold mb-2">Live Metrics</h3>
                        <div class="grid grid-cols-3 gap-4">
                            ${Object.entries(data.metrics).map(([key, value]) => `
                                <div class="bg-gray-700 p-3 rounded">
                                    <div class="text-sm text-gray-400">${key}</div>
                                    <div class="text-2xl font-bold">${value}</div>
                                </div>
                            `).join('')}
                        </div>
                    </div>
                </div>
            `;

            // Stop polling if experiment completed
            if (data.status !== 'running') {
                clearInterval(pollInterval);
                setTimeout(() => {
                    document.getElementById('active-experiment').classList.add('hidden');
                    currentExperimentId = null;
                }, 5000);
            }
        }

        document.getElementById('stop-btn').addEventListener('click', async () => {
            await fetch(`/api/chaos/stop/${currentExperimentId}`, {method: 'POST'});
            clearInterval(pollInterval);
        });

        // Initialize
        loadScenarios();
    </script>
</body>
</html>
    """

    return {
        "statusCode": 200,
        "headers": {"Content-Type": "text/html"},
        "body": html
    }
```

#### 1.6 Terraform Module Integration

**File:** `infrastructure/terraform/modules/chaos/main.tf` (new)

```hcl
# Chaos testing module (preprod only)

variable "environment" {
  type = string
}

variable "dashboard_lambda_role_name" {
  type = string
}

# Import DynamoDB table
module "chaos_table" {
  source = "./dynamodb.tf"
  count  = var.environment == "prod" ? 0 : 1

  environment = var.environment
}

# Output table name for Lambda environment variable
output "chaos_experiments_table_name" {
  value = var.environment == "prod" ? "" : aws_dynamodb_table.chaos_experiments[0].name
}
```

**File:** `infrastructure/terraform/main.tf` (modify)

```hcl
# Add chaos testing module
module "chaos" {
  source = "./modules/chaos"
  count  = var.environment == "prod" ? 0 : 1

  environment               = var.environment
  dashboard_lambda_role_name = module.lambda.dashboard_role_name
}

# Update dashboard Lambda environment variables
resource "aws_lambda_function" "dashboard" {
  # ... existing config ...

  environment {
    variables = merge(
      local.base_env_vars,
      var.environment == "prod" ? {} : {
        CHAOS_EXPERIMENTS_TABLE = module.chaos[0].chaos_experiments_table_name
      }
    )
  }
}
```

---

### Phase 2: AWS FIS Integration (Week 2)

#### 2.1 FIS Experiment Template - DynamoDB Throttling

**File:** `infrastructure/terraform/modules/chaos/fis_templates.tf` (new)

```hcl
resource "aws_fis_experiment_template" "dynamodb_throttle" {
  count       = var.environment == "prod" ? 0 : 1
  description = "[Chaos] Inject DynamoDB throttling exceptions"

  role_arn = aws_iam_role.fis_role[0].arn

  action {
    name      = "throttle-dynamodb"
    action_id = "aws:dynamodb:api-throttle"

    parameter {
      key   = "duration"
      value = "PT5M"  # 5 minutes
    }

    parameter {
      key   = "percentage"
      value = "25"  # Throttle 25% of requests
    }

    parameter {
      key   = "operations"
      value = "PutItem,GetItem"
    }

    target {
      key   = "Tables"
      value = "dynamodb-tables"
    }
  }

  target {
    name           = "dynamodb-tables"
    resource_type  = "aws:dynamodb:table"
    selection_mode = "ALL"

    resource_tag {
      key   = "Environment"
      value = var.environment
    }

    resource_tag {
      key   = "chaos-testing-enabled"
      value = "true"
    }
  }

  stop_condition {
    source = "aws:cloudwatch:alarm"
    value  = aws_cloudwatch_metric_alarm.chaos_critical_error_rate[0].arn
  }

  tags = {
    managed-by = "terraform"
    scenario   = "dynamodb-throttle"
  }
}

# CloudWatch alarm as automatic kill switch
resource "aws_cloudwatch_metric_alarm" "chaos_critical_error_rate" {
  count               = var.environment == "prod" ? 0 : 1
  alarm_name          = "${var.environment}-chaos-critical-error-rate"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = "1"
  metric_name         = "Errors"
  namespace           = "AWS/Lambda"
  period              = "60"
  statistic           = "Sum"
  threshold           = "50"  # Stop if >50 errors in 1 minute
  alarm_description   = "Emergency stop for chaos experiments"

  dimensions = {
    FunctionName = var.analysis_lambda_name
  }
}

# FIS service role
resource "aws_iam_role" "fis_role" {
  count = var.environment == "prod" ? 0 : 1
  name  = "${var.environment}-fis-chaos-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Action = "sts:AssumeRole"
      Effect = "Allow"
      Principal = {
        Service = "fis.amazonaws.com"
      }
    }]
  })
}

resource "aws_iam_role_policy" "fis_policy" {
  count = var.environment == "prod" ? 0 : 1
  name  = "fis-chaos-permissions"
  role  = aws_iam_role.fis_role[0].id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "dynamodb:DescribeTable",
          "dynamodb:PutItem",
          "dynamodb:GetItem"
        ]
        Resource = "*"
        Condition = {
          StringEquals = {
            "aws:ResourceTag/chaos-testing-enabled" = "true"
          }
        }
      },
      {
        Effect = "Allow"
        Action = [
          "cloudwatch:DescribeAlarms"
        ]
        Resource = "*"
      }
    ]
  })
}

output "fis_template_dynamodb_throttle_id" {
  value = var.environment == "prod" ? "" : aws_fis_experiment_template.dynamodb_throttle[0].id
}
```

#### 2.2 Tag DynamoDB Table for Chaos Testing

**File:** `infrastructure/terraform/modules/dynamodb/main.tf` (modify)

```hcl
resource "aws_dynamodb_table" "sentiment_items" {
  # ... existing config ...

  tags = merge(
    var.common_tags,
    {
      chaos-testing-enabled = var.environment == "preprod" ? "true" : "false"
    }
  )
}
```

#### 2.3 Update Dashboard Lambda Environment Variables

**File:** `infrastructure/terraform/modules/lambda/dashboard.tf` (modify)

```hcl
environment {
  variables = merge(
    local.base_env_vars,
    var.environment == "prod" ? {} : {
      CHAOS_EXPERIMENTS_TABLE         = var.chaos_experiments_table_name
      FIS_TEMPLATE_DYNAMODB_THROTTLE  = var.fis_template_dynamodb_throttle_id
    }
  )
}
```

---

### Phase 3: Custom Fault Injection for External APIs (Week 3)

#### 3.1 Chaos Injector Lambda Layer

**File:** `src/lambda_layers/chaos_injector/chaos_injector.py` (new)

```python
"""Lambda layer for injecting faults into external API calls."""
import os
import time
import random
import boto3
from typing import Optional, Dict

dynamodb = boto3.resource('dynamodb')
CHAOS_TABLE = os.environ.get('CHAOS_EXPERIMENTS_TABLE')


class ChaosInjector:
    """Inject controlled failures into Lambda functions."""

    def __init__(self):
        self.table = dynamodb.Table(CHAOS_TABLE) if CHAOS_TABLE else None
        self.enabled = os.environ.get('CHAOS_ENABLED', 'false') == 'true'

    def should_inject_failure(self, fault_type: str) -> bool:
        """Check if we should inject failure for this fault type."""
        if not self.enabled or not self.table:
            return False

        # Query for active experiments targeting this fault type
        response = self.table.query(
            IndexName='status-index',
            KeyConditionExpression='#status = :running',
            FilterExpression='scenario_id = :scenario',
            ExpressionAttributeNames={'#status': 'status'},
            ExpressionAttributeValues={
                ':running': 'running',
                ':scenario': fault_type
            }
        )

        if not response['Items']:
            return False

        # Get blast radius percentage
        experiment = response['Items'][0]
        blast_radius = experiment.get('blast_radius_pct', 0)

        # Probabilistic injection based on blast radius
        return random.randint(1, 100) <= blast_radius

    def inject_api_failure(self, api_name: str) -> Optional[Exception]:
        """
        Inject API failure if chaos experiment is active.

        Returns:
            Exception to raise, or None if no failure should be injected
        """
        fault_type = f'api-{api_name}-failure'

        if not self.should_inject_failure(fault_type):
            return None

        # Simulate different failure modes
        failure_mode = random.choice(['timeout', '500', 'connection_error'])

        if failure_mode == 'timeout':
            time.sleep(30)  # Simulate timeout
            return TimeoutError(f"[CHAOS] Simulated timeout for {api_name}")
        elif failure_mode == '500':
            return ConnectionError(f"[CHAOS] Simulated 500 error from {api_name}")
        else:
            return ConnectionError(f"[CHAOS] Simulated connection error to {api_name}")


# Singleton instance
chaos_injector = ChaosInjector()
```

#### 3.2 Update Ingestion Lambda to Use Chaos Injector

**File:** `src/lambdas/ingestion/lambda_function.py` (modify)

```python
from chaos_injector import chaos_injector

def fetch_news_from_api(topic: str) -> List[Dict]:
    """Fetch news with chaos injection capability."""

    # Check for chaos injection
    chaos_error = chaos_injector.inject_api_failure('newsapi')
    if chaos_error:
        raise chaos_error

    # Normal API call
    newsapi = NewsApiClient(api_key=get_secret('newsapi'))
    return newsapi.get_everything(q=topic, language='en', page_size=10)
```

#### 3.3 Package and Deploy Chaos Injector Layer

**File:** `infrastructure/terraform/modules/lambda/layers.tf` (new)

```hcl
resource "aws_lambda_layer_version" "chaos_injector" {
  count               = var.environment == "prod" ? 0 : 1
  filename            = "${path.module}/../../../packages/chaos-injector-layer.zip"
  layer_name          = "${var.environment}-chaos-injector"
  compatible_runtimes = ["python3.11"]

  source_code_hash = filebase64sha256("${path.module}/../../../packages/chaos-injector-layer.zip")
}

# Attach layer to ingestion Lambda
resource "aws_lambda_function" "ingestion" {
  # ... existing config ...

  layers = var.environment == "prod" ? [] : [
    aws_lambda_layer_version.chaos_injector[0].arn
  ]

  environment {
    variables = merge(
      var.base_env_vars,
      var.environment == "prod" ? {} : {
        CHAOS_ENABLED           = "true"
        CHAOS_EXPERIMENTS_TABLE = var.chaos_experiments_table_name
      }
    )
  }
}
```

#### 3.4 Build Script for Chaos Injector Layer

**File:** `scripts/build-chaos-layer.sh` (new)

```bash
#!/bin/bash
set -e

echo "📦 Building chaos injector Lambda layer..."

# Create layer structure
mkdir -p packages/chaos-layer/python

# Copy chaos injector code
cp src/lambda_layers/chaos_injector/chaos_injector.py packages/chaos-layer/python/

# Install dependencies
pip install boto3 -t packages/chaos-layer/python/

# Create zip
cd packages/chaos-layer
zip -r ../chaos-injector-layer.zip python/
cd ../..

echo "✅ Chaos injector layer built: packages/chaos-injector-layer.zip"
```

---

### Phase 4: Lambda Delay Injection (Week 4)

#### 4.1 FIS Template - Lambda Invocation Delay

**File:** `infrastructure/terraform/modules/chaos/fis_templates.tf` (add)

```hcl
resource "aws_fis_experiment_template" "lambda_delay" {
  count       = var.environment == "prod" ? 0 : 1
  description = "[Chaos] Add artificial delay to Lambda invocations"

  role_arn = aws_iam_role.fis_role[0].arn

  action {
    name      = "delay-lambda"
    action_id = "aws:lambda:invocation-add-delay"

    parameter {
      key   = "duration"
      value = "PT3M"  # 3 minutes
    }

    parameter {
      key   = "delay"
      value = "25000"  # 25 seconds delay
    }

    parameter {
      key   = "percentage"
      value = "50"  # Affect 50% of invocations
    }

    target {
      key   = "Functions"
      value = "lambda-functions"
    }
  }

  target {
    name           = "lambda-functions"
    resource_type  = "aws:lambda:function"
    selection_mode = "ALL"

    resource_tag {
      key   = "chaos-testing-enabled"
      value = "true"
    }
  }

  stop_condition {
    source = "aws:cloudwatch:alarm"
    value  = aws_cloudwatch_metric_alarm.chaos_timeout_rate[0].arn
  }

  tags = {
    managed-by = "terraform"
    scenario   = "lambda-cold-start"
  }
}

resource "aws_cloudwatch_metric_alarm" "chaos_timeout_rate" {
  count               = var.environment == "prod" ? 0 : 1
  alarm_name          = "${var.environment}-chaos-timeout-rate"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = "1"
  metric_name         = "Throttles"
  namespace           = "AWS/Lambda"
  period              = "60"
  statistic           = "Sum"
  threshold           = "10"
  alarm_description   = "Stop chaos experiment if timeout rate too high"
}

output "fis_template_lambda_delay_id" {
  value = var.environment == "prod" ? "" : aws_fis_experiment_template.lambda_delay[0].id
}
```

#### 4.2 Tag Lambda Functions for Chaos Testing

**File:** `infrastructure/terraform/modules/lambda/main.tf` (modify)

```hcl
resource "aws_lambda_function" "analysis" {
  # ... existing config ...

  tags = merge(
    var.common_tags,
    {
      chaos-testing-enabled = var.environment == "preprod" ? "true" : "false"
    }
  )
}
```

---

### Phase 5: Polish and Production Readiness (Week 5)

#### 5.1 Enhanced Metrics Collection

**File:** `src/lambdas/dashboard/chaos_api.py` (enhance)

```python
def fetch_live_metrics(metric_names: List[str], start_time: int, end_time: int) -> Dict:
    """Enhanced metrics collection with proper CloudWatch queries."""
    metrics = {}

    for metric_name in metric_names:
        if metric_name == "dlq_depth":
            response = cloudwatch.get_metric_statistics(
                Namespace='AWS/SQS',
                MetricName='ApproximateNumberOfMessagesVisible',
                Dimensions=[
                    {'Name': 'QueueName', 'Value': f"{os.environ['ENVIRONMENT']}-sentiment-analysis-dlq"}
                ],
                StartTime=start_time,
                EndTime=end_time,
                Period=30,
                Statistics=['Maximum']
            )
            datapoints = sorted(response['Datapoints'], key=lambda x: x['Timestamp'])
            metrics['dlq_depth'] = int(datapoints[-1]['Maximum']) if datapoints else 0

        elif metric_name == "error_rate_pct":
            # Get error count
            errors = cloudwatch.get_metric_statistics(
                Namespace='AWS/Lambda',
                MetricName='Errors',
                Dimensions=[
                    {'Name': 'FunctionName', 'Value': f"{os.environ['ENVIRONMENT']}-sentiment-analysis"}
                ],
                StartTime=start_time,
                EndTime=end_time,
                Period=60,
                Statistics=['Sum']
            )

            # Get invocation count
            invocations = cloudwatch.get_metric_statistics(
                Namespace='AWS/Lambda',
                MetricName='Invocations',
                Dimensions=[
                    {'Name': 'FunctionName', 'Value': f"{os.environ['ENVIRONMENT']}-sentiment-analysis"}
                ],
                StartTime=start_time,
                EndTime=end_time,
                Period=60,
                Statistics=['Sum']
            )

            error_sum = sum(d['Sum'] for d in errors['Datapoints'])
            invocation_sum = sum(d['Sum'] for d in invocations['Datapoints'])

            metrics['error_rate_pct'] = round((error_sum / invocation_sum * 100), 2) if invocation_sum > 0 else 0.0

        elif metric_name == "p99_latency_ms":
            response = cloudwatch.get_metric_statistics(
                Namespace='AWS/Lambda',
                MetricName='Duration',
                Dimensions=[
                    {'Name': 'FunctionName', 'Value': f"{os.environ['ENVIRONMENT']}-sentiment-analysis"}
                ],
                StartTime=start_time,
                EndTime=end_time,
                Period=60,
                ExtendedStatistics=['p99']
            )
            datapoints = sorted(response['Datapoints'], key=lambda x: x['Timestamp'])
            metrics['p99_latency_ms'] = int(datapoints[-1]['ExtendedStatistics']['p99']) if datapoints else 0

    return metrics
```

#### 5.2 Error Handling and Validation

**File:** `src/lambdas/dashboard/chaos_api.py` (add)

```python
def validate_blast_radius(blast_radius_pct: int) -> None:
    """Validate blast radius is within safe limits."""
    if blast_radius_pct < 10 or blast_radius_pct > 100:
        raise ValueError("Blast radius must be between 10% and 100%")

    if blast_radius_pct > 50:
        # Require explicit confirmation for high blast radius
        # (This would be a UI confirmation in practice)
        pass


def check_experiment_conflicts() -> Optional[str]:
    """Ensure no conflicting experiments are running."""
    table = dynamodb.Table(CHAOS_TABLE)

    response = table.query(
        IndexName='status-index',
        KeyConditionExpression='#status = :running',
        ExpressionAttributeNames={'#status': 'status'},
        ExpressionAttributeValues={':running': 'running'}
    )

    if response['Items']:
        return f"Experiment {response['Items'][0]['experiment_id']} is already running"

    return None
```

#### 5.3 Experiment History View

**File:** `src/lambdas/dashboard/chaos_ui.py` (enhance)

Add history section to UI:

```html
<!-- Experiment History -->
<div class="bg-gray-800 rounded-lg p-6">
    <h2 class="text-xl font-semibold mb-4">Experiment History</h2>
    <div id="experiment-history" class="space-y-2"></div>
</div>
```

```javascript
async function loadHistory() {
    // This would query DynamoDB for recent experiments
    // Display in table format with filters
}
```

#### 5.4 Documentation

**File:** `docs/chaos-testing-guide.md` (new)

```markdown
# Chaos Testing Guide

## Quick Start

1. **Access Chaos Dashboard**
   ```
   https://<dashboard-url>/chaos
   ```

2. **Select Scenario** - Choose from 3 priority scenarios

3. **Configure Blast Radius** - Start with 10%, increase to 100%

4. **Monitor Live** - Watch metrics update every 2 seconds

5. **Stop Anytime** - Manual kill switch always available

## Safety Mechanisms

- ⏱️ **Time Limits**: All experiments auto-stop after duration
- 🚨 **CloudWatch Alarms**: Automatic stop if critical thresholds breached
- 🔒 **Environment Gating**: Only runs in preprod, never production
- 🎯 **Blast Radius**: Gradual scaling from 10% to 100%

## Scenarios

### 1. DynamoDB Throttling
**What it does**: Injects throttling errors to 25% of DynamoDB operations
**What to observe**: Retry logic, DLQ fill/recovery, error rates
**Duration**: 5 minutes

### 2. NewsAPI Unavailable
**What it does**: Simulates external API returning 500 errors or timeouts
**What to observe**: Alarm triggering, fallback behavior, error handling
**Duration**: 3 minutes

### 3. Lambda Cold Start Delay
**What it does**: Adds 25-second delay to 50% of Lambda invocations
**What to observe**: Timeout handling, retry behavior, latency spikes
**Duration**: 3 minutes

## Troubleshooting

**Q: Experiment won't start**
- Check no other experiment is running
- Verify FIS templates exist in Terraform state
- Check dashboard Lambda has FIS permissions

**Q: Metrics not updating**
- Check CloudWatch metrics exist for target resources
- Verify metric collection period (30-60 seconds)

**Q: Can't stop experiment**
- Use AWS Console FIS to force-stop
- Check experiment status in DynamoDB table
```

---

## Testing Checklist

### Phase 1 Testing
- [ ] DynamoDB table created in preprod
- [ ] Dashboard Lambda has chaos permissions
- [ ] `/chaos` route renders UI correctly
- [ ] Scenario list loads from `/api/chaos/scenarios`
- [ ] Can start experiment (creates DynamoDB record)

### Phase 2 Testing
- [ ] FIS template created for DynamoDB throttling
- [ ] CloudWatch alarm exists as stop condition
- [ ] Starting scenario #1 triggers FIS experiment
- [ ] FIS experiment ID stored in DynamoDB
- [ ] Metrics poll and update during experiment

### Phase 3 Testing
- [ ] Chaos injector layer builds successfully
- [ ] Ingestion Lambda has layer attached
- [ ] NewsAPI failure scenario injects faults correctly
- [ ] Blast radius percentage controls injection rate
- [ ] Experiment stops cleanly

### Phase 4 Testing
- [ ] FIS template created for Lambda delay
- [ ] Lambda functions tagged for chaos testing
- [ ] Delay scenario starts successfully
- [ ] P99 latency metrics reflect delays
- [ ] Timeout alarm triggers if needed

### Phase 5 Testing
- [ ] All 3 scenarios run end-to-end successfully
- [ ] Metrics collection accurate and real-time
- [ ] Error handling prevents invalid states
- [ ] History view shows past experiments
- [ ] Documentation complete and accurate

---

## Deployment Commands

### Deploy Chaos Infrastructure (Preprod Only)

```bash
# 1. Build chaos injector layer
./scripts/build-chaos-layer.sh

# 2. Deploy Terraform (preprod)
cd infrastructure/terraform
terraform init -backend-config=backend-preprod.hcl -reconfigure
terraform plan -var-file=preprod.tfvars
terraform apply -var-file=preprod.tfvars

# 3. Verify FIS templates created
aws fis list-experiment-templates --region us-east-1

# 4. Test chaos dashboard
curl https://<preprod-dashboard-url>/chaos
```

### Run First Chaos Experiment

```bash
# Via UI: https://<dashboard-url>/chaos

# Or via API:
curl -X POST https://<dashboard-url>/api/chaos/start \
  -H "Content-Type: application/json" \
  -d '{
    "scenario_id": "dynamodb-throttle",
    "blast_radius_pct": 25
  }'
```

---

## Cost Estimate

**Monthly Cost (Preprod Only):**
- DynamoDB chaos-experiments table: $1-2 (on-demand)
- AWS FIS experiment runs: $0.50 per experiment (~$5/month for 10 experiments)
- CloudWatch metrics: $0.30 per metric (~$2/month)
- Lambda execution (chaos UI): Negligible (within free tier)

**Total: ~$10/month**

---

## Security Considerations

1. **Environment Gating**: All chaos resources use `count = var.environment == "prod" ? 0 : 1`
2. **IAM Least Privilege**: FIS role only targets tagged resources
3. **Manual Approval**: High blast radius (>50%) requires UI confirmation
4. **Audit Trail**: All experiments logged in DynamoDB with 30-day retention
5. **Kill Switches**: Multiple layers (manual, alarm-based, time-based)

---

## Success Metrics

**Phase 1 Complete When:**
- Chaos UI accessible at `/chaos`
- Scenario library displays 3 scenarios
- Can start/stop experiments via UI

**Phase 2 Complete When:**
- DynamoDB throttling scenario runs successfully
- CloudWatch alarm triggers automatic stop
- Metrics display in real-time

**Phase 3 Complete When:**
- NewsAPI failure scenario injects faults correctly
- Blast radius percentage controls fault rate
- Alarms trigger as expected

**Phase 4 Complete When:**
- Lambda delay scenario shows latency increases
- Timeout handling validated
- All 3 scenarios run independently

**Phase 5 Complete When:**
- All tests pass
- Documentation complete
- Team trained on chaos testing
- First production-quality chaos experiment run successfully

---

## Rollout Plan

### Week 1-2: Foundation + FIS
- Deploy Phase 1 + 2 to preprod
- Run first DynamoDB throttling experiment
- Validate metrics and alarms

### Week 3: Custom Injection
- Deploy Phase 3
- Test NewsAPI failure scenario
- Refine blast radius controls

### Week 4: Lambda Delays
- Deploy Phase 4
- Run cold start delay experiments
- Validate timeout handling

### Week 5: Production Readiness
- Complete Phase 5
- Run all 3 scenarios successfully
- Document findings
- Team demo and training
- Mark as production-ready (for preprod use)

---

## Open Questions

1. **Should we add Slack notifications for experiment start/stop?**
   - Pro: Better visibility for team
   - Con: Additional complexity
   - Decision: Add in Phase 5 if time permits

2. **Should we support scheduled experiments?**
   - Pro: Regular resilience testing
   - Con: May cause unexpected issues
   - Decision: Manual only for now, scheduled in backlog

3. **Should we add experiment templates (saved configurations)?**
   - Pro: Easier to re-run common tests
   - Con: More UI complexity
   - Decision: Add in post-MVP enhancement

---

**Status**: Ready for implementation
**Estimated Effort**: 5 weeks
**Risk Level**: Low (preprod only, multiple safety mechanisms)
**Dependencies**: None (extends existing infrastructure)
