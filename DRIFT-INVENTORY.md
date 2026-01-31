# Architecture Drift Inventory

Generated: 2026-01-29
Updated: 2026-01-30 (Excision Pass #1)
Status: Active audit in progress - Pass #1 complete

## Summary

| Category | Count | Status | Severity |
|----------|-------|--------|----------|
| Phantom Components | 4 → 1 | ✅ 3 fixed, 1 partial | HIGH |
| Deprecated Paths Still Primary | 2 | ⏳ Pending | HIGH |
| Hardcoded URLs | 8 → 5 | ✅ 3 fixed | MEDIUM |
| Legacy Code Markers | 12 | ⏳ Pending | LOW |
| Archive Directories | 3 | ✅ Acceptable | INFO |
| Commented-Out Terraform | 9 | ⏳ Pending | LOW |

**Pass #1 Progress (2026-01-30):**
- Phantom Auth Lambda: ✅ Fixed in architecture.mmd
- Phantom Scheduler Lambda: ✅ Fixed in 4 diagram files, ⚠️ ~15 refs remain in SPEC.md
- Hardcoded URLs: ✅ Fixed in traffic_generator.py (env vars) and ohlc-api.yaml (server vars)

---

## Category 1: Phantom Components (CRITICAL)

Documentation references Lambda functions that do not exist.

### Actual Lambdas (6 total)
1. `{env}-sentiment-ingestion`
2. `{env}-sentiment-analysis`
3. `{env}-sentiment-dashboard`
4. `{env}-sentiment-metrics`
5. `{env}-sentiment-notification`
6. `{env}-sentiment-sse-streaming`

### Phantom Lambdas in Documentation

| Phantom Name | Status | Resolution |
|--------------|--------|------------|
| Auth Lambda | ✅ FIXED | Removed from architecture.mmd; auth handled by Dashboard Lambda |
| Config Lambda | ✅ FIXED | USE-CASE-DIAGRAMS.md deleted (2026-01-29) |
| Alert Lambda | ✅ FIXED | USE-CASE-DIAGRAMS.md deleted; alerts handled by Notification Lambda |
| Scheduler Lambda | ⚠️ PARTIAL | Removed from diagram docs; ~15 refs remain in SPEC.md (Pass #2) |

**Completed Actions:**
- ✅ USE-CASE-DIAGRAMS.md deleted (2026-01-29)
- ✅ architecture.mmd updated to show 6 actual Lambdas (2026-01-30)
- ✅ diagram-1-high-level-overview.md fixed (2026-01-30)
- ✅ DIAGRAM-CREATION-CHECKLIST.md fixed (2026-01-30)
- ✅ diagram-2-security-flow.md DLQ list fixed (2026-01-30)
- ✅ docs/diagrams/README.md Scheduler section removed (2026-01-30)

**Remaining (Pass #2):**
- ⏳ SPEC.md has ~15 Scheduler Lambda refs in bottleneck/scaling analysis sections

---

## Category 2: Deprecated Paths Documented as Primary (CRITICAL)

### Issue: Lambda Function URL vs API Gateway

**Terraform Truth (main.tf:1078-1086):**
```hcl
output "dashboard_function_url" {
  description = "URL of the Dashboard Lambda Function URL (legacy, use API Gateway URL)"
  ...
}

output "dashboard_api_url" {
  description = "URL of the API Gateway endpoint (recommended for production)"
  ...
}
```

**Documentation Drift:**

| File | Line | Says | Should Say |
|------|------|------|------------|
| README.md | 152 | "direct Lambda Function URL access" | "API Gateway access" |
| README.md | 499 | "Dashboard Lambda (Function URL)" | "Dashboard Lambda (via API Gateway)" |
| README.md | 247 | "direct to Amplify/Lambda Function URLs" | "via API Gateway" |

**Action Required:** Update README.md to reflect API Gateway as primary path

---

## Category 3: Hardcoded URLs (MEDIUM)

### Lambda Function URLs

| URL | Files | Risk |
|-----|-------|------|
| `cjx6qw4a7xqw6cuifvkbi6ae2e0evviw.lambda-url.us-east-1.on.aws` | interview/traffic_generator.py:35 | HIGH |
| `ee2a3fxtkxmpwp2bhul3uylmb40hfknf.lambda-url.us-east-1.on.aws` | tests/integration/test_e2e_lambda_invocation_preprod.py:42 | HIGH |
| `prod-sentiment-dashboard.lambda-url.us-east-1.on.aws` | ~~interview/traffic_generator.py:36~~ (FIXED) | ~~MEDIUM~~ ✅ |

### API Gateway URLs

| URL | Files | Context |
|-----|-------|---------|
| `yikrqu13lj.execute-api.us-east-1.amazonaws.com` | specs/107-fix-cloudfront-403/spec.md:21,25, specs/1114-cors-api-gateway-fix/research.md:20,24 | Historical spec docs |

### S3 URLs

| URL | Files |
|-----|-------|
| `preprod-sentiment-lambda-deployments.s3.amazonaws.com/deployment-metadata.json` | interview/index.html:1815 |

**Action Required:** Replace hardcoded URLs with environment variables or Terraform outputs

---

## Category 4: Legacy Code Markers (LOW)

### Authentication (Legacy X-User-ID Header)
- `src/lambdas/dashboard/router_v2.py:255` - Legacy header support
- `src/lambdas/sse_streaming/handler.py:372,382,411` - Legacy fallback
- `src/lambdas/shared/middleware/auth_middleware.py:1-7,404-406` - DEPRECATED function

### Data Access
- `src/lambdas/dashboard/auth.py:447-450` - `get_user_by_email()` DEPRECATED (O(n) scan)
- `src/lambdas/shared/dynamodb.py:203-208` - `item_exists()` deprecated

### Aliases
- `src/lambdas/sse_streaming/stream.py:473-474` - `stream_generator` alias deprecated

### Model Fields
- `src/lambdas/shared/models/configuration.py:43` - `is_active` field legacy (use `status`)
- `src/lambdas/shared/models/magic_link_token.py:13` - `signature` field deprecated (Feature 1166)

### Other
- `src/lambdas/ingestion/handler.py:300` - Sequential mode marked legacy
- `src/lambdas/shared/auth/merge.py:402-405` - `_transfer_items()` deprecated
- `src/lambdas/shared/middleware/security_headers.py:43` - X-XSS-Protection legacy

---

## Category 5: Archive Directories (INFO)

Well-organized archives exist at:
- `/docs/archive/` - Historical documentation
- `/docs/archived-specs/` - Superseded specifications
- `/specs/1126-auth-httponly-migration/archive/` - Auth migration archives

---

## Category 6: Commented-Out Terraform (LOW)

### Lambda Deployment S3 Bucket (main.tf:142-165)
```hcl
# Commented aws_s3_bucket resource
# Commented aws_s3_bucket_versioning resource
# Commented aws_s3_bucket_public_access_block resource
```

### Chaos Engineering (modules/chaos/main.tf:125-243)
- Lambda latency experiment template (AWS provider limitation #41208)
- Lambda error experiment template (awaiting provider update)

---

## Remediation Priority

### P0 - Do Now
1. [x] ~~DELETE `docs/architecture/USE-CASE-DIAGRAMS.md`~~ (Deleted 2026-01-29)
2. [ ] Update README.md lines 152, 247, 499 to reference API Gateway

### P1 - This Week
3. [x] ~~Replace hardcoded URLs in traffic_generator.py with env vars~~ (2026-01-30 - Added SENTIMENT_PREPROD_URL, SENTIMENT_PROD_URL env vars + --url CLI override)
4. [x] ~~Update ohlc-api.yaml OpenAPI spec with parameterized URLs~~ (2026-01-30 - Added server variables)
5. [ ] Verify frontend is wired to API Gateway, not Lambda Function URL

### P2 - This Month
6. [ ] Complete X-User-ID header deprecation
7. [ ] Remove commented Terraform once AWS provider updated
8. [ ] Audit `get_user_by_email()` callers for GSI migration

### Added in Pass #1 (2026-01-30)
9. [x] ~~Fix phantom Auth Lambda in architecture.mmd~~ (Merged auth into Dashboard Lambda, added Metrics + Notification Lambdas)
10. [x] ~~Clean up Scheduler Lambda refs in diagram docs~~ (Fixed diagram-1, diagram-2, CHECKLIST, README)
11. [ ] SPEC.md comprehensive Scheduler Lambda cleanup - ~15 references remain in bottleneck/scaling/metrics sections

---

## Verification Commands

```bash
# List actual deployed Lambdas (requires IAM permissions)
aws lambda list-functions --query "Functions[?starts_with(FunctionName, 'preprod-sentiment')].FunctionName"

# Check API Gateway configuration
aws apigateway get-rest-apis --query "items[?contains(name, 'sentiment')].{id:id,name:name}"

# Verify Terraform outputs
cd infrastructure/terraform && terraform output
```

---

## Related Files

- **Terraform Truth:** `infrastructure/terraform/main.tf`, `outputs.tf`
- **Primary Docs:** `README.md`, `docs/architecture/`
- **Target Repo Config:** Template's `.specify/target-repo.yaml` (path updated to /home/zeebo/)
