# AR#1: Crash Loop Risk from Missing Terraform Environment Variables

## Adversarial Question

What if a Terraform `environment` block is missing a variable that code now requires
via `os.environ["VAR"]`? The Lambda enters a crash loop: cold start fails, AWS
retries, fails again. For synchronous invocations (API Gateway), this means 502s.
For async (EventBridge, SNS), this means retries until exhaustion then DLQ or drop.

## Risk Matrix

| Scenario | Severity | Likelihood | Detection Time |
|----------|----------|------------|----------------|
| Missing var in Terraform for existing Lambda | **Critical** | Low (we verify in Stage 4) | Minutes (cold start crash logged) |
| Missing var in Terraform for NEW env (e.g., staging) | **Critical** | Medium | Minutes after first deploy |
| Var present but empty string in Terraform | **High** | Low | Minutes (KeyError on cold start) |
| Var present in Terraform but not propagated (Terraform apply not run) | **Critical** | Low | Minutes |

## Analysis

### Why fail-fast is SAFER than silent empty string

The current pattern `os.environ.get("DASHBOARD_URL", "")` does NOT crash. Instead:

1. CORS headers contain `Access-Control-Allow-Origin: ""` -- browsers reject all
   cross-origin requests. The dashboard appears to load but all API calls fail silently.
2. OAuth URLs contain empty pool IDs -- Cognito returns opaque 400 errors that don't
   mention the root cause (missing env var).
3. SNS publish with empty TopicArn -- boto3 returns a `ParameterValueInvalid` error
   that doesn't mention the env var.

In all cases, the **symptom** (CORS error, OAuth error, SNS error) is far from the
**cause** (missing env var). Time to diagnose: minutes to hours.

With `os.environ["VAR"]`, the Lambda crashes with:
```
KeyError: 'DASHBOARD_URL'
```
Time to diagnose: seconds. The error names the exact missing variable.

### Crash loop mechanics

- **Lambda retry behavior**: Synchronous invocations (API Gateway) do NOT retry --
  they return 502 immediately. No crash loop.
- **Async invocations** (EventBridge rules, SNS triggers): Retry 2 times then send
  to DLQ if configured. Not a true crash loop.
- **Cold start behavior**: KeyError at module level means every invocation fails.
  But Lambda doesn't "loop" -- it waits for the next invocation.

The "crash loop" fear is overstated. Lambda is not a container that restarts itself.
Each invocation fails independently. The real risk is **all invocations failing**,
which is exactly what happens with empty strings too -- just harder to diagnose.

## Mitigations

### M1: Terraform Verification (Stage 4)

Before any code change, verify every Category A variable exists in the corresponding
Lambda's Terraform `environment` block. This is the primary mitigation.

### M2: CloudWatch Alarm on Lambda Errors

Existing CloudWatch alarms on Lambda error rate will fire within 5 minutes of
deployment if cold starts fail. This provides rapid detection.

### M3: Canary Lambda

The canary Lambda (existing infrastructure) exercises the dashboard and ingestion
endpoints. A missing env var will trigger canary failure alerts.

### M4: Terraform Plan Review

`terraform plan` will show the environment block changes. Reviewers can verify
all required vars are present before apply.

### M5: Staged Rollout

Deploy to dev first (LocalStack), then preprod (real AWS), then prod. Missing vars
caught in dev never reach prod.

## Verdict

**PROCEED with Category A changes.** The crash-on-missing-var behavior is strictly
superior to silent-failure-with-empty-string. The "crash loop" risk is mitigated by:
1. Lambda doesn't actually loop (it's invocation-based)
2. Terraform verification (Stage 4) prevents the scenario
3. CloudWatch alarms provide rapid detection
4. Staged rollout catches issues before prod

## Open Item

Stage 4 must confirm every variable. If ANY Category A variable is missing from
Terraform, that variable must be added to Terraform BEFORE the code change, or
downgraded to Category B.
