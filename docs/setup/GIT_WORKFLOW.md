# Git Workflow & Rebase Policy

## TL;DR

**CRITICAL**: Always rebase feature branches on main before pushing to avoid triggering manual Deploy Pipeline steps.

```bash
# Before every push:
git fetch origin main
git rebase origin/main
git push origin <branch-name> --force-with-lease
```

## Why Rebasing Matters

Our Deploy Pipeline is triggered by pushes to main. When a feature branch is merged without rebasing:
- Creates merge commits
- Requires manual intervention to trigger deployment
- Clutters git history

**Solution**: Pre-push hook enforces rebasing before pushing feature branches.

## Setup Git Hooks

After cloning the repository:

```bash
./scripts/setup-git-hooks.sh
```

This installs a pre-push hook that:
- ✅ Checks if feature branch is rebased on main
- ✅ Blocks push if branch has diverged
- ✅ Provides clear fix instructions
- ✅ Ensures Deploy Pipeline triggers automatically

## Standard Workflow

### 1. Create Feature Branch

```bash
git checkout main
git pull origin main
git checkout -b feat/my-feature
```

### 2. Work on Feature

```bash
# Make changes
git add .
git commit -m "feat: Add feature"
```

### 3. Before Pushing (CRITICAL STEP)

```bash
# Fetch latest main
git fetch origin main

# Rebase your branch on main
git rebase origin/main

# If conflicts, resolve them:
# 1. Fix conflicts in files
# 2. git add <resolved-files>
# 3. git rebase --continue

# Push with force-with-lease (safer than --force)
git push origin feat/my-feature --force-with-lease
```

### 4. Create Pull Request

The pre-push hook will verify you've rebased before allowing the push.

### 5. If Main Changes While PR is Open

```bash
# Fetch latest main
git fetch origin main

# Rebase again
git rebase origin/main

# Push updated branch
git push origin feat/my-feature --force-with-lease
```

## Pre-Push Hook Behavior

The hook checks feature branches matching these patterns:
- `feat/*` - New features
- `fix/*` - Bug fixes
- `docs/*` - Documentation
- `chore/*` - Maintenance
- `refactor/*` - Code refactoring
- `test/*` - Test additions
- `style/*` - Code style changes
- `perf/*` - Performance improvements

### Successful Push (Rebased)

```bash
$ git push origin feat/my-feature
Checking if branch is rebased on main...
✓ Branch is rebased on latest main
To https://github.com/user/repo.git
   abc123..def456  feat/my-feature -> feat/my-feature
```

### Blocked Push (Not Rebased)

```bash
$ git push origin feat/my-feature
Checking if branch is rebased on main...
✗ ERROR: Branch is not rebased on latest main!

Your branch has diverged from main. You must rebase before pushing.

To fix this, run:
  git fetch origin main
  git rebase origin/main

After resolving any conflicts:
  git push origin feat/my-feature --force-with-lease
```

## Bypassing the Hook (NOT RECOMMENDED)

In rare cases where you need to bypass the hook:

```bash
git push --no-verify
```

**Warning**: This will create merge commits and require manual Deploy Pipeline intervention.

## Common Scenarios

### Scenario 1: Simple Rebase

```bash
# Your branch: feat/my-feature
# Main has moved forward with commits A and B

git fetch origin main
git rebase origin/main
# Rebase successful, no conflicts
git push origin feat/my-feature --force-with-lease
```

### Scenario 2: Rebase with Conflicts

```bash
git fetch origin main
git rebase origin/main
# CONFLICT in file.py

# Fix conflicts in file.py
git add file.py
git rebase --continue

# If more conflicts, repeat:
# 1. Fix conflicts
# 2. git add <files>
# 3. git rebase --continue

# Once done:
git push origin feat/my-feature --force-with-lease
```

### Scenario 3: Abort Rebase

```bash
git rebase origin/main
# Too many conflicts, want to start over

git rebase --abort
# Back to original state
```

### Scenario 4: Multiple PRs Open

```bash
# You have feat/feature-a and feat/feature-b

# Rebase feature-a
git checkout feat/feature-a
git fetch origin main
git rebase origin/main
git push origin feat/feature-a --force-with-lease

# Rebase feature-b
git checkout feat/feature-b
git fetch origin main
git rebase origin/main
git push origin feat/feature-b --force-with-lease
```

## Why --force-with-lease?

`--force-with-lease` is safer than `--force`:

```bash
# GOOD: Checks remote hasn't changed
git push origin feat/my-feature --force-with-lease

# RISKY: Overwrites remote unconditionally
git push origin feat/my-feature --force
```

If someone else pushed to your branch, `--force-with-lease` will reject the push:

```bash
$ git push origin feat/my-feature --force-with-lease
error: failed to push some refs to 'origin'
hint: Updates were rejected because the remote contains work that you do
hint: not have locally. This is usually caused by another repository pushing
```

Solution: Pull and rebase:

```bash
git pull --rebase origin feat/my-feature
git push origin feat/my-feature --force-with-lease
```

## Troubleshooting

### "fatal: refusing to merge unrelated histories"

This means branches have completely diverged. Contact team lead.

### "error: cannot rebase: You have unstaged changes"

Commit or stash your changes first:

```bash
git stash
git rebase origin/main
git stash pop
```

### "detached HEAD state"

During rebase, you're in detached HEAD. This is normal. Complete the rebase:

```bash
git rebase --continue  # after fixing conflicts
# OR
git rebase --abort     # to cancel
```

### Hook not running

Reinstall hooks:

```bash
./scripts/setup-git-hooks.sh
```

Verify hook is executable:

```bash
ls -la .git/hooks/pre-push
# Should show: -rwxr-xr-x (executable)
```

## References

- [Git Rebase Documentation](https://git-scm.com/docs/git-rebase)
- [Git Hooks Documentation](https://git-scm.com/docs/githooks)
- [Atlassian: Merging vs Rebasing](https://www.atlassian.com/git/tutorials/merging-vs-rebasing)
