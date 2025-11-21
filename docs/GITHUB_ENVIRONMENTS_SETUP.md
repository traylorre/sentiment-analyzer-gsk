# GitHub Environments Setup Guide

**Purpose**: Configure GitHub Environments to enable conditional deployment gating (Dependabot auto-promotes, humans require approval).

**Date**: 2025-11-20
**Prerequisites**: Credential separation complete (Phase 1)

---

## Overview

GitHub Environments provide:
1. **Scoped Secrets**: Different credentials per environment
2. **Required Reviewers**: Manual approval gates for production
3. **Deployment Protection Rules**: Wait timers, branch restrictions

**Our Strategy**:
- `preprod`: No approval (automatic deployment)
- `production`: Manual approval (human PRs only)
- `production-auto`: No approval (Dependabot bypass)

---

## Step 1: Create Environments

### Navigate to Repository Settings

```
https://github.com/traylorre/sentiment-analyzer-gsk/settings/environments
```

### Create Environment: `preprod`

1. Click "New environment"
2. Name: `preprod`
3. **Protection Rules**:
   - [ ] Required reviewers: (leave empty - no approval needed)
   - [ ] Wait timer: (leave empty)
   - [x] Deployment branches: `main` only

4. Click "Configure environment"

### Create Environment: `production`

1. Click "New environment"
2. Name: `production`
3. **Protection Rules**:
   - [x] **Required reviewers**: Add `@traylorre` (or your GitHub username)
   - [ ] Wait timer: (leave empty)
   - [x] Deployment branches: `main` only

4. Click "Configure environment"

### Create Environment: `production-auto`

1. Click "New environment"
2. Name: `production-auto`
3. **Protection Rules**:
   - [ ] Required reviewers: (leave empty - Dependabot bypass)
   - [ ] Wait timer: (leave empty)
   - [x] Deployment branches: `main` only

4. Click "Configure environment"

---

## Step 2: Add Secrets to Environments

### Preprod Environment Secrets

Navigate to: `Settings → Environments → preprod → Add Secret`

Add the following secrets (values from Phase 1 credential setup):

```
Name: PREPROD_AWS_ACCESS_KEY_ID
Value: <from preprod-deployer-credentials.json>

Name: PREPROD_AWS_SECRET_ACCESS_KEY
Value: <from preprod-deployer-credentials.json>

Name: PREPROD_NEWSAPI_SECRET_ARN
Value: arn:aws:secretsmanager:us-east-1:ACCOUNT:secret:preprod/sentiment-analyzer/newsapi-XXXXXX

Name: PREPROD_DASHBOARD_API_KEY_SECRET_ARN
Value: arn:aws:secretsmanager:us-east-1:ACCOUNT:secret:preprod/sentiment-analyzer/dashboard-api-key-XXXXXX

Name: PREPROD_DASHBOARD_API_KEY
Value: <generated preprod API key from Phase 1>

Name: PREPROD_SNS_TOPIC_ARN
Value: (leave empty initially - will be set after first preprod deploy)
```

### Production Environment Secrets

Navigate to: `Settings → Environments → production → Add Secret`

Add the following secrets:

```
Name: PROD_AWS_ACCESS_KEY_ID
Value: <from prod-deployer-credentials.json>

Name: PROD_AWS_SECRET_ACCESS_KEY
Value: <from prod-deployer-credentials.json>

Name: PROD_NEWSAPI_SECRET_ARN
Value: arn:aws:secretsmanager:us-east-1:ACCOUNT:secret:prod/sentiment-analyzer/newsapi-XXXXXX

Name: PROD_DASHBOARD_API_KEY_SECRET_ARN
Value: arn:aws:secretsmanager:us-east-1:ACCOUNT:secret:prod/sentiment-analyzer/dashboard-api-key-XXXXXX

Name: PROD_DASHBOARD_API_KEY
Value: <generated prod API key from Phase 1>
```

### Production-Auto Environment Secrets

Navigate to: `Settings → Environments → production-auto → Add Secret`

**IMPORTANT**: Add the SAME secrets as `production` environment.

This allows Dependabot to use prod credentials but bypass manual approval.

---

## Step 3: Verify Environment Configuration

### Check Preprod Environment

```
Settings → Environments → preprod
```

Expected configuration:
- ✅ Deployment branches: `main` only
- ❌ Required reviewers: (none)
- ❌ Wait timer: (none)
- ✅ Secrets: 6 secrets configured

### Check Production Environment

```
Settings → Environments → production
```

Expected configuration:
- ✅ Deployment branches: `main` only
- ✅ **Required reviewers: @traylorre (or your username)**
- ❌ Wait timer: (none)
- ✅ Secrets: 5 secrets configured

### Check Production-Auto Environment

```
Settings → Environments → production-auto
```

Expected configuration:
- ✅ Deployment branches: `main` only
- ❌ **Required reviewers: (none - Dependabot bypass)**
- ❌ Wait timer: (none)
- ✅ Secrets: 5 secrets configured (same as production)

---

## Step 4: Test Environment Gating

### Test 1: Human PR → Manual Approval Required

1. Create a test branch: `git checkout -b test/environment-gating`
2. Make a trivial change: `echo "test" >> README.md`
3. Commit and push: `git commit -am "test: Verify environment gating" && git push`
4. Create PR via GitHub UI
5. **Expected**: After dev tests pass and PR is merged:
   - `build-and-promote.yml` runs automatically
   - If preprod tests pass, `deploy-prod.yml` triggers
   - **Production deployment WAITS for manual approval**
   - You see: "Waiting for approval from @traylorre"

### Test 2: Dependabot PR → Auto-Promote

1. Wait for Dependabot to create a PR (or manually trigger one)
2. **Expected**: After dev tests pass and PR auto-merges:
   - `build-and-promote.yml` runs automatically
   - If preprod tests pass, `deploy-prod.yml` triggers
   - **Production deployment PROCEEDS WITHOUT APPROVAL**
   - Uses `production-auto` environment (no reviewers)

---

## How the Conditional Logic Works

**In `.github/workflows/deploy-prod.yml` line 102**:

```yaml
environment:
  name: ${{ github.actor == 'dependabot[bot]' && 'production-auto' || 'production' }}
```

**Explanation**:
- If PR author is `dependabot[bot]` → use `production-auto` environment
- If PR author is anything else → use `production` environment

**Result**:
- Human PRs: Blocked by required reviewer in `production` environment
- Dependabot PRs: No blocker in `production-auto` environment (auto-deploys)

---

## Security Implications

### Why This is Safe

1. **Dependabot auto-promote is safe because**:
   - Dev tests must pass (branch protection)
   - Preprod integration tests must pass (workflow gate)
   - Canary test runs in prod (health check)
   - CloudWatch alarms monitored (system health)
   - Automatic rollback on failure

2. **Humans require approval because**:
   - Feature changes need code review
   - Architectural changes need scrutiny
   - Manual approval provides oversight

3. **Credentials still isolated**:
   - Even though `production-auto` has same secrets as `production`
   - IAM policies prevent preprod from touching prod
   - Secrets scoped to environments (not repository-wide)

### What Could Go Wrong

❌ **Risk**: Malicious dependency introduced by Dependabot
- **Mitigation**: Preprod tests catch malicious behavior
- **Mitigation**: Canary test catches broken prod
- **Mitigation**: Automatic rollback if canary fails

❌ **Risk**: Dependabot updates break application
- **Mitigation**: Dev tests catch breaking changes
- **Mitigation**: Preprod integration tests catch infrastructure issues
- **Mitigation**: Automatic rollback if prod tests fail

❌ **Risk**: Reviewer accidentally approves bad change
- **Mitigation**: Same safety mechanisms as Dependabot
- **Mitigation**: Code review before approval
- **Mitigation**: Canary + rollback safety net

---

## Troubleshooting

### Problem: "Environment protection rules not met"

**Cause**: Deployment triggered but required reviewer not approved

**Fix**: Check GitHub Actions → Click "Review pending deployments" → Approve

### Problem: Dependabot PR waiting for approval (shouldn't be)

**Cause**: Wrong environment selected (using `production` instead of `production-auto`)

**Fix**: Check workflow logs → Verify `github.actor == 'dependabot[bot]'` evaluated correctly

### Problem: Secrets not found in environment

**Cause**: Secrets added to repository instead of environment

**Fix**: Navigate to `Settings → Environments → [env name] → Secrets` (not repository secrets)

### Problem: Manual approval required but no reviewer configured

**Cause**: `production` environment has no required reviewers

**Fix**: `Settings → Environments → production → Protection rules → Add @traylorre`

---

## Maintenance

### Rotate Environment Secrets

When rotating credentials (e.g., after security incident):

1. Generate new AWS access keys (see Phase 1 documentation)
2. Update GitHub Environment secrets:
   ```
   Settings → Environments → preprod → Secrets → PREPROD_AWS_ACCESS_KEY_ID → Update
   Settings → Environments → preprod → Secrets → PREPROD_AWS_SECRET_ACCESS_KEY → Update
   ```
3. Repeat for `production` and `production-auto`
4. Delete old AWS access keys:
   ```bash
   aws iam delete-access-key \
     --user-name sentiment-analyzer-preprod-deployer \
     --access-key-id <OLD_KEY_ID>
   ```

### Add New Required Reviewer

If team grows and multiple people can approve prod deployments:

```
Settings → Environments → production → Protection rules → Add reviewer → @new-teammate
```

**IMPORTANT**: Anyone with approve permissions can deploy to prod. Choose carefully.

---

## References

- [GitHub Environments Documentation](https://docs.github.com/en/actions/deployment/targeting-different-environments/using-environments-for-deployment)
- [Required Reviewers](https://docs.github.com/en/actions/deployment/targeting-different-environments/using-environments-for-deployment#required-reviewers)
- Project: `docs/PROMOTION_WORKFLOW_DESIGN.md`
- Project: `infrastructure/docs/CREDENTIAL_SEPARATION_SETUP.md`
