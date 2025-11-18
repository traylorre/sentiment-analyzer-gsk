# Dashboard Lambda - Contract

**Handler**: `src/lambdas/dashboard/handler.lambda_handler`
**Trigger**: Lambda Function URL (HTTPS requests from browser)
**Purpose**: Serve dashboard UI and provide real-time metrics via Server-Sent Events (SSE)

**Updated**: 2025-11-17 - Regional Multi-AZ architecture

---

## Data Access Strategy

**Read Target**: `sentiment-items` (single table)
- Queries using GSIs: `by_sentiment`, `by_tag`, `by_status`
- Eventually consistent reads (acceptable for dashboard use case)
- Direct DynamoDB queries (no caching layer for Demo 1)

---

## Endpoints

### GET /

Serve static dashboard HTML page.

**Response**:
- Content-Type: `text/html`
- Body: `index.html` with embedded Chart.js visualizations

---

### GET /api/metrics

Return current metrics snapshot for dashboard initialization.

**Query Parameters**:
| Parameter | Type | Required | Description |
|---|---|---|---|
| `source_type` | String | No | Filter by source (default: `newsapi`) |
| `hours` | Integer | No | Time window in hours (default: `24`) |

**Response** (JSON):
```json
{
  "summary": {
    "total_items": 1523,
    "positive_count": 612,
    "neutral_count": 489,
    "negative_count": 422,
    "last_updated": "2025-11-16T14:30:25.000Z"
  },
  "sentiment_distribution": {
    "positive": 612,
    "neutral": 489,
    "negative": 422
  },
  "tag_distribution": {
    "AI": 340,
    "climate": 298,
    "economy": 315,
    "health": 287,
    "sports": 283
  },
  "recent_items": [
    {
      "source_id": "newsapi#a3f4e9d2c1b8a7f6",
      "ingested_at": "2025-11-16T14:25:10.000Z",
      "sentiment": "positive",
      "score": 0.89,
      "text_snippet": "European markets surge on positive economic data...",
      "matched_tags": ["economy", "positive"],
      "metadata": {
        "title": "European Markets Rally",
        "source_name": "Financial Times"
      }
    }
    // ... 19 more items
  ],
  "ingestion_rate": {
    "last_hour": 47,
    "last_24h": 1523
  }
}
```

---

### GET /api/stream

Server-Sent Events (SSE) stream for real-time updates.

**Query Parameters**:
| Parameter | Type | Required | Description |
|---|---|---|---|
| `source_type` | String | No | Filter by source (default: `newsapi`) |

**Response**:
- Content-Type: `text/event-stream`
- Connection: `keep-alive`
- Transfer-Encoding: `chunked`

**SSE Event Format**:
```
event: update
data: {"new_items": [...], "updated_metrics": {...}, "timestamp": "2025-11-16T14:30:30.000Z"}

event: update
data: {"new_items": [...], "updated_metrics": {...}, "timestamp": "2025-11-16T14:30:35.000Z"}
```

**Event Data Schema**:
```json
{
  "new_items": [
    {
      "source_id": "newsapi#...",
      "sentiment": "positive",
      "score": 0.92,
      "text_snippet": "...",
      "ingested_at": "2025-11-16T14:30:28.000Z"
    }
  ],
  "updated_metrics": {
    "total_items": 1524,
    "sentiment_distribution": {
      "positive": 613,
      "neutral": 489,
      "negative": 422
    }
  },
  "timestamp": "2025-11-16T14:30:30.000Z"
}
```

**Update Frequency**: Every 5 seconds

**Connection Timeout**: 15 minutes (Lambda max timeout), client should reconnect

---

## FastAPI Implementation

### Main Application

```python
# src/lambdas/dashboard/handler.py
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, StreamingResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
import asyncio
import json
import os
from datetime import datetime, timedelta
import boto3

app = FastAPI(title="Sentiment Analyzer Dashboard")

# Mount static files (CSS, JS, images)
app.mount("/static", StaticFiles(directory="static"), name="static")

dynamodb = boto3.client('dynamodb')
```

### Serve Dashboard HTML

```python
@app.get("/", response_class=HTMLResponse)
async def serve_dashboard():
    """
    Serve main dashboard HTML page.
    """
    with open("static/index.html", "r") as f:
        html_content = f.read()

    return HTMLResponse(content=html_content)
```

### Metrics Snapshot Endpoint

```python
@app.get("/api/metrics")
async def get_metrics(source_type: str = "newsapi", hours: int = 24):
    """
    Return current metrics snapshot for dashboard initialization.

    ROUTING LOGIC:
    - Queries sentiment-items (single table)
    - Uses day_partition PK for efficient queries
    try:
        # Calculate day partitions to query (today + yesterday for 24h window)
        today = datetime.utcnow().strftime('%Y-%m-%d')
        yesterday = (datetime.utcnow() - timedelta(days=1)).strftime('%Y-%m-%d')

        items = []

        # Query today's partition
        response_today = dynamodb.query(
            TableName=os.environ['DYNAMODB_TABLE'],  # sentiment-items
            KeyConditionExpression='day_partition = :day',
            ExpressionAttributeValues={':day': {'S': today}},
            ScanIndexForward=False,  # Newest first
            Limit=1000,
            ConsistentRead=False  # Eventually consistent (acceptable)
        )
        items.extend(parse_dynamodb_items(response_today['Items']))

        # Query yesterday's partition if hours > 12
        if hours > 12:
            response_yesterday = dynamodb.query(
                TableName=os.environ['DYNAMODB_TABLE'],
                KeyConditionExpression='day_partition = :day',
                ExpressionAttributeValues={':day': {'S': yesterday}},
                ScanIndexForward=False,
                Limit=1000,
                ConsistentRead=False
            )
            items.extend(parse_dynamodb_items(response_yesterday['Items']))

        # Filter by time window and source type
        cutoff = (datetime.utcnow() - timedelta(hours=hours)).isoformat() + 'Z'
        filtered_items = [
            item for item in items
            if item['ingested_at'] > cutoff and item.get('source_type') == source_type
        ]

        # Calculate metrics
        metrics = calculate_metrics(filtered_items)

        return JSONResponse(content=metrics)

    except Exception as e:
        logger.error(f"Failed to fetch metrics from dashboard table: {str(e)}")

        # FALLBACK: Try primary table (slower, but functional)
        try:
            logger.warning("Falling back to primary table query")
            response = dynamodb.query(
                TableName=os.environ['DYNAMODB_TABLE'],
                # Use primary table's schema (no day_partition)
                ...
            )
            # Process and return
        except Exception as fallback_error:
            logger.error(f"Fallback also failed: {str(fallback_error)}")
            return JSONResponse(
                status_code=500,
                content={"error": "Failed to fetch metrics", "details": str(e)}
            )
```

### Server-Sent Events Stream

```python
@app.get("/api/stream")
async def stream_updates(request: Request, source_type: str = "newsapi"):
    """
    Server-Sent Events stream for real-time dashboard updates.
    Polls DynamoDB every 5 seconds and emits new items.
    """
    async def event_generator():
        last_check = datetime.utcnow().isoformat() + 'Z'

        try:
            while True:
                # Check if client disconnected
                if await request.is_disconnected():
                    logger.info("Client disconnected from SSE stream")
                    break

                # Query DynamoDB for new items since last check
                response = dynamodb.query(
                    TableName=os.environ['DYNAMODB_TABLE'],
                    IndexName='by_timestamp',
                    KeyConditionExpression='source_type = :st AND ingested_at > :last',
                    ExpressionAttributeValues={
                        ':st': {'S': source_type},
                        ':last': {'S': last_check}
                    },
                    ScanIndexForward=False,
                    Limit=100
                )

                items = parse_dynamodb_items(response['Items'])

                if items:
                    # Calculate updated metrics
                    updated_metrics = calculate_metrics_delta(items)

                    # Emit SSE event
                    event_data = {
                        'new_items': items[:20],  # Last 20 for display
                        'updated_metrics': updated_metrics,
                        'timestamp': datetime.utcnow().isoformat() + 'Z'
                    }

                    yield f"event: update\n"
                    yield f"data: {json.dumps(event_data)}\n\n"

                    # Update last_check to most recent item
                    last_check = items[0]['ingested_at']

                # Wait 5 seconds before next poll
                await asyncio.sleep(5)

        except asyncio.CancelledError:
            logger.info("SSE stream cancelled")
        except Exception as e:
            logger.error(f"SSE stream error: {str(e)}")
            yield f"event: error\n"
            yield f"data: {json.dumps({'error': str(e)})}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no"  # Disable nginx buffering
        }
    )
```

---

## Helper Functions

### Parse DynamoDB Items

```python
def parse_dynamodb_items(items: list) -> list:
    """
    Parse DynamoDB items into dashboard-friendly format.
    """
    parsed = []

    for item in items:
        parsed.append({
            'source_id': item['source_id']['S'],
            'ingested_at': item['ingested_at']['S'],
            'sentiment': item.get('sentiment', {}).get('S', 'pending'),
            'score': float(item.get('score', {}).get('N', '0')),
            'text_snippet': item.get('text_snippet', {}).get('S', ''),
            'matched_tags': list(item.get('matched_tags', {}).get('SS', [])),
            'metadata': parse_metadata(item.get('metadata', {}).get('M', {}))
        })

    return parsed

def parse_metadata(metadata_map: dict) -> dict:
    """
    Parse DynamoDB Map type to Python dict.
    """
    return {
        'title': metadata_map.get('title', {}).get('S', ''),
        'author': metadata_map.get('author', {}).get('S', ''),
        'source_name': metadata_map.get('source_name', {}).get('S', '')
    }
```

### Calculate Metrics

```python
from collections import Counter

def calculate_metrics(items: list) -> dict:
    """
    Calculate dashboard metrics from items list.
    """
    total = len(items)

    # Sentiment distribution
    sentiment_counts = Counter(item['sentiment'] for item in items)

    # Tag distribution
    tag_counter = Counter()
    for item in items:
        tag_counter.update(item['matched_tags'])

    # Recent items (last 20)
    recent_items = sorted(items, key=lambda x: x['ingested_at'], reverse=True)[:20]

    # Ingestion rate
    last_hour = sum(
        1 for item in items
        if datetime.fromisoformat(item['ingested_at'].replace('Z', '+00:00'))
           > datetime.utcnow() - timedelta(hours=1)
    )

    return {
        'summary': {
            'total_items': total,
            'positive_count': sentiment_counts.get('positive', 0),
            'neutral_count': sentiment_counts.get('neutral', 0),
            'negative_count': sentiment_counts.get('negative', 0),
            'last_updated': datetime.utcnow().isoformat() + 'Z'
        },
        'sentiment_distribution': dict(sentiment_counts),
        'tag_distribution': dict(tag_counter.most_common(10)),  # Top 10 tags
        'recent_items': recent_items,
        'ingestion_rate': {
            'last_hour': last_hour,
            'last_24h': total
        }
    }
```

---

## Lambda Handler (Mangum Adapter)

```python
# Lambda entry point
from mangum import Mangum

# Wrap FastAPI app for Lambda
lambda_handler = Mangum(app, lifespan="off")
```

**Configuration**:
- `lifespan="off"`: Disable lifespan events (not needed for Lambda)
- Mangum automatically handles API Gateway / Lambda Function URL events

---

## Static Dashboard UI

### index.html (Simplified)

```html
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Sentiment Analyzer Dashboard</title>
    <script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.0"></script>
    <link rel="stylesheet" href="/static/styles.css">
</head>
<body>
    <div class="dashboard-container">
        <header>
            <h1>Real-Time Sentiment Analysis</h1>
            <div id="status" class="status-connected">● Live</div>
        </header>

        <div class="metrics-grid">
            <div class="metric-card">
                <h3>Total Items</h3>
                <div id="total-items" class="metric-value">0</div>
            </div>
            <div class="metric-card">
                <h3>Positive</h3>
                <div id="positive-count" class="metric-value positive">0</div>
            </div>
            <div class="metric-card">
                <h3>Neutral</h3>
                <div id="neutral-count" class="metric-value neutral">0</div>
            </div>
            <div class="metric-card">
                <h3>Negative</h3>
                <div id="negative-count" class="metric-value negative">0</div>
            </div>
        </div>

        <div class="charts-grid">
            <div class="chart-container">
                <h3>Sentiment Distribution</h3>
                <canvas id="sentiment-pie"></canvas>
            </div>
            <div class="chart-container">
                <h3>Tag Matches</h3>
                <canvas id="tag-bar"></canvas>
            </div>
        </div>

        <div class="recent-items">
            <h3>Recent Items</h3>
            <table id="items-table">
                <thead>
                    <tr>
                        <th>Time</th>
                        <th>Snippet</th>
                        <th>Sentiment</th>
                        <th>Score</th>
                        <th>Tags</th>
                    </tr>
                </thead>
                <tbody id="items-tbody"></tbody>
            </table>
        </div>
    </div>

    <script src="/static/app.js"></script>
</body>
</html>
```

### app.js (Client-Side Logic)

```javascript
// Initialize charts
let sentimentChart, tagChart;

// Fetch initial metrics
async function initDashboard() {
    const response = await fetch('/api/metrics');
    const data = await response.json();

    updateMetrics(data);
    initCharts(data);
    connectSSE();
}

// Update metric cards
function updateMetrics(data) {
    document.getElementById('total-items').textContent = data.summary.total_items;
    document.getElementById('positive-count').textContent = data.summary.positive_count;
    document.getElementById('neutral-count').textContent = data.summary.neutral_count;
    document.getElementById('negative-count').textContent = data.summary.negative_count;
}

// Initialize Chart.js charts
function initCharts(data) {
    // Sentiment pie chart
    const sentimentCtx = document.getElementById('sentiment-pie').getContext('2d');
    sentimentChart = new Chart(sentimentCtx, {
        type: 'pie',
        data: {
            labels: ['Positive', 'Neutral', 'Negative'],
            datasets: [{
                data: [
                    data.summary.positive_count,
                    data.summary.neutral_count,
                    data.summary.negative_count
                ],
                backgroundColor: ['#4ade80', '#94a3b8', '#f87171']
            }]
        }
    });

    // Tag bar chart
    const tagCtx = document.getElementById('tag-bar').getContext('2d');
    tagChart = new Chart(tagCtx, {
        type: 'bar',
        data: {
            labels: Object.keys(data.tag_distribution),
            datasets: [{
                label: 'Matches',
                data: Object.values(data.tag_distribution),
                backgroundColor: '#3b82f6'
            }]
        }
    });

    // Update recent items table
    updateItemsTable(data.recent_items);
}

// Server-Sent Events connection
function connectSSE() {
    const eventSource = new EventSource('/api/stream');

    eventSource.addEventListener('update', (event) => {
        const data = JSON.parse(event.data);

        // Update metrics
        if (data.updated_metrics) {
            updateCharts(data.updated_metrics);
        }

        // Prepend new items to table
        if (data.new_items && data.new_items.length > 0) {
            prependItems(data.new_items);
        }

        // Update status indicator
        document.getElementById('status').className = 'status-connected';
    });

    eventSource.addEventListener('error', (event) => {
        console.error('SSE error:', event);
        document.getElementById('status').className = 'status-disconnected';
        document.getElementById('status').textContent = '● Disconnected';

        // Retry connection after 5 seconds
        setTimeout(() => {
            eventSource.close();
            connectSSE();
        }, 5000);
    });
}

// Update charts with new data
function updateCharts(metrics) {
    sentimentChart.data.datasets[0].data = [
        metrics.sentiment_distribution.positive || 0,
        metrics.sentiment_distribution.neutral || 0,
        metrics.sentiment_distribution.negative || 0
    ];
    sentimentChart.update();

    // Update tag chart if provided
    // ... (similar logic)
}

// Prepend new items to table
function prependItems(items) {
    const tbody = document.getElementById('items-tbody');

    items.forEach(item => {
        const row = document.createElement('tr');
        row.innerHTML = `
            <td>${new Date(item.ingested_at).toLocaleTimeString()}</td>
            <td class="snippet">${item.text_snippet}</td>
            <td class="sentiment-${item.sentiment}">${item.sentiment}</td>
            <td>${item.score.toFixed(2)}</td>
            <td>${item.matched_tags.join(', ')}</td>
        `;

        // Insert at top
        tbody.insertBefore(row, tbody.firstChild);

        // Remove old rows (keep max 20)
        while (tbody.children.length > 20) {
            tbody.removeChild(tbody.lastChild);
        }
    });
}

// Initialize on page load
document.addEventListener('DOMContentLoaded', initDashboard);
```

---

## Configuration

### Environment Variables

| Variable | Description | Example |
|---|---|---|
| `DYNAMODB_TABLE` | **DASHBOARD** read table name | `"sentiment-items"` |
| `DYNAMODB_TABLE` | Primary table (fallback only) | `"sentiment-items"` |

---

## IAM Permissions Required

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "dynamodb:Query",
        "dynamodb:GetItem"
      ],
      "Resource": [
        "arn:aws:dynamodb:*:*:table/sentiment-items",
        "arn:aws:dynamodb:*:*:table/sentiment-items/index/by_sentiment",
        "arn:aws:dynamodb:*:*:table/sentiment-items/index/by_tag"
      ]
    },
    {
      "Effect": "Allow",
      "Action": [
        "dynamodb:Query"
      ],
      "Resource": [
        "arn:aws:dynamodb:*:*:table/sentiment-items"
      ],
      "Condition": {
        "StringEquals": {
          "dynamodb:Select": "SPECIFIC_ATTRIBUTES"
        }
      },
      "Description": "Fallback access to primary table (read-only, for emergency use)"
    },
    {
      "Effect": "Allow",
      "Action": [
        "logs:CreateLogGroup",
        "logs:CreateLogStream",
        "logs:PutLogEvents"
      ],
      "Resource": "arn:aws:logs:*:*:log-group:/aws/lambda/sentiment-dashboard:*"
    }
  ]
}
```

---

## Deployment

### Lambda Configuration

```hcl
resource "aws_lambda_function" "dashboard" {
  filename      = "dashboard_function.zip"
  function_name = "sentiment-dashboard"
  role          = aws_iam_role.lambda_dashboard.arn
  handler       = "handler.lambda_handler"
  runtime       = "python3.11"
  timeout       = 60  # Support long SSE connections
  memory_size   = 512

  environment {
    variables = {
      DYNAMODB_TABLE = aws_dynamodb_table.sentiment_items.name
    }
  }
}

resource "aws_lambda_function_url" "dashboard" {
  function_name      = aws_lambda_function.dashboard.function_name
  authorization_type = "NONE"  # Public for demo

  cors {
    allow_origins     = ["*"]
    allow_methods     = ["GET", "POST"]
    allow_headers     = ["content-type"]
    max_age           = 86400
  }
}

output "dashboard_url" {
  value       = aws_lambda_function_url.dashboard.function_url
  description = "Dashboard URL for demo"
}
```

---

## Testing

### Integration Test

```python
# tests/integration/test_dashboard.py
import pytest
import requests

def test_dashboard_loads():
    """Test dashboard HTML endpoint."""
    response = requests.get("https://LAMBDA_FUNCTION_URL/")

    assert response.status_code == 200
    assert "Sentiment Analyzer" in response.text

def test_metrics_endpoint():
    """Test metrics API endpoint."""
    response = requests.get("https://LAMBDA_FUNCTION_URL/api/metrics")

    assert response.status_code == 200
    data = response.json()

    assert 'summary' in data
    assert 'sentiment_distribution' in data
    assert 'recent_items' in data

def test_sse_stream():
    """Test Server-Sent Events stream."""
    import sseclient  # pip install sseclient-py

    response = requests.get("https://LAMBDA_FUNCTION_URL/api/stream", stream=True)
    client = sseclient.SSEClient(response)

    # Read first event (within 10 seconds)
    for event in client.events():
        if event.event == 'update':
            data = json.loads(event.data)
            assert 'new_items' in data
            break
```

---

## Performance SLA

- **Cold start**: <2 seconds (FastAPI + static files)
- **HTML load**: <500ms
- **Metrics API**: <200ms (DynamoDB query + aggregation)
- **SSE latency**: <10 seconds (5s poll interval + processing)
- **Memory**: 512 MB
- **Timeout**: 60 seconds (supports SSE connections up to 1 minute)

---

## Monitoring & Alarms

### CloudWatch Metrics

| Metric | Description |
|---|---|
| `DashboardRequests` | Total HTTP requests |
| `SSEConnections` | Active SSE connections |
| `MetricsAPILatency` | Time to return metrics |
| `DashboardErrors` | HTTP 500 errors |

### Alarms

1. **High error rate**: `DashboardErrors > 10` in 5 minutes
2. **Slow metrics**: `MetricsAPILatency > 1000ms` (P95)
3. **No SSE connections**: `SSEConnections = 0` for 10 minutes (demo inactive)
