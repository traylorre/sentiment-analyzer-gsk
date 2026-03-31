# Terraform Dependency Cycle Fix — Strategy 4 Analysis

## Understanding Statement (Corrected)

The dependency cycle is a 5-module chain through **Lambda environment variables**, not CORS headers:

- `notification_lambda.DASHBOARD_URL` → needs `amplify_frontend.production_url`
- `amplify_frontend.api_gateway_url` → needs `api_gateway.api_endpoint`
- `api_gateway.lambda_invoke_arn` → needs `dashboard_lambda.invoke_arn`
- `dashboard_lambda.SCHEDULER_ROLE_ARN` → needs `chaos.chaos_scheduler_role_arn`
- `chaos.lambda_arns` → needs `notification_lambda.function_arn`

Strategy 4 (Split Definition + Wiring) breaks this by creating Lambda modules with placeholder environment variables, then populating cross-module values via separate Terraform resources after all modules exist.

**Principle**: One resource owns the Lambda's existence (definition). Another resource owns the env var values that cross module boundaries (wiring). The definition resource uses `lifecycle { ignore_changes = [environment] }` so the wiring resource is the sole owner of those values.

---

## Dependency Graph — Current (Broken)

```
┌─────────────────────┐
│  amplify_frontend    │
│  (Amplify Hosting)   │◄────────────────────────────────────────┐
└──────────┬──────────┘                                          │
           │ api_gateway_url = module.api_gateway.api_endpoint   │
           │ dashboard_lambda_url = module.dashboard_lambda.url  │
           ▼                                                     │
┌─────────────────────┐                                          │
│  api_gateway         │                                          │
│  (REST API + CORS)   │                                          │
└──────────┬──────────┘                                          │
           │ lambda_invoke_arn = module.dashboard_lambda.arn      │
           ▼                                                     │
┌─────────────────────┐                                          │
│  dashboard_lambda    │                                          │
│  (Main API handler)  │                                          │
└──────────┬──────────┘                                          │
           │ SCHEDULER_ROLE_ARN = try(module.chaos.role, "")     │
           ▼                                                     │
┌─────────────────────┐                                          │
│  chaos               │                                          │
│  (FIS experiments)   │                                          │
└──────────┬──────────┘                                          │
           │ lambda_arns = [... module.notification_lambda.arn]   │
           ▼                                                     │
┌─────────────────────┐                                          │
│  notification_lambda │                                          │
│  (Email alerts)      │──────────────────────────────────────────┘
└─────────────────────┘  DASHBOARD_URL = module.amplify[0].url
                         depends_on = [module.amplify_frontend]

RESULT: Terraform Cycle Error — cannot determine creation order
```

### Edge Classification

| From | To | Via | Type | Breakable? |
|------|----|-----|------|-----------|
| amplify_frontend | api_gateway | `api_gateway_url` input | **HARD** | No — Amplify needs the API URL to function |
| api_gateway | dashboard_lambda | `lambda_invoke_arn` input | **HARD** | No — API Gateway integration requires Lambda ARN |
| dashboard_lambda | chaos | `SCHEDULER_ROLE_ARN` env var | **SOFT** | Yes — Lambda works without it, just can't auto-restore |
| chaos | notification_lambda | `lambda_arns` list | **HARD** | No — FIS experiment templates need target ARNs |
| notification_lambda | amplify_frontend | `DASHBOARD_URL` env var | **SOFT** | Yes — Lambda works without it, emails just have wrong links |

**Two breakable edges**: dashboard_lambda → chaos, notification_lambda → amplify_frontend.
**Strategy 4 breaks BOTH** by deferring env var population.

---

## Dependency Graph — With Strategy 4 (Fixed)

```
PHASE 1: DEFINITION (all modules created with placeholder env vars)
═══════════════════════════════════════════════════════════════════

┌─────────────────────┐      ┌─────────────────────┐
│  dashboard_lambda    │      │  notification_lambda │
│  SCHEDULER_ROLE=     │      │  DASHBOARD_URL=      │
│  "" (placeholder)    │      │  "" (placeholder)    │
│                      │      │                      │
│  ignore_changes =    │      │  ignore_changes =    │
│  [environment]       │      │  [environment]       │
└──────────┬──────────┘      └──────────┬──────────┘
           │                            │
           ▼                            ▼
┌─────────────────────┐      ┌─────────────────────┐
│  api_gateway         │      │  chaos               │
│  invoke_arn = ✓      │      │  lambda_arns = ✓     │
│  (dashboard exists)  │      │  (both lambdas exist)│
└──────────┬──────────┘      └─────────────────────┘
           │
           ▼
┌─────────────────────┐
│  amplify_frontend    │
│  api_gateway_url = ✓ │
│  (API Gateway exists)│
└─────────────────────┘

No cycle — all HARD dependencies satisfied. Lambdas exist with placeholders.


PHASE 2: WIRING (cross-module env vars populated)
═══════════════════════════════════════════════════

┌─────────────────────────────────────────────────────────────┐
│  terraform_data "dashboard_lambda_wiring"                    │
│                                                              │
│  triggers = {                                                │
│    scheduler_role = module.chaos.chaos_scheduler_role_arn     │
│  }                                                           │
│                                                              │
│  provisioner "local-exec" {                                  │
│    command = "aws lambda update-function-configuration        │
│      --function-name ${module.dashboard_lambda.function_name} │
│      --environment Variables={SCHEDULER_ROLE_ARN=...}"        │
│  }                                                           │
│                                                              │
│  depends_on = [module.dashboard_lambda, module.chaos]         │
└─────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────┐
│  terraform_data "notification_lambda_wiring"                     │
│                                                                  │
│  triggers = {                                                    │
│    dashboard_url = module.amplify_frontend[0].production_url     │
│  }                                                               │
│                                                                  │
│  provisioner "local-exec" {                                      │
│    command = "aws lambda update-function-configuration            │
│      --function-name ${module.notification_lambda.function_name}  │
│      --environment Variables={DASHBOARD_URL=...}"                 │
│  }                                                               │
│                                                                  │
│  depends_on = [module.notification_lambda, module.amplify_frontend]│
└─────────────────────────────────────────────────────────────────┘

RESULT: Terraform creates all resources in Phase 1, patches env vars in Phase 2.
        Single `terraform apply`. No manual intervention.
```

### Dependency Hazards Without This Fix

| Hazard | Modules | Edge | Status |
|--------|---------|------|--------|
| **Primary cycle** | amplify → api_gw → dashboard → chaos → notification → amplify | 5 SOFT+HARD edges | **BLOCKED — Terraform refuses to plan** |
| **Cognito ↔ Amplify** | amplify needs cognito creds, cognito needs amplify callback URL | Bidirectional | **SOLVED** — terraform_data patch (line 1294) |
| **Chaos ↔ Dashboard** | chaos needs lambda_arns, dashboard needs scheduler_role | Bidirectional | **BLOCKED** — part of primary cycle |
| **Notification ↔ Amplify** | notification needs production_url, amplify needs notification (indirect) | Through chaos | **BLOCKED** — part of primary cycle |
| **Latent hazard**: SSE Lambda | If SSE ever needs an api_gateway output | Not yet connected | **SAFE** — SSE → CloudFront → API Gateway is unidirectional |

---

## Timing Constraints

### Execution Sequence (single `terraform apply`)

```
T0: Terraform starts plan
    ├── All modules resolve inputs from variables/tfvars (no cross-module env vars)
    ├── HARD dependencies determine creation order:
    │   IAM → ECR → dashboard_lambda → api_gateway → amplify_frontend
    │   IAM → notification_lambda → chaos
    └── No cycle — plan succeeds

T1: IAM roles + ECR repos created
    └── Foundation resources, no external dependencies

T2: Lambda functions created (dashboard, notification, SSE, etc.)
    ├── dashboard_lambda: SCHEDULER_ROLE_ARN = "" (placeholder)
    ├── notification_lambda: DASHBOARD_URL = "" (placeholder)
    ├── Function URLs assigned by AWS (takes 1-3 seconds)
    └── All Lambda ARNs now available

T3: API Gateway created
    ├── Uses dashboard_lambda.invoke_arn (available from T2)
    ├── Gateway responses, routes, integrations created
    └── api_endpoint URL now available

T4: Chaos module created
    ├── Uses lambda_arns from T2 (all available)
    ├── FIS templates, roles created
    └── chaos_scheduler_role_arn now available

T5: Amplify Frontend created
    ├── Uses api_gateway.api_endpoint from T3
    ├── Uses dashboard_lambda.function_url from T2
    ├── Amplify app + branch created
    └── production_url now available

T6: terraform_data "dashboard_lambda_wiring" executes
    ├── depends_on: dashboard_lambda (T2) + chaos (T4) — both exist
    ├── aws lambda update-function-configuration
    │   --environment Variables={..., SCHEDULER_ROLE_ARN=<actual value>, ...}
    └── Lambda updated in-place (no downtime, no new version)

T7: terraform_data "notification_lambda_wiring" executes
    ├── depends_on: notification_lambda (T2) + amplify_frontend (T5) — both exist
    ├── aws lambda update-function-configuration
    │   --environment Variables={..., DASHBOARD_URL=<actual value>, ...}
    └── Lambda updated in-place

T8: terraform_data "cognito_callback_patch" executes (existing)
    ├── depends_on: cognito + amplify_frontend — both exist
    └── aws cognito-idp update-user-pool-client --callback-urls <amplify URL>

T9: Terraform apply completes
    └── All resources created and wired
```

### Critical Timing Windows

| Window | Duration | State | Impact |
|--------|----------|-------|--------|
| T2 → T6 | ~30-60s | dashboard_lambda has SCHEDULER_ROLE_ARN="" | Chaos auto-restore won't trigger. Manual chaos stop still works. |
| T2 → T7 | ~60-90s | notification_lambda has DASHBOARD_URL="" | Email links would point to empty string. No emails sent during apply. |
| T2 → T5 | ~30-60s | Amplify not yet created | Frontend not accessible. No user traffic. |

**All timing windows are during `terraform apply` when the infrastructure is being created/updated. No user traffic flows during this period.**

---

## Race Condition Analysis — Proof of Safety

### Claim: No race conditions can occur with Strategy 4.

**Proof by exhaustive enumeration:**

### RC-1: Lambda invoked during env var update (T6/T7)

**Scenario**: A request arrives at dashboard_lambda exactly when `aws lambda update-function-configuration` is executing.

**Analysis**: AWS Lambda's `update-function-configuration` is atomic. The Lambda runtime sees either the OLD configuration or the NEW configuration, never a partial update. The AWS API returns `LastUpdateStatus: InProgress` during the update and `Successful` after. Requests in flight use the existing environment. New cold starts after the update use the new environment.

**Verdict**: **NOT A RACE CONDITION.** AWS Lambda env var updates are atomic.

### RC-2: Amplify build triggers before wiring completes

**Scenario**: Amplify starts building the frontend (T5) before notification_lambda is wired (T7).

**Analysis**: Amplify build uses NEXT_PUBLIC_* env vars baked into the build. These come from the Amplify module inputs (api_gateway_url, cognito_*, etc.), NOT from notification_lambda's DASHBOARD_URL. The notification lambda wiring is invisible to Amplify.

**Verdict**: **NOT A RACE CONDITION.** Amplify and notification_lambda wiring are independent.

### RC-3: Chaos experiment starts during dashboard_lambda wiring (T6)

**Scenario**: Someone starts a chaos experiment before SCHEDULER_ROLE_ARN is populated.

**Analysis**:
1. During `terraform apply`, chaos module is created at T4 but chaos experiments are created via API calls, not Terraform. No one is calling the API during apply.
2. Even if someone did: SCHEDULER_ROLE_ARN="" means `arn = os.environ.get("SCHEDULER_ROLE_ARN", "")` returns empty string. The auto-restore scheduler creation would fail with an invalid ARN, but the experiment itself would still start and stop. Manual stop always works.
3. After T6, the env var is populated and auto-restore works normally.

**Verdict**: **NOT A RACE CONDITION.** The timing window (T4→T6) has no user traffic. Even if it did, failure is graceful (auto-restore disabled, manual stop works).

### RC-4: terraform_data provisioner fails mid-execution

**Scenario**: `aws lambda update-function-configuration` fails at T6 (e.g., throttled, transient error).

**Analysis**: This is NOT a race condition — it's a failure case (see Failure Cases below). The Lambda continues running with placeholder env vars. Next `terraform apply` retries the provisioner because `triggers` haven't changed (the chaos output is the same).

**Verdict**: **NOT A RACE CONDITION.** Provisioner failure is idempotent and retryable.

### RC-5: Two concurrent `terraform apply` runs

**Scenario**: CI runs `terraform apply` while another is in progress.

**Analysis**: Terraform state locking (DynamoDB lock table) prevents concurrent applies. The second apply waits or fails with a lock error.

**Verdict**: **NOT A RACE CONDITION.** State locking prevents concurrency.

### RC-6: Lambda cold start between T2 and T6

**Scenario**: Lambda cold-starts with SCHEDULER_ROLE_ARN="" before wiring.

**Analysis**: This can only happen if something invokes the Lambda during apply. API Gateway is created at T3 but the stage deployment happens atomically — there's no window where the API is "partially live." Even if invoked, the Lambda handles SCHEDULER_ROLE_ARN="" gracefully (see RC-3).

**Verdict**: **NOT A RACE CONDITION.** No traffic path exists during apply.

**Conclusion: Zero race conditions.** All timing windows occur during `terraform apply` when no user traffic flows. AWS Lambda env var updates are atomic. Terraform state locking prevents concurrent applies.

---

## Failure Cases

### F-1: Provisioner fails — `aws lambda update-function-configuration` returns error

| Aspect | Detail |
|--------|--------|
| **Cause** | AWS throttling, IAM permission missing, Lambda UpdateFunctionConfiguration denied |
| **State after** | Lambda exists with placeholder env vars. terraform_data marked as failed in state. |
| **User impact** | dashboard_lambda: chaos auto-restore disabled. notification_lambda: email links empty. |
| **Detection** | `terraform apply` exits with error. CI pipeline fails at deploy step. |
| **Recovery** | Fix root cause (IAM, throttle), re-run `terraform apply`. Provisioner retries. |
| **Severity** | **MEDIUM** — functionality degraded but core service works |

### F-2: Provisioner succeeds but sets wrong env vars

| Aspect | Detail |
|--------|--------|
| **Cause** | Bug in the local-exec command (typo in env var name, wrong JSON escaping) |
| **State after** | Lambda has corrupted env vars. Terraform thinks wiring succeeded. |
| **User impact** | Runtime errors when Lambda tries to use the env var value |
| **Detection** | Canary tests or health checks fail. CloudWatch errors spike. |
| **Recovery** | Fix the provisioner command, `terraform taint terraform_data.dashboard_lambda_wiring`, re-apply. |
| **Severity** | **HIGH** — silent corruption, detected only at runtime |

### F-3: `ignore_changes` causes drift — manual env var change overwritten by wiring

| Aspect | Detail |
|--------|--------|
| **Cause** | Someone manually updates Lambda env vars via console. Next `terraform apply` doesn't detect the change (ignore_changes). But the wiring provisioner runs and overwrites with Terraform values. |
| **State after** | Manual change lost. |
| **User impact** | Depends on what was changed. Could break custom debugging env vars. |
| **Detection** | None — silent overwrite on next apply. |
| **Recovery** | Don't manually edit env vars on these Lambdas. Document this constraint. |
| **Severity** | **LOW** — operational discipline issue, not a system failure |

### F-4: Lambda function updated by CI between T2 and T6 (env vars overwritten)

| Aspect | Detail |
|--------|--------|
| **Cause** | CI deploys a new Lambda image (docker push + update-function-code) while terraform apply is still running. The CI pipeline's force-image-update step sets env vars to the Docker image defaults. |
| **State after** | Wiring provisioner may overwrite CI's env vars, or CI may overwrite wiring's env vars — last writer wins. |
| **User impact** | Env vars may be stale or mixed between Terraform and CI versions. |
| **Detection** | Deployment health checks or E2E tests fail. |
| **Recovery** | Re-run `terraform apply` to re-trigger wiring provisioners. |
| **Severity** | **LOW** — only during deploy, CI and Terraform don't run simultaneously (deploy pipeline is sequential) |

### F-5: Amplify not created (enable_amplify = false) — notification_lambda wiring skips

| Aspect | Detail |
|--------|--------|
| **Cause** | `enable_amplify = false` in tfvars. Amplify module has `count = 0`. |
| **State after** | `module.amplify_frontend[0].production_url` doesn't exist. Wiring resource must handle this with `count` or `try()`. |
| **User impact** | notification_lambda.DASHBOARD_URL stays as placeholder ("http://localhost:3000" fallback). Emails have localhost links. |
| **Detection** | Test emails show localhost URLs in preprod/prod. |
| **Recovery** | Set `enable_amplify = true`, re-apply. |
| **Severity** | **LOW** — expected behavior when Amplify is disabled |

### F-6: CORS remains broken — Gateway responds with wrong origin

| Aspect | Detail |
|--------|--------|
| **Cause** | Strategy 4 addresses the CYCLE but doesn't add the Amplify URL to `cors_allowed_origins`. The gateway response uses `method.request.header.origin` (echo), which works regardless of tfvars. BUT Lambda Function URL CORS (lines 476-489) only allows origins from `var.cors_allowed_origins`. |
| **State after** | API Gateway CORS works (origin echoing). Lambda Function URL CORS may reject if Amplify URL not in tfvars. |
| **User impact** | **Browser requests via Lambda Function URL blocked.** Requests via API Gateway work. If all traffic routes through API Gateway (Feature 1253), this is a non-issue. If any traffic hits Lambda Function URL directly, CORS fails. |
| **Detection** | Playwright CORS tests (cors-headers.spec.ts, cors-prod.spec.ts). |
| **Recovery** | Add Amplify URL to `cors_allowed_origins` in tfvars. |
| **Severity** | **MEDIUM** — depends on traffic routing. Currently all traffic goes through API Gateway, so this is latent. |

### F-7: `terraform destroy` leaves patched values — orphaned Lambda config

| Aspect | Detail |
|--------|--------|
| **Cause** | `terraform destroy` removes terraform_data resources but the Lambda env vars were set by local-exec, not by Terraform state. Destroy removes the Lambda itself, so this is moot. |
| **State after** | Clean — Lambda is destroyed along with its env vars. |
| **User impact** | None. |
| **Severity** | **NONE** — destroy is complete |

---

## Playwright Test Mapping

### Legend
- ✅ = Fully covered by existing test
- ⚠️ = Partially covered (test exists but doesn't assert this specific failure mode)
- ❌ = No coverage

### Failure Cases → Test Coverage

| Failure Case | Relevant Test | Coverage | Gap |
|---|---|---|---|
| **F-1**: Provisioner fails, placeholder env vars | No test | ❌ | Need test: "service degrades gracefully when SCHEDULER_ROLE_ARN is empty" |
| **F-2**: Wrong env vars set | No test | ❌ | Need test: "chaos auto-restore triggers when experiment exceeds duration" (validates SCHEDULER_ROLE_ARN works) |
| **F-3**: Manual env var drift | N/A (operational) | N/A | Not testable via Playwright — operational runbook item |
| **F-4**: CI/Terraform race on env vars | No test | ❌ | Not testable via Playwright — CI pipeline ordering issue |
| **F-5**: Amplify disabled, email links wrong | No test | ❌ | Need test: "notification email contains valid dashboard URL" (requires email capture) |
| **F-6**: CORS broken on Function URL | cors-headers.spec.ts | ⚠️ | Existing test hits `/health` but doesn't test Lambda Function URL directly (goes through API Gateway) |
| **F-7**: Terraform destroy cleanup | N/A | N/A | Not testable — infrastructure lifecycle |

### Edge Cases → Test Coverage

| Edge Case | Relevant Test | Coverage | Gap |
|---|---|---|---|
| Browser request during CORS misconfiguration | cors-headers.spec.ts test 1 | ✅ | Credentialed fetch to API, asserts no CORS error |
| Browser request blocked by CORS | cors-prod.spec.ts test 1 | ✅ | Captures `requestfailed` events, asserts zero |
| 401 response with CORS headers | error-visibility-auth.spec.ts test 3 | ✅ | Routes `/auth/refresh` to 401, reads body |
| 403 response with CORS headers | No test | ❌ | Need test: "403 response body readable (CORS headers present)" |
| 404 response with CORS headers | cors-env-gated-404.spec.ts | ⚠️ | Uses `page.route()` mock, not real API Gateway 404 |
| API Gateway timeout (504) | No test | ❌ | Need test: "504 gateway timeout returns CORS headers" |
| SSE connection during CORS failure | chaos-sse-lifecycle.spec.ts | ⚠️ | Tests SSE reconnection but doesn't test CORS-blocked SSE |
| Health banner during CORS outage | chaos-degradation.spec.ts test 1 | ⚠️ | Tests banner on 503 but not on CORS block (different failure mode) |
| Empty SCHEDULER_ROLE_ARN at runtime | chaos.spec.ts lifecycle tests | ⚠️ | Tests experiment lifecycle but doesn't test auto-restore scheduling |
| Email with empty DASHBOARD_URL | No test | ❌ | Need test: email link validation (requires MailSlurp or similar) |
| API recovery after CORS fix deploy | cors-prod.spec.ts test 3 | ✅ | Verifies API fetch succeeds from page context |
| Cross-origin preflight (OPTIONS) | No explicit test | ❌ | Need test: "OPTIONS preflight returns correct CORS headers" |
| Credential-mode fetch to non-matching origin | No test | ❌ | Need test: "fetch with credentials to wrong origin fails predictably" |

### Summary: Test Gaps to Address

| Priority | Gap | Recommended Test |
|----------|-----|-----------------|
| **P0** | OPTIONS preflight not tested | New: `cors-preflight.spec.ts` — verify OPTIONS returns correct headers |
| **P0** | 403 CORS headers not tested | Extend: `cors-env-gated-404.spec.ts` → add 403 case |
| **P1** | Auto-restore with valid SCHEDULER_ROLE_ARN | New: `chaos-auto-restore.spec.ts` — start experiment, verify auto-restore triggers |
| **P1** | CORS-blocked SSE connection | Extend: `chaos-sse-lifecycle.spec.ts` → add test for SSE when CORS fails |
| **P2** | Lambda Function URL CORS vs API Gateway CORS | New: `cors-function-url.spec.ts` — test Function URL directly (preprod only) |
| **P2** | Notification email URL validation | New: `notification-email.spec.ts` — requires MailSlurp integration |
| **P2** | 504 Gateway Timeout CORS headers | Extend: `error-visibility-banner.spec.ts` → add 504 case |

---

## Adversarial Review #1 — Stakeholder Perspectives

### DevOps Perspective (Gameday Visibility, Outage Visibility)

**Finding D-1 (CRITICAL): `ignore_changes = [environment]` creates a Terraform blind spot.**

Terraform will never detect env var drift on dashboard_lambda and notification_lambda. If the wiring provisioner fails silently (e.g., AWS CLI returns 0 but doesn't actually update), Terraform won't know. The next `terraform plan` will show "No changes" even though env vars are wrong.

**Impact**: During an outage, `terraform plan` says infrastructure is correct. DevOps trusts this and looks elsewhere. The actual issue is a Lambda with stale env vars.

**Mitigation**: Add a CloudWatch metric or custom health check that validates critical env vars at runtime:
```python
# In Lambda handler startup
scheduler_arn = os.environ.get("SCHEDULER_ROLE_ARN", "")
if not scheduler_arn and ENVIRONMENT != "dev":
    logger.warning("SCHEDULER_ROLE_ARN is empty — auto-restore disabled",
                   extra={"metric": "env_var_missing", "var": "SCHEDULER_ROLE_ARN"})
```

**Finding D-2 (MEDIUM): No alarm for wiring provisioner failure.**

If the `terraform_data` provisioner fails, the deploy pipeline fails. But if the pipeline is re-run and someone skips the failed step (or the failure is transient and not noticed), the Lambda runs indefinitely with placeholder values.

**Impact**: Silent degradation. Auto-restore doesn't work. Email links are broken. No alert fires because the Lambda itself is healthy (no errors, just wrong behavior).

**Mitigation**: Add E2E smoke test after deploy that validates SCHEDULER_ROLE_ARN and DASHBOARD_URL are non-empty. Already partially covered by preprod integration tests, but needs explicit assertion.

**Finding D-3 (LOW): Provisioner requires AWS CLI in CI runner.**

The `local-exec` provisioner runs `aws lambda update-function-configuration`. This requires:
1. AWS CLI installed on the runner
2. Valid AWS credentials with `lambda:UpdateFunctionConfiguration` permission
3. The correct region set

**Impact**: If CI runner image changes (e.g., Ubuntu 26.04 update removes AWS CLI), deploy silently breaks.

**Mitigation**: Already mitigated — CI uses `aws-actions/configure-aws-credentials` which installs CLI. Pin the action version.

### Senior Engineer Perspective (Adding New Features, Understanding Code)

**Finding E-1 (HIGH): `ignore_changes` is a foot-gun for future feature work.**

A developer adding a new env var to dashboard_lambda will:
1. Add it to the `environment_variables` block in main.tf
2. Run `terraform plan` — sees the change
3. Run `terraform apply` — change is applied
4. Next time the wiring provisioner runs, it **overwrites ALL env vars** because `update-function-configuration --environment` replaces the entire environment block

The developer's new env var disappears after the next unrelated apply.

**Impact**: Extremely confusing. Env var works in dev (no wiring provisioner), breaks in preprod/prod. Hard to debug.

**Mitigation**: The wiring provisioner MUST merge with existing env vars, not replace them:
```bash
# BAD: Overwrites all env vars
aws lambda update-function-configuration \
  --environment "Variables={SCHEDULER_ROLE_ARN=...}"

# GOOD: Read existing, merge, update
EXISTING=$(aws lambda get-function-configuration --function-name X --query 'Environment.Variables')
MERGED=$(echo "$EXISTING" | jq '. + {"SCHEDULER_ROLE_ARN": "..."}')
aws lambda update-function-configuration \
  --environment "Variables=$MERGED"
```

**Finding E-2 (MEDIUM): Cognitive overhead — three places to understand Lambda config.**

A developer looking at dashboard_lambda needs to check:
1. `module "dashboard_lambda"` in main.tf for the base config
2. `terraform_data "dashboard_lambda_wiring"` for cross-module env vars
3. The Lambda module source code (`modules/lambda/main.tf`) for `ignore_changes`

This splits the "truth" about what env vars a Lambda has across multiple locations.

**Impact**: Slows onboarding. Increases chance of misconfiguration.

**Mitigation**: Clear comments at each location referencing the others:
```hcl
# NOTE: This Lambda uses split definition/wiring pattern.
# - Base config: here (module "dashboard_lambda")
# - Cross-module env vars: terraform_data "dashboard_lambda_wiring" (line XXX)
# - Pattern docs: docs/terraform-patterns.md#split-definition-wiring
```

**Finding E-3 (LOW): No way to test the wiring in isolation.**

The provisioner only runs during `terraform apply`. There's no way to dry-run or validate that the `aws lambda update-function-configuration` command will succeed without actually running it.

**Impact**: Failures only discovered during deploy, not during CI.

**Mitigation**: Add a `terraform plan` output that shows what the provisioner WILL do. Or add a CI step that validates IAM permissions for `lambda:UpdateFunctionConfiguration` before apply.

### Engineering Manager Perspective (Cost, Resilience)

**Finding M-1 (LOW): Zero additional cost.**

Strategy 4 adds `terraform_data` resources (no AWS resources). The `aws lambda update-function-configuration` API call is free. No new Lambda functions, no new DynamoDB tables, no new infrastructure.

**Impact**: $0/month incremental cost.

**Finding M-2 (MEDIUM): Increased deploy pipeline fragility.**

The deploy pipeline now has more steps that can fail. Before: create resources. After: create resources + patch env vars. Each patch is a separate API call that can fail independently.

**Impact**: Deploy pipeline failure rate may increase slightly. Each failure requires investigation (is it a real issue or transient?).

**Mitigation**: Add retry logic to the provisioner (3 retries with backoff). AWS CLI supports `--retry-mode adaptive`.

**Finding M-3 (HIGH): This is tech debt that should be resolved permanently.**

Strategy 4 is a workaround, not a fix. The real fix is to restructure the module dependencies so env vars don't cross module boundaries. Options:
1. Notification_lambda looks up DASHBOARD_URL at runtime via SSM Parameter Store
2. Dashboard_lambda looks up SCHEDULER_ROLE_ARN at runtime via SSM or tags
3. Restructure modules to eliminate the cycle

**Impact**: Every future module addition risks creating new cycles. The `ignore_changes` + provisioner pattern doesn't scale.

**Mitigation**: File tech debt ticket. Target resolution: next quarter. In the meantime, Strategy 4 unblocks deploys.

---

## Adversarial Review #2 — State-Sponsored Attacker Analysis

### Attack Surface Assessment

The split definition/wiring pattern introduces ONE new attack surface: the `local-exec` provisioner that runs `aws lambda update-function-configuration`.

### A-1: Provisioner Command Injection (CRITICAL if exploitable)

**Vector**: The provisioner command interpolates Terraform variables. If any variable contains shell metacharacters, they could be executed.

**Analysis**: The `triggers` values come from Terraform module outputs (chaos_scheduler_role_arn, amplify production_url). These are AWS-generated strings:
- ARN format: `arn:aws:iam::123456789012:role/preprod-chaos-scheduler` — no shell metacharacters
- Amplify URL format: `https://main.d29tlmksqcx494.amplifyapp.com` — no shell metacharacters

An attacker would need to compromise either:
1. The Terraform state file (to inject a malicious ARN)
2. The AWS API response (to return a crafted ARN)
3. The CI pipeline (to modify the provisioner command)

**Verdict**: **LOW RISK.** All interpolated values are AWS-generated and follow strict formats. However, the provisioner should use `--cli-input-json` instead of inline string interpolation for defense-in-depth:
```bash
# SAFER: JSON input prevents shell injection
aws lambda update-function-configuration \
  --cli-input-json "$(cat <<EOF
{
  "FunctionName": "${function_name}",
  "Environment": {"Variables": {"SCHEDULER_ROLE_ARN": "${arn}"}}
}
EOF
)"
```

### A-2: Env Var Poisoning via Terraform State (HIGH)

**Vector**: An attacker with write access to the Terraform state file (S3 bucket) modifies the `chaos_scheduler_role_arn` output to point to an attacker-controlled IAM role.

**Analysis**: If SCHEDULER_ROLE_ARN points to an attacker's role, and that role has permissions to invoke Lambda, the chaos auto-restore feature could be used to execute arbitrary Lambda invocations under the attacker's role.

**Prerequisite**: Write access to Terraform state S3 bucket.

**Mitigation**:
1. S3 bucket versioning enabled (detect unauthorized changes)
2. S3 bucket policy restricts writes to CI role only
3. State file encryption with KMS (customer-managed key)
4. CloudTrail monitoring on state bucket writes

**Verdict**: **HIGH RISK if state bucket is compromised.** But this is a general Terraform risk, not specific to Strategy 4. The provisioner doesn't make it worse — the same attack works by modifying any env var in state.

### A-3: Privilege Escalation via Lambda Env Var Update (MEDIUM)

**Vector**: The CI pipeline needs `lambda:UpdateFunctionConfiguration` permission. This is a powerful permission — it can set ANY env var on ANY Lambda (if not scoped).

**Analysis**: If the CI role has `lambda:UpdateFunctionConfiguration` on `*`, an attacker who compromises the CI pipeline can:
1. Change any Lambda's env vars (e.g., set DASHBOARD_API_KEY_SECRET_ARN to an attacker-controlled secret)
2. Point Lambda to attacker-controlled DynamoDB tables
3. Exfiltrate data by changing log destinations

**Mitigation**: Scope the IAM permission to specific Lambda function ARNs:
```json
{
  "Effect": "Allow",
  "Action": "lambda:UpdateFunctionConfiguration",
  "Resource": [
    "arn:aws:lambda:*:*:function:preprod-sentiment-dashboard",
    "arn:aws:lambda:*:*:function:preprod-sentiment-notification"
  ]
}
```

**Verdict**: **MEDIUM RISK.** Mitigated by scoping IAM. Must be implemented as part of Strategy 4 rollout.

### A-4: DNS Rebinding via Amplify URL in CORS (LOW)

**Vector**: Amplify URLs (`*.amplifyapp.com`) are controlled by Amplify, not the user. If an attacker creates their own Amplify app with a similar-looking domain, and that domain ends up in CORS origins, cross-origin requests from the attacker's app would be allowed.

**Analysis**: The wiring provisioner uses `module.amplify_frontend[0].production_url`, which is the actual Amplify app URL. An attacker can't inject their URL into this output — it comes from AWS's response, not user input.

**Verdict**: **LOW RISK.** Amplify URL is AWS-controlled.

### A-5: Timing Attack — Invoke Lambda During Placeholder Window (LOW)

**Vector**: An attacker who knows the deploy schedule invokes dashboard_lambda during the T2→T6 window when SCHEDULER_ROLE_ARN is empty. They start a chaos experiment, knowing auto-restore won't trigger, then exploit the degraded state.

**Analysis**:
1. The T2→T6 window is ~30-60 seconds during `terraform apply`
2. During apply, the API Gateway stage may not be fully deployed
3. Even if reachable, starting a chaos experiment requires authentication
4. The attacker would need both: knowledge of deploy timing AND valid auth credentials

**Verdict**: **LOW RISK.** Narrow window, requires auth, minimal impact (auto-restore disabled doesn't create vulnerability — experiments still stop manually).

### A-6: Supply Chain — AWS CLI Backdoor in CI (CRITICAL if realized)

**Vector**: The provisioner runs `aws` CLI. If the CI runner's AWS CLI is compromised (supply chain attack on the `aws-cli` package), every `update-function-configuration` call could exfiltrate env var values (which include secret ARNs, API keys, JWT secrets).

**Analysis**: This is a general CI supply chain risk, not specific to Strategy 4. However, Strategy 4 INCREASES the attack surface because it adds new `aws` CLI invocations that handle sensitive env vars.

**Mitigation**:
1. Pin AWS CLI version in CI
2. Verify CLI checksums
3. Use OIDC federation instead of static credentials
4. Monitor CloudTrail for anomalous `UpdateFunctionConfiguration` calls

**Verdict**: **LOW probability, CRITICAL impact.** Standard supply chain mitigation applies.

### Attack Surface Summary

| Attack | Probability | Impact | Risk | Introduced by Strategy 4? |
|--------|------------|--------|------|--------------------------|
| A-1: Command injection | Very Low | Critical | LOW | Yes — new shell commands |
| A-2: State poisoning | Low | High | MEDIUM | No — general Terraform risk |
| A-3: Privilege escalation | Medium | High | MEDIUM | Yes — new IAM permission needed |
| A-4: DNS rebinding | Very Low | Low | LOW | No — URL source unchanged |
| A-5: Timing attack | Low | Low | LOW | Yes — new timing window |
| A-6: Supply chain | Very Low | Critical | LOW | Partially — more CLI calls |

### Mandatory Security Controls for Strategy 4

1. **Scope IAM**: `lambda:UpdateFunctionConfiguration` restricted to specific function ARNs
2. **Use --cli-input-json**: Prevent shell injection in provisioner commands
3. **CloudTrail alert**: Monitor `UpdateFunctionConfiguration` calls outside deploy windows
4. **Merge env vars**: Provisioner must read-merge-write, not overwrite
5. **Pin AWS CLI**: Version-pin in CI workflow
