# Quickstart: Quota Tracker Reduced-Rate Mode Hysteresis

**Feature**: 1231-quota-rate-hysteresis
**Created**: 2026-03-21

## Summary

Add hysteresis (stability window) to quota tracker reduced-rate mode transitions. Require N consecutive DynamoDB failures before entering reduced-rate mode and N consecutive successes before exiting. Prevents oscillation during DynamoDB connectivity flapping.

## What Changes

| File | Description |
|------|-------------|
| `src/lambdas/shared/quota_tracker.py` | Add hysteresis counters, `_record_dynamo_success/failure()` functions, update mode transition callers |
| `tests/unit/test_quota_tracker_hysteresis.py` | New test file for hysteresis behavior |

## Key Design Decisions

1. **Counter-based hysteresis** (not time-window): Simpler, deterministic, testable
2. **Same threshold for entry and exit**: `QUOTA_RATE_STABILITY_THRESHOLD` (default 3)
3. **Configurable via env var**: Allows tuning without code changes
4. **Module-level globals**: Consistent with existing `_reduced_rate_mode` pattern

## Quick Verification

```bash
# Run hysteresis tests
python -m pytest tests/unit/test_quota_tracker_hysteresis.py -v

# Run all quota tracker tests (backward compatibility)
python -m pytest tests/unit/shared/test_quota_tracker.py tests/unit/shared/test_quota_tracker_threadsafe.py tests/unit/test_quota_tracker_atomic.py -v

# Full validation
make validate && make test-local
```

## Configuration

| Env Var | Default | Description |
|---------|---------|-------------|
| `QUOTA_RATE_STABILITY_THRESHOLD` | `3` | Consecutive events required for mode transition |
