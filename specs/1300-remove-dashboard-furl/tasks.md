# Feature 1300: Tasks

## Task Dependency Graph

```
T1 (Terraform) → T2 (CI/CD) → T3 (Tests) → T4 (Verify)
```

### T1: Remove Dashboard Function URL from Terraform

**File:** `infrastructure/terraform/main.tf`
**Requirements:** FR-001, FR-002, FR-005

1. Set `create_function_url = false` on `module "dashboard_lambda"`
2. Remove `function_url_auth_type`, `function_url_invoke_mode`, `function_url_cors` from Dashboard module call
3. Remove `output "dashboard_function_url"` from root outputs
4. KEEP `SSE_LAMBDA_URL` env var on Dashboard Lambda

**Acceptance:** `terraform plan` shows only Dashboard Function URL resource destruction. SSE unaffected.

---

### T2: Remove Dashboard Function URL from CI/CD

**File:** `.github/workflows/deploy.yml`
**Requirements:** FR-003

1. Remove `terraform output dashboard_function_url` retrieval (preprod lines ~1074, prod lines ~1998)
2. Remove `dashboard_url` from step outputs and job outputs
3. Remove Dashboard warmup curl (keep SSE warmup)
4. Remove "Wait for Function URL propagation" step
5. Remove `DASHBOARD_FUNCTION_URL` env var from test job (line ~1527)
6. Replace `dashboard_url` in deployment metadata with API Gateway URL

**Acceptance:** CI/CD pipeline has zero references to Dashboard Function URL. SSE references intact.

---

### T3: Update test_function_url_restricted.py

**File:** `tests/e2e/test_function_url_restricted.py`
**Requirements:** FR-004

1. Remove `test_dashboard_function_url_returns_403`
2. Remove `test_bearer_token_on_function_url_still_403`
3. Keep `test_sse_function_url_returns_403`, `test_api_gateway_health_works`, `test_cloudfront_sse_status_works`
4. Rename class `TestDirectFunctionURLBlocked` → `TestDirectSSEFunctionURLBlocked`

**Acceptance:** 3 tests remain, 2 removed. File still validates SSE Function URL security.

---

### T4: Verify no remaining references

**Requirements:** NFR-001, NFR-002

1. `grep -rn 'dashboard_function_url\|DASHBOARD_FUNCTION_URL' infrastructure/ .github/ tests/` returns zero hits
2. `terraform plan` shows ONLY Dashboard Function URL destruction
3. SSE Lambda Function URL unchanged
4. Run unit tests: `pytest tests/unit/ -q`

**Acceptance:** Zero references to Dashboard Function URL. All tests pass.

## Requirements Coverage

| Requirement | Task(s) |
|-------------|---------|
| FR-001 | T1 |
| FR-002 | T1 |
| FR-003 | T2 |
| FR-004 | T3 |
| FR-005 | T1 (explicit KEEP) |
| NFR-001 | T4 |
| NFR-002 | T4 |

## Adversarial Review #3

**Highest-risk task:** T2 (CI/CD). The deploy.yml has ~20 references to dashboard_url across preprod and prod sections. Missing one creates a CI failure on next deploy.

**Most likely rework:** T2 — the deployment metadata JSON structure may need adjustment when `dashboard_url` is removed. Downstream consumers of S3 metadata (monitoring, dashboards) may expect the field.

### Gate Statement
**READY FOR IMPLEMENTATION.** 0 CRITICAL, 0 HIGH remaining.
