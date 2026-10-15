# Feature Specification: Elapsed time on a monotonic clock

**Feature Branch**: `card-16`
**Created**: 2026-10-13
**Status**: Implemented
**Card**: `cards/16.json`

## Problem

Cache expiry and unit-test timing bounds measure elapsed time with `time.time()`, the wall clock.
A wall clock that is stepped backwards keeps an expired cache entry alive, and one stepped forwards
inflates a measured duration. On this WSL2 host the wall clock steps about every 30 s, which failed
`tests/unit/test_secrets.py::TestGetSecret::test_cache_expiry` 1 run in 15 and the pre-push hook with
it. Under a load average of 27 to 30, a 50 ms ceiling over a 100 ms parallel fetch failed
`test_parallel_execution_with_one_source_failure` the same way.

## Decision

- An elapsed-time question is answered on `time.monotonic()`. A value that is serialized, returned
  to a caller, or compared with an external wall-clock time stays on `time.time()`.
- A test that checks expiry controls the clock it reads. It never sleeps across a jittered boundary.
- A test that checks concurrency proves concurrency by synchronisation (a barrier both workers must
  reach, an event one worker waits on). An elapsed-time ceiling cannot tell a parallel run on a loaded
  host from a sequential one on an idle host.
- A test that checks the cost of CPU-bound work measures `time.process_time()`. Process CPU time does
  not advance while the scheduler leaves the process waiting, and no clock step moves it.

Rejected: `perf_counter()` for the cache sites. It is monotonic too, but `monotonic()` is the clock
`src/lambdas/shared/cache/sentiment_cache.py` already uses for the same purpose, and one clock for one
question is easier to audit. Rejected: widening the test ceilings. A wider wall-clock ceiling fails
less often and fails for the same reason.

## Scope: cache sites

Census: `grep -rn --include='*.py' 'jittered_ttl' src/` on card-16 at `def4cb81` lists 12 cache
modules. `sentiment_cache.py` already uses `monotonic()`. Each `time.time()` in the other 11 was read
in place, and no cache-entry timestamp is read outside its own module
(`grep -rn` for each cache's name across `src/` finds no other reader).

| File | `time.time()` at | Meaning | Clock after |
|---|---|---|---|
| `src/lambdas/shared/secrets.py` | 311, 337 | `expires_at` set and compared | monotonic |
| `src/lib/timeseries/cache.py` | 61, 128, 157 (+ field comments 55, 56) | entry age, last access | monotonic |
| `src/lambdas/dashboard/metrics.py` | 79, 101 | entry age | monotonic |
| `src/lambdas/dashboard/ohlc.py` | 135, 163, 647 | entry age; 647 is the age sent in the cache header, also elapsed | monotonic |
| `src/lambdas/dashboard/sentiment.py` | 83, 104 | entry age | monotonic |
| `src/lambdas/dashboard/configurations.py` | 80, 105, 118, 135 | entry age | monotonic |
| `src/lambdas/shared/adapters/tiingo.py` | 58, 77 | entry age | monotonic |
| `src/lambdas/shared/adapters/finnhub.py` | 61, 80 | entry age | monotonic |
| `src/lambdas/shared/circuit_breaker.py` | 80, 100 | entry age | monotonic |
| `src/lambdas/shared/cache/ticker_cache.py` | 270, 292, 304, 326 | entry age | monotonic |
| `src/lambdas/shared/quota_tracker.py` | 89, 107, 130 | cache age and sync interval, one tuple | monotonic |
| `src/lambdas/shared/quota_tracker.py` | 151, 155, 171 | reduced-rate duration, alert spam interval | unchanged, out of scope |
| `src/lambdas/shared/quota_tracker.py` | 571 | DynamoDB TTL epoch | wall clock, correct |

## Scope: test timing bounds

Census: `grep -rn --include='*.py' -E 'assert (elapsed|duration)[a-z_]* *<' tests/unit` gives 8 assertions
in 3 files. `test_duration_ms_metric_is_accurate` asserts an upper bound with `abs(...) < 20`, so the
regex misses it, and it is in scope.

| Test | Today | After |
|---|---|---|
| `ingestion/test_parallel_timing.py`, 4 parallelism tests | sleep 50 to 150 ms, assert wall-clock ceiling | both adapter calls wait on one `threading.Barrier(2)` with a timeout; a sequential fetch breaks the barrier and fails with a message naming it |
| `test_parallel_execution_with_one_source_failure` | 100 ms ceiling | Tiingo waits on an `Event` that the failing Finnhub call sets; Tiingo's success proves the failure did not block it |
| `test_parallel_execution_scales_with_tickers` | ceiling per ticker count | barrier per fetch, plus each adapter called once per fetch whatever the ticker count |
| `test_duration_ms_metric_is_accurate` | internal vs external within 20 ms | the fetcher's clock is patched to known instants; `duration_ms` equals their difference exactly |
| `middleware/test_jwt_validation.py::test_jwt_performance_benchmark` | 1000 validations < 1 s wall | same bound on `process_time()` |
| `test_missing_jwt_secret_fails_fast` | < 0.1 s wall | `jwt.decode` is never called when no secret is configured |
| `test_multi_ticker_query.py`, 2 tests | < 1 s wall over mocked queries | same bound on `process_time()` |
| `test_secrets.py::test_cache_expiry` | sleeps 1.1 s against a TTL jittered up to 1.1 s | patches the module's monotonic clock past the jittered TTL; a second case steps the wall clock back and asserts the entry still expires |

Existing tests that set entry timestamps from `time.time()` (`test_ohlc_cache.py`, `test_shared_cache.py`,
`test_ticker_cache_ttl.py`, `test_cache_jitter_integration.py`) move to `time.monotonic()` with the code.

## Requirements

- **FR-001**: Every cache in the scope table computes and compares entry age on `time.monotonic()`.
- **FR-002**: A backward wall-clock step does not extend a secrets-cache entry's life. A test steps
  the wall clock back and passes only on the monotonic clock.
- **FR-003**: No unit test in the census asserts an upper bound on wall-clock elapsed time.
- **FR-004**: Each rewritten concurrency test fails when the fetcher runs its sources sequentially.

## Verification

- `make validate` and `make test-unit` pass.
- Mutant 1: revert `secrets.py` to `time.time()`. The wall-clock-step test fails.
- Mutant 2: make `ParallelFetcher` run sequentially (`max_workers=1`). Every barrier test fails with
  the barrier message.

Measured on card-16 at `e679075f`, load average 17 to 23:

| Check | Result |
|---|---|
| `make validate`, after the gate's `terraform init -backend=false` | 8 of 8 blocking stages pass |
| `make test-unit` | 4259 passed, 0 failed |
| Mutant 1, `secrets.py` and `ohlc.py` back on `time.time()` | fails `test_cache_expires_across_backward_wall_clock_step` and `test_ohlc_cache.py::test_cache_expiry`, nothing else |
| Mutant 2, `MAX_WORKERS = 1` | fails the 4 concurrency tests, each with its own message; `test_duration_ms_metric_is_accurate` passes |
| Mutant 3, `validate_jwt` decodes without a configured secret | fails `test_missing_jwt_secret_fails_fast` |

## Out of scope, carded

`grep -rn --include='*.py' 'time\.time()' src/` outside the 11 files lists 32 more calls in 10 files,
among them SSE heartbeats and uptime, failover durations, ingestion metrics, the CloudWatch flush timer
in `src/lib/cache_utils.py`, and `quota_tracker.py:151-171`. Some of them are elapsed time and some
are real epochs (a Lambda deadline, a DynamoDB TTL). Each needs the same per-call read as this card
gave the cache sites, so they are raised as `cards/NEW-card-16-wall-clock-elapsed-sites.json`.
