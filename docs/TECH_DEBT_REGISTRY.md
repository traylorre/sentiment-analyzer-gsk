# Tech Debt Registry

> **Purpose**: Track all technical debt, shortcuts, and loose ends discovered during the CI/CD stabilization phase (commits 5ea852b to HEAD). This is a prioritized, actionable list for cleanup.

---

## Critical Priority (Security/Production Risk)

### TD-001: CORS allow_methods Configuration [RESOLVED]
**Location**: `infrastructure/terraform/main.tf:229`
```hcl
allow_methods = ["GET"]  # AWS handles OPTIONS preflight automatically
```
**Status**: RESOLVED - Correct configuration
**Root Cause**: AWS API constraint requires each method <= 6 characters; "OPTIONS" is 7
**Resolution**: AWS Lambda Function URLs automatically handle OPTIONS preflight requests
**Note**: Only specify actual methods your Lambda handles; AWS manages CORS preflight

### TD-002: CORS allow_origins Wildcard [RESOLVED]
**Location**:
- `infrastructure/terraform/main.tf:248`
- `infrastructure/terraform/variables.tf:56-64`
- `infrastructure/terraform/*.tfvars`

**Status**: RESOLVED
**Resolution**:
- Added `cors_allowed_origins` variable with validation blocking wildcards
- Environment-specific configuration via tfvars:
  - dev: localhost origins for local development
  - preprod: localhost for testing
  - prod: empty by default (must be explicitly configured)
- Lambda receives `CORS_ORIGINS` env var (comma-separated)
- Handler already implements environment-based CORS logic

### TD-003: CloudWatch Metrics IAM Resource Wildcard
**Location**: `infrastructure/terraform/modules/iam/main.tf` (lines 107, 184, 304, 380)
```hcl
Resource = "*"
Condition = {
  StringEquals = {
    "cloudwatch:namespace" = "SentimentAnalyzer"
  }
}
```
**Status**: ACCEPTABLE - Has namespace condition constraint
**Note**: CloudWatch PutMetricData requires `*` resource, condition provides security

---

## High Priority (Code Quality/Maintainability)

### TD-004: noqa Comments for E402 Lint Errors
**Location**:
- `tests/integration/test_dashboard_e2e.py:29-34`
- `tests/unit/test_dashboard_handler.py:29-34`
```python
os.environ["API_KEY"] = "test-api-key-12345"  # Before imports
import boto3  # noqa: E402
```
**Root Cause**: Dashboard handler reads API_KEY at module import time
**Why It's Debt**: Working around a design flaw instead of fixing it
**Better Fix**: Make handler read env vars lazily, not at import time
**Commits**: 0b27743, 007cc16

### TD-005: Integration Test Cleanup Not Implemented
**Location**: `.github/workflows/integration.yml:117-123`
```yaml
- name: Cleanup test data
  run: |
    echo "Cleaning up test data..."
    # Cleanup logic will be implemented in test fixtures
```
**Risk**: Test data accumulates in dev DynamoDB over time
**Root Cause**: Rushed to fix integration tests, deferred cleanup
**Fix**: Implement cleanup in test fixtures or add explicit delete commands
**Commit**: Part of integration.yml creation

### TD-006: Test Expectation Changes Without Root Cause Fix
**Location**: `tests/unit/test_ingestion_handler.py`
**Commit**: 0062d8d
```python
# Was: 4 new, 0 duplicates
# Now: 2 new, 2 duplicates
# Comment: "Same articles returned for both tags"
```
**Issue**: Changed test expectations to match observed behavior, not fixed root cause
**Questions to Answer**:
1. Is the deduplication behavior correct or a bug?
2. Should the mock return different articles per tag?
3. Is the "duplicates_skipped" count accurate?

### TD-007: secret_not_found Test Returns 401 Instead of 500
**Location**: `tests/unit/test_ingestion_handler.py:864`
**Commit**: 0062d8d
```python
# Changed from 500 to 401
assert result["statusCode"] == 401
# Comment: "Missing secret results in authentication failure"
```
**Issue**: Changed expectation to match behavior without verifying it's correct
**Question**: Should missing NewsAPI secret return 401 (unauthorized) or 500 (server error)?

---

## Medium Priority (Cleanup/Polish)

### TD-008: Unused F841 Variables Ignored in Tests
**Location**: `pyproject.toml:102`
```toml
"F841",  # unused variables - often used for side effects in tests
```
**Risk**: Masks legitimate unused variable bugs
**Better Fix**: Use explicit `_` prefix for intentionally unused variables
**Why Ignored**: Quick fix to pass linting

### TD-009: Deprecation Warnings Filtered
**Location**: `pyproject.toml:134-137`
```toml
filterwarnings = [
    "ignore::DeprecationWarning:moto.*:",
    "ignore::DeprecationWarning:boto.*:",
]
```
**Risk**: Won't be warned when moto/boto deprecate APIs we use
**Root Cause**: moto 5.0 upgrade caused warning spam
**Better Fix**: Address specific deprecations, not blanket ignore

### TD-010: Protected Namespace Workaround [RESOLVED]
**Location**: `src/lambdas/shared/schemas.py`
**Commit**: b90bc06

**Status**: RESOLVED
**Resolution**:
- Renamed Python field `model_version` → `inference_version` in Pydantic models
- Used `Field(alias="model_version")` for backward compatibility with:
  - DynamoDB attribute names (no migration needed)
  - API response JSON keys (no frontend breaking changes)
  - SNS message payloads (no cross-Lambda changes needed)
- Replaced `protected_namespaces=()` with `populate_by_name=True`
- All existing tests pass (33 schema tests verified)

**Files Changed**:
- `src/lambdas/shared/schemas.py`
- `src/lambdas/dashboard/sentiment.py`
- `src/lambdas/shared/models/sentiment_result.py`

### TD-011: Metrics Lambda Not Implemented [RESOLVED]
**Location**: `src/lambdas/metrics/handler.py`

**Status**: RESOLVED
**Resolution**:
- Created Metrics Lambda that monitors for stuck items (pending > 5 minutes)
- Queries `by_status` GSI and emits `StuckItems` CloudWatch metric
- Runs every 1 minute via EventBridge schedule
- Added to Terraform deployment pipeline
- Unit tests: `tests/unit/test_metrics_handler.py` (14 tests)

### TD-012: S3 Archival Lambda Specified But Not Implemented
**Location**: Referenced in `docs/INTERFACE-ANALYSIS-SUMMARY.md:58`
**Status**: Spec says archival Lambda exists, but it doesn't
**Risk**: Documentation mismatch with reality

---

## Low Priority (Nice to Have)

### TD-013: Multiple Import Fix Approaches
**Location**: `.github/workflows/test.yml`
**Commits**: 59dbbb1, f9a00c4
**History**:
1. First tried: `PYTHONPATH=. pytest`
2. Then changed to: `pip install -e .`
**Note**: Editable install is correct, but shows trial-and-error

### TD-014: moto Version Jump [RESOLVED]
**Location**: `requirements-dev.txt`
**Commit**: 1f2c1ae
```text
moto==5.0.0  # Upgraded from 4.2.0 for mock_aws decorator
```
**Status**: RESOLVED - All tests pass with moto 5.0
**Note**: mock_aws unified decorator works correctly; no breaking changes found

### TD-015: pytest-env Dependency Added [RESOLVED]
**Location**: `requirements-dev.txt`
**Commit**: b90bc06
**Status**: RESOLVED - Removed pytest-env and pytest-asyncio (unused)
**Fix Commit**: 6abdf29

---

## Cloud Provider Portability

> **Context**: Comprehensive portability audit completed (see `docs/CLOUD_PROVIDER_PORTABILITY_AUDIT.md`). Quick wins implemented in PR #43. This section tracks longer-term refactoring work.

### TD-016: Repository Pattern for Database Access
**Status**: Future work (2-3 weeks)
**Current State**: Direct boto3 DynamoDB usage in ~350 LOC across lambdas
**Locations**:
- `src/lambdas/ingestion/handler.py`
- `src/lambdas/analysis/handler.py`
- `src/lambdas/dashboard/handler.py`
- `src/lambdas/shared/dynamodb.py`

**Proposed Fix**: Create cloud-agnostic repository interface
```python
# Example target architecture:
class SentimentRepository(ABC):
    @abstractmethod
    def save_article(self, article: Article) -> bool: ...
    @abstractmethod
    def get_article(self, source_id: str, timestamp: str) -> Article | None: ...

class DynamoDBRepository(SentimentRepository):
    # AWS implementation

class FirestoreRepository(SentimentRepository):
    # GCP implementation
```

**Benefits**:
- Clean abstraction for NoSQL operations
- Testability without mocking boto3
- Easy swap to GCP Firestore or Azure Cosmos DB

**Effort**: 2-3 weeks
**Risk**: Medium (requires refactoring all database calls)

### TD-017: Metrics Interface Abstraction
**Status**: Future work (1-2 weeks)
**Current State**: Direct CloudWatch metrics emission in ~200 LOC
**Locations**:
- `src/lib/metrics.py`
- All lambda handlers emitting custom metrics

**Proposed Fix**: Create metrics interface
```python
class MetricsProvider(ABC):
    @abstractmethod
    def emit_counter(self, name: str, value: int, dimensions: dict): ...
    @abstractmethod
    def emit_gauge(self, name: str, value: float, dimensions: dict): ...

class CloudWatchMetrics(MetricsProvider):
    # AWS implementation

class StackdriverMetrics(MetricsProvider):
    # GCP implementation
```

**Benefits**:
- Swap monitoring backend without code changes
- Support hybrid cloud deployments
- Easier local development (mock metrics)

**Effort**: 1-2 weeks
**Risk**: Low (isolated to metrics.py)

### TD-018: Secrets Management Abstraction
**Status**: Future work (1 week)
**Current State**: Direct AWS Secrets Manager usage in ~100 LOC
**Locations**:
- `src/lambdas/shared/secrets.py`
- `src/lambdas/ingestion/handler.py` (NewsAPI key retrieval)

**Proposed Fix**: Create secrets interface
```python
class SecretsProvider(ABC):
    @abstractmethod
    def get_secret(self, secret_id: str) -> str: ...

class AWSSecretsManager(SecretsProvider):
    # AWS implementation

class GCPSecretManager(SecretsProvider):
    # GCP implementation
```

**Benefits**:
- Environment-based secrets provider selection
- Support for local .env files in development
- Easier testing with mock secrets

**Effort**: 1 week
**Risk**: Low (isolated to secrets.py)

### TD-019: Event Source Abstraction
**Status**: Future work (2-3 weeks)
**Current State**: Direct SNS/EventBridge usage, Lambda-specific event handlers
**Locations**:
- `src/lambdas/ingestion/handler.py` (SNS publish)
- `infrastructure/terraform/modules/lambda/main.tf` (EventBridge schedules)

**Proposed Fix**: Create event adapter layer
```python
class EventPublisher(ABC):
    @abstractmethod
    def publish(self, topic: str, message: dict): ...

class SNSPublisher(EventPublisher):
    # AWS implementation

class PubSubPublisher(EventPublisher):
    # GCP implementation
```

**Benefits**:
- Decouple business logic from AWS event services
- Easier testing without mocking SNS
- Support GCP Pub/Sub or Azure Event Grid

**Effort**: 2-3 weeks
**Risk**: Medium (touches event-driven architecture)

### TD-020: Infrastructure as Code Abstraction
**Status**: Future work (4-6 weeks)
**Current State**: AWS-specific Terraform with 12 AWS provider resources
**Locations**: All of `infrastructure/terraform/`

**Options**:
1. **Pulumi**: Multi-cloud IaC in Python
2. **Terragrunt**: Terraform wrapper with better modularity
3. **CDK for Terraform**: Type-safe infrastructure in Python

**Proposed Fix**: Migrate to Pulumi for cloud-agnostic IaC
```python
# Example Pulumi abstraction:
class CloudDatabase(ComponentResource):
    def __init__(self, provider: "aws" | "gcp" | "azure"):
        if provider == "aws":
            self.table = dynamodb.Table(...)
        elif provider == "gcp":
            self.table = firestore.Database(...)
```

**Benefits**:
- Single codebase for multi-cloud deployments
- Type safety and IDE autocomplete
- Easier testing of infrastructure

**Effort**: 4-6 weeks
**Risk**: High (complete infrastructure rewrite)

### TD-021: Lambda FIS Chaos Testing Blocked by Terraform Provider
**Status**: Blocked - Waiting for upstream fix
**Location**: `infrastructure/terraform/main.tf:442-445`, `modules/chaos/main.tf`
**Issue**: [hashicorp/terraform-provider-aws#41208](https://github.com/hashicorp/terraform-provider-aws/issues/41208)

**Current State**: AWS FIS added Lambda fault injection actions in October 2024:
- `aws:lambda:invocation-add-delay` - Inject latency
- `aws:lambda:invocation-error` - Force errors

However, the Terraform AWS provider validation doesn't recognize `"Functions"` as a valid
target key. The provider only allows: `AutoScalingGroups`, `Buckets`, `Cluster`, `Clusters`,
`DBInstances`, `Instances`, `Nodegroups`, `Pods`, `ReplicationGroups`, `Roles`, `SpotInstances`,
`Subnets`, `Tables`, `Tasks`, `TransitGateways`, `Volumes`.

**Workaround**: Set `enable_chaos_testing = false` in main.tf until provider is updated.

**Resolution**: Monitor the GitHub issue. Once resolved:
1. Update AWS provider version in `versions.tf`
2. Change `enable_chaos_testing = false` back to `var.environment == "preprod"`
3. Test chaos experiments in preprod

**Effort**: 30 minutes once provider is updated
**Risk**: None (feature disabled, not broken)

---

## Cloud Portability Action Plan

### Phase 1: Quick Wins (COMPLETED ✅)
- [x] CLOUD_REGION environment variable with AWS_REGION fallback
- [x] DATABASE_TABLE environment variable with DYNAMODB_TABLE fallback
- [x] Comprehensive portability audit document created
- **PR**: #43
- **Effort**: 2-3 hours
- **Portability Score**: Improved from 20/100 to 25/100

### Phase 2: Abstraction Layers (Future - 6-8 weeks)
- [ ] TD-016: Repository pattern for database access
- [ ] TD-017: Metrics interface abstraction
- [ ] TD-018: Secrets management abstraction
- [ ] TD-019: Event source abstraction
- **Estimated Effort**: 6-8 weeks
- **Portability Score**: Would reach 60-70/100

### Phase 3: Infrastructure Abstraction (Future - 4-6 weeks)
- [ ] TD-020: Migrate to Pulumi or multi-cloud Terraform modules
- **Estimated Effort**: 4-6 weeks
- **Portability Score**: Would reach 80-90/100

### Cost-Benefit Analysis
- **Current State**: 25/100 portability (heavily AWS-coupled)
- **Cost to Reach 60/100**: ~6-8 weeks engineering time
- **Cost to Reach 80/100**: ~10-14 weeks total engineering time
- **Business Value**: Enables multi-cloud strategy, reduces vendor lock-in
- **Recommendation**: Defer until multi-cloud is a business requirement

### References
- Full audit: `docs/CLOUD_PROVIDER_PORTABILITY_AUDIT.md` (729 lines)
- Quick wins implementation: PR #43
- GCP migration estimate: 8-12 weeks for full port

---

## Commit-by-Commit Lessons

### Commits That Were Shortcuts

| Commit | Description | Problem |
|--------|-------------|---------|
| 5ea852b | Align code formatting | Removed blank lines from tests - not a fix, cosmetic |
| 007cc16 | Resolve ruff linting | 71 auto-fixes in one commit - should have been reviewed |
| 0b27743 | Add noqa comments | Workaround instead of fixing root cause |
| e2cb2fa | Resolve test failures | Multiple unrelated fixes in one commit |
| 0062d8d | Update test expectations | Changed tests to match behavior, not fixed behavior |
| 108a34f | CORS wildcard | Acknowledged hack, good that it's tracked |
| bc44128 | Access keys for integration | Removed OIDC attempt without understanding why it failed |

### Pattern of Problems

1. **Hole-by-hole fixing**: Each CI failure fixed one thing, pushed, hit next error
2. **Test adjustment over code fixing**: When tests failed, adjusted expectations
3. **Lint suppression over lint fixing**: noqa instead of restructuring
4. **Major dependency jumps**: moto 4.2→5.0 without incremental testing

---

## Action Items for Cleanup Sprint

### Must Fix Before Demo - COMPLETED
- [x] TD-001: CORS allow_methods restored to ["GET", "OPTIONS"]
- [x] TD-002: Documented allow_origins * for demo, checklist item for prod
- [x] TD-005: Clarified integration tests use moto mocks (no cleanup needed)

### Should Fix for Code Quality - COMPLETED
- [x] TD-004: Dashboard handler now reads env lazily via get_api_key()
- [x] TD-006: Documented deduplication behavior (correct)
- [x] TD-007: Fixed secret_not_found to return 500 (server config error)
- [x] TD-008: Replaced F841 blanket ignore with explicit `_` variables

### Can Defer - RESOLVED OR ACCEPTABLE
- [x] TD-009: Deprecation warnings properly filtered (third-party only)
- [ ] TD-010: Rename model_version field (low risk, workaround in place)
- [x] TD-012: S3 archival Lambda deferred to post-demo (documented)
- [x] TD-014: moto 5.0 verified working (all tests pass)
- [x] TD-015: pytest-env removed (was unused)

---

## Tracking Metrics

| Metric | Value |
|--------|-------|
| Total Tech Debt Items | 21 |
| Critical (Security) | 3 |
| High (Quality) | 4 |
| Medium (Cleanup) | 6 |
| Low (Nice to Have) | 3 |
| Cloud Portability (Future) | 5 |
| Items from shortcuts | 7 |
| Items acceptable for demo | 4 |
| Items completed | 13 |
| Items deferred to future | 8 |

---

## Testing Infrastructure

### TD-021: Sophisticated Race Condition Integration Tests
**Status**: Future work (2-3 weeks)
**Priority**: Medium (Production hardening)
**Context**: Basic concurrent request tests exist in `test_e2e_lambda_invocation_preprod.py`, but sophisticated race condition scenarios need dedicated test infrastructure.

**Current State**:
- Basic concurrency tests: 10 concurrent requests, rapid sequential requests
- No testing of concurrent writes, conditional updates, or message ordering
- No chaos engineering or failure injection tests

**Proposed Tests**:

1. **Concurrent DynamoDB Writes**
   - Multiple Lambdas writing same item_id with conditional updates
   - Verify optimistic locking prevents data corruption
   - Test: 10 concurrent PUT requests with version checks
   - Expected: All writes succeed or fail gracefully with ConditionalCheckFailed

2. **SNS Message Ordering**
   - Publish multiple messages rapidly, verify processing order
   - Test: Publish 20 messages in <1s, validate timestamp ordering in DynamoDB
   - Expected: Messages processed with correct causality guarantees

3. **Lambda Cold Start Race Conditions**
   - Trigger 50 concurrent Lambda invocations to force cold starts
   - Verify: No import errors, no shared state corruption, correct initialization
   - Test: Concurrent requests during blue/green deployment
   - Expected: All requests succeed, no 502 errors

4. **DynamoDB GSI Eventual Consistency**
   - Write to base table, immediately query GSI
   - Test: Verify application handles GSI lag gracefully
   - Expected: Dashboard shows eventual consistency, no errors

5. **S3 Model Loading Race Conditions**
   - 20 concurrent Analysis Lambda invocations loading same model
   - Verify: No S3 throttling, efficient caching, correct model versioning
   - Test: Concurrent model downloads with ETag validation
   - Expected: Efficient caching, no duplicate downloads

6. **Secrets Manager Rate Limiting**
   - 100 concurrent Lambda cold starts fetching API key
   - Verify: Graceful degradation, caching works, no request failures
   - Test: Simulate Secrets Manager throttling
   - Expected: Exponential backoff, cached values used

7. **DynamoDB Conditional Update Conflicts**
   - Simulate: Multiple Lambdas updating same item status simultaneously
   - Test: Concurrent status transitions (pending → processing → completed)
   - Expected: Only one Lambda wins, others retry or fail gracefully

8. **EventBridge/SNS Duplicate Message Handling**
   - Send duplicate events (same source_id + timestamp)
   - Verify: Idempotency keys prevent duplicate processing
   - Test: Publish same event 5 times rapidly
   - Expected: Only 1 DynamoDB item created

**Test Infrastructure Needed**:
```python
# Example chaos testing framework
class ChaosTest:
    def inject_dynamodb_throttling(self, rate: float):
        """Inject DynamoDB throttling errors"""

    def inject_s3_latency(self, delay_ms: int):
        """Add artificial S3 latency"""

    def inject_lambda_timeout(self, percentage: float):
        """Randomly timeout percentage of Lambda invocations"""

    def inject_network_partition(self, duration_s: int):
        """Simulate network partition between services"""
```

**Complexity**:
- Requires: Chaos engineering tools (e.g., aws-fault-injection-simulator)
- Requires: Test fixtures to inject failures
- Requires: DynamoDB conditional update test harness
- Requires: Metrics to detect race conditions (duplicate writes, etc.)

**Effort Estimate**: 2-3 weeks
- Week 1: Design test infrastructure, set up chaos tools
- Week 2: Implement 8 race condition test scenarios
- Week 3: CI/CD integration, flakiness fixes

**Business Value**:
- HIGH: Catches production race conditions before deployment
- Validates: Distributed system correctness guarantees
- Prevents: Data corruption, duplicate processing, lost messages

**References**:
- AWS Fault Injection Simulator: https://aws.amazon.com/fis/
- DynamoDB Transactions: https://docs.aws.amazon.com/amazondynamodb/latest/developerguide/transactions.html
- Chaos Engineering principles: https://principlesofchaos.org/

**Related**: Basic E2E tests in `tests/integration/test_e2e_lambda_invocation_preprod.py:377-418`

---

### TD-015: Performance Tuning and Load Testing

**Status**: RESOLVED
**Priority**: Medium
**Created**: 2024-11-24
**Resolved**: 2024-11-29 (PR #205)

**Context**: System needs performance baseline and tuning to understand capacity limits.

**Resolution**:
- Created k6 load testing script (`tests/load/api-load-test.js`)
  - Smoke test: Quick validation (1 VU, 30s)
  - Load test: Normal traffic (ramp to 50 VUs over 5 minutes)
  - Stress test: Find breaking point (ramp to 200 VUs)
  - Soak test: Extended duration (50 VUs for 30 minutes)
- Created scaling runbook (`docs/runbooks/scaling.md`)
  - Key metrics and thresholds for Lambda, DynamoDB, API Gateway
  - Scaling procedures for Lambda concurrency, DynamoDB capacity, provisioned concurrency
  - Emergency procedures for high error rates, sustained throttling, hot keys
  - Load testing procedures using k6
  - Cost considerations matrix

**Acceptance Criteria**:
- [x] Establish baseline: k6 load test script provides baseline metrics
- [x] Determine breaking point: Stress test stage ramps to 200 VUs
- [x] Document p50/p95/p99 latencies: k6 handleSummary reports these
- [ ] Model cost: on-demand vs provisioned DynamoDB (deferred - needs production data)
- [x] Create runbook: scaling procedures for traffic spikes

**Files Added**:
- `tests/load/api-load-test.js` - k6 load test script
- `docs/runbooks/scaling.md` - Scaling runbook with procedures
- `tests/load/.gitignore` - Ignore test output files

---

*This registry should be reviewed before any production deployment. Items marked as "acceptable for demo" must be addressed for production.*
