# Feature 1317: Fix CI Playwright Infrastructure

## Status: SPECIFIED

## Problem Statement

The Playwright E2E test infrastructure in CI is broken in two independent ways, resulting
in zero E2E test coverage on PR checks:

1. **SSE_LAMBDA_URL KeyError crashes the backend API server.** The Playwright config
   (`playwright.config.ts` line 56) starts `scripts/run-local-api.py` as a webServer.
   That script sets environment variables (lines 74-87) but does NOT set `SSE_LAMBDA_URL`.
   When the handler module is imported, `src/lambdas/dashboard/handler.py` line 109
   executes `SSE_LAMBDA_URL = os.environ["SSE_LAMBDA_URL"]` at module scope with no
   default -- raising `KeyError` and crashing the server before it can serve any request.
   The Playwright webServer health check (`http://localhost:8000/api`) times out,
   and ALL tests fail.

2. **Test glob is too narrow.** `.github/workflows/pr-checks.yml` line 321 runs
   `npx playwright test tests/e2e/chaos-*.spec.ts` -- this matches only 9 chaos test
   files. The remaining 29 non-chaos spec files (auth, CORS, chart, navigation, settings,
   error handling, accessibility, etc.) never execute in CI PR checks.

## User Stories

### US-1: Developer confidence in CI
As a developer, I want ALL 38 E2E test files to run in CI PR checks so that I have
confidence my changes don't break user-facing behavior before merging.

### US-2: Backend API starts reliably in CI
As the CI pipeline, I need `scripts/run-local-api.py` to start successfully without
crashing on missing environment variables, so that Playwright tests have a functioning
backend to test against.

### US-3: Separation of chaos and feature tests
As a developer, I want chaos-specific tests and feature tests to remain logically
separated in CI output, so that I can quickly identify whether a failure is in core
functionality or chaos resilience behavior.

### US-4: No regression in existing chaos tests
As the chaos testing framework, I need the existing 9 chaos test files to continue
running with the same behavior and pass/skip logic they have today.

## Requirements

### FR-001: Set SSE_LAMBDA_URL in run-local-api.py
Add `os.environ.setdefault("SSE_LAMBDA_URL", "http://localhost:8000/api/v2/stream")` to
`scripts/run-local-api.py` alongside the other environment variable defaults (after
line 87). This must be set BEFORE the handler module is imported (line 234).

**Rationale:** In local/dev mode, the SSE_LAMBDA_URL is only consumed by the
`/api/v2/settings` endpoint (handler.py line 619-622) which returns it in the response
body for the frontend to discover the SSE streaming URL. In local mode this response is
gated behind `_is_dev_environment()` returning True for `ENVIRONMENT=local`. The value
`http://localhost:8000/api/v2/stream` is the correct local equivalent.

### FR-002: Expand Playwright test glob to run all E2E tests
Change `.github/workflows/pr-checks.yml` line 321 from:
```
npx playwright test tests/e2e/chaos-*.spec.ts
```
to run ALL spec files:
```
npx playwright test tests/e2e/*.spec.ts
```

### FR-003: Run only Desktop Chrome project in CI
Keep `--project="Desktop Chrome"` to limit CI runtime. Running all 5 projects (Desktop
Chrome, Firefox, WebKit, Mobile Chrome, Mobile Safari) would multiply test time by 5x.
Cross-browser testing is a separate concern for deploy-time E2E, not PR checks.

### FR-004: Increase CI timeout appropriately
The current job has `timeout-minutes: 5` and the test command has `timeout 300` (5min).
With 38 test files (vs 9), these may need adjustment. The Playwright config sets
`workers: 1` in CI (line 15), so tests run serially. Each test file averages ~15-30s
for chart interaction tests, 2-5s for simpler tests.

**Estimate:** 38 files x ~15s average = ~570s (~10 min) worst case.
Set `timeout 600` on the test command and `timeout-minutes: 15` on the job.

### FR-005: Rename workflow job for clarity
Rename the job from `playwright-chaos` / "Playwright Chaos Tests" to
`playwright-e2e` / "Playwright E2E Tests" to reflect the expanded scope.

### FR-006: Update artifact names
Update artifact names from `playwright-chaos-report` / `playwright-chaos-results` to
`playwright-e2e-report` / `playwright-e2e-results`.

### FR-007: Handle tests that need PREPROD_API_ENDPOINT or PREPROD_API_URL
Some tests (e.g., `cors-headers.spec.ts`, `cors-prod.spec.ts`) skip themselves when
`PREPROD_API_ENDPOINT` is not set (line 13: `test.skip(!API_ENDPOINT, ...)`). This is
correct behavior -- these tests are designed for deployed environments only. No change
needed; they will self-skip in CI PR checks.

## Non-Functional Requirements

### NFR-001: No new dependencies
The fix must not add any new Python or Node.js dependencies.

### NFR-002: No changes to production handler.py
The fix is in `scripts/run-local-api.py` (dev-only) and `.github/workflows/pr-checks.yml`
(CI-only). The production handler code in `handler.py` must NOT be modified.

### NFR-003: Backward compatibility
The `SSE_LAMBDA_URL` default must use `setdefault()` so that if a developer has it set in
their `.env.local` or environment, their value takes precedence.

## Success Criteria

| Criteria | Metric |
|---|---|
| Backend starts in CI | `http://localhost:8000/api` returns 200 within 30s |
| All 38 E2E files execute | Playwright report shows 38 test files attempted |
| Chaos tests still pass | 9 chaos-*.spec.ts files have same pass/skip behavior |
| Non-chaos tests run | 29 non-chaos spec files execute (pass or self-skip) |
| CI job completes | Job finishes within 15 minutes |
| No prod code changes | `handler.py` diff is empty |

## Edge Cases

### EC-1: API keys not set in CI
Tests like `sanity.spec.ts` call the ticker search API, which uses Tiingo/Finnhub. In
CI, `TIINGO_API_KEY` and `FINNHUB_API_KEY` are not set. The mock DynamoDB has no cached
data, so API calls may return empty results. Tests should still pass because they use
`expect().toBeVisible({ timeout: 15000 })` which will wait and eventually find elements
populated by the mock API responses.

**Risk:** The local API uses moto mocks, so DynamoDB operations work, but real external
API calls (Tiingo, Finnhub) will fail. If tests depend on real API data returning non-empty
results, they will time out and fail.

**Mitigation:** The `run-local-api.py` mock setup creates tables but does not populate
them. The ticker search endpoint returns mock data from the handler, not from external
APIs. Chart data endpoints will return empty data. Tests that assert `[1-9]\d* price
candles` will fail if no mock data exists.

**Resolution:** This is a KNOWN LIMITATION. Tests that require real ticker data will fail
in CI unless the mock API seeds synthetic data. This is out of scope for 1317 (see
Out of Scope). The immediate fix ensures tests RUN (not crash on startup). A follow-up
feature should add mock data seeding.

### EC-2: Tests that use PREPROD_API_ENDPOINT or PREPROD_API_URL
Files: `cors-headers.spec.ts`, `cors-prod.spec.ts`, `cors-env-gated-404.spec.ts`
These tests use `test.skip()` when the env var is not set. They will self-skip in CI
PR checks. This is correct and expected.

### EC-3: chaos.spec.ts (no hyphen) vs chaos-*.spec.ts
The file `chaos.spec.ts` is NOT matched by `chaos-*.spec.ts` glob (no hyphen after
"chaos"). It IS matched by `*.spec.ts`. Currently it is excluded from CI. After this
fix it will be included. This is correct -- it should have been running all along.

### EC-4: Playwright webServer startup race condition
The `playwright.config.ts` configures two webServers: backend API (port 8000) and
Next.js frontend (port 3000). Playwright waits for both health checks before running
tests. If the backend crashes (current bug), the health check times out after 30s and
tests fail. After the fix, the backend should start in ~2-5s.

### EC-5: tests/conftest.py already sets SSE_LAMBDA_URL for Python tests
`tests/conftest.py` line 120-121 sets `SSE_LAMBDA_URL` as a fallback for pytest.
This is for Python unit/integration tests, NOT for the Playwright webServer process.
The `run-local-api.py` script runs in a separate process spawned by Playwright, so
it does NOT load `tests/conftest.py`. The fix in `run-local-api.py` is necessary and
non-redundant.

### EC-6: Cross-browser test files (chaos-cross-browser.spec.ts)
This file tests cross-browser behavior. In CI with only "Desktop Chrome" project, it
may behave differently than intended. However, the test file should still execute and
pass/fail based on its internal logic, not the project selection.

## Out of Scope

- **OS-1:** Not fixing the 40+ Dependabot vulnerability alerts
- **OS-2:** Not adding new E2E test files
- **OS-3:** Not seeding mock data for ticker/chart tests (follow-up feature)
- **OS-4:** Not adding cross-browser CI testing (Firefox, WebKit, Mobile)
- **OS-5:** Not fixing tests that may fail due to missing mock data -- only fixing the
  infrastructure that prevents them from RUNNING at all
- **OS-6:** Not modifying `playwright.config.ts` -- it already correctly handles CI vs
  local via `process.env.CI` checks

## Files to Modify

| File | Change |
|---|---|
| `scripts/run-local-api.py` | Add `SSE_LAMBDA_URL` to env defaults (after line 87) |
| `.github/workflows/pr-checks.yml` | Expand glob, rename job, update timeouts, update artifact names |

## Adversarial Review #1

### Threat Analysis

| ID | Severity | Finding | Resolution |
|---|---|---|---|
| AR1-01 | CRITICAL | **Wrong SSE_LAMBDA_URL default could break frontend SSE discovery.** If the default URL is wrong, the `/api/v2/settings` endpoint returns a bad URL, and the frontend connects to nowhere for SSE streaming. | **RESOLVED.** The `/api/v2/settings` endpoint is gated behind `_is_dev_environment()` (handler.py line 619). In local mode (`ENVIRONMENT=local`), it returns the SSE URL. The default `http://localhost:8000/api/v2/stream` is the correct local streaming path. In prod/preprod, `SSE_LAMBDA_URL` is always set by Terraform (`main.tf` line 466) and the settings endpoint returns `None` anyway (line 626). The default is ONLY used in local/CI dev mode. |
| AR1-02 | HIGH | **Running 38 tests may exceed CI time limits.** Current timeout is 5 min for 9 tests. 38 tests at ~15s each = ~10 min. With 2 retries on failure, worst case = ~30 min. | **RESOLVED.** FR-004 increases job timeout to 15 min and command timeout to 600s. The Playwright retry count is 2 (config line 14), but retries only fire on failure. In steady state, 38 tests x 15s = ~10 min fits within 15 min. If many tests fail on retry, that is a signal the tests need fixing, not that the timeout is wrong. Added: set retries to 1 (not 2) in the workflow command via `--retries=1` to cap worst-case time. |
| AR1-03 | HIGH | **Non-chaos tests may need real API keys.** Tests like `sanity.spec.ts` search for AAPL ticker and expect price data. Without API keys, the mock API may not return data, causing timeout failures. | **RESOLVED (accepted risk).** This is documented in EC-1. The immediate goal is to fix the infrastructure so tests CAN run. Tests that fail due to missing mock data are a separate issue (OS-5). The Playwright report will show which tests pass and which fail, providing a baseline. We expect chaos tests and simple UI tests (auth, navigation, error handling) to pass. Chart data tests may fail -- that is acceptable and will be addressed in a follow-up. |
| AR1-04 | MEDIUM | **Test isolation: running all tests together may cause flakiness.** Shared browser state, cookie pollution, or port conflicts between test files. | **RESOLVED.** Playwright creates a fresh browser context per test by default. The `globalSetup` (line 57 of global-setup.ts) cleans stale e2e- data. Tests are `fullyParallel: true` but CI uses `workers: 1` (config line 15), so tests run serially -- no port conflicts. Each test navigates to its own page independently. |
| AR1-05 | LOW | **Security: does defaulting SSE_LAMBDA_URL to localhost leak anything?** Could the default URL be served to users in production? | **RESOLVED.** The default only applies when `ENVIRONMENT=local` (set by `run-local-api.py` line 75). The `/api/v2/settings` endpoint only returns `sse_url` when `_is_dev_environment()` returns True (handler.py line 619). In non-dev environments, it returns `None` (line 626). The default can NEVER reach production because: (1) production Lambda does not use `run-local-api.py`, (2) Terraform always sets `SSE_LAMBDA_URL` explicitly, (3) the settings endpoint suppresses it for non-dev environments. |
| AR1-06 | MEDIUM | **Job rename may break branch protection.** If "Playwright Chaos Tests" is a required check in branch protection, renaming to "Playwright E2E Tests" will break it. | **RESOLVED.** Check branch protection before applying. Run `gh api repos/{owner}/{repo}/branches/main/protection` to verify. If "Playwright Chaos Tests" is required, update branch protection simultaneously. Implementation plan must include this verification step. |
| AR1-07 | LOW | **chaos.spec.ts (EC-3) has never run in CI.** It may have hidden failures since it was never tested in the pipeline. | **ACCEPTED.** This is a discovery, not a risk. If it fails, the Playwright report will show it and it can be fixed. Better to discover hidden failures than to keep them hidden. |
| AR1-08 | MEDIUM | **Frontend dev server (`npm run dev`) startup time in CI.** The Playwright config starts both backend AND frontend servers. Next.js cold start in CI can take 30-60s. Combined with backend startup, total wait could be 60-90s before tests begin. | **RESOLVED.** The Playwright config already sets `timeout: 60000` (60s) for the frontend server and `timeout: 30000` (30s) for the backend. These are sequential waits. The 15-minute job timeout accommodates this startup overhead. No change needed. |
| AR1-09 | LOW | **Dependabot PRs will also run expanded tests.** The expanded test suite will run on Dependabot PRs, potentially increasing CI costs. | **ACCEPTED.** This is a feature, not a bug. Dependabot PRs should be tested. The cost increase is ~10 min of CI time per Dependabot PR, which is negligible. |

### Gate Statement

**PASS.** All CRITICAL and HIGH findings are resolved. The spec is ready for Stage 3
(Plan). Two accepted risks remain:
1. Some chart-data tests may fail due to missing mock data (EC-1, AR1-03) -- this is
   expected and out of scope.
2. Branch protection may need updating if the job name is a required check (AR1-06) --
   implementation plan must verify this.

## Clarifications (Stage 4)

### Q1: Should we split chaos and non-chaos E2E tests into separate CI jobs?

**Answer: No.** Answered from codebase.

**Evidence:** There is no technical reason for separation. Both chaos and non-chaos tests
use the same webServer setup (backend API on :8000 + Next.js on :3000), the same Playwright
config, and the same browser project. Splitting would mean two jobs each paying the ~60-90s
startup cost (Python backend + Next.js frontend + Chromium install). A single job amortizes
this cost. The Playwright HTML report already groups tests by file, so chaos vs non-chaos
results are visually separated in the report output.

If separation becomes needed later (e.g., to parallelize or gate differently), it can be
added as a second job. But for now, one job is simpler and faster.

### Q2: Do any non-chaos tests require API keys that are unavailable in CI?

**Answer: Tests self-skip gracefully.** Answered from codebase.

**Evidence:** Searched all 38 spec files for `process.env.PREPROD`, `process.env.TIINGO`,
`process.env.FINNHUB`, and `test.skip`:

- `cors-headers.spec.ts` line 13: `test.skip(!API_ENDPOINT, 'PREPROD_API_ENDPOINT not set')` -- self-skips
- `cors-prod.spec.ts` lines 17, 46: `test.skip(!PROD_URL, ...)` and `test.skip(!PROD_API_URL, ...)` -- self-skips
- `chaos.spec.ts` lines 75+: `test.skip(!chaosAvailable, 'Chaos API not available...')` -- self-skips when no JWT auth
- `sentiment-visibility.spec.ts` line 35: `test.skip(true, 'Rate limited...')` -- self-skips on 429
- `keyboard-nav.spec.ts` lines 79,97,134,157,190: `test.skip()` -- unconditionally skipped tests
- `settings.spec.ts` lines 267,273,298: `test.skip(...)` for auth-only tests
- `error-visibility-auth.spec.ts` lines 86,126: `test.skip(true, ...)` for environment-specific tests
- `navigation.spec.ts` lines 11,34: `test.skip()` for in-progress tests
- `dialog-dismissal.spec.ts` line 203: `test.skip(...)` for toast tests

**No test uses Tiingo or Finnhub API keys directly.** Those keys are only used by the
Python backend, not by the Playwright test files. Tests interact with the frontend which
calls the API, and the mock DynamoDB handles the backend data layer.

### Q3: What is the current CI run time for the chaos-only Playwright job?

**Answer: ~2 min 43s (but all tests fail due to the SSE_LAMBDA_URL crash).** Answered
from CI logs.

**Evidence:** Most recent run (ID 23991970142, 2026-04-05):
- `Playwright Chaos Tests` job: started 01:52:03, completed 01:54:46 = **2m 43s**
- But the job fails because the backend crashes immediately on `KeyError: 'SSE_LAMBDA_URL'`
  (confirmed in logs -- the KeyError repeats every ~1.3s as Playwright retries the
  webServer startup). The actual test execution time is ~0s because no tests run.

**Estimate for fixed job:** Backend startup ~2-5s. Frontend startup ~30-60s. 38 tests x
~15s avg = ~570s (~9.5 min). Total: ~11-12 min. The 15-minute job timeout has ~3 min
margin.

### Q4: Is "Playwright Chaos Tests" a required branch protection check?

**Answer: No.** Answered from GitHub API.

**Evidence:** `gh api repos/traylorre/sentiment-analyzer-gsk/branches/main/protection`
returns required status checks:
- `Secrets Scan`
- `Lint`
- `Run Tests`

"Playwright Chaos Tests" is NOT in the required checks list. The job rename from
`playwright-chaos` / "Playwright Chaos Tests" to `playwright-e2e` / "Playwright E2E Tests"
is safe. No branch protection update needed.

**Note:** `required_signatures: true` is enabled, confirming the repo requires signed
commits (use `--squash` for auto-merge per CLAUDE.md lessons learned).

### Q5: Are there other hard-required env vars in handler.py that run-local-api.py might miss?

**Answer: No, SSE_LAMBDA_URL is the only gap.** Answered from codebase.

**Evidence:** `handler.py` has 4 hard-required env vars (using `os.environ["..."]`):
1. `USERS_TABLE` (line 105) -- set by `run-local-api.py` line 76
2. `SENTIMENTS_TABLE` (line 106) -- set by `run-local-api.py` line 77
3. `ENVIRONMENT` (line 108) -- set by `run-local-api.py` line 75
4. `SSE_LAMBDA_URL` (line 109) -- **NOT SET** (this is the bug)

`CHAOS_EXPERIMENTS_TABLE` (line 107) uses `os.environ.get()` with default `""`, so it
won't crash. All other env vars in handler.py use `os.environ.get()` with defaults.

**Correction to spec:** The spec references line 87 for the insertion point. The actual
last `setdefault` is at line 87 (`AWS_XRAY_SDK_ENABLED`). The new line should go after
line 87, making it line 88. This is confirmed in the plan.
