# Research: E2E Validation Suite

**Feature**: 008-e2e-validation-suite
**Date**: 2025-11-28

## Research Summary

This document captures research findings for implementing the E2E validation suite. All technical decisions are aligned with the project constitution and existing codebase patterns.

---

## 1. Synthetic Data Generation Approach

### Decision
Use factory-based synthetic data generators with deterministic seeding for reproducibility.

### Rationale
- Constitution requires synthetic test data for E2E (Section 7: "Synthetic Test Data")
- Deterministic seeds enable reproducible test failures and debugging
- Factory pattern allows flexible data generation while maintaining type safety

### Alternatives Considered
| Alternative | Why Rejected |
|-------------|--------------|
| Recorded/replayed API responses | Not deterministic, stale over time, large fixture files |
| Random data without seeds | Non-reproducible failures, flaky tests |
| Shared test fixtures | Cross-test pollution, ordering dependencies |

### Implementation Pattern
```python
# tests/e2e/fixtures/tiingo.py
from dataclasses import dataclass
from datetime import datetime
import random

@dataclass
class SyntheticNewsArticle:
    id: str
    title: str
    description: str
    published_date: datetime
    source: str
    tickers: list[str]
    sentiment_score: float  # Pre-computed for test oracle

def generate_tiingo_news(seed: int, ticker: str, count: int = 10) -> list[dict]:
    """Generate deterministic Tiingo news responses."""
    random.seed(seed)
    articles = []
    for i in range(count):
        sentiment = random.uniform(-1.0, 1.0)
        articles.append({
            "id": f"test-{seed}-{ticker}-{i}",
            "title": f"Test article about {ticker} #{i}",
            "publishedDate": datetime.utcnow().isoformat(),
            "source": "test-source",
            "tickers": [ticker],
            "_synthetic_sentiment": sentiment  # Test oracle value
        })
    return articles
```

---

## 2. Test Data Isolation Strategy

### Decision
UUID-prefixed test data with automatic cleanup via pytest fixtures.

### Rationale
- Constitution requires test runs not to interfere with each other
- UUID prefixes ensure uniqueness across concurrent runs
- Fixture-based cleanup guarantees teardown even on test failure

### Alternatives Considered
| Alternative | Why Rejected |
|-------------|--------------|
| Shared test users | Cross-run pollution, ordering dependencies |
| Database truncation | Unsafe for preprod, could delete real data |
| Time-based cleanup | Race conditions, orphaned data |

### Implementation Pattern
```python
# tests/e2e/conftest.py
import uuid
import pytest
from typing import Generator

@pytest.fixture(scope="session")
def test_run_id() -> str:
    """Unique identifier for this test run."""
    return f"e2e-{uuid.uuid4().hex[:8]}"

@pytest.fixture(scope="session")
def test_email_domain(test_run_id: str) -> str:
    """Unique email domain for this test run."""
    return f"{test_run_id}@test.sentiment-analyzer.local"

@pytest.fixture(scope="session", autouse=True)
def cleanup_test_data(test_run_id: str) -> Generator[None, None, None]:
    """Cleanup all test data after run completes."""
    yield
    # Cleanup logic runs after all tests
    cleanup_by_prefix(test_run_id)
```

---

## 3. External API Interception Mechanism

### Decision
Use `httpx` transport mocking at the adapter layer with synthetic response injection.

### Rationale
- Existing adapters (Tiingo, Finnhub) use httpx for HTTP calls
- Transport-level mocking is more reliable than URL-based mocking
- Allows testing adapter error handling and retry logic

### Alternatives Considered
| Alternative | Why Rejected |
|-------------|--------------|
| `responses` library | Only mocks `requests`, not `httpx` |
| `httpretty` | Thread-safety issues, doesn't support async |
| Service virtualization (WireMock) | Overkill for this use case, additional infra |

### Implementation Pattern
```python
# tests/e2e/helpers/mock_transport.py
import httpx
from typing import Callable

class SyntheticTransport(httpx.MockTransport):
    """Transport that returns synthetic responses for external APIs."""

    def __init__(self, handlers: dict[str, Callable]):
        self.handlers = handlers
        super().__init__(self._handle_request)

    def _handle_request(self, request: httpx.Request) -> httpx.Response:
        for pattern, handler in self.handlers.items():
            if pattern in str(request.url):
                return handler(request)
        raise ValueError(f"No handler for {request.url}")
```

---

## 4. CloudWatch Query Strategy for Observability Tests

### Decision
Use CloudWatch Logs Insights with correlation IDs for log verification; CloudWatch GetMetricData for metrics.

### Rationale
- CloudWatch Logs Insights provides fast, indexed querying
- Correlation IDs (request ID) enable precise log matching
- GetMetricData API supports multiple metrics in single call

### Alternatives Considered
| Alternative | Why Rejected |
|-------------|--------------|
| FilterLogEvents API | Slow for large log groups, no query language |
| Polling CloudWatch Metrics | Multiple API calls, higher latency |
| X-Ray trace-based log lookup | More complex, X-Ray retention is shorter |

### Implementation Pattern
```python
# tests/e2e/helpers/cloudwatch.py
import boto3
from datetime import datetime, timedelta

def query_logs(log_group: str, request_id: str, timeout_seconds: int = 30) -> list[dict]:
    """Query CloudWatch Logs for entries matching request ID."""
    client = boto3.client("logs")
    query = f'fields @timestamp, @message | filter @requestId = "{request_id}"'

    response = client.start_query(
        logGroupName=log_group,
        startTime=int((datetime.utcnow() - timedelta(minutes=5)).timestamp()),
        endTime=int(datetime.utcnow().timestamp()),
        queryString=query
    )

    # Poll for results (with timeout)
    # ...
    return results
```

---

## 5. X-Ray Trace Validation Approach

### Decision
Use X-Ray BatchGetTraces API with trace ID extraction from response headers.

### Rationale
- Lambda responses include X-Ray trace ID in `X-Amzn-Trace-Id` header
- BatchGetTraces returns full trace with all segments
- Enables validation of cross-Lambda trace propagation

### Alternatives Considered
| Alternative | Why Rejected |
|-------------|--------------|
| X-Ray GetTraceSummaries | Only returns summary, not full segment data |
| X-Ray Analytics | Overkill for individual trace validation |
| CloudWatch ServiceLens | UI-focused, no programmatic API |

### Implementation Pattern
```python
# tests/e2e/helpers/xray.py
import boto3
import time

def get_trace(trace_id: str, max_wait_seconds: int = 60) -> dict | None:
    """Retrieve X-Ray trace by ID, waiting for segments to propagate."""
    client = boto3.client("xray")

    for _ in range(max_wait_seconds // 5):
        response = client.batch_get_traces(TraceIds=[trace_id])
        if response["Traces"]:
            return response["Traces"][0]
        time.sleep(5)

    return None

def validate_trace_segments(trace: dict, expected_segments: list[str]) -> bool:
    """Validate trace contains expected Lambda segments."""
    segment_names = {seg["Name"] for seg in trace.get("Segments", [])}
    return all(name in segment_names for name in expected_segments)
```

---

## 6. Magic Link Email Verification

### Decision
Use SendGrid test mode (sandbox) with Event Webhook for delivery confirmation.

### Rationale
- SendGrid sandbox mode doesn't actually send emails
- Event Webhook provides delivery/open/click events
- Avoids rate limits and costs of real email delivery

### Alternatives Considered
| Alternative | Why Rejected |
|-------------|--------------|
| Real email delivery + IMAP | Slow, unreliable, requires email infrastructure |
| Mock SendGrid entirely | Doesn't test actual SendGrid integration |
| Mailhog/Mailpit | Additional infrastructure, not cloud-native |

### Implementation Pattern
```python
# tests/e2e/helpers/sendgrid.py
import boto3
from datetime import datetime, timedelta

def wait_for_email_event(
    message_id: str,
    event_type: str = "delivered",
    timeout_seconds: int = 60
) -> dict | None:
    """Wait for SendGrid event via webhook → SNS → DynamoDB lookup."""
    # SendGrid webhook → API Gateway → Lambda → DynamoDB
    # Query DynamoDB for event matching message_id
    pass
```

---

## 7. SSE Testing Approach

### Decision
Use `httpx-sse` library with async streaming and timeout handling.

### Rationale
- httpx-sse provides clean async SSE client
- Supports reconnection with `Last-Event-ID`
- Integrates with existing httpx-based test infrastructure

### Alternatives Considered
| Alternative | Why Rejected |
|-------------|--------------|
| `sseclient-py` | Sync only, doesn't support httpx |
| Raw streaming with httpx | More code, error-prone SSE parsing |
| WebSocket alternative | Different protocol, not testing actual SSE |

### Implementation Pattern
```python
# tests/e2e/test_sse.py
import httpx_sse
import asyncio

async def test_sse_receives_updates(api_client, config_id, access_token):
    """Verify SSE endpoint pushes sentiment updates."""
    events_received = []

    async with httpx_sse.aconnect_sse(
        api_client,
        "GET",
        f"/api/v2/configurations/{config_id}/stream",
        headers={"Authorization": f"Bearer {access_token}"}
    ) as event_source:
        async for event in asyncio.wait_for(event_source.aiter_sse(), timeout=30):
            events_received.append(event)
            if len(events_received) >= 2:
                break

    assert len(events_received) >= 1
    assert events_received[0].event in ("sentiment_update", "heartbeat")
```

---

## 8. Rate Limit Testing Strategy

### Decision
Parallel request burst with response code counting.

### Rationale
- Rate limits are per-user/per-IP, need to exceed threshold quickly
- Parallel requests simulate realistic abuse scenarios
- Count 429 responses to verify limit enforcement

### Alternatives Considered
| Alternative | Why Rejected |
|-------------|--------------|
| Sequential requests | Too slow to trigger limits before test timeout |
| Mock rate limiter | Doesn't test actual rate limit implementation |
| Lower rate limits for tests | Modifies production config, risky |

### Implementation Pattern
```python
# tests/e2e/test_rate_limiting.py
import asyncio
import httpx

async def test_rate_limit_enforced(api_client, access_token):
    """Verify rate limiting triggers after threshold."""

    async def make_request():
        return await api_client.get(
            "/api/v2/configurations",
            headers={"Authorization": f"Bearer {access_token}"}
        )

    # Fire 150 requests (limit is 100/min)
    responses = await asyncio.gather(*[make_request() for _ in range(150)])

    status_codes = [r.status_code for r in responses]
    assert status_codes.count(429) > 0, "Expected some rate-limited responses"
    assert status_codes.count(200) <= 100, "Should not exceed rate limit"

    # Verify retry_after header
    limited_response = next(r for r in responses if r.status_code == 429)
    assert "retry-after" in limited_response.headers
```

---

## 9. Circuit Breaker Testing Approach

### Decision
Inject failures via synthetic data handlers, verify circuit state via DynamoDB.

### Rationale
- Circuit breaker state is persisted in DynamoDB (`CB#{service}`)
- Synthetic handlers can return errors to trigger circuit open
- Direct DynamoDB query verifies circuit state transitions

### Alternatives Considered
| Alternative | Why Rejected |
|-------------|--------------|
| Wait for natural failures | Non-deterministic, slow |
| Modify circuit breaker config | Changes production behavior |
| Mock circuit breaker | Doesn't test actual implementation |

### Implementation Pattern
```python
# tests/e2e/test_circuit_breaker.py

async def test_circuit_breaker_opens_after_failures(
    api_client,
    dynamodb_table,
    synthetic_tiingo_handler
):
    """Verify circuit breaker opens after threshold failures."""

    # Configure synthetic handler to return 500 errors
    synthetic_tiingo_handler.set_error_mode(True)

    # Make 5 requests (circuit threshold is 5 failures in 5 minutes)
    for _ in range(5):
        await api_client.get("/api/v2/configurations/test/sentiment")

    # Query circuit breaker state in DynamoDB
    response = dynamodb_table.get_item(
        Key={"pk": "CB#tiingo", "sk": "STATE"}
    )

    assert response["Item"]["state"] == "OPEN"
    assert "opened_at" in response["Item"]
```

---

## 10. GitHub Actions Workflow Design

### Decision
Dedicated E2E workflow triggered on push to main/preprod branches, with manual trigger option.

### Rationale
- E2E tests are expensive, shouldn't run on every PR
- Manual trigger enables on-demand validation
- Separate workflow from unit/integration tests for clarity

### Alternatives Considered
| Alternative | Why Rejected |
|-------------|--------------|
| Run E2E in main CI workflow | Too slow for every PR |
| Scheduled-only E2E | Delays feedback on breaking changes |
| Local E2E execution | Violates constitution (preprod only) |

### Implementation Pattern
```yaml
# .github/workflows/e2e-preprod.yml
name: E2E Tests (Preprod)

on:
  push:
    branches: [main]
  workflow_dispatch:  # Manual trigger

env:
  AWS_REGION: us-east-1
  ENVIRONMENT: preprod

jobs:
  e2e:
    runs-on: ubuntu-latest
    environment: preprod

    steps:
      - uses: actions/checkout@v4

      - uses: aws-actions/configure-aws-credentials@v4
        with:
          role-to-assume: ${{ secrets.AWS_ROLE_ARN }}
          aws-region: ${{ env.AWS_REGION }}

      - name: Run E2E Tests
        run: |
          pytest tests/e2e/ \
            --junitxml=reports/e2e.xml \
            -v --tb=short

      - name: Upload Results
        uses: actions/upload-artifact@v4
        with:
          name: e2e-results
          path: reports/
```

---

## Dependencies

| Dependency | Version | Purpose |
|------------|---------|---------|
| pytest | ^8.0 | Test framework |
| pytest-asyncio | ^0.23 | Async test support |
| pytest-xdist | ^3.5 | Parallel test execution |
| httpx | ^0.27 | HTTP client |
| httpx-sse | ^0.4 | SSE client |
| boto3 | ^1.34 | AWS SDK |
| pydantic | ^2.5 | Data validation |

---

## Risk Assessment

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| Flaky tests due to timing | Medium | High | Generous timeouts, retry logic, deterministic data |
| Preprod cost increase | Low | Medium | Cleanup fixtures, test data TTL |
| CloudWatch query latency | Medium | Low | Async queries, parallel validation |
| X-Ray trace propagation delay | Medium | Medium | Wait/retry pattern with timeout |
