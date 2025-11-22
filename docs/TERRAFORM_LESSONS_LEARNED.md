# Terraform Lessons Learned

> **Purpose**: Document the missteps, root causes, and preventative measures discovered during the initial Terraform CI/CD setup. This is a learning document for future reference and to help others avoid similar pitfalls.

## Executive Summary

The initial Terraform deployment took **15+ CI failures** to stabilize due to a combination of:
- Missing foundational planning
- Region misconfiguration
- Incorrect resource creation order
- Incremental "hole plugging" instead of holistic fixes

**Key Lesson**: Terraform requires upfront planning and validation. The cost of "just trying it" is significantly higher than the cost of planning first.

---

## Chronological Missteps

### 1. No State Management from Day 1

**What Happened**:
- Resources were created manually or via Terraform with local state
- When S3 backend was added later, existing resources weren't in state
- Every `terraform apply` tried to recreate existing resources

**Error Messages**:
```
ResourceExistsException: Secret already exists
BucketAlreadyExists: dev-sentiment-lambda-deployments
EntityAlreadyExists: Role with name dev-ingestion-lambda-role already exists
```

**Root Cause**: Started creating infrastructure before establishing state management strategy.

**Prevention**:
- [ ] Create S3 backend FIRST, before any other resources
- [ ] Run bootstrap in a fresh AWS account to validate
- [ ] Never manually create resources that Terraform will manage

---

### 2. AWS Region Mismatch

**What Happened**:
- Local AWS CLI configured for `us-west-2`
- Terraform provider and CI configured for `us-east-1`
- Local `aws` commands returned empty results while CI saw existing resources
- Led to confusion about what resources actually existed

**How It Manifested**:
```bash
$ aws logs describe-log-groups --log-group-name-prefix "/aws/lambda/dev"
{"logGroups": []}  # Empty because looking in us-west-2

$ aws logs describe-log-groups --log-group-name-prefix "/aws/lambda/dev" --region us-east-1
/aws/lambda/dev-sentiment-analysis
/aws/lambda/dev-sentiment-dashboard
/aws/lambda/dev-sentiment-ingestion
```

**Root Cause**: No validation that local environment matched deployment target.

**Prevention**:
- [ ] Add to project setup: `aws configure set region us-east-1`
- [ ] Add region check in CLAUDE.md or README
- [ ] Add CI step to validate region:
  ```yaml
  - name: Validate AWS Region
    run: |
      if [ "$AWS_REGION" != "us-east-1" ]; then
        echo "::error::Region mismatch"
        exit 1
      fi
  ```

---

### 3. Wrong Resource Creation Order in CI

**What Happened**:
- Workflow uploaded Lambda packages to S3 AFTER Terraform apply
- Terraform tried to create Lambda functions referencing S3 objects that didn't exist yet

**Error Message**:
```
InvalidParameterValueException: Error occurred while GetObject.
S3 Error Code: NoSuchKey. S3 Error Message: The specified key does not exist.
```

**Correct Order**:
1. Package Lambda functions → zip files
2. Upload to S3 → objects exist
3. Terraform apply → creates Lambda referencing existing S3 objects
4. Update Lambda code → publishes new version

**Root Cause**: Didn't trace the dependency graph of resources before writing workflow.

**Prevention**:
- [ ] Draw dependency diagram before writing workflow
- [ ] Ask: "What must exist before X can be created?"
- [ ] Validate workflow order on paper first

---

### 4. Missing GitHub Secrets

**What Happened**:
- Workflow referenced `${{ secrets.DEPLOYMENT_BUCKET }}`
- Secret wasn't configured in repository settings
- S3 upload failed with empty bucket name

**Error Message**:
```
Invalid bucket name "": Bucket name must match the regex...
```

**Root Cause**: No checklist of required secrets before first CI run.

**Prevention**:
- [ ] Document all required secrets in README
- [ ] Validate secrets exist before workflow runs
- [ ] Add workflow step to check for required secrets:
  ```yaml
  - name: Validate secrets
    run: |
      if [ -z "${{ secrets.DEPLOYMENT_BUCKET }}" ]; then
        echo "::error::DEPLOYMENT_BUCKET secret not set"
        exit 1
      fi
  ```

---

### 5. Partial Applies Creating Orphaned Resources

**What Happened**:
- CI `terraform apply` partially succeeded before failing
- Created some resources (log groups, backup plans) but not in local state
- Next run failed because resources existed but weren't imported

**Error Messages**:
```
ResourceAlreadyExistsException: The specified log group already exists
AlreadyExistsException: Backup plan with the same plan document already exists
```

**Root Cause**: Terraform apply is not atomic - partial failure leaves infrastructure in inconsistent state.

**Prevention**:
- [ ] Always run `terraform plan` locally before pushing
- [ ] After CI failure, run `terraform refresh` locally to sync state
- [ ] Consider using `-target` for initial resource creation to control order
- [ ] Have an import script ready for recovery

---

### 6. State Lock Issues

**What Happened**:
- CI runs held state locks that weren't released on failure
- Subsequent runs failed waiting for locks
- Had to manually force-unlock

**Error Message**:
```
Error acquiring the state lock
ConditionalCheckFailedException: The conditional request failed
Lock Info:
  ID: a78a89e4-9f36-9823-b9f8-c30a5abc3e92
  Operation: OperationTypePlan
```

**Root Cause**: No automated handling of stale locks in CI.

**Prevention**:
- [x] Added stale lock detection (>1 hour old)
- [x] Added `lock-timeout=5m` to plan and apply
- [x] Added `workflow_dispatch` with force_unlock option
- [x] Added concurrency group to prevent parallel runs

---

### 7. S3 Key Path Mismatch

**What Happened**:
- Terraform configuration defined S3 keys as `ingestion/lambda.zip`
- Workflow uploaded to `lambdas/dev/ingestion.zip`
- Lambda creation failed because S3 object didn't exist at expected path

**Error Message**:
```
InvalidParameterValueException: Error occurred while GetObject.
S3 Error Code: NoSuchKey. S3 Error Message: The specified key does not exist.
```

**Root Cause**: Workflow was written without checking what paths Terraform expected.

**Prevention**:
- [ ] Check Terraform `s3_key` values before writing upload commands
- [ ] Add comment in workflow referencing Terraform config
- [ ] Consider using Terraform outputs for S3 paths

---

### 8. Incremental "Hole Plugging" Approach

**What Happened**:
- Each CI failure revealed one new issue
- Fixed that issue, pushed, hit next issue
- Resulted in 10+ commits that each fixed one thing

**Why This Is Bad**:
- Looks unprofessional in git history
- Each cycle takes 2-3 minutes (CI run time)
- Frustrating and demoralizing
- Shows lack of planning

**What Should Have Happened**:
1. Run full `terraform plan` locally first
2. Verify all resources can be created
3. Check all secrets are configured
4. Validate workflow order matches dependency graph
5. THEN push to CI

**Prevention**:
- [ ] Use pre-deployment checklist (see below)
- [ ] Never push Terraform changes without local validation
- [ ] Treat first CI run as "validation complete" not "let's see what breaks"

---

## Pre-Deployment Checklist

Use this checklist BEFORE pushing any Terraform CI changes:

### Environment Validation
- [ ] `aws configure get region` returns expected region (us-east-1)
- [ ] `terraform init` completes without errors
- [ ] `terraform validate` passes
- [ ] `terraform plan` shows expected changes (no surprises)

### State Management
- [ ] S3 backend bucket exists and is accessible
- [ ] S3 lock file exists
- [ ] No stale locks in lock table
- [ ] Local state matches remote state (`terraform refresh`)

### GitHub Configuration
- [ ] All required secrets are set in repository settings:
  - [ ] `AWS_ACCESS_KEY_ID`
  - [ ] `AWS_SECRET_ACCESS_KEY`
  - [ ] `AWS_REGION`
  - [ ] `DEPLOYMENT_BUCKET`
- [ ] Workflow file syntax is valid

### Resource Dependencies
- [ ] S3 bucket exists before Lambda packages are uploaded
- [ ] Lambda packages exist in S3 before Lambda functions are created
- [ ] IAM roles exist before Lambda functions reference them
- [ ] SNS topics exist before subscriptions are created

### Import Requirements
- [ ] All existing AWS resources are imported into Terraform state
- [ ] Run import script if resources were created outside Terraform
- [ ] Verify with `terraform plan` - should show no "already exists" errors

---

## Commands for Recovery

### Check for Existing Resources
```bash
# Check region first!
aws configure get region

# List resources that might need importing
aws logs describe-log-groups --log-group-name-prefix "/aws/lambda/dev" --region us-east-1
aws backup list-backup-plans --region us-east-1
aws dynamodb list-tables --region us-east-1
```

### Sync State After Failure
```bash
cd infrastructure/terraform
terraform refresh -var="environment=dev"
terraform plan -var="environment=dev"
```

### Force Unlock Stale Lock
```bash
# Get lock ID from error message
terraform force-unlock -force <LOCK_ID>
```

### Import Missing Resource
```bash
terraform import -var="environment=dev" "<RESOURCE_ADDRESS>" "<RESOURCE_ID>"

# Examples:
terraform import -var="environment=dev" "module.analysis_lambda.aws_cloudwatch_log_group.lambda" "/aws/lambda/dev-sentiment-analysis"
terraform import -var="environment=dev" "module.dynamodb.aws_backup_plan.dynamodb_daily" "9bdcff2e-d40e-41ff-9b8e-ea1e4441c976"
```

---

## Key Takeaways

1. **Terraform is not forgiving** - It requires exact state synchronization. There's no "close enough."

2. **Plan before you apply** - Every minute spent planning saves 10 minutes debugging CI failures.

3. **Local validation is mandatory** - Never push Terraform changes without running `plan` locally first.

4. **Region matters everywhere** - A single region mismatch can cause hours of confusion.

5. **Document your secrets** - CI will fail silently if secrets are missing.

6. **Dependency order is critical** - Resources must be created in the right order, and the workflow must reflect this.

7. **Partial applies are dangerous** - Always be prepared to import orphaned resources.

8. **Embrace the learning** - These missteps are valuable lessons. Document them, don't hide them.

---

## Additional Lessons (Post-Stabilization Audit)

### 9. Test-Driven vs Test-Adjusted Development

**What Happened**:
- When tests failed, we adjusted test expectations to match observed behavior
- Instead of investigating whether the behavior was correct
- Example: Deduplication test expected 4 new items, got 2, changed expectation

**Commit Example**: 0062d8d
```python
# Was: 4 new, 0 duplicates
# Now: 2 new, 2 duplicates
# Comment: "Same articles returned for both tags"
```

**Why This Is Bad**:
- Passing tests don't mean correct behavior
- Hides potential bugs in production
- Makes tests less trustworthy

**Root Cause**: Pressure to pass CI, treating green checkmark as goal instead of correct behavior.

**Prevention**:
- [ ] When changing test expectations, add comment explaining WHY behavior is correct
- [ ] If unsure, mark with `# TODO: Verify this is correct behavior`
- [ ] Review test changes in PRs with same scrutiny as code changes

---

### 10. Lint Suppression Debt

**What Happened**:
- Added `noqa: E402` comments to 10+ imports instead of restructuring code
- Blanket ignored F841 (unused variables) in all tests
- Filtered all deprecation warnings from moto/boto

**Root Cause**: Treating linting as checkbox, not as code quality signal.

**Prevention**:
- [ ] For every `noqa`, create a tech debt item
- [ ] Set SLA for removing `noqa` comments
- [ ] Review new lint ignores in pyproject.toml carefully
- [ ] Address specific deprecation warnings, not blanket ignore

---

### 11. Dependency Major Version Jumps

**What Happened**:
- Jumped moto from 4.2.0 to 5.0.0 to get one feature (mock_aws decorator)
- Didn't check if other tests were compatible with the new API

**Commit**: 1f2c1ae

**Root Cause**: Quick fix without reading changelog.

**Prevention**:
- [ ] Read changelog for major version bumps
- [ ] Test locally before pushing dependency changes
- [ ] Consider pinning exact versions for test dependencies

---

## Technical Debt

### TD-001: Lambda Function URL CORS allow_methods Wildcard

**Location**: `infrastructure/terraform/main.tf` line ~230

**Issue**: Using `["*"]` for `allow_methods` instead of specific methods `["GET", "OPTIONS"]`

**Why**: The specific methods list caused a validation error:
```
Value '[GET, OPTIONS]' at 'cors.allowMethods' failed to satisfy constraint
```

**Risk**: Wildcard allows all HTTP methods (POST, PUT, DELETE, etc.) when only GET and OPTIONS are needed for the dashboard.

**Resolution**: Investigate if this is:
1. AWS provider version issue
2. Terraform version issue
3. Specific AWS API limitation

Should be fixed to use specific methods for security best practices.

**Priority**: Medium - Security concern for production

---

## References

- [Terraform Import Documentation](https://developer.hashicorp.com/terraform/cli/import)
- [Terraform State Lock](https://developer.hashicorp.com/terraform/language/state/locking)
- [AWS Provider Region Configuration](https://registry.terraform.io/providers/hashicorp/aws/latest/docs#region)
- [GitHub Actions Secrets](https://docs.github.com/en/actions/security-guides/encrypted-secrets)

---

*This document was created after experiencing these issues firsthand. The goal is transparency and learning, not perfection.*
