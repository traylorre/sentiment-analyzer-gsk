# Pipeline Visibility Implementation Guide

**Status:** Ready for implementation
**Risk:** Medium (renames workflow files, changes triggers)
**Reversibility:** High (git revert)

## Overview

This guide implements the pipeline visibility improvements documented in LESSONS_LEARNED.md.

## Renaming Map

### PR Check Workflows (unchanged triggers, only rename)

| Current | New | Display Name |
|---------|-----|--------------|
| `lint.yml` | `pr-check-lint.yml` | "PR Check: Code Quality" |
| `test.yml` | `pr-check-test.yml` | "PR Check: Unit Tests" |
| `security.yml` | `pr-check-security.yml` | "PR Check: Security Scan" |
| `codeql.yml` | `pr-check-codeql.yml` | "PR Check: CodeQL Analysis" |

### Pipeline Stage Workflows (add workflow_run dependencies)

| Current | New | Display Name | Trigger |
|---------|-----|--------------|---------|
| `build-and-promote.yml` | `pipeline-1-build-and-deploy-preprod.yml` | "[1/4] Build & Deploy Preprod" | push to main |
| ~~`deploy-dev.yml`~~ | REMOVE | (deprecated - dev is local only now) | - |
| ~~`integration.yml`~~ | REMOVE | (deprecated - merged into pipeline) | - |
| `preprod-validation.yml` | `pipeline-2-test-preprod.yml` | "[2/4] Preprod Integration Tests" | workflow_run: pipeline-1 |
| `deploy-prod.yml` | `pipeline-3-deploy-prod.yml` | "[3/4] Deploy to Production" | workflow_dispatch |

### Utility Workflows (keep as-is)

| Current | Purpose | Keep? |
|---------|---------|-------|
| `dependabot-auto-merge.yml` | Auto-merge dependabot PRs | ✅ Yes |
| `pr-approval-enforcement.yml` | Require approvals | ✅ Yes |

## Implementation Phases

### Phase 1: Rename PR Check Workflows (Low Risk)

These run on PRs only, safe to rename:

```bash
cd .github/workflows
git mv lint.yml pr-check-lint.yml
git mv test.yml pr-check-test.yml
git mv security.yml pr-check-security.yml
git mv codeql.yml pr-check-codeql.yml
```

Then update each file's `name:` field:
- `pr-check-lint.yml` → `name: "PR Check: Code Quality"`
- `pr-check-test.yml` → `name: "PR Check: Unit Tests"`
- `pr-check-security.yml` → `name: "PR Check: Security Scan"`
- `pr-check-codeql.yml` → `name: "PR Check: CodeQL Analysis"`

### Phase 2: Consolidate and Rename Pipeline Workflows (Medium Risk)

**Current pipeline is confusing:**
- `build-and-promote.yml` builds AND deploys preprod AND runs tests
- `deploy-dev.yml` exists but we don't use dev environment anymore
- `integration.yml` exists but overlaps with build-and-promote

**Proposed simplification:**

**Option A: Keep current structure, just rename**
```
pipeline-1-build-and-deploy-preprod.yml  (was: build-and-promote.yml)
├─ Job: Build Lambda Packages
├─ Job: Deploy to Preprod
└─ Job: Preprod Integration Tests

pipeline-2-deploy-prod.yml (was: deploy-prod.yml)
└─ Job: Deploy to Production
```

**Option B: Split into logical stages (more work)**
```
pipeline-1-build.yml
└─ Build Lambda packages

pipeline-2-deploy-preprod.yml
└─ Deploy to preprod

pipeline-3-test-preprod.yml
└─ Preprod integration tests

pipeline-4-deploy-prod.yml
└─ Deploy to production
```

**RECOMMENDATION: Option A** (less disruptive, can refactor later)

### Phase 3: Add Failure Annotations

Add to each workflow job:

```yaml
- name: Report Test Failure
  if: failure()
  run: |
    echo "::error title=${{ github.workflow }} Failed::\
    Stage: ${{ github.job }}

    View logs: ${{ github.server_url }}/${{ github.repository }}/actions/runs/${{ github.run_id }}

    Quick commands:
    - gh run view ${{ github.run_id }} --log-failed
    - gh run rerun ${{ github.run_id }}"
```

### Phase 4: Add Workflow Dependencies

Update pipeline workflows to use `workflow_run`:

```yaml
# pipeline-2-deploy-prod.yml
on:
  workflow_run:
    workflows: ["[1/4] Build & Deploy Preprod"]
    types: [completed]
    branches: [main]
  workflow_dispatch:  # Keep manual trigger
```

### Phase 5: Create Status Dashboard

Add to README.md:

```markdown
## Deployment Pipeline

[![PR Checks](https://github.com/traylorre/sentiment-analyzer-gsk/actions/workflows/pr-check-test.yml/badge.svg)](https://github.com/traylorre/sentiment-analyzer-gsk/actions/workflows/pr-check-test.yml)

### Pipeline Stages

| Stage | Workflow | Status |
|-------|----------|--------|
| [1/4] Build & Deploy Preprod | [pipeline-1](https://github.com/traylorre/sentiment-analyzer-gsk/actions/workflows/pipeline-1-build-and-deploy-preprod.yml) | ![Status](https://github.com/traylorre/sentiment-analyzer-gsk/actions/workflows/pipeline-1-build-and-deploy-preprod.yml/badge.svg) |
| [2/4] Preprod Tests | [pipeline-2](https://github.com/traylorre/sentiment-analyzer-gsk/actions/workflows/pipeline-2-test-preprod.yml) | ![Status](https://github.com/traylorre/sentiment-analyzer-gsk/actions/workflows/pipeline-2-test-preprod.yml/badge.svg) |
| [3/4] Deploy to Prod | [pipeline-3](https://github.com/traylorre/sentiment-analyzer-gsk/actions/workflows/pipeline-3-deploy-prod.yml) | ![Status](https://github.com/traylorre/sentiment-analyzer-gsk/actions/workflows/pipeline-3-deploy-prod.yml/badge.svg) |
```

## Testing Strategy

### Phase 1 Testing
1. Rename PR check workflows
2. Create a test PR
3. Verify all checks run with new names
4. Verify branch protection rules still work

### Phase 2 Testing
1. Rename pipeline workflows
2. Push a test commit to main
3. Verify pipeline runs in correct order
4. Check failure scenarios work

### Phase 3 Testing
1. Force a test failure
2. Verify error annotations appear in UI
3. Verify commands work

## Rollback Plan

If anything breaks:

```bash
# Rollback to previous commit
git revert HEAD
git push origin main

# Or manual file rename
cd .github/workflows
git mv pr-check-lint.yml lint.yml
# ... etc
```

## Execution Order

**Recommended:** Implement in one PR with all phases, test on feature branch first:

```bash
git checkout -b feat/pipeline-visibility-improvements

# Phase 1: Rename PR checks
git mv .github/workflows/lint.yml .github/workflows/pr-check-lint.yml
# ... (all renames)

# Phase 2-5: Make other changes

# Test on PR
git push origin feat/pipeline-visibility-improvements
# Create PR, verify all checks run

# Merge when confident
```

## Breaking Changes

### Workflows that reference old names

Check for any scripts or documentation that hardcode workflow names:

```bash
grep -r "build-and-promote.yml" .
grep -r "test.yml" .
grep -r "deploy-dev.yml" .
```

### Branch Protection Rules

Verify branch protection rules in GitHub settings don't reference specific workflow names. They should use the display name, not filename.

## Success Criteria

After implementation:

- [ ] PR checks clearly labeled "PR Check: ..."
- [ ] Pipeline stages numbered [1/N]
- [ ] Failed workflows show actionable error with recovery commands
- [ ] README shows pipeline status badges
- [ ] All existing functionality preserved
- [ ] Branch protection still works

## Next Steps

1. Review this implementation guide
2. Decide on Option A vs Option B for pipeline structure
3. Create feature branch
4. Implement Phase 1 (safest)
5. Test thoroughly
6. Implement remaining phases
7. Merge when confident

## Files to Modify

### Workflow Files (11 total)
- .github/workflows/*.yml (all renamed)

### Documentation
- README.md (add status dashboard)
- docs/LESSONS_LEARNED.md (already created)

### Potential Updates Needed
- Any scripts that reference workflow names
- CI/CD documentation
- Runbooks/playbooks

## Estimated Time

- Phase 1: 15 min
- Phase 2: 30 min
- Phase 3: 45 min
- Phase 4: 20 min
- Phase 5: 15 min
- Testing: 60 min

**Total:** ~3 hours (including testing)
