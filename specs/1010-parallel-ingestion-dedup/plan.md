# Implementation Plan: Parallel Ingestion with Cross-Source Deduplication

**Branch**: `1010-parallel-ingestion-dedup` | **Date**: 2025-12-21 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `/specs/1010-parallel-ingestion-dedup/spec.md`

## Summary

Enable parallel news ingestion from Tiingo and Finnhub with cross-source deduplication. Currently, ingestion is sequential (Tiingo then Finnhub per ticker) and uses source-specific article IDs for dedup, causing duplicate database entries when both sources report the same news. This feature implements headline-based deduplication keys, parallel adapter calls using ThreadPoolExecutor, and multi-source attribution tracking while maintaining thread-safety for quota tracking and circuit breakers.

## Technical Context

**Language/Version**: Python 3.13
**Primary Dependencies**: boto3, httpx, concurrent.futures (stdlib)
**Storage**: DynamoDB (sentiment-items table with conditional writes)
**Testing**: pytest with moto for AWS mocking, responses for HTTP mocking
**Target Platform**: AWS Lambda (Python 3.13 runtime)
**Project Type**: Serverless event-driven (Lambda + SNS + DynamoDB)
**Performance Goals**: Parallel fetch + dedup < 500ms for 10 tickers (excluding network latency)
**Constraints**: Lambda 15-minute timeout, 10GB max memory, Tiingo 500/month rate limit, Finnhub 60/min rate limit
**Scale/Scope**: 13 tickers, 2 sources, ~100-200 articles/day expected

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Requirement | Status | Notes |
|-------------|--------|-------|
| **Deduplication** (Section 1) | COMPLIANT | Enhancing from source-specific to cross-source headline-based dedup |
| **Rate Limits** (Section 3) | COMPLIANT | Existing quota tracker + circuit breaker; will add thread-safety |
| **Conditional Writes** (Section 5) | COMPLIANT | Using DynamoDB ConditionExpression for atomic upserts |
| **TLS/Secrets** (Section 3) | COMPLIANT | API keys in Secrets Manager, HTTPS for all API calls |
| **Testing** (Section 7) | COMPLIANT | Unit tests with mocks, E2E with synthetic data |
| **Idempotency** (Section 5) | COMPLIANT | Conditional writes prevent duplicate inserts |
| **DLQ/Observability** (Section 5-6) | COMPLIANT | Existing CloudWatch + X-Ray integration |
| **GPG Signing** (Section 8) | COMPLIANT | All commits signed per pre-push requirements |

**Gate Status**: PASS - No violations requiring justification

## Project Structure

### Documentation (this feature)

```text
specs/1010-parallel-ingestion-dedup/
├── plan.md              # This file
├── research.md          # Phase 0 output
├── data-model.md        # Phase 1 output
├── quickstart.md        # Phase 1 output
├── contracts/           # Phase 1 output (metrics endpoint spec)
└── tasks.md             # Phase 2 output (/speckit.tasks command)
```

### Source Code (repository root)

```text
src/
├── lambdas/
│   ├── ingestion/
│   │   ├── handler.py           # Main Lambda handler (modify for parallel)
│   │   ├── parallel_fetcher.py  # NEW: ThreadPoolExecutor wrapper
│   │   └── dedup.py             # NEW: Cross-source dedup key generator
│   └── shared/
│       ├── adapters/
│       │   ├── tiingo.py        # Existing adapter (minor field mapping)
│       │   └── finnhub.py       # Existing adapter (minor field mapping)
│       ├── utils/
│       │   └── dedup.py         # Existing (activate headline-based dedup)
│       ├── quota_tracker.py     # Add thread-safety (threading.Lock)
│       └── circuit_breaker.py   # Add thread-safety (threading.Lock)
└── lib/
    └── threading_utils.py       # NEW: Thread-safe queue, lock helpers

tests/
├── unit/
│   ├── ingestion/
│   │   ├── test_parallel_fetcher.py   # NEW: Parallel execution tests
│   │   └── test_cross_source_dedup.py # NEW: Headline-based dedup tests
│   └── shared/
│       ├── test_quota_tracker_threadsafe.py  # NEW: Thread-safety tests
│       └── test_circuit_breaker_threadsafe.py # NEW: Thread-safety tests
└── integration/
    └── ingestion/
        └── test_parallel_ingestion_flow.py  # NEW: E2E parallel flow
```

**Structure Decision**: Extends existing Lambda structure. New modules added for parallel execution (`parallel_fetcher.py`) and cross-source dedup (`dedup.py` in ingestion). Thread-safety utilities centralized in `src/lib/threading_utils.py`.

## Complexity Tracking

No violations requiring justification. Design uses:
- Standard library `concurrent.futures.ThreadPoolExecutor` (no new dependencies)
- Thread-safe wrappers with `threading.Lock` (minimal complexity)
- Existing DynamoDB conditional write patterns (proven atomic dedup)

## Architecture Design

### Data Flow (Parallel Ingestion)

```
┌─────────────────────────────────────────────────────────────────────┐
│                        Ingestion Lambda                             │
│                                                                     │
│  ┌─────────────┐     ┌─────────────────────────────────────────┐   │
│  │ EventBridge │────▶│ ThreadPoolExecutor (max_workers=4)      │   │
│  │  (5 min)    │     │                                         │   │
│  └─────────────┘     │  ┌─────────┐  ┌─────────┐  ┌─────────┐ │   │
│                      │  │ Ticker1 │  │ Ticker2 │  │ Ticker3 │ │   │
│                      │  │ Tiingo  │  │ Tiingo  │  │ Finnhub │ │   │
│                      │  │ Finnhub │  │ Finnhub │  │         │ │   │
│                      │  └────┬────┘  └────┬────┘  └────┬────┘ │   │
│                      │       │            │            │       │   │
│                      └───────┼────────────┼────────────┼───────┘   │
│                              │            │            │           │
│                              ▼            ▼            ▼           │
│                      ┌───────────────────────────────────────┐     │
│                      │    Cross-Source Dedup (headline+date) │     │
│                      │    Thread-safe Queue Collection       │     │
│                      └───────────────────┬───────────────────┘     │
│                                          │                         │
│                                          ▼                         │
│                      ┌───────────────────────────────────────┐     │
│                      │   DynamoDB Conditional Upsert         │     │
│                      │   (atomic, thread-safe by design)     │     │
│                      └───────────────────┬───────────────────┘     │
│                                          │                         │
│                                          ▼                         │
│                      ┌───────────────────────────────────────┐     │
│                      │   SNS Batch Publish (deduplicated)    │     │
│                      └───────────────────────────────────────┘     │
└─────────────────────────────────────────────────────────────────────┘
```

### Cross-Source Deduplication Key Design

```
dedup_key = SHA256(normalize(headline) + "|" + publish_date[:10])[:32]

normalize(headline):
  1. lowercase
  2. strip punctuation (keep alphanumeric + spaces)
  3. collapse multiple spaces
  4. trim leading/trailing whitespace

Example:
  Tiingo:  "Apple Reports Q4 Earnings Beat - Reuters"
  Finnhub: "Apple reports Q4 earnings beat"

  Both normalize to: "apple reports q4 earnings beat"
  dedup_key = SHA256("apple reports q4 earnings beat|2025-12-21")[:32]
  Result: Same key = same article = deduplicated
```

### DynamoDB Item Schema (Enhanced)

```python
{
    "source_id": "dedup:{dedup_key}",          # NEW: Cross-source key
    "timestamp": "2025-12-21T14:30:00+00:00",  # SK (ISO8601)
    "dedup_key": "abc123...",                  # 32-char hex
    "headline": "Apple Reports Q4 Earnings Beat",
    "normalized_headline": "apple reports q4 earnings beat",
    "sources": ["tiingo", "finnhub"],          # NEW: Multi-source array
    "source_attribution": {                    # NEW: Per-source metadata
        "tiingo": {
            "article_id": "12345",
            "url": "https://...",
            "crawl_timestamp": "2025-12-21T14:28:00Z",
            "original_headline": "Apple Reports Q4 Earnings Beat - Reuters"
        },
        "finnhub": {
            "article_id": "abc-def",
            "url": "https://...",
            "crawl_timestamp": "2025-12-21T14:29:00Z",
            "original_headline": "Apple reports Q4 earnings beat"
        }
    },
    "status": "pending",
    "sentiment": null,                         # Filled after analysis
    "matched_tickers": ["AAPL"],
    "metadata": {...},
    "ttl_timestamp": 1737500000                # 30-day TTL
}
```

### Thread-Safety Design

| Component | Thread-Safety Mechanism | Notes |
|-----------|------------------------|-------|
| QuotaTracker | `threading.Lock` around `record_call()` | Atomic counter increment |
| CircuitBreaker | `threading.Lock` around state transitions | Prevent race on failure_count |
| SNS Message Queue | `queue.Queue` instead of list | Thread-safe put/get |
| Error Collection | `queue.Queue` instead of list | Thread-safe error aggregation |
| DynamoDB Writes | Built-in (distributed service) | Conditional writes are atomic |

## Risk Mitigation

| Risk | Impact | Mitigation |
|------|--------|------------|
| Parallel calls exceed rate limits | API blocks/bans | Thread-safe quota tracker with pre-call check |
| Headline normalization too aggressive | False positive dedup | Tunable normalization, logging for review |
| ThreadPoolExecutor overhead | Lambda cold start slower | Lazy initialization, max 4 workers |
| Race condition in circuit breaker | Incorrect state | Lock-protected state transitions |
| Memory pressure from parallel articles | OOM | Bounded queue, streaming processing |

## TDD Implementation Requirements

### Test-First Order

| Order | Component | Test Suite | Canonical Source |
|-------|-----------|-----------|------------------|
| 1 | Headline Normalization | `test_headline_normalization.py` | FR-002 |
| 2 | Dedup Key Generation | `test_dedup_key_generation.py` | FR-001, FR-003 |
| 3 | Thread-Safe QuotaTracker | `test_quota_tracker_threadsafe.py` | FR-011 |
| 4 | Thread-Safe CircuitBreaker | `test_circuit_breaker_threadsafe.py` | FR-007 |
| 5 | Parallel Fetcher | `test_parallel_fetcher.py` | FR-006 |
| 6 | Cross-Source Upsert | `test_cross_source_dedup.py` | FR-009, FR-012 |
| 7 | Multi-Source Attribution | `test_source_attribution.py` | FR-004, FR-005 |
| 8 | Collision Metrics | `test_collision_metrics.py` | FR-010 |

### Failure Protocol

1. Write test that fails (RED)
2. Implement minimal code to pass (GREEN)
3. Refactor if needed (REFACTOR)
4. Run full suite to confirm no regressions
5. Commit with GPG signature
6. If test exposes design flaw, update plan.md before fixing

### Coverage Requirements

- 80% minimum for new code
- All edge cases from spec.md covered
- Thread-safety tests with concurrent execution
- Integration test with LocalStack DynamoDB
