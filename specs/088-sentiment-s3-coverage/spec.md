# Feature Specification: Sentiment Model S3 Loading Test Coverage

**Feature Branch**: `088-sentiment-s3-coverage`
**Created**: 2025-12-10
**Status**: Draft
**Input**: User description: "Increase sentiment model S3 loading test coverage from 59% to 85% by adding integration tests for the S3 download path in src/lambdas/analysis/sentiment.py"

## User Scenarios & Testing *(mandatory)*

### User Story 1 - CI Pipeline Validates S3 Download Logic (Priority: P1)

When developers push code changes to the sentiment analysis module, the CI pipeline should execute tests that verify the S3 model download functionality works correctly across all code paths, providing confidence that production deployments will succeed.

**Why this priority**: The S3 download logic is on the critical path for Lambda cold starts. Untested code in this path can cause production outages during model initialization.

**Independent Test**: Can be fully tested by running `pytest tests/unit/test_sentiment.py -v` and verifying coverage report shows >=85% for sentiment.py.

**Acceptance Scenarios**:

1. **Given** a cold Lambda container with no model in /tmp, **When** the download function executes successfully, **Then** the model is downloaded from S3, extracted, and ready for inference
2. **Given** a warm Lambda container with model already in /tmp/model, **When** the download function is called, **Then** it detects existing model and skips download
3. **Given** an S3 bucket that returns NoSuchKey error, **When** the download function executes, **Then** a ModelLoadError is raised with descriptive message and error is logged

---

### User Story 2 - Error Paths Have Explicit Log Assertions (Priority: P2)

When S3 operations fail (network errors, throttling, missing objects), the test suite should verify that appropriate error messages are logged for operational monitoring and troubleshooting.

**Why this priority**: Log assertions prevent silent failures and ensure on-call engineers have visibility into production issues.

**Independent Test**: Can be tested by running tests with `caplog` fixture and verifying `assert_error_logged()` is called for each error scenario.

**Acceptance Scenarios**:

1. **Given** an S3 throttling error, **When** the download fails, **Then** an ERROR log containing "Failed to download model from S3" is emitted
2. **Given** a general S3 client error, **When** the download fails, **Then** an ERROR log with bucket and key details is emitted
3. **Given** a tar extraction failure, **When** the extraction fails, **Then** an ERROR log is emitted and ModelLoadError is raised

---

### User Story 3 - Tests Run Without Real AWS Credentials (Priority: P3)

The test suite must execute in CI environments without requiring real AWS credentials, using moto's mock_aws decorator to simulate S3 operations.

**Why this priority**: CI environments should not have access to production AWS resources. Tests must be fully isolated and deterministic.

**Independent Test**: Can be tested by running tests with AWS_ACCESS_KEY_ID and AWS_SECRET_ACCESS_KEY unset, verifying all tests pass.

**Acceptance Scenarios**:

1. **Given** a moto-mocked S3 bucket with a model tar.gz file, **When** the download function executes, **Then** it successfully downloads and extracts the mock file
2. **Given** no AWS credentials in environment, **When** tests execute, **Then** all tests pass using moto mocks

---

### Edge Cases

- What happens when /tmp storage is full during extraction?
- How does system handle corrupted tar.gz files?
- What happens when model directory exists but config.json is missing?
- How does system behave when S3 returns SlowDown (throttling) errors repeatedly?

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: Test suite MUST verify successful S3 model download, including file download, tar extraction, and cleanup of temporary tar.gz file
- **FR-002**: Test suite MUST verify warm container detection (skip download when model exists)
- **FR-003**: Test suite MUST verify NoSuchKey error handling with appropriate error logging
- **FR-004**: Test suite MUST verify Throttling error handling with appropriate error logging
- **FR-005**: Test suite MUST verify general S3 ClientError handling with appropriate error logging
- **FR-006**: Test suite MUST use moto mock_aws to simulate S3 operations without real AWS credentials
- **FR-007**: Test suite MUST include `assert_error_logged()` assertions for all error paths
- **FR-008**: Test suite MUST verify the lazy loading pattern where models are downloaded only once per Lambda container lifecycle

### Key Entities

- **_download_model_from_s3()**: Function that downloads ML model from S3 to Lambda /tmp storage (lines 70-141 in sentiment.py)
- **ModelLoadError**: Custom exception raised when model download or loading fails
- **Mock S3 Bucket**: Moto-mocked S3 bucket containing test model tar.gz file
- **Test Model Artifact**: Minimal tar.gz file simulating the ML model structure

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: sentiment.py test coverage increases from 59% to at least 85% as reported by pytest-cov
- **SC-002**: All S3 error paths (NoSuchKey, Throttling, general ClientError) have explicit `assert_error_logged()` calls
- **SC-003**: Test suite passes in CI without requiring real AWS credentials (verified by CI run logs)
- **SC-004**: All 5 S3 download scenarios have dedicated test methods: successful download, warm container skip, NoSuchKey error, Throttling error, general error
- **SC-005**: Zero new test failures introduced (existing 1992+ tests continue passing)

## Assumptions

- The existing test file `tests/unit/test_sentiment.py` will be extended rather than creating a new test file
- The moto library is already available in the test dependencies
- The test model artifact can be a minimal tar.gz containing just a config.json file
- The coverage gap is primarily in lines 81-139 of sentiment.py (S3 download logic)
- Existing tests for S3 error paths (NoSuchKey, Throttling) may need enhancement with moto mock_aws rather than simple patches
