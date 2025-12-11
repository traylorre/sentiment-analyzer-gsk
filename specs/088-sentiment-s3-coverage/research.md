# Research: Sentiment Model S3 Loading Test Coverage

**Feature**: 088-sentiment-s3-coverage
**Date**: 2025-12-10

## Research Questions

### 1. Existing Test Patterns

**Question**: What patterns does the existing `TestS3ModelDownload` class use?

**Findings**:
- Current tests at lines 440-531 of `tests/unit/test_sentiment.py`
- Uses `patch("boto3.client")` for manual S3 mocking
- Has tests for: warm container skip, NoSuchKey error, Throttling error
- Missing: successful download test with actual tar extraction
- Missing: integration with moto `mock_aws` for realistic S3 behavior

**Decision**: Enhance existing `TestS3ModelDownload` class with moto-based tests
**Rationale**: Moto provides realistic S3 behavior (bucket creation, file upload/download) vs. manual mocks

### 2. moto S3 Best Practices

**Question**: How to properly use moto `mock_aws` for S3 download_file operations?

**Findings**:
```python
from moto import mock_aws
import boto3

@mock_aws
def test_s3_download():
    # Create bucket and upload test file
    s3 = boto3.client("s3", region_name="us-east-1")
    s3.create_bucket(Bucket="test-bucket")
    s3.upload_file("local_file.tar.gz", "test-bucket", "key")

    # Function under test can now download from mock S3
    # No real AWS calls are made
```

**Key points**:
- `@mock_aws` decorator (moto 5.x) replaces deprecated `@mock_s3`
- Must create bucket and upload file INSIDE the mock context
- S3 region must match between client creation and bucket operations
- For us-east-1, no LocationConstraint needed in create_bucket

**Decision**: Use `@mock_aws` decorator with bucket pre-population fixture
**Rationale**: Provides complete S3 simulation including download_file, head_object, etc.

### 3. Coverage Gap Analysis

**Question**: Which lines in `sentiment.py` are currently uncovered?

**Findings** (lines 70-141):
| Lines | Description | Current Coverage |
|-------|-------------|------------------|
| 83-84 | boto3 import | Covered |
| 85-93 | Warm container check | Covered (test exists) |
| 95-97 | Log download start | Uncovered |
| 99-113 | S3 download + timing | Uncovered |
| 115-127 | Tar extraction + logging | Uncovered |
| 129-130 | Cleanup tar.gz | Uncovered |
| 132-141 | Error handling | Partially covered |

**Decision**: Add test for successful download path (lines 95-130)
**Rationale**: This is the main uncovered code path; error paths already have tests

### 4. Test Fixture Strategy

**Question**: How to create a minimal model tar.gz for testing?

**Findings**:
- The code checks for `config.json` existence to verify model is extracted
- Minimal fixture needs: `model/config.json` in tar.gz
- Can create in-memory using `tarfile` and `io.BytesIO`

```python
import io
import tarfile

def create_test_model_tar() -> bytes:
    """Create minimal model tar.gz for testing."""
    buffer = io.BytesIO()
    with tarfile.open(fileobj=buffer, mode="w:gz") as tar:
        # Create config.json content
        config_data = b'{"model_type": "test"}'
        config_info = tarfile.TarInfo(name="model/config.json")
        config_info.size = len(config_data)
        tar.addfile(config_info, io.BytesIO(config_data))
    buffer.seek(0)
    return buffer.read()
```

**Decision**: Create in-memory tar.gz fixture in test setup
**Rationale**: No need for external fixture files; keeps tests self-contained

## Summary

| Research Area | Decision | Alternative Rejected |
|--------------|----------|---------------------|
| Test approach | Enhance existing tests with moto | LocalStack (overkill) |
| S3 mocking | moto `@mock_aws` decorator | Manual boto3 patches (incomplete) |
| Fixture | In-memory tar.gz | External fixture file |
| Coverage target | Lines 95-130 (successful path) | Error paths only |

## Next Steps

1. Create `TestS3ModelDownloadWithMoto` class with `@mock_aws` decorator
2. Add fixture to create and upload test model tar.gz
3. Add test for successful download + extraction
4. Verify coverage reaches 85% target
