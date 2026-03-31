# Adversarial Reviews — Terraform Cycle Fix (Strategy 4)

Generated: 2026-03-30
Feature: Terraform dependency cycle resolution via split definition/wiring pattern

---

## AR#1 — Stakeholder Perspectives

### DevOps (Gameday & Outage Visibility)

| ID | Severity | Finding | Mitigation |
|----|----------|---------|------------|
| D-1 | **CRITICAL** | `ignore_changes = [environment]` creates Terraform blind spot. `terraform plan` shows "No changes" even when env vars are wrong. During outage investigation, this is a false negative. | Add runtime env var validation in Lambda startup. Emit CloudWatch metric `env_var_missing` when critical vars are empty. |
| D-2 | **MEDIUM** | No alarm for wiring provisioner failure. Lambda runs indefinitely with placeholder values. Auto-restore silently disabled. Email links silently broken. | Add E2E smoke test after deploy: assert SCHEDULER_ROLE_ARN and DASHBOARD_URL are non-empty. Add CloudWatch alarm on `env_var_missing` metric. |
| D-3 | **LOW** | Provisioner requires AWS CLI in CI runner. Runner image change could silently break deploys. | Pin `aws-actions/configure-aws-credentials` action version. Validate CLI availability in pre-deploy step. |

**DevOps Verdict**: Acceptable with mitigations D-1 and D-2. The blind spot (D-1) is the biggest risk — it violates the principle that `terraform plan` is the source of truth for infrastructure state.

### Senior Engineer (Feature Development & Code Understanding)

| ID | Severity | Finding | Mitigation |
|----|----------|---------|------------|
| E-1 | **HIGH** | `ignore_changes` is a foot-gun. Developer adds env var to Lambda block → works in dev → disappears in preprod because wiring provisioner OVERWRITES all env vars. | Wiring provisioner MUST read-merge-write env vars (not replace). Document this in CLAUDE.md and module README. |
| E-2 | **MEDIUM** | Lambda config truth split across 3 locations: module block, terraform_data, lambda module source. | Add cross-reference comments. Create docs/terraform-patterns.md documenting the pattern with diagrams. |
| E-3 | **LOW** | No way to test wiring in isolation. Failures only discovered during deploy. | Add CI step that dry-runs IAM permission check for `lambda:UpdateFunctionConfiguration`. |

**Senior Engineer Verdict**: Acceptable with E-1 mitigation (merge, don't replace). Without E-1 fix, this pattern will cause a production incident within 2 sprints when someone adds an env var.

### Engineering Manager (Cost & Resilience)

| ID | Severity | Finding | Mitigation |
|----|----------|---------|------------|
| M-1 | **LOW** | Zero additional AWS cost. terraform_data resources are free. | None needed. |
| M-2 | **MEDIUM** | Deploy pipeline has more failure points. Each provisioner is an independent API call that can fail. | Add retry logic (3x with backoff) to provisioner commands. Monitor deploy duration for regression. |
| M-3 | **HIGH** | This is tech debt, not a permanent fix. Every new module risks new cycles. `ignore_changes` + provisioner doesn't scale. | File tech debt ticket. Target: next quarter. Long-term fix: runtime resolution via SSM Parameter Store or restructure modules. |

**EM Verdict**: Approve as short-term fix. Requires tech debt ticket and timeline for permanent resolution. Cost impact: $0.

---

## AR#2 — State-Sponsored Attacker Analysis

### Threat Model

**Attacker profile**: State-sponsored actor with sophisticated tooling, patience for long-term access, and interest in:
1. Data exfiltration (financial data, user sessions, API keys)
2. Supply chain compromise (CI/CD pipeline)
3. Persistent access (IAM roles, Lambda env vars)

**New attack surface introduced by Strategy 4**: `local-exec` provisioner that runs AWS CLI commands to update Lambda environment variables during `terraform apply`.

### Findings

| ID | Vector | Probability | Impact | Risk | New Surface? |
|----|--------|------------|--------|------|-------------|
| A-1 | **Command injection via provisioner interpolation** — Shell metacharacters in Terraform variable values could execute arbitrary commands during local-exec | Very Low | Critical | LOW | **Yes** |
| A-2 | **Terraform state poisoning** — Attacker with S3 state bucket write access modifies module outputs to inject malicious ARNs/URLs into Lambda env vars | Low | High | MEDIUM | No (general risk) |
| A-3 | **Privilege escalation via UpdateFunctionConfiguration** — CI role needs new IAM permission. Unscoped, allows changing ANY Lambda's env vars (secrets, API keys, DB tables) | Medium | High | **MEDIUM** | **Yes** |
| A-4 | **DNS rebinding via Amplify URL** — Attacker-controlled Amplify app domain injected into CORS origins | Very Low | Low | LOW | No |
| A-5 | **Timing attack during placeholder window** — Exploit 30-60s window when Lambda has empty env vars during deploy | Low | Low | LOW | **Yes** |
| A-6 | **Supply chain via AWS CLI** — Compromised CLI exfiltrates env var values (contain secret ARNs, JWT secrets) during UpdateFunctionConfiguration call | Very Low | Critical | LOW | Partially |

### Mandatory Security Controls

These MUST be implemented as part of Strategy 4 rollout:

1. **IAM scoping** (blocks A-3):
```json
{
  "Effect": "Allow",
  "Action": "lambda:UpdateFunctionConfiguration",
  "Resource": [
    "arn:aws:lambda:us-east-1:ACCOUNT:function:preprod-sentiment-dashboard",
    "arn:aws:lambda:us-east-1:ACCOUNT:function:preprod-sentiment-notification"
  ]
}
```

2. **JSON input for CLI** (blocks A-1):
```bash
aws lambda update-function-configuration \
  --cli-input-json file:///tmp/lambda-config.json
```
Not inline string interpolation.

3. **CloudTrail alerting** (detects A-2, A-3):
```
EventName = "UpdateFunctionConfiguration20150331v2"
AND sourceIPAddress != <CI runner IP range>
→ SNS alert to security team
```

4. **Env var merge, not replace** (blocks E-1 footgun, limits A-3 blast radius):
```bash
EXISTING=$(aws lambda get-function-configuration \
  --function-name X --query 'Environment.Variables')
MERGED=$(echo "$EXISTING" | jq '. + {"SCHEDULER_ROLE_ARN": "new-value"}')
aws lambda update-function-configuration \
  --function-name X \
  --environment "Variables=$MERGED"
```

5. **Pin AWS CLI version** (mitigates A-6):
```yaml
- uses: aws-actions/configure-aws-credentials@v4.2.0  # pinned
- run: aws --version  # Log for audit
```

### State-Sponsored Attacker Verdict

Strategy 4 introduces **two new attack surfaces** (A-1, A-3) and **one new timing window** (A-5). All are mitigable with the 5 mandatory controls above. The highest-risk finding (A-3: privilege escalation) is fully blocked by IAM scoping.

**Overall risk**: ACCEPTABLE with mandatory controls. The new attack surface is smaller than the current risk of having NO deploys (the cycle blocks all infrastructure updates, which means security patches can't be deployed either).

---

## Gate Statement

**AR#1**: PASS with conditions — E-1 (merge env vars) and D-1 (runtime validation) must be in implementation plan.

**AR#2**: PASS with conditions — All 5 mandatory security controls must be implemented before merging to main.

---

## Inputs for /battleplan

When running `/battleplan` for this feature, include these constraints:

1. **Mandatory**: Wiring provisioner uses read-merge-write for env vars (not overwrite)
2. **Mandatory**: IAM permission scoped to specific Lambda ARNs
3. **Mandatory**: CLI input via JSON file (not inline interpolation)
4. **Mandatory**: Runtime env var validation in Lambda startup
5. **Mandatory**: CloudTrail alert for out-of-band UpdateFunctionConfiguration
6. **Tech debt**: File ticket for permanent fix (SSM Parameter Store or module restructure)
7. **Testing**: E2E smoke test after deploy validates non-empty env vars
8. **Documentation**: docs/terraform-patterns.md documenting the split definition/wiring pattern
