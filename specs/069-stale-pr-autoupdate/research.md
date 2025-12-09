# Research: Stale PR Auto-Update

**Feature**: 069-stale-pr-autoupdate
**Date**: 2025-12-08

## Research Tasks & Findings

### 1. GitHub API for Updating PR Branches

**Question**: What API endpoint updates a PR branch with the base branch?

**Finding**: The `PUT /repos/{owner}/{repo}/pulls/{pull_number}/update-branch` endpoint performs a merge from the base branch into the PR branch.

**API Details**:
```
PUT /repos/{owner}/{repo}/pulls/{pull_number}/update-branch
```

**Request Body** (optional):
```json
{
  "expected_head_sha": "string"  // Optional: fails if head doesn't match
}
```

**Response Codes**:
| Code | Meaning |
|------|---------|
| 202 | Accepted - Update in progress |
| 403 | Forbidden - Insufficient permissions |
| 422 | Unprocessable - Branch cannot be updated (conflicts or already up to date) |

**Canonical Source**: [GitHub REST API - Update a pull request branch](https://docs.github.com/en/rest/pulls/pulls#update-a-pull-request-branch)

---

### 2. GitHub Actions Path Filtering

**Question**: How to trigger workflow only when workflow files change?

**Finding**: Use `on.push.paths` with glob patterns.

**Syntax**:
```yaml
on:
  push:
    branches: [main]
    paths:
      - '.github/workflows/**'
```

**Behavior**:
- Workflow triggers ONLY if pushed files match at least one path pattern
- `**` matches any number of directory levels
- Multiple patterns are OR'd together

**Canonical Source**: [GitHub Actions - Workflow syntax for paths](https://docs.github.com/en/actions/using-workflows/workflow-syntax-for-github-actions#onpushpull_requestpull_request_targetpathspaths-ignore)

---

### 3. GITHUB_TOKEN Permissions

**Question**: What permissions does GITHUB_TOKEN need?

**Finding**: The default GITHUB_TOKEN needs `contents: write` and `pull-requests: write` permissions.

**Required Permissions**:
```yaml
permissions:
  contents: write        # To push updates to PR branches
  pull-requests: write   # To access PR information
```

**Note**: These permissions are available by default in most repository configurations but should be explicitly declared for clarity.

**Canonical Source**: [GitHub Actions - Permissions for GITHUB_TOKEN](https://docs.github.com/en/actions/security-guides/automatic-token-authentication#permissions-for-the-github_token)

---

### 4. GitHub CLI in Actions

**Question**: How to use `gh` CLI in GitHub Actions?

**Finding**: The `gh` CLI is pre-installed on all GitHub-hosted runners. Set `GH_TOKEN` environment variable for authentication.

**Usage**:
```yaml
- name: Use GitHub CLI
  env:
    GH_TOKEN: ${{ github.token }}
  run: |
    gh pr list --state open --json number -q '.[].number'
```

**Pre-installed Tools**:
- `gh` (GitHub CLI) - pre-installed on ubuntu-latest
- `jq` - pre-installed for JSON processing

**Canonical Source**: [GitHub Actions - Using the GitHub CLI](https://docs.github.com/en/actions/using-workflows/using-github-cli-in-workflows)

---

### 5. Error Handling Strategy

**Question**: How to handle PRs that can't be updated (conflicts)?

**Finding**: The API returns 422 when a PR has merge conflicts. Use `|| true` or conditional logic to continue processing other PRs.

**Pattern**:
```bash
if gh api repos/REPO/pulls/$pr/update-branch -X PUT 2>/dev/null; then
  echo "✓ Updated"
else
  echo "⚠ Skipped (likely conflicts)"
fi
```

**Rationale**: Failing on one PR should not block updates to other PRs.

---

## Summary

| Research Item | Status | Finding |
|---------------|--------|---------|
| Update branch API | Complete | `PUT /pulls/{n}/update-branch` returns 202/422 |
| Path filtering | Complete | `on.push.paths: ['.github/workflows/**']` |
| Permissions | Complete | `contents: write`, `pull-requests: write` |
| GitHub CLI | Complete | Pre-installed, use `GH_TOKEN` env var |
| Error handling | Complete | Continue on 422, log skipped PRs |

## Sources

- [GitHub REST API - Update a pull request branch](https://docs.github.com/en/rest/pulls/pulls#update-a-pull-request-branch)
- [GitHub Actions - Workflow syntax](https://docs.github.com/en/actions/using-workflows/workflow-syntax-for-github-actions)
- [GitHub Actions - GITHUB_TOKEN permissions](https://docs.github.com/en/actions/security-guides/automatic-token-authentication)
- [GitHub CLI in workflows](https://docs.github.com/en/actions/using-workflows/using-github-cli-in-workflows)
