# Tasks: 1279-playwright-verify

## Task 1: Create feature branch
- **Status**: pending
- **File**: N/A (git operation)
- **Action**: `git checkout -b A-1279-playwright-verify origin/main`
- **Depends on**: nothing
- **Verification**: `git branch --show-current` returns `A-1279-playwright-verify`

## Task 2: Apply pydantic pin to requirements-dev.txt
- **Status**: pending
- **File**: `requirements-dev.txt`
- **Action**: Add 2 lines after `-r requirements.txt`:
  ```
  # Override: moto[all]==5.1.22 requires pydantic<=2.12.4, but requirements.txt pins 2.12.5
  pydantic==2.12.4
  ```
- **Depends on**: Task 1
- **Verification**: `grep pydantic requirements-dev.txt` shows the pin

## Task 3: Commit the change (signed)
- **Status**: pending
- **File**: `requirements-dev.txt`
- **Action**: `git add requirements-dev.txt && git commit -S -m "fix(deps): Pin pydantic==2.12.4 in requirements-dev.txt (moto compat)"`
- **Depends on**: Task 2
- **Verification**: `git log -1 --oneline` shows the commit

## Task 4: Push branch to origin
- **Status**: pending
- **File**: N/A (git operation)
- **Action**: `git push -u origin A-1279-playwright-verify`
- **Depends on**: Task 3
- **Verification**: Branch exists on remote

## Task 5: Create PR WITHOUT auto-merge
- **Status**: pending
- **File**: N/A (GitHub operation)
- **Action**: `gh pr create` with title and body. NO `--auto` flag.
- **Depends on**: Task 4
- **Verification**: PR exists, auto-merge NOT enabled

## Task 6: Wait for CI to complete (all jobs)
- **Status**: pending
- **File**: N/A (observation)
- **Action**: Poll `gh pr checks` until all jobs reach terminal state
- **Depends on**: Task 5
- **Verification**: Playwright Chaos Tests shows COMPLETED (pass or fail, NOT cancelled)

## Task 7: Download CI artifacts
- **Status**: pending
- **File**: N/A (download operation)
- **Action**: `gh run download` for playwright-chaos-report and playwright-chaos-results
- **Depends on**: Task 6
- **Verification**: Files exist locally

## Task 8: Analyze and document results
- **Status**: pending
- **File**: `specs/1279-playwright-verify/results.md`
- **Action**: Parse HTML report, extract pass/fail counts and error messages
- **Depends on**: Task 7
- **Verification**: results.md contains test outcomes with evidence
