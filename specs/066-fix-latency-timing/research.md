# Research: Fix Latency Timing in Traffic Generator

**Feature**: 066-fix-latency-timing
**Date**: 2025-12-08

## Research Tasks

### 1. Python Time Functions for Elapsed Time Measurement

**Question**: What is the correct Python function for measuring elapsed time?

**Answer**: `time.monotonic()`

**Sources**:
- Python Documentation: [time.monotonic()](https://docs.python.org/3/library/time.html#time.monotonic)
- Python Documentation: [time.time()](https://docs.python.org/3/library/time.html#time.time)

**Key Findings**:

| Function | Monotonic | Affected by Clock Adjustments | Use Case |
|----------|-----------|-------------------------------|----------|
| `time.time()` | No | Yes (NTP, manual changes) | Wall clock timestamps |
| `time.monotonic()` | Yes | No | Elapsed time measurement |
| `time.perf_counter()` | Yes | No | High-resolution benchmarks |

**Decision**: Use `time.monotonic()` for latency measurement.

**Rationale**:
1. Immune to system clock adjustments
2. Designed specifically for measuring elapsed time
3. Available since Python 3.3 (we use Python 3.13)
4. Lower overhead than `time.perf_counter()` while sufficient for ms-level precision

### 2. Constitution Compliance

**Question**: What does the project constitution say about time functions?

**Answer**: Amendment 1.5 (Deterministic Time Handling) explicitly prohibits `time.time()`:

> PROHIBITED in tests:
> - `time.time()` - Epoch timestamps vary per execution

**Decision**: Fix is required to comply with constitution.

### 3. Codebase Precedent

**Question**: Is `time.monotonic()` used elsewhere in the codebase?

**Answer**: Yes, documented in `specs/012-ohlc-sentiment-e2e-tests/research.md` as the recommended pattern.

**Decision**: Follow existing pattern for consistency.

## Summary

| Decision | Rationale | Alternatives Rejected |
|----------|-----------|----------------------|
| Use `time.monotonic()` | Monotonic, immune to clock adjustments | `time.time()` (affected by clock), `time.perf_counter()` (overkill), mocking time (treats symptom not cause) |

## No External Research Required

This fix uses well-documented Python stdlib functionality. No web research or external API investigation needed.
