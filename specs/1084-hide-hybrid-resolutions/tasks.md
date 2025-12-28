# Implementation Tasks: Hide Hybrid Resolution Buckets

**Branch**: `1084-hide-hybrid-resolutions` | **Created**: 2025-12-28

## Phase 1: Implementation

- [X] T001 [US1] Filter UNIFIED_RESOLUTIONS by exact:true in renderSelector()
- [X] T002 [US1] Validate saved resolution is exact in loadSavedResolution()
- [X] T003 [US1] Add Feature 1084 comment for traceability

## Phase 2: Testing

- [X] T004 Create static analysis test for exact-only resolutions

## Phase 3: Verification

- [ ] T005 Deploy and verify only 4 buttons appear (1m, 5m, 1h, Day)
- [ ] T006 Verify clicking each button updates both charts correctly

## Dependencies

```text
T001 → T002 → T003 → T004 → T005 → T006
```

## Notes

- Existing `exact` property already defined in config.js
- Default resolution '1h' is already exact - no change needed
- Minimal code change: add `.filter(r => r.exact !== false)` to button render
