# Production Deployment Pre-Flight Checklist

> **Purpose**: Comprehensive checklist before deploying to production. Based on lessons learned from 15+ CI failures during dev environment setup.

## Before Any Production Deployment

### 1. Terraform State Verification

- [ ] Verify dev deployment succeeded first
- [ ] Confirm dev and prod use separate state files:
  - Dev: `s3://sentiment-analyzer-tfstate-218795110243/dev/terraform.tfstate`
  - Prod: `s3://sentiment-analyzer-tfstate-218795110243/prod/terraform.tfstate`
- [ ] Confirm dev and prod use separate lock tables:
  - Dev: `dev/terraform.tfstate.tflock`
  - Prod: `prod/terraform.tfstate.tflock`
- [ ] Run `terraform state list` to verify state is populated (not empty)
- [ ] No active state lock: `aws s3api head-object --bucket sentiment-analyzer-terraform-state-218795110243 --key/terraform.tfstate.tflock`

### 2. AWS Resources Pre-Check

- [ ] Lambda packages exist in S3 with correct keys:
  ```bash
  aws s3 ls s3://$DEPLOYMENT_BUCKET/ingestion/lambda.zip
  aws s3 ls s3://$DEPLOYMENT_BUCKET/analysis/lambda.zip
  aws s3 ls s3://$DEPLOYMENT_BUCKET/dashboard/lambda.zip
  ```
- [ ] Region is correct (us-east-1 for this project)
- [ ] All IAM roles exist and have correct permissions
- [ ] DynamoDB table exists with correct GSIs
- [ ] SNS topic exists
- [ ] Secrets Manager secrets are populated:
  - `prod/sentiment-analyzer/newsapi`

### 3. GitHub Secrets Verification

- [ ] `AWS_ACCESS_KEY_ID` is set
- [ ] `AWS_SECRET_ACCESS_KEY` is set
- [ ] `DEPLOYMENT_BUCKET` is set to the S3 bucket name
- [ ] All secrets are for the PRODUCTION AWS account (not dev)

### 4. Code Quality Checks

- [ ] All tests pass locally: `pytest tests/unit/`
- [ ] Linting passes: `ruff check src/ tests/`
- [ ] Terraform validates: `terraform validate`
- [ ] Terraform formats: `terraform fmt -check`
- [ ] No TODO/FIXME/HACK comments in critical paths

### 5. Security Review

#### CORS Configuration
- [ ] TD-002: `allow_origins` in `main.tf:230` - Review for production
  - Current: `["*"]` (demo mode)
  - Production: Restrict to specific domains
- [ ] Dashboard handler CORS in `src/lambdas/dashboard/handler.py:109`
  - Current: `allow_origins=["*"]`
  - Production: Restrict to CloudFront domain or specific origins

#### API Keys & Secrets
- [ ] NewsAPI key is valid and has production quota
- [ ] Dashboard API key is set and rotated from dev key
- [ ] No hardcoded credentials in code

#### IAM Permissions
- [ ] Review Lambda execution roles for least privilege
- [ ] CloudWatch metrics use namespace condition (TD-003 - acceptable)

#### Branch Protection ✅ CONFIGURED
- [x] Review GitHub branch protection rules: Settings → Branches → main
  - See `docs/security/BRANCH-PROTECTION.md` for required settings
- [x] Verify required status checks include all CI workflows:
  - `Test / test`
  - `Lint / lint`
  - `Security Scan / Dependency Vulnerability Scan`
  - `CodeQL Analysis / Analyze`
- [x] Confirm "Do not allow bypassing" is enabled
- [x] Dependabot auto-merge requires these status checks to pass:
  - Auto-merge will NOT proceed if any check fails
  - This is your safety net for dependency updates

> **Note**: Branch protection configured 2025-11-19. Dependabot PRs will
> auto-merge only after all required status checks pass.

### 6. Monitoring & Alerting

- [ ] CloudWatch alarms are configured for all Lambdas
- [ ] Alarm SNS topic is set to alert on-call
- [ ] Dashboard health check endpoint works
- [ ] Log retention is set (90 days for prod)

### 7. Data & State

- [ ] DynamoDB backup plan is configured
- [ ] TTL is set correctly (30 days)
- [ ] No test data in production tables

## During Deployment

### 8. Deployment Execution

- [ ] Monitor GitHub Actions workflow
- [ ] Watch for Terraform plan output - review changes
- [ ] Verify no unexpected destroys in plan
- [ ] Confirm "Apply complete" message

### 9. Smoke Tests After Deployment

- [ ] Lambda functions are in "Active" state:
  ```bash
  aws lambda get-function --function-name prod-sentiment-ingestion
  aws lambda get-function --function-name prod-sentiment-analysis
  aws lambda get-function --function-name prod-sentiment-dashboard
  ```
- [ ] Dashboard health check returns 200:
  ```bash
  curl -s https://<function-url>/health
  ```
- [ ] Test ingestion with manual EventBridge trigger
- [ ] Verify item appears in DynamoDB
- [ ] Check CloudWatch logs for errors

### 10. Rollback Preparation

- [ ] Know the previous commit hash
- [ ] Have rollback commands ready:
  ```bash
  git revert <commit>
  # or
  ./infrastructure/scripts/rollback.sh
  ```
- [ ] Know how to force-unlock Terraform state if needed

## Post-Deployment

### 11. Verification

- [ ] All CloudWatch alarms in OK state
- [ ] No errors in Lambda logs
- [ ] Dashboard accessible and showing data
- [ ] Metrics updating in real-time

### 12. Documentation

- [ ] Update deployment log with:
  - Commit hash
  - Deploy timestamp
  - Any issues encountered
  - Any manual interventions required

---

## Quick Reference: Common Issues

### State Lock Stuck
```bash
terraform force-unlock <LOCK_ID>
```

### Lambda Not Updating
```bash
aws lambda update-function-code \
  --function-name prod-sentiment-<lambda> \
  --s3-bucket $DEPLOYMENT_BUCKET \
  --s3-key <lambda>/lambda.zip \
  --publish
```

### Resource Already Exists
```bash
terraform import <resource_address> <resource_id>
```

### Partial Apply Recovery
1. List what was created: `terraform state list`
2. Import missing resources
3. Re-run apply

---

## Tech Debt to Address Before First Prod Deploy

**CRITICAL**:
- [ ] TD-001: Verify CORS allow_methods `["GET", "OPTIONS"]` works (currently in this commit)

**HIGH**:
- [ ] TD-002: Restrict CORS allow_origins for production domain

**MEDIUM** (can defer):
- [ ] TD-005: Integration test cleanup
- [ ] TD-010: Rename model_version to avoid Pydantic warning
- [ ] TD-012: Remove S3 archival Lambda references

---

**Last Updated**: 2025-11-19
**Author**: @traylorre
