# Quickstart: Test Coverage Completion

**Feature**: 087-test-coverage-completion
**Date**: 2025-12-11

## Prerequisites

- Python 3.13+
- pytest 8.0+
- pytest-cov
- moto (for AWS mocking)

```bash
# Install dev dependencies
pip install -r requirements-dev.txt
```

## Running Coverage Analysis

### Check Current Coverage

```bash
# Dashboard handler coverage
python3 -m pytest tests/unit/ \
  --cov=src.lambdas.dashboard.handler \
  --cov-report=term-missing \
  --tb=no -q

# Sentiment model coverage
python3 -m pytest tests/unit/ \
  --cov=src.lambdas.analysis.sentiment \
  --cov-report=term-missing \
  --tb=no -q

# Combined coverage for both modules
python3 -m pytest tests/unit/ \
  --cov=src.lambdas.dashboard.handler \
  --cov=src.lambdas.analysis.sentiment \
  --cov-report=term-missing \
  --tb=no -q
```

### Check Log Assertions

```bash
# Run the pre-commit hook
./scripts/check-error-log-assertions.sh --verbose
```

## Adding Tests

### 1. Dashboard Handler Coverage Tests

Add tests to existing files, targeting uncovered functions:

```python
# tests/unit/test_dashboard_handler.py

class TestGetDashboardMetricsErrors:
    """Tests for dashboard metrics error handling (lines 548-576)."""

    @pytest.fixture
    def mock_db_error(self):
        """Mock DynamoDB error."""
        return ClientError(
            {"Error": {"Code": "ThrottlingException", "Message": "Rate exceeded"}},
            "Query"
        )

    async def test_metrics_dynamodb_error(self, client, mock_db_error, caplog):
        """Test error handling when DynamoDB fails."""
        with patch("src.lambdas.dashboard.handler.get_table") as mock_get_table:
            mock_get_table.return_value.query.side_effect = mock_db_error

            response = await client.get("/api/dashboard/metrics")

            assert response.status_code == 500
            assert_error_logged(caplog, "Failed to get dashboard metrics")
```

### 2. SSE Lambda Tests (New File)

Create dedicated test file per FR-014:

```python
# tests/unit/dashboard/test_dashboard_handler_sse.py

"""
SSE Lambda streaming tests for 087-test-coverage-completion.

This file tests the SSE Lambda which uses RESPONSE_STREAM mode,
separate from the main dashboard handler (BUFFERED mode).
"""

import pytest
from unittest.mock import patch, AsyncMock
from moto import mock_aws

@pytest.fixture
def mock_sse_generator():
    """Mock SSE event generator."""
    async def generator():
        yield {"event": "heartbeat", "data": "ping"}
        yield {"event": "metrics", "data": {"sentiment_avg": 0.65}}
    return generator

class TestSSEStreaming:
    """Tests for SSE streaming endpoint coverage."""

    async def test_stream_returns_sse_events(self, client, mock_sse_generator):
        """Test SSE stream returns expected events."""
        # Implementation depends on actual SSE endpoint structure
        pass
```

### 3. S3 Model Download Tests

```python
# tests/unit/test_sentiment.py

import tarfile
import io
from moto import mock_aws
import boto3

class TestS3ModelDownload:
    """Tests for S3 model download path (lines 83-141)."""

    @pytest.fixture
    def mock_model_tar(self):
        """Create mock model tar.gz."""
        tar_buffer = io.BytesIO()
        with tarfile.open(fileobj=tar_buffer, mode="w:gz") as tar:
            config_data = b'{"model_type": "distilbert"}'
            config_info = tarfile.TarInfo(name="model/config.json")
            config_info.size = len(config_data)
            tar.addfile(config_info, io.BytesIO(config_data))
        tar_buffer.seek(0)
        return tar_buffer

    @mock_aws
    def test_download_model_success(self, mock_model_tar, caplog):
        """Test successful model download from S3."""
        s3 = boto3.client("s3", region_name="us-east-1")
        s3.create_bucket(Bucket="sentiment-model-bucket")
        s3.put_object(
            Bucket="sentiment-model-bucket",
            Key="models/sentiment-v1.tar.gz",
            Body=mock_model_tar.read()
        )

        from src.lambdas.analysis.sentiment import download_model_from_s3
        download_model_from_s3()

        assert "Model downloaded from S3" in caplog.text

    @mock_aws
    def test_download_model_not_found(self, caplog):
        """Test error handling when model not found in S3."""
        s3 = boto3.client("s3", region_name="us-east-1")
        s3.create_bucket(Bucket="sentiment-model-bucket")
        # Don't upload model - simulate not found

        from src.lambdas.analysis.sentiment import download_model_from_s3, ModelLoadError

        with pytest.raises(ModelLoadError):
            download_model_from_s3()

        assert_error_logged(caplog, "Failed to download model from S3")
```

### 4. Adding Log Assertions

Pattern for adding log assertions to existing tests:

```python
# Before (test passes but ERROR log not validated)
def test_error_case(self):
    with patch('some_module', side_effect=SomeError("error")):
        result = handler(event, context)
    assert result["statusCode"] == 500

# After (ERROR log explicitly validated)
def test_error_case(self, caplog):
    with patch('some_module', side_effect=SomeError("error")):
        result = handler(event, context)
    assert result["statusCode"] == 500
    assert_error_logged(caplog, "Expected error message")  # Substring match
```

## Validation

### Run All Unit Tests

```bash
python3 -m pytest tests/unit/ -v --tb=short
```

### Verify Coverage Thresholds

```bash
# Must pass: dashboard handler ≥85%
python3 -m pytest tests/unit/ \
  --cov=src.lambdas.dashboard.handler \
  --cov-fail-under=85 \
  --tb=no -q

# Must pass: sentiment model ≥85%
python3 -m pytest tests/unit/ \
  --cov=src.lambdas.analysis.sentiment \
  --cov-fail-under=85 \
  --tb=no -q
```

### Verify Log Assertions

```bash
# Run pre-commit hook - should report zero unasserted ERROR logs
./scripts/check-error-log-assertions.sh
```

## Test Constraints (from Clarifications)

1. **Fresh mocks per test** - Each test creates its own moto/mock context
2. **30s max per test** - Tests exceeding 30s indicate design problem
3. **Substring matching** - Log assertions use substring match, not exact string
4. **Add to existing files** - Except SSE Lambda tests → `test_dashboard_handler_sse.py`
