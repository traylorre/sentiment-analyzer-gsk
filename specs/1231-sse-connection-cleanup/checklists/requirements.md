# Specification Quality Checklist: SSE Connection Leak Cleanup

**Purpose**: Validate specification completeness and quality before proceeding to planning
**Created**: 2026-03-21
**Feature**: [spec.md](../spec.md)

## Content Quality

- [x] No implementation details (languages, frameworks, APIs)
- [x] Focused on user value and business needs
- [x] Written for non-technical stakeholders
- [x] All mandatory sections completed

## Requirement Completeness

- [x] No [NEEDS CLARIFICATION] markers remain
- [x] Requirements are testable and unambiguous
- [x] Success criteria are measurable
- [x] Success criteria are technology-agnostic (no implementation details)
- [x] All acceptance scenarios are defined
- [x] Edge cases are identified
- [x] Scope is clearly bounded
- [x] Dependencies and assumptions identified

## Feature Readiness

- [x] All functional requirements have clear acceptance criteria
- [x] User scenarios cover primary flows
- [x] Feature meets measurable outcomes defined in Success Criteria
- [x] No implementation details leak into specification

## Adversarial Review Findings

### Leak Scenario Verification

The connection leak is **confirmed real**. Evidence from source code review:

1. `connection.py` (line 79-287): `ConnectionManager` has NO TTL, NO `last_activity` tracking, NO cleanup sweep, NO stale connection detection.
2. `handler.py` (lines 298-311, 430-446): `connection_manager.release()` is called in `finally` blocks, but `finally` does NOT execute on SIGKILL/OOM.
3. `stream.py` (line 322-343): `_check_deadline_flush()` handles *approaching* deadlines but not force-kills. If the deadline check doesn't fire (e.g., Lambda killed with >3s remaining), the connection is orphaned.
4. `connection.py` (line 287): The global `connection_manager = ConnectionManager()` persists across warm invocations -- orphaned entries accumulate.

### No Existing Mitigation

- No TTL mechanism exists anywhere in `connection.py`
- No periodic cleanup or sweep
- No `last_activity` or `last_heartbeat` tracking on `SSEConnection`
- The `connected_at` field exists but is never used for expiry
- The `get_status()` method shows `connections` count but gives no indication of staleness

### Risk Assessment

- **False positive risk**: Low. The 2x heartbeat multiplier provides ample margin. A healthy connection sends heartbeats every 30s, so it must be silent for 60s to be swept.
- **Backward compatibility risk**: None. All changes are additive -- new fields with defaults, new methods, existing API unchanged.
- **Performance risk**: Negligible. Sweep iterates max 100 entries under an existing lock. This adds microseconds to `acquire()`.

## Notes

- All items pass. Spec is ready for implementation.
- This is a reliability fix, not a feature. The primary value is preventing cascading failures under chaos.
- Zero changes to handler.py or stream.py -- the fix is entirely within ConnectionManager internals.
