# Tasks: E2E CI Artifacts

**Feature**: 1277-e2e-ci-artifacts
**Created**: 2026-03-28

## Task List

### Task 1: Change Playwright reporter flag from list to html,list
- **File**: `.github/workflows/pr-checks.yml`
- **Action**: In the `playwright-chaos` job, change `--reporter=list` to `--reporter=html,list` in the "Run chaos E2E tests" step
- **Acceptance**: `grep 'reporter=html,list' .github/workflows/pr-checks.yml` matches; list reporter still provides console output; html reporter generates `playwright-report/` directory
- **Status**: done
- **Dependencies**: none

### Task 2: Add artifact upload step for Playwright HTML report
- **File**: `.github/workflows/pr-checks.yml`
- **Action**: Add `actions/upload-artifact@v7` step after "Run chaos E2E tests" with `if: always()`, name `playwright-chaos-report`, path `frontend/playwright-report/`, retention-days 7
- **Acceptance**: Step exists with correct parameters; uses `@v7` matching repo standard; `if: always()` ensures upload on failure
- **Status**: done
- **Dependencies**: Task 1

### Task 3: Add artifact upload step for Playwright test results
- **File**: `.github/workflows/pr-checks.yml`
- **Action**: Add `actions/upload-artifact@v7` step after the report upload with `if: always()`, name `playwright-chaos-results`, path `frontend/test-results/`, retention-days 7
- **Acceptance**: Step exists with correct parameters; uses `@v7` matching repo standard; `if: always()` ensures upload on failure
- **Status**: done
- **Dependencies**: Task 1

### Task 4: Validate YAML syntax
- **File**: `.github/workflows/pr-checks.yml`
- **Action**: Parse the modified YAML to confirm no syntax errors
- **Acceptance**: `python -c "import yaml; yaml.safe_load(open('.github/workflows/pr-checks.yml'))"` exits 0
- **Status**: done (verified: YAML parses cleanly, reporter flag correct, 4 upload-artifact@v7 steps total)
- **Dependencies**: Task 2, Task 3
