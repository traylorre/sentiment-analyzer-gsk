# Fix Self-Healing Composite Key Bug

## Problem Statement

The self-healing module in the ingestion Lambda fails to retrieve full item data from DynamoDB because it only provides the partition key (`source_id`) to GetItem, but the table uses a composite primary key (`source_id` + `timestamp`).

### Evidence

CloudWatch logs show repeated "Failed to get full item" warnings:
```
2025-12-20T16:37:49.236Z [WARNING] Failed to get full item
2025-12-20T16:37:49.245Z [WARNING] Failed to get full item
... (100+ occurrences per invocation)
```

Despite 466 pending items in DynamoDB older than 1 hour, self-healing reports:
```json
{
  "items_found": 0,
  "items_republished": 0
}
```

### Root Cause

The `get_full_items()` function in `self_healing.py` line 198-199:
```python
response = table.get_item(
    Key={"source_id": source_id},  # Missing timestamp
)
```

The DynamoDB table `preprod-sentiment-items` has:
- Partition Key (PK): `source_id`
- Sort Key (SK): `timestamp`

GetItem requires BOTH keys for a composite primary key.

### Why GSI Query Works But GetItem Fails

1. The `by_status` GSI query succeeds and returns items with `source_id`, `timestamp`, `status`
2. GSI uses `KEYS_ONLY` projection, so full item data is not available
3. GetItem is called to fetch full item data (text_for_analysis, matched_tickers, etc.)
4. GetItem fails because only `source_id` is provided, not `source_id` + `timestamp`

## User Stories

### P0: Self-Healing Retrieves Full Item Data
As a system operator, I need self-healing to successfully retrieve full item data from DynamoDB so that stale pending items can be republished to SNS for analysis.

## Functional Requirements

### FR-001: Use Composite Key for GetItem
The `get_full_items()` function MUST provide both `source_id` and `timestamp` when calling DynamoDB GetItem.

**Acceptance Criteria:**
- GetItem Key includes both `source_id` and `timestamp` from GSI response
- No "Failed to get full item" warnings in CloudWatch logs
- Items are successfully retrieved when they exist

### FR-002: Handle Missing Timestamp Gracefully
If an item from the GSI response is missing the `timestamp` attribute, the function MUST skip that item and log a warning.

**Acceptance Criteria:**
- Items without timestamp are skipped, not causing exceptions
- Warning logged with source_id for debugging
- Processing continues for remaining items

### FR-003: Maintain Existing Filter Logic
The existing logic to filter out items that already have a `sentiment` attribute MUST be preserved.

**Acceptance Criteria:**
- Items with sentiment attribute are still excluded
- Debug log still generated for skipped items

## Success Criteria

| Metric | Target |
|--------|--------|
| SC-001 | Self-healing finds >0 items when pending items exist older than threshold |
| SC-002 | Self-healing successfully republishes stale items to SNS |
| SC-003 | Dashboard shows sentiment data within 10 minutes of fix deployment |
| SC-004 | Zero "Failed to get full item" warnings for valid items |

## Out of Scope

- Changing GSI projection type (would require infrastructure change)
- Changing table primary key design (would require migration)
- Modifying deduplication logic

## Technical Context

### Affected File
- `src/lambdas/ingestion/self_healing.py` - `get_full_items()` function

### DynamoDB Table Schema
- Table: `preprod-sentiment-items`
- PK: `source_id` (String)
- SK: `timestamp` (String, ISO8601 format)

### GSI Schema
- GSI: `by_status`
- Hash Key: `status`
- Range Key: `timestamp`
- Projection: `KEYS_ONLY` (returns source_id, timestamp, status)

## Test Requirements

### Unit Tests
- Test GetItem called with both source_id and timestamp
- Test handling of missing timestamp in GSI response
- Test existing sentiment filter logic preserved
