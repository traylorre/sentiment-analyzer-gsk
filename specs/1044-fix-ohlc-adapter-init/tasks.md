# Tasks: Fix OHLC Adapter Initialization

**Feature ID**: 1044
**Input**: spec.md

## Phase 1: Fix Adapter Initialization

- [x] T001 Update get_tiingo_adapter() to read TIINGO_SECRET_ARN from os.environ, fetch from Secrets Manager, and pass to TiingoAdapter() constructor in src/lambdas/dashboard/ohlc.py
- [x] T002 Update get_finnhub_adapter() to read FINNHUB_SECRET_ARN from os.environ, fetch from Secrets Manager, and pass to FinnhubAdapter() constructor in src/lambdas/dashboard/ohlc.py
- [x] T003 Add import for os module at top of src/lambdas/dashboard/ohlc.py (if not already present)
- [x] T004 Add graceful handling for missing API keys (log warning, raise HTTPException 503)

## Phase 2: Verification

- [x] T005 Verified TIINGO_SECRET_ARN is configured in infrastructure/terraform/main.tf (module.secrets.tiingo_secret_arn)
- [x] T006 Verified FINNHUB_SECRET_ARN is configured in infrastructure/terraform/main.tf (module.secrets.finnhub_secret_arn)
- [x] T007 Run existing unit tests to ensure no regressions: pytest tests/unit/dashboard/test_ohlc*.py -v (26 passed)

## Phase 3: Testing

- [ ] T008 Run make validate to verify no regressions
- [ ] T009 Manual E2E test: curl the OHLC endpoint after deployment and verify 200 response

## Additional Changes Made

- Added TIINGO_API_KEY and FINNHUB_API_KEY test environment variables to tests/conftest.py

## Dependencies

- T001 and T002 can run in parallel
- T003 must complete before T001 and T002 (import needed)
- T004 depends on T001 and T002
- T005 and T006 are informational checks, can run in parallel
- T007 depends on T001-T004
- T008 and T009 run last

## Estimated Complexity

- **Very Low**: 4 lines of code changed
- **Files Modified**: 1 (src/lambdas/dashboard/ohlc.py)
