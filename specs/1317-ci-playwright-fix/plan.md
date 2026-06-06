# Feature 1317: Fix CI Playwright Infrastructure — Implementation Plan

## Technical Context

### File 1: `scripts/run-local-api.py`

**Current state (lines 74-87):** Sets 10 environment variables via `os.environ.setdefault()`:
- ENVIRONMENT, USERS_TABLE, SENTIMENTS_TABLE, CHAOS_EXPERIMENTS_TABLE, OHLC_CACHE_TABLE
- AWS_DEFAULT_REGION, AWS_REGION, CLOUD_REGION, AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY
- AWS_XRAY_SDK_ENABLED (line 87)

**Missing:** `SSE_LAMBDA_URL` — required by `handler.py` line 109 (`os.environ["SSE_LAMBDA_URL"]`
with no default). The handler is imported at line 234 (`from src.lambdas.dashboard.handler
import lambda_handler`), which is AFTER the env setup block. So adding the setdefault before
line 89 ensures it's set before import.

**Also missing:** `CORS_ORIGINS` — handler.py line 115 reads this. Currently defaults to empty
string via `os.environ.get("CORS_ORIGINS", "")`, so it won't crash, but it logs a warning
(line 120-123). Not a blocker but worth noting.

### File 2: `.github/workflows/pr-checks.yml`

**Current state (lines 284-341):** Job `playwright-chaos` with name "Playwright Chaos Tests":
- Line 321: `timeout 300 npx playwright test tests/e2e/chaos-*.spec.ts`
- Line 341: `timeout-minutes: 5`
- Lines 329, 337: Artifact names `playwright-chaos-report`, `playwright-chaos-results`

**Branch protection check result:** Required checks are:
- `Secrets Scan`
- `Lint`
- `Run Tests`

**"Playwright Chaos Tests" is NOT a required check.** The rename from `playwright-chaos` to
`playwright-e2e` is safe — no branch protection update needed.

### File 3: `src/lambdas/dashboard/handler.py` (READ-ONLY verification)

**Line 109:** `SSE_LAMBDA_URL = os.environ["SSE_LAMBDA_URL"]` — confirmed, no default, crashes
on KeyError.

**Line 619-622:** Settings endpoint returns `SSE_LAMBDA_URL` only when `_is_dev_environment()`
returns True. In local mode (`ENVIRONMENT=local`), this is the correct behavior.

**No changes to this file.** (NFR-002)

### File 4: `frontend/playwright.config.ts` (READ-ONLY verification)

**Line 14:** `retries: process.env.CI ? 2 : 0` — the config defaults to 2 retries in CI.
The workflow command can override this with `--retries=1` per AR1-02.

**Line 15:** `workers: process.env.CI ? 1 : undefined` — serial execution in CI. Confirmed.

**Line 55-57:** WebServer command uses `cd .. && python scripts/run-local-api.py` in CI.

**No changes to this file.** (OS-6)

## Implementation Plan

### Change 1: `scripts/run-local-api.py` — Add SSE_LAMBDA_URL default

**Location:** After line 87 (`os.environ.setdefault("AWS_XRAY_SDK_ENABLED", "false")`)

**Add:**
```python
os.environ.setdefault("SSE_LAMBDA_URL", "http://localhost:8000/api/v2/stream")
```

**Rationale:** Must be set BEFORE handler import at line 234. Placed with the other
`setdefault()` calls for readability. Uses `setdefault()` per NFR-003 so existing env
values take precedence.

**Lines affected:** Insert 1 line after line 87. No existing lines modified.

### Change 2: `.github/workflows/pr-checks.yml` — Full job update

**2a. Job ID rename (line 285):**
```yaml
# Before
  playwright-chaos:
# After
  playwright-e2e:
```

**2b. Job name rename (line 286):**
```yaml
# Before
    name: Playwright Chaos Tests
# After
    name: Playwright E2E Tests
```

**2c. Expand test glob + update timeout + add retries override (line 321):**
```yaml
# Before
          timeout 300 npx playwright test tests/e2e/chaos-*.spec.ts \
            --project="Desktop Chrome" \
            --reporter=html,list
# After
          timeout 600 npx playwright test tests/e2e/*.spec.ts \
            --project="Desktop Chrome" \
            --retries=1 \
            --reporter=html,list
```

**2d. Update artifact name (line 329):**
```yaml
# Before
          name: playwright-chaos-report
# After
          name: playwright-e2e-report
```

**2e. Update artifact name (line 337):**
```yaml
# Before
          name: playwright-chaos-results
# After
          name: playwright-e2e-results
```

**2f. Update job timeout (line 341):**
```yaml
# Before
    timeout-minutes: 5
# After
    timeout-minutes: 15
```

### Change 3: `pip install -e .` — Missing from Playwright job

**Observation:** The `test` job (line 93) runs `pip install -e .` after installing
requirements. The `playwright-chaos` job (line 303) only runs `pip install -r requirements-ci.txt`
without `pip install -e .`. The `run-local-api.py` script does `from src.lambdas.dashboard.handler
import lambda_handler` which requires the `src` package to be importable.

**However:** Line 322-324 of `run-local-api.py` adds the repo root to `sys.path`:
```python
src_path = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, src_path)
```
This makes `src.lambdas.dashboard.handler` importable without `pip install -e .`.

**Decision:** No change needed. The `sys.path` manipulation handles it.

## Summary of Changes

| File | Lines | Change | Risk |
|---|---|---|---|
| `scripts/run-local-api.py` | +1 after line 87 | Add `SSE_LAMBDA_URL` setdefault | LOW — follows existing pattern |
| `.github/workflows/pr-checks.yml` | 7 edits in lines 283-341 | Rename job + comment, expand glob, update timeouts, rename artifacts | LOW — no branch protection conflict |

**Total:** 2 files, ~8 line-level changes. Zero production code changes.

## Risk Assessment

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| Some non-chaos tests fail due to missing mock data | HIGH | LOW | Expected and documented (EC-1). Tests failing is better than tests not running. |
| `chaos.spec.ts` (EC-3) fails — never ran in CI before | MEDIUM | LOW | Discovery is the point. Fix if needed. |
| Job timeout exceeded with 38 tests + retries | LOW | MEDIUM | 38 tests x 15s avg = ~10 min. With 1 retry on failures, worst case ~20 min. 15 min limit will catch if too slow. Can increase later. |
| Frontend `npm run dev` slow to start in CI | LOW | LOW | Already has 60s timeout in playwright.config.ts. Well within 15 min job limit. |
| Other jobs affected by PR | NONE | — | Only touching the playwright job and a dev-only script. |

## Verification Plan

### Pre-merge verification
1. **Local smoke test:** Run `cd frontend && npx playwright test tests/e2e/*.spec.ts --project="Desktop Chrome" --retries=1 --reporter=list` locally to verify all 38 files attempt to run.
2. **Backend startup test:** Run `python scripts/run-local-api.py` and verify it starts without KeyError.
3. **CI pipeline run:** Push the branch, create PR, verify the `Playwright E2E Tests` job:
   - Starts successfully (no webServer timeout)
   - Runs all 38 test files
   - Chaos tests maintain same pass/skip behavior
   - Job completes within 15 minutes
   - Artifacts upload with new names

### Post-merge verification
4. **Branch protection still works:** Verify required checks (`Secrets Scan`, `Lint`, `Run Tests`) still gate merges. The renamed playwright job is NOT a required check, so no impact.

## Rollback Plan

**If backend still crashes:**
- Revert the `run-local-api.py` change
- Check if `SSE_LAMBDA_URL` is the only missing env var (search handler.py for other `os.environ["..."]` calls)

**If too many tests fail:**
- Keep the infrastructure fix (SSE_LAMBDA_URL)
- Revert glob from `*.spec.ts` back to `chaos-*.spec.ts`
- Create follow-up to expand incrementally

**If CI timeout exceeded:**
- Increase `timeout-minutes` to 20
- Or increase `timeout` command to 900

**Full revert:** `git revert <commit>` — single commit, clean revert.

## Dependency Order

No dependencies between changes. Both can be applied in a single commit:
1. `scripts/run-local-api.py` — add env var (fixes crash)
2. `.github/workflows/pr-checks.yml` — expand glob + rename + timeouts (runs all tests)

Both changes are required for the feature to work. Partial application:
- Only change 1 → Backend starts, but still only runs 8/38 chaos tests
- Only change 2 → Backend still crashes, ALL 38 tests fail (worse than before)

**Recommendation:** Single atomic commit with both changes.

## Adversarial Review #2

### Spec Drift Analysis

| ID | Category | Finding | Severity | Resolution |
|---|---|---|---|---|
| AR2-01 | Spec drift | **Spec says "9 chaos test files" matched by `chaos-*.spec.ts`, but only 8 match.** Files: chaos-accessibility, chaos-cached-data, chaos-cross-browser, chaos-degradation, chaos-error-boundary, chaos-scenarios, chaos-sse-lifecycle, chaos-sse-recovery. The 9th chaos file (`chaos.spec.ts`) does NOT match `chaos-*.spec.ts` because there is no hyphen. The spec uses "9" in the Problem Statement (line 19), FR-002 (implicit), Success Criteria (line 114), and AR1-03 (line 196). The plan correctly says "8/38" at line 203. | LOW | **ACCEPTED.** The spec's count is cosmetically wrong but the fix is the same regardless -- expand to `*.spec.ts`. The plan already has the correct understanding. No plan change needed. |
| AR2-02 | Spec drift | **Spec references `/api/v2/settings` endpoint but it does not exist.** FR-001 rationale (line 54), AR1-01 (line 194), and AR1-05 (line 198) all reference `/api/v2/settings` as the endpoint that returns `SSE_LAMBDA_URL`. The actual endpoint is `/api/v2/runtime` (handler.py line 612). The behavior described is correct (gated behind `_is_dev_environment()`), but the endpoint name is wrong. | LOW | **ACCEPTED.** The spec's rationale text has the wrong endpoint name, but the fix is unchanged -- `SSE_LAMBDA_URL` is consumed at module scope (line 109) regardless of which endpoint uses it. The plan does not reference `/api/v2/settings` at all, so no plan drift. Spec documentation error only. |
| AR2-03 | Cross-artifact | **Plan omits updating the YAML comment block at lines 282-284.** The comment says `# JOB: Playwright Chaos Tests (Feature 1265)`. After renaming, this becomes stale. | LOW | **RESOLVED.** Added Change 2g below to update the comment block. |
| AR2-04 | Cross-artifact | **Plan line numbers verified against actual files.** run-local-api.py line 87 = `AWS_XRAY_SDK_ENABLED` (confirmed), handler.py line 109 = `SSE_LAMBDA_URL = os.environ["SSE_LAMBDA_URL"]` (confirmed), handler.py line 234 = `from src.lambdas.dashboard.handler import lambda_handler` (confirmed -- but this is in run-local-api.py, not handler.py), pr-checks.yml lines 285/286/321/329/337/341 all confirmed. | INFO | No drift. |
| AR2-05 | Cross-artifact | **Default URL `http://localhost:8000/api/v2/stream` verified as correct.** The SSE router in `src/lambdas/dashboard/sse.py` line 264 defines `@router.get("/api/v2/stream")`, included in the main app via `router_v2.py` line 2182. The local server runs on port 8000. The URL is valid and reachable when the server is running. | INFO | No drift. |
| AR2-06 | Cross-artifact | **Glob `*.spec.ts` verified safe.** 38 files match in `tests/e2e/`. No non-test `.spec.ts` files exist in that directory (only `global-setup.ts` and `helpers/` directory, neither using `.spec.ts`). node_modules `.spec.ts` files are not caught because the command specifies `tests/e2e/*.spec.ts` as the path. | INFO | No drift. |
| AR2-07 | Security | **`setdefault()` is the correct call (not `os.environ["..."] = "..."`).** `setdefault()` only sets the value if the key is absent. This means: (a) Developer `.env.local` values take precedence (NFR-003), (b) If CI sets the var explicitly, that value wins, (c) The default is only a fallback. Using `os.environ["..."] = "..."` would unconditionally overwrite, breaking developers who set a custom SSE URL. | INFO | No drift. |
| AR2-08 | Security | **SSE_LAMBDA_URL default cannot be used for data exfiltration.** The value is only returned by `/api/v2/runtime` (line 612) when `_is_dev_environment()` returns True (ENVIRONMENT in `{"local", "dev", "test"}`). In CI, `run-local-api.py` sets `ENVIRONMENT=local`, so the value IS returned -- but only to localhost Playwright tests, not to external clients. An attacker who can set env vars in CI already has full control and doesn't need this vector. | INFO | No concern. |
| AR2-09 | Implementation risk | **First CI run after rename: no race condition.** "Playwright Chaos Tests" is NOT a required branch protection check (confirmed via `gh api`). Required checks are: Secrets Scan, Lint, Run Tests. The rename to "Playwright E2E Tests" has zero impact on merge gating. Old check name will simply stop appearing after the PR merges. | INFO | No risk. |
| AR2-10 | Spec drift | **Clarification says "no job split needed" -- was this in the original spec?** US-3 (line 36) says chaos and feature tests should remain "logically separated in CI output." The clarification Q1 resolves this by noting Playwright's HTML report already groups by file, providing visual separation without a job split. This is consistent, not a drift -- US-3 asks for logical separation, not physical job separation. | INFO | No drift. |
| AR2-11 | Cross-artifact | **Timeout values consistent.** Spec FR-004: `timeout 600` command + `timeout-minutes: 15` job. Plan Change 2c: `timeout 600`. Plan Change 2f: `timeout-minutes: 15`. AR1-02: retries reduced to 1. Plan Change 2c: `--retries=1`. All consistent. | INFO | No drift. |

### New Change Required

**Change 2g: Update job section comment (line 283):**
```yaml
# Before
  # JOB: Playwright Chaos Tests (Feature 1265)
# After
  # JOB: Playwright E2E Tests (Feature 1265, 1317)
```

### Gate Statement

**PASS.** No CRITICAL or HIGH findings. Two LOW cosmetic issues in the spec (file count and endpoint name) do not affect the implementation plan. One LOW omission in the plan (stale comment block) resolved with Change 2g. All line numbers verified. All cross-artifact references consistent. Security posture confirmed safe.
