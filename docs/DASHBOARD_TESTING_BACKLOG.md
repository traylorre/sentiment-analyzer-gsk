# Dashboard Testing Backlog - Post-Production Deep Dive

**Created**: 2025-11-22
**Status**: BACKLOG (implement after first production deployment)
**Priority**: MEDIUM
**Owner**: TBD

---

## Executive Summary

This document outlines comprehensive testing for the dashboard Lambda that goes beyond current unit and integration tests. These tests focus on **non-functional requirements** (NFRs) like performance, resilience, scalability, and operational characteristics.

**Current State**: Dashboard has solid functional test coverage (8/10)
**Goal**: Achieve 10/10 with NFR testing for production confidence

---

## Test Categories

### 1. Performance Testing

#### 1.1 Response Time / Latency
**Priority**: HIGH
**Rationale**: Dashboard Lambda has P95 latency alarm at 1 second (`infrastructure/terraform/modules/monitoring/main.tf:144`)

**Tests to Add**:
- [ ] **Cold start time** - First invocation after deployment
  - Target: <3 seconds (Lambda Python 3.13 + 50MB package)
  - Measure: Time from invoke to first byte
  - Track: Across different package sizes (current ~50MB)

- [ ] **Warm invocation latency** - Subsequent requests
  - Target: <500ms P50, <1s P95 (alarm threshold)
  - Measure: Full request/response cycle
  - Test scenarios:
    - `/health` endpoint (simplest)
    - `/api/metrics` with varying hours parameter (1h, 24h, 168h)
    - `/api/items` with different limits (10, 50, 100)

- [ ] **DynamoDB query performance**
  - Measure: Query time vs table size
  - Test with: Empty table, 1K items, 10K items, 100K items
  - Verify: GSI usage (by_sentiment, by_status) vs table scan

- [ ] **Dependency import overhead**
  - Measure: Time to import fastapi, mangum, sse-starlette
  - Baseline: Record after PR #50 dependency bundling
  - Track: Changes over time as dependencies update

**Implementation**:
```python
# tests/performance/test_dashboard_latency.py

import time
import pytest
from fastapi.testclient import TestClient

@pytest.mark.performance
class TestDashboardPerformance:
    def test_cold_start_time(self, client, auth_headers):
        """Measure cold start time for dashboard Lambda."""
        # Simulate cold start by reimporting handler
        from importlib import reload
        from src.lambdas.dashboard import handler

        start = time.perf_counter()
        reload(handler)
        test_client = TestClient(handler.app)
        response = test_client.get("/health")
        duration = time.perf_counter() - start

        assert response.status_code == 200
        assert duration < 3.0  # Cold start SLA
        print(f"Cold start time: {duration:.2f}s")

    def test_warm_invocation_p95_latency(self, client, auth_headers):
        """Test P95 latency is under 1 second (alarm threshold)."""
        latencies = []

        # Run 100 requests to get P95
        for _ in range(100):
            start = time.perf_counter()
            response = client.get("/api/metrics", headers=auth_headers)
            duration = time.perf_counter() - start
            latencies.append(duration)
            assert response.status_code == 200

        # Calculate P95
        latencies.sort()
        p95 = latencies[int(len(latencies) * 0.95)]

        assert p95 < 1.0  # P95 SLA from CloudWatch alarm
        print(f"P50: {latencies[50]:.3f}s, P95: {p95:.3f}s, P99: {latencies[99]:.3f}s")
```

---

#### 1.2 Memory Usage
**Priority**: MEDIUM
**Rationale**: Lambda memory affects cost and cold start time

**Tests to Add**:
- [ ] **Memory consumption** during normal operation
  - Target: <256MB (current Lambda memory allocation)
  - Measure: Peak memory usage during requests
  - Track: With/without large result sets

- [ ] **Memory leak detection** - Repeated requests
  - Target: No memory growth over 1000 requests
  - Measure: Memory before/after 1000 invocations
  - Detect: >10% growth indicates leak

**Implementation**:
```python
import psutil
import os

@pytest.mark.performance
def test_memory_consumption(client, auth_headers):
    """Measure peak memory usage during dashboard requests."""
    process = psutil.Process(os.getpid())

    # Baseline
    baseline_mb = process.memory_info().rss / 1024 / 1024

    # Make 100 requests
    for _ in range(100):
        client.get("/api/metrics", headers=auth_headers)

    # Peak
    peak_mb = process.memory_info().rss / 1024 / 1024

    assert peak_mb < 256  # Lambda memory limit
    print(f"Baseline: {baseline_mb:.1f}MB, Peak: {peak_mb:.1f}MB")
```

---

### 2. Resilience / Error Handling

#### 2.1 DynamoDB Failures
**Priority**: HIGH
**Rationale**: Dashboard depends entirely on DynamoDB availability

**Tests to Add**:
- [ ] **Table not found** (ResourceNotFoundException)
  - Expected: 503 Service Unavailable
  - User experience: "Service temporarily unavailable"

- [ ] **DynamoDB throttling** (ProvisionedThroughputExceededException)
  - Expected: 503 with retry-after header
  - Behavior: Graceful degradation, not crash

- [ ] **Network timeout** to DynamoDB
  - Expected: 504 Gateway Timeout
  - Timeout: <5 seconds (fail fast)

- [ ] **Partial query results** (LastEvaluatedKey pagination)
  - Expected: Handle pagination correctly
  - Verify: All items returned, not truncated

**Implementation**:
```python
@pytest.mark.resilience
class TestDynamoDBResilience:
    def test_table_not_found_returns_503(self, monkeypatch):
        """Test graceful handling when DynamoDB table doesn't exist."""
        # Override table name to non-existent
        monkeypatch.setenv("DYNAMODB_TABLE", "nonexistent-table-12345")

        from importlib import reload
        from src.lambdas.dashboard import handler
        reload(handler)

        client = TestClient(handler.app)
        response = client.get("/api/metrics", headers=auth_headers)

        assert response.status_code == 503
        assert "unavailable" in response.json()["detail"].lower()

    @mock_aws
    def test_dynamodb_throttling_graceful_degradation(self, client, auth_headers):
        """Test dashboard degrades gracefully when DynamoDB is throttled."""
        # moto doesn't simulate throttling well
        # In production, use chaos testing (see TC-003)
        pass  # Implement with chaos engineering tools
```

---

#### 2.2 SSE Stream Resilience
**Priority**: MEDIUM
**Rationale**: SSE streams are long-lived connections prone to issues

**Tests to Add**:
- [ ] **Client disconnect detection** - Verify stream stops when client disconnects
- [ ] **Lambda timeout handling** - Test behavior at 15-minute Lambda timeout
- [ ] **DynamoDB error during stream** - Verify stream sends error event, doesn't crash
- [ ] **Backpressure handling** - Client can't keep up with events

**Implementation**:
```python
@pytest.mark.resilience
class TestSSEResilience:
    @pytest.mark.asyncio
    async def test_sse_client_disconnect_detection(self):
        """Test SSE stream detects client disconnect and stops gracefully."""
        # This requires async client and manual connection management
        # Deferred to E2E testing or manual validation
        pass

    def test_sse_lambda_timeout_handling(self):
        """Test SSE stream behavior near Lambda 15-minute timeout."""
        # Run SSE stream for 14 minutes, verify graceful termination
        # Requires real Lambda environment (integration test)
        pass
```

---

### 3. Load / Scalability Testing

#### 3.1 Concurrent Requests
**Priority**: HIGH
**Rationale**: Dashboard has reserved concurrency = 10 (`infrastructure/terraform/main.tf:221`)

**Tests to Add**:
- [ ] **Concurrency limit enforcement** - Verify 10 concurrent requests max
  - Expected: 11th request queued or throttled (429 Too Many Requests)
  - Measure: Response time degradation at limit

- [ ] **Burst traffic handling** - 100 requests in 1 second
  - Expected: No crashes, graceful queuing
  - Verify: All requests eventually succeed

- [ ] **Sustained load** - 10 RPS for 5 minutes
  - Expected: No memory leaks, consistent latency
  - Measure: P50/P95/P99 latency stays stable

**Implementation**:
```python
import concurrent.futures

@pytest.mark.load
class TestDashboardLoad:
    def test_concurrent_request_limit(self, client, auth_headers):
        """Test dashboard handles concurrent requests up to limit."""

        def make_request():
            start = time.time()
            response = client.get("/api/metrics", headers=auth_headers)
            duration = time.time() - start
            return response.status_code, duration

        # Send 20 concurrent requests (2x the limit)
        with concurrent.futures.ThreadPoolExecutor(max_workers=20) as executor:
            futures = [executor.submit(make_request) for _ in range(20)]
            results = [f.result() for f in futures]

        # Verify all eventually succeeded
        status_codes = [r[0] for r in results]
        assert all(code in [200, 429] for code in status_codes)

        # Check latency degradation
        durations = [r[1] for r in results]
        max_duration = max(durations)
        assert max_duration < 5.0  # Should complete within 5s even when queued
```

---

#### 3.2 Large Data Sets
**Priority**: MEDIUM
**Rationale**: Dashboard queries entire time window (up to 168 hours)

**Tests to Add**:
- [ ] **Large result set** - 10K items in 24-hour window
  - Expected: Pagination works, no timeout
  - Measure: Query time, memory usage

- [ ] **Many tags** - 1000 unique tags in tag distribution
  - Expected: Tag aggregation doesn't timeout
  - Measure: Processing time

- [ ] **Long time window** - 168 hours (max allowed)
  - Expected: Query completes within 1 second P95
  - Verify: GSI used (not table scan)

**Implementation**:
```python
@pytest.mark.load
@mock_aws
class TestLargeDataSets:
    def test_large_result_set_10k_items(self, client, auth_headers):
        """Test dashboard handles 10K items in 24-hour window."""
        table = create_test_table()

        # Seed 10K items
        now = datetime.now(UTC)
        for i in range(10000):
            table.put_item(Item={
                "source_id": f"newsapi#article{i}",
                "timestamp": (now - timedelta(minutes=i % 1440)).isoformat(),
                "sentiment": ["positive", "neutral", "negative"][i % 3],
                "status": "analyzed",
            })

        # Query
        start = time.time()
        response = client.get("/api/metrics?hours=24", headers=auth_headers)
        duration = time.time() - start

        assert response.status_code == 200
        assert duration < 2.0  # Should complete quickly even with 10K items
        data = response.json()
        assert data["total"] == 10000
```

---

### 4. Security Testing

#### 4.1 API Key Validation
**Priority**: HIGH
**Rationale**: API key is the only authentication

**Tests to Add** (beyond existing):
- [ ] **Timing attack resistance** - Constant-time comparison
  - Verify: Time to reject invalid key is same as valid key
  - Prevent: Information leakage via timing

- [ ] **Key rotation** - Old key stops working immediately
  - Test: Change API_KEY environment variable
  - Verify: Old key rejected, new key accepted

- [ ] **Missing Bearer prefix** - Various malformed headers
  - Test: "Basic", "Token", no prefix, etc.
  - Verify: All rejected with 401

**Implementation**:
```python
@pytest.mark.security
class TestAPIKeySecurity:
    def test_timing_attack_resistance(self, client):
        """Test API key comparison is constant-time."""
        import statistics

        # Measure time to reject completely wrong key
        wrong_times = []
        for _ in range(100):
            start = time.perf_counter()
            client.get("/api/metrics", headers={"Authorization": "Bearer wrong-key"})
            wrong_times.append(time.perf_counter() - start)

        # Measure time to reject almost-correct key
        almost_times = []
        correct_key = os.environ["API_KEY"]
        almost_key = correct_key[:-1] + "X"
        for _ in range(100):
            start = time.perf_counter()
            client.get("/api/metrics", headers={"Authorization": f"Bearer {almost_key}"})
            almost_times.append(time.perf_counter() - start)

        # Statistical test: means should be similar (constant-time)
        wrong_mean = statistics.mean(wrong_times)
        almost_mean = statistics.mean(almost_times)

        # Allow 10% variance (timing attacks need <1% variance to exploit)
        assert abs(wrong_mean - almost_mean) / wrong_mean < 0.10
```

---

#### 4.2 Input Validation
**Priority**: MEDIUM
**Rationale**: Prevent injection attacks and DoS

**Tests to Add** (beyond existing):
- [ ] **SQL injection attempts** (shouldn't apply to DynamoDB, but verify)
- [ ] **NoSQL injection** - Test with crafted filter values
- [ ] **Path traversal** - Already tested in unit tests ✅
- [ ] **XSS in responses** - Verify JSON encoding prevents script injection
- [ ] **ReDoS (regex DoS)** - Test with pathological inputs

---

### 5. Operational / Observability Testing

#### 5.1 Logging
**Priority**: MEDIUM
**Rationale**: CloudWatch logs are primary debugging tool

**Tests to Add**:
- [ ] **Structured logging format** - All logs are JSON with required fields
  - Verify: timestamp, level, message, context (request_id, etc.)
  - Check: No PII in logs (sanitization works)

- [ ] **Error logging** - Errors include stack traces
  - Verify: Exceptions logged with full context
  - Check: No sensitive data in error messages

- [ ] **Log volume** - Verify not excessive (cost impact)
  - Measure: Logs per request
  - Target: <5 log lines per request (info level)

**Implementation**:
```python
@pytest.mark.operational
class TestLogging:
    def test_structured_logging_format(self, client, auth_headers, caplog):
        """Test all logs are structured JSON with required fields."""
        with caplog.at_level("INFO"):
            client.get("/api/metrics", headers=auth_headers)

        for record in caplog.records:
            # Verify structured format (python-json-logger)
            assert hasattr(record, "timestamp")
            assert hasattr(record, "level")
            assert hasattr(record, "message")
```

---

#### 5.2 Metrics / Monitoring
**Priority**: LOW
**Rationale**: CloudWatch metrics already configured

**Tests to Add**:
- [ ] **Custom metrics emission** - Verify metrics are sent to CloudWatch
  - Check: NewsAPIRateLimitHit, NewItemsIngested
  - Verify: Dimensions are correct (environment, etc.)

- [ ] **Alarm triggering** - Simulate conditions that should trigger alarms
  - Test: Error rate > threshold → alarm fires
  - Verify: SNS notification sent

---

### 6. Chaos Testing (TC-003)

**Priority**: LOW (post-production)
**Rationale**: Validate system behavior under failure conditions

**Related**: `docs/TECH_DEBT_REGISTRY.md` TC-003

**Tests to Add**:
- [ ] **Random Lambda failures** - Inject failures in 5% of requests
- [ ] **DynamoDB latency injection** - Add artificial delays
- [ ] **Network partitions** - Simulate AWS region issues
- [ ] **Resource exhaustion** - Fill up memory/CPU

**Tools to Consider**:
- AWS Fault Injection Simulator (FIS)
- Gremlin
- Chaos Mesh
- LocalStack Pro (for local chaos testing)

---

## Implementation Priorities

### Phase 1: Pre-Production (Before First Deploy) ✅
- [x] Unit tests for all endpoints (existing)
- [x] Integration tests with real DynamoDB (existing)
- [x] API key validation (existing)
- [x] Parameter validation (existing)

### Phase 2: Post-Production Week 1
**Goal**: Ensure production stability

- [ ] Performance: Cold start time measurement
- [ ] Performance: P95 latency verification
- [ ] Resilience: DynamoDB table not found
- [ ] Load: Concurrent request limit verification

### Phase 3: Post-Production Month 1
**Goal**: Long-term reliability confidence

- [ ] Load: Large dataset handling (10K items)
- [ ] Load: Sustained load testing (5 minutes)
- [ ] Resilience: DynamoDB error handling
- [ ] Security: Timing attack resistance

### Phase 4: Continuous (Ongoing)
**Goal**: Operational excellence

- [ ] Chaos testing (quarterly)
- [ ] Performance regression testing (per release)
- [ ] Security penetration testing (annually)

---

## Success Metrics

**Test Coverage**:
- Functional: 95%+ (currently ~90%) ✅
- Non-functional: 80%+ (currently ~0%)

**Performance**:
- Cold start: <3s (P95)
- Warm latency: <1s (P95) ← CloudWatch alarm threshold
- Memory: <256MB peak

**Resilience**:
- Zero crashes under load
- Graceful degradation on DynamoDB failures
- 100% request success under concurrency limit

**Operational**:
- Structured logs on all paths
- Custom metrics emitted correctly
- Alarms trigger as expected

---

## Tools & Frameworks

**Performance Testing**:
- `pytest-benchmark` - Microbenchmarks
- `locust` - Load testing
- `psutil` - Memory/CPU monitoring

**Chaos Testing**:
- AWS Fault Injection Simulator (FIS)
- `chaos-lambda` (AWS Labs)
- Gremlin (if budget allows)

**Security Testing**:
- `bandit` - Static analysis (already used) ✅
- `safety` - Dependency vulnerabilities (already used) ✅
- Manual penetration testing

---

## References

- **Current Test Coverage**: `tests/unit/test_dashboard_handler.py`, `tests/integration/test_dashboard_preprod.py`
- **CloudWatch Alarms**: `infrastructure/terraform/modules/monitoring/main.tf`
- **Lambda Concurrency**: `infrastructure/terraform/main.tf:221`
- **Tech Debt**: `docs/TECH_DEBT_REGISTRY.md` (TC-003: Chaos Testing)
- **Performance Requirements**: SC-12 in `docs/ON_CALL_SOP.md`

---

**Next Steps**:
1. Review this backlog with team
2. Prioritize Phase 2 tests for Week 1 post-production
3. Set up performance test infrastructure (locust, metrics collection)
4. Schedule chaos testing for Month 2

---

*Created: 2025-11-22*
*Owner: To be assigned after production deployment*
*Review Frequency: Monthly*
