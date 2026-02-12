# Data Model: Test Coverage Completion

**Feature**: 087-test-coverage-completion
**Date**: 2025-12-11

## Overview

This is a test-only feature with no production data model changes. This document describes the test data structures and mock patterns used.

## Test Entities

### CoverageGap

Represents uncovered lines identified by pytest-cov.

| Attribute | Type | Description |
|-----------|------|-------------|
| file_path | str | Source file path (e.g., `src/lambdas/dashboard/handler.py`) |
| function_name | str | Function containing uncovered code |
| lines | list[int] | Uncovered line numbers |
| coverage_before | float | Coverage % before adding tests |
| coverage_after | float | Coverage % after adding tests |

### ErrorPattern

Represents an error log pattern requiring assertion.

| Attribute | Type | Description |
|-----------|------|-------------|
| pattern | str | Substring to match in error log |
| source_module | str | Module that emits the error |
| test_file | str | Test file where assertion should be added |
| has_assertion | bool | Whether `assert_error_logged()` exists |

### MockModel

Represents a mock ML model for S3 download testing.

| Attribute | Type | Description |
|-----------|------|-------------|
| bucket | str | S3 bucket name |
| key | str | S3 object key for model tar.gz |
| contents | dict | Mock model files (config.json, etc.) |

## Mock Data Patterns

### S3 Model Mock

```python
MOCK_MODEL = {
    "bucket": "sentiment-model-bucket",
    "key": "models/sentiment-v1.tar.gz",
    "contents": {
        "model/config.json": '{"model_type": "distilbert"}',
        "model/pytorch_model.bin": b"mock_weights",
    }
}
```

### Error Response Mock

```python
MOCK_ERROR_RESPONSES = {
    "dynamodb_error": ClientError(
        {"Error": {"Code": "ThrottlingException", "Message": "Rate exceeded"}},
        "Query"
    ),
    "s3_not_found": ClientError(
        {"Error": {"Code": "NoSuchKey", "Message": "Key not found"}},
        "GetObject"
    ),
}
```

### SSE Event Mock

```python
MOCK_SSE_EVENTS = [
    {"event": "heartbeat", "data": "ping", "id": "1"},
    {"event": "metrics", "data": {"sentiment_avg": 0.65}, "id": "2"},
    {"event": "new_item", "data": {"id": "item-1", "sentiment": "positive"}, "id": "3"},
]
```

## Relationships

```
CoverageGap 1..* -- 1 SourceFile
ErrorPattern 1..* -- 1 TestFile
MockModel 1 -- 1 S3DownloadTest
```

## State Transitions

N/A - Test-only feature with no stateful entities.
