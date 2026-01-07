# Tasks: Remove X-User-ID from OHLC API

**Feature**: 001-1167-remove-x

## Task List

- [x] **T1**: Update fetchOHLCData - remove userId param and X-User-ID header
- [x] **T2**: Update fetchSentimentHistory - remove userId param and X-User-ID header
- [x] **T3**: Update useChartData hook - remove userId, gate on accessToken
- [x] **T4**: Update auth-store.test.ts - remove X-User-ID test
- [x] **T5**: Run typecheck and fix any remaining callers
- [x] **T6**: Run tests and verify all pass
- [x] **T7**: Grep verify no X-User-ID in production code

## Completion Summary

All tasks completed. X-User-ID header completely removed from OHLC API calls.
- Typecheck: PASS
- Tests: PASS (57 tests)
- Production code grep: Only comments remain (documenting removal)
