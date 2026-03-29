# Adversarial Review: E2E CI Artifacts

**Feature**: 1277-e2e-ci-artifacts
**Reviewed**: 2026-03-28
**Reviewer**: Self (adversarial)

## Review Scope

Reviewed: spec.md, plan.md, tasks.md, research.md

## Findings

### Finding 1: Artifact path assumes `cd frontend` context (MEDIUM)

**Issue**: The workflow step runs `cd frontend && timeout 300 npx playwright test ...`. Playwright generates `playwright-report/` relative to where `npx playwright test` is invoked, which is `frontend/`. But the upload step runs at the workspace root. The path `frontend/playwright-report/` is correct.

**Verdict**: No issue. The spec correctly uses `frontend/playwright-report/` and `frontend/test-results/`. The `cd frontend` in the run command means Playwright writes to `$GITHUB_WORKSPACE/frontend/playwright-report/`. The upload path `frontend/playwright-report/` resolves relative to the workspace root. Confirmed correct.

### Finding 2: test-results/ may not exist on all-pass runs (LOW)

**Issue**: When all tests pass on the first attempt (no retries), `test-results/` may be empty or not exist. Playwright only populates it with traces on retries (`trace: 'on-first-retry'`).

**Verdict**: Acceptable. `actions/upload-artifact@v7` emits a warning but doesn't fail the step when the path doesn't exist. The `if: always()` combined with the action's behavior means this is a no-op warning, not a failure. The spec acknowledges this in Edge Cases. No change needed.

### Finding 3: upload-artifact version mismatch with feature description (LOW)

**Issue**: The feature description says `actions/upload-artifact@v4` but the repo uses `@v7` everywhere.

**Verdict**: Research caught this. Spec correctly uses `@v7`. No issue.

### Finding 4: Reporter order matters for output priority (LOW)

**Issue**: `--reporter=html,list` -- does the order affect behavior?

**Verdict**: No. Playwright runs all reporters simultaneously. The `html` reporter writes files; the `list` reporter writes to stdout. Order doesn't matter. No issue.

### Finding 5: Job timeout vs artifact upload time (LOW)

**Issue**: The job has `timeout-minutes: 5`. If tests take close to 5 minutes, will the artifact upload have time to complete?

**Verdict**: The `timeout-minutes` applies to the entire job including all steps. If the test step takes 4:50 of the 5-minute budget, the upload steps might timeout. However: the test step itself has `timeout 300` (5 minutes), and the artifact upload is fast (<10s for small reports). In practice, if the test step uses the full 300s, the job timeout will kill it, but the `if: always()` step will still run within the remaining time. If the job itself times out, no steps run -- but this is the existing behavior and the upload doesn't make it worse.

**Recommendation**: No change. The 5-minute timeout is tight but matches existing behavior. If it becomes an issue, increase `timeout-minutes` in a separate feature.

## Summary

**Verdict**: PASS. No blocking issues found. The spec is tight, correctly scoped, and handles edge cases. Proceed to implementation.

**Changes required**: None.
