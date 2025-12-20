# Implementation Plan

## Overview

Fix the `get_full_items()` function in `self_healing.py` to use the composite primary key (source_id + timestamp) when calling DynamoDB GetItem.

## Phase 1: Code Fix

### Task 1.1: Update GetItem Key
**File:** `src/lambdas/ingestion/self_healing.py`

Change line ~198-199 from:
```python
response = table.get_item(
    Key={"source_id": source_id},
```

To:
```python
response = table.get_item(
    Key={"source_id": source_id, "timestamp": timestamp},
```

### Task 1.2: Extract Timestamp from Item
Before the GetItem call, extract timestamp from the GSI response item:
```python
source_id = item.get("source_id")
timestamp = item.get("timestamp")
if not source_id or not timestamp:
    logger.warning("Skipping item missing required keys", ...)
    continue
```

### Task 1.3: Update ProjectionExpression
Remove `#ts` from ProjectionExpression since we already have timestamp from GSI:
```python
ProjectionExpression=(
    "source_id, source_type, text_for_analysis, "
    "matched_tickers, sentiment, metadata"
),
```
Remove the ExpressionAttributeNames for timestamp as well.

## Phase 2: Unit Tests

### Task 2.1: Update Existing Tests
Update `tests/unit/lambdas/ingestion/test_self_healing.py` to verify:
- GetItem is called with both source_id and timestamp
- Mock responses include timestamp in Key

### Task 2.2: Add Missing Timestamp Test
Add test case for when GSI returns item without timestamp:
- Verify warning is logged
- Verify item is skipped
- Verify processing continues

## Phase 3: Validation

### Task 3.1: Run Unit Tests
```bash
python -m pytest tests/unit/lambdas/ingestion/test_self_healing.py -v
```

### Task 3.2: Verify Linting
```bash
ruff check src/lambdas/ingestion/self_healing.py
```

## Dependencies

- No infrastructure changes required
- No new dependencies

## Risks

| Risk | Mitigation |
|------|------------|
| Existing tests may mock single-key GetItem | Update mocks to expect composite key |
| GSI may not return timestamp for some items | Add null check with warning log |
