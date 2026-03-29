# Tasks: Increase Playwright CI Timeout to 600s

**Feature**: 001-ci-timeout-600s
**Generated**: 2026-03-29
**Spec**: [spec.md](./spec.md) | **Plan**: [plan.md](./plan.md)

## Phase 0: Setup

- [ ] T-000 P1 -- Create feature branch `001-ci-timeout-600s` from `origin/main`

## Phase 1: Foundational (Codebase Verification)

- [ ] T-100 P1 FR-006 Exhaustive search for `timeout.*300` across `src/playwright/` to confirm exactly 2 source locations (executor.py:119, runner.py:775) and no new occurrences since research date
- [ ] T-101 P1 FR-006 Verify contract doc location: confirm `specs/029-playwright-e2e-implementation/contracts/playwright-api.yaml` lines 26, 43-44 still reference `default: 300`

## Phase 2: US1 -- CI Playwright Suite Completes Without False Timeouts

- [ ] T-200 P1 US1/FR-001,FR-003,FR-007 `src/playwright/executor.py` -- Add `MAX_SUITE_TIMEOUT = 1800` module-level constant. Change `run_suite()` default parameter from `timeout=300` to `timeout=600`. Add clamping line `timeout = max(1, min(timeout, MAX_SUITE_TIMEOUT))` at top of function body before subprocess call.
- [ ] T-201 P1 US1/FR-003,FR-008 `src/playwright/runner.py` -- Replace hardcoded `timeout=300` call with env var read: `int(os.environ.get("PLAYWRIGHT_SUITE_TIMEOUT", "600"))` wrapped in try/except ValueError that logs warning and falls back to 600. Pass result to `run_suite(timeout=suite_timeout)`.
- [ ] T-202 P1 US1/FR-004 `specs/029-playwright-e2e-implementation/contracts/playwright-api.yaml` -- Update default timeout from 300 to 600. Document maximum ceiling of 1800. Document `PLAYWRIGHT_SUITE_TIMEOUT` environment variable.

## Phase 3: Polish

- [ ] T-300 P1 -- Run `grep -rn 'timeout.*300' src/playwright/` to verify zero remaining references to the old 300s timeout in source files
- [ ] T-301 P1 -- Run `make validate` and confirm clean pass
- [ ] T-302 P1 -- Commit with GPG signing (`git commit -S`)

## Adversarial Review #3

**Reviewed**: 2026-03-29

- **Highest-risk task**: T-201 — runner.py env var handling with ValueError try/except is the most error-prone change. Non-integer strings, empty strings, and edge cases around int parsing.
- **Most likely rework**: None — this is a straightforward config change with clear clamping logic.
- **CRITICAL/HIGH remaining**: 0. (FR-005 coverage gap is MEDIUM — local dev non-impact is preserved by design since changes only touch Python orchestration layer.)
- **READY FOR IMPLEMENTATION**
