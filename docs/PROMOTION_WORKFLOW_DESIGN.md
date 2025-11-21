# Promotion Workflow Design: Dev → Preprod → Prod

**Date**: 2025-11-20
**Status**: DESIGN PHASE
**Purpose**: Complete architectural design for automated promotion pipeline

---

## Design Goals

1. **Dependabot flows automatically to prod** (security updates without human delay)
2. **Human PRs require manual approval** for preprod→prod promotion
3. **Every stage has rollback capability**
4. **Credentials isolated per environment** (preprod can't touch prod)
5. **Infrastructure mirrors production** (preprod = prod rehearsal)
6. **Failures block promotion** (never promote broken code)
7. **Interview-ready narrative** (demonstrates production thinking)

---

## High-Level Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                         CODE CHANGES                                 │
└─────────────────────────────────────────────────────────────────────┘
                          │
                          ├──────────────┬──────────────┐
                          ▼              ▼              ▼
                    ┌──────────┐  ┌──────────┐  ┌──────────┐
                    │Human PR  │  │Dependabot│  │Schedule  │
                    │          │  │Security  │  │(weekly)  │
                    └──────────┘  └──────────┘  └──────────┘
                          │              │              │
                          └──────────────┴──────────────┘
                                      │
                                      ▼
┌─────────────────────────────────────────────────────────────────────┐
│                         STAGE 1: DEV CI                              │
│  Trigger: Every PR + every merge to main                             │
│  Tests: Unit + E2E (mocked AWS)                                      │
│  Cost: $0                                                            │
│  Duration: ~2-5 minutes                                              │
│  Gate: Required status check (branch protection)                     │
└─────────────────────────────────────────────────────────────────────┘
                          │
                    ┌─────┴─────┐
                    │   PASS?   │
                    └─────┬─────┘
                          │ YES
                          ▼
                  ┌───────────────┐
                  │  PR Mergeable │
                  └───────────────┘
                          │
              ┌───────────┴───────────┐
              │                       │
              ▼ Dependabot            ▼ Human
      ┌──────────────┐        ┌──────────────┐
      │ Auto-merge   │        │ Manual merge │
      │ (if approved)│        │ (requires    │
      │              │        │  review)     │
      └──────────────┘        └──────────────┘
              │                       │
              └───────────┬───────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────────────────┐
│                    STAGE 2: PREPROD DEPLOY                           │
│  Trigger: Merge to main (automatic)                                  │
│  Actions:                                                            │
│    1. Package Lambda functions                                       │
│    2. Upload to S3 (preprod bucket)                                  │
│    3. Terraform apply (preprod backend)                              │
│    4. Run integration tests (REAL preprod AWS)                       │
│  Cost: ~$1-2 per run                                                 │
│  Duration: ~5-10 minutes                                             │
│  Gate: None (automatic on merge)                                     │
└─────────────────────────────────────────────────────────────────────┘
                          │
                    ┌─────┴─────┐
                    │   PASS?   │
                    └─────┬─────┘
                          │
              ┌───────────┴───────────┐
              │ NO                    │ YES
              ▼                       ▼
      ┌──────────────┐        ┌──────────────────────┐
      │ BLOCK        │        │ Create deployment    │
      │ Notify team  │        │ artifact             │
      │ Manual fix   │        │ (Git SHA + packages) │
      └──────────────┘        └──────────────────────┘
                                      │
                          ┌───────────┴───────────┐
                          │                       │
                          ▼ Dependabot            ▼ Human
              ┌───────────────────┐   ┌──────────────────────┐
              │ Auto-promote      │   │ GATE: Manual approve │
              │ (no human gate)   │   │ GitHub Environment:  │
              │                   │   │ "production"         │
              └───────────────────┘   │ Required reviewers   │
                          │           └──────────────────────┘
                          │                       │
                          └───────────┬───────────┘
                                      │ Approved
                                      ▼
┌─────────────────────────────────────────────────────────────────────┐
│                     STAGE 3: PROD DEPLOY                             │
│  Trigger: Manual approval (human) OR auto (Dependabot)               │
│  Actions:                                                            │
│    1. Use SAME Lambda packages from preprod (artifact promotion)     │
│    2. Upload to S3 (prod bucket)                                     │
│    3. Terraform apply (prod backend)                                 │
│    4. Run canary test (health check only)                            │
│    5. Monitor CloudWatch alarms (5 min observation)                  │
│  Cost: Varies by usage                                               │
│  Duration: ~3-5 minutes                                              │
│  Gate: GitHub Environment "production" (conditional)                 │
└─────────────────────────────────────────────────────────────────────┘
                          │
                    ┌─────┴─────┐
                    │   PASS?   │
                    └─────┬─────┘
                          │
              ┌───────────┴───────────┐
              │ NO                    │ YES
              ▼                       ▼
      ┌──────────────┐        ┌──────────────┐
      │ ROLLBACK     │        │ ✅ SUCCESS   │
      │ Revert to    │        │ Update docs  │
      │ previous     │        │ Notify team  │
      │ Terraform    │        └──────────────┘
      │ state        │
      └──────────────┘
```

---

## Key Decision: Dependabot vs Human Gating

### The Challenge

How do we allow Dependabot to auto-promote to prod (for security patches) while requiring manual approval for human feature PRs?

### Solution: GitHub Environments + Conditional Workflows

**GitHub Environments Configuration**:

1. **Create Environment: `preprod`**
   - No required reviewers (automatic deployment)
   - Secrets: `PREPROD_*` (credentials)

2. **Create Environment: `production`**
   - Required reviewers: `@traylorre` (or team)
   - **Bypass protection**: Enable for Dependabot bot account
   - Secrets: `PROD_*` (credentials)

**Workflow Logic**:

```yaml
# .github/workflows/promote-to-prod.yml

on:
  workflow_run:
    workflows: ["Promote to Preprod"]
    types: [completed]
    branches: [main]

jobs:
  promote:
    runs-on: ubuntu-latest
    environment:
      # CRITICAL: Conditional environment based on PR author
      name: ${{ github.event.workflow_run.actor.login == 'dependabot[bot]' && 'production-auto' || 'production' }}

    steps:
      - name: Deploy to production
        # ... deployment steps
```

**Environment Configurations**:

- `production-auto`: No required reviewers (Dependabot uses this)
- `production`: Required reviewers (humans use this)

**How GitHub determines which environment**:
- PR from `dependabot[bot]` → `production-auto` → No gate → Auto-deploy
- PR from human → `production` → Manual approval required → Waits for @traylorre

---

## Artifact Promotion Strategy

### Problem

Building Lambda packages multiple times introduces risk:
- Dev builds package A
- Preprod builds package B (slightly different due to timestamp/randomness)
- Prod builds package C

**If preprod passes but prod uses different package → untested code in prod!**

### Solution: Build Once, Promote Through Environments

```
┌──────────────────────────────────────────────────────────────┐
│ STAGE 1: Build (on merge to main)                            │
├──────────────────────────────────────────────────────────────┤
│ Actions:                                                      │
│   1. Package Lambda functions                                │
│   2. Tag with Git SHA: lambda-${GITHUB_SHA}.zip              │
│   3. Upload to artifact storage (GitHub Artifacts)           │
│   4. Store metadata: { sha, timestamp, author }              │
└──────────────────────────────────────────────────────────────┘
                          │
                          ▼
┌──────────────────────────────────────────────────────────────┐
│ STAGE 2: Deploy to Preprod                                   │
├──────────────────────────────────────────────────────────────┤
│ Actions:                                                      │
│   1. Download artifact: lambda-${GITHUB_SHA}.zip             │
│   2. Upload to S3: s3://...-preprod/lambda-${GITHUB_SHA}.zip │
│   3. Terraform apply with var: lambda_version = ${GITHUB_SHA}│
│   4. Lambda uses: s3://.../lambda-${GITHUB_SHA}.zip          │
│   5. Run integration tests                                   │
│   6. If PASS: Tag artifact as "preprod-validated"            │
└──────────────────────────────────────────────────────────────┘
                          │
                          ▼
┌──────────────────────────────────────────────────────────────┐
│ STAGE 3: Deploy to Prod                                      │
├──────────────────────────────────────────────────────────────┤
│ Actions:                                                      │
│   1. Download SAME artifact: lambda-${GITHUB_SHA}.zip        │
│   2. Upload to S3: s3://...-prod/lambda-${GITHUB_SHA}.zip    │
│   3. Terraform apply with SAME var: lambda_version = $SHA    │
│   4. Lambda uses: EXACT SAME PACKAGE as preprod              │
│   5. Run canary test                                         │
│   6. If PASS: Tag artifact as "prod-deployed"                │
└──────────────────────────────────────────────────────────────┘
```

**Benefits**:
- ✅ Preprod tests the EXACT code that will run in prod
- ✅ No "works in preprod but fails in prod due to build variance"
- ✅ Audit trail: Git SHA links code → artifact → deployment
- ✅ Rollback: Just redeploy previous SHA's artifact

**Implementation**:

```yaml
# .github/workflows/build-and-deploy-preprod.yml

jobs:
  build:
    runs-on: ubuntu-latest
    outputs:
      artifact-sha: ${{ steps.package.outputs.sha }}

    steps:
      - name: Package Lambdas
        id: package
        run: |
          SHA="${GITHUB_SHA:0:7}"
          echo "sha=$SHA" >> $GITHUB_OUTPUT

          # Package each Lambda
          cd src/lambdas/ingestion
          zip -r ../../../packages/ingestion-${SHA}.zip .
          cd ../../..

          # Repeat for analysis, dashboard

      - name: Upload artifacts
        uses: actions/upload-artifact@v4
        with:
          name: lambda-packages-${{ steps.package.outputs.sha }}
          path: packages/
          retention-days: 90  # Keep for 3 months

  deploy-preprod:
    needs: build
    runs-on: ubuntu-latest
    environment: preprod

    steps:
      - name: Download artifacts
        uses: actions/download-artifact@v4
        with:
          name: lambda-packages-${{ needs.build.outputs.artifact-sha }}
          path: packages/

      - name: Upload to S3 (preprod)
        run: |
          SHA="${{ needs.build.outputs.artifact-sha }}"
          aws s3 cp packages/ingestion-${SHA}.zip \
            s3://sentiment-analyzer-lambda-packages-preprod/ingestion/${SHA}/lambda.zip

      - name: Terraform apply
        run: |
          terraform apply \
            -var="lambda_version=${{ needs.build.outputs.artifact-sha }}" \
            -var-file=preprod.tfvars \
            -auto-approve

  deploy-prod:
    needs: [build, deploy-preprod]
    runs-on: ubuntu-latest
    environment: production  # Requires manual approval for human PRs

    steps:
      - name: Download SAME artifacts
        uses: actions/download-artifact@v4
        with:
          name: lambda-packages-${{ needs.build.outputs.artifact-sha }}
          path: packages/

      - name: Upload to S3 (prod)
        run: |
          SHA="${{ needs.build.outputs.artifact-sha }}"
          aws s3 cp packages/ingestion-${SHA}.zip \
            s3://sentiment-analyzer-lambda-packages-prod/ingestion/${SHA}/lambda.zip

      - name: Terraform apply
        run: |
          terraform apply \
            -var="lambda_version=${{ needs.build.outputs.artifact-sha }}" \
            -var-file=prod.tfvars \
            -auto-approve
```

---

## Credential Separation Design

### Current State (Assumed UNSAFE)

```
┌─────────────────────────────────────────────────────┐
│ GitHub Secrets (Repository-wide)                    │
├─────────────────────────────────────────────────────┤
│ AWS_ACCESS_KEY_ID        → Same for all envs       │
│ AWS_SECRET_ACCESS_KEY    → Same for all envs       │
│ NEWSAPI_KEY              → Same for all envs       │
└─────────────────────────────────────────────────────┘
              │                    │
              ▼                    ▼
        ┌──────────┐          ┌──────────┐
        │ Preprod  │          │   Prod   │
        │ Can read │          │ Can read │
        │ prod     │          │ preprod  │
        │ secrets! │          │ secrets! │
        └──────────┘          └──────────┘
```

**Risk**: Compromised preprod → attacker has prod credentials

### Proposed State (SECURE)

```
┌────────────────────────────────────────────────────────────────┐
│ GitHub Environments (scoped secrets)                            │
├────────────────────────────────────────────────────────────────┤
│ Environment: preprod                                            │
│   PREPROD_AWS_ACCESS_KEY_ID      → IAM user: preprod-deployer │
│   PREPROD_AWS_SECRET_ACCESS_KEY  → Limited to *-preprod-*     │
│   PREPROD_NEWSAPI_SECRET_ARN     → arn:.../preprod-newsapi    │
├────────────────────────────────────────────────────────────────┤
│ Environment: production                                         │
│   PROD_AWS_ACCESS_KEY_ID         → IAM user: prod-deployer    │
│   PROD_AWS_SECRET_ACCESS_KEY     → Limited to *-prod-*        │
│   PROD_NEWSAPI_SECRET_ARN        → arn:.../prod-newsapi       │
└────────────────────────────────────────────────────────────────┘
              │                                │
              ▼                                ▼
        ┌──────────┐                      ┌──────────┐
        │ Preprod  │                      │   Prod   │
        │ Can ONLY │                      │ Can ONLY │
        │ read     │                      │ read     │
        │ preprod  │                      │ prod     │
        │ secrets  │                      │ secrets  │
        └──────────┘                      └──────────┘
```

### IAM Policy Design

**Preprod IAM User**: `sentiment-analyzer-preprod-deployer`

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "PreprodResourcesOnly",
      "Effect": "Allow",
      "Action": [
        "dynamodb:*",
        "lambda:*",
        "s3:*",
        "sns:*",
        "sqs:*",
        "secretsmanager:*",
        "events:*",
        "iam:*",
        "logs:*"
      ],
      "Resource": [
        "arn:aws:dynamodb:*:*:table/preprod-*",
        "arn:aws:lambda:*:*:function:preprod-*",
        "arn:aws:s3:::*-preprod-*",
        "arn:aws:s3:::*-preprod-*/*",
        "arn:aws:sns:*:*:preprod-*",
        "arn:aws:sqs:*:*:preprod-*",
        "arn:aws:secretsmanager:*:*:secret:preprod-*",
        "arn:aws:events:*:*:rule/preprod-*",
        "arn:aws:iam::*:role/preprod-*",
        "arn:aws:logs:*:*:log-group:/aws/lambda/preprod-*"
      ]
    },
    {
      "Sid": "TerraformStateAccess",
      "Effect": "Allow",
      "Action": [
        "s3:GetObject",
        "s3:PutObject"
      ],
      "Resource": "arn:aws:s3:::sentiment-analyzer-terraform-state/preprod/*"
    },
    {
      "Sid": "TerraformLockAccess",
      "Effect": "Allow",
      "Action": [
        "dynamodb:GetItem",
        "dynamodb:PutItem",
        "dynamodb:DeleteItem"
      ],
      "Resource": "arn:aws:dynamodb:*:*:table/terraform-state-lock-preprod"
    },
    {
      "Sid": "DenyProdResources",
      "Effect": "Deny",
      "Action": "*",
      "Resource": [
        "arn:aws:dynamodb:*:*:table/prod-*",
        "arn:aws:lambda:*:*:function:prod-*",
        "arn:aws:s3:::*-prod-*",
        "arn:aws:s3:::*-prod-*/*"
      ]
    }
  ]
}
```

**Prod IAM User**: `sentiment-analyzer-prod-deployer`

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "ProdResourcesOnly",
      "Effect": "Allow",
      "Action": [
        "dynamodb:*",
        "lambda:*",
        "s3:*",
        "sns:*",
        "sqs:*",
        "secretsmanager:*",
        "events:*",
        "iam:*",
        "logs:*"
      ],
      "Resource": [
        "arn:aws:dynamodb:*:*:table/prod-*",
        "arn:aws:lambda:*:*:function:prod-*",
        "arn:aws:s3:::*-prod-*",
        "arn:aws:s3:::*-prod-*/*",
        "arn:aws:sns:*:*:prod-*",
        "arn:aws:sqs:*:*:prod-*",
        "arn:aws:secretsmanager:*:*:secret:prod-*",
        "arn:aws:events:*:*:rule/prod-*",
        "arn:aws:iam::*:role/prod-*",
        "arn:aws:logs:*:*:log-group:/aws/lambda/prod-*"
      ]
    },
    {
      "Sid": "TerraformStateAccess",
      "Effect": "Allow",
      "Action": [
        "s3:GetObject",
        "s3:PutObject"
      ],
      "Resource": "arn:aws:s3:::sentiment-analyzer-terraform-state/prod/*"
    },
    {
      "Sid": "TerraformLockAccess",
      "Effect": "Allow",
      "Action": [
        "dynamodb:GetItem",
        "dynamodb:PutItem",
        "dynamodb:DeleteItem"
      ],
      "Resource": "arn:aws:dynamodb:*:*:table/terraform-state-lock-prod"
    },
    {
      "Sid": "DenyPreprodResources",
      "Effect": "Deny",
      "Action": "*",
      "Resource": [
        "arn:aws:dynamodb:*:*:table/preprod-*",
        "arn:aws:lambda:*:*:function:preprod-*",
        "arn:aws:s3:::*-preprod-*",
        "arn:aws:s3:::*-preprod-*/*"
      ]
    }
  ]
}
```

### AWS Secrets Manager Strategy

**Create separate secrets**:

```bash
# Preprod NewsAPI key
aws secretsmanager create-secret \
  --name preprod-newsapi-key \
  --description "NewsAPI key for preprod environment (free tier)" \
  --secret-string '{"api_key":"PREPROD_KEY_HERE"}' \
  --region us-east-1

# Prod NewsAPI key
aws secretsmanager create-secret \
  --name prod-newsapi-key \
  --description "NewsAPI key for production environment (paid tier)" \
  --secret-string '{"api_key":"PROD_KEY_HERE"}' \
  --region us-east-1
```

**Terraform configuration**:

```hcl
# modules/lambda/variables.tf
variable "newsapi_secret_name" {
  description = "Name of Secrets Manager secret for NewsAPI key"
  type        = string
}

# preprod.tfvars
newsapi_secret_name = "preprod-newsapi-key"

# prod.tfvars
newsapi_secret_name = "prod-newsapi-key"
```

**Benefits**:
- ✅ Preprod can't exhaust prod API quota
- ✅ Compromised preprod key doesn't affect prod
- ✅ Can rotate preprod key without touching prod
- ✅ Cost: $0 (no additional Secrets Manager charges - same count)

---

## Failure Recovery Design

### Failure Scenarios and Responses

#### Scenario 1: Dev Tests Fail

```
PR created → Dev CI runs → Tests FAIL
```

**Response**: Automatic
- ❌ PR cannot merge (branch protection)
- Developer fixes code
- Push to PR branch
- Dev CI re-runs automatically
- Loop until PASS

**Rollback**: Not needed (never merged)

---

#### Scenario 2: Preprod Deployment Fails (Terraform)

```
Merge to main → Preprod deploy workflow → Terraform apply FAILS
```

**Causes**:
- AWS API errors
- Terraform state lock held
- Resource quota exceeded
- Invalid configuration

**Response**: Semi-automatic
1. Workflow marks job as FAILED (red X)
2. Preprod remains in previous state (Terraform atomicity)
3. GitHub notification sent
4. Manual investigation required

**Recovery**:
```bash
# Check Terraform state
cd infrastructure/terraform
terraform init -backend-config=backend-preprod.hcl
terraform state list
terraform plan -var-file=preprod.tfvars

# If state lock held
terraform force-unlock <LOCK_ID>

# If quota issue
# Increase AWS quota or reduce resources in preprod.tfvars

# Re-run workflow
gh workflow run preprod-validation.yml
```

**Rollback**:
```bash
# Revert to previous state
git revert HEAD
git push origin main
# Workflow auto-runs with previous config
```

---

#### Scenario 3: Preprod Tests Fail (Integration)

```
Preprod deployed OK → Integration tests run → Tests FAIL
```

**Causes**:
- Infrastructure deployed but misconfigured
- Lambda runtime errors
- DynamoDB schema mismatch
- Secrets not accessible

**Response**: Semi-automatic
1. Workflow marks job as FAILED
2. Test logs uploaded to GitHub Artifacts
3. Preprod infrastructure remains deployed (but broken)
4. Production deployment BLOCKED (no artifact tagged "preprod-validated")

**Recovery**:
```bash
# Option 1: Fix forward
# Fix code, merge to main, preprod redeploys

# Option 2: Rollback
git revert HEAD
git push origin main

# Option 3: Manual investigation
# Check CloudWatch logs
aws logs tail /aws/lambda/preprod-sentiment-ingestion --follow

# Check DynamoDB
aws dynamodb scan --table-name preprod-sentiment-items --limit 10

# Check Secrets
aws secretsmanager get-secret-value --secret-id preprod-newsapi-key
```

**Rollback**:
- Terraform destroy preprod (nuclear option)
- OR: Revert code, redeploy

---

#### Scenario 4: Prod Deployment Fails (Terraform)

```
Manual approval → Prod deploy workflow → Terraform apply FAILS
```

**Causes**:
- AWS API errors
- State drift (manual changes in prod)
- Resource conflicts

**Response**: CRITICAL - Manual intervention required
1. Workflow marks job as FAILED
2. Page on-call engineer
3. DO NOT auto-retry (could make it worse)

**Recovery**:
```bash
# CRITICAL: Prod may be in partial state
cd infrastructure/terraform
terraform init -backend-config=backend-prod.hcl

# Check what applied
terraform state list

# Check what's in AWS
aws dynamodb list-tables | grep prod
aws lambda list-functions | grep prod

# Compare to desired state
terraform plan -var-file=prod.tfvars

# If partial apply:
# Option 1: Complete the apply
terraform apply -var-file=prod.tfvars

# Option 2: Rollback to previous Lambda version
terraform apply -var-file=prod.tfvars -var="lambda_version=PREVIOUS_SHA"
```

**Rollback**:
```bash
# Find previous working SHA
git log --oneline -10

# Redeploy previous version
terraform apply \
  -var-file=prod.tfvars \
  -var="lambda_version=PREVIOUS_SHA" \
  -auto-approve
```

---

#### Scenario 5: Prod Tests Fail (Canary)

```
Prod deployed OK → Canary test → Health check FAILS
```

**Response**: CRITICAL - Immediate rollback
1. Workflow detects canary failure
2. Automatic rollback triggered
3. Page on-call engineer

**Automatic Rollback Workflow**:

```yaml
# .github/workflows/deploy-prod.yml

jobs:
  deploy:
    # ... deployment steps

    - name: Run canary test
      id: canary
      run: |
        # Test health endpoint
        curl -f https://prod-dashboard-url/health || exit 1

    - name: Monitor CloudWatch alarms
      if: steps.canary.outcome == 'success'
      run: |
        # Wait 5 minutes, check for alarms
        sleep 300
        aws cloudwatch describe-alarms \
          --alarm-name-prefix "prod-" \
          --state-value ALARM \
          --query 'MetricAlarms[].AlarmName' \
          --output text > alarms.txt

        if [ -s alarms.txt ]; then
          echo "❌ CloudWatch alarms triggered!"
          cat alarms.txt
          exit 1
        fi

    - name: Rollback on failure
      if: failure()
      run: |
        echo "🚨 ROLLBACK: Deploying previous version"

        # Get previous SHA from git
        PREVIOUS_SHA=$(git log --oneline -2 | tail -1 | cut -d' ' -f1)

        cd infrastructure/terraform
        terraform init -backend-config=backend-prod.hcl
        terraform apply \
          -var-file=prod.tfvars \
          -var="lambda_version=$PREVIOUS_SHA" \
          -auto-approve

        echo "✅ Rollback complete"

    - name: Notify on-call
      if: failure()
      run: |
        # Send SNS notification
        aws sns publish \
          --topic-arn arn:aws:sns:us-east-1:ACCOUNT:prod-alerts \
          --subject "🚨 PROD DEPLOYMENT FAILED - ROLLBACK INITIATED" \
          --message "Deployment of ${{ github.sha }} failed. Rolled back to previous version."
```

---

#### Scenario 6: Dependabot PR Fails Preprod

```
Dependabot PR → Dev PASS → Merge → Preprod deploy PASS → Preprod tests FAIL
```

**Response**: Automatic revert
1. Preprod tests fail
2. Workflow reverts the merge commit
3. Dependabot PR reopened with failure notice
4. Human investigates

**Revert Workflow**:

```yaml
# .github/workflows/preprod-validation.yml

jobs:
  integration-tests:
    # ... test steps

    - name: Revert if Dependabot PR fails
      if: failure() && github.event.head_commit.author.name == 'dependabot[bot]'
      run: |
        git revert HEAD --no-edit
        git push origin main

        # Reopen Dependabot PR
        gh pr reopen ${{ github.event.pull_request.number }} \
          --comment "⚠️ Preprod tests failed. Merge reverted. Please investigate."
```

**Goal**: Dependabot should auto-promote ONLY if all tests pass. If preprod fails, revert immediately.

---

## Terraform Resource Mirroring Verification

### Required Resources (Preprod MUST Match Prod)

| Resource | Terraform Module | Environment Variable | Verified? |
|----------|------------------|---------------------|-----------|
| DynamoDB Table | `aws_dynamodb_table.sentiment_items` | `var.environment` prefix | ⏳ |
| SNS Topic | `aws_sns_topic.analysis_notifications` | `var.environment` prefix | ⏳ |
| SQS Queue (DLQ) | `aws_sqs_queue.analysis_dlq` | `var.environment` prefix | ⏳ |
| Lambda (Ingestion) | `aws_lambda_function.ingestion` | `var.environment` prefix | ⏳ |
| Lambda (Analysis) | `aws_lambda_function.analysis` | `var.environment` prefix | ⏳ |
| Lambda (Dashboard) | `aws_lambda_function.dashboard` | `var.environment` prefix | ⏳ |
| Lambda IAM Roles | `aws_iam_role.lambda_*` | `var.environment` prefix | ⏳ |
| S3 Bucket (packages) | `aws_s3_bucket.lambda_packages` | `var.environment` suffix | ⏳ |
| EventBridge Rule | `aws_cloudwatch_event_rule.ingestion_schedule` | `var.environment` prefix | ⏳ |
| CloudWatch Alarms | `aws_cloudwatch_metric_alarm.*` | `var.environment` prefix | ⏳ |
| Secrets Manager | External (created manually) | Separate ARNs | ⏳ |

### Verification Checklist

**Step 1: Review Terraform modules** (next task)
- [ ] Confirm all resources use `var.environment` in name
- [ ] Confirm no hardcoded "dev" or "prod" strings
- [ ] Confirm S3 bucket names unique per environment
- [ ] Confirm IAM roles scoped per environment

**Step 2: Dry-run preprod deployment**
- [ ] `terraform plan -var-file=preprod.tfvars` (review output)
- [ ] Verify resource names: `preprod-sentiment-items`, not `prod-*`
- [ ] Verify IAM policies reference preprod resources only

**Step 3: Deploy preprod and verify**
- [ ] `terraform apply -var-file=preprod.tfvars`
- [ ] `aws dynamodb list-tables | grep preprod`
- [ ] `aws lambda list-functions | grep preprod`
- [ ] `aws s3 ls | grep preprod`

---

## CloudWatch Alarms Design (Preprod)

### Required Alarms

Preprod MUST have same alarms as prod (same thresholds):

1. **Lambda Errors** (per function)
   - Metric: `Errors`
   - Threshold: > 5 errors in 5 minutes
   - Action: SNS notification

2. **Lambda Throttles** (per function)
   - Metric: `Throttles`
   - Threshold: > 0
   - Action: SNS notification

3. **DynamoDB Throttles**
   - Metric: `UserErrors` (ProvisionedThroughputExceededException)
   - Threshold: > 10 in 5 minutes
   - Action: SNS notification

4. **DLQ Messages**
   - Metric: `ApproximateNumberOfMessagesVisible`
   - Threshold: > 5 messages
   - Action: SNS notification (analysis retries piling up)

5. **Cost Anomaly**
   - AWS Cost Anomaly Detection
   - Threshold: > $50/day (preprod should be ~$1/day)
   - Action: SNS notification (runaway resources)

**Implementation**:

```hcl
# modules/monitoring/alarms.tf

resource "aws_cloudwatch_metric_alarm" "lambda_errors" {
  for_each = toset(["ingestion", "analysis", "dashboard"])

  alarm_name          = "${var.environment}-sentiment-${each.key}-errors"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 1
  metric_name         = "Errors"
  namespace           = "AWS/Lambda"
  period              = 300
  statistic           = "Sum"
  threshold           = 5
  alarm_description   = "Lambda ${each.key} error count exceeded"
  alarm_actions       = [aws_sns_topic.alerts.arn]

  dimensions = {
    FunctionName = "${var.environment}-sentiment-${each.key}"
  }
}
```

**SNS Topic** (per environment):

```hcl
resource "aws_sns_topic" "alerts" {
  name = "${var.environment}-sentiment-alerts"
}

resource "aws_sns_topic_subscription" "email" {
  topic_arn = aws_sns_topic.alerts.arn
  protocol  = "email"
  endpoint  = var.alert_email  # From tfvars
}
```

**tfvars**:

```hcl
# preprod.tfvars
alert_email = "your-email+preprod@example.com"

# prod.tfvars
alert_email = "your-email+prod@example.com"
```

---

## Canary Test Design

### Purpose

Test the health endpoint that will be used for prod monitoring BEFORE deploying to prod.

### Test Structure

```python
# tests/integration/test_canary_preprod.py
"""
Canary Test for Preprod

This is a META-TEST: We're testing the canary itself.

The canary is a simple health check that will run hourly in prod
to validate the system is operational. If this test fails in preprod,
the canary is broken and we should NOT deploy to prod (we'd have no monitoring).
"""

import requests
import pytest
import os


class TestCanaryPreprod:
    """Test the production canary against preprod."""

    def test_health_endpoint_structure(self):
        """
        Verify the health endpoint returns the expected structure.

        This is what the prod canary will check every hour.
        If this fails, the canary won't work in prod.
        """
        dashboard_url = os.environ["PREPROD_DASHBOARD_URL"]
        api_key = os.environ["PREPROD_DASHBOARD_API_KEY"]

        response = requests.get(
            f"{dashboard_url}/health",
            headers={"X-API-Key": api_key},
            timeout=10,
        )

        # Canary requirement: Must return 200
        assert response.status_code == 200, \
            f"Health check failed with {response.status_code}"

        # Canary requirement: Must have JSON body
        data = response.json()
        assert "status" in data, "Missing 'status' field"
        assert data["status"] == "healthy", f"Status is {data['status']}, not 'healthy'"

        # Canary requirement: Must include version
        assert "version" in data, "Missing 'version' field"
        assert "timestamp" in data, "Missing 'timestamp' field"

    def test_health_endpoint_performance(self):
        """
        Verify the health endpoint responds quickly.

        Prod canary has 10-second timeout. If preprod is slower,
        the prod canary will fail spuriously.
        """
        dashboard_url = os.environ["PREPROD_DASHBOARD_URL"]
        api_key = os.environ["PREPROD_DASHBOARD_API_KEY"]

        import time
        start = time.time()

        response = requests.get(
            f"{dashboard_url}/health",
            headers={"X-API-Key": api_key},
            timeout=10,
        )

        duration = time.time() - start

        assert response.status_code == 200
        assert duration < 5.0, \
            f"Health check took {duration:.2f}s (should be <5s)"

    def test_health_endpoint_without_auth(self):
        """
        Verify the health endpoint rejects requests without API key.

        This ensures we're actually testing authentication, not an open endpoint.
        """
        dashboard_url = os.environ["PREPROD_DASHBOARD_URL"]

        response = requests.get(
            f"{dashboard_url}/health",
            timeout=10,
        )

        assert response.status_code == 401, \
            "Health endpoint should require authentication"
```

### Prod Canary (for reference)

```python
# canary/prod_health_check.py
"""
Production Canary - Runs hourly via EventBridge

If this fails, page on-call immediately.
"""

import requests
import os
import boto3


def lambda_handler(event, context):
    """Check prod health endpoint."""
    dashboard_url = os.environ["PROD_DASHBOARD_URL"]

    # Get API key from Secrets Manager
    secretsmanager = boto3.client("secretsmanager")
    secret = secretsmanager.get_secret_value(
        SecretId=os.environ["DASHBOARD_API_KEY_SECRET_ARN"]
    )
    api_key = json.loads(secret["SecretString"])["api_key"]

    try:
        response = requests.get(
            f"{dashboard_url}/health",
            headers={"X-API-Key": api_key},
            timeout=10,
        )

        if response.status_code != 200:
            raise Exception(f"Health check returned {response.status_code}")

        data = response.json()
        if data.get("status") != "healthy":
            raise Exception(f"Status is {data.get('status')}, not 'healthy'")

        return {
            "statusCode": 200,
            "body": {"message": "Canary passed", "details": data}
        }

    except Exception as e:
        # Alert SNS
        sns = boto3.client("sns")
        sns.publish(
            TopicArn=os.environ["ALERT_TOPIC_ARN"],
            Subject="🚨 PROD CANARY FAILED",
            Message=f"Production health check failed: {str(e)}"
        )

        raise
```

---

## Implementation Phases

### Phase 1: Credential Separation (CRITICAL)
**Duration**: 1-2 hours

1. Create IAM users:
   - `sentiment-analyzer-preprod-deployer`
   - `sentiment-analyzer-prod-deployer`
2. Apply IAM policies (resource scoping)
3. Create separate Secrets Manager secrets:
   - `preprod-newsapi-key`
   - `prod-newsapi-key`
4. Configure GitHub Environments:
   - `preprod` with `PREPROD_*` secrets
   - `production` with `PROD_*` secrets
   - `production-auto` (Dependabot bypass)
5. Update Terraform modules to use `var.newsapi_secret_name`

**Validation**:
- [ ] Preprod credentials cannot access prod resources (test with AWS CLI)
- [ ] Prod credentials cannot access preprod resources

---

### Phase 2: Terraform Resource Verification (CRITICAL)
**Duration**: 2-3 hours

1. Review all Terraform modules for `var.environment` usage
2. `terraform plan -var-file=preprod.tfvars` (dry-run)
3. Verify no resource name collisions
4. Add CloudWatch alarms to modules
5. Deploy preprod: `terraform apply -var-file=preprod.tfvars`
6. Verify all resources created:
   ```bash
   aws dynamodb list-tables | grep preprod
   aws lambda list-functions | grep preprod
   aws s3 ls | grep preprod
   ```

**Validation**:
- [ ] All resources prefixed with `preprod-`
- [ ] CloudWatch alarms exist for preprod
- [ ] SNS topic `preprod-sentiment-alerts` created

---

### Phase 3: Promotion Workflow Implementation (CRITICAL)
**Duration**: 3-4 hours

1. Create `.github/workflows/build-and-promote.yml`
   - Build Lambda packages (tag with Git SHA)
   - Upload to GitHub Artifacts
   - Deploy to preprod (automatic)
   - Run preprod integration tests
   - Tag artifact as "preprod-validated" if pass
2. Create `.github/workflows/deploy-prod.yml`
   - Download artifact from preprod (same SHA)
   - Deploy to prod (manual approval for humans, auto for Dependabot)
   - Run canary test
   - Monitor CloudWatch alarms (5 min)
   - Rollback on failure
3. Configure GitHub branch protection:
   - Require "Tests (Dev)" to pass
4. Configure GitHub Environments:
   - `production`: Required reviewers = @traylorre
   - `production-auto`: No reviewers (Dependabot bypass)

**Validation**:
- [ ] Human PR triggers manual approval gate
- [ ] Dependabot PR auto-promotes (if tests pass)
- [ ] Same Lambda package deployed to preprod and prod
- [ ] Rollback works (manually test)

---

### Phase 4: Failure Recovery Documentation (HIGH)
**Duration**: 1 hour

1. Create `docs/RUNBOOK_FAILURE_RECOVERY.md`
   - Document each failure scenario
   - Recovery commands for each
   - Rollback procedures
2. Update on-call guide with escalation paths

---

### Phase 5: Canary Test (HIGH)
**Duration**: 1 hour

1. Create `tests/integration/test_canary_preprod.py`
2. Add to preprod validation workflow
3. Create `canary/prod_health_check.py` (for future prod deployment)

---

### Phase 6: NewsAPI Mock Expansion (MEDIUM)
**Duration**: 2-3 hours

1. Create `tests/fixtures/newsapi_responses.py`
   - Happy path (current)
   - Empty response (`{"articles": []}`)
   - Missing fields (`url: null`)
   - API error (`{"status": "error", "code": "rateLimited"}`)
   - Bulk (100 articles)
2. Update dev E2E tests to cover each scenario

---

## Summary

This design provides:

1. ✅ **Dependabot auto-promotion** via GitHub Environment bypass
2. ✅ **Human manual gates** via required reviewers
3. ✅ **Credential isolation** via IAM policies and scoped secrets
4. ✅ **Artifact promotion** (build once, deploy everywhere)
5. ✅ **Automatic rollback** on prod canary failure
6. ✅ **Production-mirrored preprod** (same Terraform, different tfvars)
7. ✅ **Comprehensive monitoring** (CloudWatch alarms per environment)
8. ✅ **Failure recovery** (documented runbooks)

**Total Estimated Implementation Time**: 10-14 hours across 6 phases

**Critical Path** (must complete before ANY deployment):
- Phase 1: Credential Separation (1-2 hrs)
- Phase 2: Terraform Verification (2-3 hrs)
- Phase 3: Promotion Workflows (3-4 hrs)

**Total Critical Path**: 6-9 hours

---

## Interview Narrative

> "When designing the promotion pipeline, I identified 8 critical concerns that could cause production failures or security vulnerabilities. Rather than rushing to implementation, I designed the complete architecture first.
>
> The key insight was using **GitHub Environments with conditional bypass** to allow Dependabot security patches to flow automatically to production while requiring manual approval for feature changes. This ensures security updates deploy within hours, not days.
>
> For security, I separated credentials per environment using IAM resource scoping - preprod literally cannot modify prod resources even if compromised. This costs nothing extra but provides defense-in-depth.
>
> For reliability, I implemented **artifact promotion** - the exact Lambda package that passes preprod tests is what deploys to prod, eliminating build variance as a failure mode.
>
> For safety, every stage has automatic rollback: if the prod canary fails, we revert to the previous Git SHA automatically and page on-call. No production downtime.
>
> The entire design took ~3 hours to document, but will save weeks of debugging production incidents from rushed implementation."

---

**NEXT DECISION POINT**: Review this design, then proceed to Phase 1 implementation?
