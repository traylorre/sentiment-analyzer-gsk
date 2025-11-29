# Quickstart: E2E Validation Suite

**Feature**: 008-e2e-validation-suite
**Date**: 2025-11-28
**Status**: Implementation Complete

## Overview

This E2E validation suite provides comprehensive testing against the preprod AWS environment. It covers 12 user stories with 94+ test cases across authentication, configuration, sentiment analysis, alerts, notifications, and observability.

## Prerequisites

1. **AWS Credentials**: Access to preprod AWS account via GitHub Actions OIDC or local credentials
2. **Python 3.13**: Required for test execution
3. **Preprod Deployment**: Feature 006/007 deployed to preprod environment

## Local Development

> **Note**: E2E tests are designed to run in CI only (preprod environment). Local execution is for development/debugging only.

### Setup

```bash
# Clone and install
cd sentiment-analyzer-gsk
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev,test]"

# Verify AWS access (preprod)
aws sts get-caller-identity
```

### Environment Variables

```bash
# Required for E2E tests
export ENVIRONMENT=preprod
export AWS_REGION=us-east-1
export API_BASE_URL=https://api.preprod.sentiment-analyzer.com
export COGNITO_USER_POOL_ID=us-east-1_XXXXXX
export COGNITO_CLIENT_ID=XXXXXXXXXXXXXX
```

### Running Tests Locally (Development Only)

```bash
# Run single test file
pytest tests/e2e/test_auth_anonymous.py -v

# Run with specific marker
pytest tests/e2e/ -m "auth" -v

# Run with verbose output
pytest tests/e2e/ -v --tb=long

# Run with coverage
pytest tests/e2e/ --cov=tests/e2e --cov-report=term-missing
```

---

## CI Execution (Primary Method)

### Trigger E2E Tests

```bash
# Manual trigger via GitHub CLI
gh workflow run e2e-preprod.yml

# View run status
gh run list --workflow=e2e-preprod.yml

# Watch specific run
gh run watch <run-id>
```

### Workflow Location

`.github/workflows/e2e-preprod.yml`

### Trigger Conditions

- Push to `main` branch
- Manual `workflow_dispatch` trigger
- Scheduled (optional): nightly at 2 AM UTC

---

## Test Structure

```
tests/e2e/
├── conftest.py              # Fixtures: test_run_id, api_client, cleanup
├── fixtures/                # Synthetic data generators
│   ├── tiingo.py
│   ├── finnhub.py
│   └── sendgrid.py
├── helpers/                 # Test utilities
│   ├── auth.py              # create_anonymous_session(), verify_magic_link()
│   ├── api_client.py        # PreprodAPIClient
│   ├── cloudwatch.py        # query_logs(), get_metrics()
│   └── xray.py              # get_trace(), validate_segments()
└── test_*.py                # Test modules (12 total)
```

---

## Writing New Tests

### Basic Test Structure

```python
# tests/e2e/test_example.py
import pytest
from tests.e2e.helpers.api_client import PreprodAPIClient

@pytest.mark.e2e
@pytest.mark.asyncio
async def test_example_endpoint(
    api_client: PreprodAPIClient,
    test_run_id: str,
    access_token: str
):
    """Verify example endpoint returns expected response."""
    response = await api_client.get(
        "/api/v2/example",
        headers={"Authorization": f"Bearer {access_token}"}
    )

    assert response.status_code == 200
    assert "expected_field" in response.json()
```

### Using Synthetic Data

```python
@pytest.mark.e2e
@pytest.mark.asyncio
async def test_sentiment_with_synthetic_data(
    api_client: PreprodAPIClient,
    synthetic_data: SyntheticDataSet,
    config_id: str
):
    """Verify sentiment matches synthetic expectations."""
    response = await api_client.get(f"/api/v2/configurations/{config_id}/sentiment")

    # Use test oracle pattern
    expected = compute_expected_sentiment(synthetic_data, "TEST1")
    actual = response.json()["tickers"][0]["sentiment"]

    assert abs(actual["tiingo"]["score"] - expected["score"]) < 0.01
```

### Verifying Observability

```python
@pytest.mark.e2e
@pytest.mark.asyncio
async def test_logs_emitted(
    api_client: PreprodAPIClient,
    cloudwatch_helper: CloudWatchHelper
):
    """Verify CloudWatch logs are created."""
    response = await api_client.get("/api/v2/configurations")
    request_id = response.headers.get("x-request-id")

    # Wait for log propagation
    logs = await cloudwatch_helper.query_logs(
        log_group="/aws/lambda/dashboard-api-preprod",
        request_id=request_id,
        timeout_seconds=30
    )

    assert len(logs) > 0
    assert any("GET /api/v2/configurations" in log for log in logs)
```

---

## Test Markers

```python
# Available markers
@pytest.mark.e2e          # All E2E tests (required)
@pytest.mark.preprod      # Preprod-only tests (requires AWS credentials)
@pytest.mark.slow         # Tests > 30 seconds
@pytest.mark.cleanup      # Manual cleanup utilities
@pytest.mark.manual       # Tests requiring manual triggering

# User story markers
@pytest.mark.us1          # Anonymous to Authenticated flow
@pytest.mark.us2          # OAuth authentication flows
@pytest.mark.us3          # Configuration CRUD operations
@pytest.mark.us4          # Sentiment and Volatility data
@pytest.mark.us5          # Alert rule lifecycle
@pytest.mark.us6          # Notification delivery pipeline
@pytest.mark.us7          # Rate limiting enforcement
@pytest.mark.us8          # Circuit breaker behavior
@pytest.mark.us9          # Ticker validation
@pytest.mark.us10         # Real-time SSE updates
@pytest.mark.us11         # CloudWatch observability
@pytest.mark.us12         # Market status
```

### Running by Marker

```bash
# Run specific user story tests
pytest tests/e2e/ -m "us1" -v
pytest tests/e2e/ -m "us1 or us2" -v

# Exclude slow tests
pytest tests/e2e/ -m "preprod and not slow" -v

# Run auth-related tests
pytest tests/e2e/ -m "us1 or us2" -v

# Skip cleanup utilities
pytest tests/e2e/ -m "not cleanup" -v
```

---

## Debugging Failed Tests

### View Test Output

```bash
# Verbose output with full tracebacks
pytest tests/e2e/test_auth_anonymous.py -v --tb=long

# Stop on first failure
pytest tests/e2e/ -x

# Drop into debugger on failure
pytest tests/e2e/ --pdb
```

### Check Preprod Logs

```bash
# Query CloudWatch logs
aws logs filter-log-events \
  --log-group-name /aws/lambda/dashboard-api-preprod \
  --start-time $(date -d '1 hour ago' +%s)000 \
  --filter-pattern "ERROR"

# Get X-Ray trace
aws xray batch-get-traces --trace-ids "1-abc123..."
```

### View Test Data in DynamoDB

```bash
# Query test data by prefix
aws dynamodb scan \
  --table-name sentiment-analyzer-preprod \
  --filter-expression "begins_with(pk, :prefix)" \
  --expression-attribute-values '{":prefix":{"S":"USER#e2e-"}}'
```

---

## Cleanup

### Manual Cleanup (if needed)

```bash
# Dry run - see what would be cleaned up
pytest tests/e2e/test_cleanup.py::test_dry_run_cleanup -v

# Run actual cleanup (requires --run-cleanup flag)
pytest tests/e2e/test_cleanup.py --run-cleanup -v

# Cleanup specific types
pytest tests/e2e/test_cleanup.py::test_cleanup_old_test_sessions --run-cleanup -v
pytest tests/e2e/test_cleanup.py::test_cleanup_old_test_configs --run-cleanup -v
```

### Orphan Detection

```bash
# Find stale test data (>24h old)
pytest tests/e2e/test_cleanup.py::test_find_orphaned_test_data --run-cleanup -v

# Verify cleanup patterns are safe
pytest tests/e2e/test_cleanup.py::test_verify_no_production_data_affected -v
```

---

## Common Issues

| Issue | Cause | Solution |
|-------|-------|----------|
| `401 Unauthorized` | Expired/invalid token | Check Cognito config, regenerate tokens |
| `Connection refused` | Preprod not deployed | Verify deployment via Terraform |
| `Timeout waiting for logs` | CloudWatch delay | Increase timeout, check log group name |
| `X-Ray trace not found` | Trace propagation delay | Increase wait time to 60s |
| `Test data not cleaned up` | Cleanup fixture failure | Run manual cleanup script |

---

## CI/CD Integration

### JUnit XML Reports

```bash
# Generate JUnit XML for CI
pytest tests/e2e/ --junitxml=reports/e2e-results.xml
```

### Coverage Reports

```bash
# Generate coverage
pytest tests/e2e/ --cov=tests/e2e --cov-report=xml:reports/coverage.xml
```

### GitHub Actions Artifacts

Reports are automatically uploaded as artifacts:
- `e2e-results/e2e-results.xml` - JUnit test results
- `e2e-results/coverage.xml` - Coverage report
