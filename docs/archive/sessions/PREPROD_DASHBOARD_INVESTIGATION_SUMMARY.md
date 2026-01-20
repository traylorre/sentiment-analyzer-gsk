# Preprod Dashboard Investigation Summary

**Date**: 2025-11-22
**Investigator**: Claude Code
**Objective**: Get preprod dashboard running before first production deployment

---

## Investigation Timeline

### 1. Initial Attempt to Access Dashboard

**Action**: Tried to get preprod dashboard URL via terraform

**Blocker**: Terraform not initialized for preprod backend

**Lesson Learned Applied**: Referenced `docs/TERRAFORM_LESSONS_LEARNED.md` before proceeding

### 2. Safe Terraform Initialization

**Steps Taken** (documented in `docs/GET_DASHBOARD_RUNNING.md`):
1. ✅ Verified working directory: `/home/traylorre/projects/sentiment-analyzer-gsk/infrastructure/terraform`
2. ✅ Checked AWS region: Was `us-west-2`, fixed to `us-east-1` (Lesson #2 from terraform docs)
3. ✅ Verified backend config exists: `backend-preprod.hcl`
4. ✅ Initialized terraform with preprod backend: `terraform init -backend-config=backend-preprod.hcl -backend-config="region=us-east-1"`
5. ✅ Retrieved dashboard URL: `https://ee2a3fxtkxmpwp2bhul3uylmb40hfknf.lambda-url.us-east-1.on.aws/`

**Success**: Terraform state synced, infrastructure exists

### 3. Dashboard Access Attempt

**Action**: Tested dashboard health endpoint

**Result**: ❌ `Internal Server Error`

**Investigation**: Checked CloudWatch logs

### 4. Root Cause Identified

**Error in CloudWatch**:
```
[ERROR] Runtime.ImportModuleError: Unable to import module 'handler': No module named 'fastapi'
```

**Root Cause**: Lambda package missing dependencies

**Full Analysis**: See `docs/LAMBDA_DEPENDENCY_ANALYSIS.md`

---

## Key Findings

### 1. Infrastructure is Deployed ✅

- ✅ Preprod terraform state exists and is accessible
- ✅ DynamoDB table exists: `preprod-sentiment-items`
- ✅ Lambda functions exist:
  - `preprod-sentiment-ingestion`
  - `preprod-sentiment-analysis`
  - `preprod-sentiment-dashboard`
- ✅ Secrets Manager secrets exist (but not populated with values)
- ✅ Lambda Function URL configured

### 2. Lambda Packaging is Broken ❌

**Problem**: CI/CD workflow only zips handler code, not dependencies

**Evidence**:
```bash
# Current build (broken)
cd src/lambdas/dashboard
zip -r ../../../packages/dashboard-${SHA}.zip .
# Only includes: handler.py, metrics.py, local imports
# Missing: fastapi, mangum, sse-starlette, pydantic, etc.
```

**Impact**: Dashboard Lambda cannot start (missing fastapi)

### 3. All Lambdas Likely Affected ⚠️

| Lambda | Missing Dependencies | Status |
|--------|---------------------|---------|
| **Dashboard** | fastapi, mangum, sse-starlette, pydantic | ❌ Failing |
| **Ingestion** | requests, pydantic, python-json-logger | ⚠️ May be failing |
| **Analysis** | pydantic, python-json-logger (torch/transformers via layer) | ⚠️ May be failing |

### 4. Cost Controls are in Place ✅

**Verified from terraform code**:

```hcl
# Lambda concurrency limits (main.tf:127,171,221)
Ingestion: reserved_concurrency = 1   ✅ CRITICAL
Analysis: reserved_concurrency = 5    ✅
Dashboard: reserved_concurrency = 10  ✅

# Budget alarm (modules/monitoring/main.tf:274)
Monthly limit: $100                   ✅
Alert at 80%: $80                     ✅
Alert at 100%: $100                   ✅
```

**All other alarms configured** (see `docs/FIRST_PROD_DEPLOY_READY.md`)

---

## Recommendation

### Immediate Actions Required

1. **Fix Lambda Packaging** (BLOCKER for prod deploy)
   - Implement Option 1 from `docs/LAMBDA_DEPENDENCY_ANALYSIS.md`
   - Bundle dependencies in Lambda packages
   - Estimated time: 1-2 hours to implement + test

2. **Test in Preprod** (After fix)
   - Verify all 3 Lambdas can import modules
   - Test dashboard health endpoint
   - Test full ingestion → analysis → dashboard flow

3. **Proceed to Production** (After preprod validation)
   - Follow `docs/FIRST_PROD_DEPLOY_READY.md`
   - Execute production preflight checklist
   - Deploy with monitoring

### Sequence

```
1. Fix Lambda packaging (GitHub Actions workflow)
   ↓
2. Deploy to preprod (automatic via CI/CD)
   ↓
3. Validate preprod dashboard works
   ↓
4. Review production preflight checklist
   ↓
5. Deploy to production
   ↓
6. Monitor for 1 hour with dashboard
```

---

## Decision Point

**Question**: Do we fix preprod first, or go directly to production?

### Option A: Fix Preprod First (RECOMMENDED ✅)

**Pros**:
- Validate fix works before production
- Dashboard observability before prod deploy
- Lower risk
- Follows best practices

**Cons**:
- Additional 1-2 hours delay
- One more CI/CD cycle

**Timeline**: ~2-3 hours total (fix + test + deploy)

### Option B: Skip Preprod, Fix in Production (NOT RECOMMENDED ❌)

**Pros**:
- Faster to production
- Only one CI/CD cycle

**Cons**:
- **HIGH RISK** - untested fix in production
- No observability before deploy
- If dashboard fails in prod, no way to monitor
- Violates promotion pipeline design

**Timeline**: ~1-2 hours total (fix + deploy)

---

## Recommendation: Option A ✅

**Rationale**:
1. We already have cost controls in place (low financial risk)
2. Dashboard observability is critical for first prod deploy
3. Testing packaging fix in preprod ensures it works
4. Only 1-2 extra hours vs significantly higher risk

**Next Steps**:
1. Create PR to fix Lambda packaging (Option 1 from analysis doc)
2. Merge and deploy to preprod
3. Validate dashboard works
4. Proceed to production with confidence

---

## Documents Created

1. **`docs/GET_DASHBOARD_RUNNING.md`**
   - Step-by-step terraform initialization
   - How to access preprod dashboard
   - Safety checks before production
   - Troubleshooting guide

2. **`docs/LAMBDA_DEPENDENCY_ANALYSIS.md`**
   - Root cause of dashboard failure
   - Complete dependency analysis for all 3 Lambdas
   - 3 solution options with pros/cons
   - Implementation plan (recommended: Option 1)
   - Testing checklist
   - Tech debt created

3. **`docs/FIRST_PROD_DEPLOY_READY.md`** (already existed)
   - Cost controls verification
   - Production preflight checklist
   - Andon cord procedures
   - Post-deployment monitoring

4. **This summary document**
   - Investigation timeline
   - Key findings
   - Recommendations
   - Decision point

---

## Cost Impact

**Fixing dependencies**: ~$0.03/month additional storage (negligible)

**Current blocker cost**: $0 (dashboard not working, so not incurring costs)

**After fix**: Normal operational costs as documented in `FIRST_PROD_DEPLOY_READY.md` ($5-15/month)

---

## Confidence Level

**For Production Deployment**:

| Aspect | Confidence | Notes |
|--------|-----------|-------|
| Cost controls in place | ✅ HIGH | Verified in terraform |
| Monitoring configured | ✅ HIGH | All alarms exist |
| Andon cord ready | ✅ HIGH | Documented procedures |
| Dashboard observability | ⚠️ MEDIUM | Needs dependency fix |
| Lambda functionality | ⚠️ MEDIUM | Needs packaging fix |

**Overall**: ⚠️ **NOT READY** until Lambda packaging is fixed

**After fixing dependencies**: ✅ **READY FOR PRODUCTION**

---

## Team Communication

**Status for user**:

> We successfully accessed preprod infrastructure and identified the root cause of the dashboard failure. The Lambda packages are missing Python dependencies (fastapi, mangum, etc.). This affects all 3 Lambdas.
>
> **Good news**: All cost controls are in place (concurrency limits, budget alarms).
>
> **Action needed**: Fix Lambda packaging in CI/CD workflow to bundle dependencies. Estimated 1-2 hours to implement and test in preprod.
>
> **Recommendation**: Fix preprod first, validate dashboard works, THEN deploy to production with confidence.

---

*Investigation completed: 2025-11-22*
*Ready for next phase: Lambda packaging fix*
