# Implementation Plan: Timeseries Integration Test Suite

**Branch**: `1016-timeseries-integration-test` | **Date**: 2025-12-22 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `/specs/1016-timeseries-integration-test/spec.md`

## Summary

Implement a comprehensive integration test suite for the timeseries pipeline using LocalStack DynamoDB. The tests validate the complete data flow from sentiment score ingestion through write fanout to all 8 resolution buckets, query operations with time ordering, partial bucket detection, and OHLC aggregation accuracy.

## Technical Context

**Language/Version**: Python 3.13 (project standard)
**Primary Dependencies**: pytest, boto3, freezegun, LocalStack DynamoDB
**Storage**: DynamoDB (timeseries table with PK: ticker#resolution, SK: bucket timestamp)
**Testing**: pytest with LocalStack fixtures from `tests/integration/conftest.py`
**Target Platform**: CI/CD pipeline (GitHub Actions) + local development
**Project Type**: Single project - serverless Lambda architecture
**Performance Goals**: Test suite completes in <60 seconds
**Constraints**: LocalStack-only (no real AWS in tests), deterministic time handling
**Scale/Scope**: 4 test classes covering fanout, query, partial bucket, and OHLC

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Gate | Status | Evidence |
|------|--------|----------|
| Unit Tests vs Integration Tests distinction | PASS | Integration tests use real LocalStack resources, not mocks |
| LocalStack for integration tests | PASS | Uses existing `tests/integration/conftest.py` fixtures |
| Deterministic time handling | PASS | Will use freezegun for time-dependent tests |
| No flaky dates | PASS | Fixed historical timestamps used throughout |
| Test isolation | PASS | Table setup/teardown per test class |
| 80% coverage threshold | PASS | Target timeseries pipeline code |

**Constitution Sections Applied**:
- Section 7: Testing & Validation (Environment matrix, Integration tests with real dev resources)
- Amendment 1.5: Deterministic Time Handling (freezegun, fixed dates)

## Project Structure

### Documentation (this feature)

```text
specs/1016-timeseries-integration-test/
├── plan.md              # This file
├── spec.md              # Feature specification
├── research.md          # Phase 0 output
├── data-model.md        # Phase 1 output (test fixtures)
├── quickstart.md        # Phase 1 output (running tests)
├── contracts/           # Phase 1 output (test oracle definitions)
│   └── test-oracle.yaml # Expected outputs for test inputs
└── checklists/
    └── requirements.md  # Validation checklist
```

### Source Code (repository root)

```text
tests/
├── integration/
│   ├── conftest.py                      # LocalStack fixtures (existing)
│   └── timeseries/                      # NEW: Timeseries test module
│       ├── __init__.py
│       ├── conftest.py                  # Timeseries-specific fixtures
│       └── test_timeseries_pipeline.py  # Integration test suite

src/
├── lib/
│   └── timeseries/                      # Existing library (test targets)
│       ├── models.py                    # Resolution, SentimentScore, etc.
│       ├── bucket.py                    # floor_to_bucket, calculate_progress
│       ├── aggregation.py               # aggregate_ohlc
│       └── fanout.py                    # generate_fanout_items, write_fanout
```

**Structure Decision**: Tests placed in `tests/integration/timeseries/` to follow existing organization pattern (see `tests/integration/ohlc/`, `tests/integration/ingestion/`).

## Complexity Tracking

No constitution violations. Implementation is straightforward:
- Uses existing LocalStack fixtures
- Tests existing timeseries library code
- Follows established integration test patterns

---

## Phase 0: Research Findings

### RQ-001: LocalStack DynamoDB Table Creation Pattern

**Decision**: Use class-scoped fixtures for table lifecycle

**Rationale**:
- Table creation is slow (~2s per table in LocalStack)
- Tests within same class share table for performance
- Teardown ensures test isolation between classes
- Pattern already used in `tests/integration/ohlc/test_happy_path.py`

**Alternative Considered**: Session-scoped table shared by all tests
- Rejected: Risk of test pollution, harder to isolate failures

### RQ-002: Time Mocking Strategy for Partial Buckets

**Decision**: Use freezegun with fixed timestamps per constitution Amendment 1.5

**Rationale**:
- `@freeze_time("2024-01-02T10:37:30Z")` provides deterministic time
- Allows testing partial bucket at 50% progress exactly
- Compatible with datetime.now(timezone.utc) pattern
- Already a project dependency

**Alternative Considered**: Manual time injection via parameters
- Rejected: More boilerplate, less realistic testing

### RQ-003: Test Data Generation Approach

**Decision**: Use deterministic fixtures with known values

**Rationale**:
- Constitution requires synthetic test data (Section 7)
- Fixed ticker symbols (AAPL, TSLA) for reproducibility
- Fixed sentiment values ([0.6, 0.9, 0.3, 0.7]) for OHLC verification
- ISO8601 timestamps for CodeQL compatibility

**Alternative Considered**: Hypothesis property-based testing
- Deferred: Good for edge cases but adds complexity; can add later

### RQ-004: Query Interface for Testing

**Decision**: Call `write_fanout` and `query_timeseries` directly

**Rationale**:
- Integration tests target the library code, not Lambda handlers
- Direct function calls are faster than HTTP invocation
- Matches existing integration test patterns in codebase
- Lambda handler integration is covered in E2E tests

**Alternative Considered**: Invoke Lambda functions via LocalStack
- Rejected: Slower, more complex setup, overkill for library testing

### RQ-005: Assertion Strategy for OHLC Values

**Decision**: Use pytest.approx for float comparisons

**Rationale**:
- Sentiment scores are floats (0.0-1.0)
- Floating point comparison needs tolerance
- `pytest.approx(0.7, rel=0.001)` prevents false failures
- Standard pytest pattern

---

## Phase 1: Design Artifacts

### Architecture Overview

```
┌──────────────────────────────────────────────────────────────────┐
│                    Integration Test Suite                         │
├──────────────────────────────────────────────────────────────────┤
│                                                                   │
│  ┌─────────────────────────────────────────────────────────────┐ │
│  │                  Test Fixtures (conftest.py)                 │ │
│  │                                                              │ │
│  │  timeseries_table ──► LocalStack DynamoDB                   │ │
│  │  sample_scores ──────► List[SentimentScore]                 │ │
│  │  assert_eventually ──► Eventually-consistent helper         │ │
│  │                                                              │ │
│  └─────────────────────────────────────────────────────────────┘ │
│                              │                                    │
│                              ▼                                    │
│  ┌─────────────────────────────────────────────────────────────┐ │
│  │              Test Classes (test_timeseries_pipeline.py)      │ │
│  │                                                              │ │
│  │  TestWriteFanout                                             │ │
│  │    ├── test_fanout_creates_8_resolution_items               │ │
│  │    ├── test_partition_key_format                            │ │
│  │    └── test_bucket_timestamps_aligned                       │ │
│  │                                                              │ │
│  │  TestQueryOrdering                                           │ │
│  │    ├── test_query_returns_ascending_order                   │ │
│  │    ├── test_out_of_order_insert_returns_sorted              │ │
│  │    └── test_empty_range_returns_empty_list                  │ │
│  │                                                              │ │
│  │  TestPartialBucket                                           │ │
│  │    ├── test_current_bucket_flagged_partial                  │ │
│  │    ├── test_progress_percentage_calculated                  │ │
│  │    └── test_complete_bucket_not_partial                     │ │
│  │                                                              │ │
│  │  TestOHLCAggregation                                         │ │
│  │    ├── test_ohlc_values_correct                             │ │
│  │    ├── test_label_counts_aggregated                         │ │
│  │    └── test_avg_and_count_calculated                        │ │
│  │                                                              │ │
│  └─────────────────────────────────────────────────────────────┘ │
│                              │                                    │
│                              ▼                                    │
│  ┌─────────────────────────────────────────────────────────────┐ │
│  │                Target Code (src/lib/timeseries/)             │ │
│  │                                                              │ │
│  │  fanout.py ───────► generate_fanout_items(), write_fanout() │ │
│  │  bucket.py ───────► floor_to_bucket(), calculate_progress() │ │
│  │  aggregation.py ──► aggregate_ohlc()                        │ │
│  │  models.py ───────► Resolution, SentimentScore, etc.        │ │
│  │                                                              │ │
│  └─────────────────────────────────────────────────────────────┘ │
│                              │                                    │
│                              ▼                                    │
│  ┌─────────────────────────────────────────────────────────────┐ │
│  │                 LocalStack DynamoDB                          │ │
│  │                                                              │ │
│  │  Table: test-timeseries-{test_run_id}                       │ │
│  │  PK: {ticker}#{resolution}  (e.g., AAPL#5m)                 │ │
│  │  SK: {bucket_timestamp}     (e.g., 2024-01-02T10:35:00Z)    │ │
│  │                                                              │ │
│  └─────────────────────────────────────────────────────────────┘ │
│                                                                   │
└──────────────────────────────────────────────────────────────────┘
```

### Key Test Scenarios

| User Story | Test Class | Tests | Validation |
|------------|------------|-------|------------|
| US1: Write Fanout | TestWriteFanout | 3 | FR-003, FR-004, FR-005 |
| US2: Query Ordering | TestQueryOrdering | 3 | FR-006 |
| US3: Partial Bucket | TestPartialBucket | 3 | FR-007 |
| US4: OHLC Aggregation | TestOHLCAggregation | 3 | FR-008 |

### Test Data Oracle

Fixed inputs with deterministic outputs:

```yaml
# Test Oracle: Fanout
input:
  ticker: "AAPL"
  value: 0.75
  label: "positive"
  timestamp: "2024-01-02T10:35:47Z"

expected:
  item_count: 8
  partition_keys:
    - "AAPL#1m"
    - "AAPL#5m"
    - "AAPL#10m"
    - "AAPL#1h"
    - "AAPL#3h"
    - "AAPL#6h"
    - "AAPL#12h"
    - "AAPL#24h"
  bucket_timestamps:
    1m: "2024-01-02T10:35:00Z"
    5m: "2024-01-02T10:35:00Z"
    10m: "2024-01-02T10:30:00Z"
    1h: "2024-01-02T10:00:00Z"
    3h: "2024-01-02T09:00:00Z"
    6h: "2024-01-02T06:00:00Z"
    12h: "2024-01-02T00:00:00Z"
    24h: "2024-01-02T00:00:00Z"

# Test Oracle: OHLC
input:
  scores: [0.6, 0.9, 0.3, 0.7]
  labels: ["positive", "neutral", "positive", "negative"]

expected:
  open: 0.6
  high: 0.9
  low: 0.3
  close: 0.7
  avg: 0.625
  count: 4
  label_counts:
    positive: 2
    neutral: 1
    negative: 1
```

---

## Phase 1 Complete

**Artifacts Generated**:
1. `plan.md` - This implementation plan
2. `research.md` - Research findings (5 questions resolved)
3. `data-model.md` - Test fixture definitions
4. `contracts/test-oracle.yaml` - Expected test outputs
5. `quickstart.md` - How to run the tests

**Next Step**: Run `/speckit.tasks` to generate task breakdown
