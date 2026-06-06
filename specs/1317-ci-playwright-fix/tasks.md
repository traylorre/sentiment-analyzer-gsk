# Feature 1317: Fix CI Playwright Infrastructure — Tasks

## Implementation Tasks

### T-01: Add SSE_LAMBDA_URL default to run-local-api.py
- **File:** `scripts/run-local-api.py`
- **Location:** After line 87 (`os.environ.setdefault("AWS_XRAY_SDK_ENABLED", "false")`)
- **Action:** Insert one line:
  ```python
  os.environ.setdefault("SSE_LAMBDA_URL", "http://localhost:8000/api/v2/stream")
  ```
- **Done condition:** `python -c "import scripts.run_local_api"` or starting the server no longer raises `KeyError: 'SSE_LAMBDA_URL'`
- **Traces to:** FR-001, Plan Change 1

### T-02: Update job section comment in pr-checks.yml
- **File:** `.github/workflows/pr-checks.yml`
- **Location:** Line 283
- **Action:** Change `# JOB: Playwright Chaos Tests (Feature 1265)` to `# JOB: Playwright E2E Tests (Feature 1265, 1317)`
- **Done condition:** Comment reflects new job name and both feature numbers
- **Traces to:** FR-005, Plan Change 2g (from AR#2)

### T-03: Rename job ID from playwright-chaos to playwright-e2e
- **File:** `.github/workflows/pr-checks.yml`
- **Location:** Line 285
- **Action:** Change `playwright-chaos:` to `playwright-e2e:`
- **Done condition:** `grep 'playwright-e2e:' .github/workflows/pr-checks.yml` returns match
- **Traces to:** FR-005, Plan Change 2a

### T-04: Rename job name from "Playwright Chaos Tests" to "Playwright E2E Tests"
- **File:** `.github/workflows/pr-checks.yml`
- **Location:** Line 286
- **Action:** Change `name: Playwright Chaos Tests` to `name: Playwright E2E Tests`
- **Done condition:** `grep 'name: Playwright E2E Tests' .github/workflows/pr-checks.yml` returns match
- **Traces to:** FR-005, Plan Change 2b

### T-05: Rename step name from "Run chaos E2E tests" to "Run E2E tests"
- **File:** `.github/workflows/pr-checks.yml`
- **Location:** Line 318
- **Action:** Change `- name: Run chaos E2E tests` to `- name: Run E2E tests`
- **Done condition:** `grep 'name: Run E2E tests' .github/workflows/pr-checks.yml` returns match
- **Traces to:** FR-005 (rename for clarity), GAP-01 from AR#3

### T-06: Expand test glob from chaos-*.spec.ts to *.spec.ts
- **File:** `.github/workflows/pr-checks.yml`
- **Location:** Line 321
- **Action:** Change `timeout 300 npx playwright test tests/e2e/chaos-*.spec.ts \` to `timeout 600 npx playwright test tests/e2e/*.spec.ts \`
- **Done condition:** Glob matches all 38 spec files instead of 8
- **Traces to:** FR-002, FR-004 (timeout 300->600), Plan Change 2c

### T-07: Add --retries=1 flag to Playwright command
- **File:** `.github/workflows/pr-checks.yml`
- **Location:** After `--project="Desktop Chrome"` line (line 322)
- **Action:** Insert `--retries=1 \` between `--project="Desktop Chrome" \` and `--reporter=html,list`
- **Done condition:** Command includes `--retries=1` flag
- **Traces to:** AR1-02 resolution (cap worst-case time), Plan Change 2c

### T-08: Rename artifact name playwright-chaos-report to playwright-e2e-report
- **File:** `.github/workflows/pr-checks.yml`
- **Location:** Line 329
- **Action:** Change `name: playwright-chaos-report` to `name: playwright-e2e-report`
- **Done condition:** `grep 'playwright-e2e-report' .github/workflows/pr-checks.yml` returns match
- **Traces to:** FR-006, Plan Change 2d

### T-09: Rename artifact name playwright-chaos-results to playwright-e2e-results
- **File:** `.github/workflows/pr-checks.yml`
- **Location:** Line 337
- **Action:** Change `name: playwright-chaos-results` to `name: playwright-e2e-results`
- **Done condition:** `grep 'playwright-e2e-results' .github/workflows/pr-checks.yml` returns match
- **Traces to:** FR-006, Plan Change 2e

### T-10: Update job timeout from 5 to 15 minutes
- **File:** `.github/workflows/pr-checks.yml`
- **Location:** Line 341
- **Action:** Change `timeout-minutes: 5` to `timeout-minutes: 15`
- **Done condition:** Job timeout is 15 minutes
- **Traces to:** FR-004, Plan Change 2f

### T-11: Verify — Local API server starts without KeyError
- **Type:** Verification (no file change)
- **Action:** Run `cd /home/zeebo/projects/sentiment-analyzer-gsk && python scripts/run-local-api.py` and confirm it starts without `KeyError: 'SSE_LAMBDA_URL'`. Kill after confirming successful startup.
- **Done condition:** Server binds to port 8000 and responds to health check, or at minimum starts without env var crash
- **Traces to:** Success Criteria row 1 ("Backend starts in CI"), US-2
- **Depends on:** T-01

### T-12: Verify — Branch protection does not reference old check name
- **Type:** Verification (no file change)
- **Action:** Run `gh api repos/traylorre/sentiment-analyzer-gsk/branches/main/protection --jq '.required_status_checks.checks[].context'` and confirm "Playwright Chaos Tests" is NOT in the list.
- **Done condition:** Output contains only "Secrets Scan", "Lint", "Run Tests" (no playwright reference)
- **Traces to:** AR1-06 (branch protection conflict risk), Clarification Q4
- **Note:** Already verified in Stage 4 (Q4 answer: NOT a required check). This is a pre-flight reconfirmation.

### T-13: Verify — handler.py has NO changes
- **Type:** Verification (no file change)
- **Action:** Run `git diff src/lambdas/dashboard/handler.py` and confirm empty output
- **Done condition:** Zero diff on handler.py
- **Traces to:** NFR-002 ("No changes to production handler.py")

### T-14: Commit and push
- **Type:** Git operation
- **Action:** Stage both files (`scripts/run-local-api.py`, `.github/workflows/pr-checks.yml`), create signed commit with message following project conventions, push to feature branch
- **Done condition:** Commit pushed, PR created or updated
- **Depends on:** T-01 through T-13 (all tasks and verifications complete)
- **Traces to:** Plan "Recommendation: Single atomic commit with both changes"

## Dependency Graph

```
T-01 (run-local-api.py) ─────────────────┐
T-02 (comment) ──────────────────────────┤
T-03 (job ID) ───────────────────────────┤
T-04 (job name) ─────────────────────────┤
T-05 (step name) ───────────────────────┤
T-06 (glob + timeout) ──────────────────┤
T-07 (retries flag) ────────────────────┤
T-08 (artifact report name) ────────────┤
T-09 (artifact results name) ───────────┤
T-10 (job timeout) ─────────────────────┤
                                         │
T-11 (verify: API startup) ──[T-01]──┤
T-12 (verify: branch protection) ────┤
T-13 (verify: handler.py unchanged) ─┤
                                         │
T-14 (commit + push) ────[ALL]──────────┘
```

T-01 through T-10 are independent of each other (different lines in different or same files).
T-11 depends on T-01 (needs env var set to verify startup).
T-12 and T-13 are independent verifications.
T-14 depends on all prior tasks.

## Cross-Artifact Traceability Matrix

### Spec Requirements -> Tasks

| Requirement | Task(s) | Coverage |
|---|---|---|
| FR-001: Set SSE_LAMBDA_URL | T-01 | FULL |
| FR-002: Expand glob | T-06 | FULL |
| FR-003: Desktop Chrome only | (no change needed) | N/A — already in workflow, retained by T-06 |
| FR-004: Increase timeout | T-06 (command timeout), T-10 (job timeout) | FULL |
| FR-005: Rename job | T-02, T-03, T-04, T-05 | FULL |
| FR-006: Update artifacts | T-08, T-09 | FULL |
| FR-007: PREPROD skip handling | (no change needed) | N/A — tests self-skip |
| NFR-001: No new deps | (implicit) | VERIFIED by inspection |
| NFR-002: No handler.py changes | T-13 | FULL |
| NFR-003: setdefault() usage | T-01 | FULL (uses setdefault) |
| US-1: All 38 files run | T-06 | FULL |
| US-2: Backend starts | T-01, T-11 | FULL |
| US-3: Logical separation | (no change needed) | N/A — HTML report provides separation |
| US-4: No chaos regression | T-06 (glob includes chaos-*) | FULL |

### Plan Changes -> Tasks

| Plan Change | Task | Coverage |
|---|---|---|
| Change 1: SSE_LAMBDA_URL | T-01 | FULL |
| Change 2a: Job ID | T-03 | FULL |
| Change 2b: Job name | T-04 | FULL |
| Change 2c: Glob + timeout + retries | T-06, T-07 | FULL |
| Change 2d: Artifact report name | T-08 | FULL |
| Change 2e: Artifact results name | T-09 | FULL |
| Change 2f: Job timeout | T-10 | FULL |
| Change 2g: Comment block | T-02 | FULL |
| Change 3: pip install -e . | (no change needed) | N/A — plan confirmed not needed |

### Orphan Check

- **Tasks without requirement:** NONE. All tasks trace to spec requirements or plan changes.
- **Requirements without task:** NONE. All spec requirements are either covered by a task or explicitly documented as "no change needed" with rationale.
- **Plan changes without task:** NONE. All 8 plan changes (including Change 2g from AR#2) map to tasks.

### Gap Analysis

| Gap ID | Description | Severity | Resolution |
|---|---|---|---|
| GAP-01 | Step name "Run chaos E2E tests" (line 318) becomes misleading after scope expansion | LOW | **RESOLVED.** Added T-05 to rename step name to "Run E2E tests". Not in the original plan -- discovered by AR#3 cross-artifact analysis. |

## Adversarial Review #3

### Implementation Readiness Assessment

| Criterion | Status | Notes |
|---|---|---|
| Every task has a single file target | PASS | T-01 targets run-local-api.py; T-02 through T-10 target pr-checks.yml; T-11-T-13 are verifications; T-14 is git |
| Every task has exact line numbers | PASS | All line numbers verified against current codebase |
| Every task has a testable done condition | PASS | Each task specifies a grep command or observable outcome |
| No task requires judgment calls | PASS | All changes are literal string replacements or insertions |
| Dependency ordering is correct | PASS | T-11 depends on T-01; T-14 depends on all. No circular deps. |
| Two-file scope confirmed | PASS | Only `scripts/run-local-api.py` and `.github/workflows/pr-checks.yml` are modified |

**Verdict:** An implementer can execute these 14 tasks mechanically without ambiguity. Each task is a single-line edit or insertion with exact before/after text specified in the plan.

### Highest-Risk Task

**T-06: Expand test glob from `chaos-*.spec.ts` to `*.spec.ts`**

This is the highest-risk task because it changes the set of tests CI executes from 8 files to 38 files. The risk is not implementation risk (the edit is trivial) but outcome risk:

- **30 previously-untested files will run for the first time in CI.** Some may fail due to missing mock data (EC-1), missing auth tokens, or environment assumptions that hold locally but not in CI.
- **The first CI run will likely show failures.** These failures are expected and documented (spec OS-5), but they will be visible on the PR and could cause confusion.
- **Mitigation:** The spec explicitly states this is acceptable (EC-1: "Tests failing is better than tests not running"). The Playwright HTML report artifact (T-08) will show exactly which tests pass/fail/skip, providing a baseline for follow-up work.

This risk is ACCEPTED, not mitigated. It is the entire point of the feature -- discover what works and what does not.

### Most Likely Source of Rework

**CI timeout tuning (T-06 command timeout + T-10 job timeout).**

The current estimate is 38 tests x ~15s avg = ~570s (~10 min), with 15 min job timeout providing ~3 min margin. But:

1. The ~15s average is based on chaos tests, which are relatively fast. Non-chaos tests (chart interaction, auth flows, navigation) may be slower due to more complex page interactions and wait times.
2. With `--retries=1` (T-07), any failing test runs twice. If 10 tests fail (plausible for first run with missing mock data), that adds ~150s of retry time.
3. Frontend `npm run dev` cold start in CI adds 30-60s overhead not counted in the test time estimate.

**Worst case:** 38 tests x 20s + 10 retries x 20s + 60s startup = 1020s (~17 min) > 15 min timeout.

**Likely outcome:** The first CI run may timeout. The fix is trivial -- increase `timeout-minutes` from 15 to 20 and `timeout` from 600 to 900. This is explicitly covered in the plan's Rollback Plan section.

**Severity:** LOW. Timeout is easily adjustable in a follow-up commit without touching any logic.

### Missing Task Check

| ID | Finding | Severity | Resolution |
|---|---|---|---|
| AR3-01 | **Step name "Run chaos E2E tests" (line 318) not in plan or original tasks.** The plan covers job ID (2a), job name (2b), comment (2g), artifacts (2d/2e), glob (2c), timeout (2f) -- but not the step `name:` field on line 318. | LOW | **RESOLVED.** Added T-05 to rename step to "Run E2E tests". Tasks renumbered T-05 through T-14. Traceability matrix updated. |
| AR3-02 | **No task to update `CORS_ORIGINS` default.** Plan notes (line 17-19) that `CORS_ORIGINS` defaults to empty string via `os.environ.get()` and won't crash, but logs a warning. | INFO | **NOT NEEDED.** The plan explicitly notes this is "not a blocker" and the handler uses `get()` with a default. A warning log is acceptable for CI. No task required. |
| AR3-03 | **T-06 and T-07 modify adjacent lines -- could they conflict during editing?** T-06 changes line 321 (glob + timeout), T-07 inserts `--retries=1` after line 322. Both are in the same YAML run block. | INFO | **NO CONFLICT.** The edits are on different lines. T-06 changes the `timeout 300 npx playwright test tests/e2e/chaos-*.spec.ts \` line. T-07 inserts a new line after `--project="Desktop Chrome" \`. The plan's Change 2c shows the final state with all three changes applied together, so the implementer should apply T-06 and T-07 as a single logical edit to the run block. |
| AR3-04 | **No task covers verifying the renamed step name does not break `needs:` references.** Could other jobs reference `playwright-chaos` in their `needs:` array? | INFO | **NO RISK.** Searched the workflow file -- no other job has `needs: [playwright-chaos]` or any reference to the playwright job in a `needs` clause. The playwright job runs independently (no downstream jobs depend on it). The job ID rename (T-03) is safe. |

### Cross-Artifact Consistency Final Check

- **spec.md FR-001** says "after line 87" -- T-01 says "after line 87" -- actual file has `AWS_XRAY_SDK_ENABLED` at line 87: **CONSISTENT**
- **spec.md FR-002** says line 321 -- T-06 says line 321 -- actual file has `timeout 300 npx playwright test` at line 321: **CONSISTENT**
- **spec.md FR-004** says `timeout 600` + `timeout-minutes: 15` -- T-06 and T-10 match: **CONSISTENT**
- **spec.md FR-005** says rename to `playwright-e2e` / "Playwright E2E Tests" -- T-03 and T-04 match: **CONSISTENT**
- **spec.md FR-006** says `playwright-e2e-report` / `playwright-e2e-results` -- T-08 and T-09 match: **CONSISTENT**
- **plan.md Change 2g** (from AR#2) says update comment to include Feature 1317 -- T-02 matches: **CONSISTENT**
- **File count:** 38 total spec files (verified), 8 match `chaos-*.spec.ts` (verified), plan says "8/38" (line 203): **CONSISTENT**

### Gate Statement

**READY FOR IMPLEMENTATION.**

All CRITICAL and HIGH findings: NONE found. One LOW gap (GAP-01 / AR3-01) self-resolved by adding T-05. All 14 tasks are atomic, ordered, testable, and fully traced to spec requirements and plan changes. Two files modified, zero production code changes. The highest-risk task (T-06) has accepted, documented risk with a trivial rollback. The most likely rework (timeout tuning) requires a one-line follow-up edit if triggered.

Total implementation scope: 10 line-level edits across 2 files + 3 verifications + 1 commit.
