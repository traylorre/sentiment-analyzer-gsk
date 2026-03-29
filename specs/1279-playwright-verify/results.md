# Results: 1279-playwright-verify

## CI Run Summary

- **PR**: #839 — `fix(deps): Pin pydantic in dev requirements for Playwright CI verification`
- **Run ID**: 23711116583
- **Branch**: `A-1279-playwright-verify`
- **Date**: 2026-03-29

## Overall Result: CANCELLED (auto-merge race)

The PR Merge workflow (`pr-merge.yml`) automatically enables auto-merge on ALL non-Dependabot PRs
via the `enable-auto-merge` job (triggered by `pull_request_target` event). This happens regardless
of whether the PR was created with `--auto` or not.

**Timeline**:
- 14:21:17Z — Auto-merge enabled by PR Merge workflow
- 14:22:56Z — Playwright tests begin executing
- 14:24:42Z — PR merged (required checks passed: Lint, Run Tests, Secrets Scan)
- 14:26:27Z — Playwright job cancelled mid-test (#27 of 31)
- 14:26:29Z — Artifacts partially uploaded

## Pydantic Pin: SUCCESS

The `requirements-dev.txt` pydantic pin was merged successfully. This resolves the moto
compatibility issue for dev/local environments.

## Playwright Partial Results (27 of 31 tests attempted)

### Tests That Passed (9 unique tests)

| # | File | Test Name | Duration |
|---|------|-----------|----------|
| 1 | chaos-accessibility.spec.ts:29 | health banner has zero critical accessibility violations | 9.2s |
| 14 | chaos-cross-browser.spec.ts:27 | health banner appears after 3 failures | 4.6s |
| 21 | chaos-degradation.spec.ts:31 | health banner appears after 3 consecutive API failures | 4.6s |
| 22 | chaos-degradation.spec.ts:52 | health banner dismissal emits console event | 4.6s |
| 23 | chaos-degradation.spec.ts:76 | health banner auto-clears on recovery | 4.7s |
| 24 | chaos-degradation.spec.ts:110 | single failure does not trigger banner | 5.6s |
| 25 | chaos-degradation.spec.ts:145 | cross-endpoint success prevents banner despite other endpoint failures | 7.1s |
| 26 | chaos-degradation.spec.ts:193 | dismissed banner reappears on new degradation cycle | 8.6s |
| 27 | chaos-error-boundary.spec.ts:36 | error boundary fallback renders with recovery actions | 3.2s |

### Tests That Failed (5 unique tests, all retried 3x)

| # | File | Test Name | Failure Category |
|---|------|-----------|-----------------|
| 2-4 | chaos-accessibility.spec.ts:68 | error boundary fallback has zero critical a11y violations | Error boundary a11y |
| 5-7 | chaos-accessibility.spec.ts:109 | error boundary buttons are keyboard-focusable with accessible labels | Error boundary a11y |
| 8-10 | chaos-cached-data.spec.ts:39 | previously loaded data remains visible during API outage | Cached data |
| 11-13 | chaos-cached-data.spec.ts:69 | cached data survives API timeout | Cached data |
| 15-17 | chaos-cross-browser.spec.ts:35 | cached data persists during API outage | Cached data |
| 18-20 | chaos-cross-browser.spec.ts:69 | SSE reconnection issues new fetch after connection drop | SSE lifecycle |

### Tests Never Reached (4 remaining tests from chaos-error-boundary + chaos-scenarios + chaos-sse-*)

The run was cancelled after test #27. Files not started:
- `chaos-error-boundary.spec.ts` (partially started — 1 of ~4 tests ran)
- `chaos-scenarios.spec.ts` (not started)
- `chaos-sse-lifecycle.spec.ts` (not started)
- `chaos-sse-recovery.spec.ts` (not started)

## Failure Analysis

### Category 1: Cached Data Tests (3 unique failures)
All cached data tests fail because the test expects data to persist when the API is intercepted,
but the page snapshot shows the dashboard loaded WITHOUT cached data visible. The error-context
files show either an empty chart state or a ticker search state, not previously-loaded data.

**Root cause hypothesis**: The mock API server does not seed data before the test intercepts
routes, so there is nothing cached to persist.

### Category 2: Accessibility Tests (2 unique failures)
The error boundary renders correctly (page snapshot confirms "Something went wrong" heading,
Try Again/Reload Page/Go Home buttons), but the a11y audit fails. The error-context shows
the error boundary IS rendering — the a11y violation is likely a missing ARIA attribute or
color contrast issue in the error boundary UI.

### Category 3: SSE Reconnection (1 unique failure)
The SSE reconnection test takes ~17s per attempt and fails all 3 retries. The page snapshot
shows the dashboard in a "Track Price & Sentiment" empty state, suggesting the SSE connection
never established or the page navigated away.

## Artifacts

### Available
- `playwright-chaos-results` (2.7MB): 20 directories with page snapshots and 6 trace.zip files
- Downloaded to: `/tmp/playwright-1279-artifacts/results/`

### Not Available
- `playwright-chaos-report` (HTML report): Not generated — run was cancelled before Playwright
  could write the report. The `if: always()` step found no files at `frontend/playwright-report/`.

## Critical Discovery: Auto-Merge Blocks Playwright Observation

The PR Merge workflow (`pr-merge.yml`, Job 3: "Enable Auto-Merge") uses
`peter-evans/enable-pull-request-automerge@v3` on ALL non-Dependabot PRs via the
`pull_request_target` event. This means:

1. Creating a PR WITHOUT `--auto` does NOT prevent auto-merge
2. The workflow itself enables auto-merge on every PR
3. Required checks (Lint, Run Tests, Secrets Scan) pass in ~3 minutes
4. Playwright takes ~5+ minutes (with retries for failures)
5. Playwright will ALWAYS be cancelled by auto-merge

**To actually observe Playwright**, one of these approaches is needed:
1. **Disable auto-merge after PR creation**: `gh pr merge --disable-auto 839`
2. **Add Playwright to required checks**: Update branch protection
3. **Use `workflow_dispatch`**: Trigger the workflow manually on a branch (no PR merge race)
4. **Modify the auto-merge job**: Add a condition to skip for specific labels (e.g., `no-auto-merge`)

## Recommendations

### Immediate (next PR)
- After creating the PR, immediately run `gh pr merge --disable-auto <PR_NUMBER>`
- Or trigger the workflow manually via `workflow_dispatch`

### Long-term
- Add a `no-auto-merge` label check to the Enable Auto-Merge job
- Consider adding Playwright to required checks once tests are stable

## Scorecard

| Metric | Value |
|--------|-------|
| Unique tests passed | 9 |
| Unique tests failed | 6 |
| Tests not reached | ~20 (cancelled) |
| Total test files | 8 |
| Files completed | 4 of 8 (partially) |
| Pydantic pin | MERGED |
| HTML report | NOT GENERATED |
| Test results artifacts | PARTIAL (6 failures with traces) |
