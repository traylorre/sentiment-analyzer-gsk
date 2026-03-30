# Feature 1269: CORS Production Origins

## Status: DRAFT

## Problem Statement

`infrastructure/terraform/prod.tfvars` has `cors_allowed_origins = []` (empty). When deployed to production, both Lambda Function URLs (dashboard and SSE) will compute `allow_origins = []` because the ternary in `main.tf` returns an empty list for prod when no origins are provided. This means **all cross-origin requests from the Amplify frontend will be blocked** — the production dashboard will be non-functional.

A `check` block exists in `main.tf:42-46` that validates this, but Terraform `check` blocks are **warning-only** — they do not fail `terraform plan` or `terraform apply`. The safeguard is insufficient.

## Root Cause Analysis

Three compounding gaps:

1. **Data gap**: `prod.tfvars` was templated with an empty list placeholder and never populated with the actual Amplify domain. The comment says "set before deploying" but there is no enforcement.
2. **Enforcement gap**: The Terraform `check` block only emits a warning. A production deploy with empty CORS origins would succeed, creating a silently broken frontend.
3. **Detection gap**: No CI validator exists to catch empty `cors_allowed_origins` for prod environments before the code reaches `terraform plan`.

## Scope

### In Scope

- **IS-1**: Populate `prod.tfvars` with production Amplify domain(s)
- **IS-2**: Upgrade Terraform validation from `check` (warning) to `precondition` or variable `validation` (hard failure)
- **IS-3**: Create a CI validator (Python, in template validator pattern) that statically catches empty `cors_allowed_origins` in prod tfvars
- **IS-4**: Tests at every layer: unit, integration, E2E, Playwright

### Out of Scope

- Changing the CORS header values themselves (allow_headers, allow_methods, etc.)
- Modifying the dev or preprod tfvars files
- Changing the Amplify module or its outputs
- Custom domain configuration (separate feature)
- API Gateway CORS configuration (handled by Feature 1253/1114)

## Requirements

### FR-1: Populate Production CORS Origins

`prod.tfvars` must contain the production Amplify domain in `cors_allowed_origins`. The domain follows the pattern `https://main.<app-id>.amplifyapp.com`. Since prod Amplify is not yet deployed (`enable_amplify` is not set in prod.tfvars), the value must be set as a placeholder with a clear pattern, OR `enable_amplify = true` must be added with the corresponding `amplify_github_repository`.

**Decision**: Since preprod uses `https://main.d29tlmksqcx494.amplifyapp.com`, and prod will get its own Amplify app ID after first deploy, we will:
- Add `enable_amplify = true` and `amplify_github_repository` to prod.tfvars
- Set `cors_allowed_origins` to include the GitHub Pages domain (known) as a baseline
- Add a `# TODO: Add Amplify production URL after first deploy` comment
- The Terraform validation will catch the case where `enable_amplify = true` but no amplifyapp.com domain is in `cors_allowed_origins`

**Revised decision**: Actually, the safer approach is to NOT try to guess the Amplify URL. Instead:
- Set `cors_allowed_origins = ["https://traylorre.github.io"]` for the known GitHub Pages origin
- Add `enable_amplify = true` and `amplify_github_repository` to prod.tfvars
- Document that the Amplify URL must be added to cors_allowed_origins after first deploy
- The hard-failure validation ensures the list is non-empty for prod (preventing the total-blackout scenario)
- A separate Terraform `check` can warn when `enable_amplify = true` but no `.amplifyapp.com` domain is in the list

### FR-2: Hard-Failure Terraform Validation

Replace or supplement the existing `check` block with a validation that **fails** `terraform plan`:

**Option A**: Variable `validation` block on `cors_allowed_origins`
- Pro: Fails at variable validation time (earliest possible)
- Con: Variable validation cannot reference other variables (`var.environment`), only the variable's own value

**Option B**: `precondition` on a resource (e.g., the dashboard Lambda Function URL)
- Pro: Can reference `var.environment` and `var.cors_allowed_origins` together
- Con: Only fires during plan/apply of that specific resource

**Option C**: `locals` block with a validation using `terraform_data`
- Pro: Always evaluates during plan
- Con: Creates a dummy resource

**Decision**: Use Option B — add `precondition` blocks to both Lambda Function URL CORS configurations (dashboard and SSE). These are the exact resources that would be misconfigured, making the precondition semantically precise. Keep the existing `check` block as an additional warning layer.

### FR-3: CI Validator

Create `src/validators/cors_prod_origins.py` (in the template repo) that:
- Scans `*.tfvars` files for `environment = "prod"`
- In those files, checks that `cors_allowed_origins` is non-empty
- Validates no wildcard `*` in origins (reinforcing existing variable validation)
- Validates all origins use `https://` (not `http://`) for prod
- Reports findings with severity HIGH

### FR-4: Multi-Layer Testing

| Layer | What | How |
|-------|------|-----|
| Unit | Terraform precondition fails when prod + empty origins | `terraform plan` with test tfvars (empty origins + env=prod) should fail |
| Unit | CI validator detects empty origins in prod.tfvars | Python unit test with synthetic tfvars content |
| Integration | CI validator runs against real repo tfvars | Run validator against sentiment-analyzer-gsk repo |
| E2E | Production CORS headers are correct | HTTP request to prod Function URL, verify Access-Control-Allow-Origin |
| Playwright | Customer dashboard loads in prod | Playwright test against prod Amplify URL, verify no CORS errors |

## Technical Design

### prod.tfvars Changes

```hcl
# CORS: Production requires explicit origins - NO WILDCARDS
cors_allowed_origins = [
  "https://traylorre.github.io",  # GitHub Pages interview demo
  # TODO(1269): Add Amplify production URL after first deploy
  # Get it from: terraform output amplify_production_url
  # Format: "https://main.<app-id>.amplifyapp.com"
]

# Feature 1105: AWS Amplify SSR Frontend
enable_amplify            = true
amplify_github_repository = "https://github.com/traylorre/sentiment-analyzer-gsk"
```

### main.tf Precondition (Dashboard Lambda)

```hcl
function_url_cors = {
  allow_credentials = true
  allow_headers     = [...]
  allow_methods     = [...]
  allow_origins = length(var.cors_allowed_origins) > 0 ? var.cors_allowed_origins : (
    var.environment != "prod" ? ["http://localhost:3000", "http://localhost:8080"] : []
  )
  ...
}

# Add precondition to the module block or a lifecycle block
precondition {
  condition     = var.environment != "prod" || length(var.cors_allowed_origins) > 0
  error_message = "FATAL: cors_allowed_origins cannot be empty for production. Set explicit origins in prod.tfvars."
}
```

### Validator Pattern

```python
class CorsProdOriginsValidator(BaseValidator):
    name = "cors-prod-origins-validate"
    description = "Detect empty or insecure CORS origins in production tfvars"

    RULES = [
        "CPO-001: Empty cors_allowed_origins in prod tfvars",
        "CPO-002: Wildcard origin in prod tfvars",
        "CPO-003: HTTP (non-HTTPS) origin in prod tfvars",
        "CPO-004: Localhost origin in prod tfvars",
    ]
```

## Dependencies

- Feature 1267 (cors-wildcard-fix): Must land first — fixes the existing wildcard/credentials incompatibility
- Feature 1105 (Amplify SSR): prod.tfvars will reference Amplify configuration

## Risks

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| Amplify app ID unknown until first deploy | HIGH | MEDIUM | Use GitHub Pages as baseline origin; add Amplify URL post-deploy |
| Precondition placement in module | MEDIUM | LOW | Verify terraform-aws-modules/lambda supports lifecycle preconditions |
| Prod deploy blocked by empty origins | LOW | LOW | This is the desired behavior — forces explicit configuration |

## Open Questions

- **OQ-1**: Can `precondition` be placed inside the `function_url_cors` map, or does it need to be at the module level? **Self-resolved**: Preconditions go on `resource` or `data` blocks, not inside maps. Since we use a module (`module.dashboard_lambda`), we need either a `precondition` on a `terraform_data` resource or a variable validation that cross-references. The cleanest approach is a `terraform_data` resource with a `precondition` lifecycle block.
- **OQ-2**: E2E and Playwright tests against prod are only meaningful after prod is deployed. Should these be marked as skip-if-not-deployed? **Self-resolved**: Yes, use `SkipInfo` pattern with environment detection.
- **OQ-3**: Should the validator live in the template repo or the target repo? **Self-resolved**: Template repo (consistent with all other validators), then available to all dependent repos via the validation framework.

---

## Adversarial Review #1

### AR1-FINDING-1: Precondition Placement is Architecturally Wrong (CRITICAL)

**Problem**: The spec proposes adding `precondition` blocks to the Lambda Function URL CORS configurations. However, the `aws_lambda_function_url` resource lives INSIDE `modules/lambda/main.tf` (line 136), not in the root `main.tf`. The root `main.tf` only passes `function_url_cors` as a variable to the module. You cannot add a `precondition` to a resource inside a module from outside.

**Options**:
1. Add `precondition` inside the lambda module's `aws_lambda_function_url` resource — but this makes the module opinionated about CORS policy, which is wrong for a reusable module.
2. Use a `terraform_data` resource in root `main.tf` with a `lifecycle { precondition {} }` — clean, always evaluates, semantically clear.
3. Use a `null_resource` with a `lifecycle { precondition {} }` — similar but `terraform_data` is the modern replacement.

**Resolution**: Use Option 2. Create a `terraform_data.cors_production_guard` resource in root `main.tf` with a precondition. This fires during every plan, references both `var.environment` and `var.cors_allowed_origins`, and fails the plan if the condition is violated. The existing `check` block stays as a secondary warning.

**Spec update required**: FR-2 decision must change from "add precondition to module" to "add terraform_data guard resource".

### AR1-FINDING-2: Variable Validation Cannot Cross-Reference (Confirmed)

The spec correctly identifies that variable `validation` blocks cannot reference other variables. This means we cannot do `condition = var.environment != "prod" || length(self) > 0` in the `cors_allowed_origins` variable block. The `terraform_data` approach resolves this.

### AR1-FINDING-3: enable_amplify in prod.tfvars Has Infrastructure Side Effects

**Problem**: Adding `enable_amplify = true` to prod.tfvars will trigger creation of an entire Amplify app, IAM service role, and Cognito callback patching. This is a significant infrastructure change that goes beyond the CORS fix scope.

**Resolution**: Keep `enable_amplify` addition but document it clearly in the plan as a deliberate infrastructure expansion. It IS required for prod to have a frontend at all. However, it requires `amplify_github_repository` and a pre-provisioned GitHub token in Secrets Manager (`prod/amplify/github-token`). The plan must include a pre-flight check for the Secrets Manager token.

### AR1-FINDING-4: Terraform Plan Test Feasibility (OPEN QUESTION)

The spec says "unit test: terraform plan with test tfvars should fail". Running `terraform plan` requires:
- Terraform binary installed
- AWS credentials (even for plan with some providers)
- All providers initialized
- State file access

This is not a unit test; it is an integration test at minimum. For a true unit test of the Terraform validation logic, we would need to either:
1. Use `terraform validate` (which checks syntax and variable validation but NOT preconditions)
2. Use a Terraform testing framework (e.g., `terraform test` with `.tftest.hcl` files)
3. Accept this as an integration-level test

**Resolution**: Use Terraform's native `terraform test` command (available since Terraform 1.6) with a `.tftest.hcl` file. This can run `plan` in a test harness without actually applying. Mark it as integration-level in the test taxonomy. If `terraform test` is not available in CI, fall back to the Python CI validator as the primary gate.

### AR1-FINDING-5: GitHub Pages Origin May Be Stale

**Problem**: `https://traylorre.github.io` is in preprod cors_allowed_origins. Adding it to prod is fine, but if GitHub Pages is not actively serving content, it is dead configuration.

**Resolution**: This is acceptable. It is a valid, known origin and costs nothing. It provides a working prod CORS configuration immediately while Amplify URL is pending.

### AR1-FINDING-6: HTTPS-Only Validation Edge Case

The validator rule CPO-003 flags HTTP origins in prod. But the existing dev.tfvars has `http://localhost:3000`. The validator must be scoped to prod-only files to avoid false positives on dev/preprod configs that legitimately use HTTP for local development.

**Resolution**: Validator already scans only files where `environment = "prod"`. No change needed, but add an explicit test case for this edge case.

### AR1-FINDING-7: Two Lambda Function URLs, One CORS Config Variable

Both the dashboard Lambda (main.tf:446-459) and SSE Lambda (main.tf:774-783) use the same `var.cors_allowed_origins` for their `allow_origins`. A single `terraform_data` guard protects both simultaneously. No need for two separate guards.

### Spec Amendments from AR#1

**FR-2 AMENDED**: Replace "precondition on module" with "terraform_data guard resource in root main.tf":

```hcl
resource "terraform_data" "cors_production_guard" {
  lifecycle {
    precondition {
      condition     = var.environment != "prod" || length(var.cors_allowed_origins) > 0
      error_message = "FATAL: cors_allowed_origins cannot be empty for production. Set explicit origins in prod.tfvars."
    }
  }
}
```

**FR-1 AMENDED**: Adding `enable_amplify = true` to prod.tfvars requires:
- Pre-provisioned GitHub token at `prod/amplify/github-token` in Secrets Manager
- If token does not exist, the Terraform plan will fail on the Amplify module
- This is an intentional infrastructure expansion, not just a CORS fix

**FR-4 AMENDED**: "Terraform unit test" reclassified to integration test using `terraform test` or Python-based tfvars parsing. True unit tests limited to the Python CI validator.

---

## Clarification (Stage 4)

### CQ-1: Should enable_amplify be part of this feature or split out?

**Self-resolved**: Enabling Amplify in prod is a prerequisite for having a frontend that needs CORS. However, it introduces significant infrastructure (Amplify app, IAM role, Secrets Manager dependency, Cognito callback patching).

**Decision**: SPLIT. This feature (1269) focuses on the CORS safety net:
- Populate `cors_allowed_origins` with `["https://traylorre.github.io"]` (known, safe)
- Add `terraform_data` guard (hard-fail on empty)
- Add HTTPS-only check
- Create CI validator
- Do NOT add `enable_amplify = true` to prod.tfvars (separate feature scope)

Rationale: The core problem is "empty CORS list silently deployed to prod." The fix is "make it non-empty and make it impossible to be empty." Amplify enablement is orthogonal infrastructure expansion.

### CQ-2: What if prod.tfvars cors_allowed_origins has origins but none match the actual frontend URL?

The `terraform_data` guard only checks non-empty. It does NOT verify that the listed origins match the actual Amplify URL. This is intentional — the guard prevents the catastrophic case (zero origins). Verifying correct origins requires runtime E2E testing.

**Decision**: Add a second `check` block (warning-only) that, when `enable_amplify = true`, warns if no `.amplifyapp.com` domain appears in `cors_allowed_origins`. This is an advisory, not a blocker.

### CQ-3: terraform_data.cors_production_guard ordering and dependencies

The `terraform_data` resource has no dependencies and no triggers. It evaluates its precondition during every plan. It does NOT need `depends_on` because it only reads variables, not resource outputs.

**Confirmed**: No ordering issues. The precondition evaluates at plan time before any resource creation.

### CQ-4: Terraform test (.tftest.hcl) feasibility in CI

`terraform test` requires:
- Terraform 1.6+ (check CI version)
- Provider initialization (but test can use `mock_provider` in Terraform 1.7+)
- For precondition testing: actual `plan` command execution

**Decision**: The `.tftest.hcl` file is a NICE-TO-HAVE, not a requirement. Primary automated gate is the Python CI validator. The Terraform test is documented for local verification. If the CI Terraform version supports it, integrate it later.

### CQ-5: Validator tfvars parsing strategy

HCL tfvars files have a simple format: `key = value`. For this validator, we need:
- `environment = "prod"` detection
- `cors_allowed_origins = [...]` list extraction

Regex is sufficient for this. The list can span multiple lines. Strategy:
1. Read entire file
2. Regex match `environment\s*=\s*"(\w+)"` to get environment
3. Regex match `cors_allowed_origins\s*=\s*\[(.*?)\]` (with DOTALL) to get the list content
4. If list content is empty or whitespace/comments only, flag CPO-001
5. Extract individual strings with `"([^"]+)"` regex within the list content
6. Check each string against CPO-002, CPO-003, CPO-004 rules

This avoids any HCL parser dependency.
