# Quickstart: SSE Streaming Lambda

**Feature**: 016-sse-streaming-lambda
**Date**: 2025-12-02

## Prerequisites

- Python 3.13
- Docker (for building Lambda container)
- AWS CLI configured with appropriate credentials
- Terraform CLI
- Access to ECR for pushing container images

## Local Development

### 1. Set Up Virtual Environment

```bash
cd /home/traylorre/projects/sentiment-analyzer-gsk
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### 2. Run SSE Lambda Locally

The SSE Lambda uses uvicorn directly (not Mangum):

```bash
# Set required environment variables
export DYNAMODB_TABLE=dev-sentiment-data
export ENVIRONMENT=dev
export SSE_HEARTBEAT_INTERVAL=30
export SSE_MAX_CONNECTIONS=100
export SSE_POLL_INTERVAL=5

# Run with uvicorn
cd src/lambdas/sse_streaming
uvicorn handler:app --host 0.0.0.0 --port 8081 --reload
```

### 3. Test SSE Connection

```bash
# In a new terminal
curl -N http://localhost:8081/api/v2/stream

# Expected output (events stream continuously):
# event: heartbeat
# id: evt_abc123
# data: {"timestamp":"2025-12-02T10:30:00Z","connections":1}
#
# event: metrics
# id: evt_def456
# data: {"total":150,"positive":80,...}
```

### 4. Run Unit Tests

```bash
# Run SSE streaming unit tests
PYTHONPATH=. pytest tests/unit/sse_streaming/ -v

# Run all unit tests
PYTHONPATH=. pytest tests/unit/ -v
```

## Docker Build

### 1. Build Container Image

```bash
cd src/lambdas/sse_streaming

docker build -t sse-streaming-lambda:latest .
```

### 2. Test Container Locally

```bash
docker run -p 8081:8080 \
  -e DYNAMODB_TABLE=dev-sentiment-data \
  -e ENVIRONMENT=dev \
  -e AWS_LWA_INVOKE_MODE=RESPONSE_STREAM \
  sse-streaming-lambda:latest
```

### 3. Push to ECR

```bash
# Login to ECR
aws ecr get-login-password --region us-east-1 | \
  docker login --username AWS --password-stdin <account>.dkr.ecr.us-east-1.amazonaws.com

# Tag and push
docker tag sse-streaming-lambda:latest <account>.dkr.ecr.us-east-1.amazonaws.com/sse-streaming-lambda:latest
docker push <account>.dkr.ecr.us-east-1.amazonaws.com/sse-streaming-lambda:latest
```

## Terraform Deployment

### 1. Initialize Terraform

```bash
cd infrastructure/terraform
terraform init
```

### 2. Plan Changes

```bash
terraform plan -var="environment=preprod"
```

### 3. Apply Changes

```bash
terraform apply -var="environment=preprod"
```

### 4. Get Function URL

```bash
terraform output sse_lambda_function_url
```

## Verifying Deployment

### 1. Test SSE Endpoint

```bash
# Get the SSE Lambda Function URL from Terraform output
SSE_URL=$(terraform output -raw sse_lambda_function_url)

# Test global stream
curl -N "${SSE_URL}/api/v2/stream"

# Test stream status (non-streaming)
curl "${SSE_URL}/api/v2/stream/status"
```

### 2. Run E2E Tests

```bash
# Set preprod API URL
export PREPROD_API_URL=<dashboard-lambda-url>
export PREPROD_SSE_URL=<sse-lambda-url>

# Run E2E tests
PYTHONPATH=. pytest tests/e2e/test_sse.py -v -m preprod
```

## Frontend Configuration

Update `src/dashboard/config.js`:

```javascript
const CONFIG = {
    API_BASE_URL: '',  // Dashboard Lambda (REST)
    SSE_BASE_URL: 'https://xxx.lambda-url.us-east-1.on.aws',  // SSE Lambda
    // ... rest unchanged
};
```

## Troubleshooting

### SSE Connection Immediately Closes

1. Check Lambda invoke mode is `RESPONSE_STREAM`
2. Verify Lambda Web Adapter is installed in container
3. Check `AWS_LWA_INVOKE_MODE=RESPONSE_STREAM` env var

### No Events Received

1. Check DynamoDB table has data
2. Verify Lambda has read permissions on table
3. Check CloudWatch logs for errors

### 503 Service Unavailable

1. Connection limit (100) reached
2. Wait for connections to close or Lambda to scale
3. Check `SSE_MAX_CONNECTIONS` environment variable

### Cold Start Slow (>3s)

1. Consider provisioned concurrency for SSE Lambda
2. Optimize Docker image size
3. Reduce dependencies

## Related Documentation

- [Spec](./spec.md) - Feature specification
- [Research](./research.md) - Technical decisions
- [Data Model](./data-model.md) - Entity definitions
- [Contracts](./contracts/sse-events.md) - API contracts
