# Quickstart: Sentiment Model S3 Coverage Tests

**Feature**: 088-sentiment-s3-coverage
**Date**: 2025-12-10

## Overview

This feature adds comprehensive S3 model download tests to achieve 85% coverage of `src/lambdas/analysis/sentiment.py`.

## Prerequisites

- Python 3.13
- pytest and moto installed (in dev dependencies)
- No AWS credentials required

## Running the Tests

```bash
# Run all sentiment tests
pytest tests/unit/test_sentiment.py -v

# Run only S3 download tests
pytest tests/unit/test_sentiment.py -v -k "S3"

# Run with coverage report
pytest tests/unit/test_sentiment.py --cov=src/lambdas/analysis/sentiment --cov-report=term-missing
```

## Test Structure

### Existing Tests (TestS3ModelDownload)
- `test_download_model_skips_if_exists` - Warm container path
- `test_download_model_s3_error` - NoSuchKey error
- `test_download_model_throttling_error` - Throttling error

### New Tests (TestS3ModelDownloadWithMoto)
- `test_successful_download_and_extraction` - Full happy path
- `test_cleanup_tar_after_extraction` - Verifies temp file cleanup
- `test_general_client_error` - Generic S3 error handling

## Test Fixture

The tests use an in-memory tar.gz fixture:

```python
import io
import tarfile

def create_test_model_tar() -> bytes:
    """Create minimal model tar.gz for testing."""
    buffer = io.BytesIO()
    with tarfile.open(fileobj=buffer, mode="w:gz") as tar:
        config_data = b'{"model_type": "test"}'
        config_info = tarfile.TarInfo(name="model/config.json")
        config_info.size = len(config_data)
        tar.addfile(config_info, io.BytesIO(config_data))
    buffer.seek(0)
    return buffer.read()
```

## Coverage Target

| Metric | Before | Target | Verification |
|--------|--------|--------|--------------|
| sentiment.py coverage | 59% | 85% | pytest --cov |

## Troubleshooting

### moto version issues
Ensure moto 5.x is installed. The `@mock_aws` decorator replaces the deprecated `@mock_s3`.

### S3 region issues
Always use `us-east-1` for test bucket creation to avoid LocationConstraint issues.

### Cleanup issues
Each test should use `tmp_path` fixture and patch `LOCAL_MODEL_PATH` to avoid pollution.
