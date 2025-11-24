# Preprod Dashboard HTTP 502 Root Cause Analysis

**Date**: 2025-11-24
**Severity**: P0 - Blocking preprod integration tests
**Status**: IDENTIFIED - Fix in progress

---

## Executive Summary

All preprod integration tests calling the Dashboard Lambda Function URL are failing with **HTTP 502 (Bad Gateway)** errors. Root cause identified: **Missing binary dependency `pydantic_core._pydantic_core`** in the Lambda deployment package.

---

## Symptoms

### Failed Tests
- `test_e2e_lambda_invocation_preprod.py`: **24/25 tests FAILED**
- All failures: `AssertionError: Health check failed with 502. Response: Internal Server Error`

### Lambda Error Logs
```
[ERROR] Runtime.ImportModuleError: Unable to import module 'handler': No module named 'pydantic_core._pydantic_core'
```

**Frequency**: Every invocation (100% failure rate)
**Impact**: Preprod dashboard completely non-functional

---

## Root Cause

### The Problem: Platform Binary Incompatibility

The Dashboard Lambda deployment uses **ZIP packaging** with platform-specific `pip install`:

```bash
pip install pydantic==2.12.4 \
  --platform manylinux2014_x86_64 \
  --python-version 3.13 \
  --only-binary=:all:
```

**Issue**: `pydantic` has native C extensions (`pydantic_core._pydantic_core`) that must be:
1. **Compiled for the target platform** (Lambda's AL2023 runtime)
2. **Linked correctly** to Python 3.13's binary interface

The `--platform manylinux2014_x86_64` flag downloads pre-built wheels, but these may not be compatible with:
- Lambda's **Amazon Linux 2023** runtime
- Python **3.13** (very recent version, may have ABI changes)

### Why This Happens

When using `--platform` flag:
- Pip downloads **pre-built binary wheels** from PyPI
- These wheels are built for **generic manylinux2014** (CentOS 7 baseline)
- Lambda runs on **Amazon Linux 2023** (different glibc, system libraries)
- **Binary incompatibility** occurs if the wheel expects different library versions

---

## Evidence

### 1. Lambda Configuration ✅
```bash
$ aws lambda get-function --function-name preprod-sentiment-dashboard
FunctionName: preprod-sentiment-dashboard
State: Active
LastUpdateStatus: Successful  # ⚠️ Deployment succeeded, but runtime fails
Runtime: python3.13
PackageType: Zip
```

**Analysis**: Lambda accepted the deployment, but the package is broken at runtime.

### 2. Environment Variables ✅
```json
{
  "DASHBOARD_API_KEY_SECRET_ARN": "arn:aws:secretsmanager:...",
  "API_KEY": "",  # ⚠️ Empty but acceptable (fetched from Secrets Manager)
  "DYNAMODB_TABLE": "preprod-sentiment-items",
  "ENVIRONMENT": "preprod",
  "SSE_POLL_INTERVAL": "5"
}
```

**Analysis**: Configuration is correct.

### 3. Function URL ✅
```json
{
  "FunctionUrl": "https://ee2a3fxtkxmpwp2bhul3uylmb40hfknf.lambda-url.us-east-1.on.aws/",
  "AuthType": "NONE",
  "Cors": { "AllowOrigins": ["*"] }
}
```

**Analysis**: Function URL is correctly configured.

### 4. CloudWatch Logs ❌
```
2025-11-24T03:23:45 [ERROR] Runtime.ImportModuleError:
  Unable to import module 'handler': No module named 'pydantic_core._pydantic_core'
```

**Analysis**: Binary dependency missing or incompatible.

---

## Why Tests Are Structured This Way

### Test Architecture Validation ✅

The preprod integration tests are **correctly implemented** per Zero Trust architecture:

#### 1. **Ingestion Tests** (`test_ingestion_preprod.py`)
- ✅ Uses REAL preprod DynamoDB (`preprod-sentiment-items`)
- ✅ Uses REAL preprod SNS topic (`preprod-sentiment-topic`)
- ✅ ONLY mocks: NewsAPI (external 3rd party), Secrets Manager (test isolation)
- **Rationale**: Tests actual AWS infrastructure permissions and data flow

#### 2. **Analysis Tests** (`test_analysis_preprod.py`)
- ✅ Uses REAL preprod DynamoDB
- ✅ Uses REAL preprod SNS
- ✅ ONLY mocks: ML inference (prohibitively expensive, non-deterministic)
- **Rationale**: Tests AWS integration without $1000+ transformer model downloads

#### 3. **Dashboard Unit Tests** (`test_dashboard_preprod.py`)
- ✅ Uses REAL preprod DynamoDB for data queries
- ⚠️ Uses FastAPI `TestClient` (in-process, not real HTTP)
- **Rationale**: Tests business logic and DynamoDB queries

#### 4. **Dashboard E2E Tests** (`test_e2e_lambda_invocation_preprod.py`) ⚠️ **FAILING**
- ✅ Makes REAL HTTP requests to deployed Lambda Function URL
- ✅ Tests complete request/response cycle through AWS
- ❌ **Current Issue**: Lambda crashes on import, returns HTTP 502
- **Purpose**: Last line of defense - tests what users actually experience

### Goal: "PREPRODUCTION MIRRORS PROD" ✅

**Verification Result**: Test architecture is **CORRECT**. The preprod tests properly call REAL AWS resources (not mocked), ensuring preprod mirrors prod.

**Only Acceptable Mocks**:
1. NewsAPI (external 3rd party - prevents rate limits)
2. Secrets Manager API key retrieval (test isolation)
3. ML inference (cost/performance - documented exception)

**NO mocks for**:
- ✅ DynamoDB operations (all tests use REAL tables)
- ✅ SNS topic operations (all tests use REAL topics)
- ✅ Lambda invocations (E2E tests call REAL Function URL)
- ✅ IAM permissions (all tests validate REAL permissions)

---

## Solution Options

### Option 1: Use Docker-based Lambda Layers (RECOMMENDED)
Build dependencies inside a Lambda-compatible Docker container:

```bash
docker run --rm \
  -v $(pwd):/workspace \
  public.ecr.aws/lambda/python:3.13 \
  bash -c "pip install pydantic==2.12.4 -t /workspace/python/"
```

**Pros**:
- Guaranteed binary compatibility with Lambda runtime
- Matches exact Lambda environment (AL2023 + Python 3.13)
- No platform guessing

**Cons**:
- Requires Docker in CI/CD
- Slightly longer build time

### Option 2: Switch to Container Image Deployment
Package Dashboard Lambda as a Docker container image:

```dockerfile
FROM public.ecr.aws/lambda/python:3.13
COPY requirements.txt .
RUN pip install -r requirements.txt
COPY src/ .
CMD ["handler.lambda_handler"]
```

**Pros**:
- Full control over runtime environment
- No dependency packaging issues
- Easier to debug (can run locally)
- Aligns with Analysis Lambda strategy (see PR #58)

**Cons**:
- Requires ECR repository
- Larger deployment artifact (~200MB vs ~10MB)
- Longer cold start time

### Option 3: Remove `--platform` Flag (QUICK FIX)
Let pip install from source or detect platform automatically:

```bash
pip install pydantic==2.12.4 -t packages/dashboard-deps/
```

**Pros**:
- Minimal code change
- May work if build environment is compatible

**Cons**:
- Still building on Ubuntu (GitHub Actions runner)
- May work by luck, not by design
- Could break again with future dependency updates

---

## Recommended Fix

**Hybrid Approach**:
1. **Short-term (Today)**: Remove `--platform` flag for Dashboard Lambda (Option 3)
2. **Medium-term (PR #59)**: Migrate Dashboard Lambda to container images (Option 2)
3. **Long-term**: Standardize all Lambdas on container images for consistency

### Implementation Plan

**Phase 1: Immediate Fix (30 minutes)**
1. Edit `.github/workflows/deploy.yml` - remove `--platform` flags for Dashboard Lambda
2. Test build locally
3. Deploy to preprod
4. Run E2E tests to verify HTTP 502s are resolved

**Phase 2: Container Migration (3-5 days)**
1. Create Dockerfile for Dashboard Lambda
2. Add ECR repository to Terraform
3. Update deploy workflow to build and push container
4. Update Lambda to use container image
5. Verify preprod deployment
6. Document in ADR (Architecture Decision Record)

**Phase 3: Standardization (1 week)**
1. Migrate Ingestion Lambda to container (optional - current ZIP works)
2. Migrate Analysis Lambda to container (already planned in PR #58)
3. Update all documentation
4. Remove ZIP packaging code from workflows

---

## Testing Checklist

After applying fix:

- [ ] Build succeeds locally: `cd .github/workflows && bash deploy.yml` (extract build steps)
- [ ] Dashboard package contains `pydantic_core/_pydantic_core.*.so`
- [ ] Deploy to preprod succeeds
- [ ] Lambda cold start succeeds (check CloudWatch logs)
- [ ] HTTP 502 errors resolved: `curl https://ee2a3fxtkxmpwp2bhul3uylmb40hfknf.lambda-url.us-east-1.on.aws/health`
- [ ] E2E tests pass: `pytest tests/integration/test_e2e_lambda_invocation_preprod.py`
- [ ] No new import errors in CloudWatch

---

## Related Issues

- **PR #58**: Analysis Lambda container migration (blocked on this issue)
- **ADR-004**: Hybrid Lambda packaging strategy (ZIP vs containers)
- **Issue #51**: Pydantic import errors in production (same root cause)

---

## Appendix: Binary Dependency Analysis

### Files Required by Pydantic 2.12.4

```
pydantic/
pydantic_core/
  __init__.py
  _pydantic_core.cpython-313-x86_64-linux-gnu.so  ⚠️ Binary!
  core_schema.py
  ... (other Python files)
```

The `.so` file is a **compiled shared library** that must match:
- **CPU architecture**: x86_64 (Lambda uses Intel/AMD)
- **OS**: Linux
- **Python version**: 3.13 (CPython ABI)
- **glibc version**: 2.17+ (manylinux2014) or 2.34+ (AL2023)

**Mismatch** in any of these → `ImportModuleError`

### Verification Command

To verify binary compatibility in deployed Lambda:
```bash
aws lambda invoke --function-name preprod-sentiment-dashboard \
  --payload '{"rawPath": "/health"}' \
  /tmp/response.json && cat /tmp/response.json
```

**Expected** (after fix): `{"status": "healthy", ...}`
**Current**: `{"statusCode": 502, "body": "Internal Server Error"}`

---

## Permissions Audit Cross-Reference

This issue does NOT relate to IAM permissions. The Zero Trust permissions audit (see `ZERO_TRUST_PERMISSIONS_AUDIT.md`) confirms:
- ✅ Dashboard Lambda has correct DynamoDB read permissions
- ✅ Function URL is publicly accessible (AuthType: NONE)
- ✅ CORS is correctly configured
- ✅ CloudWatch logging permissions are valid

**The issue is purely a packaging/deployment problem**, not a permissions issue.

---

## Next Steps

1. **Apply immediate fix**: Remove `--platform` flags from Dashboard Lambda packaging
2. **Verify fix**: Deploy to preprod and run E2E tests
3. **Plan container migration**: Create ADR and implementation plan for PR #59
4. **Update documentation**: Reflect new packaging strategy in DEPLOYMENT.md

**Assigned To**: CI/CD Team
**Target Resolution**: Within 24 hours
**Follow-up**: Container migration within 1 week
