# GitHub Actions Workflow Documentation

Complete reference for all automated workflows in the sentiment-analyzer-gsk repository.

Last Updated: 2025-11-24

## Overview

This repository implements a fully continuous deployment pipeline where:
1. Feature branches automatically create PRs (via git hook)
2. PRs automatically enable auto-merge
3. PRs automatically merge when all checks pass
4. Merged code automatically deploys through dev → preprod → prod

## Workflow Trigger Map

```
┌─────────────────────────────────────────────────────────────────────────┐
│                         CONTINUOUS PIPELINE                              │
└─────────────────────────────────────────────────────────────────────────┘

Feature Branch Push (feat/*, fix/*, docs/*, etc.)
       │
       ├─→ pre-push git hook ─────→ Creates PR automatically (local)
       │
       └─→ PR Created ────────────────┐
                                      │
                                      ├─→ pr-auto-merge-enable.yml ─→ Enables auto-merge
                                      │
                                      ├─→ pr-check-lint.yml ────────→ Runs ruff linter
                                      │
                                      ├─→ pr-check-test.yml ────────→ Runs pytest
                                      │
                                      ├─→ pr-check-security.yml ────→ Runs bandit & safety
                                      │
                                      └─→ pr-check-codeql.yml ──────→ Runs CodeQL analysis
                                      │
                                      └─→ All Checks Pass ──────────→ Auto-merge to main
                                                                      │
Push to Main (from PR merge) ──────────────────────────────────────────────┤
       │                                                                    │
       └─→ deploy.yml ────────────────┐                                    │
           ├─→ build                  │                                    │
           ├─→ deploy-dev              │                                    │
           ├─→ test-dev                │                                    │
           ├─→ deploy-preprod          │                                    │
           ├─→ test-preprod            │                                    │
           └─→ deploy-prod             │                                    │
```

## Workflow Details

### 1. pre-push Git Hook (Auto-Create PR)

**Purpose**: Automatically creates a PR when pushing a feature branch to remote.

**Location**: `.githooks/pre-push`

**Setup**:
```bash
./scripts/setup-git-hooks.sh
```

**Triggers**:
- Runs locally on `git push` for feature branches:
  - `feat/**`, `fix/**`, `docs/**`, `refactor/**`, `test/**`, `chore/**`

**Behavior**:
- Checks if PR already exists for the branch (skips if yes)
- Generates PR title from branch name using conventional commit format
  - Example: `feat/add-feature` → `"feat: Add Feature"`
- Generates PR body with:
  - Commit messages since divergence from main
  - List of changed files
  - Test plan checklist
- Creates PR targeting `main` branch using `gh pr create`
- Enables auto-merge with squash strategy
- PR creation triggers GitHub Actions workflows (checks)

**Requirements**:
- GitHub CLI (`gh`) installed and authenticated
- Git hooks configured (`./scripts/setup-git-hooks.sh`)

**Human Interaction Required**: None (runs automatically on push)

**Bypass Hook**: Use `git push --no-verify` to skip PR creation temporarily

**Why Git Hook Instead of GitHub Actions?**:
- GitHub Actions with default `GITHUB_TOKEN` cannot create PRs from push-triggered workflows
- This is a security restriction to prevent infinite workflow loops
- Git hooks run locally using your authenticated `gh` CLI, avoiding this limitation

---

### 2. pr-auto-merge-enable.yml (Enable Auto-Merge)

**Purpose**: Automatically enables auto-merge on newly created PRs.

**Location**: `.github/workflows/pr-auto-merge-enable.yml`

**Triggers**:
```yaml
on:
  pull_request_target:
    types: [opened, reopened, ready_for_review]
```

**Behavior**:
- Enables GitHub's auto-merge feature for the PR
- PR will merge automatically once all required checks pass
- Uses merge strategy (not squash or rebase)

**Permissions Required**:
- `pull-requests: write` - Enable auto-merge on PRs

**Human Interaction Required**: None (fully automated)

**Manual Override**: To disable auto-merge:
```bash
gh pr merge --disable-auto <PR_NUMBER>
```

---

### 3. pr-check-lint.yml (Lint Checks)

**Purpose**: Runs code quality checks on PR code.

**Location**: `.github/workflows/pr-check-lint.yml`

**Triggers**:
```yaml
on:
  push:
    branches: [main]
  pull_request:
    branches: [main]
```

**Behavior**:
- Runs `ruff check .` to check Python code style
- Runs `ruff format --check .` to verify formatting
- Fails PR checks if linting errors found
- Reports results as PR check status

**Permissions Required**:
- `contents: read` - Read repository code

**Human Interaction Required**: Fix linting errors if check fails

---

### 5. pr-check-test.yml (Unit Tests)

**Purpose**: Runs unit tests on PR code.

**Location**: `.github/workflows/pr-check-test.yml`

**Triggers**:
```yaml
on:
  push:
    branches: [main]
  pull_request:
    branches: [main]
```

**Behavior**:
- Sets up Python 3.13 environment
- Installs dependencies from `requirements.txt` and `requirements-dev.txt`
- Runs `pytest` with coverage reporting
- Fails PR checks if tests fail
- Uploads coverage report as artifact

**Permissions Required**:
- `contents: read` - Read repository code

**Human Interaction Required**: Fix failing tests if check fails

---

### 6. pr-check-security.yml (Security Scanning)

**Purpose**: Scans PR code for security vulnerabilities.

**Location**: `.github/workflows/pr-check-security.yml`

**Triggers**:
```yaml
on:
  push:
    branches: [main]
  pull_request:
    branches: [main]
```

**Behavior**:
- Runs `bandit` to scan for common security issues
- Runs `safety check` to scan dependencies for known vulnerabilities
- Fails PR checks if security issues found
- Reports results as PR check status

**Permissions Required**:
- `contents: read` - Read repository code

**Human Interaction Required**: Fix security issues if check fails

---

### 7. pr-check-codeql.yml (CodeQL Analysis)

**Purpose**: Performs advanced semantic code analysis.

**Location**: `.github/workflows/pr-check-codeql.yml`

**Triggers**:
```yaml
on:
  push:
    branches: [main]
  pull_request:
    branches: [main]
  schedule:
    - cron: '0 0 * * 0'  # Weekly on Sunday
```

**Behavior**:
- Initializes CodeQL with Python language support
- Builds codebase for analysis
- Performs CodeQL security and quality queries
- Uploads results to GitHub Security tab
- Fails PR checks if critical issues found

**Permissions Required**:
- `security-events: write` - Upload CodeQL results
- `contents: read` - Read repository code

**Human Interaction Required**: Review and fix CodeQL alerts

---

### 8. deploy.yml (Deployment Pipeline)

**Purpose**: Deploys code through dev → preprod → prod environments.

**Location**: `.github/workflows/deploy.yml`

**Triggers**:
```yaml
on:
  push:
    branches:
      - main
  workflow_dispatch:  # Manual trigger with environment selection
```

**Behavior**:

**Job Flow**:
```
build
  ↓
deploy-dev
  ↓
test-dev (mocked AWS)
  ↓
deploy-preprod
  ↓
test-preprod (real AWS)
  ↓
deploy-prod (requires approval)
```

**Build Job**:
- Packages Lambda functions: ingestion, analysis, dashboard
- Uploads packages as artifacts for deployment jobs

**Deploy-Dev Job**:
- Downloads Lambda packages
- Uploads to S3: `dev-sentiment-lambda-deployments`
- Runs Terraform with `backend-dev.hcl` and `dev.tfvars`
- Outputs: `dashboard_url`, `sns_topic_arn`
- Runs smoke test on dashboard Lambda

**Test-Dev Job**:
- Runs integration tests with mocked AWS services
- Uses pytest with `--env=dev` flag

**Deploy-Preprod Job**:
- Downloads Lambda packages
- Uploads to S3: `preprod-sentiment-lambda-deployments`
- Runs Terraform with `backend-preprod.hcl` and `preprod.tfvars`
- Outputs: `dashboard_url`, `sns_topic_arn`
- Runs smoke test on dashboard Lambda

**Test-Preprod Job**:
- Runs integration tests against real preprod environment
- Uses pytest with `--env=preprod` flag
- Tests real AWS services (DynamoDB, SNS, Lambda, etc.)

**Deploy-Prod Job**:
- **Requires manual approval** (GitHub environment protection)
- Downloads Lambda packages
- Uploads to S3: `prod-sentiment-lambda-deployments`
- Runs Terraform with `backend-prod.hcl` and `prod.tfvars`
- Outputs: `dashboard_url`, `sns_topic_arn`
- Runs smoke test on dashboard Lambda

**Canary-Test Job** (after prod deploy):
- Waits 5 minutes for prod to stabilize
- Runs canary tests against production
- Can trigger rollback if tests fail

**Permissions Required**:
- `contents: read` - Read repository code
- `id-token: write` - OIDC authentication with AWS

**Secrets Required**:
- `DEV_AWS_ACCESS_KEY_ID`
- `DEV_AWS_SECRET_ACCESS_KEY`
- `PREPROD_AWS_ACCESS_KEY_ID`
- `PREPROD_AWS_SECRET_ACCESS_KEY`
- `PROD_AWS_ACCESS_KEY_ID`
- `PROD_AWS_SECRET_ACCESS_KEY`
- `NEWSAPI_API_KEY`

**Human Interaction Required**:
- Approval for production deployment
- Response to failed deployments/tests

**Manual Trigger**:
```bash
# Deploy to specific environment
gh workflow run deploy.yml -f environment=preprod
gh workflow run deploy.yml -f environment=prod
```

---

## Complete Flow Example

Here's what happens when you push a new feature:

### Step 1: Push Feature Branch
```bash
git checkout -b feat/add-new-feature
# ... make changes ...
git add .
git commit -m "feat: Add new feature"
git push -u origin feat/add-new-feature
```

### Step 2: Auto-Create PR (feature-auto-pr.yml)
- Triggers immediately on push
- Creates PR #123: "feat: Add New Feature"
- PR body includes commits and changed files

### Step 3: Enable Auto-Merge (pr-auto-merge-enable.yml)
- Triggers when PR #123 is created
- Enables auto-merge on PR #123

### Step 4: Run PR Checks (all pr-check-*.yml workflows)
- All 4 checks run in parallel:
  - Lint ✓
  - Tests ✓
  - Security ✓
  - CodeQL ✓

### Step 5: Auto-Merge PR
- Once all checks pass ✓
- PR #123 automatically merges to main
- Feature branch can be deleted

### Step 6: Deploy Pipeline (deploy.yml)
- Triggers on push to main (from merge)
- Runs full deployment:
  - Build Lambda packages
  - Deploy to dev → test dev
  - Deploy to preprod → test preprod
  - Deploy to prod (after approval) → canary test

### Step 7: Rebase Open PRs (pr-auto-rebase.yml)
- Triggers on push to main (from merge)
- Finds other open PRs
- Rebases them onto latest main
- Re-runs their PR checks

### Result
Your feature is now deployed to production, and all other open PRs are up-to-date with your changes.

---

## Getting Dashboard URLs

### Via AWS CLI (Fast)
```bash
# Preprod
aws lambda get-function-url-config \
  --function-name preprod-sentiment-dashboard \
  | grep -o 'https://[^"]*'

# Prod
aws lambda get-function-url-config \
  --function-name prod-sentiment-dashboard \
  | grep -o 'https://[^"]*'

# Dev
aws lambda get-function-url-config \
  --function-name dev-sentiment-dashboard \
  | grep -o 'https://[^"]*'
```

### Via Terraform (Requires Workspace)
```bash
cd infrastructure/terraform

# Preprod
terraform workspace select preprod
terraform output -raw dashboard_url

# Prod
terraform workspace select prod
terraform output -raw dashboard_url

# Dev
terraform workspace select dev
terraform output -raw dashboard_url
```

### Current URLs (as of 2025-12-29)
- **Preprod**: https://cjx6qw4a7xqw6cuifvkbi6ae2e0evviw.lambda-url.us-east-1.on.aws/
- **Prod**: (Not yet deployed)
- **Dev**: (Not yet deployed)

---

## Workflow Permissions Summary

| Workflow | Contents | PRs | Security Events |
|----------|----------|-----|-----------------|
| pre-push (git hook) | local | local (via gh CLI) | - |
| pr-auto-merge-enable.yml | - | write | - |
| pr-check-lint.yml | read | - | - |
| pr-check-test.yml | read | - | - |
| pr-check-security.yml | read | - | - |
| pr-check-codeql.yml | read | - | write |
| deploy.yml | read | - | - |

---

## Branch Protection Rules

The `main` branch should have the following protections:

**Required Status Checks**:
- `pr-check-lint` ✓
- `pr-check-test` ✓
- `pr-check-security` ✓
- `pr-check-codeql` ✓

**Settings**:
- ✓ Require branches to be up to date before merging
- ✓ Require status checks to pass before merging
- ✓ Do not allow bypassing the above settings
- ✗ Require pull request reviews (auto-merge enabled instead)

---

## Manual Workflow Operations

### Disable Auto-Merge on Specific PR
```bash
gh pr merge --disable-auto 123
```

### Manually Trigger Deploy
```bash
# Deploy to preprod
gh workflow run deploy.yml -f environment=preprod

# Deploy to prod
gh workflow run deploy.yml -f environment=prod
```

### Check PR Status
```bash
gh pr checks 123
```

### View Workflow Runs
```bash
gh run list --workflow=deploy.yml --limit 5
```

### Watch Workflow Run
```bash
gh run watch 12345678
```

---

## Troubleshooting

### PR Not Auto-Creating
**Symptom**: Pushed feature branch, but no PR created

**Check**:
1. Verify branch name matches pattern: `feat/*`, `fix/*`, etc.
2. Check workflow run: `gh run list --workflow=feature-auto-pr.yml --limit 1`
3. View workflow logs: `gh run view <run-id>`

**Manual Workaround**:
```bash
gh pr create --base main --fill
```

---

### PR Not Auto-Merging
**Symptom**: All checks pass, but PR doesn't merge

**Check**:
1. Verify auto-merge is enabled: `gh pr view 123 --json autoMergeRequest`
2. Check if PR is behind main: `git log origin/main..origin/feat/branch`
3. Wait for auto-rebase workflow to run

**Manual Workaround**:
```bash
# Rebase manually
git checkout feat/branch
git fetch origin
git rebase origin/main
git push -f origin feat/branch

# Or merge manually
gh pr merge 123 --merge
```

---

### Deployment Failing
**Symptom**: Deploy pipeline fails on specific environment

**Check**:
1. View failed job: `gh run view <run-id> --log-failed`
2. Check AWS credentials are valid
3. Check Terraform state isn't locked

**Common Issues**:
- **AccessDeniedException**: IAM policy needs updating (see `docs/IAM_CI_USER_POLICY.md`)
- **State Lock**: Someone else running Terraform
- **Resource Conflict**: Resource exists but not in state

**Manual Workaround**:
```bash
cd infrastructure/terraform
terraform workspace select preprod
terraform init -backend-config=backend-preprod.hcl
terraform plan -var-file=preprod.tfvars
# Review and fix issues
terraform apply -var-file=preprod.tfvars
```

---

## Architecture Decisions

### Why Auto-Create PRs?
- Ensures code review visibility for all changes
- Triggers automated checks on all feature work
- Creates audit trail of what changed and when
- Enables auto-merge workflow

### Why Auto-Rebase?
- Keeps PRs up-to-date with main automatically
- Reduces merge conflicts
- Ensures PR checks run against latest main
- Reduces manual git operations

### Why Auto-Merge?
- Eliminates manual merge step when checks pass
- Speeds up delivery of verified changes
- Reduces context switching for developers
- Maintains high code quality via required checks

### Why Three Environments?
- **Dev**: Fast feedback, mocked services, safe experimentation
- **Preprod**: Real AWS, integration testing, staging environment
- **Prod**: Customer-facing, requires approval, canary testing

---

## Future Enhancements

Potential improvements to consider:

1. **Slack Notifications**: Notify team of deployments, failures
2. **Rollback Automation**: Auto-rollback on canary test failures
3. **Progressive Deployment**: Gradual traffic shifting in prod
4. **Cost Monitoring**: Alert on unexpected cost increases
5. **Performance Testing**: Automated load testing in preprod
6. **Compliance Scanning**: Automated compliance checks
7. **Dependency Updates**: Automated dependency update PRs
8. **Release Notes**: Auto-generate release notes from PR titles

---

## Version History

- **2025-11-24**:
  - Added `feature-auto-pr.yml` for automatic PR creation
  - Added `pr-auto-rebase.yml` for automatic PR rebase
  - Added `deploy-dev` job to deployment pipeline
  - Created this comprehensive documentation
