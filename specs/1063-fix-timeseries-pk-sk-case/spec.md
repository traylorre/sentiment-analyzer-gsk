# Feature Specification: Fix Timeseries API DynamoDB Key Case Mismatch

**Feature Branch**: `1063-fix-timeseries-pk-sk-case`
**Created**: 2025-12-26
**Status**: Draft
**Input**: Investigation of 500 errors on `/api/v2/timeseries/{ticker}?resolution=6h`

## Problem Statement

The timeseries API endpoint returns HTTP 500 Internal Server Error for all resolution values. CloudWatch logs show:

```
botocore.exceptions.ClientError: An error occurred (ValidationException) when calling the Query operation: Query condition missed key schema element: PK
```

**Root Cause**: The `timeseries.py` query code uses lowercase attribute names (`pk`, `sk`) in the KeyConditionExpression and ExclusiveStartKey, but the `preprod-sentiment-timeseries` DynamoDB table uses uppercase attribute names (`PK`, `SK`).

**Evidence**:
- Table schema: `{"AttributeName": "PK", "KeyType": "HASH"}, {"AttributeName": "SK", "KeyType": "RANGE"}`
- Sample item: `"PK": {"S": "TSM#12h"}, "SK": {"S": "2025-12-15T00:00:00+00:00"}`
- Code at timeseries.py:254: `key_condition = "pk = :pk"` (lowercase)
- Code at timeseries.py:285: `{"pk": pk, "sk": cursor}` (lowercase)

## User Scenarios & Testing

### User Story 1 - View Sentiment Timeseries (Priority: P1)

As a user viewing the sentiment dashboard, I want to see sentiment trend data for any ticker at various time resolutions so that I can analyze sentiment patterns over time.

**Why this priority**: This is a blocking bug preventing the demo URL from displaying any sentiment trend data.

**Independent Test**: Make API requests to `/api/v2/timeseries/AAPL?resolution=6h` and verify 200 response.

**Acceptance Scenarios**:

1. **Given** the timeseries endpoint is deployed, **When** I request `/api/v2/timeseries/AAPL?resolution=6h` with valid auth, **Then** I receive HTTP 200 with sentiment bucket data
2. **Given** the timeseries endpoint is deployed, **When** I request `/api/v2/timeseries/AAPL?resolution=1h` with valid auth, **Then** I receive HTTP 200 with sentiment bucket data
3. **Given** there is no data for a ticker, **When** I request `/api/v2/timeseries/INVALID?resolution=6h`, **Then** I receive HTTP 200 with empty buckets array

---

### User Story 2 - Frontend Sentiment Trend Chart (Priority: P1)

As a user on the frontend dashboard, I want to see the Sentiment Trend chart populate with data when I select different resolutions.

**Why this priority**: The frontend component is built but shows "Failed to load timeseries data: Error: HTTP 500".

**Independent Test**: Load the dashboard and verify the sentiment trend chart displays data.

**Acceptance Scenarios**:

1. **Given** I am on the dashboard, **When** the page loads, **Then** the sentiment trend chart displays data without errors
2. **Given** I am on the dashboard, **When** I change the resolution selector, **Then** the chart refreshes with the new resolution data

---

### Edge Cases

- What happens when cursor pagination is used? - Fix ExclusiveStartKey to use uppercase keys
- What happens when time range filtering is used? - Should work since filter uses expression values, not attribute names

## Requirements

### Functional Requirements

- **FR-001**: System MUST query DynamoDB using correct uppercase attribute names `PK` and `SK`
- **FR-002**: System MUST support all resolution values: 1m, 5m, 10m, 1h, 3h, 6h, 12h, 24h
- **FR-003**: System MUST support pagination with cursor parameter
- **FR-004**: System MUST return empty buckets array (not error) when no data exists

### Technical Requirements

- **TR-001**: Update KeyConditionExpression at timeseries.py:254 to use `PK` instead of `pk`
- **TR-002**: Update ExclusiveStartKey at timeseries.py:285 to use `{"PK": pk, "SK": cursor}`
- **TR-003**: Verify `_item_to_bucket` function reads items correctly (may use lowercase internally)
- **TR-004**: Add unit test coverage for DynamoDB query construction

## Success Criteria

### Measurable Outcomes

- **SC-001**: API requests with any resolution return HTTP 200 (currently returns 500)
- **SC-002**: All supported resolutions (1m, 5m, 10m, 1h, 3h, 6h, 12h, 24h) return valid responses
- **SC-003**: Pagination with cursor parameter works correctly
- **SC-004**: Unit tests pass for query construction
- **SC-005**: Frontend sentiment trend chart displays data

## Implementation Notes

The fix requires changing the key names in the query:

```python
# Line 254 - KeyConditionExpression
# Current (broken):
key_condition = "pk = :pk"
# Fixed:
key_condition = "PK = :pk"

# Lines 261, 266, 270 - Sort key conditions
# Current (broken):
key_condition += " AND sk BETWEEN :start AND :end"
# Fixed:
key_condition += " AND SK BETWEEN :start AND :end"

# Line 285 - ExclusiveStartKey
# Current (broken):
query_kwargs["ExclusiveStartKey"] = {"pk": pk, "sk": cursor}
# Fixed:
query_kwargs["ExclusiveStartKey"] = {"PK": pk, "SK": cursor}
```

Note: The `_item_to_bucket` function at line 294 reads items using lowercase keys from the response - this may also need updating if DynamoDB returns uppercase keys.

## Files to Modify

- `src/lambdas/dashboard/timeseries.py` - Fix key case at lines 254, 261, 266, 270, 285, and verify _item_to_bucket
- `tests/unit/dashboard/test_timeseries.py` - Add/update tests for DynamoDB query construction
