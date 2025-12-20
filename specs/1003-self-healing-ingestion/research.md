# Research: Self-Healing Ingestion

**Feature**: 1003-self-healing-ingestion
**Date**: 2025-12-20

## Research Tasks

### R1: DynamoDB GSI Query Pattern for Pending Items

**Question**: How to efficiently query pending items older than 1 hour using by_status GSI?

**Findings**:
- `by_status` GSI exists with `status` (hash key) and `timestamp` (range key)
- Projection type is `KEYS_ONLY` - only returns `source_id`, `status`, `timestamp`
- For full item data, need to do `GetItem` on base table after GSI query

**Decision**: Use two-step approach:
1. Query `by_status` GSI with `status = "pending"` and `timestamp < (now - 1 hour)`
2. Batch GetItem on base table to retrieve full item data (specifically `text_for_analysis`, `matched_tickers`)

**Rationale**:
- GSI query is efficient (O(result) not O(table))
- KEYS_ONLY projection saves storage/cost but requires secondary lookup
- Alternative (adding `text_for_analysis` to projection) would significantly increase GSI storage

**Alternatives Considered**:
1. Scan with filter - Rejected: O(table) performance
2. Change GSI projection to ALL - Rejected: Increases cost, requires Terraform change
3. New GSI with ALL projection - Rejected: Over-engineering for <100 stale items

### R2: Stale Threshold Determination

**Question**: What threshold separates "normal pipeline latency" from "stuck item"?

**Findings**:
- Analysis Lambda triggered via SNS (not EventBridge)
- Normal SNS delivery: <1 second
- Analysis Lambda cold start + inference: ~10 seconds
- DynamoDB write latency: <50ms
- End-to-end normal latency: <30 seconds

**Decision**: Use 1 hour threshold

**Rationale**:
- Provides 120x safety margin over normal latency
- Avoids false positives during high-load periods
- Allows manual investigation before auto-retry
- Matches user expectation from spec

**Alternatives Considered**:
1. 15 minutes - Rejected: Too aggressive, may cause duplicate processing during load spikes
2. 24 hours - Rejected: Dashboard would show stale data too long
3. Configurable via env var - Deferred: Can add later if needed

### R3: SNS Batch Publishing Pattern

**Question**: How to efficiently publish republished items to SNS?

**Findings**:
- Existing pattern in `handler.py` at line 917: `_publish_sns_batch()`
- Uses `sns_client.publish_batch()` with max 10 messages per call
- Already handles partial failures with retry logic
- Returns count of successfully published messages

**Decision**: Reuse existing `_publish_sns_batch()` function

**Rationale**:
- Code reuse, no duplication
- Already tested and working in production
- Handles edge cases (partial failures, retries)

**Alternatives Considered**:
1. New publish function - Rejected: Duplication
2. SQS instead of SNS - Rejected: Analysis Lambda already wired to SNS

### R4: Item Detection Strategy

**Question**: How to detect items that need self-healing?

**Findings**:
- Items have `status` field: "pending" or "analyzed"
- Items get `sentiment` field only after Analysis Lambda processes them
- Stale items have: `status = "pending"` AND `sentiment` attribute missing AND `timestamp < 1 hour ago`

**Decision**: Query by_status GSI for `status = "pending"`, filter by timestamp, check for missing sentiment

**Rationale**:
- `by_status` GSI optimized for this query pattern
- Timestamp range key allows efficient filtering
- Sentiment attribute check confirms item wasn't partially processed

**Implementation**:
```python
# Query GSI for pending items older than 1 hour
response = table.query(
    IndexName="by_status",
    KeyConditionExpression="status = :status AND #ts < :threshold",
    ExpressionAttributeNames={"#ts": "timestamp"},
    ExpressionAttributeValues={
        ":status": "pending",
        ":threshold": (datetime.now(UTC) - timedelta(hours=1)).isoformat(),
    },
)
```

### R5: Idempotency Considerations

**Question**: What happens if an item is republished multiple times?

**Findings**:
- Analysis Lambda checks if item already has sentiment before processing
- If sentiment exists, Lambda skips processing (no-op)
- SNS deduplication not needed since Lambda handles it

**Decision**: Rely on Analysis Lambda idempotency, no additional safeguards needed

**Rationale**:
- Existing idempotency in Analysis Lambda is sufficient
- Adding more checks would be over-engineering
- Items that fail analysis repeatedly will keep getting retried (desired behavior)

### R6: Batching Strategy

**Question**: How to handle >100 stale items without overwhelming SNS?

**Findings**:
- SNS batch limit: 10 messages per publish_batch call
- Analysis Lambda concurrency: 25 (from PR #424)
- Processing time per item: ~5 seconds

**Decision**: Batch 100 items max per self-healing run

**Rationale**:
- 100 items = 10 SNS publish_batch calls = reasonable Lambda execution time
- 25 concurrent Analysis Lambda invocations can handle 100 items in ~20 seconds
- Remaining stale items processed in next run (5 min interval)

## Summary

| Decision | Choice | Confidence |
|----------|--------|------------|
| Query strategy | by_status GSI + GetItem | High |
| Stale threshold | 1 hour | High |
| SNS publishing | Reuse _publish_sns_batch | High |
| Batch size | 100 items max | Medium |
| Idempotency | Rely on Analysis Lambda | High |
