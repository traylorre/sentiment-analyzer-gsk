# Feature Specification: 096-sse-routing-fix

**Branch**: `096-sse-routing-fix` | **Date**: 2025-12-12

## Problem Statement

SSE E2E tests are failing because the API client routes config-specific stream endpoints to the wrong Lambda:
- `/api/v2/stream` → SSE Lambda ✅
- `/api/v2/configurations/{id}/stream` → Dashboard Lambda ❌

The Dashboard Lambda uses BUFFERED mode, which causes timeouts for streaming requests.

## Root Cause

In `tests/e2e/helpers/api_client.py` line 312-314:
```python
effective_url = (
    self.sse_url if path.startswith("/api/v2/stream") else self.base_url
)
```

The `startswith("/api/v2/stream")` check doesn't match `/api/v2/configurations/{id}/stream`.

## Solution

Change routing logic to detect any path containing `/stream`:
```python
effective_url = (
    self.sse_url if "/stream" in path else self.base_url
)
```

## Scope

| In Scope | Out of Scope |
|----------|--------------|
| Fix SSE URL routing in api_client.py | Lambda configuration changes |
| Update routing comment | New SSE endpoints |

## Success Criteria

| ID | Criterion | Verification |
|----|-----------|--------------|
| SC-001 | SSE tests pass in pipeline | Integration tests succeed |
| SC-002 | Config stream routes to SSE Lambda | `/api/v2/configurations/{id}/stream` uses sse_url |
| SC-003 | Non-stream routes unchanged | Regular endpoints still use base_url |

## Technical Details

**File**: `tests/e2e/helpers/api_client.py`
**Line**: 312-314
**Change**: 1 condition modification

### Before
```python
effective_url = (
    self.sse_url if path.startswith("/api/v2/stream") else self.base_url
)
```

### After
```python
effective_url = (
    self.sse_url if "/stream" in path else self.base_url
)
```

## Clarifications

### Session 2025-12-12

No critical ambiguities. Fix is straightforward string matching change.

## Dependencies

- Blocks: Preprod Integration Tests passing
