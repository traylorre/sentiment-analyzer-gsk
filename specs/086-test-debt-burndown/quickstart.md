# Quickstart: Test Debt Burndown Development

**Feature**: 086-test-debt-burndown
**Date**: 2025-12-11

## Prerequisites

- Python 3.13
- pytest with pytest-cov
- moto (for AWS mocking)
- Access to target repo: `sentiment-analyzer-gsk`

## Running Tests

### Run All Unit Tests
```bash
python3 -m pytest tests/unit/ -v --tb=short
```

### Run Tests with Coverage
```bash
python3 -m pytest tests/unit/ --cov=src --cov-report=term-missing
```

### Run Specific Module Coverage
```bash
# Dashboard handler coverage
python3 -m pytest tests/unit/dashboard/ --cov=src/lambdas/dashboard/handler --cov-report=term-missing

# Sentiment model coverage
python3 -m pytest tests/unit/ --cov=src/lambdas/analysis/sentiment --cov-report=term-missing
```

### Check for pytest.skip() in Observability Tests
```bash
grep -n "pytest.skip" tests/integration/test_observability_preprod.py || echo "No skips found"
```

## Adding caplog Assertions

### Pattern to Follow

**Before** (error not validated):
```python
def test_model_load_error(self):
    with patch('load_model', side_effect=ModelLoadError("Model not found")):
        result = handler(event, context)
    assert result["statusCode"] == 500
    # ERROR log appears but isn't validated!
```

**After** (error explicitly validated):
```python
def test_model_load_error(self, caplog):
    with patch('load_model', side_effect=ModelLoadError("Model not found")):
        result = handler(event, context)
    assert result["statusCode"] == 500
    assert_error_logged(caplog, "Model load error")
```

### Key Steps

1. Add `caplog` parameter to test function signature
2. Keep existing assertions unchanged
3. Add `assert_error_logged(caplog, "pattern")` after existing assertions
4. Pattern should match substring of expected error message

## Adding SSE/WebSocket Tests

### SSE Test Pattern
```python
def test_sse_client_disconnect(self, caplog):
    """Test graceful cleanup on SSE client disconnect."""
    mock_connection = MagicMock()
    mock_connection.send.side_effect = ConnectionError("Client disconnected")

    with patch('create_sse_connection', return_value=mock_connection):
        result = handle_sse_request(event, context)

    # Verify cleanup
    mock_connection.close.assert_called_once()
    # Verify logging
    assert_warning_logged(caplog, "disconnect")
    # Verify no resource leaks
    assert result["statusCode"] == 200
```

### WebSocket Test Pattern
```python
def test_websocket_disconnect(self, caplog):
    """Test connection cleanup on WebSocket disconnect."""
    mock_ws = MagicMock()

    with patch('websocket_handler.connection', mock_ws):
        result = handle_disconnect(event, context)

    mock_ws.cleanup.assert_called_once()
    assert_warning_logged(caplog, "disconnect")
```

## Adding S3 Model Loading Tests

### moto Pattern for S3
```python
import moto
import boto3

@moto.mock_aws
def test_s3_model_download(self, caplog):
    """Test S3 model download path."""
    # Setup mock S3
    s3 = boto3.client('s3', region_name='us-east-1')
    s3.create_bucket(Bucket='model-bucket')
    s3.put_object(Bucket='model-bucket', Key='model.tar.gz', Body=b'model-data')

    # Test download
    result = download_model('model-bucket', 'model.tar.gz')

    assert result is not None
```

### S3 Error Test Pattern
```python
@moto.mock_aws
def test_s3_throttling_error(self, caplog):
    """Test S3 throttling error handling."""
    with patch('boto3.client') as mock_client:
        mock_client.return_value.get_object.side_effect = \
            botocore.exceptions.ClientError(
                {'Error': {'Code': 'SlowDown', 'Message': 'Reduce your request rate'}},
                'GetObject'
            )

        with pytest.raises(ModelLoadError):
            download_model('bucket', 'key')

    assert_error_logged(caplog, "throttling")
```

## Validation Commands

### Pre-Commit Validation
```bash
make validate        # Full validation (fmt + lint + security)
make test-local      # Unit + integration tests
```

### Coverage Verification
```bash
# Check dashboard handler coverage
python3 -m pytest tests/unit/dashboard/ --cov=src/lambdas/dashboard/handler --cov-fail-under=85

# Check sentiment coverage
python3 -m pytest tests/unit/ --cov=src/lambdas/analysis/sentiment --cov-fail-under=85
```

### Full Test Suite
```bash
python3 -m pytest tests/unit/ tests/integration/ -v --tb=short
```

## Success Criteria Checklist

- [ ] SC-001: Zero ERROR logs without `assert_error_logged()` assertion
- [ ] SC-002: Dashboard handler ≥85% coverage
- [ ] SC-003: Sentiment model ≥85% coverage
- [ ] SC-004: All 21 error patterns have assertions
- [ ] SC-005: All tests pass (`pytest -v --tb=short`)
- [ ] SC-006: Overall coverage remains ≥85%
- [ ] SC-007: Zero `pytest.skip()` in observability tests

## File Reference

| Test File | Error Patterns | Status |
|-----------|----------------|--------|
| `test_analysis_handler.py` | 6 | TODO |
| `test_ingestion_handler.py` | 6 | TODO |
| `test_sentiment.py` | 3 | TODO |
| `test_newsapi_adapter.py` | ~2 | TODO |
| `test_errors.py` | 6 | TODO |
| `test_secrets.py` | 2 | TODO |
| `test_metrics.py` | 1 | TODO |
| `dashboard/test_handler.py` | SSE/WS | TODO |
| `test_observability_preprod.py` | Verify | TODO |
