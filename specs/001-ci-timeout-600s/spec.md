# Feature Specification: Increase Playwright CI Timeout to 600s

**Feature Branch**: `001-ci-timeout-600s`
**Created**: 2026-03-29
**Status**: Draft
**Input**: User description: "Increase Playwright CI timeout from 300 seconds to 600 seconds to prevent false failures during slow CI runner execution."

## User Scenarios & Testing _(mandatory)_

### User Story 1 - CI Playwright Suite Completes Without False Timeouts (Priority: P1)

As a developer whose PR triggers CI Playwright tests, I want the test suite timeout to be long enough to accommodate slow CI runners so that legitimate test runs are not killed by a premature timeout, forcing unnecessary re-runs.

**Why this priority**: False timeout failures are the most disruptive class of CI failure — the test code is correct, the application works, but the run environment was slow. This wastes developer time on re-runs and erodes trust in the CI pipeline.

**Independent Test**: Can be fully tested by running the Playwright suite on a CI runner under load and verifying the suite completes within the 600-second budget without being killed.

**Acceptance Scenarios**:

1. **Given** a Playwright test suite is executing on a slow CI runner, **When** execution takes between 300 and 600 seconds, **Then** the suite completes and reports results instead of being killed by timeout.
2. **Given** a Playwright test suite is executing normally, **When** execution takes less than 300 seconds, **Then** the suite completes normally (no change in behavior for fast runs).
3. **Given** a Playwright test suite is genuinely stuck, **When** execution exceeds 600 seconds, **Then** the suite is killed by timeout and reports a timeout failure.

---

### Edge Cases

- What happens when the timeout is increased but individual test timeouts remain at 60 seconds? The suite timeout is for the entire run, not individual tests — individual tests still fail fast.
- What happens when the suite has retries enabled? Each retry attempt shares the same suite timeout budget.
- What happens if a future test addition pushes legitimate execution time past 600 seconds? This would require another timeout increase — the spec documents the current appropriate value.

## Requirements _(mandatory)_

### Functional Requirements

- **FR-001**: The Playwright suite execution timeout default MUST be 600 seconds (10 minutes). This is the default value, overridable per FR-003.
- **FR-002**: Individual test timeouts MUST remain unchanged — only the suite-level timeout increases.
- **FR-003**: The timeout value MUST be configurable via the `PLAYWRIGHT_SUITE_TIMEOUT` environment variable or function parameter. The configurable value MUST be clamped to a maximum of 1800 seconds (30 minutes) to prevent runaway runners from consuming resources indefinitely.
- **FR-004**: The API contract documentation MUST reflect the updated default timeout value and the maximum ceiling.
- **FR-005**: Local development execution MUST NOT be affected — the timeout change targets CI execution only.
- **FR-006**: All locations where the timeout is configured MUST be updated. An exhaustive search of the codebase for the value 300 in timeout-related contexts MUST be performed during implementation to ensure no location is missed. (Note: research phase confirmed exactly 2 source locations + 1 contract doc; verify no new locations added since research date.)
- **FR-007**: Timeout values less than or equal to 0 MUST be rejected (raise an error) to prevent disabling the timeout entirely. The clamping logic MUST enforce `max(1, min(timeout, 1800))`.
- **FR-008**: Non-integer environment variable values (e.g., empty string, alphabetic characters) MUST be handled gracefully by falling back to the default value (600) with a warning log, not by crashing the runner.

## Success Criteria _(mandatory)_

### Measurable Outcomes

- **SC-001**: Zero false timeout failures across 20 consecutive CI runs (compared to current baseline of intermittent 300s timeouts).
- **SC-002**: The 600-second timeout provides at least 2x headroom over the P95 suite execution time (if P95 is ~250s, 600s gives 2.4x headroom).
- **SC-003**: Genuinely stuck suites are still killed within a reasonable timeframe (10 minutes, not left running indefinitely).

## Assumptions

- The current 300-second timeout is configured in two locations: the executor default parameter and the runner service hardcoded call.
- The P95 suite execution time on CI runners is approximately 200-300 seconds, with slow runners occasionally exceeding 300 seconds.
- The API contract YAML documents the default timeout value for consumers.
- Individual Playwright test timeouts (60s per test) provide fast failure for individual test issues.

## Scope Boundaries

**In scope**:
- Increasing suite-level timeout from 300s to 600s
- Making the timeout configurable (not hardcoded)
- Updating API contract documentation

**Out of scope**:
- Changing individual test timeouts
- Changing Playwright config-level timeouts (action, navigation, expect)
- Investigating why CI runners are slow (infrastructure concern, not test concern)
- Adding timeout monitoring or alerting (tracked as follow-up — recommended to detect P95 creep)

## Adversarial Review #1

**Reviewed**: 2026-03-29

| Severity | Finding | Resolution |
|----------|---------|------------|
| CRITICAL | No upper bound on configurable timeout — attacker with CI env access gets unlimited runner time | Added FR-003 ceiling: max 1800s (30 min). Prevents cryptomining/exfiltration via timeout abuse. |
| HIGH | FR-001 "MUST be 600s" contradicts FR-003 "MUST be configurable" | Clarified FR-001: 600s is the default, FR-003 makes it overridable with a ceiling |
| HIGH | Assumption of exactly 2 locations is untestable — third location could silently keep 300s | Added FR-006: exhaustive codebase search for timeout value during implementation |
| HIGH | Missing monitoring means P95 creep silently erodes headroom until failures resume | Added follow-up note to scope boundaries. Monitoring is out of scope but recommended. |
| MEDIUM | Retry interaction underspecified — retry starved if first attempt takes 500s | Accepted — retry behavior is a property of the Playwright runner, not the timeout config |
| MEDIUM | SC-001 "20 runs" not statistically rigorous | Accepted — practical validation, not statistical proof. 7-day window would be better but 20 runs is reasonable for initial verification. |
| MEDIUM | P95 range too wide for capacity planning | Accepted — implementation should measure baseline before/after |
| LOW | FR-004 doesn't name the specific API contract file | Accepted — implementation will locate and update the correct file |
| LOW | Per-test timeout validation not in scope | Accepted — out of scope per FR-002 |

**Gate**: 0 CRITICAL, 0 HIGH remaining. All resolved via spec edits.

## Clarifications

### Q1: Are there exactly 2 source locations with timeout=300, or could there be more?
**Answer**: Confirmed exactly 2 source locations and 1 documentation location. The research.md performed an exhaustive search (FR-006) and found: (1) `src/playwright/executor.py` line 119: `timeout: int = 300` default parameter, (2) `src/playwright/runner.py` line 775: `timeout=300` hardcoded call. The contract at `specs/029-playwright-e2e-implementation/contracts/playwright-api.yaml` lines 26 and 43-44 documents the default as 300. The `playwright.config.ts` has a separate per-test timeout of 60000ms (60s) which is out of scope per FR-002. No other files reference 300 in a timeout context.
**Evidence**: `grep 'timeout.*300' src/playwright/` returns exactly 2 hits: executor.py:119 and runner.py:775. Research.md "Scope Verification" section confirms these locations. playwright-api.yaml line 26: `default: 300`.

### Q2: Does the playwright.config.ts timeout (60s) need to change, and how does it relate to the suite timeout?
**Answer**: No. The `playwright.config.ts` `timeout: 60000` (line 62) is the per-test timeout — each individual test gets 60 seconds. This is distinct from the suite-level timeout in `executor.py` which caps the entire `npx playwright test` subprocess. FR-002 explicitly states "Individual test timeouts MUST remain unchanged." The per-test timeout catches stuck individual tests quickly; the suite timeout catches the aggregate run exceeding safe bounds.
**Evidence**: `playwright.config.ts` line 62: `timeout: 60000`. FR-002: "Individual test timeouts MUST remain unchanged". executor.py's `timeout` parameter controls the subprocess `timeout` argument, not Playwright's internal config.

### Q3: How does the environment variable interact with the function default and clamping?
**Answer**: The flow is: CI workflow sets `PLAYWRIGHT_SUITE_TIMEOUT` env var (optional) -> `runner.py` reads env var with fallback to "600" -> passes integer to `run_suite(timeout=...)` -> `executor.py` clamps to `min(timeout, 1800)` before passing to subprocess. If no env var is set, the default flows: runner.py uses 600 -> executor.py accepts 600 (below 1800 ceiling) -> subprocess gets 600s timeout. The clamping is in executor.py (defense in depth), not runner.py, ensuring no caller can bypass the ceiling.
**Evidence**: Plan.md "Change 2" shows runner.py reading env var with "600" default. Plan.md "Change 1" shows executor.py clamping. Research.md "Clamping Location" decision: "Clamp in executor.py (not runner.py) — the boundary closest to the dangerous operation enforces the constraint."

### Q4: Will this change affect local development runs (FR-005)?
**Answer**: No. Local development uses `npx playwright test` directly via the npm scripts in `package.json` (e.g., `npm test`, `npm run test:headed`). These bypass `executor.py` and `runner.py` entirely — those modules are the Python orchestration layer for the CI/dev-loop pipeline. Local runs use `playwright.config.ts` timeouts only (60s per test, 10s action, 30s navigation). The suite-level timeout only applies when running through the Python `run_suite()` function in CI.
**Evidence**: `package.json` scripts: `"test": "playwright test"` — invokes Playwright directly. FR-005: "Local development execution MUST NOT be affected." The Python executor wraps the subprocess for CI; local devs run Playwright natively.

### Q5: What happens to retries when the suite timeout is consumed?
**Answer**: Playwright retries share the suite timeout budget. If a first attempt takes 500s on a test with retries=2, the retry attempt has only 100s remaining before the 600s subprocess timeout kills the entire process. This is acceptable behavior — the spec's adversarial review noted this as MEDIUM risk and accepted it: "retry behavior is a property of the Playwright runner, not the timeout config." The per-test timeout (60s) provides fast failure for individual stuck tests, so a single test consuming 500s would have already been killed by Playwright's internal timeout long before the suite timeout matters.
**Evidence**: Adversarial review MEDIUM finding: "Retry interaction underspecified — retry starved if first attempt takes 500s. Accepted — retry behavior is a property of the Playwright runner." Per-test timeout of 60s (playwright.config.ts line 62) prevents any single test from consuming more than 60s.
