# Quickstart: Dependabot Auto-Merge Configuration Audit

**Feature**: 067-dependabot-automerge-audit
**Date**: 2025-12-08

## Prerequisites

- GitHub repository admin access
- GitHub CLI (`gh`) authenticated

## Implementation Steps

### Step 1: Enable GitHub Actions PR Approval Permission (P1 - Critical)

This is the root cause of approval failures.

**Via GitHub Web UI:**
1. Go to https://github.com/traylorre/sentiment-analyzer-gsk/settings/actions
2. Scroll to "Workflow permissions"
3. Check "Allow GitHub Actions to create and approve pull requests"
4. Click "Save"

**Verification:**
```bash
# Check if the setting is now enabled (requires admin)
gh api repos/traylorre/sentiment-analyzer-gsk --jq '.permissions'
```

### Step 2: Rebase Existing Dependabot PRs (P2)

PRs are stuck with `mergeStateStatus: BEHIND`.

```bash
# Comment on each PR to trigger rebase
for pr in 309 310 311; do
  gh pr comment $pr --body "@dependabot rebase"
  echo "Requested rebase for PR #$pr"
done
```

**Wait 1-2 minutes for Dependabot to rebase each PR.**

### Step 3: Verify Auto-Merge Activation

After rebase completes:

```bash
# Check auto-merge status for grouped PRs (should be enabled)
for pr in 309 310 311; do
  echo "PR #$pr:"
  gh pr view $pr --json autoMergeRequest,mergeStateStatus --jq '{auto: (.autoMergeRequest.enabledAt // "NOT ENABLED"), status: .mergeStateStatus}'
done
```

**Expected output:**
```
PR #309:
{"auto":"2025-12-08T17:32:24Z","status":"CLEAN"}
```

### Step 4: Create Missing Labels (P3 - Optional)

```bash
# Create labels for better PR filtering
gh label create "dependencies" --color "0366d6" --description "Pull requests that update a dependency" --force
gh label create "python" --color "3572A5" --description "Python dependency updates" --force
gh label create "github-actions" --color "000000" --description "GitHub Actions dependency updates" --force
gh label create "terraform" --color "7B42BC" --description "Terraform dependency updates" --force

# Verify
gh label list | grep -E "dependencies|python|github-actions|terraform"
```

### Step 5: Handle Major Version PRs (Manual Review)

PRs #312 (pytest) and #313 (pre-commit) are **major version updates** and correctly require manual review.

**Options:**
1. Review and merge manually if breaking changes are acceptable
2. Close with `@dependabot close` if not ready
3. Pin to current major version in `requirements.txt`

```bash
# View major version PRs
gh pr view 312  # pytest 8→9
gh pr view 313  # pre-commit 3→4
```

## Success Criteria Verification

| Criterion | Command | Expected Result |
|-----------|---------|-----------------|
| SC-001: Minor/patch auto-merge | `gh pr view 309 --json autoMergeRequest` | `enabledAt` not null |
| SC-002: Major blocks auto-merge | `gh pr view 313 --json autoMergeRequest` | `null` |
| SC-003: Labels applied | `gh pr view 309 --json labels` | Has "dependencies", "python" |
| SC-004: Zero manual intervention | Monitor over 30 days | No stuck PRs |

## Troubleshooting

### Auto-merge still not working after rebase

1. Check branch protection requires status checks:
```bash
gh api repos/traylorre/sentiment-analyzer-gsk/branches/main/protection/required_status_checks
```

2. Verify all required checks pass:
```bash
gh pr checks 309
```

### Approval still failing

Verify the repository setting is saved:
```bash
# Re-trigger the workflow
gh pr close 309 && gh pr reopen 309
# Or request rebase again
gh pr comment 309 --body "@dependabot rebase"
```

### Labels not appearing on new PRs

Dependabot may need a new PR to apply labels. Wait for next update cycle or manually trigger:
```bash
# Check for new updates
gh api repos/traylorre/sentiment-analyzer-gsk/dependabot/alerts
```
