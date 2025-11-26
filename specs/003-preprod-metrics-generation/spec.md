# 003: Preprod Metrics Generation

## Problem Statement

Observability tests in `test_observability_preprod.py` skip when CloudWatch metrics don't exist. This hides real issues because if the system is running correctly, metrics SHOULD exist. Currently, 6 `pytest.skip()` calls mask potential problems:

- Line 72: Skip when metrics namespace not found
- Line 122: Skip when no invocation metrics in last hour
- Line 130: Skip when no invocations in last hour
- Line 165: Skip when no duration metrics in last hour
- Line 200: Skip when no error metrics found
- Line 261, 281: Skip when log groups not found

## Goal

Guarantee that preprod deployment generates CloudWatch metrics so observability tests can validate real data instead of skipping.

## Requirements

### Functional Requirements

1. **FR-001:** During preprod deployment, invoke each Lambda at least once to generate metrics
2. **FR-002:** Wait for CloudWatch metrics to be queryable (up to 2 minutes)
3. **FR-003:** Verify metrics exist before running observability tests
4. **FR-004:** Convert all `pytest.skip()` calls to `pytest.fail()` after metrics are guaranteed

### Non-Functional Requirements

1. **NFR-001:** Metric generation adds < 3 minutes to deployment pipeline
2. **NFR-002:** No manual intervention required
3. **NFR-003:** Metrics must be from current deployment (not stale historical data)

## Technical Approach

### Phase 1: Add Warmup Step to CI Pipeline

Add a new CI step after preprod deployment but before integration tests:

```yaml
- name: Warm Up Lambdas for Metrics
  run: |
    # Invoke dashboard Lambda
    curl -H "X-API-Key: $API_KEY" "$DASHBOARD_URL/health"
    curl -H "X-API-Key: $API_KEY" "$DASHBOARD_URL/api/metrics"

    # Invoke ingestion Lambda (trigger SNS)
    aws lambda invoke --function-name preprod-sentiment-ingestion \
      --payload '{"source": "test"}' /dev/null

    # Invoke analysis Lambda
    aws lambda invoke --function-name preprod-sentiment-analysis \
      --payload '{"test": true}' /dev/null

    # Wait for metrics to propagate
    echo "Waiting 60s for CloudWatch metrics to be available..."
    sleep 60
```

### Phase 2: Update Observability Tests

Convert skips to failures:

```python
# BEFORE
if not metrics:
    pytest.skip("No invocation metrics in last hour")

# AFTER
assert metrics, (
    "No invocation metrics found. "
    "Warmup step should have generated metrics. "
    "Check CI logs for warmup failures."
)
```

### Phase 3: Add Metric Validation Step

Add explicit metric existence check before running tests:

```python
@pytest.fixture(scope="session")
def verify_metrics_exist(cloudwatch_client):
    """Verify warmup step generated metrics."""
    response = cloudwatch_client.list_metrics(
        Namespace="AWS/Lambda",
        Dimensions=[{"Name": "FunctionName", "Value": "preprod-sentiment-dashboard"}]
    )
    assert response["Metrics"], "No metrics found - warmup step may have failed"
```

## Files to Modify

1. `.github/workflows/deploy.yml` - Add warmup step
2. `tests/integration/test_observability_preprod.py` - Convert skips to assertions
3. `tests/conftest.py` - Add metric verification fixture

## Test Debt Resolution

This spec resolves:
- **TD-001:** Observability Tests Skip on Missing Metrics

## Acceptance Criteria

1. [ ] Warmup step invokes all Lambdas during preprod deploy
2. [ ] CloudWatch metrics are queryable within 2 minutes of warmup
3. [ ] Zero `pytest.skip()` calls remain in `test_observability_preprod.py`
4. [ ] Observability tests pass with real metric data
5. [ ] Pipeline time increase < 3 minutes

## Dependencies

- AWS Lambda invoke permissions in CI
- CloudWatch read permissions in CI
- API key available in CI environment
