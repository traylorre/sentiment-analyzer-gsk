# Lambda Dependency Analysis - Root Cause of Preprod Dashboard Failure

**Date**: 2025-11-22
**Issue**: Preprod dashboard returns `No module named 'fastapi'`
**Status**: ROOT CAUSE IDENTIFIED ⚠️

---

## Executive Summary

The dashboard Lambda is failing because **dependencies are NOT included in the Lambda package**. The CI/CD build process only zips the Python handler code, but FastAPI, Mangum, and other dependencies are missing.

**Impact**: Dashboard is non-functional in preprod (and likely will be in prod if deployed as-is).

**Severity**: **HIGH** - Blocks first production deployment

---

## Root Cause Analysis

### What's Happening

The GitHub Actions workflow (`.github/workflows/deploy.yml` lines 94-98) packages the dashboard Lambda like this:

```bash
cd src/lambdas/dashboard
zip -r ../../../packages/dashboard-${SHA}.zip . \
  -x "*.pyc" "__pycache__/*" "*.pytest_cache/*" "tests/*"
```

This creates a ZIP with only:
- `handler.py` (main entry point)
- `metrics.py` (dashboard metrics module)
- Local imports from `src/lambdas/shared/`

**Missing**: All external dependencies from `requirements.txt`

### Why It Fails

When Lambda tries to import the handler:

```python
from fastapi import Depends, FastAPI, HTTPException, Request  # ❌ FAILS
from fastapi.middleware.cors import CORSMiddleware              # ❌ FAILS
from fastapi.responses import FileResponse, HTMLResponse        # ❌ FAILS
from mangum import Mangum                                        # ❌ FAILS
from sse_starlette.sse import EventSourceResponse               # ❌ FAILS
```

Lambda runtime cannot find these modules → `Runtime.ImportModuleError`

---

## Dashboard Dependencies

### Required Python Packages

From `requirements.txt` and `src/lambdas/dashboard/handler.py`:

| Package | Version | Purpose | Size Estimate |
|---------|---------|---------|---------------|
| **fastapi** | 0.121.3 | Web framework for REST API | ~10 MB |
| **mangum** | 0.19.0 | Lambda Function URL adapter for FastAPI | ~500 KB |
| **sse-starlette** | 3.0.3 | Server-Sent Events for real-time updates | ~100 KB |
| **uvicorn** | 0.38.0 | ASGI server (local dev only, not needed in Lambda) | ~5 MB |
| **pydantic** | 2.12.4 | Data validation (used by FastAPI) | ~15 MB |
| **boto3** | 1.41.0 | AWS SDK (for DynamoDB access) | Included in Lambda runtime |
| **botocore** | 1.41.0 | AWS SDK core (for DynamoDB) | Included in Lambda runtime |
| **python-json-logger** | 4.0.0 | Structured logging | ~50 KB |

**Total estimated size (excluding boto3)**: ~30-40 MB

### Transitive Dependencies

These packages have their own dependencies:

- **fastapi** requires:
  - `starlette` (~5 MB)
  - `anyio` (~1 MB)
  - `typing-extensions` (~100 KB)

- **pydantic** requires:
  - `pydantic-core` (~5 MB)
  - `typing-extensions` (~100 KB)

**Total with transitive deps**: ~50-60 MB

### Not Needed in Lambda

- `uvicorn` - Only for local development
- `torch` - Only needed for analysis Lambda (ML model)
- `transformers` - Only needed for analysis Lambda (ML model)

---

## Other Lambdas - Dependency Status

### Ingestion Lambda ✅ (Mostly Working)

**Dependencies needed**:
- `boto3` / `botocore` → ✅ Included in Lambda runtime
- `requests` (NewsAPI client) → ⚠️ **MISSING** (should be failing too!)
- `pydantic` (schemas) → ⚠️ **MISSING**
- `python-json-logger` → ⚠️ **MISSING**

**Current status**: May be working if it doesn't hit code paths requiring requests/pydantic

### Analysis Lambda ⚠️ (Partial Solution)

**Dependencies needed**:
- `transformers` + `torch` → ✅ Provided via Lambda Layer
- `boto3` / `botocore` → ✅ Included in Lambda runtime
- `pydantic` (schemas) → ⚠️ **MISSING**
- `python-json-logger` → ⚠️ **MISSING**

**Current status**: ML model layer provides transformers/torch, but pydantic/logging missing

---

## Solution Options

### Option 1: Bundle Dependencies in Lambda Package (Immediate Fix)

**Pros**:
- Simple to implement
- Works immediately
- No infrastructure changes

**Cons**:
- Larger package size (~50-60 MB per Lambda)
- Slower cold starts
- Duplicates dependencies across Lambdas

**Implementation**:

```bash
# In .github/workflows/deploy.yml, replace dashboard packaging with:

# Package Dashboard Lambda WITH dependencies
mkdir -p packages/dashboard-build
pip install -r requirements.txt -t packages/dashboard-build/
cp -r src/lambdas/dashboard/* packages/dashboard-build/
cp -r src/lambdas/shared packages/dashboard-build/src/lambdas/
cp -r src/lib packages/dashboard-build/src/
cd packages/dashboard-build
zip -r ../dashboard-${SHA}.zip . \
  -x "*.pyc" "__pycache__/*" "*.pytest_cache/*" "tests/*"
cd ../..
rm -rf packages/dashboard-build
```

**Estimated build time**: +2-3 minutes per deployment

### Option 2: Create Dependencies Lambda Layer (Better Long-Term)

**Pros**:
- Smaller Lambda packages (only handler code)
- Faster deployments (layer cached)
- Shared dependencies across Lambdas
- Faster cold starts (layer pre-loaded)

**Cons**:
- More complex setup
- Requires layer management
- One-time build effort

**Implementation**:

```bash
# Create dependencies layer
mkdir -p layer/python
pip install -r requirements.txt -t layer/python/
cd layer
zip -r ../dependencies-layer.zip python/
cd ..

# Upload to S3
aws s3 cp dependencies-layer.zip s3://BUCKET/layers/dependencies.zip

# Publish as layer
aws lambda publish-layer-version \
  --layer-name sentiment-dependencies \
  --description 'Python dependencies for sentiment analyzer' \
  --content S3Bucket=BUCKET,S3Key=layers/dependencies.zip \
  --compatible-runtimes python3.13
```

Then update `infrastructure/terraform/main.tf` to attach layer to dashboard Lambda:

```hcl
module "dashboard_lambda" {
  # ... existing config ...

  layers = [
    aws_lambda_layer_version.dependencies.arn
  ]
}
```

**Estimated build time**: One-time layer build (~5 min), then <30 sec per deployment

### Option 3: Docker Image Lambda (Overkill for Now)

**Pros**:
- Full control over environment
- Can exceed 250 MB unzipped limit
- Better for complex dependencies

**Cons**:
- Much more complex
- Requires ECR repository
- Slower cold starts
- More expensive

**Not recommended** for this project (dependencies are simple enough)

---

## Recommended Solution

**Immediate**: Option 1 (Bundle dependencies)
- Fixes preprod dashboard NOW
- Allows us to proceed with production deployment
- Simple to implement

**Next iteration**: Option 2 (Lambda layer)
- Better architecture
- Implement after first successful prod deploy
- Add to tech debt registry

---

## Implementation Plan (Option 1)

### Step 1: Update GitHub Actions Workflow

Modify `.github/workflows/deploy.yml` to bundle dependencies for ALL Lambdas:

```yaml
- name: Package Lambda Functions
  id: package
  run: |
    SHA="${GITHUB_SHA:0:7}"
    echo "sha=${SHA}" >> $GITHUB_OUTPUT
    echo "name=lambda-packages-${SHA}" >> $GITHUB_OUTPUT

    echo "📦 Building Lambda packages for commit: ${SHA}"
    mkdir -p packages

    # Install dependencies once
    pip install -r requirements.txt -t packages/deps/

    # Package Ingestion Lambda WITH dependencies
    mkdir -p packages/ingestion-build
    cp -r packages/deps/* packages/ingestion-build/
    cp -r src/lambdas/ingestion/* packages/ingestion-build/
    cp -r src/lambdas/shared packages/ingestion-build/src/lambdas/
    cp -r src/lib packages/ingestion-build/src/
    cd packages/ingestion-build
    zip -r ../ingestion-${SHA}.zip . -x "*.pyc" "__pycache__/*"
    cd ../..

    # Package Analysis Lambda WITH dependencies (excluding torch/transformers - in layer)
    mkdir -p packages/analysis-build
    cp -r packages/deps/* packages/analysis-build/
    rm -rf packages/analysis-build/torch*  # Provided by layer
    rm -rf packages/analysis-build/transformers*  # Provided by layer
    cp -r src/lambdas/analysis/* packages/analysis-build/
    cp -r src/lambdas/shared packages/analysis-build/src/lambdas/
    cp -r src/lib packages/analysis-build/src/
    cd packages/analysis-build
    zip -r ../analysis-${SHA}.zip . -x "*.pyc" "__pycache__/*"
    cd ../..

    # Package Dashboard Lambda WITH dependencies
    mkdir -p packages/dashboard-build
    cp -r packages/deps/* packages/dashboard-build/
    cp -r src/lambdas/dashboard/* packages/dashboard-build/
    cp -r src/lambdas/shared packages/dashboard-build/src/lambdas/
    cp -r src/lib packages/dashboard-build/src/
    cp -r src/dashboard packages/dashboard-build/src/  # Static files
    cd packages/dashboard-build
    zip -r ../dashboard-${SHA}.zip . -x "*.pyc" "__pycache__/*"
    cd ../..

    # Cleanup
    rm -rf packages/deps
    rm -rf packages/*-build

    ls -lh packages/
    echo "✅ Lambda packages built successfully"
```

### Step 2: Test Locally

```bash
# Build dashboard package locally
mkdir -p test-package
pip install -r requirements.txt -t test-package/
cp -r src/lambdas/dashboard/* test-package/
cp -r src/lambdas/shared test-package/src/lambdas/
cp -r src/lib test-package/src/

# Verify fastapi is included
unzip -l test-package.zip | grep fastapi
# Should see: fastapi/__init__.py, fastapi/applications.py, etc.

# Check package size
du -h test-package.zip
# Should be ~50-60 MB
```

### Step 3: Deploy to Preprod

```bash
# Push workflow changes
git add .github/workflows/deploy.yml
git commit -m "fix: Bundle Python dependencies in Lambda packages"
git push origin main

# Monitor deployment
gh run watch --repo traylorre/sentiment-analyzer-gsk
```

### Step 4: Verify Dashboard Works

```bash
# Test preprod dashboard
curl -s https://PREPROD_DASHBOARD_URL/health | jq
# Should return: {"status": "healthy", ...}

# Test with API key
curl -H "X-API-Key: $API_KEY" https://PREPROD_DASHBOARD_URL/api/metrics
# Should return metrics data
```

---

## Cost Impact

### Current (Broken)
- Dashboard package: ~50 KB (code only)
- Storage cost: ~$0.00001/month

### After Fix (Option 1)
- Dashboard package: ~50-60 MB (code + deps)
- Storage cost: ~$0.01/month per Lambda × 3 = ~$0.03/month
- Cold start: +200-300ms

### After Optimization (Option 2 - Layer)
- Dashboard package: ~50 KB (code only)
- Dependencies layer: ~50 MB (shared)
- Storage cost: ~$0.01/month (layer) + $0.00003/month (3 Lambdas) = ~$0.01/month
- Cold start: +100-150ms (layer cached)

**Verdict**: Negligible cost impact either way

---

## Testing Checklist

After implementing fix:

- [ ] Dashboard `/health` endpoint returns 200
- [ ] Dashboard `/api/metrics` endpoint returns data
- [ ] Dashboard web UI loads in browser
- [ ] SSE stream (`/api/stream`) connects and sends updates
- [ ] No `ImportError` in CloudWatch logs
- [ ] Cold start time acceptable (<3 seconds)
- [ ] Package size < 250 MB unzipped (Lambda limit)

---

## Tech Debt Created

Add to `docs/TECH_DEBT_REGISTRY.md`:

**TD-021: Lambda Dependencies Bundled in Package**
- **Category**: Build/Deploy
- **Priority**: MEDIUM
- **Effort**: 4-6 hours
- **Description**: Lambda packages bundle all dependencies (~50 MB each) instead of using shared layer
- **Impact**: Slower deployments, larger storage, duplicated dependencies
- **Recommended**: Create dependencies Lambda layer (Option 2 above)
- **SLA**: Implement after first successful production deployment

---

## Lessons Learned

1. **Validate Lambda packages locally** before deploying to AWS
   - Unzip package and check for dependencies
   - Test import statements

2. **CI/CD should mimic local development**
   - If local dev needs `pip install -r requirements.txt`, so does Lambda

3. **Lambda runtime only includes standard library + boto3**
   - Everything else must be bundled or provided via layer

4. **Package inspection commands**:
   ```bash
   # List contents of Lambda ZIP
   unzip -l lambda.zip | head -20

   # Check for specific module
   unzip -l lambda.zip | grep fastapi

   # Extract and inspect
   unzip lambda.zip -d /tmp/inspect
   ls -R /tmp/inspect
   ```

5. **Missing dependency detection**:
   - Lambda logs: `Runtime.ImportModuleError`
   - Always check CloudWatch logs after first deploy
   - Test all endpoints, not just health check

---

## References

- **AWS Lambda Packaging**: https://docs.aws.amazon.com/lambda/latest/dg/python-package.html
- **Lambda Layers**: https://docs.aws.amazon.com/lambda/latest/dg/configuration-layers.html
- **FastAPI Documentation**: https://fastapi.tiangolo.com/deployment/aws-lambda/
- **Mangum (FastAPI Lambda adapter)**: https://mangum.io/

---

*Root cause identified: 2025-11-22*
*Recommendation: Implement Option 1 (bundle dependencies) immediately to unblock production deployment*
