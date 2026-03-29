# Research: E2E CI Artifacts

**Feature**: 1277-e2e-ci-artifacts
**Created**: 2026-03-28

## Problem Statement

Playwright chaos tests run in CI via the `playwright-chaos` job in `pr-checks.yml`. When tests fail, developers cannot diagnose root causes because:

1. No HTML report is uploaded -- the only output is console log lines from `--reporter=list`
2. No screenshots or DOM snapshots are preserved from failures
3. No trace files are uploaded (Playwright generates traces on first retry per config: `trace: 'on-first-retry'`)

This caused an entire debugging session to be spent guessing at CI failures.

## Current State Analysis

### Workflow: `.github/workflows/pr-checks.yml`

The `playwright-chaos` job (lines 284-325):
- Installs Python deps, Node deps, Playwright Chromium
- Runs: `npx playwright test tests/e2e/chaos-*.spec.ts --project="Desktop Chrome" --reporter=list`
- Has `timeout-minutes: 5`
- **No artifact upload step** -- all test artifacts are lost when the runner terminates

### Playwright Config: `frontend/playwright.config.ts`

- `reporter: 'html'` -- generates HTML report in `playwright-report/` by default
- `trace: 'on-first-retry'` -- generates trace files in `test-results/` on retries
- `retries: process.env.CI ? 2 : 0` -- CI gets 2 retries, so traces ARE generated

### Existing Artifact Patterns in Repo

The repo already uses `actions/upload-artifact@v7` consistently:
- `pr-checks.yml` line 115: coverage report upload with `retention-days: 30`
- `pr-checks.yml` line 170: pip-audit results with `retention-days: 90`
- `deploy.yml`: multiple artifact uploads with `retention-days: 7`

## Key Findings

1. **Reporter override**: The workflow uses `--reporter=list` which overrides the config's `reporter: 'html'`. To get both, use `--reporter=html,list`.
2. **Artifact version**: The repo standardizes on `actions/upload-artifact@v7`, not v4 as originally suggested.
3. **Output directories**: Playwright generates:
   - `playwright-report/` -- HTML report (from `html` reporter)
   - `test-results/` -- Screenshots, DOM snapshots, trace files (from test execution)
4. **Retention**: Deploy workflow uses 7-day retention for ephemeral artifacts. This matches the feature requirement.
5. **if: always()**: Required to upload artifacts even when tests fail (which is the primary use case).
