# Failure Recovery Runbook

**Purpose**: Step-by-step recovery procedures for promotion pipeline failures

**Audience**: On-call engineers, DevOps, developers

**Last Updated**: 2025-11-20

---

## Quick Reference

| Failure Scenario | Severity | Auto-Rollback? | Recovery Time |
|------------------|----------|----------------|---------------|
| Dev tests fail | LOW | N/A | Fix code, push again |
| Preprod deploy fail | MEDIUM | No | Revert commit OR fix Terraform |
| Preprod tests fail | MEDIUM | No | Revert commit OR fix code |
| Prod deploy fail | **HIGH** | Yes | 5-10 minutes (automatic) |
| Canary fail | **CRITICAL** | Yes | 5 minutes (automatic) |
| Rollback fail | **CRITICAL** | No | Manual intervention required |

---

## Scenario 1: Dev Tests Fail

### Symptoms

```
GitHub Actions → Tests (Dev) → ❌ FAILED
PR cannot merge (branch protection)
```

### Root Causes

- Test code broken
- Application code broken
- Dependency issue
- Environment variable missing

### Recovery Steps

**Automatic**: Branch protection prevents merge

**Manual Fix**:

1. Check test logs:
   ```bash
   gh run view <RUN_ID> --log-failed
   ```

2. Fix the issue locally:
   ```bash
   # Run tests locally
   pytest tests/unit/ tests/integration/test_*_dev.py -v

   # Fix code
   # Commit and push
   git commit -am "fix: <description>"
   git push
   ```

3. Verify:
   - Dev tests re-run automatically
   - PR becomes mergeable when tests pass

**Prevention**:
- Run tests locally before pushing: `pytest`
- Use pre-commit hooks: `pre-commit install`

---

## Scenario 2: Preprod Deployment Fails (Terraform)

### Symptoms

```
GitHub Actions → Build and Promote to Preprod → Deploy to Preprod → ❌ FAILED
Terraform apply failed
Preprod infrastructure may be in partial state
```

### Root Causes

- Terraform configuration error
- AWS API error (throttling, quota)
- State lock held
- Resource already exists (manual creation)

### Recovery Steps

#### Option 1: Revert the Commit (Safest)

```bash
# Find the failing commit
git log --oneline -5

# Revert it
git revert HEAD
git push origin main

# Workflow re-runs with previous config
# Preprod returns to stable state
```

#### Option 2: Fix Terraform Manually

```bash
# Check Terraform state
cd infrastructure/terraform
terraform init -backend-config=backend-preprod.hcl
terraform state list

# Check current state vs desired
terraform plan -var-file=preprod.tfvars

# If state lock held
terraform force-unlock <LOCK_ID>

# If resource conflict
terraform import <resource> <aws-id>

# Re-apply
terraform apply -var-file=preprod.tfvars
```

#### Option 3: Destroy and Recreate (Nuclear)

```bash
# DANGER: Only if preprod is completely broken
terraform destroy -var-file=preprod.tfvars

# Re-run workflow to redeploy
gh workflow run build-and-promote.yml
```

### Validation

```bash
# Verify preprod resources exist
aws dynamodb list-tables | grep preprod
aws lambda list-functions | grep preprod
aws s3 ls | grep preprod

# Check Terraform state is healthy
terraform plan -var-file=preprod.tfvars
# Should show: "No changes"
```

### Prevention

- Test Terraform changes locally first: `terraform plan -var-file=preprod.tfvars`
- Use `terraform validate` before committing
- Never manually create resources in preprod

---

## Scenario 3: Preprod Tests Fail (Integration)

### Symptoms

```
GitHub Actions → Build and Promote to Preprod → Preprod Integration Tests → ❌ FAILED
Preprod infrastructure deployed OK
Tests failed against real AWS
Production deployment BLOCKED
```

### Root Causes

- Application code broken
- Infrastructure misconfigured
- AWS resource issue (throttling, permissions)
- Test data pollution
- Secrets not accessible

### Recovery Steps

#### Step 1: Check Test Logs

```bash
# View failed test output
gh run view <RUN_ID> --log-failed

# Download test results artifact
gh run download <RUN_ID> --name preprod-test-results-<SHA>
```

#### Step 2: Reproduce Locally (if possible)

```bash
# Set preprod environment variables
export AWS_ACCESS_KEY_ID="<PREPROD_KEY>"
export AWS_SECRET_ACCESS_KEY="<PREPROD_SECRET>"
export ENVIRONMENT=preprod
export DYNAMODB_TABLE=preprod-sentiment-items
# ... other env vars

# Run preprod tests locally
pytest tests/integration/test_*_preprod.py -v --tb=short
```

#### Step 3: Fix the Issue

**If code is broken**:
```bash
# Fix code locally
# Run tests: pytest tests/integration/test_*_preprod.py -v
git commit -am "fix: <description>"
git push origin main
# Workflow re-runs automatically
```

**If infrastructure is misconfigured**:
```bash
# Check AWS resources
aws dynamodb describe-table --table-name preprod-sentiment-items
aws lambda get-function --function-name preprod-sentiment-ingestion

# Check Secrets Manager
aws secretsmanager get-secret-value --secret-id preprod/sentiment-analyzer/newsapi

# Fix Terraform if needed
cd infrastructure/terraform
terraform apply -var-file=preprod.tfvars
```

**If test data is polluted**:
```bash
# Clean up preprod DynamoDB (use cautiously)
aws dynamodb scan --table-name preprod-sentiment-items \
  --projection-expression "source_id,timestamp" \
  | jq -r '.Items[] | "\(.source_id.S) \(.timestamp.S)"' \
  | while read source_id timestamp; do
      aws dynamodb delete-item \
        --table-name preprod-sentiment-items \
        --key "{\"source_id\":{\"S\":\"$source_id\"},\"timestamp\":{\"S\":\"$timestamp\"}}"
    done
```

### Validation

```bash
# Re-run preprod validation manually
gh workflow run build-and-promote.yml

# Wait for completion
gh run watch

# Check status
gh run list --workflow=build-and-promote.yml --limit 1
```

### Prevention

- Run preprod tests before merging: `pytest tests/integration/test_*_preprod.py`
- Use unique test data (timestamp-based IDs)
- Clean up test data in `try/finally` blocks

---

## Scenario 4: Production Deployment Fails (Terraform)

### Symptoms

```
GitHub Actions → Deploy to Production → Deploy to Production → ❌ FAILED
Terraform apply failed in production
Automatic rollback triggered
```

### Auto-Recovery

**Automatic** rollback workflow triggers:
1. Finds previous successful prod deployment SHA
2. Redeploys previous version via Terraform
3. Notifies on-call

**Expected**: Prod reverted within 5-10 minutes

### Manual Recovery (if auto-rollback fails)

#### Step 1: Verify Current State

```bash
# Check what's deployed
aws lambda list-functions | grep prod

# Check Terraform state
cd infrastructure/terraform
terraform init -backend-config=backend-prod.hcl
terraform state list
```

#### Step 2: Manual Rollback

```bash
# Find previous working SHA
git log --oneline -10

# Identify last known good version
PREVIOUS_SHA="<SHA from git log>"

# Redeploy previous version
terraform apply \
  -var-file=prod.tfvars \
  -var="model_version=${PREVIOUS_SHA}" \
  -auto-approve
```

#### Step 3: Verify Rollback

```bash
# Test prod health endpoint
curl https://<prod-dashboard-url>/health \
  -H "X-API-Key: ${PROD_API_KEY}"

# Check CloudWatch alarms
aws cloudwatch describe-alarms \
  --alarm-name-prefix "prod-" \
  --state-value ALARM
# Should return empty
```

### Post-Incident

1. **Root cause analysis**: Why did Terraform fail?
2. **Fix the issue** in a new PR
3. **Test in preprod** before attempting prod again
4. **Document** what went wrong

### Prevention

- Always deploy to preprod first
- Never skip preprod validation
- Test Terraform changes in preprod: `terraform plan -var-file=prod.tfvars`

---

## Scenario 5: Canary Test Fails (Production)

### Symptoms

```
GitHub Actions → Deploy to Production → Production Canary Test → ❌ FAILED
Health check returned non-200
OR CloudWatch alarms triggered
Automatic rollback triggered
```

### Auto-Recovery

**Automatic** rollback workflow triggers:
1. Detects canary failure
2. Finds previous successful deployment
3. Redeploys previous version
4. Notifies on-call

**Expected**: Prod reverted within 5 minutes

### Root Causes

- Dashboard Lambda broken
- API key authentication failing
- DynamoDB not accessible
- Secrets Manager not accessible
- Network/VPC issue

### Manual Investigation (after auto-rollback)

#### Check Canary Logs

```bash
# View failed canary output
gh run view <RUN_ID> --log-failed

# Look for HTTP status code
# Look for error messages
```

#### Check Lambda Logs

```bash
# Check dashboard Lambda logs
aws logs tail /aws/lambda/prod-sentiment-dashboard --follow --since 10m

# Look for errors
aws logs filter-log-events \
  --log-group-name /aws/lambda/prod-sentiment-dashboard \
  --filter-pattern "ERROR" \
  --start-time $(date -u -d '10 minutes ago' +%s)000
```

#### Check CloudWatch Alarms

```bash
# List all prod alarms
aws cloudwatch describe-alarms --alarm-name-prefix "prod-"

# Check alarm history
aws cloudwatch describe-alarm-history \
  --alarm-name prod-dashboard-errors \
  --max-records 10
```

#### Test Health Endpoint Manually

```bash
# Test dashboard health check
DASHBOARD_URL=$(terraform output -raw dashboard_function_url)
API_KEY="<PROD_API_KEY>"

curl -v https://${DASHBOARD_URL}/health \
  -H "X-API-Key: ${API_KEY}"

# Should return 200 with {"status":"healthy",...}
```

### Post-Rollback Fix

1. **Identify root cause** from logs
2. **Fix the issue** in a new PR
3. **Test in preprod**:
   ```bash
   pytest tests/integration/test_canary_preprod.py -v
   ```
4. **Deploy to prod** only after preprod validation passes

### Prevention

- Test canary in preprod before prod: `tests/integration/test_canary_preprod.py`
- Monitor preprod for canary failures
- Keep canary simple (health check only)

---

## Scenario 6: Rollback Fails (CRITICAL)

### Symptoms

```
GitHub Actions → Deploy to Production → Rollback on Failure → ❌ FAILED
Auto-rollback attempted but failed
Production may be in broken state
IMMEDIATE ACTION REQUIRED
```

### Immediate Response (CRITICAL PATH)

#### Step 1: Assess Production State

```bash
# Check if Lambda functions are active
aws lambda list-functions | grep prod

for func in ingestion analysis dashboard; do
  state=$(aws lambda get-function \
    --function-name prod-sentiment-${func} \
    --query 'Configuration.State' \
    --output text)
  echo "${func}: ${state}"
done
```

#### Step 2: Emergency Manual Rollback

```bash
# Use LAST KNOWN GOOD SHA
# Check deployment history
gh api repos/traylorre/sentiment-analyzer-gsk/actions/workflows/deploy-prod.yml/runs \
  --jq '.workflow_runs[] | select(.conclusion == "success") | {id: .id, sha: .head_sha, created: .created_at}' \
  | head -5

# Identify last successful SHA
GOOD_SHA="<SHA from above>"

# Manual Terraform rollback
cd infrastructure/terraform
terraform init -backend-config=backend-prod.hcl
terraform apply \
  -var-file=prod.tfvars \
  -var="model_version=${GOOD_SHA}" \
  -auto-approve \
  -lock-timeout=10m
```

#### Step 3: Force Lambda Update (if Terraform fails)

```bash
# Nuclear option: Update Lambda functions directly
BUCKET="prod-sentiment-lambda-deployments"
GOOD_SHA="<last known good>"

for func in ingestion analysis dashboard; do
  aws lambda update-function-code \
    --function-name prod-sentiment-${func} \
    --s3-bucket ${BUCKET} \
    --s3-key ${func}/lambda-${GOOD_SHA}.zip \
    --publish
done
```

#### Step 4: Verify Recovery

```bash
# Test health endpoint
curl https://<prod-dashboard-url>/health -H "X-API-Key: ${PROD_API_KEY}"

# Check CloudWatch alarms
aws cloudwatch describe-alarms \
  --alarm-name-prefix "prod-" \
  --state-value ALARM

# Monitor for 10 minutes
watch -n 30 'aws cloudwatch describe-alarms --alarm-name-prefix "prod-" --state-value ALARM'
```

### Post-Incident (REQUIRED)

1. **Write incident report**: What happened, why rollback failed, how it was resolved
2. **Root cause analysis**: Why did automatic rollback fail?
3. **Update runbook**: Add new failure mode to this document
4. **Test rollback procedure**: Ensure it works next time

### Escalation

If manual rollback fails:
1. **Page senior engineer** immediately
2. **Consider full outage**: Take prod offline if data corruption risk
3. **Restore from backup**: Use DynamoDB point-in-time recovery
4. **Redeploy from scratch**: Last resort

### Prevention

- Test rollback procedure in preprod
- Keep rollback logic simple
- Monitor GitHub Actions workflow health
- Maintain list of known-good SHAs

---

## General Troubleshooting

### GitHub Actions Workflow Stuck

**Symptoms**: Workflow running for >30 minutes

**Fix**:
```bash
# Cancel stuck workflow
gh run cancel <RUN_ID>

# Re-run workflow
gh run rerun <RUN_ID>
```

### Terraform State Lock Held

**Symptoms**: `Error acquiring the state lock`

**Fix**:
```bash
# Check who holds the lock
terraform force-unlock <LOCK_ID>

# If unsure, check DynamoDB lock table
aws dynamodb scan --table-name terraform-state-lock-prod
```

### Secrets Not Accessible

**Symptoms**: `AccessDeniedException` or `SecretNotFoundException`

**Fix**:
```bash
# Verify secret exists
aws secretsmanager list-secrets --query 'SecretList[?starts_with(Name, `prod/`)]'

# Verify IAM permissions
aws iam get-user-policy \
  --user-name sentiment-analyzer-prod-deployer \
  --policy-name ProdDeploymentPolicy
```

### CloudWatch Alarms Won't Clear

**Symptoms**: Alarm stays in ALARM state after fix

**Fix**:
```bash
# Check alarm history
aws cloudwatch describe-alarm-history --alarm-name <ALARM_NAME>

# Manually set to OK (if justified)
aws cloudwatch set-alarm-state \
  --alarm-name <ALARM_NAME> \
  --state-value OK \
  --state-reason "Manual override after verified fix"
```

---

## Escalation Matrix

| Issue Severity | Response Time | Escalation Path |
|----------------|---------------|-----------------|
| Dev tests fail | Best effort | Developer fixes |
| Preprod fail | 1 hour | DevOps team |
| Prod fail (auto-rollback works) | 15 minutes | On-call engineer |
| Prod fail (auto-rollback fails) | **IMMEDIATE** | Page senior engineer |
| Data corruption | **IMMEDIATE** | CTO + senior engineer |

---

## Post-Incident Checklist

After ANY production incident:

- [ ] Write incident report (what, when, why, how resolved)
- [ ] Root cause analysis (5 whys)
- [ ] Update this runbook with new failure mode
- [ ] Create GitHub issue to prevent recurrence
- [ ] Test recovery procedure works
- [ ] Update monitoring/alerting if gaps found
- [ ] Share lessons learned with team

---

## References

- Promotion workflow design: `docs/PROMOTION_WORKFLOW_DESIGN.md`
- Terraform verification: `infrastructure/docs/TERRAFORM_RESOURCE_VERIFICATION.md`
- Credential separation: `infrastructure/docs/CREDENTIAL_SEPARATION_SETUP.md`
- GitHub Environments: `docs/GITHUB_ENVIRONMENTS_SETUP.md`
