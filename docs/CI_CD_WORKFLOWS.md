# CI/CD Workflows

> **Purpose**: Document all GitHub Actions workflows and their behavior.

---

## Table of Contents

- [PR Check Workflows](#pr-check-workflows)
- [Auto-Merge Configuration](#auto-merge-configuration)
- [Deployment Pipeline](#deployment-pipeline)
- [Workflow Triggers](#workflow-triggers)

---

## PR Check Workflows

All PRs trigger the following required status checks:

### 1. Unit Tests (`pr-check-test.yml`)

**Job Name**: `Run Tests`

**What it does:**
- Runs unit tests with pytest
- Validates code coverage (minimum 80%)
- Executes dev integration tests (mocked AWS)
- Uploads coverage reports

**Runs on:**
- Every push to main
- Every pull request to main
- Manual dispatch

**Key Features:**
- No path filters - runs on ALL PRs
- Uses mocked AWS services (moto)
- Fast feedback (~2 minutes)
- Zero cost (no real AWS calls)

**Coverage Requirements:**
- Minimum 80% coverage or build fails
- Coverage report posted as PR comment

---

### 2. Code Quality (`pr-check-lint.yml`)

**Job Name**: `Code Quality`

**What it does:**
- Checks code formatting with black
- Runs linting with ruff
- Validates security rules (bandit)

**Runs on:**
- Every push to main
- Every pull request to main
- Manual dispatch

**Tools:**
- `black==25.11.0` - Code formatting
- `ruff==0.14.5` - Fast Python linter with security checks

---

### 3. Dependency Vulnerability Scan (`pr-check-security.yml`)

**Job Name**: `Dependency Vulnerability Scan`

**What it does:**
- Scans Python dependencies for known CVEs
- Uses pip-audit against PyPI advisory database
- Reports vulnerabilities with severity scores

**Runs on:**
- Every push to main
- Every pull request to main
- Weekly schedule (Monday 9am UTC)
- Manual dispatch

**Schedule:**
- Runs automatically weekly to catch new CVEs
- No path filters - always runs on PRs

---

### 4. CodeQL Analysis (`pr-check-codeql.yml`)

**Job Name**: `Analyze`

**What it does:**
- Static code analysis for security vulnerabilities
- Scans for common coding mistakes
- Checks for potential security issues

**Runs on:**
- Every push to main
- Every pull request to main
- Weekly schedule (Monday 6am UTC)
- Manual dispatch

**Languages:** Python

---

## Auto-Merge Configuration

### Automatic PR Merging (`pr-auto-merge-enable.yml`)

**Triggers:** When PR is opened, reopened, or marked ready for review

**What it does:**
1. Enables GitHub auto-merge on the PR
2. Adds comment explaining auto-merge status
3. PR auto-merges when all checks pass

**Conditions:**
- Skips Dependabot PRs (handled by separate workflow)
- Applies to all other PRs automatically

**Merge Method:** Squash merge

**Safety Guarantees:**
- All branch protection rules enforced
- All required status checks must pass:
  - ✅ Run Tests
  - ✅ Code Quality
  - ✅ Dependency Vulnerability Scan
  - ✅ Analyze (CodeQL)
- Branch must be up to date with main
- All conversations must be resolved
- Signed commits required

**To disable auto-merge:**
```bash
gh pr merge --disable-auto <PR_NUMBER>
```

---

### Dependabot Auto-Merge (`dependabot-auto-merge.yml`)

**Triggers:** When Dependabot PR is opened or updated

**Auto-merge rules:**

| Update Type | Package Ecosystem | Auto-merge? |
|-------------|-------------------|-------------|
| Patch/Minor | Python (pip) | ✅ Yes |
| Major | Python (pip) | ❌ No - Manual review required |
| Major | GitHub Actions | ✅ Yes - Actions use different versioning |
| Security | Any | ✅ Yes - Expedited merge |

**What it does:**
1. Fetches Dependabot metadata
2. Checks update type (patch/minor/major)
3. Enables auto-merge for safe updates
4. Approves PR automatically
5. Comments on major Python updates requiring review

**Comment Example (Major Python update):**
```
⚠️ Major Python dependency update detected

This PR updates `package-name` to a new major version.

Major updates may contain breaking changes and require manual review:
1. Check the changelog for breaking changes
2. Review test results carefully
3. Test locally if needed
4. Merge manually when ready

This PR will NOT be auto-merged.
```

---

## Deployment Pipeline

See `docs/TERRAFORM_DEPLOYMENT_FLOW.md` for complete deployment pipeline documentation.

**Pipeline Workflow:** `deploy.yml`

**Stages:**
1. Build - Package Lambda functions
2. Deploy Preprod - Deploy to preprod environment
3. Test Preprod - Run integration tests
4. Deploy Production - Deploy to production

---

## Workflow Triggers

### Why No Path Filters on Required Checks?

Previously, workflows had path filters like:
```yaml
on:
  pull_request:
    paths:
      - 'src/**'
      - 'tests/**'
```

**Problem:** GitHub branch protection doesn't distinguish between:
- "Check skipped due to path filter"
- "Check pending/waiting to run"

This caused PRs to stall forever waiting for checks that would never run.

**Solution:** Removed path filters from all required status checks.

**Impact:**
- ✅ All required checks run on every PR
- ✅ Consistent CI validation
- ✅ No stalled PRs
- ✅ Fast workflows (~2 min each) make this acceptable

**Example:** PR that only changes Terraform `.hcl` files will still run:
- Unit tests (to ensure no unexpected breakage)
- Linting (always good to validate)
- Security scan (dependencies don't change, but check is fast)
- CodeQL (comprehensive security analysis)

---

## Workflow Files Reference

| Workflow | File | Job Name | Required Check? |
|----------|------|----------|-----------------|
| Unit Tests | `pr-check-test.yml` | Run Tests | ✅ Yes |
| Code Quality | `pr-check-lint.yml` | Code Quality | ✅ Yes |
| Security Scan | `pr-check-security.yml` | Dependency Vulnerability Scan | ✅ Yes |
| CodeQL | `pr-check-codeql.yml` | Analyze | ✅ Yes |
| Auto-Merge Enable | `pr-auto-merge-enable.yml` | - | No |
| Dependabot Auto-Merge | `dependabot-auto-merge.yml` | - | No |
| Deploy Pipeline | `deploy.yml` | - | No |
| PR Approval Enforcement | `pr-approval-enforcement.yml` | - | No |

---

## Monitoring Workflows

### Check workflow runs:
```bash
# List recent runs
gh run list --repo traylorre/sentiment-analyzer-gsk --limit 10

# View specific run
gh run view <run-id> --repo traylorre/sentiment-analyzer-gsk

# Watch active run
gh run watch
```

### Check PR status:
```bash
# View PR checks
gh pr view <PR_NUMBER> --repo traylorre/sentiment-analyzer-gsk

# Check auto-merge status
gh pr view <PR_NUMBER> --json autoMergeRequest,mergeable
```

---

## Troubleshooting

### PR Not Auto-Merging

**Check 1:** Is auto-merge enabled?
```bash
gh pr view <PR_NUMBER> --json autoMergeRequest
# Should return: {"autoMergeRequest": {"enabledAt": "timestamp"}}
```

**Check 2:** Are all required checks passing?
```bash
gh pr view <PR_NUMBER> --json statusCheckRollup
```

**Check 3:** Is branch up to date?
```bash
gh pr view <PR_NUMBER> --json mergeable,mergeStateStatus
```

**Common Issues:**
- Branch not up to date → rebase or merge main
- Conversations not resolved → resolve all threads
- Required checks failed → fix and push new commit
- Auto-merge not enabled → workflow may have failed, enable manually

### Workflow Not Triggering

**Check 1:** Does workflow file exist in `.github/workflows/`?

**Check 2:** Are trigger conditions met?
- PR opened/reopened for auto-merge
- Push to main or PR for checks

**Check 3:** Check workflow run history:
```bash
gh run list --workflow=<workflow-name>.yml --limit 5
```

---

## Security Considerations

### Workflow Permissions

All workflows use minimal permissions:

```yaml
permissions:
  contents: read      # Read repository contents
  pull-requests: write # Comment on PRs (auto-merge only)
  checks: write       # Report check results (tests only)
```

### Secrets

- Workflows use `GITHUB_TOKEN` (automatically provided)
- No custom secrets required for PR checks
- Deployment uses repository secrets (AWS credentials)

### Branch Protection Integration

All required checks are enforced by branch protection rules.
See `docs/security/BRANCH-PROTECTION.md` for configuration.

---

**Last Updated:** 2025-11-22
**Maintainer:** @traylorre
