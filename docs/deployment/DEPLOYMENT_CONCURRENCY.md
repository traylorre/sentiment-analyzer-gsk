# Deployment Concurrency and Race Condition Prevention

## Overview

The promotion pipeline uses GitHub Actions concurrency controls and Terraform state locking to prevent race conditions during deployments.

## Concurrency Groups by Environment

Each environment has its own concurrency group to prevent race conditions:

| Environment | Concurrency Group | Workflow |
|-------------|-------------------|----------|
| Dev | `terraform-deploy-dev` | `deploy-dev.yml` |
| Preprod | `deploy-preprod` | `build-and-promote.yml` |
| Production | `deploy-production` | `deploy-prod.yml` |
| Production-Auto | `deploy-production` | `deploy-prod.yml` |

**Key insight:** `production` and `production-auto` share the same concurrency group, preventing Dependabot and human deploys from racing.

## Race Condition Scenarios Prevented

### Scenario 1: Concurrent Dev Deployments
**Without protection:**
```
Time: 0s  → Commit A merges → deploy-dev starts
Time: 30s → Commit B merges → deploy-dev starts
Result: Both try to deploy to dev simultaneously ❌
```

**With concurrency control:**
```yaml
# .github/workflows/deploy-dev.yml
concurrency:
  group: terraform-deploy-dev
  cancel-in-progress: false
```

Result: Second deployment queues and waits for first to complete ✅

### Scenario 2: Concurrent Preprod Deployments
**Without protection:**
```
Time: 0s  → Commit A merges → build-and-promote starts
Time: 30s → Commit B merges → build-and-promote starts
Result: Both try to deploy to preprod simultaneously ❌
```

**With concurrency control:**
```yaml
# .github/workflows/build-and-promote.yml
concurrency:
  group: deploy-preprod
  cancel-in-progress: false
```

Result: Second deployment queues and waits for first to complete ✅

### Scenario 3: Concurrent Production Deployments (Dependabot + Human)
**Without protection:**
```
Time: 0s  → Dependabot PR merges → production-auto deploys
Time: 30s → You manually trigger prod deploy
Result: Both try to deploy to production simultaneously ❌
```

**With concurrency control:**
```yaml
# .github/workflows/deploy-prod.yml
concurrency:
  group: deploy-production  # Same group for both production and production-auto
  cancel-in-progress: false
```

Result: Second deployment queues and waits for first to complete ✅

## Complete Deployment Flow with Concurrency Checkpoints

```
┌─────────────────────────────────────────────────────────────┐
│ 1. PR Merged to Main                                        │
└────────────────────┬────────────────────────────────────────┘
                     │
                     v
┌─────────────────────────────────────────────────────────────┐
│ 2. Deploy Dev Workflow                                      │
│    Concurrency: terraform-deploy-dev                        │
│    Checkpoint: Queues if another dev deploy is running      │
└────────────────────┬────────────────────────────────────────┘
                     │
                     v
┌─────────────────────────────────────────────────────────────┐
│ 3. Build and Promote to Preprod Workflow                    │
│    Concurrency: deploy-preprod                              │
│    Checkpoint: Queues if another preprod deploy is running  │
│    - Builds Lambda packages (ONCE)                          │
│    - Deploys to preprod                                     │
│    - Runs integration tests                                 │
└────────────────────┬────────────────────────────────────────┘
                     │
                     v
┌─────────────────────────────────────────────────────────────┐
│ 4. Deploy to Production Workflow (triggered on success)     │
│    Concurrency: deploy-production                           │
│    Checkpoint: Queues if another prod deploy is running     │
│    Environment: production OR production-auto               │
│    - production: Requires @traylorre approval               │
│    - production-auto: No approval (Dependabot only)         │
│    - Downloads SAME packages from preprod                   │
│    - Deploys to production                                  │
│    - Runs canary tests                                      │
└─────────────────────────────────────────────────────────────┘
```

**Critical invariants:**
- Each stage has its own concurrency group
- Deployments within a stage are serialized (queued)
- Deployments across stages can run in parallel (dev + preprod simultaneously is OK)
- Production and production-auto share a group (Dependabot vs human deploys are serialized)

## How GitHub Actions Concurrency Works

### Concurrency Group Behavior

When a workflow run enters a concurrency group:

1. **Group is empty:** Workflow runs immediately
2. **Group is occupied:** Workflow enters queue
3. **Previous run completes:** Queued workflow starts

```
┌─────────────────────────────────────┐
│  Concurrency Group: deploy-production│
├─────────────────────────────────────┤
│  [Run A] ← Currently running         │
│  [Run B] ← Queued                   │
│  [Run C] ← Queued                   │
└─────────────────────────────────────┘
```

### Cancel vs Queue

```yaml
cancel-in-progress: false  # Queue subsequent runs (RECOMMENDED)
cancel-in-progress: true   # Cancel previous runs (DANGEROUS)
```

**We use `false` because:**
- Canceling mid-deployment can leave infrastructure in inconsistent state
- Queuing ensures each deployment completes fully
- Order is preserved (FIFO)

## Testing for Race Conditions

### Test 1: Rapid Fire Deploys

```bash
# Trigger first deploy
gh workflow run build-and-promote.yml --ref main

# Immediately trigger second (while first running)
gh workflow run build-and-promote.yml --ref main

# Check status
gh run list --workflow build-and-promote.yml --limit 5
```

**Expected output:**
```
in_progress  Build and Promote...  (run 1)
queued       Build and Promote...  (run 2) ← Waiting
```

### Test 2: Dependabot + Manual Deploy

```bash
# Merge Dependabot PR (triggers production-auto)
gh pr merge 123

# Immediately trigger manual deploy
gh workflow run deploy-prod.yml --ref main

# Check status
gh run list --workflow deploy-prod.yml --limit 5
```

**Expected output:**
```
in_progress  Deploy to Production (production-auto)
queued       Deploy to Production (production)
```

### Test 3: Monitor Concurrency in Real-Time

```bash
# Watch workflow runs update every 5 seconds
watch -n 5 'gh run list --workflow deploy-prod.yml --limit 3'
```

## Backup Protection: Terraform State Locking

Even if GitHub concurrency control failed (it won't), Terraform provides a second defense layer:

```yaml
# Terraform commands use:
terraform apply -lock-timeout=5m
```

**How it works:**
1. First deploy creates S3 lock file (`{env}/terraform.tfstate.tflock`)
2. Second deploy waits up to 5 minutes for lock file to be deleted
3. If timeout → fails safely (no corruption)

**Lock file location:**
```
S3 Bucket: sentiment-analyzer-terraform-state-218795110243
Lock Files:
  - dev/terraform.tfstate.tflock
  - preprod/terraform.tfstate.tflock
  - prod/terraform.tfstate.tflock
```

## Proof of No Race Condition

### Layer 1: GitHub Actions Guarantee
**Source:** [GitHub Actions Documentation](https://docs.github.com/en/actions/using-workflows/workflow-syntax-for-github-actions#concurrency)

> "When a concurrent job or workflow is queued, if another job or workflow using the same concurrency group in the repository is in progress, the queued job or workflow will be pending."

**Guarantee:** GitHub Actions **guarantees** sequential execution within a concurrency group.

### Layer 2: Terraform State Lock
**Source:** [Terraform S3 Backend - Native Locking](https://developer.hashicorp.com/terraform/language/backend/s3)

> "S3 native locking uses lock files stored directly in the S3 bucket. Terraform will automatically create a lock file before any operation that could write state, and delete the lock file when the operation completes."

**Guarantee:** Terraform **guarantees** exclusive state access via S3 lock files.

### Layer 3: Idempotent Operations
Even if both layers failed (they won't), Lambda deployments are idempotent:
- S3 upload with same SHA → overwrites with identical content
- Terraform apply with same SHA → detects no changes
- Lambda function update → updates to same code version

## Monitoring Concurrency

### Check Active Deployments

```bash
# Preprod deployments
gh run list --workflow build-and-promote.yml --status in_progress

# Production deployments  
gh run list --workflow deploy-prod.yml --status in_progress
```

### Check Terraform Locks

```bash
# Dev environment
aws s3api head-object \
  --bucket sentiment-analyzer-terraform-state-218795110243 \
  --key dev/terraform.tfstate.tflock

# Preprod environment
aws s3api head-object \
  --bucket sentiment-analyzer-terraform-state-218795110243 \
  --key preprod/terraform.tfstate.tflock

# Production environment
aws s3api head-object \
  --bucket sentiment-analyzer-terraform-state-218795110243 \
  --key prod/terraform.tfstate.tflock
```

### Remove Orphaned Locks

If a lock file exists from a crashed workflow:

```bash
# Remove lock file for specific environment
aws s3 rm s3://sentiment-analyzer-terraform-state-218795110243/prod/terraform.tfstate.tflock

# Or use terraform force-unlock (requires Lock ID from workflow logs)
cd infrastructure/terraform
terraform force-unlock <LOCK_ID>
```

## Recovery from Stuck Locks

If deployment is stuck due to a stale lock:

```bash
# Manual unlock
cd infrastructure/terraform
terraform init -backend-config=backend-prod.hcl
terraform force-unlock <LOCK_ID>

# Or use workflow with force_unlock=true
gh workflow run deploy-dev.yml --ref main \
  -f force_unlock=true
```

## Best Practices

1. **Never cancel running deployments** - Let them complete or fail naturally
2. **Monitor concurrency** - Check for queued workflows regularly
3. **Test concurrency** - Periodically trigger rapid-fire deploys to verify queuing works
4. **Trust the system** - Concurrency controls are automatic and reliable

## References

- [GitHub Actions Concurrency](https://docs.github.com/en/actions/using-workflows/workflow-syntax-for-github-actions#concurrency)
- [Terraform S3 Backend - Native Locking](https://developer.hashicorp.com/terraform/language/backend/s3)
- [S3 Object Operations](https://docs.aws.amazon.com/AmazonS3/latest/userguide/object-operations.html)
