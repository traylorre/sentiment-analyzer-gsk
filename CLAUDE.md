# sentiment-analyzer-gsk Development Guidelines

Auto-generated from all feature plans. Last updated: 2025-11-16

## Active Technologies

- Python 3.11 (001-interactive-dashboard-demo)

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

- Python 3.11: Follow PEP 8, use black for formatting
- Linting: ruff (replaces flake8, isort, bandit)
- Line length: 88 characters
- Configuration: pyproject.toml (single source of truth)

## Recent Changes

- 001-interactive-dashboard-demo: Added Python 3.11

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
terraform import module.secrets.aws_secretsmanager_secret.newsapi dev/sentiment-analyzer/newsapi
terraform import module.secrets.aws_secretsmanager_secret.dashboard_api_key dev/sentiment-analyzer/dashboard-api-key

# 6. Verify everything is in state
terraform plan
```

After this setup, CI/CD deployments will persist state in S3 and won't recreate existing resources.

<!-- MANUAL ADDITIONS END -->
