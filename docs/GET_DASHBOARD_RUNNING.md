# Get Preprod Dashboard Running - Step by Step

**Goal**: Access preprod dashboard to observe metrics BEFORE production deploy

**Context**: Based on lessons learned from 15+ CI failures, we're being methodical about terraform initialization and environment setup.

---

## Prerequisites Checklist

Before running ANY terraform commands:

- [ ] Verify current working directory: `pwd` should show `.../infrastructure/terraform`
- [ ] Verify AWS region configuration
- [ ] Verify backend configuration exists
- [ ] Understand what terraform init does

---

## Step 1: Verify Environment

```bash
# Check current directory
pwd
# Should be: /home/traylorre/projects/sentiment-analyzer-gsk/infrastructure/terraform

# Check AWS region configuration
aws configure get region
# Should return: us-east-1

# If not us-east-1, set it
aws configure set region us-east-1

# Verify with explicit region check
echo $AWS_REGION
aws sts get-caller-identity --region us-east-1
```

**Why**: Lessons Learned #2 - Region mismatch caused hours of confusion

---

## Step 2: Verify Backend Configuration

```bash
# Check backend config file exists
ls -la backend-preprod.hcl

# View backend config
cat backend-preprod.hcl
```

**Expected content**:
```hcl
bucket  = "sentiment-analyzer-terraform-state-218795110243"
key     = "preprod/terraform.tfstate"
region  = "us-east-1"
encrypt = true
```

**Why**: Lessons Learned #1 - State management must be established first

---

## Step 3: Initialize Terraform (Read-Only)

```bash
# Set region environment variable (failsafe)
export AWS_REGION=us-east-1

# Initialize with preprod backend
terraform init -backend-config=backend-preprod.hcl -reconfigure

# Expected output:
# - "Terraform has been successfully initialized!"
# - Backend configured with S3
# - Modules downloaded
```

**What this does**:
- Configures S3 backend for preprod state
- Downloads provider plugins (AWS provider)
- Downloads modules (dynamodb, lambda, monitoring, etc.)
- Does NOT create/modify any resources

**If it fails**:
- Check error message for missing region
- Check error message for S3 bucket access
- Verify AWS credentials are configured

---

## Step 4: Get Dashboard URL (Read-Only)

```bash
# Get preprod outputs from terraform state
terraform output

# OR get specific output
terraform output dashboard_function_url

# OR get as JSON
terraform output -json | jq -r '.dashboard_function_url.value'
```

**Expected output**:
```
https://XXXXXXXXXX.lambda-url.us-east-1.on.aws/
```

**What this does**:
- Reads existing terraform state from S3
- Shows outputs from previous deployment
- Does NOT modify any resources

**If it fails**:
- Error "No outputs found" → Preprod not deployed yet
- Error "Backend not initialized" → Re-run step 3
- Error "Access denied" → Check AWS credentials

---

## Step 5: Get Dashboard API Key

```bash
# Get API key from Secrets Manager
aws secretsmanager get-secret-value \
  --secret-id preprod/sentiment-analyzer/dashboard-api-key \
  --region us-east-1 \
  --query 'SecretString' --output text | jq -r '.api_key'

# Save to environment variable
export PREPROD_DASHBOARD_API_KEY=$(aws secretsmanager get-secret-value \
  --secret-id preprod/sentiment-analyzer/dashboard-api-key \
  --region us-east-1 \
  --query 'SecretString' --output text | jq -r '.api_key')

# Verify
echo "API Key: $PREPROD_DASHBOARD_API_KEY"
```

**What this does**:
- Retrieves secret from AWS Secrets Manager
- Stores in environment variable for use
- Does NOT modify anything

**If it fails**:
- Error "Secret not found" → Preprod secrets not created yet
- Error "Access denied" → Check IAM permissions for Secrets Manager

---

## Step 6: Test Dashboard Health

```bash
# Get dashboard URL from terraform
DASHBOARD_URL=$(terraform output -raw dashboard_function_url)

# Test health endpoint (no auth required)
curl -s https://${DASHBOARD_URL}/health | jq

# Expected response:
# {
#   "status": "healthy",
#   "environment": "preprod",
#   "timestamp": "2025-11-22T...",
#   ...
# }
```

**What this tests**:
- Dashboard Lambda is deployed and active
- Function URL is accessible
- Lambda can respond to requests

**If it fails**:
- HTTP 404 → Dashboard not deployed
- HTTP 500 → Dashboard Lambda error (check CloudWatch logs)
- Connection timeout → Network/VPC issue

---

## Step 7: Test Dashboard API (with Auth)

```bash
# Test metrics endpoint (requires API key)
curl -s -H "X-API-Key: ${PREPROD_DASHBOARD_API_KEY}" \
  "https://${DASHBOARD_URL}/api/metrics?hours=24" | jq

# Expected response:
# {
#   "total": 123,
#   "positive": 45,
#   "neutral": 56,
#   "negative": 22,
#   "by_tag": {...},
#   "recent_items": [...]
# }
```

**What this tests**:
- API key authentication working
- DynamoDB integration working
- Dashboard can query preprod data

**If it fails**:
- HTTP 403 → API key invalid or missing
- HTTP 500 → DynamoDB access error (check IAM permissions)
- Empty data → No items in preprod DynamoDB yet (expected if not running)

---

## Step 8: Open Dashboard in Browser

```bash
# Get full dashboard URL with API key
DASHBOARD_FULL_URL="https://${DASHBOARD_URL}/?api_key=${PREPROD_DASHBOARD_API_KEY}"

# Copy to clipboard (if xclip installed)
echo $DASHBOARD_FULL_URL | xclip -selection clipboard

# Or just display
echo "Dashboard URL:"
echo $DASHBOARD_FULL_URL

# Open in browser (if running locally)
# xdg-open $DASHBOARD_FULL_URL
```

**Manual steps**:
1. Copy the URL from terminal
2. Open in browser
3. Verify dashboard loads and shows:
   - Total items count
   - Sentiment distribution chart
   - Recent items list
   - Real-time updates (SSE stream)

---

## Safety Checks Before Production

After dashboard is accessible, verify these before prod deploy:

```bash
# 1. Check preprod is using correct region
terraform output | grep region
# Should show: us-east-1

# 2. Check preprod state is separate from prod
cat backend-preprod.hcl | grep key
# Should show: preprod/terraform.tfstate

cat backend-prod.hcl | grep key
# Should show: prod/terraform.tfstate

# 3. Verify preprod resources exist
aws dynamodb describe-table \
  --table-name preprod-sentiment-items \
  --region us-east-1 \
  --query 'Table.TableName'
# Should return: "preprod-sentiment-items"

# 4. Verify prod backend config is separate
cat backend-prod.hcl
```

---

## Troubleshooting

### "Backend initialization required"

**Symptom**: `Error: Backend initialization required`

**Fix**: Run terraform init
```bash
terraform init -backend-config=backend-preprod.hcl -reconfigure
```

### "No outputs found"

**Symptom**: `terraform output` returns nothing

**Cause**: Preprod infrastructure not deployed yet

**Fix**: Check if preprod deployment succeeded in CI
```bash
gh run list --repo traylorre/sentiment-analyzer-gsk --workflow=deploy.yml --limit 5
```

### "Secret not found"

**Symptom**: `SecretNotFoundException: Secret not found: preprod/sentiment-analyzer/dashboard-api-key`

**Cause**: Preprod secrets not created

**Fix**: Check if preprod terraform applied successfully

### "Access denied"

**Symptom**: `AccessDeniedException` from AWS API calls

**Cause**: AWS credentials not configured or insufficient permissions

**Fix**:
```bash
# Check credentials
aws sts get-caller-identity

# Check if using preprod credentials (if separate)
echo $AWS_ACCESS_KEY_ID
```

---

## Summary Checklist

Before proceeding to production:

- [ ] Successfully ran `terraform init` for preprod
- [ ] Retrieved dashboard URL from terraform output
- [ ] Retrieved API key from Secrets Manager
- [ ] Dashboard `/health` endpoint returns 200
- [ ] Dashboard `/api/metrics` endpoint returns data (or empty if no items)
- [ ] Dashboard web UI loads in browser
- [ ] Verified preprod state is separate from prod state
- [ ] Understand andon cord procedures from `FIRST_PROD_DEPLOY_READY.md`

---

## Next Steps

Once dashboard is confirmed working:

1. Review `docs/FIRST_PROD_DEPLOY_READY.md`
2. Execute production preflight checklist
3. Deploy to production
4. Monitor dashboard during first hour

---

*Based on lessons learned from 15+ CI failures during initial terraform setup*
*See: `docs/TERRAFORM_LESSONS_LEARNED.md`*
