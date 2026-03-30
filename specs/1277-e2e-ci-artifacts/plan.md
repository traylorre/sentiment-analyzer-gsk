# Implementation Plan: E2E CI Artifacts

**Feature**: 1277-e2e-ci-artifacts
**Created**: 2026-03-28
**Spec**: [spec.md](spec.md)

## Summary

Add Playwright HTML report and test result artifact uploads to the `playwright-chaos` CI job. Switch reporter from `list` to `html,list` for dual output. Upload artifacts with `if: always()` and 7-day retention.

## Design Decision

**Approach**: Add `--reporter=html,list` and two `actions/upload-artifact@v7` steps.

**Alternatives considered**:
1. **Modify `playwright.config.ts` to always output HTML**: Already does (`reporter: 'html'`), but the CLI `--reporter=list` overrides it. Changing the config would affect local dev experience. Rejected.
2. **Use `PLAYWRIGHT_HTML_REPORT` env var**: Unnecessary complexity. Playwright defaults `playwright-report/` directory which is standard. Rejected.
3. **Single combined artifact**: Merging `playwright-report/` and `test-results/` into one artifact loses semantic separation. The report is for viewing; results are for trace analysis. Rejected.
4. **Upload only on failure**: Missing the ability to review passing test reports (useful for performance analysis, screenshot comparison). Using `if: always()` matches repo conventions. Rejected.

## Implementation Steps

### Step 1: Change reporter flag

**File**: `.github/workflows/pr-checks.yml`
**Line**: 322

Change `--reporter=list` to `--reporter=html,list`.

This enables dual output: HTML report files written to `frontend/playwright-report/` and real-time console output via list reporter.

### Step 2: Add artifact upload steps

**File**: `.github/workflows/pr-checks.yml`
**After**: Line 323 (end of "Run chaos E2E tests" step)

Add two `actions/upload-artifact@v7` steps with `if: always()` and `retention-days: 7`.

The steps are placed before `timeout-minutes: 5` (which is a job-level key, not a step).

## Verification

1. YAML syntax: `python -c "import yaml; yaml.safe_load(open('.github/workflows/pr-checks.yml'))"` -- parses without error
2. Visual inspection: The `playwright-chaos` job now has 8 steps (was 6) -- checkout, python setup, python deps, node setup, node deps, playwright install, run tests, upload report, upload results
3. Reporter flag: `grep 'reporter=html,list' .github/workflows/pr-checks.yml` -- matches
4. Artifact names: Both artifacts have unique names (`playwright-chaos-report`, `playwright-chaos-results`)

## Risk Assessment

- **Risk**: None. CI-only workflow change. No production code, test logic, or config changes.
- **Rollback**: Revert the single file change.
