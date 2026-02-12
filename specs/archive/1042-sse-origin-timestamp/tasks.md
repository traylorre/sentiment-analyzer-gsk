# Tasks: SSE Origin Timestamp

**Feature**: 1042-sse-origin-timestamp
**Date**: 2025-12-23

## Task List

### T001: Rename timestamp to origin_timestamp in HeartbeatEventData

**File**: `src/lambdas/dashboard/sse.py`
**Line**: ~96
**Change**: Rename `timestamp` field to `origin_timestamp`

**Before**:
```python
class HeartbeatEventData(BaseModel):
    """Payload for heartbeat events (FR-004)."""

    timestamp: datetime = Field(default_factory=lambda: datetime.now(UTC))
    connections: int = Field(ge=0)
```

**After**:
```python
class HeartbeatEventData(BaseModel):
    """Payload for heartbeat events (FR-004)."""

    origin_timestamp: datetime = Field(default_factory=lambda: datetime.now(UTC))
    connections: int = Field(ge=0)
```

**Acceptance**: Field renamed, model still validates

---

### T002: Rename timestamp to origin_timestamp in MetricsEventData

**File**: `src/lambdas/dashboard/sse.py`
**Line**: ~80
**Change**: Rename `timestamp` field to `origin_timestamp`

**Before**:
```python
class MetricsEventData(BaseModel):
    """Payload for metrics events (FR-009)."""
    # ... other fields ...
    timestamp: datetime = Field(default_factory=lambda: datetime.now(UTC))
```

**After**:
```python
class MetricsEventData(BaseModel):
    """Payload for metrics events (FR-009)."""
    # ... other fields ...
    origin_timestamp: datetime = Field(default_factory=lambda: datetime.now(UTC))
```

**Acceptance**: Field renamed, model still validates

---

### T003: Verify no other references to old field name

**Command**:
```bash
grep -r "\.timestamp" src/ tests/ --include="*.py" | grep -v origin_timestamp
```

**Acceptance**: No references to `.timestamp` on SSE event objects remain

---

### T004: Run unit tests

**Command**:
```bash
pytest tests/unit/ -v
```

**Acceptance**: All unit tests pass

---

## Summary

| Task | Description | Status |
|------|-------------|--------|
| T001 | Rename HeartbeatEventData.timestamp | pending |
| T002 | Rename MetricsEventData.timestamp | pending |
| T003 | Verify no stale references | pending |
| T004 | Run unit tests | pending |
