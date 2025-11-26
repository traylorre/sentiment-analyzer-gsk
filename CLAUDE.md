# sentiment-analyzer-gsk Development Guidelines

Auto-generated from all feature plans. Last updated: 2025-11-16

## Active Technologies
- Python 3.13 + FastAPI, boto3, pydantic, aws-lambda-powertools, requests (006-user-config-dashboard)
- DynamoDB (users, configurations, sentiment results, alerts), S3 (static assets) (006-user-config-dashboard)

- Python 3.13 (001-interactive-dashboard-demo)

## Project Structure

```text
src/
tests/
```

## Commands

```bash
# Run tests
pytest

# Format code
black src/ tests/

# Lint code
ruff check src/ tests/

# Auto-fix lint issues
ruff check --fix src/ tests/
```

## Code Style

- Python 3.13: Follow PEP 8, use black for formatting
- Linting: ruff (replaces flake8, isort, bandit)
- Line length: 88 characters
- Configuration: pyproject.toml (single source of truth)

## Git Commit Security Requirements

**CRITICAL SECURITY POLICY - NEVER BYPASS**:

1. **ALL commits MUST be GPG-signed** - Use `git commit -S` or `git commit --amend -S`
2. **NEVER use `--no-gpg-sign`** - This bypasses critical security verification
3. **If GPG signing fails**, this indicates a security configuration issue that MUST be fixed
4. **DO NOT attempt to bypass GPG failures** - Investigate and resolve the root cause

**Why This Matters**:
- GPG signatures verify commit authenticity and prevent impersonation
- Unsigned commits create security vulnerabilities in the supply chain
- GPG failures often indicate misconfiguration that could affect other security tools

**Correct Workflow**:
```bash
# Making commits
git commit -S -m "commit message"

# Amending commits
git commit --amend -S --no-edit

# If GPG fails - FIX IT, don't bypass it
# Check GPG configuration, verify key exists, ensure agent is running
```

**Test Environment Separation**:
- **LOCAL mirrors DEV**: Always uses mocked AWS resources (moto)
- **PREPROD mirrors PROD**: Always uses real AWS resources
- Preprod tests are excluded from local runs via pytest marker: `-m "not preprod"`
- Never attempt to run preprod tests locally - they require real AWS credentials

## Recent Changes
- 006-user-config-dashboard: Added Python 3.13 + FastAPI, boto3, pydantic, aws-lambda-powertools, requests

- 001-interactive-dashboard-demo: Added Python 3.13

<!-- MANUAL ADDITIONS START -->

## GitHub CLI Setup

Install gh CLI for checking CI results and managing PRs:

```bash
# Install to local bin (no sudo required)
mkdir -p ~/.local/bin
curl -sL https://github.com/cli/cli/releases/download/v2.40.1/gh_2.40.1_linux_amd64.tar.gz | tar xz -C /tmp
mv /tmp/gh_2.40.1_linux_amd64/bin/gh ~/.local/bin/
export PATH="$HOME/.local/bin:$PATH"

# One-time authentication
gh auth login
```

**Auth login steps:**
1. Where do you use GitHub? → `GitHub.com`
2. Preferred protocol? → `HTTPS`
3. Authenticate Git with credentials? → `Yes`
4. How to authenticate? → `Login with a web browser`

A one-time code will appear (8 characters). Copy just the code itself, then paste it in the browser when prompted.

```bash
# Check CI workflow runs
gh run list --repo traylorre/sentiment-analyzer-gsk --limit 5

# View specific run details
gh run view <run-id> --repo traylorre/sentiment-analyzer-gsk
```

## Terraform Backend Setup (One-Time)

Before CI/CD deploys will work, you must set up the Terraform state backend:

```bash
# 1. Create the S3 bucket and DynamoDB table for state
cd infrastructure/terraform/bootstrap
terraform init
terraform apply

# 2. Note the bucket name from output
terraform output state_bucket_name

# 3. Update main.tf with your bucket name
# Edit infrastructure/terraform/main.tf and replace
# "sentiment-analyzer-tfstate-YOUR_ACCOUNT_ID" with the actual bucket name

# 4. Initialize main terraform with S3 backend
cd ../
terraform init

# 5. Import existing secrets (if they exist in AWS)
terraform import -var="environment=dev" module.secrets.aws_secretsmanager_secret.newsapi dev/sentiment-analyzer/newsapi
terraform import -var="environment=dev" module.secrets.aws_secretsmanager_secret.dashboard_api_key dev/sentiment-analyzer/dashboard-api-key

# 6. Verify everything is in state
terraform plan -var="environment=dev"
```

After this setup, CI/CD deployments will persist state in S3 and won't recreate existing resources.

## Terraform State Management

### How State Locking Works

Terraform uses **S3 native locking** to prevent concurrent modifications. Lock files are stored as `.tflock` files directly in the S3 state bucket. The CI/CD pipeline handles most lock scenarios automatically:

1. **Concurrency control**: Only one deployment runs at a time (GitHub Actions `concurrency` group)
2. **Lock timeout**: Terraform waits up to 5 minutes for locks to be released (`-lock-timeout=5m`)
3. **Lock detection**: CI checks for existing lock files before each deploy and provides guidance
4. **Automatic cleanup**: Terraform removes lock files when operations complete normally

### Best Practices

- **Never run terraform locally while CI is deploying** - This causes lock conflicts
- **Don't cancel running deploy workflows** - This may leave orphaned lock files
- **Use the GitHub Actions UI** to trigger deploys, not local terraform

### Manual State Lock Recovery

If a lock file is orphaned, you can manually unlock:

```bash
cd infrastructure/terraform
terraform init

# Get the Lock ID from the error message or workflow logs, then:
terraform force-unlock <LOCK_ID>

# Example:
terraform force-unlock 4a2b102d-2da5-6055-25d4-0aa01be88bbb
```

Or delete the lock file directly via AWS CLI:

```bash
# For preprod
aws s3 rm s3://sentiment-analyzer-terraform-state-218795110243/preprod/terraform.tfstate.tflock

# For prod
aws s3 rm s3://sentiment-analyzer-terraform-state-218795110243/prod/terraform.tfstate.tflock
```

### Checking Lock Status

```bash
# Check for preprod lock file
aws s3api head-object \
  --bucket sentiment-analyzer-terraform-state-218795110243 \
  --key preprod/terraform.tfstate.tflock

# Check for prod lock file
aws s3api head-object \
  --bucket sentiment-analyzer-terraform-state-218795110243 \
  --key prod/terraform.tfstate.tflock
```

<!-- MANUAL ADDITIONS END -->
