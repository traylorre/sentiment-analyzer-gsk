# Quickstart: Fix Infracost Cost Check Workflow Failure

**Feature**: 068-fix-infracost-action
**Date**: 2025-12-08

## Prerequisites

- Git access to repository
- Editor for YAML files

## The Fix

### Step 1: Locate the Broken Action

Open `.github/workflows/pr-checks.yml` and find lines 270-275:

```yaml
# CURRENT (BROKEN) - lines 270-275
      - name: Post Infracost comment
        uses: infracost/actions/comment@v1
        with:
          path: /tmp/infracost-diff.json
          behavior: update
        continue-on-error: true
```

### Step 2: Replace with CLI Command

Replace the above with:

```yaml
# FIXED - use CLI command instead of deprecated action
      - name: Post Infracost comment
        run: |
          infracost comment github \
            --path /tmp/infracost-diff.json \
            --repo $GITHUB_REPOSITORY \
            --github-token ${{ github.token }} \
            --pull-request ${{ github.event.pull_request.number }} \
            --behavior update
        continue-on-error: true
```

### Step 3: Commit and Push

```bash
git add .github/workflows/pr-checks.yml
git commit -S -m "fix(ci): Replace deprecated infracost/actions/comment with CLI command"
git push origin 068-fix-infracost-action
```

### Step 4: Verify Fix

```bash
# Check that the Cost job passes on this PR
gh pr checks $(gh pr view --json number -q .number)

# Verify blocked PRs can now pass
gh pr checks 312  # pytest major
gh pr checks 313  # pre-commit major
gh pr checks 316  # Feature 067
```

## Success Criteria Verification

| Criterion | Command | Expected Result |
|-----------|---------|-----------------|
| SC-001: Cost check passes | `gh pr checks 316` | Cost: pass |
| SC-002: Future PRs pass | Check this PR's checks | All pass |
| SC-003: Comments work | Submit PR with TF changes | Infracost comment appears |
| SC-004: No regression | Check all PR checks | All other checks pass |
| SC-005: Documented | Read research.md | Process improvement recommendation present |

## Troubleshooting

### If Cost job still fails

1. Check the error message in the job logs:
```bash
gh run view --job JOB_ID --log
```

2. Verify the CLI is installed by the setup action (should be earlier in the job)

3. Check that `INFRACOST_API_KEY` secret is configured:
```bash
gh secret list | grep INFRACOST
```

### If comments don't appear

1. Verify `pull-requests: write` permission is set on the job
2. Check that `/tmp/infracost-diff.json` exists (previous step must succeed)
3. Verify the PR number is correctly passed

## Reference

- [Infracost CLI comment command](https://www.infracost.io/docs/features/cli_commands/#comment)
- [infracost/actions setup](https://github.com/infracost/actions/tree/master/setup)
