# Research: Dependabot Auto-Merge Configuration Audit

**Feature**: 067-dependabot-automerge-audit
**Date**: 2025-12-08

## Research Tasks & Findings

### 1. GitHub Dependabot Grouping Behavior

**Question**: Why does `other-minor-patch` group capture major version updates?

**Finding**: The grouping is configured correctly. Groups with `update-types: ["minor", "patch"]` should only capture minor and patch updates. However, the **individual PRs** for pytest and pre-commit are NOT grouped PRs - they're standalone PRs for major version updates.

**Evidence**:
- PR #312 (pytest 8.3.4→9.0.2): This is a **major** update, correctly NOT in the "testing" group (which only accepts minor/patch)
- PR #313 (pre-commit 3.6.0→4.5.0): This is a **major** update, correctly NOT in the "code-quality" group

**Decision**: No changes needed to grouping configuration. The current config correctly separates major updates from grouped minor/patch updates.

**Canonical Source**: [GitHub Docs - Controlling Dependencies Updated](https://docs.github.com/en/code-security/dependabot/dependabot-version-updates/controlling-dependencies-updated)

---

### 2. GitHub Auto-merge API Permissions

**Question**: Why does workflow show SUCCESS but `autoMergeRequest: null` on some PRs?

**Root Cause Analysis**:

1. **PR #309 (aws-sdk group)**: Auto-merge IS enabled (`enabledAt: 2025-12-08T17:32:24Z`)
2. **PR #313 (pre-commit)**: Auto-merge NOT enabled because it's a **major** update and the workflow correctly skipped the auto-merge step

**Detailed Investigation**:

| PR | Update Type | Auto-Merge Status | Reason |
|----|-------------|-------------------|--------|
| #309 | semver-minor | ENABLED | Correctly detected as minor, `gh pr merge --auto` succeeded |
| #310 | semver-minor | ENABLED (check) | Should be enabled (grouped code-quality) |
| #311 | semver-minor | ENABLED (check) | Should be enabled (grouped other-minor-patch) |
| #312 | semver-major | NOT ENABLED | Correctly blocked (pytest major) |
| #313 | semver-major | NOT ENABLED | Correctly blocked (pre-commit major) |

**Decision**: Auto-merge logic is working correctly. The PRs that show `autoMergeRequest: null` are major updates that were correctly excluded.

**Canonical Source**: [GitHub Docs - Automatically Merging PRs](https://docs.github.com/en/pull-requests/collaborating-with-pull-requests/incorporating-changes-from-a-pull-request/automatically-merging-a-pull-request)

---

### 3. dependabot/fetch-metadata Output

**Question**: What values does `update-type` output contain? How does it handle grouped PRs?

**Finding**: The action outputs:
- `version-update:semver-major`
- `version-update:semver-minor`
- `version-update:semver-patch`

For grouped PRs, it reports the **highest** semver change (e.g., if a group has minor and patch updates, it reports `semver-minor`).

**Evidence** (from workflow logs):
```
outputs.dependency-names: boto3, botocore
outputs.update-type: version-update:semver-minor
outputs.dependency-group: aws-sdk
```

**Known Issue**: For some grouped PRs, `update-type` can be `null` if the commit message doesn't contain the type. The action attempts to calculate it but may fail for complex groups.

**Decision**: Current workflow correctly handles the output. No changes needed.

**Canonical Source**: [dependabot/fetch-metadata README](https://github.com/dependabot/fetch-metadata)

---

### 4. Label Application by Dependabot

**Question**: Why are labels specified in dependabot.yml not being applied?

**Root Cause**: The labels `dependencies`, `python`, `github-actions`, `terraform` **do not exist** in the repository. Only default GitHub labels exist:
- bug, documentation, duplicate, enhancement, good first issue, help wanted, invalid, question, wontfix

Dependabot needs permission to create labels or they must pre-exist.

**Decision**: Create the required labels in the repository.

**Fix Required**:
```bash
gh label create "dependencies" --color "0366d6" --description "Pull requests that update a dependency"
gh label create "python" --color "3572A5" --description "Python dependency updates"
gh label create "github-actions" --color "000000" --description "GitHub Actions dependency updates"
gh label create "terraform" --color "7B42BC" --description "Terraform dependency updates"
```

**Canonical Source**: [GitHub Docs - Dependabot Options Reference](https://docs.github.com/en/code-security/dependabot/dependabot-version-updates/configuration-options-for-the-dependabot.yml-file)

---

### 5. PR Approval Failure

**Question**: Why does the approval step fail?

**Root Cause** (from workflow logs):
```
failed to create review: GraphQL: GitHub Actions is not permitted to approve pull requests.
```

**Fix Required**: Enable "Allow GitHub Actions to create and approve pull requests" in repository settings:
Settings → Actions → General → Workflow permissions → Check "Allow GitHub Actions to create and approve pull requests"

**Decision**: This is a repository settings fix, not a workflow code change.

**Canonical Source**: [GitHub Docs - GITHUB_TOKEN Permissions](https://docs.github.com/en/actions/writing-workflows/choosing-what-your-workflow-does/controlling-permissions-for-github_token)

---

### 6. PRs Not Merging Due to "BEHIND" Status

**Question**: Why are PRs with auto-merge enabled not merging?

**Root Cause**: All Dependabot PRs show `mergeStateStatus: "BEHIND"` - they need to be rebased against main.

**Options**:
1. **Manual rebase**: Use `@dependabot rebase` comment on each PR
2. **Configure rebase strategy**: Dependabot can auto-rebase with `rebase-strategy: auto`
3. **Use update-branch action**: Automatically update branches when behind

**Decision**: Use `@dependabot rebase` comments for existing PRs, then evaluate if auto-rebase configuration is needed.

**Canonical Source**: [Dependabot Commands](https://docs.github.com/en/code-security/dependabot/working-with-dependabot/managing-pull-requests-for-dependency-updates#managing-dependabot-pull-requests-with-comment-commands)

---

## Summary of Root Causes and Fixes

| Issue | Root Cause | Fix Type | Priority |
|-------|------------|----------|----------|
| Major updates not auto-merging | Working as designed | None | N/A |
| Auto-merge showing null | Only for major updates (correct) | None | N/A |
| Labels not applied | Labels don't exist in repo | Create labels | P3 |
| Approval step failing | Repo setting disabled | Enable setting | P1 |
| PRs stuck "BEHIND" | Need rebase | Manual rebase + evaluate auto-rebase | P2 |

## Recommended Actions

### Immediate (P1)
1. Enable "Allow GitHub Actions to create and approve pull requests" in repo settings

### Short-term (P2)
2. Rebase existing Dependabot PRs using `@dependabot rebase` comment
3. Verify auto-merge completes after rebase

### Nice-to-have (P3)
4. Create missing labels for better PR filtering

### Evaluation
5. Consider if `/dependabot-validate` methodology is warranted (likely not - this is a one-time configuration issue)

---

## Future Enhancement: Major Version Auto-Merge Capability

### Current Architecture (T017)

The workflow at `.github/workflows/pr-merge.yml:150` uses `steps.metadata.outputs.update-type` to determine auto-merge eligibility:

```yaml
# Line 150 - Current: Only patch and minor auto-merge
if: steps.metadata.outputs.update-type == 'version-update:semver-patch' ||
    steps.metadata.outputs.update-type == 'version-update:semver-minor'
run: gh pr merge --auto --squash "$PR_URL"
```

### Future Enablement (T018)

To enable major version auto-merge for all Python dependencies, modify line 150:

```yaml
# Add major to the condition
if: steps.metadata.outputs.update-type == 'version-update:semver-patch' ||
    steps.metadata.outputs.update-type == 'version-update:semver-minor' ||
    steps.metadata.outputs.update-type == 'version-update:semver-major'
```

**Consideration**: This would bypass human review for breaking changes. A safer approach would be ecosystem-specific (already implemented for GitHub Actions at line 156-160).

### Recommendation

Maintain current behavior (major requires manual review) unless:
1. Strong test coverage exists to catch breaking changes
2. Rollback procedures are documented
3. Team agrees to accept risk of automated major updates

---

## Sources

- [GitHub Dependabot Documentation](https://docs.github.com/en/code-security/dependabot)
- [dependabot/fetch-metadata Action](https://github.com/dependabot/fetch-metadata)
- [GitHub Auto-merge Documentation](https://docs.github.com/en/pull-requests/collaborating-with-pull-requests/incorporating-changes-from-a-pull-request/automatically-merging-a-pull-request)
- [Automating Dependabot with GitHub Actions](https://docs.github.com/en/code-security/dependabot/working-with-dependabot/automating-dependabot-with-github-actions)
- [GitHub CLI Discussions - gh pr merge permissions](https://github.com/cli/cli/discussions/6379)
