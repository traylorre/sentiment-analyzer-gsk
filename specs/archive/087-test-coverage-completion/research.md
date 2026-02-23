# Research: Test Coverage Completion

**Feature**: 087-test-coverage-completion
**Date**: 2025-12-11
**Purpose**: Resolve unknowns for dashboard handler and sentiment model test coverage

## Research Tasks & Findings

### 1. SSE Streaming Mocking

**Question**: How to mock SSE connections in unit tests?

**Decision**: Use `unittest.mock.AsyncMock` to mock the streaming response generator

**Rationale**:
- SSE endpoints return async generators that yield `ServerSentEvent` objects
- The SSE streaming code in `handler.py` uses `StreamingResponse` from Starlette
- Tests can mock the underlying data source (DynamoDB) and verify the endpoint produces correct streaming responses
- `httpx` with `AsyncClient` in test mode handles async streaming

**Alternatives Considered**:
- `aiohttp` test utilities - Rejected: project uses FastAPI/Starlette
- Real SSE connections - Rejected: violates unit test isolation

**Pattern**:
```python
@pytest.fixture
def mock_streaming_response():
    """Mock SSE streaming data source."""
    async def mock_generator():
        yield {"event": "heartbeat", "data": "ping"}
        yield {"event": "update", "data": {"sentiment": 0.8}}
    return mock_generator

async def test_sse_stream(client, mock_streaming_response):
    with patch("src.lambdas.dashboard.sse.create_event_generator", mock_streaming_response):
        async with client.stream("GET", "/api/v2/stream") as response:
            events = [chunk async for chunk in response.aiter_text()]
            assert len(events) >= 2
```

---

### 2. WebSocket Mocking

**Question**: How to mock WebSocket connections in unit tests?

**Decision**: WebSocket code in handler.py (lines 743-758) are error handling paths for trend data endpoint, not actual WebSocket endpoints

**Rationale**:
- Coverage report shows lines 743-760 in `get_trend_v2()` endpoint
- These are exception handlers (`except ValueError`, `except Exception`)
- No actual WebSocket implementation exists in dashboard handler
- Test coverage needed for error paths, not WebSocket connections

**Pattern**:
```python
async def test_get_trend_value_error(client, mock_db):
    """Test ValueError handling in trend endpoint."""
    with patch("src.lambdas.dashboard.handler.get_trend_data", side_effect=ValueError("Invalid interval")):
        response = await client.get("/api/v2/trend?tags=AI&interval=invalid")
        assert response.status_code == 400
```

---

### 3. S3 Model Download Mocking

**Question**: Best practices for moto S3 mocking with model files?

**Decision**: Use `@mock_aws` decorator with `boto3.client("s3")` to create bucket and upload mock model tar.gz

**Rationale**:
- moto provides complete S3 mock that supports `download_file()`
- Model download function (`download_model_from_s3`) uses standard boto3 patterns
- Can test: successful download, S3 errors (NoSuchKey, AccessDenied), extraction failures

**Pattern**:
```python
import tarfile
import io
from moto import mock_aws

@mock_aws
def test_download_model_from_s3_success():
    """Test successful S3 model download."""
    # Setup: Create bucket and upload mock model
    s3 = boto3.client("s3", region_name="us-east-1")
    s3.create_bucket(Bucket="sentiment-model-bucket")

    # Create minimal valid tar.gz with config.json
    tar_buffer = io.BytesIO()
    with tarfile.open(fileobj=tar_buffer, mode="w:gz") as tar:
        config_data = b'{"model_type": "distilbert"}'
        config_info = tarfile.TarInfo(name="model/config.json")
        config_info.size = len(config_data)
        tar.addfile(config_info, io.BytesIO(config_data))
    tar_buffer.seek(0)

    s3.put_object(
        Bucket="sentiment-model-bucket",
        Key="models/sentiment-v1.tar.gz",
        Body=tar_buffer.read()
    )

    # Execute
    download_model_from_s3()

    # Verify model extracted
    assert Path("/tmp/model/config.json").exists()
```

---

### 4. Uncovered Line Mapping

**Question**: Map current uncovered lines to function/class names

**Decision**: Documented below with function names as primary identifiers (per FR-011)

#### Dashboard Handler (handler.py) - 71% coverage, 77 uncovered lines

| Lines | Function/Context | Description |
|-------|-----------------|-------------|
| 104-118 | `get_api_key()` | Secrets Manager fallback path (error handling) |
| 131, 155-163 | `lifespan()` | App startup/shutdown logging |
| 225-229 | `verify_api_key()` | API key validation error path |
| 290-294 | `get_items()` | Error handler for item retrieval |
| 318-322 | `get_item()` | Error handler for single item retrieval |
| 352-353, 368, 384 | Multiple | Static file serving edge cases |
| 548-576 | `get_dashboard_metrics()` | Metrics aggregation and error handling |
| 642-656 | `get_sentiment_v2()` | DynamoDB error handling |
| 715-716, 729, 736 | `get_trend_v2()` | Range parsing edge cases |
| 743-758 | `get_trend_v2()` | ValueError and Exception handlers |
| 800 | `get_articles_v2()` | Limit validation |
| 835-849 | `get_articles_v2()` | ValueError and Exception handlers |
| 910-911, 937-938 | Chaos endpoints | Error response formatting |
| 975-989 | `get_chaos_experiment()` | FIS status fetch error handling |
| 1029-1030, 1057-1071 | Chaos start/stop | ChaosError and EnvironmentNotAllowed handlers |
| 1126-1136 | `delete_chaos_experiment()` | Delete error handling |

#### Sentiment Model (sentiment.py) - 87% coverage, 23 uncovered lines

| Lines | Function/Context | Description |
|-------|-----------------|-------------|
| 83-141 | `download_model_from_s3()` | S3 download path (warm container check, download, extract) |
| 452 | Error handling | Single error path line |

---

## Log Assertion Patterns

The 21 error patterns from TEST_LOG_ASSERTIONS_TODO.md need explicit assertions:

### Analysis Handler (6 patterns)
1. `Inference error: CUDA error` - test_analysis_handler.py
2. `Invalid SNS message format` - test_analysis_handler.py
3. `Model load error: Model not found` - test_sentiment.py
4. `Failed to load model: Model files missing` - test_sentiment.py
5. `Failed to load model: Model not found` - test_sentiment.py
6. `Inference failed: CUDA error` - test_sentiment.py

### Ingestion Handler (6 patterns)
7. `Circuit breaker opened` - test_newsapi_adapter.py
8. `NewsAPI authentication failed` - test_ingestion_handler.py
9. `Authentication error: Invalid NewsAPI key` - test_ingestion_handler.py
10. `Authentication failed for NewsAPI` - test_ingestion_handler.py
11. `Configuration error: WATCH_TAGS environment variable` - test_ingestion_handler.py
12. `Unexpected error: Secret not found` - test_ingestion_handler.py

### Shared Errors (6 patterns)
13. `Database operation failed: put_item` - test_errors.py
14. `Database operation failed: query` - test_errors.py
15. `Failed to retrieve configuration` - test_errors.py
16. `Internal error details` - test_errors.py
17. `Model loading failed` - test_sentiment.py
18. `Sentiment analysis failed` - test_sentiment.py

### Secrets (2 patterns)
19. `Failed to parse secret as JSON` - test_secrets.py
20. `Secret not found` - test_secrets.py

### Metrics (1 pattern)
21. `Failed to emit metric: InvalidClientTokenId` - test_metrics.py

---

## Existing Test Structure

Current test files with relevant tests:
- `tests/unit/dashboard/test_sse.py` - SSE connection manager, event generation
- `tests/unit/test_dashboard_handler.py` - Main handler tests
- `tests/unit/test_analysis_handler.py` - Analysis handler tests (3 assertions exist)
- `tests/unit/test_sentiment.py` - Sentiment model tests (2 assertions exist)
- `tests/unit/test_errors.py` - Error helper tests (2 assertions exist)
- `tests/unit/test_secrets.py` - Secrets tests (2 assertions exist)

**Existing `assert_error_logged()` calls**: 28 total (9 of 21 patterns covered)
