# Research: SSE Origin Timestamp

**Date**: 2025-12-23

## Summary

No external research required. This is a field naming alignment between backend and frontend.

## Decision: Field Naming Strategy

**Decision**: Rename `timestamp` to `origin_timestamp` in SSE event Pydantic models

**Rationale**:
- The test code in `test_live_update_latency.py` specifically looks for `origin_timestamp` (line 163)
- The name `origin_timestamp` clearly indicates this is the server's origin time, not the client's receive time
- Matches the latency measurement pattern: `latency = receive_time - origin_time`

**Alternatives Considered**:
1. **Add `origin_timestamp` as alias** - Rejected because it creates redundancy
2. **Update test to use `timestamp`** - Rejected because `origin_timestamp` is semantically clearer
3. **Keep both fields** - Rejected because it's over-engineering for this use case

## Backward Compatibility Check

Searched codebase for SSE event timestamp field usage:

```bash
grep -r "\.timestamp" src/lambdas/dashboard/ --include="*.py"
```

Results:
- Only the Pydantic model definitions use the field
- No parsing code references the `timestamp` field name directly
- SSE events are JSON-serialized via `model_dump(mode="json")`, so consumers parse JSON

**Conclusion**: Renaming is safe. No backward compatibility concerns.
