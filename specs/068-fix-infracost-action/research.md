# Research: Fix Infracost Cost Check Workflow Failure

**Feature**: 068-fix-infracost-action
**Date**: 2025-12-08

## Research Tasks & Findings

### 1. Infracost Actions Repository Structure

**Question**: What actions are available in the infracost/actions repository?

**Finding**: The repository contains only two action entry points:
- `infracost/actions@v3` - Root action.yml (composite action for full workflow)
- `infracost/actions/setup@v3` - Setup action that installs Infracost CLI

**Evidence** (from `gh api repos/infracost/actions/contents`):
```
.github/
scripts/
setup/           ← Only subfolder action
action.yml       ← Root action
README.md
```

**Key Discovery**: The `comment/` subfolder that `infracost/actions/comment@v1` referenced **no longer exists**. It was removed in favor of CLI-based commenting.

**Canonical Source**: [infracost/actions Repository](https://github.com/infracost/actions)

---

### 2. Infracost CLI Comment Command

**Question**: What is the correct CLI syntax for posting PR comments?

**Finding**: The `infracost comment github` command provides equivalent functionality.

**CLI Syntax**:
```bash
infracost comment github \
  --path /path/to/infracost.json \
  --repo OWNER/REPO \
  --github-token $GITHUB_TOKEN \
  --pull-request PR_NUMBER \
  --behavior update|new|hide-and-new|delete-and-new
```

**Required Flags**:
| Flag | Description | Value in Workflow |
|------|-------------|-------------------|
| `--path` | Path to Infracost JSON output | `/tmp/infracost-diff.json` |
| `--repo` | GitHub repository (owner/repo) | `$GITHUB_REPOSITORY` |
| `--github-token` | Token for GitHub API | `${{ github.token }}` |
| `--pull-request` | PR number | `${{ github.event.pull_request.number }}` |
| `--behavior` | Comment behavior | `update` (create or update single comment) |

**Canonical Source**: [Infracost CLI comment command](https://www.infracost.io/docs/features/cli_commands/#comment)

---

### 3. GitHub Actions Context Variables

**Question**: What environment variables are available for the CLI command?

**Finding**: All required values are available in the GitHub Actions context.

| Variable | Source | Description |
|----------|--------|-------------|
| `$GITHUB_REPOSITORY` | Environment | `owner/repo` format |
| `${{ github.token }}` | Context | GITHUB_TOKEN with PR write access |
| `${{ github.event.pull_request.number }}` | Event payload | PR number |

**Canonical Source**: [GitHub Actions Context](https://docs.github.com/en/actions/learn-github-actions/contexts)

---

### 4. Behavior Options

**Question**: What does `--behavior update` do?

**Finding**: The `update` behavior (matching the deprecated action's default):
- Creates a single comment on first run
- Updates the same comment on subsequent runs
- "Quietest" option - avoids comment spam on PRs

**Alternatives**:
| Behavior | Description |
|----------|-------------|
| `update` | Create or update single comment (recommended) |
| `new` | Always create new comment |
| `hide-and-new` | Hide previous, create new |
| `delete-and-new` | Delete previous, create new |

**Canonical Source**: [Infracost comment behaviors](https://www.infracost.io/docs/features/cli_commands/#comment)

---

## Process Improvement Evaluation

### Should `/add-methodology` be invoked?

**Evaluated Methodology**: `/workflow-action-validate` - Detect deprecated GitHub Actions

**Decision**: **No** - Not warranted at this time

**Rationale**:

1. **Frequency (Low)**
   - First occurrence of deprecated action breaking CI
   - GitHub Actions deprecations are infrequent
   - Not a recurring problem pattern

2. **Detection Complexity (High)**
   - Would require querying upstream repos for each action
   - GitHub API rate limits apply
   - Action version semantics vary (v1, v3, @main, @sha)

3. **Existing Mitigations**
   - Dependabot already alerts on action updates
   - GitHub shows warnings for deprecated actions in UI
   - Upstream repos typically provide migration docs

4. **Cost-Benefit Analysis**
   - Methodology implementation: ~4-8 hours
   - Annual time saved: ~1 hour (estimated 1-2 occurrences)
   - ROI: Negative - not justified

**Alternative Action**: Document this failure pattern in CLAUDE.md under "Lessons Learned" section.

---

## Summary

| Research Item | Status | Finding |
|---------------|--------|---------|
| Available actions | Complete | Only `setup/` subfolder; `comment/` removed |
| CLI syntax | Complete | `infracost comment github` with required flags |
| Context variables | Complete | All values available in workflow |
| Behavior options | Complete | `update` matches deprecated action default |
| Process improvement | Complete | Not warranted - document as lesson learned |

## Sources

- [infracost/actions Repository](https://github.com/infracost/actions)
- [Infracost CLI comment command](https://www.infracost.io/docs/features/cli_commands/#comment)
- [Infracost GitHub Actions Integration](https://www.infracost.io/docs/integrations/github_actions/)
- [GitHub Actions Context Reference](https://docs.github.com/en/actions/learn-github-actions/contexts)
