# Branch Protection Rules

> **Purpose**: Prevent accidental or malicious changes to the main branch.
> These rules are critical for 1-year unattended operation.

---

## Required Settings

Go to: **GitHub → Settings → Branches → Add rule** for `main`

### Protect matching branches

- [x] **Require a pull request before merging**
  - [x] Require approvals: **1**
  - [x] Dismiss stale pull request approvals when new commits are pushed
  - [x] Require review from Code Owners

- [x] **Require status checks to pass before merging**
  - [x] Require branches to be up to date before merging
  - Required status checks:
    - `Run Tests` - Unit tests with coverage validation
    - `Code Quality` - Linting with ruff and black
    - `Dependency Vulnerability Scan` - pip-audit security scanning
    - `Analyze` - CodeQL static analysis

- [x] **Require conversation resolution before merging**

- [x] **Require signed commits** (optional but recommended)

- [x] **Do not allow bypassing the above settings**

- [x] **Restrict who can push to matching branches**
  - Only @traylorre (admin)

---

## Auto-Merge Configuration

### Automatic PR Merging

All PRs have auto-merge **automatically enabled** via the `pr-auto-merge-enable.yml` workflow.

**How it works:**
1. Developer creates PR → auto-merge is enabled automatically
2. All required status checks pass → PR auto-merges with squash
3. No manual merge step required

**Workflow File**: `.github/workflows/pr-auto-merge-enable.yml`

**Safety guarantees:**
- All branch protection rules enforced (status checks, approvals, etc.)
- Branch must be up to date with main
- All conversations must be resolved
- Uses squash merge for clean git history

**To disable auto-merge on a specific PR:**
```bash
gh pr merge --disable-auto <PR_NUMBER>
```

**Dependabot PRs:**
Dependabot PRs use a separate workflow (`dependabot-auto-merge.yml`) that:
- Auto-merges patch/minor version updates
- Auto-merges GitHub Actions major updates
- Requires manual review for Python major version updates

---

## Why This Matters

Without branch protection:
- Anyone with push access can force-push to main
- PRs can be merged without review or passing CI
- Malicious code could be deployed directly

With branch protection:
- All changes require PR review
- CI must pass (tests, lint, security scans)
- Audit trail of all changes
- No "oops I pushed to main" accidents

---

## Verification

Run this check periodically:

```bash
# Using GitHub CLI
gh api repos/{owner}/{repo}/branches/main/protection
```

Expected output should show:
- `required_pull_request_reviews.required_approving_review_count: 1`
- `required_status_checks.strict: true`
- `enforce_admins.enabled: true`

---

## Emergency Override

In case of critical production issues requiring immediate fix:

1. Admin can temporarily disable "Do not allow bypassing"
2. Push hotfix directly to main
3. **Immediately re-enable protection**
4. Create PR retroactively documenting the change
5. Document in incident report

**Never leave protection disabled overnight.**

---

## Audit

GitHub automatically logs all branch protection changes in the audit log:
- Settings → Audit log → Filter: `action:protected_branch`

Review this quarterly to ensure no unauthorized changes.
