# Feature 1321: Playwright Workers CI

## Problem Statement

The E2E test suite contains 244 Playwright tests running against `ubuntu-latest` CI
runners (4 vCPUs, 16GB RAM). The current configuration forces serial execution with a
single worker:

- `frontend/playwright.config.ts` line 15: `workers: process.env.CI ? 1 : undefined`
- `.github/workflows/pr-checks.yml` lines 318-324: `--retries=0`, 900s timeout

With 1 worker, the suite times out at 900s, reaching only test #99 of 244. Many
individual tests take ~30s each (failing tests hit the per-test timeout). Even with
Feature 1319 fixing the API format mismatch that causes most failures, serial execution
of 244 tests is unsustainable:

- **Best case** (all pass, ~3s each): 244 x 3s = 732s (cuts it close)
- **Realistic** (some slow tests): 244 x 5s avg = 1220s (exceeds timeout)
- **With 4 workers**: 244 / 4 x 5s = 305s (well within timeout)

The CI runner has 4 vCPUs sitting idle while tests run serially. This is a pure
throughput problem with a straightforward fix.

## User Stories

### US1: CI Playwright Tests Use 4 Workers

As a developer pushing a PR, I want Playwright to run 4 parallel workers in CI so that
the full 244-test suite completes within the 900s timeout, giving me timely feedback on
E2E regressions.

## Requirements

### R1: Set Workers to 4 in CI Configuration

Update `frontend/playwright.config.ts` to use 4 workers when `CI` environment variable
is set, instead of 1. Additionally, pass `--workers=4` in the CI workflow command for
explicit override (belt and suspenders).

### R2: Keep Retries at 0

Do not change the `--retries=0` flag in the CI workflow. Retries mask flaky tests and
inflate CI time. Feature 1319 addresses the root cause of test failures.

### R3: Maintain or Adjust Timeout

Keep the 900s timeout. With 4 workers, the projected runtime is ~305s (realistic) to
~183s (optimistic), well within the limit. No timeout change needed.

## Edge Cases

### EC1: Resource Contention on ubuntu-latest

4 workers x 1 Chromium instance each = 4 browsers. Each Chromium process uses ~800MB
RAM. Total: ~3.2GB of 16GB available. CPU: 4 workers on 4 vCPUs = 1:1 mapping. This is
within safe limits but leaves minimal headroom for the API server and OS overhead.

### EC2: Local API Server Concurrent Requests

Parallel workers send concurrent requests to the local API server started by
`global-setup.ts`. Feature 1319 makes the API server thread-safe, which is a
prerequisite for this feature. Without 1319, parallel workers would hit race conditions
in the API handler.

### EC3: Shared Browser Context Between Workers

Playwright creates separate browser contexts per worker by default. Tests that rely on
shared state (cookies, localStorage) between test files will break with parallel
execution. However, Playwright's design isolates workers at the browser level -- each
worker gets its own browser instance.

### EC4: Test Data Races

Tests that create and read `e2e-` prefixed test data could race if two workers create
overlapping data. Global setup runs once before all workers (Playwright guarantee), so
cleanup is safe. Worker-level test data should use unique identifiers per test.

## Non-Requirements

- **Local worker configuration changes** -- Feature 1320 handles local worker count
- **API server thread safety** -- Feature 1319 handles this (dependency)
- **Test flakiness fixes** -- Parallel execution may surface flaky tests, but fixing
  them is separate work
- **Sharding across multiple CI runners** -- Overkill for 244 tests; 4 workers on 1
  runner is sufficient

## Success Metrics

1. Full 244-test suite completes within 900s CI timeout
2. No increase in test flakiness (flaky test count stays the same or decreases)
3. CI wall-clock time for E2E job drops by ~60-75% vs single-worker baseline

## Dependencies

| Feature | Status | Relationship |
|---------|--------|-------------|
| 1319 (API thread safety) | In progress | Hard dependency -- API must handle concurrent requests |
| 1320 (Local workers) | Spec'd | Soft -- this feature is CI-only, 1320 is local-only |

---

## Adversarial Review #1: Attack Spec

### AV1: Config vs CLI Drift (CRITICAL)

**Attack**: `playwright.config.ts` sets `workers: process.env.CI ? 1 : undefined`. If we
only update the CI workflow to pass `--workers=4` but leave the config at `1`, the CLI
flag overrides correctly -- but if someone runs `npx playwright test` in CI without the
flag (e.g., a new workflow, a local CI simulation), they silently get 1 worker.

**Assessment**: The CLI flag wins over config, so the immediate behavior is correct. But
config drift creates a maintenance trap.

**Resolution**: Update BOTH locations. Set `workers: process.env.CI ? 4 : 4` in the
config file AND pass `--workers=4` in the CLI command. Belt and suspenders. If either
is accidentally removed, the other still enforces 4 workers.

**Status**: CRITICAL resolved -- both locations updated in plan.

### AV2: Memory Pressure Under 4 Chromium Instances (HIGH)

**Attack**: 4 Chromium instances x ~800MB each = ~3.2GB. Add the local API server
(~200MB), Node.js test runner (~300MB), and OS overhead (~500MB). Total: ~4.2GB of 16GB.
That's 26% utilization -- safe.

**Assessment**: ubuntu-latest provides 16GB RAM. Even worst-case (Chromium tabs
accumulating DOM state across long test suites), each instance is unlikely to exceed 1.5GB.
6GB + overhead = ~7.5GB peak. Still under 50% of available RAM.

**Status**: HIGH resolved -- safe margin confirmed. No action needed.

### AV3: Global Setup Race with Workers (HIGH)

**Attack**: `global-setup.ts` cleans `e2e-` prefixed test data. If workers start before
global setup completes, they may read partially-cleaned state.

**Assessment**: Playwright guarantees `globalSetup` completes before ANY worker launches.
This is a sequential barrier in Playwright's architecture, not a race condition.

**Verification**: Playwright docs confirm: "Global setup runs once before all tests."
Workers are spawned only after globalSetup resolves.

**Status**: HIGH resolved -- Playwright architecture prevents this.

### AV4: Test Ordering Assumptions (MEDIUM)

**Attack**: Some tests may implicitly depend on execution order (e.g., test B reads data
created by test A in a different file). With 1 worker, file order is deterministic. With
4 workers, file execution order is non-deterministic.

**Assessment**: This is a test quality issue, not a configuration issue. Tests with
ordering dependencies are inherently flaky. Parallel execution will surface these, which
is a feature, not a bug.

**Status**: MEDIUM accepted -- surfacing hidden dependencies is beneficial.

### Gate Result

| Severity | Count | Resolved | Remaining |
|----------|-------|----------|-----------|
| CRITICAL | 1 | 1 | 0 |
| HIGH | 2 | 2 | 0 |
| MEDIUM | 1 | 0 (accepted) | 0 |

**Gate: PASS** -- 0 CRITICAL, 0 HIGH remaining.

---

## Clarifications

### Q1: Should we also update `fullyParallel` in config?

**Self-answered**: `fullyParallel: true` is already set in the config (line 8). This
means tests within a single file also run in parallel. The `workers` setting controls
how many parallel worker processes run test files concurrently. Both are independent and
both should be enabled. No change needed for `fullyParallel`.

### Q2: What if Feature 1319 is not merged when 1321 lands?

**Self-answered**: Without thread-safe API handling, 4 workers will send concurrent
requests that may corrupt shared state. However, this only affects tests that hit the
local API -- and those tests are already failing due to the format mismatch that 1319
fixes. The workers change is safe to merge independently; it just won't help until 1319
also lands. Merge order does not matter.

### Q3: Should we set workers to match vCPU count dynamically?

**Self-answered**: `os.cpus().length` could be used instead of hardcoding 4. However:
- ubuntu-latest consistently provides 4 vCPUs
- Hardcoded value is more predictable and debuggable
- If GitHub changes runner specs, we want to notice (not silently scale)
- Dynamic CPU detection adds complexity for zero practical benefit

Decision: Hardcode 4. Revisit if runner specs change.

### Q4: Do we need to update the test timeout per-test?

**Self-answered**: The per-test timeout in `playwright.config.ts` (`timeout: 30000` or
30s) is per individual test, not per suite. With 4 workers, each test still gets its
full 30s. The 900s CI timeout is for the entire job. No per-test timeout change needed.
