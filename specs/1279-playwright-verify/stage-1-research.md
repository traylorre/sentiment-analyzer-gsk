# Stage 1: Research — 1279-playwright-verify

## Research Date
2026-03-28

## Problem Domain
CI observability gap: Playwright Chaos Tests job has been CANCELLED on every PR since its
introduction (#835, #837, #838). Auto-merge kills the workflow before the non-required
Playwright job completes. We have never seen a clean Playwright CI run.

## Key Findings

### 1. Auto-Merge Race Condition
- Required status checks: Secrets Scan, Lint, Run Tests
- Playwright Chaos Tests is NOT a required check
- Auto-merge triggers as soon as the 3 required checks pass (~3-5 min)
- Playwright takes ~5 min (npm ci + playwright install + test run)
- Result: Playwright is always cancelled mid-run

### 2. Pydantic Version Conflict
- `requirements.txt`: `pydantic==2.12.5`
- `requirements-ci.txt`: `pydantic==2.12.4` (override, moto compatibility)
- `requirements-dev.txt`: NO override (inherits 2.12.5 via `-r requirements.txt`)
- `moto[all]==5.1.22` requires `pydantic<=2.12.4`
- CI uses `requirements-ci.txt` (already fixed), but deploy pipeline uses `requirements-dev.txt`

### 3. Artifact Upload Already Configured
- PR #838 (Feature 1277) added `upload-artifact@v7` steps to `playwright-chaos` job
- Artifacts: `playwright-chaos-report` (HTML report) and `playwright-chaos-results` (traces)
- Uses `if: always()` so artifacts upload even on failure
- Retention: 7 days

### 4. Previous Playwright Fixes (Untested)
- PR #835: Accessibility tree race condition fix (1270/1271)
- PR #836: addInitScript for error boundary navigation
- PR #837: 7 remaining failures (1272/1273/1274)
- PR #838: 5 remaining failures (1275/1276/1277) + artifact upload
- None of these have been verified because Playwright was always cancelled

## Strategy
Create a PR with ONLY the pydantic dev pin fix. Do NOT enable auto-merge.
Wait for all CI jobs to complete, including Playwright. Download and analyze artifacts.
