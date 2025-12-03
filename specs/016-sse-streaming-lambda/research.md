# Research: SSE Streaming Lambda

**Feature**: 016-sse-streaming-lambda
**Date**: 2025-12-02

## Research Tasks

### 1. AWS Lambda Web Adapter for RESPONSE_STREAM

**Decision**: Use AWS Lambda Web Adapter for RESPONSE_STREAM mode with FastAPI

**Rationale**:
- AWS-maintained solution specifically designed for streaming responses
- Supports Python/FastAPI applications natively
- Enables true SSE streaming (not buffered like Mangum)
- Requires Docker-based Lambda deployment (acceptable per spec assumptions)
- Version 0.9.1 is stable and production-ready

**Implementation Pattern**:
```dockerfile
FROM python:3.13-slim
COPY --from=public.ecr.aws/awsguru/aws-lambda-adapter:0.9.1 /lambda-adapter /opt/extensions/
# ... rest of app
```

**Environment Configuration**:
- Set `AWS_LWA_INVOKE_MODE=RESPONSE_STREAM`
- Configure Function URL with `invoke_mode = "RESPONSE_STREAM"`

**Alternatives Considered**:
- **Mangum**: Does not support RESPONSE_STREAM mode (confirmed via GitHub issue #341)
- **Custom Lambda handler**: Too complex, would need to implement SSE protocol manually
- **API Gateway WebSocket**: Overkill for one-way server push

---

### 2. Dashboard Lambda Mode Verification

**Decision**: Keep dashboard Lambda in BUFFERED mode with Mangum

**Rationale**:
- Existing Mangum integration works correctly for REST APIs
- BUFFERED mode properly unwraps Lambda proxy responses
- No code changes needed to existing dashboard Lambda
- E2E tests already pass in BUFFERED mode

**Implementation**:
- Change dashboard Lambda's `function_url_invoke_mode` back to `"BUFFERED"`
- This is a one-line Terraform change

**Alternatives Considered**:
- Migrate dashboard to Lambda Web Adapter: Unnecessary complexity, Mangum works fine for REST

---

### 3. SSE Event Format and Protocol

**Decision**: Use standard SSE protocol with sse-starlette EventSourceResponse

**Rationale**:
- sse-starlette 3.0.3 already in project dependencies
- Provides `EventSourceResponse` that handles SSE protocol correctly
- Supports async generators for event streaming
- Built-in support for event types, IDs, and retry intervals

**Event Format**:
```text
event: metrics
id: evt_abc123
data: {"total": 150, "positive": 80, "neutral": 45, "negative": 25}

event: heartbeat
id: evt_def456
data: {"timestamp": "2025-12-02T10:30:00Z", "connections": 15}

event: sentiment_update
id: evt_ghi789
data: {"ticker": "AAPL", "score": 0.85, "label": "positive"}
```

**Alternatives Considered**:
- Raw StreamingResponse: More manual work, doesn't handle SSE protocol
- WebSockets: Bidirectional (overkill for server push)

---

### 4. Connection Pool Management

**Decision**: In-memory connection tracking with thread-safe counter

**Rationale**:
- Lambda instances are isolated; per-instance tracking is sufficient
- 100 connection limit per instance is reasonable for Lambda memory constraints
- Thread-safe counter prevents race conditions during concurrent connects/disconnects
- No external state store needed (avoids DynamoDB/Redis complexity)

**Implementation Pattern**:
```python
import threading

class ConnectionManager:
    def __init__(self, max_connections: int = 100):
        self._count = 0
        self._lock = threading.Lock()
        self.max_connections = max_connections

    def acquire(self) -> bool:
        with self._lock:
            if self._count >= self.max_connections:
                return False
            self._count += 1
            return True

    def release(self):
        with self._lock:
            self._count = max(0, self._count - 1)
```

**Alternatives Considered**:
- DynamoDB connection tracking: Overkill, adds latency and cost
- Redis: Not in current stack, unnecessary complexity
- asyncio.Lock: Less robust for mixed sync/async code paths

---

### 5. DynamoDB Polling Strategy

**Decision**: Poll DynamoDB at 5-second intervals (configurable via environment variable)

**Rationale**:
- Matches existing dashboard Lambda pattern (uses same `aggregate_dashboard_metrics` function)
- 5-second interval balances latency (SC-001: <5s) with DynamoDB read costs
- Configurable via `SSE_POLL_INTERVAL` environment variable
- Reuses existing shared utilities from `src/lambdas/shared/`

**Implementation**:
- Import `get_table` and `aggregate_dashboard_metrics` from shared modules
- Poll on configurable interval, emit events only when data changes
- Compare current metrics with previous to avoid redundant events

**Alternatives Considered**:
- DynamoDB Streams: More complex, requires additional Lambda subscription
- SNS/SQS push: Adds infrastructure, increases latency
- Shorter interval (<5s): Increases costs without proportional benefit

---

### 6. Docker Lambda Packaging

**Decision**: Docker-based Lambda with slim Python base image

**Rationale**:
- Required for AWS Lambda Web Adapter (extension must be copied into image)
- python:3.13-slim provides minimal footprint for faster cold starts
- Multi-stage build reduces final image size
- ECR for container registry (existing infrastructure)

**Dockerfile Structure**:
```dockerfile
FROM python:3.13-slim as builder
# Install dependencies

FROM python:3.13-slim
COPY --from=public.ecr.aws/awsguru/aws-lambda-adapter:0.9.1 /lambda-adapter /opt/extensions/
COPY --from=builder /app /app
CMD ["python", "-m", "uvicorn", "handler:app", "--host", "0.0.0.0", "--port", "8080"]
```

**Alternatives Considered**:
- ZIP deployment: Not compatible with Lambda Web Adapter
- Larger base images: Slower cold starts, larger storage costs

---

### 7. Terraform Module for Docker Lambda

**Decision**: Extend existing Lambda module to support Docker image source

**Rationale**:
- Existing `modules/lambda` already supports S3 deployment
- Adding `image_uri` parameter enables Docker-based Lambdas
- Keeps infrastructure DRY (Don't Repeat Yourself)
- One module serves both ZIP and Docker deployment patterns

**Module Changes**:
```hcl
variable "image_uri" {
  description = "ECR image URI for Docker-based Lambda"
  type        = string
  default     = null
}

resource "aws_lambda_function" "this" {
  # Conditional: use image_uri OR s3_bucket/s3_key
  package_type = var.image_uri != null ? "Image" : "Zip"
  image_uri    = var.image_uri
  # ... existing config
}
```

**Alternatives Considered**:
- Separate Docker Lambda module: Code duplication, harder maintenance
- Hardcode in main.tf: Less reusable, violates module abstraction

---

### 8. Frontend SSE URL Configuration

**Decision**: Add `SSE_BASE_URL` to frontend config.js

**Rationale**:
- Minimal change to existing frontend
- Maintains backward compatibility (REST endpoints unchanged)
- SSE URL injected via build/deployment process
- Existing reconnection logic works without modification

**Implementation**:
```javascript
const CONFIG = {
    API_BASE_URL: '',  // Existing REST endpoint
    SSE_BASE_URL: 'https://xxx.lambda-url.region.on.aws',  // New SSE Lambda
    // ... rest unchanged
};
```

**Alternatives Considered**:
- Environment variable injection at runtime: More complex, requires server-side rendering
- Same URL with path routing: Not possible with two separate Lambdas

---

## Summary

| Topic | Decision | Confidence |
|-------|----------|------------|
| Streaming Adapter | AWS Lambda Web Adapter 0.9.1 | High |
| Dashboard Mode | Keep BUFFERED with Mangum | High |
| SSE Library | sse-starlette EventSourceResponse | High |
| Connection Tracking | In-memory with thread lock | High |
| Data Source | DynamoDB polling (5s interval) | High |
| Packaging | Docker with slim Python image | High |
| Terraform | Extend existing module for Docker | High |
| Frontend | Add SSE_BASE_URL config | High |

All research complete. No NEEDS CLARIFICATION items remain.
