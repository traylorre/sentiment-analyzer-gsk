# Feature 1320: Playwright Workers Local

## Status: SPECIFIED

## Problem Statement

In `frontend/playwright.config.ts` (line 15), the local worker count is set to `undefined`:

```typescript
workers: process.env.CI ? 1 : undefined,
```

When `undefined`, Playwright defaults to half the CPU count on the machine. This means:

- On a 16-core machine: 8 workers
- On a 4-core machine: 2 workers
- On a 2-core machine: 1 worker

Local test behavior varies across developer machines. The user wants a deterministic `workers: 4` for local runs so that test execution is reproducible regardless of hardware.

## Dependencies

- **Feature 1319** (ThreadingHTTPServer): The local API server at `scripts/run-local-api.py` must handle concurrent requests from 4 parallel workers. Feature 1319 adds `ThreadingHTTPServer` with handler-level serialization lock. This feature MUST be merged before 1320 is meaningful.

## User Stories

### US1: Deterministic Local Worker Count

**As a** developer running Playwright tests locally,
**I want** the worker count fixed at 4,
**So that** test execution is reproducible across machines and I can reason about concurrency behavior.

**Acceptance Criteria:**
- `npx playwright test --list` shows "Using 4 workers" when run locally (no `CI` env var)
- CI behavior unchanged: still 1 worker when `process.env.CI` is truthy

## Requirements

| ID  | Requirement                                          | Priority | Story |
| --- | ---------------------------------------------------- | -------- | ----- |
| R1  | Set local Playwright workers to exactly 4            | MUST     | US1   |
| R2  | Preserve CI workers=1 (unchanged until Feature 1321) | MUST     | US1   |

## Edge Cases

| Edge Case                        | Handling                                                                                                             |
| -------------------------------- | -------------------------------------------------------------------------------------------------------------------- |
| Machine with <4 CPU cores        | Playwright still runs 4 workers. OS handles scheduling. Tests may be slightly slower but correctness is unaffected.  |
| API server under 4 workers       | Feature 1319 adds `ThreadingHTTPServer` so the API can handle concurrent requests. Without 1319, requests queue.     |
| `CI` env var set locally         | Workers remain 1. This is intentional -- developer can unset `CI` to get 4 workers.                                 |
| `--workers` CLI override         | Playwright CLI `--workers=N` overrides config. This is expected Playwright behavior and not affected by this change. |

## Out of Scope

- **CI worker changes**: Feature 1321 will address CI parallelism separately.
- **API server threading**: Feature 1319 owns the `ThreadingHTTPServer` migration.
- **Per-project worker overrides**: All 5 browser projects share the same worker pool. No per-project tuning.

## Success Metrics

| Metric                                              | Target                   |
| --------------------------------------------------- | ------------------------ |
| `npx playwright test --list` shows worker count     | "Using 4 workers"        |
| CI worker count unchanged                           | 1 worker when `CI` is set|
| No test flakiness increase after switching to 4     | Flake rate <= baseline   |

---

## Adversarial Review #1

### AR1-F1: Single-Threaded API Server Under 4 Workers

**Severity:** HIGH (mitigated)
**Finding:** Setting `workers: 4` locally while the API server (`scripts/run-local-api.py`) uses `HTTPServer` (single-threaded) causes request queuing. Four Playwright workers hitting the API simultaneously means 3 requests block while 1 is served.
**Resolution:** Feature 1319 (dependency) replaces `HTTPServer` with `ThreadingHTTPServer` and adds a handler-level serialization lock. This handles concurrent connections while maintaining data safety. Dependency is explicit in this spec.
**Residual risk:** None, provided 1319 merges first.

### AR1-F2: fullyParallel Interaction

**Severity:** INFO
**Finding:** `fullyParallel: true` is already set at line 12 of `playwright.config.ts`. With `workers: 4`, up to 4 tests run truly concurrently (test-level parallelism, not just file-level). No additional configuration is needed -- `workers` and `fullyParallel` are complementary settings.
**Resolution:** No action required. Documented for completeness.

### Gate: 0 CRITICAL, 0 HIGH remaining. PASS.

---

## Clarifications

### Q1: Does `workers: 4` override `fullyParallel: true`?

**Answer (self-resolved):** No, they are complementary settings.

- `workers` sets the maximum number of parallel worker processes.
- `fullyParallel` controls whether individual tests within a file can be distributed across workers (true) or must run sequentially within a single worker (false).
- With `workers: 4` and `fullyParallel: true`, Playwright distributes individual tests across up to 4 workers. Both settings are needed for maximum parallelism.

No user input required -- this is documented Playwright behavior.
