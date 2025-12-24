# Tasks: Fix SSE Lambda Environment Variable Mismatch

**Feature ID**: 1045
**Input**: spec.md

## Phase 1: Code Fix

- [x] T001 Update polling.py line 42: change `DYNAMODB_TABLE` to `SENTIMENTS_TABLE`
- [x] T002 Update polling.py lines 44-47: change error message to reference `SENTIMENTS_TABLE`
- [x] T003 Update polling.py line 247: fix comment to reference `SENTIMENTS_TABLE`

## Phase 2: Test Updates

- [x] T004 Update test_polling.py: change env var patches from `DYNAMODB_TABLE` to `SENTIMENTS_TABLE`
- [x] T005 Update test_polling.py: rename test `test_missing_dynamodb_table_raises_error` to `test_missing_sentiments_table_raises_error`
- [x] T006 Run SSE Lambda unit tests: 183 passed

## Phase 3: Deployment

- [ ] T007 Commit and push changes
- [ ] T008 Create PR with auto-merge
- [ ] T009 Verify E2E tests pass after deployment

## Dependencies

- T001-T003 are the code changes
- T004-T005 are the test updates
- T006 verifies the changes
- T007-T009 are sequential deployment steps

## Estimated Complexity

- **Very Low**: 6 lines of code changed, 4 test lines updated
- **Files Modified**: 2 (polling.py, test_polling.py)
