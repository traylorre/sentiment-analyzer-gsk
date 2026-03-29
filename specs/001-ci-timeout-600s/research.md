# Research: Increase Playwright CI Timeout to 600s

**Feature**: 001-ci-timeout-600s
**Date**: 2026-03-29

## Timeout Value: Why 600s

### Decision: 600 seconds (10 minutes) as new default

**Rationale**: The P95 suite execution time on CI runners is approximately 200-300 seconds. Slow runners (resource contention, cold starts, shared GitHub Actions runners) occasionally exceed 300s, causing false timeout failures. 600s provides approximately 2x headroom over the P95, which is the standard safety margin for CI timeouts.

**Alternatives Considered**:
1. **450s (1.5x headroom)**: Rejected - insufficient margin for worst-case CI runner performance. Likely to recur.
2. **600s (2x headroom)**: Selected - standard safety margin. Catches genuinely stuck suites within 10 minutes.
3. **900s (3x headroom)**: Rejected - too long before detecting genuine hangs. Developer waiting 15 minutes for a stuck suite is poor experience.

## Max Ceiling: Why 1800s

### Decision: 1800 seconds (30 minutes) as absolute maximum

**Rationale**: The ceiling prevents abuse if someone configures an absurdly high timeout via environment variable. 30 minutes is generous enough for any legitimate Playwright suite while still preventing runaway runners from consuming CI minutes indefinitely.

**Threat model** (from spec adversarial review): An attacker with CI environment variable access could set `PLAYWRIGHT_SUITE_TIMEOUT=999999` to keep a runner occupied for cryptomining or data exfiltration. The 1800s ceiling bounds this risk.

**Alternatives Considered**:
1. **1200s (20 min)**: Rejected - too tight for future suite growth
2. **1800s (30 min)**: Selected - generous upper bound, still reasonable resource consumption
3. **3600s (60 min)**: Rejected - a full hour is too long; any suite taking that long has a different problem

## Configurability: Environment Variable

### Decision: `PLAYWRIGHT_SUITE_TIMEOUT` environment variable in runner.py

**Rationale**: The runner is the entry point that orchestrates suite execution. Making the timeout configurable at the runner level via environment variable allows CI workflows to override it without code changes. The executor's function parameter serves as the programmatic API; the env var is the operational knob.

**Flow**:
```
CI Workflow (env var) -> runner.py (reads env, passes to executor) -> executor.py (clamps to max, uses value)
```

**Alternatives Considered**:
1. **Environment variable in executor.py**: Rejected - the executor is a library function; it should accept parameters, not read env vars directly. Runner is the appropriate integration point.
2. **Config file**: Rejected - overengineered for a single integer value
3. **CLI argument**: Rejected - runner invocation is already complex; env var is simpler for CI matrix overrides

## Clamping Location

### Decision: Clamp in executor.py (not runner.py)

**Rationale**: The executor is the function that actually passes the timeout to the subprocess. Clamping at this layer ensures that no caller — whether the runner, tests, or future code — can bypass the ceiling. Defense in depth: the boundary closest to the dangerous operation (subprocess timeout) enforces the constraint.

## Scope Verification

### Exhaustive Search Results (FR-006)

The timeout value 300 appears in timeout-related contexts in exactly two source locations:
1. `src/playwright/executor.py` line 119: `def run_suite(suite_path, base_url, timeout=300, retries=2)` - default parameter
2. `src/playwright/runner.py` line 775: `result = run_suite(..., timeout=300, ...)` - hardcoded call site

The contract documentation references it in one location:
3. `specs/029-playwright-e2e-implementation/contracts/playwright-api.yaml` lines 26, 43-44: documents default as 300

Individual test timeouts (60s in `playwright.config.ts`) are out of scope per FR-002.

## Canonical Sources

- **Playwright Test Timeouts**: https://playwright.dev/docs/test-timeouts
- **GitHub Actions Billing**: https://docs.github.com/en/billing/managing-billing-for-github-actions/about-billing-for-github-actions (runner-minutes cost context for ceiling justification)
