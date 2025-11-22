# Lessons Learned: Pipeline Visibility & Transparency

**Date:** 2025-11-22
**Context:** Debugging failed preprod deployments revealed critical UX issues with GitHub Actions pipeline visibility

## Problem Statement

### The Issue
When investigating why PR #28's post-merge deployment failed, the root cause was buried and nearly impossible to find:

1. **GitHub's PR status UI was confusing** - Mixed pre-merge checks with post-merge pipeline results
2. **Workflow names were ambiguous** - "Build and Promote to Preprod" doesn't tell you it's a pipeline stage
3. **No visual hierarchy** - Can't tell at a glance where in the pipeline a change failed
4. **Failures were opaque** - Had to drill through 3-4 UI layers to find actual error: "Secret not found"
5. **No clear stage progression** - Unclear which stages passed and which failed

### User Experience Pain Points

```
❌ BAD: Current experience
1. See "Some checks were not successful" (vague!)
2. Click to see list of workflows
3. See mix of ✅ and ❌ but unclear which workflow matters
4. Click "Details" on suspicious workflow
5. See list of jobs
6. Click failed job
7. Scroll through logs to find error
8. Finally find: "Secret not found"

Result: 7 clicks and 5+ minutes to diagnose
```

```
✅ GOOD: Desired experience
1. See "[5/6] Preprod Integration Tests - FAILED"
2. Click to see: "❌ test_full_ingestion_flow: Secret not found at preprod/newsapi"
3. See recovery command: "gh run rerun <ID>"

Result: 2 clicks and 30 seconds to diagnose
```

## Solution: Pipeline Visibility Improvements

### 1. Clear Naming Convention

**Before:**
- `test.yml` → "Tests (Dev)"
- `build-and-promote.yml` → "Build and Promote to Preprod"

**After:**
```
PR Checks:
- pr-check-lint.yml        → "PR Check: Code Quality"
- pr-check-test.yml        → "PR Check: Unit Tests"
- pr-check-security.yml    → "PR Check: Security Scan"

Pipeline Stages:
- pipeline-1-build.yml          → "[1/6] Build Artifacts"
- pipeline-2-deploy-dev.yml     → "[2/6] Deploy to Dev"
- pipeline-3-test-dev.yml       → "[3/6] Dev Integration Tests"
- pipeline-4-deploy-preprod.yml → "[4/6] Deploy to Preprod"
- pipeline-5-test-preprod.yml   → "[5/6] Preprod Integration Tests"
- pipeline-6-deploy-prod.yml    → "[6/6] Deploy to Production"
```

**Why:** Immediately obvious which workflows are PR checks vs pipeline stages, and where in the pipeline you are.

### 2. Workflow Dependencies (Visual Chain)

Use `workflow_run` to create visual dependency chains in GitHub UI:

```yaml
# pipeline-5-test-preprod.yml
on:
  workflow_run:
    workflows: ["[4/6] Deploy to Preprod"]
    types: [completed]
    branches: [main]
```

**Why:** GitHub shows workflows in a dependency graph, making the pipeline flow obvious.

### 3. Rich Failure Annotations

Add `::error` annotations with actionable information:

```yaml
- name: Report Failure
  if: failure()
  run: |
    echo "::error title=Stage 5 Failed::❌ Preprod Integration Tests FAILED

    Failed test: test_full_ingestion_flow
    Root cause: Secret not found: preprod/sentiment-analyzer/newsapi

    Recovery steps:
    1. Check secret exists: aws secretsmanager describe-secret --secret-id preprod/sentiment-analyzer/newsapi
    2. Verify IAM permissions for preprod CI user
    3. Re-run: gh run rerun ${{ github.run_id }}

    View logs: ${{ github.server_url }}/${{ github.repository }}/actions/runs/${{ github.run_id }}"
```

**Why:** Error shows up prominently in GitHub UI with recovery steps, reducing time-to-resolution.

### 4. README Pipeline Status Dashboard

Visual status badges showing pipeline health at a glance:

```markdown
## Deployment Pipeline Status

| Stage | Workflow | Status |
|-------|----------|--------|
| PR Checks | Code Quality | ![](badge-url) |
| [1/6] | Build Artifacts | ![](badge-url) |
| [2/6] | Deploy to Dev | ![](badge-url) |
| [3/6] | Dev Tests | ![](badge-url) |
| [4/6] | Deploy to Preprod | ![](badge-url) |
| [5/6] | Preprod Tests | ![](badge-url) |
| [6/6] | Deploy to Prod | ![](badge-url) |
```

**Why:** One glance at README shows entire pipeline health without clicking anything.

### 5. Job Grouping with Clear Names

```yaml
jobs:
  test-ingestion:
    name: "Test: Ingestion Lambda (preprod)"
  test-analysis:
    name: "Test: Analysis Lambda (preprod)"
  test-dashboard:
    name: "Test: Dashboard API (preprod)"
```

**Why:** When a stage fails, you can immediately see WHICH component failed.

## Key Principles for Pipeline UX

### Principle 1: **Minimize Time-to-Diagnosis**
Every additional click/page is friction. Aim for 2 clicks max from GitHub homepage to root cause.

### Principle 2: **Progressive Disclosure**
- High-level status (pipeline stage) should be visible immediately
- Details (which test, which component) on first click
- Logs/recovery steps on second click

### Principle 3: **Actionable Error Messages**
Never just say "failed". Always include:
1. What failed (specific test/component)
2. Why it failed (root cause)
3. How to fix it (recovery steps or commands)

### Principle 4: **Clear Stage Progression**
Use numbering ([1/6], [2/6]) so it's always obvious:
- How far the pipeline progressed
- Where it failed
- What stages are blocked

### Principle 5: **Separate Pre-Merge from Post-Merge**
Use distinct prefixes:
- `PR Check:` = Runs on feature branches
- `[N/M]` = Runs on main as part of delivery pipeline

This prevents confusion about which workflows matter when.

## Metrics for Success

**Before improvements:**
- Time to diagnose failure: 5-10 minutes
- Clicks required: 5-7
- Clarity of error: Low (generic "some checks failed")

**After improvements:**
- Time to diagnose failure: < 1 minute
- Clicks required: 1-2
- Clarity of error: High (specific component + root cause + fix)

## Related Decisions

### Why Not Use GitHub Environments for Status?
GitHub Environments show deployment status but don't distinguish between stages well. Our numbering system ([1/6]) is clearer.

### Why Not Use GitHub Actions Summary?
Summaries are good but require clicking into the workflow. Our `::error` annotations surface in the PR checks UI directly.

### Why Rename Files Instead of Just Changing `name:`?
File names appear in GitHub's file browser and grep results. Consistent naming across filename and display name reduces confusion.

## Application to Other Projects

This pattern is valuable for ANY multi-stage pipeline:

```
PR Checks (always):
- pr-check-*

Pipeline Stages (numbere'd):
- pipeline-1-* (build/compile)
- pipeline-2-* (deploy to test env)
- pipeline-3-* (test)
- pipeline-4-* (deploy to staging)
- pipeline-5-* (smoke tests)
- pipeline-6-* (deploy to prod)
```

## References

- GitHub Actions Workflow Syntax: https://docs.github.com/en/actions/using-workflows/workflow-syntax-for-github-actions
- Workflow Commands (`::error`): https://docs.github.com/en/actions/using-workflows/workflow-commands-for-github-actions
- Status Badges: https://docs.github.com/en/actions/monitoring-and-troubleshooting-workflows/adding-a-workflow-status-badge

## Changelog

| Date | Change | Author |
|------|--------|--------|
| 2025-11-22 | Initial documentation of pipeline visibility improvements | Claude |
