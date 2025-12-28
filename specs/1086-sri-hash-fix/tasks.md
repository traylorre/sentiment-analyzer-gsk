# Implementation Tasks: Fix SRI Hash for Date Adapter

**Branch**: `1086-sri-hash-fix` | **Created**: 2025-12-28

## Phase 1: Implementation

- [X] T001 [US1] Update integrity hash for chartjs-adapter-date-fns in index.html
- [X] T002 [US1] Add Feature 1086 comment for traceability

## Phase 2: Verification

- [ ] T003 Deploy and verify Price Chart loads without console errors
- [ ] T004 Verify pan/zoom functionality works on Price Chart

## Dependencies

```text
T001 → T002 → T003 → T004
```

## Notes

- Correct hash verified via: `curl -sL <url> | openssl dgst -sha384 -binary | openssl base64 -A`
- Hash: `cVMg8E3QFwTvGCDuK+ET4PD341jF3W8nO1auiXfuZNQkzbUUiBGLsIQUE+b1mxws`
