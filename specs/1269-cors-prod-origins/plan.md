# Feature 1269: CORS Production Origins — Implementation Plan

## Overview

Three-layer defense against empty CORS origins in production:
1. **Data fix**: Populate prod.tfvars with known origins
2. **Terraform guard**: `terraform_data` with precondition that fails the plan
3. **CI validator**: Python validator that catches the issue before Terraform runs

## Architecture Decision Records

### ADR-1: terraform_data Guard vs. Variable Validation

**Context**: Need a Terraform mechanism that fails `plan` when `environment = "prod"` and `cors_allowed_origins` is empty. Variable `validation` blocks cannot cross-reference other variables.

**Decision**: Use `terraform_data.cors_production_guard` with a `lifecycle { precondition {} }` block in root `main.tf`. This:
- Evaluates during every `terraform plan`
- Can reference multiple variables (`var.environment`, `var.cors_allowed_origins`)
- Fails the plan (not just warns like `check` blocks)
- Lives alongside the existing `check` block (defense in depth)

**Alternatives rejected**:
- Variable validation: Cannot cross-reference `var.environment`
- Module precondition: Lambda function URL resource is inside `modules/lambda/main.tf`, inaccessible from root
- null_resource: Deprecated in favor of `terraform_data`

### ADR-2: Validator Location

**Context**: Should the CORS validator live in the template repo or target repo?

**Decision**: Template repo (`terraform-gsk-template/src/validators/cors_prod_origins.py`). All validators follow this pattern. The target repo inherits validators through the validation framework. The validator scans tfvars files in whichever repo it is pointed at.

### ADR-3: Amplify Enablement Scope (SUPERSEDED by AR#2)

**Context**: Adding `enable_amplify = true` to prod.tfvars triggers Amplify infrastructure creation.

**Decision**: EXCLUDE from this feature. Amplify enablement is a separate infrastructure expansion. This feature focuses solely on the CORS safety net: making the empty list impossible and providing a known-good origin (GitHub Pages).

## Implementation Phases

### Phase 1: Terraform Changes (sentiment-analyzer-gsk repo)

#### 1.1 Update prod.tfvars

File: `infrastructure/terraform/prod.tfvars`

```hcl
# CORS: Production requires explicit origins - NO WILDCARDS
# Feature 1269: Populated with known production origins
cors_allowed_origins = [
  "https://traylorre.github.io",  # GitHub Pages interview demo
  # TODO(1269): Add Amplify production URL after enable_amplify is set
  # Get it from: terraform output amplify_production_url
  # Format: "https://main.<app-id>.amplifyapp.com"
]
```

Note: `enable_amplify` is NOT set here (separate feature scope per AR#2).

#### 1.2 Add terraform_data Guard

File: `infrastructure/terraform/main.tf` (after existing check block at line 47)

```hcl
# Feature 1269: Hard-fail guard for production CORS origins
# Unlike the check block above (which only warns), this FAILS terraform plan.
resource "terraform_data" "cors_production_guard" {
  lifecycle {
    precondition {
      condition     = var.environment != "prod" || length(var.cors_allowed_origins) > 0
      error_message = <<-EOT
        FATAL: cors_allowed_origins cannot be empty when environment='prod'.
        Both dashboard and SSE Lambda Function URLs use this value for CORS allow_origins.
        An empty list means ALL cross-origin requests are blocked — the frontend will not work.

        Fix: Set cors_allowed_origins in prod.tfvars:
          cors_allowed_origins = ["https://your-domain.amplifyapp.com"]

        Get your Amplify URL: terraform output amplify_production_url
      EOT
    }
  }
}
```

#### 1.3 Add HTTPS-only Check for Prod Origins

File: `infrastructure/terraform/main.tf` (below the guard)

```hcl
# Feature 1269: Warn if prod origins contain non-HTTPS URLs
check "cors_production_https_only" {
  assert {
    condition = var.environment != "prod" || alltrue([
      for origin in var.cors_allowed_origins : startswith(origin, "https://")
    ])
    error_message = "WARNING: Production cors_allowed_origins should use HTTPS only. HTTP origins found."
  }
}
```

#### 1.4 Keep Existing Check Block

The existing `check "cors_production_validation"` at main.tf:42-46 stays as-is. It provides a human-readable warning even for non-prod environments that might benefit from explicit origins.

### Phase 2: CI Validator (terraform-gsk-template repo)

#### 2.1 Create Validator

File: `src/validators/cors_prod_origins.py`

Pattern: Follow `FallbackValidator` structure. The validator:
1. Finds all `*.tfvars` files in the target repo's `infrastructure/terraform/` directory
2. Parses each file to identify `environment` and `cors_allowed_origins` values
3. For files where `environment = "prod"`:
   - CPO-001: Flags empty `cors_allowed_origins`
   - CPO-002: Flags wildcard `*` in origins
   - CPO-003: Flags HTTP (non-HTTPS) origins
   - CPO-004: Flags localhost origins (http://localhost:*, http://127.0.0.1:*)

Parsing approach: Use regex to extract HCL values from tfvars (simple key-value format). Do NOT use python-hcl2 for this — tfvars files are simple enough for regex, and it avoids a dependency issue.

#### 2.2 Register Validator

Files to update:
- `.specify/methodologies/index.yaml` — add `cors_prod_origins_validation` entry
- `Makefile` — add `cors-prod-origins-validate` target
- `.claude/commands/cors-prod-origins-validate.md` — slash command

### Phase 3: Tests

#### 3.1 Unit Tests — Python Validator (template repo)

File: `tests/unit/test_cors_prod_origins_validator.py`

Test cases:
- `test_empty_origins_prod_detected` — CPO-001
- `test_wildcard_origin_prod_detected` — CPO-002
- `test_http_origin_prod_detected` — CPO-003
- `test_localhost_origin_prod_detected` — CPO-004
- `test_valid_prod_origins_pass` — no findings for correct config
- `test_empty_origins_dev_allowed` — no findings for dev with empty origins
- `test_preprod_with_http_localhost_allowed` — no findings for preprod

#### 3.2 Integration Tests — Validator Against Real Repo (template repo)

File: `tests/integration/test_cors_prod_origins_integration.py`

Test cases:
- `test_validator_against_sentiment_repo` — run validator against `../sentiment-analyzer-gsk`, verify no findings (after prod.tfvars is fixed)
- `test_validator_against_template_repo` — run validator against template repo (should find nothing, no prod.tfvars)

#### 3.3 Terraform Test — Plan Failure (sentiment-analyzer-gsk repo)

File: `infrastructure/terraform/tests/cors_guard.tftest.hcl`

```hcl
# Test that prod with empty CORS origins fails
run "prod_empty_cors_fails" {
  command = plan

  variables {
    environment          = "prod"
    cors_allowed_origins = []
    aws_region           = "us-east-1"
  }

  expect_failures = [
    terraform_data.cors_production_guard
  ]
}

# Test that prod with valid origins succeeds
run "prod_valid_cors_succeeds" {
  command = plan

  variables {
    environment          = "prod"
    cors_allowed_origins = ["https://example.com"]
    aws_region           = "us-east-1"
  }
}

# Test that dev with empty origins succeeds (localhost fallback)
run "dev_empty_cors_succeeds" {
  command = plan

  variables {
    environment          = "dev"
    cors_allowed_origins = []
    aws_region           = "us-east-1"
  }
}
```

**Caveat**: `terraform test` requires provider initialization and may need mock providers. If this proves too complex for CI, document it as a manual verification step and rely on the Python validator as the automated gate.

#### 3.4 E2E Tests — CORS Headers (sentiment-analyzer-gsk repo)

File: `tests/e2e/test_cors_prod_headers.py`

```python
@pytest.mark.skipif(
    os.getenv("AWS_ENV") != "prod",
    reason="Requires prod deployment"
)
def test_prod_cors_allows_configured_origins():
    """Verify prod Lambda Function URL returns correct CORS headers."""
    # Send preflight OPTIONS request with Origin header
    # Verify Access-Control-Allow-Origin matches configured origin
    # Verify Access-Control-Allow-Credentials is true
```

#### 3.5 Playwright Tests — Dashboard Loads (sentiment-analyzer-gsk repo)

File: `tests/e2e/playwright/test_prod_cors.spec.ts`

```typescript
test('production dashboard loads without CORS errors', async ({ page }) => {
  // Navigate to prod Amplify URL
  // Listen for console errors containing "CORS"
  // Verify page content renders (not blocked)
});
```

**Open question from spec**: Both E2E and Playwright tests require a deployed prod environment. These will be marked with skip conditions and are meaningful only after prod deployment. This is noted as a testing limitation, not a blocker.

## File Change Summary

### sentiment-analyzer-gsk repo (target)

| File | Action | Description |
|------|--------|-------------|
| `infrastructure/terraform/prod.tfvars` | MODIFY | Set cors_allowed_origins with GitHub Pages origin |
| `infrastructure/terraform/main.tf` | MODIFY | Add terraform_data guard + HTTPS check block |
| `infrastructure/terraform/tests/cors_guard.tftest.hcl` | CREATE (OPTIONAL) | Terraform native test for plan failure (nice-to-have) |
| `tests/e2e/test_cors_prod_headers.py` | CREATE | E2E CORS header verification (via API Gateway) |
| `tests/e2e/playwright/test_prod_cors.spec.ts` | CREATE | Playwright dashboard load test |

### terraform-gsk-template repo (template)

| File | Action | Description |
|------|--------|-------------|
| `src/validators/cors_prod_origins.py` | CREATE | Python CI validator |
| `tests/unit/test_cors_prod_origins_validator.py` | CREATE | Validator unit tests |
| `tests/integration/test_cors_prod_origins_integration.py` | CREATE | Validator integration tests |
| `.specify/methodologies/index.yaml` | MODIFY | Register new methodology |
| `Makefile` | MODIFY | Add make target |
| `.claude/commands/cors-prod-origins-validate.md` | CREATE | Slash command |

## Rollback Plan

If the CORS origins cause issues in prod:
1. Revert `prod.tfvars` to `cors_allowed_origins = []`
2. The terraform_data guard will block the plan — override by temporarily removing the guard resource
3. Or set a placeholder origin to satisfy the guard while debugging

This is intentionally friction-ful. An empty CORS list in prod is always wrong.

## Pre-Flight Checklist

Before deploying to prod:
- [ ] `terraform plan -var-file=prod.tfvars` succeeds (guard passes)
- [ ] CI validators pass (`make validate`)
- [ ] After Amplify is enabled: run `terraform output amplify_production_url` and add to `cors_allowed_origins`

---

## Adversarial Review #2

### AR2-FINDING-1: Scope Creep — enable_amplify REMOVED from This Feature (CRITICAL)

**Problem**: The plan includes `enable_amplify = true` and `amplify_github_repository` in prod.tfvars. Per Stage 4 clarification (CQ-1), this was SPLIT OUT because it triggers massive infrastructure creation (Amplify app, IAM role, Secrets Manager dependency, Cognito callback patching) and is orthogonal to the CORS safety net.

**Resolution**: Remove from plan. The prod.tfvars change is ONLY:
```hcl
cors_allowed_origins = [
  "https://traylorre.github.io",
]
```

No `enable_amplify`, no `amplify_github_repository`. ADR-3 is superseded.

**Impact on plan**:
- Phase 1.1: Simplified — only update cors_allowed_origins
- File change summary: prod.tfvars change is smaller
- Pre-flight checklist: Remove Secrets Manager token check
- ADR-3: Decision changed to "EXCLUDE from this feature"

### AR2-FINDING-2: terraform_data Precondition Semantics Verification

**Concern**: Does `terraform_data` with only a `lifecycle { precondition {} }` and no other attributes actually work? A `terraform_data` resource with no `input` or `triggers_replace` creates a no-op resource in state.

**Verification**: Yes, this is valid Terraform. `terraform_data` can exist solely for its lifecycle preconditions. It will appear in state as an empty managed resource, and its precondition will be evaluated during every plan. This is a documented pattern for "plan-time assertions."

**No change needed.**

### AR2-FINDING-3: HTTPS-Only Check Empty List Edge Case

**Problem**: The proposed `check "cors_production_https_only"` uses `alltrue()` on `var.cors_allowed_origins`. If the list is empty, `alltrue([])` returns `true` (vacuous truth). This means the HTTPS check would pass even when origins are empty.

**Resolution**: This is correct behavior. The empty-list case is caught by the `terraform_data` precondition (hard fail). The HTTPS check only needs to validate non-empty lists. The `alltrue([])` = `true` behavior is desired — no false positive when the guard is about to fail anyway.

### AR2-FINDING-4: Regex Parsing Robustness

**Problem**: The plan proposes regex to parse tfvars. HCL tfvars can have:
- Multi-line lists: `cors_allowed_origins = [\n  "a",\n  "b"\n]`
- Comments inside lists: `"a",  # comment`
- Trailing commas: `"a",`
- No trailing newline

**Resolution**: The regex approach handles all these cases:
1. `environment\s*=\s*"(\w+)"` — single-line, always works
2. `cors_allowed_origins\s*=\s*\[(.*?)\]` with `re.DOTALL` — captures multi-line content
3. `"([^"]+)"` within captured content — extracts strings, ignores comments
4. Empty check: if no string matches found, list is effectively empty

Edge case: What if `cors_allowed_origins` is not defined at all in a tfvars file? Then the regex finds no match, and the validator should treat it as "not set" (equivalent to default empty list). For prod, this should trigger CPO-001.

**Action**: Add explicit test case for "cors_allowed_origins not defined in prod.tfvars".

### AR2-FINDING-5: Amplify URL Check is Now Deferred

The plan had a check for `.amplifyapp.com` domain in cors_allowed_origins when `enable_amplify = true`. Since `enable_amplify` is removed from scope, this check is also removed. The check can be added when Amplify enablement is its own feature.

### AR2-FINDING-6: Terraform Test Requires Many Variable Defaults

The `.tftest.hcl` file sets only `environment`, `cors_allowed_origins`, and `aws_region`. But `main.tf` references many other variables (model_version, watch_tags, alarm_email, etc.) that need defaults. These have defaults in `variables.tf` so this should work. However, the Terraform configuration also has module references that require provider initialization.

**Resolution**: The `.tftest.hcl` is explicitly marked as NICE-TO-HAVE in CQ-4. The primary automated gate is the Python CI validator. Downgrade this to a documentation-only item — provide the test file content in the spec but do not make it a required implementation task.

### AR2-FINDING-7: E2E Test — Function URLs Are Now Behind API Gateway

Per Feature 1256, Lambda Function URLs use `AWS_IAM` auth (not NONE). Direct HTTP requests to Function URLs will get 403. The CORS headers are only meaningful through the API Gateway or CloudFront path.

**Resolution**: The E2E test must go through the API Gateway endpoint, not directly to the Function URL. Update the test design:
```python
# Use API Gateway URL, not Function URL
api_url = os.getenv("PROD_API_GATEWAY_URL")
response = requests.options(f"{api_url}/api/v2/health", headers={"Origin": "https://traylorre.github.io"})
```

However, API Gateway has its OWN CORS configuration (Feature 1253). The Lambda Function URL CORS config may be redundant when all traffic goes through API Gateway. This is an architectural question beyond this feature's scope — but the E2E test should test the path that actual users take (API Gateway).

### Plan Amendments from AR#2

1. **Phase 1.1 SIMPLIFIED**: prod.tfvars only adds `cors_allowed_origins`, no Amplify vars
2. **ADR-3 SUPERSEDED**: enable_amplify is out of scope
3. **Phase 3.3 DOWNGRADED**: .tftest.hcl is documentation-only, not required task
4. **Phase 3.4 AMENDED**: E2E test targets API Gateway URL, not Function URL directly
5. **File change summary UPDATED**: prod.tfvars is smaller change, .tftest.hcl is optional
6. **Test case ADDED**: "cors_allowed_origins not defined in prod.tfvars" triggers CPO-001
