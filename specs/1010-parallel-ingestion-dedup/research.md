# Research: Parallel Ingestion with Cross-Source Deduplication

**Feature**: 1010-parallel-ingestion-dedup
**Date**: 2025-12-21

## Research Questions

### RQ-1: Best Approach for Cross-Source Article Deduplication

**Decision**: Headline-based SHA256 hash with date normalization

**Rationale**:
- Source-specific article IDs (Tiingo vs Finnhub) are not correlated
- Same Reuters/AP wire story gets different IDs from each aggregator
- Headline is the most stable identifier across sources
- Adding publish date prevents false positives for recurring headlines

**Alternatives Considered**:
| Approach | Pros | Cons | Rejected Because |
|----------|------|------|------------------|
| URL matching | Unique per article | Different URLs per aggregator | Same content, different hosts |
| Content hash | Exact match | Minor content differences cause false negatives | Too strict |
| Fuzzy matching (Levenshtein) | Catches paraphrasing | Slow, complex, false positives | Overkill for wire stories |
| Source article ID | Simple | Not correlated across sources | Current problem |

**Implementation**:
```python
def normalize_headline(headline: str) -> str:
    """Normalize headline for cross-source comparison."""
    import re
    text = headline.lower()
    text = re.sub(r'[^\w\s]', '', text)  # Remove punctuation
    text = re.sub(r'\s+', ' ', text)      # Collapse whitespace
    return text.strip()

def generate_dedup_key(headline: str, publish_date: str) -> str:
    """Generate cross-source deduplication key."""
    import hashlib
    normalized = normalize_headline(headline)
    date_part = publish_date[:10]  # YYYY-MM-DD only
    content = f"{normalized}|{date_part}"
    return hashlib.sha256(content.encode()).hexdigest()[:32]
```

---

### RQ-2: Thread-Safety for Rate Limiting in Parallel Context

**Decision**: Use `threading.Lock` with minimal critical section

**Rationale**:
- Python GIL provides some safety but not for I/O-bound operations
- QuotaTracker.record_call() mutates shared counter
- CircuitBreaker.record_failure() mutates shared state
- Lock overhead is negligible vs API call latency (~100ms)

**Alternatives Considered**:
| Approach | Pros | Cons | Rejected Because |
|----------|------|------|------------------|
| asyncio | Native concurrency | Requires full async rewrite | Massive scope change |
| multiprocessing | True parallelism | Process overhead, state sharing hard | Overkill for I/O |
| threading.Lock | Simple, proven | GIL limits CPU parallelism | N/A - chosen |
| No locking (YOLO) | Simple | Race conditions, corrupted state | Unsafe |

**Implementation Pattern**:
```python
import threading

class ThreadSafeQuotaTracker:
    def __init__(self, wrapped_tracker):
        self._tracker = wrapped_tracker
        self._lock = threading.Lock()

    def record_call(self, source: str, count: int = 1) -> bool:
        with self._lock:
            return self._tracker.record_call(source, count)

    def check_quota(self, source: str) -> bool:
        with self._lock:
            return self._tracker.check_quota(source)
```

---

### RQ-3: Parallel Execution Strategy for Lambda

**Decision**: ThreadPoolExecutor with max 4 workers

**Rationale**:
- Lambda vCPU allocation scales with memory (1769 MB = 1 vCPU)
- I/O-bound workload (API calls) benefits from threading
- 4 workers balances parallelism vs memory overhead
- stdlib `concurrent.futures` - no new dependencies

**Alternatives Considered**:
| Approach | Pros | Cons | Rejected Because |
|----------|------|------|------------------|
| Sequential (current) | Simple | Slow (N × T per ticker) | Current problem |
| asyncio.gather | Efficient for I/O | Requires async adapters | Major refactor |
| multiprocessing.Pool | True parallelism | Lambda subprocess limits | Not suitable for Lambda |
| ThreadPoolExecutor | Simple, effective | GIL limits CPU | N/A - chosen (I/O-bound) |

**Implementation Pattern**:
```python
from concurrent.futures import ThreadPoolExecutor, as_completed

def fetch_all_sources_parallel(tickers: list[str], adapters: dict) -> list[Article]:
    results = []
    with ThreadPoolExecutor(max_workers=4) as executor:
        futures = {}
        for ticker in tickers:
            for source, adapter in adapters.items():
                future = executor.submit(adapter.fetch_news, ticker)
                futures[future] = (ticker, source)

        for future in as_completed(futures):
            ticker, source = futures[future]
            try:
                articles = future.result()
                results.extend(articles)
            except Exception as e:
                logger.error(f"Fetch failed: {source}/{ticker}: {e}")
    return results
```

---

### RQ-4: DynamoDB Upsert Pattern for Multi-Source Attribution

**Decision**: Conditional update with SET list_append and map merge

**Rationale**:
- Need to add source to existing article without overwriting
- DynamoDB UpdateItem with ConditionExpression handles atomicity
- SET sources = list_append(sources, :new_source) for array
- SET source_attribution.#src = :attr for map

**Implementation Pattern**:
```python
def upsert_article_with_source(table, dedup_key, source, attribution):
    """Add source to existing article or create new."""
    try:
        # Try update first (article exists)
        table.update_item(
            Key={"source_id": f"dedup:{dedup_key}", "timestamp": timestamp},
            UpdateExpression="SET sources = list_append(if_not_exists(sources, :empty), :src), "
                           "source_attribution.#source = :attr",
            ExpressionAttributeNames={"#source": source},
            ExpressionAttributeValues={
                ":src": [source],
                ":attr": attribution,
                ":empty": []
            },
            ConditionExpression="attribute_exists(source_id)"
        )
        return "updated"
    except ClientError as e:
        if e.response['Error']['Code'] == 'ConditionalCheckFailedException':
            # Article doesn't exist, create new
            table.put_item(Item={
                "source_id": f"dedup:{dedup_key}",
                "timestamp": timestamp,
                "sources": [source],
                "source_attribution": {source: attribution},
                # ... other fields
            })
            return "created"
        raise
```

---

### RQ-5: Collision Metrics Implementation

**Decision**: In-memory counters with CloudWatch PutMetricData

**Rationale**:
- Lambda execution is short-lived (~seconds)
- Aggregate metrics per invocation, publish at end
- CloudWatch provides alerting on threshold breach
- No external metrics service required

**Metrics to Track**:
| Metric | Type | Dimension | Alert Threshold |
|--------|------|-----------|-----------------|
| ArticlesFetched | Counter | source | N/A |
| ArticlesStored | Counter | - | N/A |
| CollisionsDetected | Counter | - | N/A |
| CollisionRate | Gauge | - | >40% or <5% |
| DedupLatencyMs | Timer | - | >100ms |

**Implementation Pattern**:
```python
class IngestionMetrics:
    def __init__(self):
        self.articles_fetched = {"tiingo": 0, "finnhub": 0}
        self.articles_stored = 0
        self.collisions_detected = 0

    def record_fetch(self, source: str, count: int):
        self.articles_fetched[source] += count

    def record_collision(self):
        self.collisions_detected += 1

    @property
    def collision_rate(self) -> float:
        total = sum(self.articles_fetched.values())
        return self.collisions_detected / total if total > 0 else 0.0

    def publish_to_cloudwatch(self, cloudwatch_client):
        # Batch put metrics
        pass
```

---

## Resolved Clarifications

All technical decisions resolved through research. No outstanding NEEDS CLARIFICATION markers.

## References

- [AWS Lambda Concurrency](https://docs.aws.amazon.com/lambda/latest/dg/configuration-concurrency.html)
- [DynamoDB Conditional Writes](https://docs.aws.amazon.com/amazondynamodb/latest/developerguide/Expressions.ConditionExpressions.html)
- [Python ThreadPoolExecutor](https://docs.python.org/3/library/concurrent.futures.html)
- [CloudWatch PutMetricData](https://docs.aws.amazon.com/AmazonCloudWatch/latest/APIReference/API_PutMetricData.html)
