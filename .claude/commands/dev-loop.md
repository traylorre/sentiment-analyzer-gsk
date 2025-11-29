---
description: Continuous development loop with periodic CI monitoring. Implements work → commit → push → monitor pipeline cycle.
---

## User Input

```text
$ARGUMENTS
```

You **MUST** consider the user input before proceeding (if not empty).

## Overview

This command implements a streamlined development workflow that:
1. Continues working on the current task until ready for commit
2. Commits and pushes changes to remote
3. Periodically checks CI pipeline status for the current branch
4. Interrupts development to fix pipeline failures when detected
5. Returns to main development work when pipeline is healthy

## Workflow State Machine

```
┌─────────────────────────────────────────────────────────────────┐
│                                                                 │
│  ┌──────────┐    commit/push    ┌──────────┐    check CI       │
│  │ DEVELOP  │ ───────────────── │ PUSHED   │ ──────────────┐   │
│  └──────────┘                   └──────────┘               │   │
│       ▲                              │                     ▼   │
│       │                              │              ┌──────────┐│
│       │ CI passing                   │              │ MONITOR  ││
│       │ or in progress               │              └──────────┘│
│       │                              │                     │   │
│       │                              ▼                     │   │
│       │                        ┌──────────┐                │   │
│       └─────────────────────── │ CI CHECK │ ◄──────────────┘   │
│                                └──────────┘                    │
│                                      │                         │
│                                      │ CI failed               │
│                                      ▼                         │
│                                ┌──────────┐                    │
│                                │   FIX    │ ───┐               │
│                                └──────────┘    │ fixed         │
│                                      ▲         │               │
│                                      └─────────┘               │
└─────────────────────────────────────────────────────────────────┘
```

## Execution Steps

### Step 1: Initialize Context

Determine the current development context:

```bash
# Get current branch
current_branch=$(git branch --show-current)

# Get any pending work context (from TodoWrite or tasks.md)
# Check if there's an active feature spec
```

Report:
- Current branch: `{branch_name}`
- Pending tasks: `{count}` from todo list or tasks.md
- Last commit: `{short_sha} - {message}`

### Step 2: Development Phase

Continue working on the current task. This means:

1. **If user provided arguments**: Work on the specified task
2. **If todo list has in_progress items**: Continue that work
3. **If tasks.md exists with incomplete tasks**: Pick up next task
4. **Otherwise**: Ask user what to work on

Work until you reach a logical commit point:
- A complete task from tasks.md
- A meaningful unit of work (feature, fix, refactor)
- User explicitly requests commit

### Step 3: Commit and Push

When ready to commit:

```bash
# Check for changes
git status --porcelain

# Stage changes (be selective - don't stage unrelated files)
git add <relevant-files>

# Create signed commit with descriptive message
git commit -S -m "$(cat <<'EOF'
<type>(<scope>): <description>

<body if needed>

🤖 Generated with [Claude Code](https://claude.com/claude-code)

Co-Authored-By: Claude <noreply@anthropic.com>
EOF
)"

# Push to remote (set upstream if needed)
git push -u origin $(git branch --show-current)
```

### Step 4: CI Pipeline Check

After push, check pipeline status:

```bash
# Get latest workflow runs for current branch
gh run list --branch $(git branch --show-current) --limit 5 --json databaseId,status,conclusion,name,createdAt

# Check for any in-progress or failed runs
```

#### Pipeline Status Interpretation

| Status | Conclusion | Action |
|--------|------------|--------|
| `in_progress` | - | Pipeline running, continue development |
| `completed` | `success` | All checks passed, continue development |
| `completed` | `failure` | **INTERRUPT**: Switch to fix mode |
| `completed` | `cancelled` | Check why, likely a newer run superseded |
| `queued` | - | Pipeline starting, continue development |

### Step 5: Branch on Pipeline State

#### If Pipeline is Passing or In Progress

```markdown
## CI Status: ✅ Healthy

| Workflow | Status | Duration |
|----------|--------|----------|
| PR Check: Unit Tests | ✅ success | 2m 15s |
| PR Check: Code Quality | ✅ success | 45s |
| PR Check: Security | 🔄 in_progress | - |

Continuing development...
```

Return to **Step 2** and continue working on the next task.

#### If Pipeline Failed

```markdown
## CI Status: ❌ Failed

| Workflow | Status | Failed Step |
|----------|--------|-------------|
| PR Check: Unit Tests | ❌ failure | Run tests |
| PR Check: Code Quality | ✅ success | - |

Switching to fix mode...
```

Proceed to **Step 6**.

### Step 6: Pipeline Fix Mode

When pipeline fails:

1. **Identify the failure**:
   ```bash
   # Get failed run details
   gh run view <run-id> --log-failed
   ```

2. **Categorize the failure**:
   - **Test failure**: Read test output, identify failing test, fix code or test
   - **Lint failure**: Run `black` and `ruff --fix` locally
   - **Security failure**: Review flagged code, apply security fix
   - **Coverage failure**: Add missing tests
   - **Terraform failure**: Fix infrastructure config

3. **Apply the fix**:
   - Make minimal, targeted changes to fix the specific issue
   - Don't introduce unrelated changes during fix mode
   - Run local verification before pushing:
     ```bash
     # For test failures
     pytest <specific-test-file> -v

     # For lint failures
     black src/ tests/ && ruff check src/ tests/

     # For coverage
     pytest --cov=src --cov-report=term-missing
     ```

4. **Commit the fix**:
   ```bash
   git add <fixed-files>
   git commit -S -m "fix(ci): <description of fix>"
   git push
   ```

5. **Return to Step 4** to verify fix worked

### Step 7: Loop Control

The development loop continues until:
- User explicitly stops (`/stop`, `quit`, or similar)
- No more tasks to work on
- Critical unrecoverable failure

After each cycle, report:
```markdown
## Development Loop Status

**Cycle**: #{n}
**Branch**: {branch}
**Commits this session**: {count}
**CI Status**: {passing|failing|in_progress}
**Current Task**: {task description or "awaiting input"}

### Recent Activity
| Time | Action | Result |
|------|--------|--------|
| 10:30 | Committed T042 | pushed |
| 10:32 | CI Check | passing |
| 10:45 | Committed T043 | pushed |
| 10:47 | CI Check | failed (lint) |
| 10:48 | Fixed lint | pushed |
| 10:50 | CI Check | passing |
```

## CI Check Frequency

- **After every push**: Mandatory check
- **During long development**: Check every ~10 minutes or after significant progress
- **Never wait for CI**: If CI is in_progress, continue development

## Command Variations

### Start with specific task
```
/dev-loop T042 - Implement user authentication
```

### Resume from last session
```
/dev-loop --resume
```

### Fix-only mode (just fix CI, don't develop)
```
/dev-loop --fix-ci
```

## Error Recovery

### Push Rejected
```bash
# Pull and rebase
git pull --rebase origin $(git branch --show-current)
# Resolve conflicts if any, then push again
git push
```

### CI Stuck
```bash
# Cancel stuck run
gh run cancel <run-id>
# Re-trigger
gh workflow run <workflow-name>
```

### Authentication Issues
```bash
# Re-authenticate gh CLI
gh auth login
```

## Integration with Tasks.md

If a `tasks.md` file exists in the active feature spec:

1. **Read task status**: Parse `[X]` (complete) vs `[ ]` (pending)
2. **Pick next task**: Select first pending task respecting dependencies
3. **Mark complete**: After successful push, update tasks.md:
   ```markdown
   - [X] T042: Implement user authentication ← mark complete
   - [ ] T043: Add password reset flow ← next task
   ```

## Example Session

```
> /dev-loop

## Dev Loop Started

**Branch**: feat/008-e2e-validation-suite
**Active Spec**: specs/008-e2e-validation-suite
**Pending Tasks**: 117 (starting with T001)

### Cycle 1

Working on T001: Create tests/e2e/ directory structure...
[Creates directory structure]
[Stages and commits]
[Pushes to origin]

CI Check: 🔄 Pipeline running (PR Check: Unit Tests)

Continuing with T002: Create tests/e2e/__init__.py...
[Creates file]
[Stages and commits]
[Pushes]

CI Check: ✅ All checks passed

### Cycle 2

Working on T003: Create conftest.py with test_run_id fixture...
[Creates conftest.py]
[Commits and pushes]

CI Check: ❌ Failed - PR Check: Code Quality
└── black --check failed (formatting issues)

**Switching to fix mode**

Running: black tests/e2e/conftest.py
[Fixed formatting]
[Commits fix]
[Pushes]

CI Check: ✅ All checks passed

### Cycle 3

Continuing with T004...
```

## Safety Guards

1. **Never force push** - Only regular push
2. **Never skip GPG signing** - All commits must be signed
3. **Never commit secrets** - Check for .env, credentials before staging
4. **Always verify locally** - Run relevant checks before pushing when fixing
5. **Respect branch protection** - Don't try to push directly to main
