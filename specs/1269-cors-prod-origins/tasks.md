# Feature 1269: CORS Production Origins — Tasks

## Task Dependency Graph

```
T1 (prod.tfvars) ──┐
                    ├──> T3 (integration test validator)
T2 (terraform_data guard) ──┐
                             ├──> T5 (E2E test)
T4 (CI validator) ──────────┘      │
  ├──> T4a (unit tests)            ├──> T6 (Playwright test)
  ├──> T4b (register methodology)  │
  └──> T4c (slash command)         │
                                   └──> T7 (optional: .tftest.hcl)
```

Parallelizable: T1+T2 can run in parallel. T4 depends on neither. T4a depends on T4.

## Tasks

### T1: Populate prod.tfvars CORS Origins

**Repo**: sentiment-analyzer-gsk
**File**: `infrastructure/terraform/prod.tfvars`
**Action**: MODIFY
**Dependencies**: None
**Estimated effort**: 5 min

Replace:
```hcl
cors_allowed_origins = []
```

With:
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

**Verification**: `grep -c 'cors_allowed_origins' infrastructure/terraform/prod.tfvars` returns non-empty list.

---

### T2: Add terraform_data Guard and HTTPS Check

**Repo**: sentiment-analyzer-gsk
**File**: `infrastructure/terraform/main.tf`
**Action**: MODIFY (insert after line 47, after existing check block)
**Dependencies**: None
**Estimated effort**: 10 min

Add after the existing `check "cors_production_validation"` block:

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

**Verification**: `terraform validate` in infrastructure/terraform/ passes. `terraform plan -var-file=dev.tfvars` still works (guard is prod-only).

---

### T3: Integration Test — Validator Against Real Repo

**Repo**: terraform-gsk-template
**File**: `tests/integration/test_cors_prod_origins_integration.py`
**Action**: CREATE
**Dependencies**: T1 (prod.tfvars must be fixed first), T4 (validator must exist)
**Estimated effort**: 15 min

Test cases:
- `test_validator_against_sentiment_repo` — run validator against `../sentiment-analyzer-gsk`, verify zero findings (prod.tfvars is now correctly populated)
- `test_validator_against_template_repo` — run validator against template repo, verify zero findings (no prod.tfvars exists)
- `test_validator_against_bad_prod_tfvars` — create temp dir with bad prod.tfvars, verify CPO-001 finding

Use `tmp_path` fixture for synthetic bad tfvars.

---

### T4: Create CORS Production Origins CI Validator

**Repo**: terraform-gsk-template
**File**: `src/validators/cors_prod_origins.py`
**Action**: CREATE
**Dependencies**: None
**Estimated effort**: 45 min

Implement `CorsProdOriginsValidator(BaseValidator)`:

```python
class CorsProdOriginsValidator(BaseValidator):
    """Validator for production CORS origin configuration in tfvars files.

    Detects:
    - CPO-001: Empty cors_allowed_origins in prod tfvars
    - CPO-002: Wildcard origin in prod tfvars
    - CPO-003: HTTP (non-HTTPS) origin in prod tfvars
    - CPO-004: Localhost origin in prod tfvars
    """

    name = "cors-prod-origins-validate"
    description = "Detect empty or insecure CORS origins in production tfvars"
```

Key implementation details:
- Scan `infrastructure/terraform/*.tfvars` (or configurable path)
- Parse environment with: `re.search(r'environment\s*=\s*"(\w+)"', content)`
- Parse origins with: `re.search(r'cors_allowed_origins\s*=\s*\[(.*?)\]', content, re.DOTALL)`
- Extract strings with: `re.findall(r'"([^"]+)"', list_content)`
- Only flag findings for `environment = "prod"` files
- If `cors_allowed_origins` is not defined at all in a prod file, treat as empty (CPO-001)

---

### T4a: Unit Tests for CORS Validator

**Repo**: terraform-gsk-template
**File**: `tests/unit/test_cors_prod_origins_validator.py`
**Action**: CREATE
**Dependencies**: T4
**Estimated effort**: 30 min

Test cases (using `tmp_path` with synthetic tfvars files):

| Test | Scenario | Expected |
|------|----------|----------|
| `test_cpo_001_empty_origins_prod` | `environment = "prod"`, `cors_allowed_origins = []` | 1 finding, CPO-001, severity HIGH |
| `test_cpo_001_missing_origins_prod` | `environment = "prod"`, no cors_allowed_origins line | 1 finding, CPO-001 |
| `test_cpo_002_wildcard_origin_prod` | `cors_allowed_origins = ["*"]` | 1 finding, CPO-002, severity CRITICAL |
| `test_cpo_003_http_origin_prod` | `cors_allowed_origins = ["http://example.com"]` | 1 finding, CPO-003, severity HIGH |
| `test_cpo_004_localhost_origin_prod` | `cors_allowed_origins = ["http://localhost:3000"]` | 1 finding, CPO-004, severity HIGH |
| `test_valid_prod_origins` | `cors_allowed_origins = ["https://example.com"]` | 0 findings |
| `test_empty_origins_dev_no_finding` | `environment = "dev"`, `cors_allowed_origins = []` | 0 findings |
| `test_localhost_preprod_no_finding` | `environment = "preprod"`, `cors_allowed_origins = ["http://localhost:3000"]` | 0 findings |
| `test_multiline_origins` | Multi-line list with comments | Parses correctly |
| `test_multiple_findings` | Prod with wildcard + http + localhost | 3 findings |
| `test_no_tfvars_files` | Empty directory | 0 findings |

---

### T4b: Register Validator in Methodology Index

**Repo**: terraform-gsk-template
**Files**:
- `.specify/methodologies/index.yaml` — add entry
- `Makefile` — add `cors-prod-origins-validate` target

**Action**: MODIFY
**Dependencies**: T4
**Estimated effort**: 10 min

Index entry:
```yaml
cors_prod_origins_validation:
  name: "CORS Production Origins Validation"
  description: "Detect empty or insecure CORS origins in production tfvars"
  validator: "src/validators/cors_prod_origins.py"
  class: "CorsProdOriginsValidator"
  verification_gate:
    command: "python -m src.validators.cors_prod_origins"
  validation_gate:
    command: "make cors-prod-origins-validate"
```

Makefile target:
```makefile
cors-prod-origins-validate:
	@echo "Running CORS production origins validator..."
	@python -m src.validators.cors_prod_origins $(REPO_PATH)
```

---

### T4c: Create Slash Command

**Repo**: terraform-gsk-template
**File**: `.claude/commands/cors-prod-origins-validate.md`
**Action**: CREATE
**Dependencies**: T4b
**Estimated effort**: 5 min

Follow existing slash command pattern (e.g., fallback-validate).

---

### T5: E2E Test — CORS Headers via API Gateway

**Repo**: sentiment-analyzer-gsk
**File**: `tests/e2e/test_cors_prod_headers.py`
**Action**: CREATE
**Dependencies**: T1, T2 (prod must be correctly configured)
**Estimated effort**: 20 min

```python
import os
import pytest
import requests
from tests.conftest import SkipInfo

skip = SkipInfo(
    condition=os.getenv("AWS_ENV") != "prod",
    reason="Requires prod deployment",
    remediation="Run with AWS_ENV=prod and PROD_API_GATEWAY_URL set"
)

@pytest.mark.skipif(skip.condition, reason=skip.reason)
class TestCorsProdHeaders:
    """Verify production CORS headers are correctly configured."""

    @pytest.fixture
    def api_url(self):
        return os.environ["PROD_API_GATEWAY_URL"]

    def test_preflight_returns_allowed_origin(self, api_url):
        """OPTIONS preflight returns Access-Control-Allow-Origin for configured origin."""
        response = requests.options(
            f"{api_url}/api/v2/health",
            headers={
                "Origin": "https://traylorre.github.io",
                "Access-Control-Request-Method": "GET",
            }
        )
        assert response.headers.get("Access-Control-Allow-Origin") == "https://traylorre.github.io"

    def test_preflight_rejects_unknown_origin(self, api_url):
        """OPTIONS preflight does NOT return ACAC for unknown origin."""
        response = requests.options(
            f"{api_url}/api/v2/health",
            headers={
                "Origin": "https://evil.com",
                "Access-Control-Request-Method": "GET",
            }
        )
        acac = response.headers.get("Access-Control-Allow-Origin", "")
        assert "evil.com" not in acac

    def test_credentials_header_present(self, api_url):
        """Access-Control-Allow-Credentials is true for configured origin."""
        response = requests.options(
            f"{api_url}/api/v2/health",
            headers={
                "Origin": "https://traylorre.github.io",
                "Access-Control-Request-Method": "GET",
            }
        )
        assert response.headers.get("Access-Control-Allow-Credentials") == "true"
```

**Note**: These tests go through API Gateway (per AR2-FINDING-7), not directly to Function URLs. API Gateway CORS is configured separately (Feature 1253). If API Gateway CORS is not yet configured, these tests will fail — and that is correct behavior (it surfaces another gap).

---

### T6: Playwright Test — Dashboard Loads in Prod

**Repo**: sentiment-analyzer-gsk
**File**: `tests/e2e/playwright/test_prod_cors.spec.ts`
**Action**: CREATE
**Dependencies**: T1 (prod cors must be set), T5 (E2E verifies headers first)
**Estimated effort**: 20 min

```typescript
import { test, expect } from '@playwright/test';

// Skip if prod URL not configured
const PROD_URL = process.env.PROD_AMPLIFY_URL;

test.describe('Production CORS', () => {
  test.skip(!PROD_URL, 'PROD_AMPLIFY_URL not set — skipping prod CORS tests');

  test('dashboard loads without CORS errors', async ({ page }) => {
    const corsErrors: string[] = [];
    page.on('console', msg => {
      if (msg.text().toLowerCase().includes('cors')) {
        corsErrors.push(msg.text());
      }
    });
    page.on('pageerror', error => {
      if (error.message.toLowerCase().includes('cors')) {
        corsErrors.push(error.message);
      }
    });

    await page.goto(PROD_URL!);
    await page.waitForLoadState('networkidle');

    expect(corsErrors).toHaveLength(0);
  });

  test('API calls succeed without CORS blocking', async ({ page }) => {
    const failedRequests: string[] = [];
    page.on('requestfailed', request => {
      if (request.failure()?.errorText?.includes('cors')) {
        failedRequests.push(request.url());
      }
    });

    await page.goto(PROD_URL!);
    await page.waitForLoadState('networkidle');

    expect(failedRequests).toHaveLength(0);
  });
});
```

---

### T7: (OPTIONAL) Terraform Native Test

**Repo**: sentiment-analyzer-gsk
**File**: `infrastructure/terraform/tests/cors_guard.tftest.hcl`
**Action**: CREATE
**Dependencies**: T2
**Estimated effort**: 30 min (may require provider mock setup)
**Priority**: NICE-TO-HAVE (per CQ-4 and AR2-FINDING-6)

This is documented for local verification but NOT a required CI task. The Python validator (T4) is the primary automated gate.

```hcl
# Test that prod with empty CORS origins fails the precondition
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

run "prod_valid_cors_succeeds" {
  command = plan

  variables {
    environment          = "prod"
    cors_allowed_origins = ["https://example.com"]
    aws_region           = "us-east-1"
  }
}

run "dev_empty_cors_allowed" {
  command = plan

  variables {
    environment          = "dev"
    cors_allowed_origins = []
    aws_region           = "us-east-1"
  }
}
```

**Known issue**: This requires all providers to be initialized and many variables have no defaults that work without real AWS context. May need `mock_provider` (Terraform 1.7+).

---

## Cross-Artifact Consistency Analysis

### Spec-to-Plan Alignment

| Spec Requirement | Plan Phase | Task(s) | Status |
|-----------------|-----------|---------|--------|
| FR-1 (populate prod.tfvars) | Phase 1.1 | T1 | ALIGNED |
| FR-2 (hard-fail validation) | Phase 1.2 | T2 | ALIGNED (amended to terraform_data) |
| FR-3 (CI validator) | Phase 2 | T4, T4a, T4b, T4c | ALIGNED |
| FR-4 (multi-layer testing) | Phase 3 | T4a, T3, T5, T6, T7 | ALIGNED |

### AR Finding Resolution

| Finding | Resolution | Task Impact |
|---------|-----------|-------------|
| AR1-1: Precondition placement | terraform_data guard | T2 uses correct approach |
| AR1-3: enable_amplify side effects | Split out (CQ-1) | T1 simplified |
| AR1-4: Terraform test feasibility | Nice-to-have (CQ-4) | T7 is optional |
| AR2-1: Scope creep | enable_amplify removed | T1 simplified |
| AR2-4: Regex robustness | Multi-line DOTALL parsing | T4 handles edge cases |
| AR2-7: API Gateway path | E2E tests via API Gateway | T5 targets correct endpoint |

### Risk Matrix

| Task | Risk | Mitigation |
|------|------|-----------|
| T1 | Low — simple file edit | Verification: grep |
| T2 | Low — standard Terraform pattern | Verification: terraform validate |
| T4 | Medium — regex parsing edge cases | Mitigation: comprehensive unit tests (T4a) |
| T5 | Medium — requires deployed prod | Mitigation: SkipInfo pattern |
| T6 | Medium — requires deployed prod + Amplify | Mitigation: test.skip() |
| T7 | High — provider init complexity | Mitigation: optional, not blocking |

### Implementation Order

1. **Wave 1** (parallel): T1, T2, T4
2. **Wave 2** (depends on T4): T4a, T4b, T4c
3. **Wave 3** (depends on T1+T4): T3
4. **Wave 4** (depends on T1+T2): T5, T6
5. **Wave 5** (optional): T7

---

## Adversarial Review #3

### AR3-FINDING-1: Missing __init__.py Registration

**Problem**: The template repo's `src/validators/__init__.py` exports all validators. T4 creates a new validator but no task explicitly updates `__init__.py` to export `CorsProdOriginsValidator`.

**Resolution**: Add to T4b (register methodology). The `__init__.py` must include:
```python
from .cors_prod_origins import CorsProdOriginsValidator
```

And add to the existing import list in alphabetical order.

### AR3-FINDING-2: T3 Dependency on T1 is Cross-Repo

T3 (integration test in template repo) depends on T1 (prod.tfvars fix in target repo). These are in DIFFERENT repositories. The integration test will fail if run before T1 is merged in the target repo.

**Resolution**: T3's `test_validator_against_sentiment_repo` should use the CURRENT state of the target repo. If prod.tfvars still has `[]`, the test should expect CPO-001 findings (not zero). After T1 lands, the test can be updated. Better approach: make T3 test only with synthetic data (tmp_path) and remove the cross-repo dependency. The existing `test_validator_against_bad_prod_tfvars` test case already covers this.

**Action**: Simplify T3 to use ONLY synthetic data. Remove cross-repo dependency.

### AR3-FINDING-3: Validator __main__ Pattern

The plan says the Makefile target runs `python -m src.validators.cors_prod_origins`. This requires the validator module to have a `__main__` block or be callable as a module. Most existing validators follow this pattern with an `if __name__ == "__main__"` block that calls `run()`.

**Resolution**: Verify T4 includes a `__main__` block. Add to the task description:
```python
if __name__ == "__main__":
    import sys
    from pathlib import Path
    from .utils import detect_repo_type

    repo_path = Path(sys.argv[1]) if len(sys.argv) > 1 else Path.cwd()
    repo_type = detect_repo_type(repo_path)
    validator = CorsProdOriginsValidator()
    result, summary = validator.run(repo_path, repo_type)
    from .output import format_yaml
    print(format_yaml(result))
    sys.exit(1 if summary.critical_count > 0 else 0)
```

### AR3-FINDING-4: Playwright Test CORS Detection is Unreliable

**Problem**: The Playwright test listens for `console` messages containing "cors". But CORS failures in browsers are OPAQUE by spec — the error message says "Failed to fetch" or "NetworkError", not "CORS". The browser does NOT expose CORS error details to JavaScript for security reasons.

**Resolution**: The Playwright test should NOT rely on error message content. Instead:
1. Listen for `requestfailed` events (any failed network request)
2. Check that the page content actually renders (not empty/error state)
3. Verify that API calls return data (not 0 or empty)

Updated test strategy:
```typescript
test('dashboard loads and shows data', async ({ page }) => {
  await page.goto(PROD_URL!);
  // Wait for actual content to render (not just the shell)
  await expect(page.locator('[data-testid="sentiment-data"]')).toBeVisible({ timeout: 10000 });
  // If CORS is blocking, this locator will never appear
});
```

This is a more reliable CORS detection strategy than parsing error messages.

### AR3-FINDING-5: E2E Test — OPTIONS Response May Not Include CORS Headers from API Gateway

API Gateway CORS (Feature 1253) may handle preflight differently than Lambda Function URLs. Specifically:
- Lambda Function URLs: CORS headers are set by AWS automatically based on the `cors` block
- API Gateway: CORS is configured via the integration response or a dedicated CORS configuration

The E2E test sends an OPTIONS request. If API Gateway is configured with a Cognito authorizer, the OPTIONS preflight may be rejected before reaching the CORS layer.

**Resolution**: API Gateway should have CORS configured to handle OPTIONS without authentication (mock integration or `ANY` with no auth). This is Feature 1253's responsibility. The E2E test is correct in its design — if OPTIONS fails, it correctly identifies that CORS is not working, which is the point.

Add a comment in T5 noting this dependency: "If this test fails with 401/403 on OPTIONS, check API Gateway CORS configuration (Feature 1253)."

### AR3-FINDING-6: Total Task Count and Effort Estimate

| Task | Effort | Required? |
|------|--------|-----------|
| T1 | 5 min | YES |
| T2 | 10 min | YES |
| T3 | 15 min | YES (simplified to synthetic only) |
| T4 | 45 min | YES |
| T4a | 30 min | YES |
| T4b | 10 min | YES (now includes __init__.py) |
| T4c | 5 min | YES |
| T5 | 20 min | YES (skip-if-not-deployed) |
| T6 | 20 min | YES (skip-if-not-deployed) |
| T7 | 30 min | NO (optional) |
| **Total** | **~3 hours** | 9 required + 1 optional |

This is reasonable for a feature that spans two repos and includes defense-in-depth at 3 layers.

### Task Amendments from AR#3

1. **T4b EXPANDED**: Must also update `src/validators/__init__.py` with import
2. **T3 SIMPLIFIED**: Remove cross-repo dependency; use only synthetic data
3. **T4 EXPANDED**: Must include `__main__` block for CLI invocation
4. **T6 AMENDED**: Replace CORS error message detection with content-presence assertion
5. **T5 AMENDED**: Add comment about API Gateway CORS dependency (Feature 1253)
