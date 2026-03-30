# Feature Specification: E2E CI Artifacts

**Feature Branch**: `1277-e2e-ci-artifacts`
**Created**: 2026-03-28
**Status**: Draft
**Input**: Modify `.github/workflows/pr-checks.yml` to upload Playwright HTML reports, screenshots, and trace files as CI artifacts so test failures can be diagnosed without guessing.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Diagnosing a Failing Playwright Test in CI (Priority: P1)

A developer pushes a PR that triggers the `playwright-chaos` job. The test fails. The developer navigates to the GitHub Actions run summary, clicks the "playwright-chaos-report" artifact, downloads it, opens `index.html`, and sees the full HTML report with screenshots, DOM snapshots, and trace files for each failed test. They identify the root cause in under 2 minutes instead of guessing.

**Why this priority**: This is the entire reason the feature exists. Without artifacts, CI failures are opaque.

**Independent Test**: Trigger a deliberately failing Playwright test in CI. Verify the artifact is downloadable and contains the HTML report.

**Acceptance Scenarios**:

1. **Given** a Playwright chaos test fails in CI, **When** the workflow run completes, **Then** the "playwright-chaos-report" artifact is available on the GitHub Actions run summary page.
2. **Given** the artifact is downloaded and extracted, **When** the developer opens `index.html`, **Then** the full Playwright HTML report renders with test results, screenshots, and trace links.
3. **Given** all Playwright chaos tests pass, **When** the workflow run completes, **Then** the artifact is still uploaded (the HTML report is useful for confirming what passed).

---

### User Story 2 - Console Output Still Available During Test Run (Priority: P1)

A developer watching the CI run in real time sees test names and pass/fail status streaming in the GitHub Actions log via the `list` reporter. The `html` reporter generates the report file silently alongside.

**Why this priority**: Losing real-time console feedback would be a regression. Both reporters are needed.

**Independent Test**: Check the CI log output for the `Run chaos E2E tests` step. It should show test names with checkmarks/crosses (list reporter format).

**Acceptance Scenarios**:

1. **Given** the reporter is set to `html,list`, **When** tests execute, **Then** the GitHub Actions log shows real-time test results (list format) AND `playwright-report/` directory is generated.

---

### Edge Cases

- What if the `frontend/playwright-report/` directory doesn't exist (e.g., Playwright crashes before generating it)? `actions/upload-artifact@v7` handles missing paths gracefully with a warning, not a failure.
- What if `frontend/test-results/` is empty (all tests pass on first try, no retries triggered)? The directory may not exist or be empty. The artifact upload step uses `if: always()` and won't fail the job if the path is missing.
- What if the artifact exceeds GitHub's 500MB limit? Playwright reports for a small test suite are typically <5MB. Not a concern.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The `playwright-chaos` job MUST use `--reporter=html,list` to generate both HTML report and console output.
- **FR-002**: The `playwright-chaos` job MUST upload `frontend/playwright-report/` as a CI artifact named `playwright-chaos-report`.
- **FR-003**: The `playwright-chaos` job MUST upload `frontend/test-results/` as a CI artifact named `playwright-chaos-results`.
- **FR-004**: Both artifact upload steps MUST use `if: always()` to capture artifacts even on test failure.
- **FR-005**: Both artifacts MUST have `retention-days: 7`.

### Non-Functional Requirements

- **NFR-001**: The artifact upload MUST use `actions/upload-artifact@v7` to match the repo's existing version.
- **NFR-002**: No application code, test code, or Playwright config is modified. This is a CI-only change.
- **NFR-003**: The existing `timeout-minutes: 5` on the job is not modified.

### Out of Scope

- Modifying `playwright.config.ts` (it already has `reporter: 'html'` and `trace: 'on-first-retry'`)
- Uploading artifacts from the deploy workflow's Playwright runs (separate feature if needed)
- Adding Playwright test result annotations to the PR (nice-to-have, future feature)
- Changing the test selection (`chaos-*.spec.ts`) or project (`Desktop Chrome`)

## Technical Design

### Change Summary

Single file modified: `.github/workflows/pr-checks.yml`, `playwright-chaos` job.

### Change 1: Reporter flag

```yaml
# BEFORE:
--reporter=list

# AFTER:
--reporter=html,list
```

The `html` reporter writes to `playwright-report/` (Playwright default output directory). The `list` reporter writes to stdout for real-time CI feedback.

### Change 2: Artifact upload steps

Add two steps after the "Run chaos E2E tests" step:

```yaml
- name: Upload Playwright HTML report
  uses: actions/upload-artifact@v7
  if: always()
  with:
    name: playwright-chaos-report
    path: frontend/playwright-report/
    retention-days: 7

- name: Upload Playwright test results
  uses: actions/upload-artifact@v7
  if: always()
  with:
    name: playwright-chaos-results
    path: frontend/test-results/
    retention-days: 7
```

### Risks

- **None**: CI-only change. No production code, no test logic, no config modification. The worst case is an empty artifact if Playwright crashes before generating reports, which doesn't affect the job outcome.

### Files Changed

| File | Change |
|------|--------|
| `.github/workflows/pr-checks.yml` | Add `html` reporter + 2 artifact upload steps to `playwright-chaos` job |
