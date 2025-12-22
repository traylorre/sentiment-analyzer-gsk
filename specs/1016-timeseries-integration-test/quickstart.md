# Quickstart: Timeseries Integration Tests

**Feature**: 1016-timeseries-integration-test
**Date**: 2025-12-22

## Prerequisites

1. **LocalStack running**: Integration tests require LocalStack for DynamoDB emulation

```bash
# Start LocalStack (if not already running)
make localstack-up

# Verify LocalStack is healthy
curl http://localhost:4566/_localstack/health
```

2. **Dependencies installed**:

```bash
# Install development dependencies
pip install -r requirements-dev.txt

# Verify freezegun is available
python -c "import freezegun; print('OK')"
```

## Running the Tests

### Run All Timeseries Integration Tests

```bash
# Full test suite
pytest tests/integration/timeseries/ -v

# With coverage
pytest tests/integration/timeseries/ -v --cov=src/lib/timeseries --cov-report=term-missing
```

### Run Individual Test Classes

```bash
# Write fanout tests only
pytest tests/integration/timeseries/test_timeseries_pipeline.py::TestWriteFanout -v

# Query ordering tests only
pytest tests/integration/timeseries/test_timeseries_pipeline.py::TestQueryOrdering -v

# Partial bucket tests only
pytest tests/integration/timeseries/test_timeseries_pipeline.py::TestPartialBucket -v

# OHLC aggregation tests only
pytest tests/integration/timeseries/test_timeseries_pipeline.py::TestOHLCAggregation -v
```

### Run with Debug Output

```bash
# Show print statements and detailed logs
pytest tests/integration/timeseries/ -v -s --log-cli-level=DEBUG
```

## Expected Output

```
tests/integration/timeseries/test_timeseries_pipeline.py::TestWriteFanout::test_fanout_creates_8_resolution_items PASSED
tests/integration/timeseries/test_timeseries_pipeline.py::TestWriteFanout::test_partition_key_format PASSED
tests/integration/timeseries/test_timeseries_pipeline.py::TestWriteFanout::test_bucket_timestamps_aligned PASSED
tests/integration/timeseries/test_timeseries_pipeline.py::TestQueryOrdering::test_query_returns_ascending_order PASSED
tests/integration/timeseries/test_timeseries_pipeline.py::TestQueryOrdering::test_out_of_order_insert_returns_sorted PASSED
tests/integration/timeseries/test_timeseries_pipeline.py::TestQueryOrdering::test_empty_range_returns_empty_list PASSED
tests/integration/timeseries/test_timeseries_pipeline.py::TestPartialBucket::test_current_bucket_flagged_partial PASSED
tests/integration/timeseries/test_timeseries_pipeline.py::TestPartialBucket::test_progress_percentage_calculated PASSED
tests/integration/timeseries/test_timeseries_pipeline.py::TestPartialBucket::test_complete_bucket_not_partial PASSED
tests/integration/timeseries/test_timeseries_pipeline.py::TestOHLCAggregation::test_ohlc_values_correct PASSED
tests/integration/timeseries/test_timeseries_pipeline.py::TestOHLCAggregation::test_label_counts_aggregated PASSED
tests/integration/timeseries/test_timeseries_pipeline.py::TestOHLCAggregation::test_avg_and_count_calculated PASSED

========================= 12 passed in 45.23s =========================
```

## Troubleshooting

### LocalStack Not Running

```
Error: Could not connect to the endpoint URL: "http://localhost:4566"
```

**Fix**: Start LocalStack with `make localstack-up` or `docker-compose up localstack -d`

### Table Creation Timeout

```
Error: Table creation timed out
```

**Fix**: Increase timeout in conftest.py or restart LocalStack

### Import Errors

```
ModuleNotFoundError: No module named 'src.lib.timeseries'
```

**Fix**: Ensure you're running from the repository root with `PYTHONPATH=.`:

```bash
PYTHONPATH=. pytest tests/integration/timeseries/ -v
```

## Coverage Requirements

Target: 80% coverage of `src/lib/timeseries/`

```bash
# Generate coverage report
pytest tests/integration/timeseries/ --cov=src/lib/timeseries --cov-report=html

# View report
open htmlcov/index.html
```

## CI Integration

These tests run automatically in GitHub Actions as part of the integration test job:

```yaml
# .github/workflows/pr-checks.yml
integration-tests:
  runs-on: ubuntu-latest
  services:
    localstack:
      image: localstack/localstack:latest
      ports:
        - 4566:4566
  steps:
    - uses: actions/checkout@v4
    - name: Run integration tests
      run: pytest tests/integration/ -v --cov=src
```

## Test Data Reference

See `contracts/test-oracle.yaml` for:
- Expected fanout partition keys and timestamps
- Expected OHLC values for test score sequences
- Expected partial bucket progress calculations
- Expected TTL values per resolution
