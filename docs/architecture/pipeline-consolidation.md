# Pipeline Architecture Mistake and Resolution

## Problem

The original deployment pipeline was incorrectly implemented as **4 separate workflows** chained together using `workflow_run` triggers:

1. `pipeline-1-build.yml` (triggered by push)
2. `pipeline-2-deploy-preprod.yml` (workflow_run of #1)
3. `pipeline-3-test-preprod.yml` (workflow_run of #2)
4. `pipeline-4-deploy-prod.yml` (workflow_run of #3)

### Why This Failed

GitHub Actions has a **3-level limit on workflow_run chaining**. From the [official documentation](https://docs.github.com/en/actions/using-workflows/events-that-trigger-workflows#workflow_run):

> You can't use workflow_run to chain together more than three levels of workflows.

This caused:
- `startup_failure` errors for the 4th workflow
- "BuildFailed" placeholder workflows appearing in the Actions UI
- Manual intervention required to progress through stages
- Confusion about why automation wasn't working

## Root Cause

**Misuse of `workflow_run`**. This trigger is designed for **cross-workflow coordination** (e.g., security scanning after a build), not for sequential deployment pipelines.

## Correct Pattern

Use **a single workflow with multiple jobs connected via `needs:`**:

```yaml
jobs:
  build:
    # builds artifacts

  deploy-preprod:
    needs: build
    # deploys to preprod

  test-preprod:
    needs: deploy-preprod
    # tests preprod

  deploy-prod:
    needs: test-preprod
    # deploys to prod
```

### Benefits

- ✅ **No nesting limits** - Jobs can depend on each other without artificial constraints
- ✅ **Shared artifacts** - Artifacts uploaded in one job are accessible to all subsequent jobs
- ✅ **Single workflow view** - All stages visible in one place
- ✅ **Automatic progression** - Jobs run automatically when dependencies succeed
- ✅ **Environment gates** - Use `environment:` for approval requirements
- ✅ **Concurrency control** - Single `concurrency:` group prevents conflicts

## Solution

Replaced the 4 separate workflows with `.github/workflows/deploy.yml`, which contains 6 jobs:

1. `build` - Package Lambda functions
2. `deploy-preprod` - Deploy to preprod environment
3. `test-preprod` - Run integration tests against preprod
4. `deploy-production` - Deploy validated artifacts to production
5. `canary-test` - Health check production deployment
6. `summary` - Report overall pipeline status

## Lessons Learned

1. **Read the documentation carefully** - The 3-level limit is documented but easy to miss
2. **Use the right tool for the job** - `workflow_run` ≠ deployment pipeline
3. **Test early** - This architectural mistake wasted hours debugging phantom issues
4. **Question assumptions** - When something seems unnecessarily complex, investigate alternatives

## Migration Impact

- **Breaking change**: Old workflow files deleted
- **No data loss**: Artifacts and history preserved
- **Same functionality**: All stages work the same way
- **Better UX**: Clearer progression, fewer manual steps

## Date

2025-11-22
