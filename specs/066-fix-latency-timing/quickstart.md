# Quickstart: Fix Latency Timing in Traffic Generator

**Feature**: 066-fix-latency-timing
**Date**: 2025-12-08

## Prerequisites

- Python 3.13
- pytest installed
- Repository cloned and on branch `066-fix-latency-timing`

## Implementation Steps

### Step 1: Verify Current Failure (Optional)

```bash
# Run the failing test to confirm the issue
pytest tests/unit/interview/test_traffic_generator.py::TestTrafficGenerator::test_very_long_latency -v
```

**Expected**: Test may fail intermittently with negative latency values.

### Step 2: Apply Fix

Edit `interview/traffic_generator.py`:

**Line 124**: Change `time.time()` to `time.monotonic()`
```python
# Before
start = time.time()

# After
start = time.monotonic()
```

**Line 135**: Change `time.time()` to `time.monotonic()`
```python
# Before
latency = (time.time() - start) * 1000

# After
latency = (time.monotonic() - start) * 1000
```

### Step 3: Validate Fix

#### 3a. Run Target Test Multiple Times

```bash
# Run test 10 times to verify consistency
for i in {1..10}; do
    pytest tests/unit/interview/test_traffic_generator.py::TestTrafficGenerator::test_very_long_latency -v
    echo "Run $i complete"
done
```

**Expected**: All 10 runs pass with positive latency values.

#### 3b. Run Full Test Suite

```bash
# Ensure no regression
make test-unit
```

**Expected**: All tests pass.

#### 3c. Verify No time.time() Remains

```bash
# Check for remaining time.time() usage in target file
grep -n "time.time()" interview/traffic_generator.py
```

**Expected**: No matches found.

## Success Criteria Verification

| Criterion | Command | Expected Result |
|-----------|---------|-----------------|
| SC-001: Test passes consistently | `pytest ...test_very_long_latency -v` x10 | 10/10 pass |
| SC-002: No time.time() in file | `grep "time.time()" interview/traffic_generator.py` | No output |
| SC-003: No regression | `make test-unit` | All pass |
| SC-004: Positive latency | Check test output | `total_latency_ms >= 100` |

## Commit and Push

```bash
# After validation passes
git add interview/traffic_generator.py
git commit -S -m "fix(066): Replace time.time() with time.monotonic() for latency measurement

Fixes test_very_long_latency failing with negative latency (-1362ms) due to
system clock adjustments affecting time.time(). time.monotonic() is immune
to clock changes and provides reliable elapsed time measurement.

Fixes: Constitution Amendment 1.5 violation (Deterministic Time Handling)
"

git push -u origin 066-fix-latency-timing
```
